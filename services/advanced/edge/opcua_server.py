"""
OPC UA Server - Production OPC UA Server per OPC 40501 CNC Systems
LEGO MCP Manufacturing System v7.0

Exposes manufacturing equipment status via OPC UA per industrial standards:
- OPC 40501 (CNC Systems) companion specification
- Equipment state machine per ISA-88 / PackML
- Real-time data from Bambu Lab, GRBL CNC, robots via ROS2 bridge

Requirements:
    pip install asyncua>=1.0.0

Standards Compliance:
    - OPC 40501-1: CNC Systems - Part 1: General definitions
    - OPC 40501-2: CNC Systems - Part 2: CNC specific semantics
    - ISA-88 State Machine for equipment states
    - OPC UA Part 8: Data Access for real-time values
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

logger = logging.getLogger(__name__)

# =============================================================================
# OPC 40501 / ISA-88 STATE MACHINE
# =============================================================================

class CNCMachineState(IntEnum):
    """
    CNC Machine State per OPC 40501 / ISA-88 State Machine.

    Maps to PackML states for manufacturing equipment.
    """
    # Stopped states
    STOPPED = 0
    IDLE = 1

    # Running states
    STARTING = 2
    EXECUTE = 3
    COMPLETING = 4
    COMPLETE = 5

    # Held states (operator hold)
    HOLDING = 6
    HELD = 7
    UNHOLDING = 8

    # Suspended states (external cause)
    SUSPENDING = 9
    SUSPENDED = 10
    UNSUSPENDING = 11

    # Abort/Stop transitions
    ABORTING = 12
    ABORTED = 13
    CLEARING = 14
    STOPPING = 15

    # Resetting
    RESETTING = 16


class CNCOperationMode(IntEnum):
    """CNC Operation Mode per OPC 40501."""
    AUTOMATIC = 0
    SEMI_AUTOMATIC = 1
    MANUAL = 2
    MANUAL_DATA_INPUT = 3
    JOG = 4
    TEACH = 5
    SIMULATION = 6


class CNCAlarmSeverity(IntEnum):
    """Alarm severity per OPC UA Part 9."""
    INFORMATIONAL = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class CNCAlarm:
    """CNC Alarm per OPC 40501."""
    alarm_id: str
    condition_name: str
    severity: CNCAlarmSeverity
    message: str
    source_name: str
    active: bool = True
    acknowledged: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alarm_id': self.alarm_id,
            'condition_name': self.condition_name,
            'severity': self.severity.name,
            'message': self.message,
            'source_name': self.source_name,
            'active': self.active,
            'acknowledged': self.acknowledged,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class CNCChannelStatus:
    """
    CNC Channel Status per OPC 40501-2.

    Represents a CNC channel (axis group) status.
    """
    channel_id: int
    name: str
    state: CNCMachineState = CNCMachineState.IDLE
    mode: CNCOperationMode = CNCOperationMode.AUTOMATIC

    # Program execution
    program_name: str = ""
    program_block: int = 0
    program_line: int = 0
    program_progress_percent: float = 0.0

    # Feed and speed
    feed_rate_actual: float = 0.0
    feed_rate_override_percent: float = 100.0
    spindle_speed_actual: float = 0.0
    spindle_speed_override_percent: float = 100.0
    rapid_override_percent: float = 100.0

    # Axes (axis name -> position)
    axis_positions: Dict[str, float] = field(default_factory=dict)
    axis_targets: Dict[str, float] = field(default_factory=dict)

    # Errors
    has_error: bool = False
    error_code: int = 0
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'channel_id': self.channel_id,
            'name': self.name,
            'state': self.state.name,
            'mode': self.mode.name,
            'program_name': self.program_name,
            'program_block': self.program_block,
            'program_line': self.program_line,
            'program_progress_percent': self.program_progress_percent,
            'feed_rate_actual': self.feed_rate_actual,
            'feed_rate_override_percent': self.feed_rate_override_percent,
            'spindle_speed_actual': self.spindle_speed_actual,
            'spindle_speed_override_percent': self.spindle_speed_override_percent,
            'axis_positions': self.axis_positions,
            'axis_targets': self.axis_targets,
            'has_error': self.has_error,
            'error_code': self.error_code,
        }


@dataclass
class CNCSpindleStatus:
    """Spindle status per OPC 40501-2."""
    spindle_id: int
    name: str
    is_turning: bool = False
    actual_speed_rpm: float = 0.0
    commanded_speed_rpm: float = 0.0
    override_percent: float = 100.0
    direction: int = 0  # 0=stopped, 1=CW, -1=CCW
    load_percent: float = 0.0
    temperature_c: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'spindle_id': self.spindle_id,
            'name': self.name,
            'is_turning': self.is_turning,
            'actual_speed_rpm': self.actual_speed_rpm,
            'commanded_speed_rpm': self.commanded_speed_rpm,
            'override_percent': self.override_percent,
            'direction': self.direction,
            'load_percent': self.load_percent,
            'temperature_c': self.temperature_c,
        }


@dataclass
class CNCToolStatus:
    """Tool status per OPC 40501-2."""
    tool_id: int
    name: str
    in_spindle: bool = False
    tool_life_remaining_percent: float = 100.0
    tool_life_count: int = 0
    tool_length_offset: float = 0.0
    tool_radius_offset: float = 0.0
    tool_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tool_id': self.tool_id,
            'name': self.name,
            'in_spindle': self.in_spindle,
            'tool_life_remaining_percent': self.tool_life_remaining_percent,
            'tool_life_count': self.tool_life_count,
            'tool_length_offset': self.tool_length_offset,
            'tool_radius_offset': self.tool_radius_offset,
            'tool_type': self.tool_type,
        }


# =============================================================================
# OPC UA EQUIPMENT NODE TYPES
# =============================================================================

@dataclass
class OPCUAEquipmentNode:
    """
    OPC UA Equipment Node representing a manufacturing device.

    Per OPC 40501, each CNC system exposes standardized information model.
    """
    node_id: str
    equipment_id: str
    equipment_type: str  # CNC, 3DPrinter, Robot, Laser
    display_name: str
    description: str = ""

    # Manufacturer info (OPC UA Device Information Model)
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    hardware_revision: str = ""
    software_revision: str = ""

    # State (ISA-88 / PackML)
    state: CNCMachineState = CNCMachineState.IDLE
    mode: CNCOperationMode = CNCOperationMode.AUTOMATIC

    # Connection
    connected: bool = False
    last_communication: Optional[datetime] = None

    # CNC-specific
    channels: List[CNCChannelStatus] = field(default_factory=list)
    spindles: List[CNCSpindleStatus] = field(default_factory=list)
    tools: List[CNCToolStatus] = field(default_factory=list)
    alarms: List[CNCAlarm] = field(default_factory=list)

    # Custom properties (equipment-specific)
    properties: Dict[str, Any] = field(default_factory=dict)

    # ROS2 topic mappings
    ros2_topics: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_id': self.node_id,
            'equipment_id': self.equipment_id,
            'equipment_type': self.equipment_type,
            'display_name': self.display_name,
            'description': self.description,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'state': self.state.name,
            'mode': self.mode.name,
            'connected': self.connected,
            'last_communication': self.last_communication.isoformat() if self.last_communication else None,
            'channels': [c.to_dict() for c in self.channels],
            'spindles': [s.to_dict() for s in self.spindles],
            'tools': [t.to_dict() for t in self.tools],
            'active_alarms': [a.to_dict() for a in self.alarms if a.active],
            'properties': self.properties,
        }


# =============================================================================
# ROS2 BRIDGE INTERFACE
# =============================================================================

class ROS2EquipmentBridge(ABC):
    """Abstract base for ROS2 equipment bridges."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to ROS2 topics."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from ROS2 topics."""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get current equipment status."""
        pass

    @abstractmethod
    def get_ros2_topics(self) -> List[str]:
        """Get list of ROS2 topics to subscribe."""
        pass


