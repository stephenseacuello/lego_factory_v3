"""
LEGO Factory v3 - SCADA API Documentation
==========================================
Flask-RESTX namespace for SCADA endpoints (Machines, Tags, Alarms).
"""

from flask import request
from flask_restx import Namespace, Resource, fields
import logging

logger = logging.getLogger(__name__)

# Create namespace
scada_ns = Namespace(
    'scada',
    description='SCADA - Supervisory Control and Data Acquisition (Level 2)',
    path='/scada',
)

# =============================================================================
# API MODELS - Machines
# =============================================================================

position_model = scada_ns.model('Position', {
    'x': fields.Float(description='X axis position (mm)', example=125.5),
    'y': fields.Float(description='Y axis position (mm)', example=85.2),
    'z': fields.Float(description='Z axis position (mm)', example=45.0),
    'a': fields.Float(description='A axis position (degrees)', example=0.0),
    'b': fields.Float(description='B axis position (degrees)', example=0.0),
    'c': fields.Float(description='C axis position (degrees)', example=0.0),
})

work_envelope_model = scada_ns.model('WorkEnvelope', {
    'x': fields.Float(description='X axis maximum (mm)', example=300),
    'y': fields.Float(description='Y axis maximum (mm)', example=300),
    'z': fields.Float(description='Z axis maximum (mm)', example=200),
})

connection_config_model = scada_ns.model('ConnectionConfig', {
    'port': fields.String(description='Serial port or network address', example='/dev/ttyUSB0'),
    'baud_rate': fields.Integer(description='Baud rate for serial', example=115200),
    'ip': fields.String(description='IP address for network controllers', example='192.168.1.100'),
    'serial': fields.String(description='Device serial number'),
    'access_code': fields.String(description='Access code for authentication'),
})

machine_model = scada_ns.model('Machine', {
    'machine_id': fields.String(description='Unique machine identifier', example='prusa_mk4_1'),
    'name': fields.String(description='Machine display name', example='Prusa MK4 #1'),
    'description': fields.String(description='Machine description', example='Primary 3D printer for brick production'),
    'machine_type': fields.String(
        description='Type of machine',
        enum=['printer_3d', 'cnc_mill', 'cnc_lathe', 'robot_arm', 'conveyor', 'sensor_station'],
        example='printer_3d'
    ),
    'controller_type': fields.String(
        description='Controller firmware type',
        enum=['tinyg', 'grbl', 'marlin', 'bambu', 'ros2', 'simulation'],
        example='marlin'
    ),
    'connection_type': fields.String(
        description='Connection method',
        enum=['serial', 'network', 'mqtt', 'ros2'],
        example='serial'
    ),
    'status': fields.String(
        description='Current machine status',
        enum=['disconnected', 'idle', 'running', 'hold', 'homing', 'alarm', 'error'],
        example='idle'
    ),
    'connected': fields.Boolean(description='Connection status', example=True),
    'enabled': fields.Boolean(description='Machine enabled for production', example=True),
    'area': fields.String(description='Factory area', example='Assembly Cell 1'),
    'cell': fields.String(description='Work cell', example='Cell-A'),
    'work_envelope': fields.Nested(work_envelope_model),
    'connection_config': fields.Nested(connection_config_model),
})

machine_status_model = scada_ns.model('MachineStatus', {
    'status': fields.String(
        description='Current machine state',
        enum=['disconnected', 'idle', 'running', 'hold', 'homing', 'alarm', 'error'],
        example='running'
    ),
    'connected': fields.Boolean(description='Connection status', example=True),
    'position': fields.Nested(position_model),
    'feed_rate': fields.Float(description='Current feed rate (mm/min)', example=1500.0),
    'spindle_speed': fields.Float(description='Current spindle/extruder speed', example=0.0),
    'progress_pct': fields.Float(description='Job progress percentage', example=45.5),
    'current_line': fields.Integer(description='Current G-code line number', example=1250),
    'total_lines': fields.Integer(description='Total G-code lines', example=2750),
    'temperatures': fields.Raw(description='Temperature readings', example={'nozzle': 215, 'bed': 60}),
    'error_message': fields.String(description='Error message if any'),
})

machine_list_response = scada_ns.model('MachineListResponse', {
    'machines': fields.List(fields.Nested(machine_model)),
    'count': fields.Integer(description='Total machine count', example=5),
})

jog_request = scada_ns.model('JogRequest', {
    'axis': fields.String(required=True, description='Axis to jog', enum=['X', 'Y', 'Z', 'A', 'B', 'C'], example='X'),
    'distance': fields.Float(required=True, description='Distance to move (mm)', example=10.0),
    'feed_rate': fields.Float(description='Feed rate (mm/min)', default=500, example=500),
})

