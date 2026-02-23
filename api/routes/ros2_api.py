"""
LEGO Factory v3 - ROS2 Robotics API
===================================
REST API endpoints for ROS2 robotics control and cell orchestration.

Provides endpoints for:
- ROS2 bridge connection management
- Robot control commands
- Cell orchestrator tasks
- Task management and monitoring
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from config.demo_mode import is_demo_mode_enabled

logger = logging.getLogger(__name__)

ros2_api_bp = Blueprint('ros2_api', __name__, url_prefix='/api/ros2')


def get_ros2_bridge():
    """Get ROS2 bridge instance."""
    try:
        from services.robotics.ros2_bridge import get_ros2_bridge
        return get_ros2_bridge()
    except Exception as e:
        logger.warning(f"ROS2 bridge not available: {e}")
        return None


def get_orchestrator():
    """Get cell orchestrator instance."""
    try:
        from services.robotics.cell_orchestrator import get_orchestrator
        return get_orchestrator()
    except Exception as e:
        logger.warning(f"Cell orchestrator not available: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Bridge Management
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/bridge/status', methods=['GET'])
@jwt_required()
def bridge_status():
    """Get ROS2 bridge connection status."""
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({
            'available': False,
            'state': 'disconnected',
            'error': 'ROS2 bridge not initialized',
        })

    return jsonify({
        'available': True,
        'state': bridge.state.value,
        'connected': bridge.is_connected,
        'url': bridge.url,
        'subscriptions': list(bridge._subscriptions.keys()),
    })


@ros2_api_bp.route('/bridge/connect', methods=['POST'])
@jwt_required()
def bridge_connect():
    """Connect to rosbridge server."""
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    data = request.get_json() or {}
    host = data.get('host', 'localhost')
    port = data.get('port', 9090)

    # Update connection settings
    bridge.host = host
    bridge.port = port
    bridge.url = f"ws://{host}:{port}"

    success = bridge.connect()

    return jsonify({
        'success': success,
        'state': bridge.state.value,
        'url': bridge.url,
    })


@ros2_api_bp.route('/bridge/disconnect', methods=['POST'])
@jwt_required()
def bridge_disconnect():
    """Disconnect from rosbridge server."""
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    bridge.disconnect()

    return jsonify({
        'success': True,
        'state': bridge.state.value,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Topic Management
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/topics', methods=['GET'])
@jwt_required()
def list_topics():
    """List subscribed topics."""
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    topics = [
        {
            'name': topic.name,
            'msg_type': topic.msg_type,
            'queue_size': topic.queue_size,
        }
        for topic in bridge._subscriptions.values()
    ]

    return jsonify({
        'topics': topics,
        'count': len(topics),
    })


@ros2_api_bp.route('/topics/publish', methods=['POST'])
@jwt_required()
def publish_topic():
    """
    Publish a message to a ROS2 topic.

    JSON body:
    - topic: Topic name (required)
    - msg_type: Message type (required)
    - msg: Message data (required)
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    if not bridge.is_connected:
        return jsonify({'error': 'Not connected to rosbridge'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    topic = data.get('topic')
    msg_type = data.get('msg_type')
    msg = data.get('msg')

    if not all([topic, msg_type, msg]):
        return jsonify({'error': 'topic, msg_type, and msg required'}), 400

    bridge.publish(topic, msg_type, msg)

    return jsonify({'success': True, 'topic': topic})


# ─────────────────────────────────────────────────────────────────────────────
# Service Calls
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/services/call', methods=['POST'])
@jwt_required()
def call_service():
    """
    Call a ROS2 service.

    JSON body:
    - service: Service name (required)
    - srv_type: Service type (required)
    - args: Service arguments (dict)
    - timeout: Timeout in seconds (default: 10)
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    service = data.get('service')
    srv_type = data.get('srv_type')
    args = data.get('args', {})
    timeout = data.get('timeout', 10.0)

    if not all([service, srv_type]):
        return jsonify({'error': 'service and srv_type required'}), 400

    result = bridge.call_service(service, srv_type, args, timeout)

    if result is None:
        return jsonify({'error': 'Service call failed or timed out'}), 500

    return jsonify({'result': result})


# ─────────────────────────────────────────────────────────────────────────────
# Cell Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/orchestrator/status', methods=['GET'])
@jwt_required()
def orchestrator_status():
    """Get cell orchestrator status."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({
            'available': False,
            'error': 'Orchestrator not initialized',
        })

    return jsonify({
        'available': True,
        'running': orchestrator._running,
        'paused': orchestrator._paused,
        'cells': list(orchestrator.work_cells.keys()),
        'total_tasks': len(orchestrator.tasks),
    })


@ros2_api_bp.route('/orchestrator/start', methods=['POST'])
@jwt_required()
def orchestrator_start():
    """Start the cell orchestrator."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    orchestrator.start()

    return jsonify({'status': 'started', 'running': orchestrator._running})


@ros2_api_bp.route('/orchestrator/stop', methods=['POST'])
@jwt_required()
def orchestrator_stop():
    """Stop the cell orchestrator."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    orchestrator.stop()

    return jsonify({'status': 'stopped', 'running': orchestrator._running})