class GRBLBridge(ROS2EquipmentBridge):
    """
    GRBL CNC Bridge via ROS2.

    Subscribes to /grbl/status and /grbl/position topics.
    """

    def __init__(self, equipment_id: str, ros2_bridge: Optional[Any] = None):
        self.equipment_id = equipment_id
        self.ros2_bridge = ros2_bridge
        self._connected = False
        self._last_status: Dict[str, Any] = {}

    async def connect(self) -> bool:
        """Connect to GRBL ROS2 topics."""
        if self.ros2_bridge:
            try:
                # Subscribe to GRBL status
                self.ros2_bridge.subscribe(
                    f'/grbl/{self.equipment_id}/status',
                    'lego_mcp_msgs/msg/GRBLStatus',
                    self._on_status
                )
                self.ros2_bridge.subscribe(
                    f'/grbl/{self.equipment_id}/position',
                    'geometry_msgs/msg/Point',
                    self._on_position
                )
                self._connected = True
                return True
            except Exception as e:
                logger.error(f"Failed to connect GRBL bridge: {e}")
                return False
        return False

    async def disconnect(self) -> None:
        """Disconnect from GRBL ROS2 topics."""
        if self.ros2_bridge:
            self.ros2_bridge.unsubscribe(f'/grbl/{self.equipment_id}/status')
            self.ros2_bridge.unsubscribe(f'/grbl/{self.equipment_id}/position')
        self._connected = False

    def _on_status(self, msg: Dict[str, Any]) -> None:
        """Handle GRBL status message."""
        self._last_status.update(msg)

    def _on_position(self, msg: Dict[str, Any]) -> None:
        """Handle position message."""
        self._last_status['position'] = msg

    async def get_status(self) -> Dict[str, Any]:
        """Get current GRBL status."""
        return self._last_status.copy()

    def get_ros2_topics(self) -> List[str]:
        return [
            f'/grbl/{self.equipment_id}/status',
            f'/grbl/{self.equipment_id}/position',
            f'/grbl/{self.equipment_id}/alarms',
        ]