gcode_request = scada_ns.model('GCodeRequest', {
    'gcode': fields.String(required=True, description='G-code command or program', example='G28 X Y'),
})

axes_request = scada_ns.model('AxesRequest', {
    'axes': fields.String(description='Axes to operate on', default='XYZ', example='XYZ'),
})


# =============================================================================
# API MODELS - Alarms
# =============================================================================

alarm_model = scada_ns.model('Alarm', {
    'alarm_id': fields.String(description='Unique alarm identifier', example='ALM-001'),
    'tag_name': fields.String(description='Source tag name', example='PRINTER_01.TEMP_NOZZLE'),
    'priority': fields.String(
        description='Alarm priority level',
        enum=['critical', 'high', 'medium', 'low', 'info'],
        example='high'
    ),
    'state': fields.String(
        description='Alarm state',
        enum=['active_unack', 'active_ack', 'cleared_unack', 'cleared'],
        example='active_unack'
    ),
    'source': fields.String(description='Alarm source/machine', example='Prusa MK4 #1'),
    'message': fields.String(description='Alarm message', example='Nozzle temperature exceeded limit'),
    'timestamp': fields.DateTime(description='Alarm trigger time'),
    'value': fields.Float(description='Value that triggered alarm', example=255.5),
    'setpoint': fields.Float(description='Alarm setpoint', example=220.0),
    'engineering_unit': fields.String(description='Engineering unit', example='C'),
    'acknowledged_at': fields.DateTime(description='Acknowledgment time'),
    'acknowledged_by': fields.String(description='User who acknowledged'),
    'cleared_at': fields.DateTime(description='Clear time'),
})

alarm_list_response = scada_ns.model('AlarmListResponse', {
    'alarms': fields.List(fields.Nested(alarm_model)),
    'count': fields.Integer(description='Total alarm count', example=5),
})

alarm_summary_model = scada_ns.model('AlarmSummary', {
    'total': fields.Integer(description='Total active alarms', example=12),
    'critical': fields.Integer(description='Critical priority count', example=2),
    'high': fields.Integer(description='High priority count', example=3),
    'medium': fields.Integer(description='Medium priority count', example=5),
    'low': fields.Integer(description='Low priority count', example=2),
    'unacknowledged': fields.Integer(description='Unacknowledged count', example=7),
})

acknowledge_request = scada_ns.model('AcknowledgeRequest', {
    'user_id': fields.String(description='User ID acknowledging', default='operator', example='operator'),
    'comment': fields.String(description='Acknowledgment comment', example='Investigating issue'),
})

batch_acknowledge_request = scada_ns.model('BatchAcknowledgeRequest', {
    'alarm_ids': fields.List(fields.String, required=True, description='Alarm IDs to acknowledge', example=['ALM-001', 'ALM-002']),
    'user_id': fields.String(description='User ID acknowledging', default='operator'),
})


# =============================================================================
# API MODELS - Tags
# =============================================================================

tag_model = scada_ns.model('Tag', {
    'tag_id': fields.String(description='Unique tag identifier', example='PRINTER_01.TEMP_NOZZLE'),
    'name': fields.String(description='Tag display name', example='Nozzle Temperature'),
    'description': fields.String(description='Tag description'),
    'data_type': fields.String(
        description='Data type',
        enum=['float', 'int', 'bool', 'string', 'array'],
        example='float'
    ),
    'value': fields.Raw(description='Current value', example=215.5),
    'quality': fields.String(
        description='Value quality',
        enum=['good', 'bad', 'uncertain'],
        example='good'
    ),
    'timestamp': fields.DateTime(description='Last update time'),
    'engineering_unit': fields.String(description='Engineering unit', example='C'),
    'machine_id': fields.String(description='Associated machine', example='prusa_mk4_1'),
    'scan_rate_ms': fields.Integer(description='Scan rate in milliseconds', example=1000),
    'deadband': fields.Float(description='Deadband for change detection', example=0.5),
    'alarm_enabled': fields.Boolean(description='Alarm enabled', example=True),
    'high_high_limit': fields.Float(description='High-high alarm limit', example=260.0),
    'high_limit': fields.Float(description='High alarm limit', example=240.0),
    'low_limit': fields.Float(description='Low alarm limit', example=180.0),
    'low_low_limit': fields.Float(description='Low-low alarm limit', example=150.0),
})

tag_list_response = scada_ns.model('TagListResponse', {
    'tags': fields.List(fields.Nested(tag_model)),
    'count': fields.Integer(description='Total tag count'),
})

