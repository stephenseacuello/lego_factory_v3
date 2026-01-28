"""
LEGO Factory v3 - ROS2 Robotics API Documentation
==================================================
Flask-RESTX namespace for ROS2 robotics control and cell orchestration.
"""

from flask import request
from flask_restx import Namespace, Resource, fields
import logging

logger = logging.getLogger(__name__)

# Create namespace
ros2_ns = Namespace(
    'ros2',
    description='ROS2 - Robot Operating System Integration & Cell Orchestration',
    path='/ros2',
)

# =============================================================================
# API MODELS - Bridge
# =============================================================================

bridge_status_model = ros2_ns.model('BridgeStatus', {
    'available': fields.Boolean(description='Bridge availability', example=True),
    'state': fields.String(
        description='Connection state',
        enum=['disconnected', 'connecting', 'connected', 'error'],
        example='connected'
    ),
    'connected': fields.Boolean(description='Connected to rosbridge', example=True),
    'url': fields.String(description='Rosbridge URL', example='ws://localhost:9090'),
    'subscriptions': fields.List(fields.String, description='Subscribed topics'),
    'error': fields.String(description='Error message if any'),
})

bridge_connect_request = ros2_ns.model('BridgeConnectRequest', {
    'host': fields.String(description='Rosbridge host', default='localhost', example='localhost'),
    'port': fields.Integer(description='Rosbridge port', default=9090, example=9090),
})

bridge_connect_response = ros2_ns.model('BridgeConnectResponse', {
    'success': fields.Boolean(description='Connection success', example=True),
    'state': fields.String(description='Connection state', example='connected'),
    'url': fields.String(description='Rosbridge URL', example='ws://localhost:9090'),
})


# =============================================================================
# API MODELS - Topics
# =============================================================================

topic_model = ros2_ns.model('Topic', {
    'name': fields.String(description='Topic name', example='/robot/joint_states'),
    'msg_type': fields.String(description='Message type', example='sensor_msgs/msg/JointState'),
    'queue_size': fields.Integer(description='Queue size', example=10),
})

topic_publish_request = ros2_ns.model('TopicPublishRequest', {
    'topic': fields.String(required=True, description='Topic name', example='/cmd_vel'),
    'msg_type': fields.String(required=True, description='Message type', example='geometry_msgs/msg/Twist'),
    'msg': fields.Raw(required=True, description='Message data', example={
        'linear': {'x': 0.5, 'y': 0.0, 'z': 0.0},
        'angular': {'x': 0.0, 'y': 0.0, 'z': 0.1}
    }),
})


# =============================================================================
# API MODELS - Services
# =============================================================================

service_call_request = ros2_ns.model('ServiceCallRequest', {
    'service': fields.String(required=True, description='Service name', example='/robot/set_gripper'),
    'srv_type': fields.String(required=True, description='Service type', example='std_srvs/srv/SetBool'),
    'args': fields.Raw(description='Service arguments', example={'data': True}),
    'timeout': fields.Float(description='Timeout in seconds', default=10.0, example=10.0),
})

service_call_response = ros2_ns.model('ServiceCallResponse', {
    'result': fields.Raw(description='Service call result'),
    'error': fields.String(description='Error message if failed'),
})


# =============================================================================
# API MODELS - Orchestrator
# =============================================================================

orchestrator_status_model = ros2_ns.model('OrchestratorStatus', {
    'available': fields.Boolean(description='Orchestrator availability', example=True),
    'running': fields.Boolean(description='Orchestrator running', example=True),
    'paused': fields.Boolean(description='Task execution paused', example=False),
    'cells': fields.List(fields.String, description='Registered work cells', example=['cell_1']),
    'total_tasks': fields.Integer(description='Total tasks', example=15),
    'error': fields.String(description='Error message if any'),
})


# =============================================================================
# API MODELS - Work Cells
# =============================================================================

work_cell_model = ros2_ns.model('WorkCell', {
    'cell_id': fields.String(description='Cell ID', example='cell_1'),
    'name': fields.String(description='Cell name', example='LEGO Assembly Cell'),
    'robots': fields.List(fields.String, description='Robot IDs in cell', example=['niryo_ned2', 'xarm_lite6']),
    'fixtures': fields.List(fields.String, description='Fixture IDs', example=['brick_feeder', 'build_plate']),
    'stations': fields.List(fields.String, description='Station IDs', example=['station_a', 'station_b']),
    'active': fields.Boolean(description='Cell active', example=True),
})

