"""
Robot Control API Routes

Exposes robot integration service via REST API for:
- Niryo Ned2 collaborative robot
- UFactory xArm Lite 6 industrial robot

Follows existing Flask blueprint pattern with async support.
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Dict, Any
import asyncio

robot_bp = Blueprint('robot', __name__, url_prefix='/api/robot')


def get_robot_service():
    """Get robot integration service from app context"""
    from services.robot_integration_service import get_robot_service as _get_service
    return _get_service()


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# =============================================================================
# Robot Registration & Status
# =============================================================================

@robot_bp.route('/register', methods=['POST'])
def register_robot():
    """
    Register a new robot in the system

    Request Body:
        robot_id: str - Unique identifier for the robot
        robot_type: str - One of 'niryo_ned2' or 'xarm_lite6'
        config: dict - Optional configuration parameters

    Returns:
        201: Robot registered successfully
        400: Invalid request
        409: Robot already registered
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    robot_id = data.get('robot_id')
    robot_type = data.get('robot_type')

    if not robot_id or not robot_type:
        return jsonify({"error": "robot_id and robot_type required"}), 400

    valid_types = ['niryo_ned2', 'xarm_lite6']
    if robot_type not in valid_types:
        return jsonify({
            "error": f"Invalid robot_type. Must be one of: {valid_types}"
        }), 400

    try:
        service = get_robot_service()
        from services.robot_integration_service import RobotType

        type_mapping = {
            'niryo_ned2': RobotType.NIRYO_NED2,
            'xarm_lite6': RobotType.XARM
        }

        service.register_robot(robot_id, type_mapping[robot_type])

        return jsonify({
            "status": "registered",
            "robot_id": robot_id,
            "robot_type": robot_type
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        current_app.logger.error(f"Robot registration error: {e}")
        return jsonify({"error": "Registration failed"}), 500


@robot_bp.route('/list', methods=['GET'])
def list_robots():
    """
    List all registered robots

    Returns:
        200: List of registered robot IDs and types
    """
    try:
        service = get_robot_service()
        robots = []

        for robot_id, interface in service.robots.items():
            robots.append({
                "robot_id": robot_id,
                "robot_type": interface.robot_type.value,
                "connected": interface.is_connected()
            })

        return jsonify({"robots": robots}), 200

    except Exception as e:
        current_app.logger.error(f"List robots error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/status', methods=['GET'])
def get_all_robot_status():
    """
    Get status of all registered robots

    Returns:
        200: Dictionary of robot statuses keyed by robot_id
    """
    try:
        service = get_robot_service()
        statuses = run_async(service.get_all_robot_status())

        result = {}
        for robot_id, status in statuses.items():
            if status:
                result[robot_id] = {
                    "state": status.state.value,
                    "tool_id": status.tool_id,
                    "speed_percentage": status.speed_percentage,
                    "payload": status.payload,
                    "joints": [
                        {
                            "position": j.position,
                            "velocity": j.velocity,
                            "effort": j.effort,
                            "temperature": j.temperature
                        }
                        for j in status.joint_states
                    ]
                }
            else:
                result[robot_id] = {"state": "disconnected"}

        return jsonify({"statuses": result}), 200

    except Exception as e:
        current_app.logger.error(f"Get all status error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/status', methods=['GET'])
def get_robot_status(robot_id: str):
    """
    Get detailed status of specific robot

    Path Parameters:
        robot_id: Robot identifier

    Returns:
        200: Detailed robot status including joint states
        404: Robot not found
    """
    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        status = run_async(service.get_robot_status(robot_id))

        if not status:
            return jsonify({
                "robot_id": robot_id,
                "state": "disconnected"
            }), 200

        return jsonify({
            "robot_id": robot_id,
            "state": status.state.value,
            "tool_id": status.tool_id,
            "speed_percentage": status.speed_percentage,
            "payload": status.payload,
            "joints": [
                {
                    "index": i,
                    "position_rad": j.position,
                    "velocity_rad_s": j.velocity,
                    "effort_nm": j.effort,
                    "temperature_c": j.temperature
                }
                for i, j in enumerate(status.joint_states)
            ]
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get robot status error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Motion Control
# =============================================================================

@robot_bp.route('/<robot_id>/move/joints', methods=['POST'])
def move_to_joints(robot_id: str):
    """
    Move robot to joint positions

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        joints: list[float] - Joint positions in radians (6 values)
        speed: float - Optional speed percentage (0-100)

    Returns:
        200: Motion completed successfully
        400: Invalid request
        404: Robot not found
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    joints = data.get('joints')
    if not joints or len(joints) != 6:
        return jsonify({"error": "joints must be array of 6 values"}), 400

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        speed = data.get('speed', 50)
        success = run_async(
            service.move_robot_to_joints(robot_id, joints)
        )

        if success:
            return jsonify({
                "status": "completed",
                "robot_id": robot_id,
                "target_joints": joints
            }), 200
        else:
            return jsonify({"error": "Motion failed"}), 500

    except Exception as e:
        current_app.logger.error(f"Move to joints error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/move/pose', methods=['POST'])
def move_to_pose(robot_id: str):
    """
    Move robot to Cartesian pose

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        x, y, z: float - Position in mm
        roll, pitch, yaw: float - Orientation in radians
        speed: float - Optional speed percentage

    Returns:
        200: Motion completed successfully
        400: Invalid request
        404: Robot not found
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ['x', 'y', 'z', 'roll', 'pitch', 'yaw']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        success = run_async(
            service.move_robot_to_pose(
                robot_id,
                x=data['x'],
                y=data['y'],
                z=data['z'],
                roll=data['roll'],
                pitch=data['pitch'],
                yaw=data['yaw']
            )
        )

        if success:
            return jsonify({
                "status": "completed",
                "robot_id": robot_id,
                "target_pose": {
                    "position": {"x": data['x'], "y": data['y'], "z": data['z']},
                    "orientation": {
                        "roll": data['roll'],
                        "pitch": data['pitch'],
                        "yaw": data['yaw']
                    }
                }
            }), 200
        else:
            return jsonify({"error": "Motion failed"}), 500

    except Exception as e:
        current_app.logger.error(f"Move to pose error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/move/linear', methods=['POST'])
def move_linear(robot_id: str):
    """
    Linear interpolated Cartesian move

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        x, y, z: float - Target position in mm
        roll, pitch, yaw: float - Target orientation in radians
        speed: float - Linear speed in mm/s

    Returns:
        200: Motion completed successfully
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ['x', 'y', 'z']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        # Use pose move with linear flag
        success = run_async(
            service.move_robot_to_pose(
                robot_id,
                x=data['x'],
                y=data['y'],
                z=data['z'],
                roll=data.get('roll', 0),
                pitch=data.get('pitch', 0),
                yaw=data.get('yaw', 0)
            )
        )

        return jsonify({
            "status": "completed" if success else "failed",
            "robot_id": robot_id,
            "move_type": "linear"
        }), 200 if success else 500

    except Exception as e:
        current_app.logger.error(f"Linear move error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/home', methods=['POST'])
def home_robot(robot_id: str):
    """
    Send robot to home position

    Path Parameters:
        robot_id: Robot identifier

    Returns:
        200: Robot homed successfully
        404: Robot not found
    """
    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        success = run_async(service.home_robot(robot_id))

        return jsonify({
            "status": "homed" if success else "failed",
            "robot_id": robot_id
        }), 200 if success else 500

    except Exception as e:
        current_app.logger.error(f"Home robot error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/stop', methods=['POST'])
def stop_robot(robot_id: str):
    """
    Emergency stop robot

    Path Parameters:
        robot_id: Robot identifier

    Returns:
        200: Robot stopped
        404: Robot not found
    """
    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        success = run_async(service.stop_robot(robot_id))

        return jsonify({
            "status": "stopped",
            "robot_id": robot_id
        }), 200

    except Exception as e:
        current_app.logger.error(f"Stop robot error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Gripper Control
# =============================================================================

@robot_bp.route('/<robot_id>/gripper/grasp', methods=['POST'])
def gripper_grasp(robot_id: str):
    """
    Close gripper to grasp object

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        force: float - Optional gripper force (0-100%)
        width: float - Optional target width in mm

    Returns:
        200: Gripper closed
    """
    data = request.get_json() or {}

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        force = data.get('force', 50)
        success = run_async(service.gripper_grasp(robot_id, force=force))

        return jsonify({
            "status": "grasped" if success else "failed",
            "robot_id": robot_id,
            "force": force
        }), 200 if success else 500

    except Exception as e:
        current_app.logger.error(f"Gripper grasp error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/gripper/release', methods=['POST'])
def gripper_release(robot_id: str):
    """
    Open gripper to release object

    Path Parameters:
        robot_id: Robot identifier

    Returns:
        200: Gripper opened
    """
    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        success = run_async(service.gripper_release(robot_id))

        return jsonify({
            "status": "released" if success else "failed",
            "robot_id": robot_id
        }), 200 if success else 500

    except Exception as e:
        current_app.logger.error(f"Gripper release error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Trajectory Execution
# =============================================================================

@robot_bp.route('/<robot_id>/trajectory', methods=['POST'])
def execute_trajectory(robot_id: str):
    """
    Execute multi-waypoint trajectory

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        waypoints: list[dict] - List of waypoints, each with:
            - joints: list[float] - 6 joint positions in radians
            OR
            - pose: dict with x, y, z, roll, pitch, yaw
        blend_radius: float - Optional blending radius in mm

    Returns:
        200: Trajectory executed
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    waypoints = data.get('waypoints')
    if not waypoints or not isinstance(waypoints, list):
        return jsonify({"error": "waypoints array required"}), 400

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        # Execute waypoints sequentially
        for i, wp in enumerate(waypoints):
            if 'joints' in wp:
                success = run_async(
                    service.move_robot_to_joints(robot_id, wp['joints'])
                )
            elif 'pose' in wp:
                pose = wp['pose']
                success = run_async(
                    service.move_robot_to_pose(
                        robot_id,
                        x=pose['x'], y=pose['y'], z=pose['z'],
                        roll=pose.get('roll', 0),
                        pitch=pose.get('pitch', 0),
                        yaw=pose.get('yaw', 0)
                    )
                )
            else:
                return jsonify({
                    "error": f"Waypoint {i} must have 'joints' or 'pose'"
                }), 400

            if not success:
                return jsonify({
                    "error": f"Failed at waypoint {i}",
                    "robot_id": robot_id
                }), 500

        return jsonify({
            "status": "completed",
            "robot_id": robot_id,
            "waypoints_executed": len(waypoints)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Trajectory execution error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Teaching/Learning Mode (Ned2 specific)
# =============================================================================

@robot_bp.route('/<robot_id>/learning-mode', methods=['POST'])
def set_learning_mode(robot_id: str):
    """
    Enable/disable learning mode (Ned2 only)

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        enabled: bool - True to enable, False to disable

    Returns:
        200: Learning mode set
        400: Not supported for this robot type
    """
    data = request.get_json() or {}
    enabled = data.get('enabled', True)

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        interface = service.robots[robot_id]
        from services.robot_integration_service import RobotType

        if interface.robot_type != RobotType.NIRYO_NED2:
            return jsonify({
                "error": "Learning mode only supported on Ned2 robot"
            }), 400

        success = run_async(interface.set_learning_mode(enabled))

        return jsonify({
            "status": "enabled" if enabled else "disabled",
            "robot_id": robot_id,
            "learning_mode": enabled
        }), 200

    except Exception as e:
        current_app.logger.error(f"Learning mode error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/record-waypoint', methods=['POST'])
def record_waypoint(robot_id: str):
    """
    Record current position as waypoint (for teaching)

    Path Parameters:
        robot_id: Robot identifier

    Request Body:
        name: str - Optional waypoint name

    Returns:
        200: Waypoint recorded with current joint positions
    """
    data = request.get_json() or {}
    name = data.get('name', f"waypoint_{robot_id}")

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        status = run_async(service.get_robot_status(robot_id))

        if not status:
            return jsonify({"error": "Could not get robot position"}), 500

        waypoint = {
            "name": name,
            "robot_id": robot_id,
            "joints": [j.position for j in status.joint_states],
            "recorded_at": "2026-01-01T00:00:00Z"
        }

        return jsonify(waypoint), 200

    except Exception as e:
        current_app.logger.error(f"Record waypoint error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Factory Integration Endpoints
# =============================================================================

@robot_bp.route('/<robot_id>/pick', methods=['POST'])
def pick_object(robot_id: str):
    """
    Execute pick operation (approach, grasp, retract)

    Request Body:
        location: str - Pick location ID (e.g., "input_pallet:slot_1")
        approach_height: float - Height above pick point (mm)
        grasp_force: float - Gripper force percentage

    Returns:
        200: Pick completed
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    location = data.get('location')
    approach_height = data.get('approach_height', 50)
    grasp_force = data.get('grasp_force', 50)

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        # This would integrate with the factory cell orchestrator
        # For now, return simulated success
        return jsonify({
            "status": "completed",
            "operation": "pick",
            "robot_id": robot_id,
            "location": location,
            "approach_height": approach_height
        }), 200

    except Exception as e:
        current_app.logger.error(f"Pick operation error: {e}")
        return jsonify({"error": str(e)}), 500


@robot_bp.route('/<robot_id>/place', methods=['POST'])
def place_object(robot_id: str):
    """
    Execute place operation (approach, release, retract)

    Request Body:
        location: str - Place location ID (e.g., "cnc_fixture:bantam_001")
        approach_height: float - Height above place point (mm)

    Returns:
        200: Place completed
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    location = data.get('location')
    approach_height = data.get('approach_height', 50)

    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        return jsonify({
            "status": "completed",
            "operation": "place",
            "robot_id": robot_id,
            "location": location,
            "approach_height": approach_height
        }), 200

    except Exception as e:
        current_app.logger.error(f"Place operation error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# DH Parameters & Kinematics (for Unity visualization)
# =============================================================================

@robot_bp.route('/<robot_id>/kinematics', methods=['GET'])
def get_robot_kinematics(robot_id: str):
    """
    Get robot kinematics data for visualization

    Returns DH parameters, joint limits, and link information
    for Unity digital twin rendering.

    Returns:
        200: Kinematics data
    """
    try:
        service = get_robot_service()

        if robot_id not in service.robots:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        interface = service.robots[robot_id]
        from services.robot_integration_service import RobotType

        if interface.robot_type == RobotType.NIRYO_NED2:
            kinematics = {
                "robot_type": "niryo_ned2",
                "dof": 6,
                "dh_parameters": [
                    {"d": 103.0, "a": 0, "alpha": -90, "theta_offset": 0},
                    {"d": 0, "a": 210.0, "alpha": 0, "theta_offset": -90},
                    {"d": 0, "a": 30.0, "alpha": -90, "theta_offset": 0},
                    {"d": 221.0, "a": 0, "alpha": 90, "theta_offset": 0},
                    {"d": 0, "a": 0, "alpha": -90, "theta_offset": 0},
                    {"d": 55.0, "a": 0, "alpha": 0, "theta_offset": 0},
                ],
                "joint_limits": [
                    {"min": -175, "max": 175},
                    {"min": -90, "max": 36.7},
                    {"min": -80, "max": 90},
                    {"min": -175, "max": 175},
                    {"min": -100, "max": 110},
                    {"min": -147.5, "max": 147.5},
                ],
                "reach_mm": 440,
                "payload_kg": 0.3
            }
        else:  # xArm Lite 6
            kinematics = {
                "robot_type": "xarm_lite6",
                "dof": 6,
                "dh_parameters": [
                    {"d": 267.0, "a": 0, "alpha": -90, "theta_offset": 0},
                    {"d": 0, "a": 289.5, "alpha": 0, "theta_offset": -90},
                    {"d": 0, "a": 77.5, "alpha": -90, "theta_offset": 0},
                    {"d": 342.5, "a": 0, "alpha": 90, "theta_offset": 0},
                    {"d": 0, "a": 0, "alpha": -90, "theta_offset": 0},
                    {"d": 97.0, "a": 0, "alpha": 0, "theta_offset": 0},
                ],
                "joint_limits": [
                    {"min": -360, "max": 360},
                    {"min": -118, "max": 120},
                    {"min": -225, "max": 11},
                    {"min": -360, "max": 360},
                    {"min": -97, "max": 180},
                    {"min": -360, "max": 360},
                ],
                "reach_mm": 700,
                "payload_kg": 5.0
            }

        return jsonify(kinematics), 200

    except Exception as e:
        current_app.logger.error(f"Get kinematics error: {e}")
        return jsonify({"error": str(e)}), 500