tag_write_request = scada_ns.model('TagWriteRequest', {
    'value': fields.Raw(required=True, description='Value to write', example=200.0),
})


# =============================================================================
# API MODELS - Recipes
# =============================================================================

recipe_parameter_model = scada_ns.model('RecipeParameter', {
    'name': fields.String(description='Parameter name', example='layer_height'),
    'value': fields.Raw(description='Parameter value', example=0.2),
    'unit': fields.String(description='Unit', example='mm'),
    'min_value': fields.Float(description='Minimum value'),
    'max_value': fields.Float(description='Maximum value'),
})

recipe_model = scada_ns.model('Recipe', {
    'recipe_id': fields.String(description='Unique recipe identifier', example='RCP-BRICK-2X4'),
    'name': fields.String(description='Recipe name', example='2x4 Brick Standard'),
    'version': fields.String(description='Recipe version', example='1.2'),
    'description': fields.String(description='Recipe description'),
    'product_id': fields.String(description='Target product', example='brick_2x4'),
    'machine_type': fields.String(description='Target machine type', example='printer_3d'),
    'status': fields.String(
        description='Recipe status',
        enum=['draft', 'pending_approval', 'approved', 'obsolete'],
        example='approved'
    ),
    'parameters': fields.List(fields.Nested(recipe_parameter_model)),
    'gcode_file': fields.String(description='Associated G-code file path'),
    'estimated_time_min': fields.Integer(description='Estimated time in minutes', example=45),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'approved_by': fields.String(description='Approver ID'),
    'approved_at': fields.DateTime(description='Approval timestamp'),
})


# =============================================================================
# API MODELS - Serial Ports
# =============================================================================

serial_port_model = scada_ns.model('SerialPort', {
    'device': fields.String(description='Device path', example='/dev/ttyUSB0'),
    'description': fields.String(description='Port description', example='USB Serial'),
    'hwid': fields.String(description='Hardware ID'),
    'manufacturer': fields.String(description='Manufacturer'),
    'product': fields.String(description='Product name'),
})


# =============================================================================
# API MODELS - Printers
# =============================================================================

printer_status_model = scada_ns.model('PrinterStatus', {
    'printer_id': fields.String(description='Printer ID', example='bambu_x1c_1'),
    'connected': fields.Boolean(description='Connection status', example=True),
    'state': fields.String(
        description='Printer state',
        enum=['offline', 'idle', 'printing', 'paused', 'error', 'finished'],
        example='printing'
    ),
    'temperatures': fields.Raw(description='Temperature readings', example={'nozzle': 215, 'bed': 60, 'chamber': 40}),
    'progress': fields.Float(description='Print progress percentage', example=45.5),
    'file_name': fields.String(description='Current file name', example='brick_2x4.gcode'),
    'remaining_time': fields.Integer(description='Remaining time in seconds', example=3600),
    'layer_current': fields.Integer(description='Current layer', example=50),
    'layer_total': fields.Integer(description='Total layers', example=150),
    'print_speed': fields.Integer(description='Print speed percentage', example=100),
})

temperature_request = scada_ns.model('TemperatureRequest', {
    'nozzle': fields.Integer(description='Nozzle temperature', example=215),
    'bed': fields.Integer(description='Bed temperature', example=60),
})

preheat_request = scada_ns.model('PreheatRequest', {
    'material': fields.String(
        required=True,
        description='Material type',
        enum=['pla', 'petg', 'abs', 'tpu'],
        example='pla'
    ),
})

print_start_request = scada_ns.model('PrintStartRequest', {
    'filename': fields.String(required=True, description='File to print', example='brick_2x4.gcode'),
})

light_control_request = scada_ns.model('LightControlRequest', {
    'light': fields.String(description='Light to control', enum=['chamber', 'work'], default='chamber'),
    'state': fields.Boolean(description='Light state (true=on)', default=True),
})

speed_request = scada_ns.model('SpeedRequest', {
    'profile': fields.String(
        description='Speed profile',
        enum=['silent', 'standard', 'sport', 'ludicrous'],
        default='standard',
        example='standard'
    ),
})


# =============================================================================
# RESOURCES - Machines
# =============================================================================

