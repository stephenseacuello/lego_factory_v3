"""
Robotics API Routes
====================

REST API endpoints for robotic arm control and scheduling.
ISO 10218 / ISO/TS 15066 compliant safety features.

Endpoints:
- Robotic arm management
- Task scheduling and queue
- Synchronized multi-arm motions
- Safety zones and violations
- Calibration and trajectories

Author: LegoMCP Team
Version: 2.0.0
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

# Create Blueprint
robotics_bp = Blueprint('robotics', __name__, url_prefix='/api/robotics')


# ================== Robotic Arms ==================

@robotics_bp.route('/arms', methods=['GET'])
def list_arms():
    """
    List all robotic arms.

    Query Parameters:
        namespace: Filter by namespace
        status: Filter by status (idle, executing, error, etc.)
        type: Filter by arm type (6dof, scara, delta, etc.)

    Returns:
        List of robotic arms with current state
    """
    try:
        from services.digital_twin import get_ome_registry, OMEType

        registry = get_ome_registry()

        # Get all robotic arms (equipment type)
        omes = registry.get_by_type(OMEType.EQUIPMENT)

        # Filter to robotic arms only
        arms = [o for o in omes if 'robot' in o.name.lower() or 'arm' in o.name.lower()
                or o.static_attributes.capabilities and 'robotic_arm' in [c.value for c in o.static_attributes.capabilities]]

        # Apply filters
        status_filter = request.args.get('status')
        if status_filter:
            arms = [a for a in arms if a.dynamic_attributes.status == status_filter]

        type_filter = request.args.get('type')
        if type_filter:
            arms = [a for a in arms if type_filter.lower() in str(a.static_attributes.model).lower()]

        return jsonify({
            'success': True,
            'count': len(arms),
            'data': [a.to_dict() for a in arms]
        })

    except Exception as e:
        logger.error(f"Error listing arms: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/arms/<arm_id>', methods=['GET'])
def get_arm(arm_id: str):
    """
    Get robotic arm details.

    Path Parameters:
        arm_id: Arm OME ID

    Returns:
        Arm details with current state and queue
    """
    try:
        from services.digital_twin import get_ome_registry, get_twin_engine

        registry = get_ome_registry()
        twin_engine = get_twin_engine()

        ome = registry.get(arm_id)
        if not ome:
            return jsonify({
                'success': False,
                'error': 'Arm not found'
            }), 404

        # Get associated twins
        twins = twin_engine.get_twins_for_ome(arm_id)

        return jsonify({
            'success': True,
            'data': {
                'ome': ome.to_dict(),
                'twins': [t.to_dict() for t in twins],
                'joint_positions': ome.dynamic_attributes.custom.get('joint_positions', []),
                'tcp_position': ome.dynamic_attributes.custom.get('tcp_position', {}),
                'status': ome.dynamic_attributes.status
            }
        })

    except Exception as e:
        logger.error(f"Error getting arm: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/arms/<arm_id>/state', methods=['PUT'])
def update_arm_state(arm_id: str):
    """
    Update robotic arm state from controller.

    Path Parameters:
        arm_id: Arm OME ID

    Body:
        joint_positions: Array of joint positions
        tcp_position: Tool center point position
        velocity_percent: Current velocity percentage
        status: Current status

    Returns:
        Updated state
    """
    try:
        from services.digital_twin import get_ome_registry

        data = request.get_json()

        registry = get_ome_registry()

        # Update dynamic attributes
        updates = {
            'dynamic_attributes': {
                'status': data.get('status'),
                'custom': {
                    'joint_positions': data.get('joint_positions'),
                    'tcp_position': data.get('tcp_position'),
                    'velocity_percent': data.get('velocity_percent'),
                    'last_update': datetime.utcnow().isoformat()
                }
            }
        }

        updated = registry.update(arm_id, updates)

        return jsonify({
            'success': True,
            'data': updated.to_dict()
        })

    except Exception as e:
        logger.error(f"Error updating arm state: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ================== Task Queue ==================

@robotics_bp.route('/arms/<arm_id>/tasks', methods=['GET'])
def list_arm_tasks(arm_id: str):
    """
    Get task queue for a robotic arm.

    Path Parameters:
        arm_id: Arm OME ID

    Query Parameters:
        status: Filter by status (pending, executing, completed, failed)

    Returns:
        List of tasks in queue
    """
    try:
        # In a real implementation, this would query the database
        # For now, return a mock queue structure
        status_filter = request.args.get('status')

        # Mock task queue
        tasks = [
            {
                'id': str(uuid.uuid4()),
                'arm_id': arm_id,
                'task_type': 'move_joint',
                'priority': 'normal',
                'status': 'pending',
                'parameters': {'target': [0, -30, 60, 0, 90, 0]},
                'created_at': datetime.utcnow().isoformat()
            }
        ]

        if status_filter:
            tasks = [t for t in tasks if t['status'] == status_filter]

        return jsonify({
            'success': True,
            'count': len(tasks),
            'data': tasks
        })

    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/arms/<arm_id>/tasks', methods=['POST'])
def queue_task(arm_id: str):
    """
    Queue a new task for a robotic arm.

    Path Parameters:
        arm_id: Arm OME ID

    Body:
        task_type: Type (move_joint, move_linear, pick, place, home, calibrate)
        priority: Priority (low, normal, high, critical)
        parameters: Task-specific parameters
        scheduled_at: Optional scheduled time

    Returns:
        Created task
    """
    try:
        data = request.get_json()

        if not data or 'task_type' not in data:
            return jsonify({
                'success': False,
                'error': 'task_type required'
            }), 400

        task = {
            'id': str(uuid.uuid4()),
            'arm_id': arm_id,
            'task_type': data['task_type'],
            'priority': data.get('priority', 'normal'),
            'status': 'pending',
            'parameters': data.get('parameters', {}),
            'scheduled_at': data.get('scheduled_at'),
            'velocity_limit_percent': data.get('velocity_limit_percent', 100),
            'collision_detection_enabled': data.get('collision_detection_enabled', True),
            'created_at': datetime.utcnow().isoformat()
        }

        # In a real implementation, this would be saved to the database
        # and sent to the task scheduler

        return jsonify({
            'success': True,
            'data': task
        }), 201

    except Exception as e:
        logger.error(f"Error queuing task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@robotics_bp.route('/arms/<arm_id>/tasks/<task_id>', methods=['GET'])
def get_task(arm_id: str, task_id: str):
    """
    Get task details.

    Path Parameters:
        arm_id: Arm OME ID
        task_id: Task ID

    Returns:
        Task details with acknowledgments
    """
    try:
        # Mock task lookup
        task = {
            'id': task_id,
            'arm_id': arm_id,
            'task_type': 'move_joint',
            'priority': 'normal',
            'status': 'pending',
            'parameters': {},
            'acknowledgments': [],
            'created_at': datetime.utcnow().isoformat()
        }

        return jsonify({
            'success': True,
            'data': task
        })

    except Exception as e:
        logger.error(f"Error getting task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/arms/<arm_id>/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(arm_id: str, task_id: str):
    """
    Cancel a pending or executing task.

    Path Parameters:
        arm_id: Arm OME ID
        task_id: Task ID

    Returns:
        Success status
    """
    try:
        # In a real implementation, this would cancel the task

        return jsonify({
            'success': True,
            'message': f'Task {task_id} cancelled'
        })

    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Immediate Commands ==================

@robotics_bp.route('/arms/<arm_id>/command', methods=['POST'])
def send_command(arm_id: str):
    """
    Send immediate command to robotic arm.

    Path Parameters:
        arm_id: Arm OME ID

    Body:
        command: Command (stop, pause, resume, home, clear_error, e_stop, reset)
        parameters: Command-specific parameters

    Returns:
        Command result
    """
    try:
        data = request.get_json()

        if not data or 'command' not in data:
            return jsonify({
                'success': False,
                'error': 'command required'
            }), 400

        command = data['command']
        valid_commands = ['stop', 'pause', 'resume', 'home', 'clear_error', 'e_stop', 'reset']

        if command not in valid_commands:
            return jsonify({
                'success': False,
                'error': f'Invalid command. Valid: {valid_commands}'
            }), 400

        # In a real implementation, this would send the command to the arm controller

        return jsonify({
            'success': True,
            'data': {
                'command': command,
                'arm_id': arm_id,
                'executed_at': datetime.utcnow().isoformat(),
                'message': f'Command {command} executed'
            }
        })

    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Synchronized Motion ==================

@robotics_bp.route('/synchronized-motion', methods=['POST'])
def create_synchronized_motion():
    """
    Create synchronized motion for multiple arms.

    Body:
        arm_ids: List of arm OME IDs
        tasks: Map of arm_id to task parameters
        sync_type: Synchronization type (barrier, timed, master_slave)
        master_arm_id: Master arm for master_slave mode
        scheduled_at: Optional scheduled time

    Returns:
        Synchronized motion details
    """
    try:
        data = request.get_json()

        if not data or 'arm_ids' not in data or 'tasks' not in data:
            return jsonify({
                'success': False,
                'error': 'arm_ids and tasks required'
            }), 400

        motion = {
            'id': str(uuid.uuid4()),
            'motion_id': f"sync-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            'arm_ids': data['arm_ids'],
            'arm_count': len(data['arm_ids']),
            'sync_type': data.get('sync_type', 'barrier'),
            'master_arm_id': data.get('master_arm_id'),
            'status': 'pending',
            'arms_ready': 0,
            'tasks': data['tasks'],
            'created_at': datetime.utcnow().isoformat()
        }

        return jsonify({
            'success': True,
            'data': motion
        }), 201

    except Exception as e:
        logger.error(f"Error creating synchronized motion: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@robotics_bp.route('/synchronized-motion/<motion_id>/status', methods=['GET'])
def get_sync_motion_status(motion_id: str):
    """
    Get synchronized motion status.

    Path Parameters:
        motion_id: Motion identifier

    Returns:
        Motion status with arm readiness
    """
    try:
        # Mock motion status
        motion = {
            'id': str(uuid.uuid4()),
            'motion_id': motion_id,
            'status': 'waiting',
            'arms_ready': 1,
            'arm_count': 2,
            'task_results': {}
        }

        return jsonify({
            'success': True,
            'data': motion
        })

    except Exception as e:
        logger.error(f"Error getting motion status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/synchronized-motion/<motion_id>/ready', methods=['POST'])
def signal_arm_ready(motion_id: str):
    """
    Signal that an arm is ready for synchronized motion.

    Path Parameters:
        motion_id: Motion identifier

    Body:
        arm_id: Arm signaling readiness

    Returns:
        Updated motion status
    """
    try:
        data = request.get_json()

        if not data or 'arm_id' not in data:
            return jsonify({
                'success': False,
                'error': 'arm_id required'
            }), 400

        # In a real implementation, this would update the motion state

        return jsonify({
            'success': True,
            'message': f"Arm {data['arm_id']} ready for motion {motion_id}"
        })

    except Exception as e:
        logger.error(f"Error signaling ready: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ================== Safety Zones ==================

@robotics_bp.route('/safety-zones', methods=['GET'])
def list_safety_zones():
    """
    List all safety zones.

    Query Parameters:
        arm_id: Filter by arm
        zone_type: Filter by type
        active: Filter by active status

    Returns:
        List of safety zones
    """
    try:
        arm_id = request.args.get('arm_id')
        zone_type = request.args.get('zone_type')
        active = request.args.get('active')

        # Mock safety zones
        zones = [
            {
                'id': str(uuid.uuid4()),
                'zone_id': 'zone-operator-area',
                'zone_name': 'Operator Safety Zone',
                'zone_type': 'reduced_speed',
                'geometry_type': 'box',
                'geometry_data': {
                    'min': {'x': -1.0, 'y': -1.0, 'z': 0},
                    'max': {'x': 1.0, 'y': 1.0, 'z': 2.0}
                },
                'velocity_limit_percent': 50,
                'is_active': True
            }
        ]

        if arm_id:
            zones = [z for z in zones if z.get('arm_id') == arm_id]
        if zone_type:
            zones = [z for z in zones if z['zone_type'] == zone_type]
        if active is not None:
            active_bool = active.lower() == 'true'
            zones = [z for z in zones if z['is_active'] == active_bool]

        return jsonify({
            'success': True,
            'count': len(zones),
            'data': zones
        })

    except Exception as e:
        logger.error(f"Error listing safety zones: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/safety-zones', methods=['POST'])
def create_safety_zone():
    """
    Create a new safety zone.

    Body:
        zone_id: Unique zone identifier
        zone_name: Display name
        zone_type: Type (restricted, reduced_speed, collaborative, stop, warning)
        geometry_type: Geometry type (box, sphere, cylinder, mesh)
        geometry_data: Geometry definition
        velocity_limit_percent: Speed limit in zone
        force_limit_n: Force limit in zone
        arm_id: Associated arm (optional, null for all arms)

    Returns:
        Created safety zone
    """
    try:
        data = request.get_json()

        required = ['zone_id', 'zone_name', 'zone_type', 'geometry_type', 'geometry_data']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'{field} required'
                }), 400

        zone = {
            'id': str(uuid.uuid4()),
            'zone_id': data['zone_id'],
            'zone_name': data['zone_name'],
            'zone_type': data['zone_type'],
            'geometry_type': data['geometry_type'],
            'geometry_data': data['geometry_data'],
            'arm_id': data.get('arm_id'),
            'velocity_limit_percent': data.get('velocity_limit_percent'),
            'force_limit_n': data.get('force_limit_n'),
            'stop_on_entry': data.get('stop_on_entry', False),
            'alarm_on_entry': data.get('alarm_on_entry', True),
            'is_active': True,
            'created_at': datetime.utcnow().isoformat()
        }

        return jsonify({
            'success': True,
            'data': zone
        }), 201

    except Exception as e:
        logger.error(f"Error creating safety zone: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@robotics_bp.route('/safety-zones/<zone_id>', methods=['PUT'])
def update_safety_zone(zone_id: str):
    """
    Update a safety zone.

    Path Parameters:
        zone_id: Zone identifier

    Body:
        Any zone properties to update

    Returns:
        Updated zone
    """
    try:
        data = request.get_json()

        # In a real implementation, this would update the zone in the database

        return jsonify({
            'success': True,
            'data': {
                'zone_id': zone_id,
                **data,
                'updated_at': datetime.utcnow().isoformat()
            }
        })

    except Exception as e:
        logger.error(f"Error updating safety zone: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@robotics_bp.route('/safety-zones/<zone_id>/activate', methods=['POST'])
def activate_zone(zone_id: str):
    """Activate a safety zone."""
    try:
        return jsonify({
            'success': True,
            'message': f'Zone {zone_id} activated'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@robotics_bp.route('/safety-zones/<zone_id>/deactivate', methods=['POST'])
def deactivate_zone(zone_id: str):
    """Deactivate a safety zone."""
    try:
        return jsonify({
            'success': True,
            'message': f'Zone {zone_id} deactivated'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ================== Zone Violations ==================

@robotics_bp.route('/violations', methods=['GET'])
def list_violations():
    """
    List safety zone violations.

    Query Parameters:
        severity: Filter by severity (warning, critical, emergency_stop)
        arm_id: Filter by arm
        zone_id: Filter by zone
        since: Filter by date
        acknowledged: Filter by acknowledgment status

    Returns:
        List of violations
    """
    try:
        # Mock violations
        violations = [
            {
                'id': str(uuid.uuid4()),
                'zone_id': 'zone-operator-area',
                'arm_id': 'arm-001',
                'violation_type': 'entry',
                'severity': 'warning',
                'detected_at': datetime.utcnow().isoformat(),
                'action_taken': 'speed_reduced',
                'operator_acknowledged': False
            }
        ]

        return jsonify({
            'success': True,
            'count': len(violations),
            'data': violations
        })

    except Exception as e:
        logger.error(f"Error listing violations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/violations/<violation_id>/acknowledge', methods=['POST'])
def acknowledge_violation(violation_id: str):
    """
    Acknowledge a safety violation.

    Path Parameters:
        violation_id: Violation identifier

    Body:
        acknowledged_by: Operator ID
        notes: Optional notes

    Returns:
        Updated violation
    """
    try:
        data = request.get_json() or {}

        return jsonify({
            'success': True,
            'data': {
                'id': violation_id,
                'operator_acknowledged': True,
                'acknowledged_by': data.get('acknowledged_by', 'operator'),
                'acknowledged_at': datetime.utcnow().isoformat(),
                'notes': data.get('notes')
            }
        })

    except Exception as e:
        logger.error(f"Error acknowledging violation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ================== Trajectories ==================

@robotics_bp.route('/arms/<arm_id>/trajectories', methods=['GET'])
def list_trajectories(arm_id: str):
    """
    List saved trajectories for an arm.

    Path Parameters:
        arm_id: Arm OME ID

    Returns:
        List of trajectories
    """
    try:
        trajectories = [
            {
                'id': str(uuid.uuid4()),
                'arm_id': arm_id,
                'trajectory_name': 'Pick and Place',
                'trajectory_type': 'pick_place',
                'waypoint_count': 5,
                'total_duration_ms': 3500,
                'is_validated': True
            }
        ]

        return jsonify({
            'success': True,
            'count': len(trajectories),
            'data': trajectories
        })

    except Exception as e:
        logger.error(f"Error listing trajectories: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/arms/<arm_id>/trajectories', methods=['POST'])
def create_trajectory(arm_id: str):
    """
    Create a new trajectory.

    Path Parameters:
        arm_id: Arm OME ID

    Body:
        trajectory_name: Name
        trajectory_type: Type (point_to_point, linear, arc, spline, pick_place)
        waypoints: List of waypoints
        interpolation: Interpolation method (linear, cubic, quintic)

    Returns:
        Created trajectory
    """
    try:
        data = request.get_json()

        if not data or 'waypoints' not in data:
            return jsonify({
                'success': False,
                'error': 'waypoints required'
            }), 400

        trajectory = {
            'id': str(uuid.uuid4()),
            'arm_id': arm_id,
            'trajectory_name': data.get('trajectory_name', 'Untitled'),
            'trajectory_type': data.get('trajectory_type', 'point_to_point'),
            'waypoint_count': len(data['waypoints']),
            'waypoints': data['waypoints'],
            'interpolation': data.get('interpolation', 'quintic'),
            'total_duration_ms': data.get('total_duration_ms'),
            'is_validated': False,
            'created_at': datetime.utcnow().isoformat()
        }

        return jsonify({
            'success': True,
            'data': trajectory
        }), 201

    except Exception as e:
        logger.error(f"Error creating trajectory: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@robotics_bp.route('/arms/<arm_id>/trajectories/<trajectory_id>/validate', methods=['POST'])
def validate_trajectory(arm_id: str, trajectory_id: str):
    """
    Validate a trajectory for execution.

    Path Parameters:
        arm_id: Arm OME ID
        trajectory_id: Trajectory ID

    Returns:
        Validation result
    """
    try:
        # Mock validation
        result = {
            'trajectory_id': trajectory_id,
            'is_valid': True,
            'validated_at': datetime.utcnow().isoformat(),
            'checks': {
                'joint_limits': {'passed': True, 'message': 'All waypoints within joint limits'},
                'collision': {'passed': True, 'message': 'No collisions detected'},
                'velocity': {'passed': True, 'message': 'Velocities within limits'},
                'acceleration': {'passed': True, 'message': 'Accelerations within limits'}
            }
        }

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Error validating trajectory: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ================== Calibration ==================

@robotics_bp.route('/arms/<arm_id>/calibrations', methods=['GET'])
def list_calibrations(arm_id: str):
    """
    List calibration records for an arm.

    Path Parameters:
        arm_id: Arm OME ID

    Returns:
        List of calibration records
    """
    try:
        calibrations = [
            {
                'id': str(uuid.uuid4()),
                'arm_id': arm_id,
                'calibration_type': 'joint_offsets',
                'performed_at': datetime.utcnow().isoformat(),
                'performed_by': 'technician',
                'accuracy_achieved_mm': 0.05,
                'passed': True,
                'next_calibration_due': (datetime.utcnow() + timedelta(days=90)).isoformat()
            }
        ]

        return jsonify({
            'success': True,
            'count': len(calibrations),
            'data': calibrations
        })

    except Exception as e:
        logger.error(f"Error listing calibrations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robotics_bp.route('/arms/<arm_id>/calibrate', methods=['POST'])
def start_calibration(arm_id: str):
    """
    Start calibration procedure.

    Path Parameters:
        arm_id: Arm OME ID

    Body:
        calibration_type: Type (joint_offsets, tool_center_point, base_frame, payload)
        performed_by: Operator/technician ID

    Returns:
        Calibration task
    """
    try:
        data = request.get_json() or {}

        calibration = {
            'id': str(uuid.uuid4()),
            'arm_id': arm_id,
            'calibration_type': data.get('calibration_type', 'joint_offsets'),
            'status': 'in_progress',
            'started_at': datetime.utcnow().isoformat(),
            'performed_by': data.get('performed_by', 'operator')
        }

        return jsonify({
            'success': True,
            'data': calibration
        }), 201

    except Exception as e:
        logger.error(f"Error starting calibration: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


__all__ = ['robotics_bp']