robot_state_model = ros2_ns.model('RobotState', {
    'status': fields.String(
        description='Robot status',
        enum=['idle', 'running', 'paused', 'error', 'offline'],
        example='idle'
    ),
    'joint_positions': fields.List(fields.Float, description='Joint positions (radians)', example=[0.0, 0.3, -0.5, 0.0, 0.2, 0.0]),
    'gripper_closed': fields.Boolean(description='Gripper closed state', example=False),
})

cell_status_model = ros2_ns.model('CellStatus', {
    'cell': fields.Nested(work_cell_model),
    'robots': fields.List(fields.Nested(ros2_ns.model('CellRobotStatus', {
        'robot_id': fields.String(description='Robot ID'),
        'status': fields.String(description='Robot status'),
        'busy': fields.Boolean(description='Robot busy'),
        'current_task': fields.String(description='Current task ID'),
        'joint_positions': fields.List(fields.Float, description='Joint positions'),
    }))),
    'tasks': fields.Nested(ros2_ns.model('CellTaskCounts', {
        'pending': fields.Integer(description='Pending tasks'),
        'queued': fields.Integer(description='Queued tasks'),
        'executing': fields.Integer(description='Executing tasks'),
    })),
    'paused': fields.Boolean(description='Cell paused'),
    'running': fields.Boolean(description='Cell running'),
})


# =============================================================================
# API MODELS - Tasks
# =============================================================================

task_pose = ros2_ns.model('TaskPose', {
    'x': fields.Float(description='X position (meters)', example=0.3),
    'y': fields.Float(description='Y position (meters)', example=0.1),
    'z': fields.Float(description='Z position (meters)', example=0.05),
    'roll': fields.Float(description='Roll angle (radians)', example=0.0),
    'pitch': fields.Float(description='Pitch angle (radians)', example=0.0),
    'yaw': fields.Float(description='Yaw angle (radians)', example=0.0),
})

task_model = ros2_ns.model('Task', {
    'task_id': fields.String(description='Task ID', example='task_abc123'),
    'task_type': fields.String(
        description='Task type',
        enum=['pick_place', 'assembly', 'inspection', 'transport', 'custom'],
        example='pick_place'
    ),
    'robot_id': fields.String(description='Assigned robot', example='xarm_lite6'),
    'priority': fields.Integer(description='Priority (1-10)', example=5),
    'state': fields.String(
        description='Task state',
        enum=['pending', 'queued', 'executing', 'completed', 'failed', 'cancelled'],
        example='executing'
    ),
    'parameters': fields.Raw(description='Task parameters', example={
        'pick_pose': {'x': 0.3, 'y': 0.1, 'z': 0.05},
        'place_pose': {'x': 0.4, 'y': -0.1, 'z': 0.05},
    }),
    'dependencies': fields.List(fields.String, description='Dependent task IDs'),
    'created_at': fields.DateTime(description='Creation time'),
    'started_at': fields.DateTime(description='Start time'),
    'completed_at': fields.DateTime(description='Completion time'),
    'error_message': fields.String(description='Error message if failed'),
    'result': fields.Raw(description='Task result'),
})

task_create = ros2_ns.model('TaskCreate', {
    'task_type': fields.String(
        required=True,
        description='Task type',
        enum=['pick_place', 'assembly', 'inspection', 'transport', 'custom'],
        example='pick_place'
    ),
    'robot_id': fields.String(description='Target robot (auto-assigned if not specified)'),
    'parameters': fields.Raw(description='Task parameters', example={
        'pick_pose': {'x': 0.3, 'y': 0.1, 'z': 0.05},
        'place_pose': {'x': 0.4, 'y': -0.1, 'z': 0.05},
    }),
    'priority': fields.Integer(description='Priority (1=highest, 10=lowest)', default=5, example=5),
    'dependencies': fields.List(fields.String, description='Task IDs that must complete first'),
})

task_create_response = ros2_ns.model('TaskCreateResponse', {
    'task_id': fields.String(description='Created task ID', example='task_abc123'),
    'status': fields.String(description='Status', example='submitted'),
})


# =============================================================================
# API MODELS - Robots
# =============================================================================