@scada_ns.route('/machines')
class MachineList(Resource):
    """Machine listing and management."""

    @scada_ns.doc(
        'list_machines',
        responses={
            200: ('List of machines', machine_list_response),
        }
    )
    @scada_ns.marshal_with(machine_list_response)
    def get(self):
        """
        List all configured machines.

        Returns all machines defined in the system configuration along with
        their current connection and operational status.

        **Machine Types:**
        - `printer_3d` - FDM/SLA 3D printers (Prusa, Bambu, etc.)
        - `cnc_mill` - CNC milling machines
        - `robot_arm` - Robotic arms (Niryo, xArm, etc.)
        - `conveyor` - Conveyor systems
        - `sensor_station` - Sensor/inspection stations

        **Controller Types:**
        - `tinyg` - TinyG/g2core motion controller
        - `grbl` - GRBL CNC controller
        - `marlin` - Marlin 3D printer firmware
        - `bambu` - Bambu Lab proprietary protocol
        - `ros2` - ROS2 robot control
        - `simulation` - Software simulation
        """
        # Implementation delegated to actual API route
        from api.routes.scada_api import list_machines
        return list_machines()


@scada_ns.route('/machines/<string:machine_id>')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineDetail(Resource):
    """Single machine operations."""

    @scada_ns.doc(
        'get_machine',
        responses={
            200: ('Machine details', machine_model),
            404: 'Machine not found',
        }
    )
    @scada_ns.marshal_with(machine_model)
    def get(self, machine_id):
        """
        Get detailed information about a specific machine.

        Returns the complete configuration and current status of the specified machine.
        """
        from api.routes.scada_api import get_machine
        return get_machine(machine_id)


@scada_ns.route('/machines/<string:machine_id>/status')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineStatusResource(Resource):
    """Machine status endpoint."""

    @scada_ns.doc(
        'get_machine_status',
        responses={
            200: ('Machine status', machine_status_model),
            404: 'Machine not found',
        }
    )
    @scada_ns.marshal_with(machine_status_model)
    def get(self, machine_id):
        """
        Get real-time machine status.

        Returns current operational status including:
        - Connection state
        - Position (for CNC/robots)
        - Feed rate and spindle speed
        - Job progress (if running)
        - Temperature readings (for printers)
        - Any active errors

        **Polling vs WebSocket:**
        For real-time updates, consider using the WebSocket connection
        instead of polling this endpoint.
        """
        from api.routes.scada_api import get_machine_status
        return get_machine_status(machine_id)


@scada_ns.route('/machines/<string:machine_id>/connect')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineConnect(Resource):
    """Machine connection endpoint."""

    @scada_ns.doc(
        'connect_machine',
        responses={
            200: 'Connection successful',
            404: 'Machine not found',
            500: 'Connection failed',
        }
    )
    def post(self, machine_id):
        """
        Connect to a machine.

        Establishes a connection to the specified machine using its
        configured connection parameters.

        **Connection Types:**
        - Serial: Opens serial port communication
        - Network: Establishes TCP/MQTT connection
        - ROS2: Connects via rosbridge

        **Notes:**
        - Connection may take several seconds
        - Machine will enter 'idle' state on successful connection
        - Check status endpoint for connection result
        """
        from api.routes.scada_api import connect_machine
        return connect_machine(machine_id)


@scada_ns.route('/machines/<string:machine_id>/disconnect')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineDisconnect(Resource):
    """Machine disconnection endpoint."""

    @scada_ns.doc(
        'disconnect_machine',
        responses={
            200: 'Disconnection successful',
            404: 'Machine not connected',
            500: 'Disconnection failed',
        }
    )
    def post(self, machine_id):
        """
        Disconnect from a machine.

        Gracefully closes the connection to the specified machine.

        **Warning:** Disconnecting while a job is running may cause the
        job to fail or leave the machine in an undefined state.
        """
        from api.routes.scada_api import disconnect_machine
        return disconnect_machine(machine_id)


@scada_ns.route('/machines/<string:machine_id>/home')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineHome(Resource):
    """Machine homing endpoint."""

    @scada_ns.doc(
        'home_machine',
        responses={
            200: 'Homing started',
            404: 'Machine not connected',
            500: 'Homing failed',
        }
    )
    @scada_ns.expect(axes_request)
    def post(self, machine_id):
        """
        Home machine axes.

        Initiates the homing sequence for the specified axes.
        The machine will move to its home/reference position.

        **Default Behavior:**
        - All axes (XYZ) are homed by default
        - Specify individual axes to home only those

        **Safety:**
        - Ensure work area is clear before homing
        - Machine will move to physical limits
        - Homing may be noisy

        **Status:**
        Machine status will change to 'homing' during operation
        and return to 'idle' upon completion.
        """
        from api.routes.scada_api import home_machine
        return home_machine(machine_id)