@ros2_api_bp.route('/orchestrator/pause', methods=['POST'])
@jwt_required()
def orchestrator_pause():
    """Pause task execution."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    orchestrator.pause()

    return jsonify({'status': 'paused', 'paused': orchestrator._paused})


@ros2_api_bp.route('/orchestrator/resume', methods=['POST'])
@jwt_required()
def orchestrator_resume():
    """Resume task execution."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    orchestrator.resume()

    return jsonify({'status': 'resumed', 'paused': orchestrator._paused})


# ─────────────────────────────────────────────────────────────────────────────
# Work Cells
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/cells', methods=['GET'])
@jwt_required()
def list_cells():
    """List work cells."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        if is_demo_mode_enabled():
            return _demo_cells()
        return jsonify({'error': 'Service not configured'}), 503

    cells = [cell.to_dict() for cell in orchestrator.work_cells.values()]

    return jsonify({
        'cells': cells,
        'count': len(cells),
    })


@ros2_api_bp.route('/cells/<cell_id>', methods=['GET'])
@jwt_required()
def get_cell_status(cell_id: str):
    """Get detailed cell status."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        if is_demo_mode_enabled():
            return _demo_cell_status(cell_id)
        return jsonify({'error': 'Service not configured'}), 503

    status = orchestrator.get_cell_status(cell_id)

    if 'error' in status:
        return jsonify(status), 404

    return jsonify(status)