class BambuLabBridge(ROS2EquipmentBridge):
    """
    Bambu Lab 3D Printer Bridge via ROS2.

    Bridges Bambu Lab printer data to OPC UA.
    """

    def __init__(self, equipment_id: str, ros2_bridge: Optional[Any] = None):
        self.equipment_id = equipment_id
        self.ros2_bridge = ros2_bridge
        self._connected = False
        self._last_status: Dict[str, Any] = {}

    async def connect(self) -> bool:
        """Connect to Bambu Lab ROS2 topics."""
        if self.ros2_bridge:
            try:
                self.ros2_bridge.subscribe(
                    f'/bambu/{self.equipment_id}/status',
                    'lego_mcp_msgs/msg/BambuStatus',
                    self._on_status
                )
                self.ros2_bridge.subscribe(
                    f'/bambu/{self.equipment_id}/print_progress',
                    'lego_mcp_msgs/msg/PrintProgress',
                    self._on_progress
                )
                self._connected = True
                return True
            except Exception as e:
                logger.error(f"Failed to connect Bambu bridge: {e}")
                return False
        return False

    async def disconnect(self) -> None:
        if self.ros2_bridge:
            self.ros2_bridge.unsubscribe(f'/bambu/{self.equipment_id}/status')
            self.ros2_bridge.unsubscribe(f'/bambu/{self.equipment_id}/print_progress')
        self._connected = False

    def _on_status(self, msg: Dict[str, Any]) -> None:
        self._last_status.update(msg)

    def _on_progress(self, msg: Dict[str, Any]) -> None:
        self._last_status['print_progress'] = msg

    async def get_status(self) -> Dict[str, Any]:
        return self._last_status.copy()

    def get_ros2_topics(self) -> List[str]:
        return [
            f'/bambu/{self.equipment_id}/status',
            f'/bambu/{self.equipment_id}/print_progress',
            f'/bambu/{self.equipment_id}/temperatures',
        ]


class RobotBridge(ROS2EquipmentBridge):
    """
    Robot Bridge (Niryo Ned2 / xArm) via ROS2.

    Bridges robot status to OPC UA.
    """

    def __init__(
        self,
        equipment_id: str,
        robot_type: str = 'ned2',
        ros2_bridge: Optional[Any] = None
    ):
        self.equipment_id = equipment_id
        self.robot_type = robot_type
        self.ros2_bridge = ros2_bridge
        self._connected = False
        self._last_status: Dict[str, Any] = {}

    async def connect(self) -> bool:
        if self.ros2_bridge:
            try:
                self.ros2_bridge.subscribe(
                    f'/{self.robot_type}/robot_state',
                    'lego_mcp_msgs/msg/RobotState',
                    self._on_status
                )
                self.ros2_bridge.subscribe(
                    f'/{self.robot_type}/joint_states',
                    'sensor_msgs/msg/JointState',
                    self._on_joints
                )
                self._connected = True
                return True
            except Exception as e:
                logger.error(f"Failed to connect robot bridge: {e}")
                return False
        return False

    async def disconnect(self) -> None:
        if self.ros2_bridge:
            self.ros2_bridge.unsubscribe(f'/{self.robot_type}/robot_state')
            self.ros2_bridge.unsubscribe(f'/{self.robot_type}/joint_states')
        self._connected = False

    def _on_status(self, msg: Dict[str, Any]) -> None:
        self._last_status.update(msg)

    def _on_joints(self, msg: Dict[str, Any]) -> None:
        self._last_status['joint_states'] = msg

    async def get_status(self) -> Dict[str, Any]:
        return self._last_status.copy()

    def get_ros2_topics(self) -> List[str]:
        return [
            f'/{self.robot_type}/robot_state',
            f'/{self.robot_type}/joint_states',
            f'/{self.robot_type}/end_effector',
        ]


# =============================================================================
# OPC UA SERVER
# =============================================================================