@scada_ns.route('/machines/<string:machine_id>/zero')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineZero(Resource):
    """Machine zero endpoint."""

    @scada_ns.doc(
        'zero_machine',
        responses={
            200: 'Zero successful',
            404: 'Machine not connected',
            500: 'Zero failed',
        }
    )
    @scada_ns.expect(axes_request)
    def post(self, machine_id):
        """
        Zero work coordinates.

        Sets the current position as the work coordinate origin (zero point).
        This does not move the machine - it only changes the coordinate system.

        **Use Cases:**
        - Setting workpiece origin after tool change
        - Establishing reference point for a job
        - Resetting after manual positioning

        **Note:** This affects work coordinates (G54-G59), not machine coordinates.
        """
        from api.routes.scada_api import zero_machine
        return zero_machine(machine_id)


@scada_ns.route('/machines/<string:machine_id>/jog')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineJog(Resource):
    """Machine jogging endpoint."""

    @scada_ns.doc(
        'jog_machine',
        responses={
            200: 'Jog successful',
            400: 'Invalid jog parameters',
            404: 'Machine not connected',
            500: 'Jog failed',
        }
    )
    @scada_ns.expect(jog_request, validate=True)
    def post(self, machine_id):
        """
        Jog machine axis.

        Moves the specified axis by the given distance at the specified feed rate.
        The move is incremental (relative to current position).

        **Parameters:**
        - `axis`: Axis to move (X, Y, Z, A, B, C)
        - `distance`: Distance in mm (positive or negative)
        - `feed_rate`: Speed in mm/min (default: 500)

        **Safety:**
        - Observe soft/hard limits
        - Use slow feed rates for fine positioning
        - Machine must be in 'idle' state
        """
        from api.routes.scada_api import jog_machine
        return jog_machine(machine_id)


@scada_ns.route('/machines/<string:machine_id>/gcode')
@scada_ns.param('machine_id', 'Machine identifier')
class MachineGCode(Resource):
    """Machine G-code endpoint."""

    @scada_ns.doc(
        'send_gcode',
        responses={
            200: 'G-code sent successfully',
            400: 'Invalid G-code',
            404: 'Machine not connected',
            500: 'G-code execution failed',
        }
    )
    @scada_ns.expect(gcode_request, validate=True)
    def post(self, machine_id):
        """
        Send G-code to machine.

        Sends a single G-code command or multiple commands to the machine.
        Commands are executed sequentially.

        **Examples:**
        - Single command: `G28 X Y` (home X and Y)
        - Move: `G1 X100 Y50 F1000`
        - Set temperature: `M104 S200`

        **Notes:**
        - Commands are validated before sending
        - Response includes machine acknowledgment
        - For large programs, use file-based job execution
        """
        from api.routes.scada_api import send_gcode
        return send_gcode(machine_id)


# =============================================================================
# RESOURCES - Alarms
# =============================================================================

@scada_ns.route('/alarms')
class AlarmList(Resource):
    """Alarm listing endpoint."""

    @scada_ns.doc(
        'list_alarms',
        responses={
            200: ('List of alarms', alarm_list_response),
        }
    )
    @scada_ns.marshal_with(alarm_list_response)
    def get(self):
        """
        List all active alarms.

        Returns all currently active alarms across the system,
        sorted by priority and timestamp.

        **Alarm States:**
        - `active_unack`: Active and not acknowledged
        - `active_ack`: Active but acknowledged
        - `cleared_unack`: Cleared but not acknowledged
        - `cleared`: Cleared and acknowledged

        **Priority Levels:**
        - `critical`: Immediate action required
        - `high`: Attention needed soon
        - `medium`: Should be addressed
        - `low`: Informational
        """
        from api.routes.scada_api import list_alarms
        return list_alarms()


@scada_ns.route('/alarms/active')
class ActiveAlarmList(Resource):
    """Active alarms endpoint."""

    @scada_ns.doc(
        'list_active_alarms',
        responses={
            200: ('Active alarms', alarm_list_response),
        }
    )
    @scada_ns.marshal_with(alarm_list_response)
    def get(self):
        """
        List only active alarms.

        Returns alarms that are currently in an active state
        (not yet cleared), regardless of acknowledgment status.
        """
        from api.routes.scada_api import list_active_alarms
        return list_active_alarms()


@scada_ns.route('/alarms/summary')
class AlarmSummary(Resource):
    """Alarm summary endpoint."""

    @scada_ns.doc(
        'alarm_summary',
        responses={
            200: ('Alarm summary', alarm_summary_model),
        }
    )
    @scada_ns.marshal_with(alarm_summary_model)
    def get(self):
        """
        Get alarm summary counts.

        Returns a summary of active alarms grouped by priority level,
        useful for dashboard displays and quick status checks.
        """
        from api.routes.scada_api import alarm_summary
        return alarm_summary()