robot_model = ros2_ns.model('Robot', {
    'robot_id': fields.String(description='Robot ID', example='niryo_ned2'),
    'cell_id': fields.String(description='Assigned cell', example='cell_1'),
    'busy': fields.Boolean(description='Robot busy', example=False),
    'current_task': fields.String(description='Current task ID'),
    'state': fields.Nested(robot_state_model),
})

gripper_control_request = ros2_ns.model('GripperControlRequest', {
    'action': fields.String(
        required=True,
        description='Gripper action',
        enum=['open', 'close'],
        example='close'
    ),
    'force': fields.Integer(description='Grip force (0-100)', default=50, example=50),
})


# =============================================================================
# RESOURCES - Bridge
# =============================================================================

@ros2_ns.route('/bridge/status')
class BridgeStatus(Resource):
    """ROS2 bridge status endpoint."""

    @ros2_ns.doc(
        'bridge_status',
        responses={
            200: ('Bridge status', bridge_status_model),
        }
    )
    @ros2_ns.marshal_with(bridge_status_model)
    def get(self):
        """
        Get ROS2 bridge connection status.

        Returns the current connection state of the rosbridge WebSocket
        connection used to communicate with ROS2.

        **States:**
        - `disconnected`: Not connected to rosbridge
        - `connecting`: Connection in progress
        - `connected`: Active connection
        - `error`: Connection error

        **Rosbridge:**
        The system uses rosbridge_suite to communicate with ROS2.
        Default connection is ws://localhost:9090.
        """
        from api.routes.ros2_api import bridge_status
        return bridge_status()


@ros2_ns.route('/bridge/connect')
class BridgeConnect(Resource):
    """ROS2 bridge connection endpoint."""

    @ros2_ns.doc(
        'bridge_connect',
        responses={
            200: ('Connection result', bridge_connect_response),
            503: 'Bridge not available',
        }
    )
    @ros2_ns.expect(bridge_connect_request)
    @ros2_ns.marshal_with(bridge_connect_response)
    def post(self):
        """
        Connect to rosbridge server.

        Establishes a WebSocket connection to the rosbridge server.

        **Prerequisites:**
        - rosbridge_suite must be running
        - Network access to the rosbridge host/port

        **Command to start rosbridge:**
        ```bash
        ros2 launch rosbridge_server rosbridge_websocket_launch.xml
        ```
        """
        from api.routes.ros2_api import bridge_connect
        return bridge_connect()


@ros2_ns.route('/bridge/disconnect')
class BridgeDisconnect(Resource):
    """ROS2 bridge disconnection endpoint."""

    @ros2_ns.doc(
        'bridge_disconnect',
        responses={
            200: 'Disconnected',
            503: 'Bridge not available',
        }
    )
    def post(self):
        """
        Disconnect from rosbridge server.

        Closes the WebSocket connection to rosbridge.
        All subscriptions will be terminated.
        """
        from api.routes.ros2_api import bridge_disconnect
        return bridge_disconnect()


# =============================================================================
# RESOURCES - Topics
# =============================================================================

@ros2_ns.route('/topics')
class TopicList(Resource):
    """ROS2 topic listing endpoint."""

    @ros2_ns.doc(
        'list_topics',
        responses={
            200: 'List of subscribed topics',
            503: 'Bridge not available',
        }
    )
    def get(self):
        """
        List subscribed topics.

        Returns all topics currently being subscribed to via the rosbridge
        connection. These topics are available for real-time data streaming.
        """
        from api.routes.ros2_api import list_topics
        return list_topics()


@ros2_ns.route('/topics/publish')
class TopicPublish(Resource):
    """ROS2 topic publish endpoint."""

    @ros2_ns.doc(
        'publish_topic',
        responses={
            200: 'Message published',
            400: 'Invalid message',
            503: 'Bridge not connected',
        }
    )
    @ros2_ns.expect(topic_publish_request, validate=True)
    def post(self):
        """
        Publish a message to a ROS2 topic.

        Sends a message to the specified topic via rosbridge.

        **Common Message Types:**
        - `geometry_msgs/msg/Twist`: Velocity commands
        - `std_msgs/msg/String`: String messages
        - `std_msgs/msg/Bool`: Boolean commands
        - `sensor_msgs/msg/JointState`: Joint state commands

        **Example - Twist Message:**
        ```json
        {
            "topic": "/cmd_vel",
            "msg_type": "geometry_msgs/msg/Twist",
            "msg": {
                "linear": {"x": 0.5, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.1}
            }
        }
        ```
        """
        from api.routes.ros2_api import publish_topic
        return publish_topic()