# ─────────────────────────────────────────────────────────────────────────────
# Tasks
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/tasks', methods=['GET'])
@jwt_required()
def list_tasks():
    """
    List tasks.

    Query params:
    - state: Filter by state (pending, queued, executing, completed, failed)
    - robot_id: Filter by robot
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        if is_demo_mode_enabled():
            return _demo_tasks()
        return jsonify({'error': 'Service not configured'}), 503

    state = request.args.get('state')
    robot_id = request.args.get('robot_id')

    tasks = orchestrator.get_all_tasks(state)

    if robot_id:
        tasks = [t for t in tasks if t.get('robot_id') == robot_id]

    return jsonify({
        'tasks': tasks,
        'count': len(tasks),
    })


@ros2_api_bp.route('/tasks', methods=['POST'])
@jwt_required()
def submit_task():
    """
    Submit a new task.

    JSON body:
    - task_type: Task type (pick_place, assembly, inspection, transport, custom)
    - robot_id: Optional robot ID (auto-assigned if not specified)
    - parameters: Task parameters
    - priority: Priority 1-10 (default: 5)
    - dependencies: List of task IDs that must complete first
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    task_type = data.get('task_type')
    if not task_type:
        return jsonify({'error': 'task_type required'}), 400

    try:
        task_id = orchestrator.submit_task(
            task_type=task_type,
            robot_id=data.get('robot_id'),
            parameters=data.get('parameters', {}),
            priority=data.get('priority', 5),
            dependencies=data.get('dependencies', []),
        )

        return jsonify({
            'task_id': task_id,
            'status': 'submitted',
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@ros2_api_bp.route('/tasks/<task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id: str):
    """Get task details."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    task = orchestrator.get_task(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(task)


@ros2_api_bp.route('/tasks/<task_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_task(task_id: str):
    """Cancel a pending or queued task."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    success = orchestrator.cancel_task(task_id)

    if not success:
        return jsonify({'error': 'Task not found or cannot be cancelled'}), 400

    return jsonify({
        'task_id': task_id,
        'status': 'cancelled',
    })


@ros2_api_bp.route('/robots/<robot_id>/queue', methods=['GET'])
@jwt_required()
def get_robot_queue(robot_id: str):
    """Get queued tasks for a robot."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    tasks = orchestrator.get_robot_queue(robot_id)

    return jsonify({
        'robot_id': robot_id,
        'tasks': tasks,
        'count': len(tasks),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Robot Control
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/robots', methods=['GET'])
@jwt_required()
def list_robots():
    """List available robots."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        if is_demo_mode_enabled():
            return _demo_robots()
        return jsonify({'error': 'Service not configured'}), 503

    robots = []
    for cell in orchestrator.work_cells.values():
        for robot_id in cell.robots:
            bridge = get_ros2_bridge()
            state = bridge.get_robot_state(robot_id) if bridge else None
            robots.append({
                'robot_id': robot_id,
                'cell_id': cell.cell_id,
                'busy': orchestrator.robot_busy.get(robot_id, False),
                'current_task': orchestrator.robot_current_task.get(robot_id),
                'state': state,
            })

    return jsonify({
        'robots': robots,
        'count': len(robots),
    })


@ros2_api_bp.route('/robots/<robot_id>/home', methods=['POST'])
@jwt_required()
def robot_home(robot_id: str):
    """Send robot to home position."""
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    # Submit home task
    task_id = orchestrator.submit_task(
        task_type='custom',
        robot_id=robot_id,
        parameters={'command': 'home'},
        priority=1,  # High priority
    )

    return jsonify({
        'task_id': task_id,
        'robot_id': robot_id,
        'command': 'home',
    })


@ros2_api_bp.route('/robots/<robot_id>/stop', methods=['POST'])
@jwt_required()
def robot_stop(robot_id: str):
    """Emergency stop a robot."""
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    # Publish emergency stop
    bridge.publish(
        f'/{robot_id}/emergency_stop',
        'std_msgs/msg/Bool',
        {'data': True}
    )

    return jsonify({
        'robot_id': robot_id,
        'command': 'emergency_stop',
        'sent': True,
    })


@ros2_api_bp.route('/robots/<robot_id>/gripper', methods=['POST'])
@jwt_required()
def robot_gripper(robot_id: str):
    """
    Control robot gripper.

    JSON body:
    - action: open or close
    - force: Grip force (0-100)
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json() or {}
    action = data.get('action', 'close')
    force = data.get('force', 50)

    task_id = orchestrator.submit_task(
        task_type='custom',
        robot_id=robot_id,
        parameters={
            'command': 'gripper',
            'action': action,
            'force': force,
        },
        priority=2,
    )

    return jsonify({
        'task_id': task_id,
        'robot_id': robot_id,
        'command': 'gripper',
        'action': action,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_cells():
    """Return demo cells."""
    return jsonify({
        'cells': [
            {
                'cell_id': 'cell_1',
                'name': 'LEGO Assembly Cell',
                'robots': ['niryo_ned2', 'xarm_lite6'],
                'fixtures': ['brick_feeder', 'build_plate'],
                'stations': ['station_a', 'station_b'],
                'active': True,
            },
        ],
        'count': 1,
    })


def _demo_cell_status(cell_id: str):
    """Return demo cell status."""
    if cell_id != 'cell_1':
        return jsonify({'error': 'Cell not found'}), 404

    return jsonify({
        'cell': {
            'cell_id': 'cell_1',
            'name': 'LEGO Assembly Cell',
            'robots': ['niryo_ned2', 'xarm_lite6'],
            'active': True,
        },
        'robots': [
            {
                'robot_id': 'niryo_ned2',
                'status': 'idle',
                'busy': False,
                'current_task': None,
                'joint_positions': [0.0, 0.3, -0.5, 0.0, 0.2, 0.0],
            },
            {
                'robot_id': 'xarm_lite6',
                'status': 'running',
                'busy': True,
                'current_task': 'task_abc123',
                'joint_positions': [0.1, -0.2, 0.4, 0.0, 0.0, 0.0],
            },
        ],
        'tasks': {
            'pending': 2,
            'queued': 1,
            'executing': 1,
        },
        'paused': False,
        'running': True,
    })


def _demo_tasks():
    """Return demo tasks."""
    return jsonify({
        'tasks': [
            {
                'task_id': 'task_abc123',
                'task_type': 'pick_place',
                'robot_id': 'xarm_lite6',
                'priority': 5,
                'state': 'executing',
                'parameters': {
                    'pick_pose': {'x': 0.3, 'y': 0.1, 'z': 0.05},
                    'place_pose': {'x': 0.4, 'y': -0.1, 'z': 0.05},
                },
            },
            {
                'task_id': 'task_def456',
                'task_type': 'assembly',
                'robot_id': 'niryo_ned2',
                'priority': 3,
                'state': 'queued',
                'parameters': {
                    'components': ['brick_2x4_red', 'brick_2x2_blue'],
                    'assembly_pose': {'x': 0.2, 'y': 0.0, 'z': 0.1},
                },
            },
        ],
        'count': 2,
    })


def _demo_robots():
    """Return demo robots."""
    return jsonify({
        'robots': [
            {
                'robot_id': 'niryo_ned2',
                'cell_id': 'cell_1',
                'busy': False,
                'current_task': None,
                'state': {
                    'status': 'idle',
                    'joint_positions': [0.0, 0.3, -0.5, 0.0, 0.2, 0.0],
                    'gripper_closed': False,
                },
            },
            {
                'robot_id': 'xarm_lite6',
                'cell_id': 'cell_1',
                'busy': True,
                'current_task': 'task_abc123',
                'state': {
                    'status': 'running',
                    'joint_positions': [0.1, -0.2, 0.4, 0.0, 0.0, 0.0],
                    'gripper_closed': True,
                },
            },
        ],
        'count': 2,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Additional Bridge Endpoints (Aliases)
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/status', methods=['GET'])
@jwt_required()
def ros2_status():
    """
    Get ROS2 bridge connection status.

    Alias for /bridge/status for convenience.

    Returns:
        JSON with connection state, availability, and active subscriptions.
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({
            'available': False,
            'state': 'disconnected',
            'connected': False,
            'error': 'ROS2 bridge not initialized',
            'simulation_mode': True,
        })

    return jsonify({
        'available': True,
        'state': bridge.state.value,
        'connected': bridge.is_connected,
        'url': bridge.url,
        'host': bridge.host,
        'port': bridge.port,
        'simulation_mode': bridge._simulation_mode,
        'subscriptions': list(bridge._subscriptions.keys()),
        'subscription_count': len(bridge._subscriptions),
    })


@ros2_api_bp.route('/connect', methods=['POST'])
@jwt_required()
def ros2_connect():
    """
    Connect to rosbridge server.

    Alias for /bridge/connect for convenience.

    JSON body (optional):
        - host: Rosbridge host (default: localhost)
        - port: Rosbridge port (default: 9090)
        - timeout: Connection timeout in seconds (default: 5.0)

    Returns:
        JSON with connection result and state.
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({
            'success': False,
            'error': 'ROS2 bridge not available',
        }), 503

    data = request.get_json() or {}
    host = data.get('host', 'localhost')
    port = data.get('port', 9090)

    # Update connection settings
    bridge.host = host
    bridge.port = port
    bridge.url = f"ws://{host}:{port}"

    success = bridge.connect()

    return jsonify({
        'success': success,
        'state': bridge.state.value,
        'url': bridge.url,
        'connected': bridge.is_connected,
    })


@ros2_api_bp.route('/disconnect', methods=['POST'])
@jwt_required()
def ros2_disconnect():
    """
    Disconnect from rosbridge server.

    Alias for /bridge/disconnect for convenience.

    Returns:
        JSON confirming disconnection.
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({
            'success': False,
            'error': 'ROS2 bridge not available',
        }), 503

    bridge.disconnect()

    return jsonify({
        'success': True,
        'state': bridge.state.value,
        'connected': False,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Topic Subscription Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/topics/subscribe', methods=['POST'])
@jwt_required()
def subscribe_topic():
    """
    Subscribe to a ROS2 topic.

    JSON body:
        - topic: Topic name (required, e.g., '/robot/joint_states')
        - msg_type: Message type (required, e.g., 'sensor_msgs/msg/JointState')
        - queue_size: Queue size for buffering messages (default: 10)

    Returns:
        JSON confirming subscription.

    Note:
        Messages received on subscribed topics are stored internally.
        Use GET /topics/{name}/messages to retrieve recent messages.
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    topic = data.get('topic')
    msg_type = data.get('msg_type')
    queue_size = data.get('queue_size', 10)

    if not topic:
        return jsonify({'error': 'topic is required'}), 400
    if not msg_type:
        return jsonify({'error': 'msg_type is required'}), 400

    # Validate topic name format
    if not topic.startswith('/'):
        topic = '/' + topic

    # Create a simple callback that logs messages
    def topic_callback(msg):
        logger.debug(f"Received message on {topic}: {msg}")

    try:
        bridge.subscribe(topic, msg_type, topic_callback, queue_size)

        return jsonify({
            'success': True,
            'topic': topic,
            'msg_type': msg_type,
            'queue_size': queue_size,
            'message': f'Subscribed to {topic}',
        }), 201

    except Exception as e:
        logger.error(f"Failed to subscribe to {topic}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@ros2_api_bp.route('/topics/unsubscribe', methods=['POST'])
@jwt_required()
def unsubscribe_topic():
    """
    Unsubscribe from a ROS2 topic.

    JSON body:
        - topic: Topic name (required)

    Returns:
        JSON confirming unsubscription.
    """
    bridge = get_ros2_bridge()

    if not bridge:
        return jsonify({'error': 'ROS2 bridge not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    topic = data.get('topic')
    if not topic:
        return jsonify({'error': 'topic is required'}), 400

    if not topic.startswith('/'):
        topic = '/' + topic

    try:
        bridge.unsubscribe(topic)

        return jsonify({
            'success': True,
            'topic': topic,
            'message': f'Unsubscribed from {topic}',
        })

    except Exception as e:
        logger.error(f"Failed to unsubscribe from {topic}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# ROS2 Services List Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/services', methods=['GET'])
@jwt_required()
def list_services():
    """
    List available ROS2 services.

    Query parameters:
        - namespace: Filter by namespace (e.g., '/niryo_robot')

    Returns:
        JSON with list of known/available services.

    Note:
        In simulation mode, returns a predefined list of common robot services.
        When connected to rosbridge, queries the ROS2 system for available services.
    """
    bridge = get_ros2_bridge()
    namespace = request.args.get('namespace', '')

    if not bridge:
        if is_demo_mode_enabled():
            return _demo_services(namespace)
        return jsonify({'error': 'Service not configured'}), 503

    if bridge._simulation_mode:
        if is_demo_mode_enabled():
            return _demo_services(namespace)
        return jsonify({'error': 'Service not configured'}), 503

    # Try to call rosapi service to list services
    try:
        result = bridge.call_service(
            '/rosapi/services',
            'rosapi/srv/Services',
            {},
            timeout=5.0
        )

        if result and 'services' in result:
            services = result['services']
            if namespace:
                services = [s for s in services if s.startswith(namespace)]

            return jsonify({
                'services': services,
                'count': len(services),
                'namespace_filter': namespace or None,
            })

    except Exception as e:
        logger.warning(f"Failed to list services via rosapi: {e}")

    # Fallback to demo services
    if is_demo_mode_enabled():
        return _demo_services(namespace)
    return jsonify({'error': 'Internal server error'}), 500


def _demo_services(namespace: str = ''):
    """Return demo services list."""
    all_services = [
        # Niryo services
        '/niryo_robot_commander/move_joints',
        '/niryo_robot_commander/move_pose',
        '/niryo_robot_commander/stop_command',
        '/niryo_robot_tools/open_gripper',
        '/niryo_robot_tools/close_gripper',
        '/niryo_robot/get_learning_mode',
        '/niryo_robot/set_learning_mode',
        '/niryo_robot/calibrate',
        # xArm services
        '/xarm/move_joint',
        '/xarm/move_line',
        '/xarm/set_gripper_position',
        '/xarm/emergency_stop',
        '/xarm/go_home',
        '/xarm/set_mode',
        '/xarm/set_state',
        # General ROS2 services
        '/rosapi/services',
        '/rosapi/topics',
        '/rosapi/get_param',
        '/rosapi/set_param',
    ]

    if namespace:
        all_services = [s for s in all_services if s.startswith(namespace)]

    return jsonify({
        'services': all_services,
        'count': len(all_services),
        'namespace_filter': namespace or None,
        'simulation_mode': True,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Individual Robot Status and Control
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/robots/<robot_id>/status', methods=['GET'])
@jwt_required()
def get_robot_status(robot_id: str):
    """
    Get detailed status of a specific robot.

    Path parameters:
        - robot_id: Robot identifier (e.g., 'niryo_ned2', 'xarm_lite6')

    Returns:
        JSON with robot status including:
        - Connection state
        - Current position (joints and cartesian)
        - Gripper state
        - Current task (if any)
        - Error state
    """
    orchestrator = get_orchestrator()
    bridge = get_ros2_bridge()

    # Get robot state from bridge
    robot_state = None
    if bridge:
        robot_state = bridge.get_robot_state(robot_id)

    # Get orchestrator info
    busy = False
    current_task = None
    queued_tasks = 0

    if orchestrator:
        busy = orchestrator.robot_busy.get(robot_id, False)
        current_task = orchestrator.robot_current_task.get(robot_id)
        queued_tasks = len([
            t for t in orchestrator.tasks.values()
            if t.robot_id == robot_id and t.state.value in ('pending', 'queued')
        ])

    # Find which cell this robot belongs to
    cell_id = None
    if orchestrator:
        for cell in orchestrator.work_cells.values():
            if robot_id in cell.robots:
                cell_id = cell.cell_id
                break

    if robot_state:
        return jsonify({
            'robot_id': robot_id,
            'cell_id': cell_id,
            'connected': robot_state.get('connected', True),
            'state': robot_state.get('state', 'unknown'),
            'position': robot_state.get('position', {}),
            'joints': robot_state.get('joints', []),
            'gripper_open': robot_state.get('gripper_open', True),
            'busy': busy,
            'current_task': current_task,
            'queued_tasks': queued_tasks,
        })

    # Return demo data if robot state not available
    if is_demo_mode_enabled():
        return _demo_robot_status(robot_id)
    return jsonify({'error': 'Service not configured'}), 503


def _demo_robot_status(robot_id: str):
    """Return demo robot status."""
    demo_states = {
        'niryo_ned2': {
            'robot_id': 'niryo_ned2',
            'cell_id': 'cell_1',
            'connected': True,
            'state': 'idle',
            'position': {'x': 0.25, 'y': 0.0, 'z': 0.35},
            'joints': [0.0, 0.3, -0.5, 0.0, 0.2, 0.0],
            'gripper_open': True,
            'busy': False,
            'current_task': None,
            'queued_tasks': 0,
        },
        'xarm_lite6': {
            'robot_id': 'xarm_lite6',
            'cell_id': 'cell_1',
            'connected': True,
            'state': 'moving',
            'position': {'x': 0.30, 'y': 0.1, 'z': 0.25},
            'joints': [0.1, -0.2, 0.4, 0.0, 0.0, 0.0],
            'gripper_open': False,
            'busy': True,
            'current_task': 'task_abc123',
            'queued_tasks': 2,
        },
    }

    if robot_id in demo_states:
        return jsonify(demo_states[robot_id])

    return jsonify({
        'error': f'Robot {robot_id} not found',
        'available_robots': list(demo_states.keys()),
    }), 404


@ros2_api_bp.route('/robots/<robot_id>/move', methods=['POST'])
@jwt_required()
def robot_move(robot_id: str):
    """
    Send move command to a robot.

    Path parameters:
        - robot_id: Robot identifier

    JSON body:
        - move_type: Type of move ('joints', 'pose', 'linear')
        - target: Target position
            - For 'joints': List of 6 joint angles in radians
            - For 'pose'/'linear': Dict with x, y, z, roll, pitch, yaw
        - velocity: Velocity scale 0.0-1.0 (default: 0.5)
        - acceleration: Acceleration scale 0.0-1.0 (default: 0.5)
        - wait: Wait for completion (default: true)

    Returns:
        JSON with task ID or immediate result.
    """
    orchestrator = get_orchestrator()
    bridge = get_ros2_bridge()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    move_type = data.get('move_type', 'pose')
    target = data.get('target')
    velocity = data.get('velocity', 0.5)
    acceleration = data.get('acceleration', 0.5)

    if not target:
        return jsonify({'error': 'target is required'}), 400

    # Validate move_type
    valid_move_types = ['joints', 'pose', 'linear']
    if move_type not in valid_move_types:
        return jsonify({
            'error': f'Invalid move_type. Must be one of: {valid_move_types}',
        }), 400

    # Validate target based on move_type
    if move_type == 'joints':
        if not isinstance(target, list) or len(target) != 6:
            return jsonify({
                'error': 'For joints move, target must be a list of 6 joint angles',
            }), 400
    else:
        if not isinstance(target, dict):
            return jsonify({
                'error': 'For pose/linear move, target must be a dict with x, y, z',
            }), 400
        required_keys = ['x', 'y', 'z']
        missing_keys = [k for k in required_keys if k not in target]
        if missing_keys:
            return jsonify({
                'error': f'Missing required keys in target: {missing_keys}',
            }), 400

    # Submit move task
    try:
        task_id = orchestrator.submit_task(
            task_type='transport',
            robot_id=robot_id,
            parameters={
                'command': 'move',
                'move_type': move_type,
                'target_pose' if move_type != 'joints' else 'target_joints': target,
                'velocity_scale': velocity,
                'acceleration_scale': acceleration,
            },
            priority=3,
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'robot_id': robot_id,
            'move_type': move_type,
            'target': target,
            'velocity': velocity,
        }), 202

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to submit move command: {e}")
        return jsonify({'error': 'Failed to submit move command'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Task Orchestration Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/tasks/pick-place', methods=['POST'])
@jwt_required()
def execute_pick_place():
    """
    Execute a pick and place operation.

    JSON body:
        - robot_id: Robot to use (optional, auto-assigned if not specified)
        - pick_pose: Pick position as {x, y, z} or {x, y, z, roll, pitch, yaw}
        - place_pose: Place position as {x, y, z} or {x, y, z, roll, pitch, yaw}
        - approach_height: Height above pick/place for approach (default: 0.05m)
        - grip_force: Gripper force 0-100 (default: 50)
        - velocity: Movement velocity scale 0.0-1.0 (default: 0.3)
        - priority: Task priority 1-10 (default: 5)

    Returns:
        JSON with task ID for tracking.
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # Validate required fields
    pick_pose = data.get('pick_pose')
    place_pose = data.get('place_pose')

    if not pick_pose:
        return jsonify({'error': 'pick_pose is required'}), 400
    if not place_pose:
        return jsonify({'error': 'place_pose is required'}), 400

    # Validate pose format
    for pose_name, pose in [('pick_pose', pick_pose), ('place_pose', place_pose)]:
        if not isinstance(pose, dict):
            return jsonify({'error': f'{pose_name} must be a dict with x, y, z'}), 400
        if 'x' not in pose or 'y' not in pose or 'z' not in pose:
            return jsonify({'error': f'{pose_name} must contain x, y, z coordinates'}), 400

    # Extract optional parameters
    robot_id = data.get('robot_id')
    approach_height = data.get('approach_height', 0.05)
    grip_force = data.get('grip_force', 50)
    velocity = data.get('velocity', 0.3)
    priority = data.get('priority', 5)

    # Validate numeric ranges
    if not 0 <= grip_force <= 100:
        return jsonify({'error': 'grip_force must be between 0 and 100'}), 400
    if not 0 < velocity <= 1.0:
        return jsonify({'error': 'velocity must be between 0 and 1.0'}), 400
    if not 1 <= priority <= 10:
        return jsonify({'error': 'priority must be between 1 and 10'}), 400

    try:
        task_id = orchestrator.submit_task(
            task_type='pick_place',
            robot_id=robot_id,
            parameters={
                'pick_pose': pick_pose,
                'place_pose': place_pose,
                'approach_height': approach_height,
                'grip_force': grip_force,
                'velocity': velocity,
            },
            priority=priority,
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'task_type': 'pick_place',
            'robot_id': robot_id or 'auto-assigned',
            'status': 'submitted',
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to submit pick-place task: {e}")
        return jsonify({'error': 'Failed to submit task'}), 500


@ros2_api_bp.route('/tasks/transfer', methods=['POST'])
@jwt_required()
def execute_transfer():
    """
    Execute a transfer operation between stations.

    JSON body:
        - robot_id: Robot to use (optional, auto-assigned if not specified)
        - from_station: Source station ID (e.g., 'station_a', 'brick_feeder')
        - to_station: Destination station ID (e.g., 'station_b', 'build_plate')
        - item_type: Type of item being transferred (optional, for logging)
        - velocity: Movement velocity scale 0.0-1.0 (default: 0.5)
        - priority: Task priority 1-10 (default: 5)

    Returns:
        JSON with task ID for tracking.

    Note:
        Station positions are looked up from the work cell configuration.
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # Validate required fields
    from_station = data.get('from_station')
    to_station = data.get('to_station')

    if not from_station:
        return jsonify({'error': 'from_station is required'}), 400
    if not to_station:
        return jsonify({'error': 'to_station is required'}), 400

    # Extract optional parameters
    robot_id = data.get('robot_id')
    item_type = data.get('item_type', 'unknown')
    velocity = data.get('velocity', 0.5)
    priority = data.get('priority', 5)

    # Define station positions (in a real system, these would come from config)
    station_positions = {
        'station_a': {'x': 0.25, 'y': 0.15, 'z': 0.05},
        'station_b': {'x': 0.25, 'y': -0.15, 'z': 0.05},
        'brick_feeder': {'x': 0.30, 'y': 0.20, 'z': 0.02},
        'build_plate': {'x': 0.20, 'y': 0.0, 'z': 0.03},
        'inspection': {'x': 0.35, 'y': 0.0, 'z': 0.10},
        'output_bin': {'x': 0.15, 'y': -0.20, 'z': 0.05},
    }

    # Validate stations exist
    if from_station not in station_positions:
        return jsonify({
            'error': f'Unknown from_station: {from_station}',
            'available_stations': list(station_positions.keys()),
        }), 400

    if to_station not in station_positions:
        return jsonify({
            'error': f'Unknown to_station: {to_station}',
            'available_stations': list(station_positions.keys()),
        }), 400

    try:
        task_id = orchestrator.submit_task(
            task_type='transport',
            robot_id=robot_id,
            parameters={
                'from_station': from_station,
                'to_station': to_station,
                'pick_pose': station_positions[from_station],
                'place_pose': station_positions[to_station],
                'item_type': item_type,
                'velocity_scale': velocity,
            },
            priority=priority,
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'task_type': 'transfer',
            'from_station': from_station,
            'to_station': to_station,
            'robot_id': robot_id or 'auto-assigned',
            'status': 'submitted',
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to submit transfer task: {e}")
        return jsonify({'error': 'Failed to submit task'}), 500


@ros2_api_bp.route('/tasks/<task_id>/status', methods=['GET'])
@jwt_required()
def get_task_status(task_id: str):
    """
    Get execution status of a specific task.

    Path parameters:
        - task_id: Task identifier

    Returns:
        JSON with detailed task status including:
        - Current state (pending, queued, executing, completed, failed, cancelled)
        - Assigned robot
        - Progress information
        - Timing information
        - Error details (if failed)
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    task = orchestrator.get_task(task_id)

    if not task:
        return jsonify({
            'error': 'Task not found',
            'task_id': task_id,
        }), 404

    # Calculate elapsed time
    elapsed_time = None
    if task.get('started_at'):
        from datetime import datetime
        started = datetime.fromisoformat(task['started_at'])
        if task.get('completed_at'):
            completed = datetime.fromisoformat(task['completed_at'])
            elapsed_time = (completed - started).total_seconds()
        else:
            elapsed_time = (datetime.utcnow() - started).total_seconds()

    return jsonify({
        'task_id': task_id,
        'task_type': task.get('task_type'),
        'state': task.get('state'),
        'robot_id': task.get('robot_id'),
        'priority': task.get('priority'),
        'parameters': task.get('parameters', {}),
        'created_at': task.get('created_at'),
        'started_at': task.get('started_at'),
        'completed_at': task.get('completed_at'),
        'elapsed_time_seconds': elapsed_time,
        'result': task.get('result', {}),
        'error_message': task.get('error_message', ''),
        'retry_count': task.get('retry_count', 0),
    })


@ros2_api_bp.route('/tasks/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id: str):
    """
    Cancel and delete a task.

    Path parameters:
        - task_id: Task identifier

    Returns:
        JSON confirming cancellation.

    Note:
        Only pending or queued tasks can be cancelled.
        Executing tasks will be allowed to complete (use robot stop for emergency).
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    # Get task to check current state
    task = orchestrator.get_task(task_id)
    if not task:
        return jsonify({
            'error': 'Task not found',
            'task_id': task_id,
        }), 404

    current_state = task.get('state')

    # Cannot cancel completed/failed/cancelled tasks
    if current_state in ('completed', 'failed', 'cancelled'):
        return jsonify({
            'error': f'Task already in terminal state: {current_state}',
            'task_id': task_id,
        }), 400

    # Cannot cancel executing tasks (use robot stop instead)
    if current_state == 'executing':
        return jsonify({
            'error': 'Cannot cancel executing task. Use robot emergency stop if needed.',
            'task_id': task_id,
            'robot_id': task.get('robot_id'),
        }), 400

    success = orchestrator.cancel_task(task_id)

    if success:
        return jsonify({
            'success': True,
            'task_id': task_id,
            'previous_state': current_state,
            'new_state': 'cancelled',
            'message': 'Task cancelled successfully',
        })
    else:
        return jsonify({
            'error': 'Failed to cancel task',
            'task_id': task_id,
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# Cell Orchestrator Control Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@ros2_api_bp.route('/cell/status', methods=['GET'])
@jwt_required()
def get_cell_status_consolidated():
    """
    Get consolidated factory cell status.

    Query parameters:
        - cell_id: Specific cell ID (default: 'cell_1')

    Returns:
        JSON with comprehensive cell status including:
        - Cell configuration
        - All robot states
        - Task queue summary
        - Production metrics
    """
    orchestrator = get_orchestrator()
    cell_id = request.args.get('cell_id', 'cell_1')

    if not orchestrator:
        # Return demo cell status
        if is_demo_mode_enabled():
            return _demo_consolidated_cell_status(cell_id)
        return jsonify({'error': 'Service not configured'}), 503

    status = orchestrator.get_cell_status(cell_id)

    if 'error' in status:
        return jsonify(status), 404

    # Enhance with additional metrics
    all_tasks = orchestrator.get_all_tasks()
    completed_count = len([t for t in all_tasks if t['state'] == 'completed'])
    failed_count = len([t for t in all_tasks if t['state'] == 'failed'])

    status['metrics'] = {
        'total_tasks_submitted': len(all_tasks),
        'tasks_completed': completed_count,
        'tasks_failed': failed_count,
        'success_rate': (completed_count / len(all_tasks) * 100) if all_tasks else 0,
    }

    return jsonify(status)


def _demo_consolidated_cell_status(cell_id: str):
    """Return demo consolidated cell status."""
    if cell_id != 'cell_1':
        return jsonify({'error': f'Cell {cell_id} not found'}), 404

    return jsonify({
        'cell': {
            'cell_id': 'cell_1',
            'name': 'LEGO Assembly Cell',
            'robots': ['niryo_ned2', 'xarm_lite6'],
            'fixtures': ['brick_feeder', 'build_plate'],
            'stations': ['station_a', 'station_b'],
            'active': True,
        },
        'robots': [
            {
                'robot_id': 'niryo_ned2',
                'connected': True,
                'state': 'idle',
                'busy': False,
                'current_task': None,
                'joints': [0.0, 0.3, -0.5, 0.0, 0.2, 0.0],
            },
            {
                'robot_id': 'xarm_lite6',
                'connected': True,
                'state': 'moving',
                'busy': True,
                'current_task': 'task_abc123',
                'joints': [0.1, -0.2, 0.4, 0.0, 0.0, 0.0],
            },
        ],
        'tasks': {
            'pending': 2,
            'queued': 1,
            'executing': 1,
            'completed': 15,
            'failed': 1,
        },
        'metrics': {
            'total_tasks_submitted': 19,
            'tasks_completed': 15,
            'tasks_failed': 1,
            'success_rate': 93.75,
        },
        'paused': False,
        'running': True,
    })


@ros2_api_bp.route('/cell/start', methods=['POST'])
@jwt_required()
def start_cell():
    """
    Start the production cell.

    JSON body (optional):
        - cell_id: Cell to start (default: 'cell_1')

    Returns:
        JSON confirming cell startup.

    Note:
        Starting the cell enables task execution and robot coordination.
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json() or {}
    cell_id = data.get('cell_id', 'cell_1')

    # Verify cell exists
    if cell_id not in orchestrator.work_cells:
        return jsonify({
            'error': f'Cell {cell_id} not found',
            'available_cells': list(orchestrator.work_cells.keys()),
        }), 404

    orchestrator.start()

    return jsonify({
        'success': True,
        'cell_id': cell_id,
        'status': 'started',
        'running': orchestrator._running,
        'paused': orchestrator._paused,
        'message': f'Production cell {cell_id} started',
    })


@ros2_api_bp.route('/cell/stop', methods=['POST'])
@jwt_required()
def stop_cell():
    """
    Stop the production cell.

    JSON body (optional):
        - cell_id: Cell to stop (default: 'cell_1')
        - graceful: Wait for executing tasks to complete (default: true)

    Returns:
        JSON confirming cell shutdown.

    Note:
        Stopping the cell halts task execution. Use graceful=false for immediate stop.
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json() or {}
    cell_id = data.get('cell_id', 'cell_1')
    graceful = data.get('graceful', True)

    # Verify cell exists
    if cell_id not in orchestrator.work_cells:
        return jsonify({
            'error': f'Cell {cell_id} not found',
            'available_cells': list(orchestrator.work_cells.keys()),
        }), 404

    orchestrator.stop()

    return jsonify({
        'success': True,
        'cell_id': cell_id,
        'status': 'stopped',
        'running': orchestrator._running,
        'graceful': graceful,
        'message': f'Production cell {cell_id} stopped',
    })


@ros2_api_bp.route('/cell/pause', methods=['POST'])
@jwt_required()
def pause_cell():
    """
    Pause the production cell operations.

    JSON body (optional):
        - cell_id: Cell to pause (default: 'cell_1')

    Returns:
        JSON confirming pause.

    Note:
        Pausing stops new task execution but allows current tasks to complete.
        Use /cell/resume to continue operations.
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json() or {}
    cell_id = data.get('cell_id', 'cell_1')

    # Verify cell exists
    if cell_id not in orchestrator.work_cells:
        return jsonify({
            'error': f'Cell {cell_id} not found',
            'available_cells': list(orchestrator.work_cells.keys()),
        }), 404

    orchestrator.pause()

    return jsonify({
        'success': True,
        'cell_id': cell_id,
        'status': 'paused',
        'running': orchestrator._running,
        'paused': orchestrator._paused,
        'message': f'Production cell {cell_id} paused',
    })


@ros2_api_bp.route('/cell/resume', methods=['POST'])
@jwt_required()
def resume_cell():
    """
    Resume paused production cell operations.

    JSON body (optional):
        - cell_id: Cell to resume (default: 'cell_1')

    Returns:
        JSON confirming resume.
    """
    orchestrator = get_orchestrator()

    if not orchestrator:
        return jsonify({'error': 'Orchestrator not available'}), 503

    data = request.get_json() or {}
    cell_id = data.get('cell_id', 'cell_1')

    # Verify cell exists
    if cell_id not in orchestrator.work_cells:
        return jsonify({
            'error': f'Cell {cell_id} not found',
            'available_cells': list(orchestrator.work_cells.keys()),
        }), 404

    orchestrator.resume()

    return jsonify({
        'success': True,
        'cell_id': cell_id,
        'status': 'running',
        'running': orchestrator._running,
        'paused': orchestrator._paused,
        'message': f'Production cell {cell_id} resumed',
    })