@scada_ns.route('/alarms/<string:alarm_id>')
@scada_ns.param('alarm_id', 'Alarm identifier')
class AlarmDetail(Resource):
    """Single alarm operations."""

    @scada_ns.doc(
        'get_alarm',
        responses={
            200: ('Alarm details', alarm_model),
            404: 'Alarm not found',
        }
    )
    @scada_ns.marshal_with(alarm_model)
    def get(self, alarm_id):
        """
        Get detailed alarm information.

        Returns complete details about a specific alarm including
        its history, associated tag, and any notes.
        """
        from api.routes.scada_api import get_alarm
        return get_alarm(alarm_id)


@scada_ns.route('/alarms/<string:alarm_id>/acknowledge')
@scada_ns.param('alarm_id', 'Alarm identifier')
class AlarmAcknowledge(Resource):
    """Alarm acknowledgment endpoint."""

    @scada_ns.doc(
        'acknowledge_alarm',
        responses={
            200: 'Alarm acknowledged',
            404: 'Alarm not found',
            500: 'Acknowledgment failed',
        }
    )
    @scada_ns.expect(acknowledge_request)
    def post(self, alarm_id):
        """
        Acknowledge an alarm.

        Marks the alarm as acknowledged by the specified user.
        This indicates awareness of the condition but does not clear it.

        **Note:** Some alarms may auto-clear when the condition resolves.
        Others require manual intervention to clear.
        """
        from api.routes.scada_api import acknowledge_alarm
        return acknowledge_alarm(alarm_id)


@scada_ns.route('/alarms/acknowledge-batch')
class AlarmAcknowledgeBatch(Resource):
    """Batch alarm acknowledgment endpoint."""

    @scada_ns.doc(
        'acknowledge_alarms_batch',
        responses={
            200: 'Alarms acknowledged',
            400: 'No alarm IDs provided',
        }
    )
    @scada_ns.expect(batch_acknowledge_request, validate=True)
    def post(self):
        """
        Acknowledge multiple alarms at once.

        Batch acknowledgment for efficiency when multiple alarms
        need to be acknowledged simultaneously.
        """
        from api.routes.scada_api import acknowledge_alarms_batch
        return acknowledge_alarms_batch()


@scada_ns.route('/alarms/export')
class AlarmExport(Resource):
    """Alarm export endpoint."""

    @scada_ns.doc(
        'export_alarms',
        params={
            'format': {'description': 'Export format', 'enum': ['csv', 'json'], 'default': 'csv'},
        },
        responses={
            200: 'Alarm export file',
        }
    )
    def get(self):
        """
        Export alarms to file.

        Exports current alarms in the specified format.
        Useful for reporting and external analysis.

        **Formats:**
        - `csv`: Comma-separated values
        - `json`: JSON array
        """
        from api.routes.scada_api import export_alarms
        return export_alarms()


# =============================================================================
# RESOURCES - Tags
# =============================================================================

@scada_ns.route('/tags')
class TagList(Resource):
    """Tag listing endpoint."""

    @scada_ns.doc(
        'list_tags',
        responses={
            200: ('List of tags', tag_list_response),
        }
    )
    @scada_ns.marshal_with(tag_list_response)
    def get(self):
        """
        List all tags.

        Returns all configured tags with their current values and metadata.
        Tags represent individual data points from machines and sensors.

        **Tag Structure:**
        Tags follow a hierarchical naming convention:
        `MACHINE_ID.CATEGORY.POINT_NAME`

        Example: `PRINTER_01.TEMP.NOZZLE`
        """
        from api.routes.scada_api import list_tags
        return list_tags()


@scada_ns.route('/tags/<string:tag_id>')
@scada_ns.param('tag_id', 'Tag identifier')
class TagDetail(Resource):
    """Single tag operations."""

    @scada_ns.doc(
        'get_tag',
        responses={
            200: ('Tag details', tag_model),
            404: 'Tag not found',
        }
    )
    @scada_ns.marshal_with(tag_model)
    def get(self, tag_id):
        """
        Get tag details.

        Returns detailed information about a specific tag including
        its current value, quality, and alarm configuration.
        """
        from api.routes.scada_api import get_tag
        return get_tag(tag_id)


# =============================================================================
# RESOURCES - Recipes
# =============================================================================