# =============================================================================
# RESOURCES - Services
# =============================================================================

@ros2_ns.route('/services/call')
class ServiceCall(Resource):
    """ROS2 service call endpoint."""

    @ros2_ns.doc(
        'call_service',
        responses={
            200: ('Service result', service_call_response),
            400: 'Invalid request',
            500: 'Service call failed',
            503: 'Bridge not available',
        }
    )
    @ros2_ns.expect(service_call_request, validate=True)
    @ros2_ns.marshal_with(service_call_response)
    def post(self):
        """
        Call a ROS2 service.

        Invokes a ROS2 service and returns the result.

        **Common Service Types:**
        - `std_srvs/srv/SetBool`: Enable/disable functionality
        - `std_srvs/srv/Trigger`: Trigger an action
        - `std_srvs/srv/Empty`: No arguments

        **Example - SetBool Service:**
        ```json
        {
            "service": "/robot/enable",
            "srv_type": "std_srvs/srv/SetBool",
            "args": {"data": true},
            "timeout": 10.0
        }
        ```

        **Note:** Service calls are blocking. Set an appropriate timeout.
        """
        from api.routes.ros2_api import call_service
        return call_service()


# =============================================================================
# RESOURCES - Orchestrator
# =============================================================================

@ros2_ns.route('/orchestrator/status')
class OrchestratorStatus(Resource):
    """Cell orchestrator status endpoint."""

    @ros2_ns.doc(
        'orchestrator_status',
        responses={
            200: ('Orchestrator status', orchestrator_status_model),
        }
    )
    @ros2_ns.marshal_with(orchestrator_status_model)
    def get(self):
        """
        Get cell orchestrator status.

        Returns the status of the cell orchestrator which manages
        task distribution and coordination across robots in work cells.
        """
        from api.routes.ros2_api import orchestrator_status
        return orchestrator_status()


@ros2_ns.route('/orchestrator/start')
class OrchestratorStart(Resource):
    """Orchestrator start endpoint."""

    @ros2_ns.doc(
        'orchestrator_start',
        responses={
            200: 'Orchestrator started',
            503: 'Orchestrator not available',
        }
    )
    def post(self):
        """
        Start the cell orchestrator.

        Begins task execution and robot coordination.
        Tasks in the queue will start being dispatched.
        """
        from api.routes.ros2_api import orchestrator_start
        return orchestrator_start()


@ros2_ns.route('/orchestrator/stop')
class OrchestratorStop(Resource):
    """Orchestrator stop endpoint."""

    @ros2_ns.doc(
        'orchestrator_stop',
        responses={
            200: 'Orchestrator stopped',
            503: 'Orchestrator not available',
        }
    )
    def post(self):
        """
        Stop the cell orchestrator.

        Stops task execution. Running tasks will complete,
        but no new tasks will be dispatched.
        """
        from api.routes.ros2_api import orchestrator_stop
        return orchestrator_stop()


@ros2_ns.route('/orchestrator/pause')
class OrchestratorPause(Resource):
    """Orchestrator pause endpoint."""

    @ros2_ns.doc(
        'orchestrator_pause',
        responses={
            200: 'Task execution paused',
            503: 'Orchestrator not available',
        }
    )
    def post(self):
        """
        Pause task execution.

        Pauses dispatching of new tasks. Currently executing
        tasks will continue until completion.
        """
        from api.routes.ros2_api import orchestrator_pause
        return orchestrator_pause()


@ros2_ns.route('/orchestrator/resume')
class OrchestratorResume(Resource):
    """Orchestrator resume endpoint."""

    @ros2_ns.doc(
        'orchestrator_resume',
        responses={
            200: 'Task execution resumed',
            503: 'Orchestrator not available',
        }
    )
    def post(self):
        """
        Resume task execution.

        Resumes dispatching of tasks after a pause.
        """
        from api.routes.ros2_api import orchestrator_resume
        return orchestrator_resume()


# =============================================================================
# RESOURCES - Work Cells
# =============================================================================

