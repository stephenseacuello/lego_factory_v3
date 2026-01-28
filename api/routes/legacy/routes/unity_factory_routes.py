"""
Unity Factory Digital Twin Routes

Extends existing Unity routes with factory-level visualization APIs
for the manufacturing cell digital twin.

Provides:
- Factory scene configuration
- Robot kinematics for animation
- Material flow tracking
- Real-time cell status
- Collision zone visualization
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Dict, Any, Optional
import asyncio

unity_factory_bp = Blueprint(
    'unity_factory',
    __name__,
    url_prefix='/api/unity/factory'
)


def get_factory_orchestrator():
    """Get factory cell orchestrator from app context"""
    from services.factory_cell_orchestrator import get_factory_orchestrator
    return get_factory_orchestrator()


def get_scene_config():
    """Get default factory scene configuration"""
    from schemas.unity_factory_scene import create_default_factory_scene
    return create_default_factory_scene()


# =============================================================================
# Scene Configuration
# =============================================================================

@unity_factory_bp.route('/scene', methods=['GET'])
def get_factory_scene():
    """
    Get complete factory scene configuration

    Returns the full scene setup for Unity to initialize the digital twin,
    including all machines, robots, pallets, sensors, and collision zones.

    Returns:
        200: Complete scene configuration
    """
    try:
        scene = get_scene_config()
        return jsonify(scene.to_dict()), 200

    except Exception as e:
        current_app.logger.error(f"Get scene error: {e}")
        return jsonify({"error": str(e)}), 500


@unity_factory_bp.route('/scene/assets', methods=['GET'])
def get_scene_assets():
    """
    Get all asset configurations (robots, CNC, pallets)

    Returns just the static asset definitions without dynamic state.

    Query Parameters:
        asset_type: Optional filter ("robot", "cnc", "pallet", "sensor")

    Returns:
        200: Asset configurations
    """
    asset_type = request.args.get('asset_type')

    try:
        scene = get_scene_config()

        assets = {
            "robots": [r.to_dict() for r in scene.robot_arms],
            "cnc_machines": [m.to_dict() for m in scene.cnc_machines],
            "pallets": [p.to_dict() for p in scene.pallets],
            "sensors": [s.to_dict() for s in scene.sensors],
            "collision_zones": [z.to_dict() for z in scene.collision_zones]
        }

        if asset_type:
            type_mapping = {
                "robot": "robots",
                "cnc": "cnc_machines",
                "pallet": "pallets",
                "sensor": "sensors",
                "zone": "collision_zones"
            }
            key = type_mapping.get(asset_type)
            if key:
                return jsonify({key: assets[key]}), 200
            else:
                return jsonify({
                    "error": f"Unknown asset_type: {asset_type}",
                    "valid_types": list(type_mapping.keys())
                }), 400

        return jsonify(assets), 200

    except Exception as e:
        current_app.logger.error(f"Get assets error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Robot Visualization
# =============================================================================

@unity_factory_bp.route('/robot/<robot_id>/kinematics', methods=['GET'])
def get_robot_kinematics(robot_id: str):
    """
    Get robot kinematics data for visualization

    Returns DH parameters, joint limits, and current joint states
    for Unity to compute forward kinematics and render the robot.

    Path Parameters:
        robot_id: Robot identifier

    Returns:
        200: Kinematics configuration and current state
        404: Robot not found
    """
    try:
        scene = get_scene_config()

        # Find robot in scene
        robot_config = None
        for robot in scene.robot_arms:
            if robot.robot_id == robot_id:
                robot_config = robot
                break

        if not robot_config:
            return jsonify({"error": f"Robot '{robot_id}' not found"}), 404

        # Get current joint state from orchestrator
        orchestrator = get_factory_orchestrator()
        current_joints = [0.0] * robot_config.num_joints

        if orchestrator.robot_service:
            try:
                loop = asyncio.new_event_loop()
                status = loop.run_until_complete(
                    orchestrator.robot_service.get_robot_status(robot_id)
                )
                loop.close()

                if status:
                    current_joints = [j.position for j in status.joint_states]
            except Exception:
                pass

        result = robot_config.to_dict()
        result["current_joints"] = current_joints

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(f"Get kinematics error: {e}")
        return jsonify({"error": str(e)}), 500


@unity_factory_bp.route('/robot/<robot_id>/trajectory', methods=['GET'])
def get_robot_trajectory(robot_id: str):
    """
    Get current trajectory for visualization

    Returns the planned trajectory (if any) for path preview in Unity.

    Path Parameters:
        robot_id: Robot identifier

    Returns:
        200: Trajectory waypoints
        404: Robot not found
    """
    try:
        # Placeholder - would integrate with motion planning
        return jsonify({
            "robot_id": robot_id,
            "trajectory": [],
            "is_executing": False,
            "progress": 0.0
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get trajectory error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# CNC Machine Visualization
# =============================================================================

@unity_factory_bp.route('/cnc/<machine_id>/state', methods=['GET'])
def get_cnc_state(machine_id: str):
    """
    Get CNC machine state for visualization

    Returns current position, spindle state, program progress,
    and sensor overlay data.

    Path Parameters:
        machine_id: Machine identifier

    Returns:
        200: Machine state
        404: Machine not found
    """
    try:
        orchestrator = get_factory_orchestrator()

        if machine_id != orchestrator.config.cnc_id:
            return jsonify({"error": f"Machine '{machine_id}' not found"}), 404

        # Get machine state
        state = {
            "machine_id": machine_id,
            "position": {"x": 0, "y": 0, "z": 0},
            "spindle": {
                "rpm": 0,
                "load_percent": 0,
                "temperature_c": 0
            },
            "program": {
                "name": None,
                "progress_percent": 0,
                "current_line": 0,
                "is_running": False
            },
            "sensors": {}
        }

        # Get sensor data if available
        if orchestrator.sensor_service:
            reading = orchestrator.sensor_service.get_current_reading()
            state["sensors"] = {
                "spindle_temp": reading.get("spindle_temp", 0),
                "vibration_rms": reading.get("vibration_rms", 0),
                "spindle_current": reading.get("spindle_current", 0)
            }

        # Get CNC position if controller available
        if orchestrator.cnc_controller:
            try:
                position = orchestrator.cnc_controller.get_position()
                state["position"] = position
            except Exception:
                pass

        return jsonify(state), 200

    except Exception as e:
        current_app.logger.error(f"Get CNC state error: {e}")
        return jsonify({"error": str(e)}), 500


@unity_factory_bp.route('/cnc/<machine_id>/toolpath', methods=['GET'])
def get_cnc_toolpath(machine_id: str):
    """
    Get current toolpath for visualization

    Returns the G-code toolpath as a series of segments
    for Unity to render.

    Path Parameters:
        machine_id: Machine identifier

    Returns:
        200: Toolpath segments
    """
    try:
        orchestrator = get_factory_orchestrator()

        if orchestrator.active_part and orchestrator.active_part.nc_program:
            # Would parse NC program and return toolpath
            return jsonify({
                "machine_id": machine_id,
                "program": orchestrator.active_part.nc_program,
                "segments": [],
                "executed_index": 0
            }), 200

        return jsonify({
            "machine_id": machine_id,
            "program": None,
            "segments": [],
            "executed_index": 0
        }), 200

    except Exception as e:
        current_app.logger.error(f"Get toolpath error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Material Flow (Workpieces)
# =============================================================================

@unity_factory_bp.route('/workpieces', methods=['GET'])
def get_all_workpieces():
    """
    Get all workpiece positions and states

    Returns all workpieces currently in the manufacturing cell
    with their positions for material flow visualization.

    Returns:
        200: List of workpieces with states
    """
    try:
        orchestrator = get_factory_orchestrator()
        workpieces = []

        # Get workpieces from active job
        if orchestrator.active_job:
            for part in orchestrator.active_job.parts:
                wp = {
                    "workpiece_id": part.part_id,
                    "job_id": part.job_id,
                    "state": part.current_stage.value,
                    "location": _get_part_location(part, orchestrator),
                    "machined_percentage": 0.0
                }

                if part.current_stage.value == "machining":
                    if part.machining_start:
                        from datetime import datetime
                        elapsed = (
                            datetime.now() - part.machining_start
                        ).total_seconds()
                        wp["machined_percentage"] = min(100, elapsed / 30 * 100)

                workpieces.append(wp)

        return jsonify({"workpieces": workpieces}), 200

    except Exception as e:
        current_app.logger.error(f"Get workpieces error: {e}")
        return jsonify({"error": str(e)}), 500


@unity_factory_bp.route('/material-flow', methods=['GET'])
def get_material_flow():
    """
    Get material flow paths for animation

    Returns the defined flow paths through the cell for
    animating workpiece movement.

    Returns:
        200: Material flow paths
    """
    try:
        flow_paths = {
            "input_to_fixture": {
                "from": "input_pallet",
                "to": "cnc_fixture",
                "via_robot": "ned2-001",
                "waypoints": [
                    {"x": -600, "y": 0, "z": 150},
                    {"x": -300, "y": 100, "z": 200},
                    {"x": 0, "y": 0, "z": 200},
                    {"x": 0, "y": 0, "z": 80}
                ]
            },
            "fixture_to_inspection": {
                "from": "cnc_fixture",
                "to": "inspection_station",
                "via_robot": "xarm-001",
                "waypoints": [
                    {"x": 0, "y": 0, "z": 80},
                    {"x": 0, "y": 0, "z": 200},
                    {"x": 200, "y": -150, "z": 200},
                    {"x": 400, "y": -300, "z": 150}
                ]
            },
            "inspection_to_output": {
                "from": "inspection_station",
                "to": "output_pallet",
                "via_robot": "xarm-001",
                "waypoints": [
                    {"x": 400, "y": -300, "z": 150},
                    {"x": 500, "y": -150, "z": 200},
                    {"x": 600, "y": 0, "z": 150}
                ]
            },
            "inspection_to_reject": {
                "from": "inspection_station",
                "to": "reject_pallet",
                "via_robot": "xarm-001",
                "waypoints": [
                    {"x": 400, "y": -300, "z": 150},
                    {"x": 500, "y": -250, "z": 200},
                    {"x": 600, "y": -200, "z": 150}
                ]
            }
        }

        return jsonify({"flow_paths": flow_paths}), 200

    except Exception as e:
        current_app.logger.error(f"Get material flow error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Collision Zones
# =============================================================================

@unity_factory_bp.route('/collision-zones', methods=['GET'])
def get_collision_zones():
    """
    Get collision zone states for visualization

    Returns all collision zones with their current occupancy
    for safety visualization in Unity.

    Returns:
        200: Collision zone states
    """
    try:
        orchestrator = get_factory_orchestrator()
        zone_status = orchestrator.zone_manager.get_zone_status()

        scene = get_scene_config()
        zones = []

        for zone_config in scene.collision_zones:
            status = zone_status.get(zone_config.zone_id.replace("-", "_"), {})
            zones.append({
                **zone_config.to_dict(),
                "is_occupied": status.get("status") == "occupied",
                "occupant_id": status.get("holder")
            })

        return jsonify({"zones": zones}), 200

    except Exception as e:
        current_app.logger.error(f"Get collision zones error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Cell Status (Real-time)
# =============================================================================

@unity_factory_bp.route('/status', methods=['GET'])
def get_cell_status():
    """
    Get comprehensive cell status for Unity

    Returns the complete cell state formatted for Unity WebSocket
    consumption, including all robots, CNC, pallets, and sensors.

    Returns:
        200: Complete cell status
    """
    try:
        orchestrator = get_factory_orchestrator()
        status = orchestrator.get_status_for_unity()

        return jsonify(status), 200

    except Exception as e:
        current_app.logger.error(f"Get cell status error: {e}")
        return jsonify({"error": str(e)}), 500


@unity_factory_bp.route('/metrics', methods=['GET'])
def get_cell_metrics():
    """
    Get cell performance metrics

    Returns OEE, cycle times, and production statistics.

    Returns:
        200: Performance metrics
    """
    try:
        orchestrator = get_factory_orchestrator()
        status = orchestrator.get_cell_status()

        metrics = {
            "production": {
                "parts_completed": status.parts_completed,
                "parts_rejected": status.parts_rejected,
                "total_parts": status.parts_completed + status.parts_rejected,
                "first_pass_yield": (
                    status.parts_completed /
                    (status.parts_completed + status.parts_rejected)
                    if (status.parts_completed + status.parts_rejected) > 0
                    else 1.0
                ) * 100
            },
            "time": {
                "uptime_seconds": status.uptime_seconds,
                "uptime_hours": status.uptime_seconds / 3600
            },
            "efficiency": {
                "oee_percentage": status.oee_percentage
            },
            "current_job": {
                "job_id": status.active_job,
                "part_id": status.current_part,
                "stage": status.current_stage.value if status.current_stage else None
            }
        }

        return jsonify(metrics), 200

    except Exception as e:
        current_app.logger.error(f"Get metrics error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# WebSocket Subscription
# =============================================================================

@unity_factory_bp.route('/subscribe', methods=['POST'])
def subscribe_to_updates():
    """
    Subscribe to real-time factory updates

    Registers a Unity client for WebSocket events including:
    - factory:cell_status
    - robot:position_update
    - workpiece:location_change
    - sensor:update

    Request Body:
        client_id: str - Unity client identifier
        events: list[str] - Events to subscribe to

    Returns:
        200: Subscription confirmed with room ID
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    client_id = data.get('client_id')
    events = data.get('events', ['all'])

    if not client_id:
        return jsonify({"error": "client_id required"}), 400

    try:
        room_id = f"factory:cell:{client_id}"

        # Would register with socketio here
        return jsonify({
            "status": "subscribed",
            "client_id": client_id,
            "room_id": room_id,
            "events": events,
            "websocket_url": "/socket.io/"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Subscribe error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Sensor Overlays
# =============================================================================

@unity_factory_bp.route('/sensors', methods=['GET'])
def get_sensor_overlays():
    """
    Get sensor overlay data for Unity visualization

    Returns all sensor configurations with current values
    for overlay rendering.

    Returns:
        200: Sensor overlay data
    """
    try:
        scene = get_scene_config()
        orchestrator = get_factory_orchestrator()

        sensors = []
        for sensor_config in scene.sensors:
            sensor_dict = sensor_config.to_dict()

            # Get current value from sensor service
            if orchestrator.sensor_service:
                reading = orchestrator.sensor_service.get_current_reading()

                if sensor_config.sensor_id == "spindle-temp":
                    sensor_dict["current_value"] = reading.get("spindle_temp", 0)
                elif sensor_config.sensor_id == "vibration-x":
                    sensor_dict["current_value"] = reading.get("vibration_rms", 0)
                elif sensor_config.sensor_id == "spindle-current":
                    sensor_dict["current_value"] = reading.get("spindle_current", 0)

            sensors.append(sensor_dict)

        return jsonify({"sensors": sensors}), 200

    except Exception as e:
        current_app.logger.error(f"Get sensors error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Helper Functions
# =============================================================================

def _get_part_location(part, orchestrator) -> str:
    """Get human-readable location for a part"""
    stage = part.current_stage.value

    if stage == "queued":
        return f"input_pallet:slot_{part.raw_stock_slot}"
    elif stage == "loading_stock":
        return "ned2_gripper"
    elif stage in ("fixturing", "machining"):
        return "cnc_fixture"
    elif stage == "unloading":
        return "xarm_gripper"
    elif stage == "inspecting":
        return "inspection_station"
    elif stage in ("complete", "storing"):
        if part.final_slot is not None:
            return f"output_pallet:slot_{part.final_slot}"
        return "xarm_gripper"
    elif stage == "rejected":
        if part.final_slot is not None:
            return f"reject_pallet:slot_{part.final_slot}"
        return "xarm_gripper"
    else:
        return "unknown"