@scada_ns.route('/recipes')
class RecipeList(Resource):
    """Recipe listing endpoint."""

    @scada_ns.doc(
        'list_recipes',
        responses={
            200: 'List of recipes',
        }
    )
    def get(self):
        """
        List all recipes.

        Returns all master recipes in the system.
        Only the latest approved version of each recipe is returned by default.

        **Recipe Types:**
        Recipes define the parameters and procedures for manufacturing
        specific products on specific machine types.
        """
        from api.routes.scada_api import list_recipes
        return list_recipes()


@scada_ns.route('/recipes/<string:recipe_id>')
@scada_ns.param('recipe_id', 'Recipe identifier')
class RecipeDetail(Resource):
    """Single recipe operations."""

    @scada_ns.doc(
        'get_recipe',
        responses={
            200: ('Recipe details', recipe_model),
            404: 'Recipe not found',
        }
    )
    @scada_ns.marshal_with(recipe_model)
    def get(self, recipe_id):
        """
        Get recipe details.

        Returns the complete recipe including all parameters,
        associated G-code, and version history.
        """
        from api.routes.scada_api import get_recipe
        return get_recipe(recipe_id)


# =============================================================================
# RESOURCES - Serial Ports
# =============================================================================

@scada_ns.route('/serial-ports')
class SerialPortList(Resource):
    """Serial port listing endpoint."""

    @scada_ns.doc(
        'list_serial_ports',
        responses={
            200: 'List of serial ports',
        }
    )
    def get(self):
        """
        List available serial ports.

        Scans the system for available serial ports that can be
        used for machine connections.

        **Common Ports:**
        - `/dev/ttyUSB0` - USB serial adapters
        - `/dev/ttyACM0` - Arduino/CDC devices
        - `COM3` - Windows serial ports
        """
        from api.routes.scada_api import list_serial_ports
        return list_serial_ports()


# =============================================================================
# RESOURCES - Printers
# =============================================================================

@scada_ns.route('/printers')
class PrinterList(Resource):
    """3D printer listing endpoint."""

    @scada_ns.doc(
        'list_printers',
        responses={
            200: 'List of printers',
        }
    )
    def get(self):
        """
        List all 3D printers.

        Returns all configured 3D printers with their current status.
        This includes FDM printers (Prusa, Bambu, etc.) and SLA printers.
        """
        from api.routes.scada_api import list_printers
        return list_printers()


@scada_ns.route('/printers/<string:printer_id>/status')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterStatusResource(Resource):
    """Printer status endpoint."""

    @scada_ns.doc(
        'get_printer_status',
        responses={
            200: ('Printer status', printer_status_model),
        }
    )
    @scada_ns.marshal_with(printer_status_model)
    def get(self, printer_id):
        """
        Get detailed printer status.

        Returns real-time printer status including temperatures,
        print progress, and current file information.
        """
        from api.routes.scada_api import get_printer_status
        return get_printer_status(printer_id)


@scada_ns.route('/printers/<string:printer_id>/connect')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterConnect(Resource):
    """Printer connection endpoint."""

    @scada_ns.doc(
        'connect_printer',
        responses={
            200: 'Connection successful',
            404: 'Printer not found',
            500: 'Connection failed',
        }
    )
    def post(self, printer_id):
        """
        Connect to a printer.

        For network printers (Bambu), may require IP, serial number,
        and access code in the request body.
        """
        from api.routes.scada_api import connect_printer
        return connect_printer(printer_id)


@scada_ns.route('/printers/<string:printer_id>/print/start')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterStart(Resource):
    """Print job start endpoint."""

    @scada_ns.doc(
        'start_print',
        responses={
            200: 'Print started',
            400: 'Invalid request',
            404: 'Printer not connected',
            500: 'Start failed',
        }
    )
    @scada_ns.expect(print_start_request, validate=True)
    def post(self, printer_id):
        """
        Start a print job.

        Begins printing the specified file on the printer.
        The file must already be present on the printer's storage.
        """
        from api.routes.scada_api import start_printer_job
        return start_printer_job(printer_id)


@scada_ns.route('/printers/<string:printer_id>/print/pause')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterPause(Resource):
    """Print job pause endpoint."""

    @scada_ns.doc(
        'pause_print',
        responses={
            200: 'Print paused',
            404: 'Printer not connected',
            500: 'Pause failed',
        }
    )
    def post(self, printer_id):
        """Pause current print job."""
        from api.routes.scada_api import pause_printer_job
        return pause_printer_job(printer_id)


@scada_ns.route('/printers/<string:printer_id>/print/resume')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterResume(Resource):
    """Print job resume endpoint."""

    @scada_ns.doc(
        'resume_print',
        responses={
            200: 'Print resumed',
            404: 'Printer not connected',
            500: 'Resume failed',
        }
    )
    def post(self, printer_id):
        """Resume paused print job."""
        from api.routes.scada_api import resume_printer_job
        return resume_printer_job(printer_id)