@ros2_ns.route('/cells')
class CellList(Resource):
    """Work cell listing endpoint."""

    @ros2_ns.doc(
        'list_cells',
        responses={
            200: 'List of work cells',
        }
    )
    def get(self):
        """
        List work cells.

        Returns all configured work cells with their robots and fixtures.

        **Work Cell:**
        A work cell is a defined area containing one or more robots,
        fixtures, and stations that work together on manufacturing tasks.
        """
        from api.routes.ros2_api import list_cells
        return list_cells()


@ros2_ns.route('/cells/<string:cell_id>')
@ros2_ns.param('cell_id', 'Work cell ID')
class CellDetail(Resource):
    """Work cell detail endpoint."""

    @ros2_ns.doc(
        'get_cell_status',
        responses={
            200: ('Cell status', cell_status_model),
            404: 'Cell not found',
        }
    )
    @ros2_ns.marshal_with(cell_status_model)
    def get(self, cell_id):
        """
        Get detailed cell status.

        Returns comprehensive status including:
        - Cell configuration
        - Robot states and positions
        - Task queue statistics
        - Operational status
        """
        from api.routes.ros2_api import get_cell_status
        return get_cell_status(cell_id)


# =============================================================================
# RESOURCES - Tasks
# =============================================================================

@ros2_ns.route('/tasks')
class TaskList(Resource):
    """Task listing and creation endpoint."""

    @ros2_ns.doc(
        'list_tasks',
        params={
            'state': {'description': 'Filter by state', 'enum': ['pending', 'queued', 'executing', 'completed', 'failed']},
            'robot_id': {'description': 'Filter by robot'},
        },
        responses={
            200: 'List of tasks',
        }
    )
    def get(self):
        """
        List tasks.

        Returns tasks with optional filtering by state or robot.
        """
        from api.routes.ros2_api import list_tasks
        return list_tasks()

    @ros2_ns.doc(
        'submit_task',
        responses={
            201: ('Task submitted', task_create_response),
            400: 'Invalid task',
            503: 'Orchestrator not available',
        }
    )
    @ros2_ns.expect(task_create, validate=True)
    @ros2_ns.marshal_with(task_create_response, code=201)
    def post(self):
        """
        Submit a new task.

        Creates a task for execution by the cell orchestrator.

        **Task Types:**
        - `pick_place`: Pick and place operation
        - `assembly`: Assembly operation
        - `inspection`: Vision inspection
        - `transport`: Material transport
        - `custom`: Custom operation with G-code or commands

        **Example - Pick and Place:**
        ```json
        {
            "task_type": "pick_place",
            "parameters": {
                "pick_pose": {"x": 0.3, "y": 0.1, "z": 0.05},
                "place_pose": {"x": 0.4, "y": -0.1, "z": 0.05},
                "approach_height": 0.1,
                "grip_force": 50
            },
            "priority": 5
        }
        ```

        **Robot Assignment:**
        If `robot_id` is not specified, the orchestrator will
        automatically assign an available robot.
        """
        from api.routes.ros2_api import submit_task
        return submit_task()


@ros2_ns.route('/tasks/<string:task_id>')
@ros2_ns.param('task_id', 'Task ID')
class TaskDetail(Resource):
    """Task detail endpoint."""

    @ros2_ns.doc(
        'get_task',
        responses={
            200: ('Task details', task_model),
            404: 'Task not found',
        }
    )
    @ros2_ns.marshal_with(task_model)
    def get(self, task_id):
        """
        Get task details.

        Returns complete task information including parameters,
        state, timing, and results.
        """
        from api.routes.ros2_api import get_task
        return get_task(task_id)


@ros2_ns.route('/tasks/<string:task_id>/cancel')
@ros2_ns.param('task_id', 'Task ID')
class TaskCancel(Resource):
    """Task cancellation endpoint."""

    @ros2_ns.doc(
        'cancel_task',
        responses={
            200: 'Task cancelled',
            400: 'Task cannot be cancelled (already executing or completed)',
            404: 'Task not found',
        }
    )
    def post(self, task_id):
        """
        Cancel a pending or queued task.

        Only pending or queued tasks can be cancelled.
        Executing tasks cannot be cancelled through this endpoint.

        **To stop an executing task:**
        Use the robot emergency stop endpoint instead.
        """
        from api.routes.ros2_api import cancel_task
        return cancel_task(task_id)