class OPCUAServer:
    """
    Production OPC UA Server per OPC 40501 CNC Systems.

    Exposes manufacturing equipment status via OPC UA with full
    compliance to industrial standards.

    Features:
        - OPC 40501 CNC companion specification
        - ISA-88 / PackML state machine
        - Real-time equipment data via ROS2 bridge
        - Alarm & Events per OPC UA Part 9
        - Historical data access
        - Security per OPC UA Part 2

    Equipment Supported:
        - GRBL-based CNC machines
        - Bambu Lab 3D printers
        - Niryo Ned2 / xArm robots
        - Laser cutters/engravers
    """

    # Namespace URIs per OPC 40501
    NAMESPACE_URI = "urn:legomcp:opcua:cnc"
    OPC_40501_NAMESPACE = "http://opcfoundation.org/UA/CNC/"

    def __init__(
        self,
        endpoint: str = "opc.tcp://0.0.0.0:4840/legomcp/server/",
        server_name: str = "LEGO MCP OPC UA Server",
        ros2_bridge: Optional[Any] = None,
        enable_security: bool = True,
        enable_history: bool = True,
    ):
        """
        Initialize OPC UA Server.

        Args:
            endpoint: OPC UA endpoint URL
            server_name: Server display name
            ros2_bridge: ROS2 bridge instance for equipment data
            enable_security: Enable OPC UA security
            enable_history: Enable historical data access
        """
        self.endpoint = endpoint
        self.server_name = server_name
        self.ros2_bridge = ros2_bridge
        self.enable_security = enable_security
        self.enable_history = enable_history

        # Server state
        self._server = None
        self._running = False
        self._namespace_idx: int = 0

        # Equipment registry
        self._equipment: Dict[str, OPCUAEquipmentNode] = {}
        self._bridges: Dict[str, ROS2EquipmentBridge] = {}

        # Node caches
        self._equipment_nodes: Dict[str, Any] = {}  # OPC UA node objects

        # Callbacks
        self._on_write_callbacks: Dict[str, Callable] = {}
        self._on_method_callbacks: Dict[str, Callable] = {}

        # Update task
        self._update_task: Optional[asyncio.Task] = None
        self._update_interval: float = 0.1  # 100ms default

        # Historical data buffer (in-memory, production would use TimescaleDB)
        self._history: Dict[str, List[Tuple[datetime, Any]]] = {}
        self._history_limit = 10000

        logger.info(f"OPC UA Server initialized: {endpoint}")

    async def start(self) -> bool:
        """
        Start the OPC UA server.

        Returns:
            True if started successfully
        """
        try:
            from asyncua import Server, ua
            from asyncua.common.methods import uamethod
        except ImportError:
            logger.error(
                "asyncua not installed. Install with: pip install asyncua"
            )
            # Run in simulation mode
            return await self._start_simulation_mode()

        try:
            self._server = Server()
            await self._server.init()

            # Configure server
            self._server.set_endpoint(self.endpoint)
            self._server.set_server_name(self.server_name)

            # Register namespace
            self._namespace_idx = await self._server.register_namespace(
                self.NAMESPACE_URI
            )

            # Setup security if enabled
            if self.enable_security:
                await self._setup_security()

            # Create OPC 40501 information model
            await self._create_information_model()

            # Create equipment nodes
            await self._create_equipment_nodes()

            # Start server
            await self._server.start()
            self._running = True

            # Start update loop
            self._update_task = asyncio.create_task(self._update_loop())

            logger.info(f"OPC UA Server started: {self.endpoint}")
            return True

        except Exception as e:
            logger.error(f"Failed to start OPC UA server: {e}")
            return await self._start_simulation_mode()

    async def _start_simulation_mode(self) -> bool:
        """Start in simulation mode without asyncua."""
        logger.warning("Starting OPC UA server in simulation mode")
        self._running = True
        self._update_task = asyncio.create_task(self._simulation_update_loop())
        return True

    async def stop(self) -> None:
        """Stop the OPC UA server."""
        self._running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Disconnect bridges
        for bridge in self._bridges.values():
            await bridge.disconnect()

        if self._server:
            await self._server.stop()

        logger.info("OPC UA Server stopped")

    async def _setup_security(self) -> None:
        """Configure OPC UA security per Part 2."""
        try:
            from asyncua.crypto import security_policies
            from asyncua import ua

            # Configure security policies
            # In production, load certificates from secure storage
            self._server.set_security_policy([
                ua.SecurityPolicyType.NoSecurity,
                ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
            ])

            logger.info("OPC UA security configured")
        except Exception as e:
            logger.warning(f"Security setup failed: {e}")

    async def _create_information_model(self) -> None:
        """
        Create OPC 40501 information model.

        Creates the standard CNC information model structure:
        - Objects/CNCInterface
        - Objects/CNCInterface/CNCChannelList
        - Objects/CNCInterface/CNCSpindleList
        - Objects/CNCInterface/CNCAxisList
        """
        if not self._server:
            return

        try:
            from asyncua import ua

            objects = self._server.nodes.objects

            # Create CNC Interface folder per OPC 40501
            cnc_folder = await objects.add_folder(
                self._namespace_idx,
                "CNCInterface"
            )

            # Create standard sub-folders
            await cnc_folder.add_folder(self._namespace_idx, "CNCChannelList")
            await cnc_folder.add_folder(self._namespace_idx, "CNCSpindleList")
            await cnc_folder.add_folder(self._namespace_idx, "CNCAxisList")
            await cnc_folder.add_folder(self._namespace_idx, "CNCToolList")
            await cnc_folder.add_folder(self._namespace_idx, "CNCAlarmList")

            # Create Equipment folder (LegoMCP extension)
            equipment_folder = await objects.add_folder(
                self._namespace_idx,
                "Equipment"
            )

            await equipment_folder.add_folder(self._namespace_idx, "CNCMachines")
            await equipment_folder.add_folder(self._namespace_idx, "3DPrinters")
            await equipment_folder.add_folder(self._namespace_idx, "Robots")
            await equipment_folder.add_folder(self._namespace_idx, "LaserCutters")

            logger.info("OPC 40501 information model created")

        except Exception as e:
            logger.error(f"Failed to create information model: {e}")

    async def _create_equipment_nodes(self) -> None:
        """Create OPC UA nodes for registered equipment."""
        for equipment_id, equipment in self._equipment.items():
            await self._create_equipment_node(equipment)

    async def _create_equipment_node(
        self,
        equipment: OPCUAEquipmentNode
    ) -> None:
        """
        Create OPC UA node structure for equipment.

        Per OPC 40501, creates:
        - Equipment object node
        - DeviceInfo variables
        - State variables
        - Channel/Spindle/Tool nodes
        """
        if not self._server:
            # Simulation mode - just store the equipment
            self._equipment_nodes[equipment.equipment_id] = equipment
            return

        try:
            from asyncua import ua

            objects = self._server.nodes.objects

            # Find parent folder based on equipment type
            folder_map = {
                'CNC': 'CNCMachines',
                '3DPrinter': '3DPrinters',
                'Robot': 'Robots',
                'Laser': 'LaserCutters',
            }
            folder_name = folder_map.get(equipment.equipment_type, 'Equipment')

            # Navigate to folder
            equipment_folder = await objects.get_child([
                f"{self._namespace_idx}:Equipment",
                f"{self._namespace_idx}:{folder_name}"
            ])

            # Create equipment object
            eq_obj = await equipment_folder.add_object(
                self._namespace_idx,
                equipment.display_name
            )

            # Add Device Information variables
            await eq_obj.add_variable(
                self._namespace_idx, "Manufacturer", equipment.manufacturer
            )
            await eq_obj.add_variable(
                self._namespace_idx, "Model", equipment.model
            )
            await eq_obj.add_variable(
                self._namespace_idx, "SerialNumber", equipment.serial_number
            )
            await eq_obj.add_variable(
                self._namespace_idx, "HardwareRevision", equipment.hardware_revision
            )
            await eq_obj.add_variable(
                self._namespace_idx, "SoftwareRevision", equipment.software_revision
            )

            # Add State variables
            state_var = await eq_obj.add_variable(
                self._namespace_idx,
                "State",
                equipment.state.value,
                varianttype=ua.VariantType.Int32
            )
            await state_var.set_writable()

            mode_var = await eq_obj.add_variable(
                self._namespace_idx,
                "OperationMode",
                equipment.mode.value,
                varianttype=ua.VariantType.Int32
            )
            await mode_var.set_writable()

            # Add Connected status
            connected_var = await eq_obj.add_variable(
                self._namespace_idx, "Connected", equipment.connected
            )

            # Add channel nodes for CNC equipment
            if equipment.equipment_type == 'CNC' and equipment.channels:
                channels_obj = await eq_obj.add_object(
                    self._namespace_idx, "Channels"
                )
                for channel in equipment.channels:
                    await self._create_channel_node(channels_obj, channel)

            # Store reference
            self._equipment_nodes[equipment.equipment_id] = eq_obj

            logger.info(f"Created OPC UA node for: {equipment.display_name}")

        except Exception as e:
            logger.error(f"Failed to create equipment node: {e}")

    async def _create_channel_node(
        self,
        parent: Any,
        channel: CNCChannelStatus
    ) -> None:
        """Create OPC UA node for CNC channel."""
        if not self._server:
            return

        try:
            from asyncua import ua

            ch_obj = await parent.add_object(
                self._namespace_idx,
                f"Channel_{channel.channel_id}"
            )

            # Add channel variables per OPC 40501
            await ch_obj.add_variable(
                self._namespace_idx, "State", channel.state.value,
                varianttype=ua.VariantType.Int32
            )
            await ch_obj.add_variable(
                self._namespace_idx, "Mode", channel.mode.value,
                varianttype=ua.VariantType.Int32
            )
            await ch_obj.add_variable(
                self._namespace_idx, "ProgramName", channel.program_name
            )
            await ch_obj.add_variable(
                self._namespace_idx, "ProgramBlock", channel.program_block,
                varianttype=ua.VariantType.Int32
            )
            await ch_obj.add_variable(
                self._namespace_idx, "ProgramLine", channel.program_line,
                varianttype=ua.VariantType.Int32
            )
            await ch_obj.add_variable(
                self._namespace_idx, "ProgramProgress", channel.program_progress_percent,
                varianttype=ua.VariantType.Double
            )
            await ch_obj.add_variable(
                self._namespace_idx, "FeedRateActual", channel.feed_rate_actual,
                varianttype=ua.VariantType.Double
            )
            await ch_obj.add_variable(
                self._namespace_idx, "FeedRateOverride", channel.feed_rate_override_percent,
                varianttype=ua.VariantType.Double
            )
            await ch_obj.add_variable(
                self._namespace_idx, "SpindleSpeedActual", channel.spindle_speed_actual,
                varianttype=ua.VariantType.Double
            )
            await ch_obj.add_variable(
                self._namespace_idx, "SpindleSpeedOverride", channel.spindle_speed_override_percent,
                varianttype=ua.VariantType.Double
            )
            await ch_obj.add_variable(
                self._namespace_idx, "HasError", channel.has_error,
                varianttype=ua.VariantType.Boolean
            )
            await ch_obj.add_variable(
                self._namespace_idx, "ErrorCode", channel.error_code,
                varianttype=ua.VariantType.Int32
            )

            # Add axis positions
            axes_obj = await ch_obj.add_object(
                self._namespace_idx, "AxisPositions"
            )
            for axis_name, position in channel.axis_positions.items():
                await axes_obj.add_variable(
                    self._namespace_idx, axis_name, position,
                    varianttype=ua.VariantType.Double
                )

        except Exception as e:
            logger.error(f"Failed to create channel node: {e}")

    # =========================================================================
    # EQUIPMENT REGISTRATION
    # =========================================================================

    def register_equipment(
        self,
        equipment_id: str,
        equipment_type: str,
        display_name: str,
        manufacturer: str = "",
        model: str = "",
        serial_number: str = "",
        ros2_topics: Optional[Dict[str, str]] = None,
    ) -> OPCUAEquipmentNode:
        """
        Register manufacturing equipment with the OPC UA server.

        Args:
            equipment_id: Unique equipment identifier
            equipment_type: Type (CNC, 3DPrinter, Robot, Laser)
            display_name: Human-readable name
            manufacturer: Equipment manufacturer
            model: Equipment model
            serial_number: Serial number
            ros2_topics: ROS2 topic mappings

        Returns:
            OPCUAEquipmentNode representing the equipment
        """
        equipment = OPCUAEquipmentNode(
            node_id=f"ns={self._namespace_idx};s=Equipment/{equipment_type}/{equipment_id}",
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            display_name=display_name,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            ros2_topics=ros2_topics or {},
        )

        # Create default channel for CNC
        if equipment_type == 'CNC':
            equipment.channels = [
                CNCChannelStatus(
                    channel_id=1,
                    name="Main",
                    axis_positions={'X': 0.0, 'Y': 0.0, 'Z': 0.0},
                    axis_targets={'X': 0.0, 'Y': 0.0, 'Z': 0.0},
                )
            ]
            equipment.spindles = [
                CNCSpindleStatus(spindle_id=1, name="Main Spindle")
            ]

        self._equipment[equipment_id] = equipment

        # Create bridge based on type
        if self.ros2_bridge:
            if equipment_type == 'CNC':
                self._bridges[equipment_id] = GRBLBridge(
                    equipment_id, self.ros2_bridge
                )
            elif equipment_type == '3DPrinter':
                self._bridges[equipment_id] = BambuLabBridge(
                    equipment_id, self.ros2_bridge
                )
            elif equipment_type == 'Robot':
                self._bridges[equipment_id] = RobotBridge(
                    equipment_id, ros2_bridge=self.ros2_bridge
                )

        logger.info(f"Registered equipment: {display_name} ({equipment_type})")

        # Create OPC UA node if server running
        if self._running:
            asyncio.create_task(self._create_equipment_node(equipment))

        return equipment

    def unregister_equipment(self, equipment_id: str) -> bool:
        """Unregister equipment from the server."""
        if equipment_id in self._equipment:
            del self._equipment[equipment_id]
            if equipment_id in self._bridges:
                asyncio.create_task(self._bridges[equipment_id].disconnect())
                del self._bridges[equipment_id]
            if equipment_id in self._equipment_nodes:
                del self._equipment_nodes[equipment_id]
            logger.info(f"Unregistered equipment: {equipment_id}")
            return True
        return False

    def get_equipment(self, equipment_id: str) -> Optional[OPCUAEquipmentNode]:
        """Get equipment by ID."""
        return self._equipment.get(equipment_id)

    def get_all_equipment(self) -> List[OPCUAEquipmentNode]:
        """Get all registered equipment."""
        return list(self._equipment.values())

    # =========================================================================
    # DATA UPDATE
    # =========================================================================

    async def _update_loop(self) -> None:
        """Main update loop for refreshing equipment data."""
        while self._running:
            try:
                await self._update_equipment_data()
            except Exception as e:
                logger.error(f"Update loop error: {e}")

            await asyncio.sleep(self._update_interval)

    async def _simulation_update_loop(self) -> None:
        """Simulation update loop without real OPC UA."""
        while self._running:
            try:
                await self._simulate_equipment_updates()
            except Exception as e:
                logger.error(f"Simulation update error: {e}")

            await asyncio.sleep(self._update_interval)

    async def _update_equipment_data(self) -> None:
        """Update equipment data from ROS2 bridges."""
        for equipment_id, equipment in self._equipment.items():
            bridge = self._bridges.get(equipment_id)
            if bridge:
                try:
                    status = await bridge.get_status()
                    await self._apply_status_update(equipment, status)
                except Exception as e:
                    logger.error(f"Failed to update {equipment_id}: {e}")

    async def _apply_status_update(
        self,
        equipment: OPCUAEquipmentNode,
        status: Dict[str, Any]
    ) -> None:
        """Apply status update to equipment and OPC UA nodes."""
        equipment.last_communication = datetime.now(timezone.utc)
        equipment.connected = True

        # Update equipment state based on status
        if 'state' in status:
            state_str = status['state'].upper()
            try:
                equipment.state = CNCMachineState[state_str]
            except KeyError:
                pass

        # Update properties
        equipment.properties.update(status)

        # Update OPC UA variables if server running
        node = self._equipment_nodes.get(equipment.equipment_id)
        if node and self._server:
            try:
                from asyncua import ua

                # Update state variable
                state_var = await node.get_child([
                    f"{self._namespace_idx}:State"
                ])
                await state_var.write_value(equipment.state.value)

                # Update connected
                connected_var = await node.get_child([
                    f"{self._namespace_idx}:Connected"
                ])
                await connected_var.write_value(True)

            except Exception as e:
                logger.debug(f"Failed to update OPC UA node: {e}")

        # Record history
        if self.enable_history:
            self._record_history(equipment.equipment_id, equipment.to_dict())

    async def _simulate_equipment_updates(self) -> None:
        """Simulate equipment updates for demo/testing."""
        import random

        for equipment_id, equipment in self._equipment.items():
            equipment.last_communication = datetime.now(timezone.utc)
            equipment.connected = True

            # Simulate state changes
            if random.random() < 0.01:
                states = [CNCMachineState.IDLE, CNCMachineState.EXECUTE]
                equipment.state = random.choice(states)

            # Update channel data for CNC
            if equipment.channels:
                channel = equipment.channels[0]
                if equipment.state == CNCMachineState.EXECUTE:
                    channel.program_progress_percent = min(
                        100.0,
                        channel.program_progress_percent + random.uniform(0.1, 0.5)
                    )
                    channel.feed_rate_actual = random.uniform(900, 1100)
                    channel.spindle_speed_actual = random.uniform(11000, 13000)

                    # Update axis positions
                    for axis in channel.axis_positions:
                        channel.axis_positions[axis] += random.uniform(-0.1, 0.1)

            # Update spindle data
            for spindle in equipment.spindles:
                if equipment.state == CNCMachineState.EXECUTE:
                    spindle.is_turning = True
                    spindle.actual_speed_rpm = random.uniform(11000, 13000)
                    spindle.load_percent = random.uniform(20, 40)
                    spindle.temperature_c = random.uniform(35, 45)
                else:
                    spindle.is_turning = False
                    spindle.actual_speed_rpm = 0

            # Record history
            if self.enable_history:
                self._record_history(equipment_id, equipment.to_dict())

    def _record_history(self, equipment_id: str, data: Dict[str, Any]) -> None:
        """Record historical data point."""
        if equipment_id not in self._history:
            self._history[equipment_id] = []

        self._history[equipment_id].append((datetime.now(timezone.utc), data))

        # Trim to limit
        if len(self._history[equipment_id]) > self._history_limit:
            self._history[equipment_id] = self._history[equipment_id][-self._history_limit:]

    # =========================================================================
    # ALARMS
    # =========================================================================

    def raise_alarm(
        self,
        equipment_id: str,
        condition_name: str,
        message: str,
        severity: CNCAlarmSeverity = CNCAlarmSeverity.MEDIUM,
    ) -> Optional[CNCAlarm]:
        """Raise an alarm for equipment."""
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            return None

        alarm = CNCAlarm(
            alarm_id=str(uuid4()),
            condition_name=condition_name,
            severity=severity,
            message=message,
            source_name=equipment.display_name,
        )

        equipment.alarms.append(alarm)

        logger.warning(
            f"Alarm raised: {equipment.display_name} - {condition_name}: {message}"
        )

        return alarm

    def acknowledge_alarm(
        self,
        equipment_id: str,
        alarm_id: str,
        comment: str = ""
    ) -> bool:
        """Acknowledge an alarm."""
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            return False

        for alarm in equipment.alarms:
            if alarm.alarm_id == alarm_id:
                alarm.acknowledged = True
                logger.info(f"Alarm acknowledged: {alarm_id}")
                return True

        return False

    def clear_alarm(self, equipment_id: str, alarm_id: str) -> bool:
        """Clear an alarm."""
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            return False

        for alarm in equipment.alarms:
            if alarm.alarm_id == alarm_id:
                alarm.active = False
                logger.info(f"Alarm cleared: {alarm_id}")
                return True

        return False

    # =========================================================================
    # METHODS
    # =========================================================================

    async def call_equipment_method(
        self,
        equipment_id: str,
        method_name: str,
        args: List[Any]
    ) -> Dict[str, Any]:
        """
        Call a method on equipment.

        Supported methods per OPC 40501:
        - Reset: Reset equipment to idle
        - Start: Start program execution
        - Stop: Stop execution
        - Suspend: Suspend execution
        - Resume: Resume execution
        - Hold: Hold execution (operator)
        - Unhold: Release hold
        - Abort: Abort execution
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            return {'success': False, 'error': 'Equipment not found'}

        method_handlers = {
            'Reset': self._method_reset,
            'Start': self._method_start,
            'Stop': self._method_stop,
            'Suspend': self._method_suspend,
            'Resume': self._method_resume,
            'Hold': self._method_hold,
            'Unhold': self._method_unhold,
            'Abort': self._method_abort,
        }

        handler = method_handlers.get(method_name)
        if not handler:
            return {'success': False, 'error': f'Unknown method: {method_name}'}

        return await handler(equipment, args)

    async def _method_reset(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Reset equipment to idle state."""
        equipment.state = CNCMachineState.RESETTING
        await asyncio.sleep(0.5)  # Simulate reset
        equipment.state = CNCMachineState.IDLE

        # Clear alarms
        for alarm in equipment.alarms:
            alarm.active = False

        # Reset progress
        for channel in equipment.channels:
            channel.program_progress_percent = 0.0
            channel.has_error = False

        # Publish to ROS2 if bridge available
        if self.ros2_bridge and equipment.equipment_id in self._bridges:
            await self.ros2_bridge.publish(
                f'/{equipment.equipment_type.lower()}/{equipment.equipment_id}/command',
                'std_msgs/msg/String',
                {'data': 'RESET'}
            )

        return {'success': True, 'state': equipment.state.name}

    async def _method_start(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Start program execution."""
        if equipment.state not in [CNCMachineState.IDLE, CNCMachineState.COMPLETE]:
            return {'success': False, 'error': 'Cannot start from current state'}

        equipment.state = CNCMachineState.STARTING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.EXECUTE

        return {'success': True, 'state': equipment.state.name}

    async def _method_stop(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Stop execution."""
        equipment.state = CNCMachineState.STOPPING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.STOPPED

        return {'success': True, 'state': equipment.state.name}

    async def _method_suspend(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Suspend execution."""
        if equipment.state != CNCMachineState.EXECUTE:
            return {'success': False, 'error': 'Can only suspend from Execute'}

        equipment.state = CNCMachineState.SUSPENDING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.SUSPENDED

        return {'success': True, 'state': equipment.state.name}

    async def _method_resume(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Resume from suspended."""
        if equipment.state != CNCMachineState.SUSPENDED:
            return {'success': False, 'error': 'Not suspended'}

        equipment.state = CNCMachineState.UNSUSPENDING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.EXECUTE

        return {'success': True, 'state': equipment.state.name}

    async def _method_hold(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Hold execution (operator action)."""
        if equipment.state != CNCMachineState.EXECUTE:
            return {'success': False, 'error': 'Can only hold from Execute'}

        equipment.state = CNCMachineState.HOLDING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.HELD

        return {'success': True, 'state': equipment.state.name}

    async def _method_unhold(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Release hold."""
        if equipment.state != CNCMachineState.HELD:
            return {'success': False, 'error': 'Not held'}

        equipment.state = CNCMachineState.UNHOLDING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.EXECUTE

        return {'success': True, 'state': equipment.state.name}

    async def _method_abort(
        self,
        equipment: OPCUAEquipmentNode,
        args: List[Any]
    ) -> Dict[str, Any]:
        """Abort execution (emergency)."""
        equipment.state = CNCMachineState.ABORTING
        await asyncio.sleep(0.1)
        equipment.state = CNCMachineState.ABORTED

        # Stop spindles
        for spindle in equipment.spindles:
            spindle.is_turning = False
            spindle.actual_speed_rpm = 0

        return {'success': True, 'state': equipment.state.name}

    # =========================================================================
    # STATUS & METRICS
    # =========================================================================

    def get_server_status(self) -> Dict[str, Any]:
        """Get server status summary."""
        return {
            'endpoint': self.endpoint,
            'server_name': self.server_name,
            'running': self._running,
            'namespace_uri': self.NAMESPACE_URI,
            'equipment_count': len(self._equipment),
            'equipment': [eq.to_dict() for eq in self._equipment.values()],
            'history_enabled': self.enable_history,
            'security_enabled': self.enable_security,
        }

    def get_equipment_history(
        self,
        equipment_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get historical data for equipment."""
        history = self._history.get(equipment_id, [])

        if start_time:
            history = [(t, d) for t, d in history if t >= start_time]
        if end_time:
            history = [(t, d) for t, d in history if t <= end_time]

        return [
            {'timestamp': t.isoformat(), 'data': d}
            for t, d in history[-limit:]
        ]


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_opcua_server: Optional[OPCUAServer] = None


def get_opcua_server() -> OPCUAServer:
    """Get or create the OPC UA server instance."""
    global _opcua_server
    if _opcua_server is None:
        _opcua_server = OPCUAServer()
    return _opcua_server


async def init_opcua_server(
    endpoint: str = "opc.tcp://0.0.0.0:4840/legomcp/server/",
    ros2_bridge: Optional[Any] = None,
    auto_register_equipment: bool = True,
) -> OPCUAServer:
    """
    Initialize and start the OPC UA server.

    Args:
        endpoint: Server endpoint URL
        ros2_bridge: ROS2 bridge for equipment data
        auto_register_equipment: Auto-register default equipment

    Returns:
        Started OPCUAServer instance
    """
    global _opcua_server
    _opcua_server = OPCUAServer(
        endpoint=endpoint,
        ros2_bridge=ros2_bridge,
    )

    # Auto-register equipment
    if auto_register_equipment:
        # GRBL CNC Router
        _opcua_server.register_equipment(
            equipment_id='grbl_cnc_1',
            equipment_type='CNC',
            display_name='GRBL CNC Router',
            manufacturer='LegoMCP',
            model='GRBL-3018',
            serial_number='GRBL-001',
        )

        # Bambu Lab X1C
        _opcua_server.register_equipment(
            equipment_id='bambu_x1c_1',
            equipment_type='3DPrinter',
            display_name='Bambu Lab X1 Carbon',
            manufacturer='Bambu Lab',
            model='X1-Carbon',
            serial_number='BBL-X1C-001',
        )

        # Niryo Ned2
        _opcua_server.register_equipment(
            equipment_id='ned2_1',
            equipment_type='Robot',
            display_name='Niryo Ned2 Robot',
            manufacturer='Niryo',
            model='Ned2',
            serial_number='NED2-001',
        )

    await _opcua_server.start()
    return _opcua_server