@scada_ns.route('/printers/<string:printer_id>/print/stop')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterStop(Resource):
    """Print job stop endpoint."""

    @scada_ns.doc(
        'stop_print',
        responses={
            200: 'Print stopped',
            404: 'Printer not connected',
            500: 'Stop failed',
        }
    )
    def post(self, printer_id):
        """
        Stop/cancel current print job.

        **Warning:** This will cancel the print and it cannot be resumed.
        The print will need to be restarted from the beginning.
        """
        from api.routes.scada_api import stop_printer_job
        return stop_printer_job(printer_id)


@scada_ns.route('/printers/<string:printer_id>/temperature')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterTemperature(Resource):
    """Printer temperature control endpoint."""

    @scada_ns.doc(
        'set_temperature',
        responses={
            200: 'Temperature set',
            404: 'Printer not connected',
            500: 'Temperature set failed',
        }
    )
    @scada_ns.expect(temperature_request)
    def post(self, printer_id):
        """
        Set printer temperatures.

        Manually set nozzle and/or bed temperatures.
        For automatic preheating, use the `/preheat` endpoint.
        """
        from api.routes.scada_api import set_printer_temperature
        return set_printer_temperature(printer_id)


@scada_ns.route('/printers/<string:printer_id>/preheat')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterPreheat(Resource):
    """Printer preheat endpoint."""

    @scada_ns.doc(
        'preheat_printer',
        responses={
            200: 'Preheating started',
            400: 'Unknown material',
            404: 'Printer not connected',
            500: 'Preheat failed',
        }
    )
    @scada_ns.expect(preheat_request, validate=True)
    def post(self, printer_id):
        """
        Preheat printer for specific material.

        Sets appropriate temperatures for the specified material type:
        - **PLA**: Nozzle 200-215C, Bed 50-60C
        - **PETG**: Nozzle 230-250C, Bed 70-80C
        - **ABS**: Nozzle 240-260C, Bed 90-110C
        - **TPU**: Nozzle 220-250C, Bed 50-60C
        """
        from api.routes.scada_api import preheat_printer
        return preheat_printer(printer_id)


@scada_ns.route('/printers/<string:printer_id>/cooldown')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterCooldown(Resource):
    """Printer cooldown endpoint."""

    @scada_ns.doc(
        'cooldown_printer',
        responses={
            200: 'Cooling down',
            404: 'Printer not connected',
            500: 'Cooldown failed',
        }
    )
    def post(self, printer_id):
        """
        Cool down printer heaters.

        Sets all heaters to 0C to begin cooling down.
        """
        from api.routes.scada_api import cooldown_printer
        return cooldown_printer(printer_id)


@scada_ns.route('/printers/<string:printer_id>/light')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterLight(Resource):
    """Printer light control endpoint."""

    @scada_ns.doc(
        'control_light',
        responses={
            200: 'Light controlled',
            400: 'Unknown light',
            404: 'Printer not connected',
            500: 'Light control failed',
        }
    )
    @scada_ns.expect(light_control_request)
    def post(self, printer_id):
        """Control printer lights (chamber or work light)."""
        from api.routes.scada_api import control_printer_light
        return control_printer_light(printer_id)


@scada_ns.route('/printers/<string:printer_id>/speed')
@scada_ns.param('printer_id', 'Printer identifier')
class PrinterSpeed(Resource):
    """Printer speed profile endpoint."""

    @scada_ns.doc(
        'set_speed_profile',
        responses={
            200: 'Speed profile set',
            404: 'Printer not connected',
            500: 'Speed set failed',
        }
    )
    @scada_ns.expect(speed_request)
    def post(self, printer_id):
        """
        Set printer speed profile.

        Adjusts print speed according to predefined profiles:
        - **silent**: Reduced speed, quieter operation
        - **standard**: Normal speed
        - **sport**: Increased speed
        - **ludicrous**: Maximum speed
        """
        from api.routes.scada_api import set_printer_speed
        return set_printer_speed(printer_id)


# =============================================================================
# RESOURCES - Health
# =============================================================================

@scada_ns.route('/health')
class HealthCheck(Resource):
    """SCADA health check endpoint."""

    @scada_ns.doc(
        'health_check',
        responses={
            200: 'SCADA system healthy',
        }
    )
    def get(self):
        """
        SCADA system health check.

        Returns overall health status of the SCADA subsystem including
        machine connectivity and service availability.
        """
        from api.routes.scada_api import health_check
        return health_check()