# =============================================================================
# RESOURCES - Robots
# =============================================================================

@ros2_ns.route('/robots')
class RobotList(Resource):
    """Robot listing endpoint."""

    @ros2_ns.doc(
        'list_robots',
        responses={
            200: 'List of robots',
        }
    )
    def get(self):
        """
        List available robots.

        Returns all robots registered with the orchestrator,
        including their current state and assigned tasks.
        """
        from api.routes.ros2_api import list_robots
        return list_robots()


@ros2_ns.route('/robots/<string:robot_id>/queue')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotQueue(Resource):
    """Robot task queue endpoint."""

    @ros2_ns.doc(
        'get_robot_queue',
        responses={
            200: 'Robot task queue',
            503: 'Orchestrator not available',
        }
    )
    def get(self, robot_id):
        """
        Get queued tasks for a robot.

        Returns tasks assigned to the specified robot
        that are waiting to be executed.
        """
        from api.routes.ros2_api import get_robot_queue
        return get_robot_queue(robot_id)


@ros2_ns.route('/robots/<string:robot_id>/home')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotHome(Resource):
    """Robot homing endpoint."""

    @ros2_ns.doc(
        'robot_home',
        responses={
            200: 'Home task submitted',
            503: 'Orchestrator not available',
        }
    )
    def post(self, robot_id):
        """
        Send robot to home position.

        Submits a high-priority task to move the robot to its
        home/reference position.

        **Note:** This is a queued operation, not immediate.
        For safety, the robot will complete its current task first.
        """
        from api.routes.ros2_api import robot_home
        return robot_home(robot_id)


@ros2_ns.route('/robots/<string:robot_id>/stop')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotStop(Resource):
    """Robot emergency stop endpoint."""

    @ros2_ns.doc(
        'robot_stop',
        responses={
            200: 'Emergency stop sent',
            503: 'ROS2 bridge not available',
        }
    )
    def post(self, robot_id):
        """
        Emergency stop a robot.

        Immediately stops all robot motion. This is a safety
        function that bypasses the task queue.

        **Warning:** This will immediately halt the robot.
        Any in-progress task will fail.

        **Recovery:**
        After an emergency stop, the robot may need to be
        re-enabled and homed before resuming operations.
        """
        from api.routes.ros2_api import robot_stop
        return robot_stop(robot_id)


@ros2_ns.route('/robots/<string:robot_id>/gripper')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotGripper(Resource):
    """Robot gripper control endpoint."""

    @ros2_ns.doc(
        'robot_gripper',
        responses={
            200: 'Gripper command submitted',
            400: 'Invalid request',
            503: 'Orchestrator not available',
        }
    )
    @ros2_ns.expect(gripper_control_request, validate=True)
    def post(self, robot_id):
        """
        Control robot gripper.

        Opens or closes the robot's end effector/gripper.

        **Parameters:**
        - `action`: 'open' or 'close'
        - `force`: Grip force 0-100 (for close action)

        **Note:** This is a queued operation. For immediate
        gripper control, use the service call endpoint directly.
        """
        from api.routes.ros2_api import robot_gripper
        return robot_gripper(robot_id)


# =============================================================================
# RESOURCES - Advanced Robot Control
# =============================================================================

@ros2_ns.route('/robots/<string:robot_id>/move')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotMove(Resource):
    """Robot move endpoint."""

    @ros2_ns.doc(
        'robot_move',
        responses={
            200: 'Move task submitted',
            400: 'Invalid pose',
            503: 'Orchestrator not available',
        }
    )
    @ros2_ns.expect(ros2_ns.model('RobotMoveRequest', {
        'pose': fields.Nested(task_pose, required=True, description='Target pose'),
        'speed': fields.Float(description='Movement speed (0-1)', default=0.5, example=0.5),
        'motion_type': fields.String(
            description='Motion type',
            enum=['joint', 'linear'],
            default='joint',
            example='linear'
        ),
    }), validate=True)
    def post(self, robot_id):
        """
        Move robot to a pose.

        Moves the robot's end effector to the specified position
        and orientation.

        **Motion Types:**
        - `joint`: Joint-space interpolation (faster, less predictable path)
        - `linear`: Cartesian-space interpolation (straight line path)

        **Coordinate Frame:**
        Poses are specified in the robot's base frame unless
        otherwise configured.
        """
        from services.robotics.ros2_bridge import get_ros2_bridge
        import uuid

        data = request.json
        pose = data.get('pose', {})
        speed = data.get('speed', 0.5)
        motion_type = data.get('motion_type', 'joint')

        bridge = get_ros2_bridge()

        if not bridge.is_connected:
            ros2_ns.abort(503, 'ROS2 bridge not connected')

        # Create a move task ID
        task_id = f'task_move_{uuid.uuid4().hex[:8]}'

        # Publish move command to robot
        move_msg = {
            'robot_id': robot_id,
            'task_id': task_id,
            'pose': {
                'position': {'x': pose.get('x', 0), 'y': pose.get('y', 0), 'z': pose.get('z', 0)},
                'orientation': {'roll': pose.get('roll', 0), 'pitch': pose.get('pitch', 0), 'yaw': pose.get('yaw', 0)},
            },
            'speed': speed,
            'motion_type': motion_type,
        }

        bridge.publish(
            f'/robot/{robot_id}/move_command',
            'lego_factory_msgs/msg/MoveCommand',
            move_msg
        )

        return {'task_id': task_id, 'status': 'submitted'}, 200


@ros2_ns.route('/robots/<string:robot_id>/joints')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotJoints(Resource):
    """Robot joint control endpoint."""

    @ros2_ns.doc(
        'robot_joints',
        responses={
            200: 'Joint move task submitted',
            400: 'Invalid joint positions',
            503: 'Orchestrator not available',
        }
    )
    @ros2_ns.expect(ros2_ns.model('RobotJointsRequest', {
        'positions': fields.List(
            fields.Float,
            required=True,
            description='Target joint positions (radians)',
            example=[0.0, 0.3, -0.5, 0.0, 0.2, 0.0]
        ),
        'speed': fields.Float(description='Movement speed (0-1)', default=0.5),
    }), validate=True)
    def post(self, robot_id):
        """
        Move robot joints to positions.

        Directly controls joint positions for precise motion.

        **Joint Order:**
        Positions are specified in order from base to end effector.
        The number of values must match the robot's DOF.
        """
        from services.robotics.ros2_bridge import get_ros2_bridge
        import uuid

        data = request.json
        positions = data.get('positions', [])
        speed = data.get('speed', 0.5)

        if not positions:
            ros2_ns.abort(400, 'Joint positions are required')

        bridge = get_ros2_bridge()

        if not bridge.is_connected:
            ros2_ns.abort(503, 'ROS2 bridge not connected')

        # Create a joint move task ID
        task_id = f'task_joints_{uuid.uuid4().hex[:8]}'

        # Publish joint move command
        joint_msg = {
            'robot_id': robot_id,
            'task_id': task_id,
            'positions': positions,
            'speed': speed,
        }

        bridge.publish(
            f'/robot/{robot_id}/joint_command',
            'lego_factory_msgs/msg/JointCommand',
            joint_msg
        )

        return {'task_id': task_id, 'status': 'submitted'}, 200


@ros2_ns.route('/robots/<string:robot_id>/state')
@ros2_ns.param('robot_id', 'Robot ID')
class RobotStateResource(Resource):
    """Robot state endpoint."""

    @ros2_ns.doc(
        'get_robot_state',
        responses={
            200: ('Robot state', robot_state_model),
            404: 'Robot not found',
        }
    )
    @ros2_ns.marshal_with(robot_state_model)
    def get(self, robot_id):
        """
        Get current robot state.

        Returns the real-time state including:
        - Joint positions
        - Gripper state
        - Operational status
        - Error conditions

        **Real-time Updates:**
        For continuous state updates, use the WebSocket subscription
        to the robot's joint_states topic.
        """
        from services.robotics.ros2_bridge import get_ros2_bridge

        bridge = get_ros2_bridge()

        # Get robot state from ROS2 bridge
        state = bridge.get_robot_state(robot_id)

        if state is None:
            # Return default state if bridge not connected or robot not found
            return {
                'status': 'offline',
                'joint_positions': [0.0] * 6,
                'gripper_closed': False,
            }

        return {
            'status': state.get('state', 'unknown'),
            'joint_positions': state.get('joints', [0.0] * 6),
            'gripper_closed': not state.get('gripper_open', True),
        }
