#!/usr/bin/env python3
"""
OPC UA CNC Information Model (OPC 40501)

Implements OPC 40501 - OPC UA for CNC Systems information model.
Provides standardized interface for CNC machine data exchange.

Industry 4.0/5.0 Architecture - ISA-95 SCADA/MES Bridge

References:
- OPC 40501-1: OPC UA for CNC Systems - Part 1: General definitions
- OPC 40501-2: OPC UA for CNC Systems - Part 2: CNC information model
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Any, Callable
import logging

logger = logging.getLogger(__name__)


class CncOperatingMode(IntEnum):
    """CNC operating modes per OPC 40501."""
    MANUAL = 0
    MDA = 1  # Manual Data Automatic
    AUTOMATIC = 2
    JOG = 3
    TEACH = 4
    HOMING = 5


class CncExecutionState(IntEnum):
    """CNC execution states per OPC 40501."""
    READY = 0
    ACTIVE = 1
    INTERRUPTED = 2
    FEED_HOLD = 3
    STOPPED = 4


class CncAxisType(Enum):
    """CNC axis types."""
    LINEAR = "linear"
    ROTARY = "rotary"
    SPINDLE = "spindle"


class CncAlarmSeverity(IntEnum):
    """CNC alarm severity levels."""
    INFORMATION = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3


@dataclass
class CncPosition:
    """CNC position in machine coordinates."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None

    def to_list(self) -> List[float]:
        """Convert to list format."""
        result = [self.x, self.y, self.z]
        if self.a is not None:
            result.append(self.a)
        if self.b is not None:
            result.append(self.b)
        if self.c is not None:
            result.append(self.c)
        return result


@dataclass
class CncAxis:
    """CNC axis information per OPC 40501."""
    axis_id: str
    axis_type: CncAxisType
    name: str
    actual_position: float = 0.0
    commanded_position: float = 0.0
    position_deviation: float = 0.0
    velocity: float = 0.0
    acceleration: float = 0.0
    is_homed: bool = False
    is_in_position: bool = False
    following_error: float = 0.0
    min_limit: float = 0.0
    max_limit: float = 0.0
    unit: str = "mm"


@dataclass
class CncSpindle:
    """CNC spindle information per OPC 40501."""
    spindle_id: str
    name: str
    actual_speed: float = 0.0
    commanded_speed: float = 0.0
    load: float = 0.0
    torque: float = 0.0
    is_running: bool = False
    direction: int = 0  # 0=stopped, 1=CW, -1=CCW
    max_speed: float = 0.0
    unit: str = "rpm"


@dataclass
class CncChannel:
    """CNC channel information per OPC 40501."""
    channel_id: str
    name: str
    operating_mode: CncOperatingMode = CncOperatingMode.MANUAL
    execution_state: CncExecutionState = CncExecutionState.READY
    program_name: str = ""
    program_status: str = ""
    block_number: int = 0
    feed_override: float = 100.0
    rapid_override: float = 100.0
    spindle_override: float = 100.0


@dataclass
class CncAlarm:
    """CNC alarm/condition per OPC 40501."""
    alarm_id: str
    alarm_number: int
    severity: CncAlarmSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    active: bool = True
    source: str = ""


@dataclass
class CncProgram:
    """CNC program information."""
    program_id: str
    name: str
    file_path: str = ""
    content: str = ""
    line_count: int = 0
    last_modified: Optional[datetime] = None
    status: str = "idle"


class CncInterfaceModel:
    """
    OPC 40501 CNC Interface Model.

    Implements the standardized OPC UA information model for CNC systems.
    Provides a unified interface for CNC data regardless of controller vendor.

    Usage:
        model = CncInterfaceModel(machine_id="bantam_cnc")

        # Update axis positions
        model.update_axis("X", actual_position=100.5)

        # Get current state
        state = model.get_state()

        # Get OPC UA nodes
        nodes = model.get_opcua_nodes()
    """

    def __init__(
        self,
        machine_id: str,
        vendor: str = "Generic",
        model_name: str = "CNC",
    ):
        """
        Initialize CNC interface model.

        Args:
            machine_id: Unique machine identifier
            vendor: Machine vendor/manufacturer
            model_name: Machine model name
        """
        self.machine_id = machine_id
        self.vendor = vendor
        self.model_name = model_name

        # Initialize components
        self._axes: Dict[str, CncAxis] = {}
        self._spindles: Dict[str, CncSpindle] = {}
        self._channels: Dict[str, CncChannel] = {}
        self._alarms: List[CncAlarm] = []
        self._programs: Dict[str, CncProgram] = {}

        # Current state
        self._operating_mode = CncOperatingMode.MANUAL
        self._execution_state = CncExecutionState.READY
        self._is_emergency_stop = False
        self._is_connected = False

        # Callbacks
        self._state_callbacks: List[Callable] = []
        self._alarm_callbacks: List[Callable] = []

        # Initialize default configuration
        self._initialize_default_config()

        logger.info(f"CNC Interface Model initialized: {machine_id}")

    def _initialize_default_config(self):
        """Initialize default CNC configuration."""
        # Default 3-axis setup
        for axis_id in ['X', 'Y', 'Z']:
            self._axes[axis_id] = CncAxis(
                axis_id=axis_id,
                axis_type=CncAxisType.LINEAR,
                name=f"{axis_id}-Axis",
            )

        # Default spindle
        self._spindles['S1'] = CncSpindle(
            spindle_id='S1',
            name='Main Spindle',
        )

        # Default channel
        self._channels['CH1'] = CncChannel(
            channel_id='CH1',
            name='Main Channel',
        )

    # ===================
    # Configuration
    # ===================

    def add_axis(
        self,
        axis_id: str,
        axis_type: CncAxisType,
        name: str,
        **kwargs,
    ) -> CncAxis:
        """Add or update an axis."""
        axis = CncAxis(
            axis_id=axis_id,
            axis_type=axis_type,
            name=name,
            **kwargs,
        )
        self._axes[axis_id] = axis
        return axis

    def add_spindle(
        self,
        spindle_id: str,
        name: str,
        **kwargs,
    ) -> CncSpindle:
        """Add or update a spindle."""
        spindle = CncSpindle(
            spindle_id=spindle_id,
            name=name,
            **kwargs,
        )
        self._spindles[spindle_id] = spindle
        return spindle

    def add_channel(
        self,
        channel_id: str,
        name: str,
        **kwargs,
    ) -> CncChannel:
        """Add or update a channel."""
        channel = CncChannel(
            channel_id=channel_id,
            name=name,
            **kwargs,
        )
        self._channels[channel_id] = channel
        return channel

    # ===================
    # State Updates
    # ===================

    def update_axis(self, axis_id: str, **kwargs):
        """Update axis state."""
        if axis_id in self._axes:
            for key, value in kwargs.items():
                if hasattr(self._axes[axis_id], key):
                    setattr(self._axes[axis_id], key, value)
            self._notify_state_change()

    def update_spindle(self, spindle_id: str, **kwargs):
        """Update spindle state."""
        if spindle_id in self._spindles:
            for key, value in kwargs.items():
                if hasattr(self._spindles[spindle_id], key):
                    setattr(self._spindles[spindle_id], key, value)
            self._notify_state_change()

    def update_channel(self, channel_id: str, **kwargs):
        """Update channel state."""
        if channel_id in self._channels:
            for key, value in kwargs.items():
                if hasattr(self._channels[channel_id], key):
                    setattr(self._channels[channel_id], key, value)
            self._notify_state_change()

    def set_operating_mode(self, mode: CncOperatingMode):
        """Set operating mode."""
        self._operating_mode = mode
        for channel in self._channels.values():
            channel.operating_mode = mode
        self._notify_state_change()

    def set_execution_state(self, state: CncExecutionState):
        """Set execution state."""
        self._execution_state = state
        for channel in self._channels.values():
            channel.execution_state = state
        self._notify_state_change()

    def set_emergency_stop(self, estop: bool):
        """Set emergency stop state."""
        self._is_emergency_stop = estop
        if estop:
            self._execution_state = CncExecutionState.STOPPED
        self._notify_state_change()

    def set_connected(self, connected: bool):
        """Set connection state."""
        self._is_connected = connected
        self._notify_state_change()

    # ===================
    # Alarms
    # ===================

    def raise_alarm(
        self,
        alarm_number: int,
        message: str,
        severity: CncAlarmSeverity = CncAlarmSeverity.WARNING,
        source: str = "",
    ) -> CncAlarm:
        """Raise a new alarm."""
        alarm = CncAlarm(
            alarm_id=f"ALM-{len(self._alarms)+1:04d}",
            alarm_number=alarm_number,
            severity=severity,
            message=message,
            source=source,
        )
        self._alarms.append(alarm)

        for callback in self._alarm_callbacks:
            try:
                callback(alarm)
            except Exception as e:
                logger.error(f"Alarm callback error: {e}")

        return alarm

    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Acknowledge an alarm."""
        for alarm in self._alarms:
            if alarm.alarm_id == alarm_id:
                alarm.acknowledged = True
                return True
        return False

    def clear_alarm(self, alarm_id: str) -> bool:
        """Clear an alarm."""
        for alarm in self._alarms:
            if alarm.alarm_id == alarm_id:
                alarm.active = False
                return True
        return False

    def reset_alarms(self):
        """Reset all alarms."""
        for alarm in self._alarms:
            alarm.active = False
            alarm.acknowledged = True

    def get_active_alarms(self) -> List[CncAlarm]:
        """Get all active alarms."""
        return [a for a in self._alarms if a.active]

    # ===================
    # Programs
    # ===================

    def load_program(
        self,
        program_id: str,
        name: str,
        content: str = "",
        file_path: str = "",
    ) -> CncProgram:
        """Load a G-code program."""
        program = CncProgram(
            program_id=program_id,
            name=name,
            content=content,
            file_path=file_path,
            line_count=len(content.split('\n')) if content else 0,
            last_modified=datetime.now(),
        )
        self._programs[program_id] = program
        return program

    def select_program(self, program_id: str, channel_id: str = 'CH1') -> bool:
        """Select a program for execution."""
        if program_id in self._programs and channel_id in self._channels:
            self._channels[channel_id].program_name = self._programs[program_id].name
            self._channels[channel_id].program_status = "selected"
            return True
        return False

    # ===================
    # State Queries
    # ===================

    def get_state(self) -> Dict[str, Any]:
        """Get complete CNC state."""
        return {
            'machine_id': self.machine_id,
            'vendor': self.vendor,
            'model': self.model_name,
            'connected': self._is_connected,
            'emergency_stop': self._is_emergency_stop,
            'operating_mode': self._operating_mode.name,
            'execution_state': self._execution_state.name,
            'axes': {
                aid: {
                    'actual_position': a.actual_position,
                    'commanded_position': a.commanded_position,
                    'velocity': a.velocity,
                    'is_homed': a.is_homed,
                }
                for aid, a in self._axes.items()
            },
            'spindles': {
                sid: {
                    'actual_speed': s.actual_speed,
                    'is_running': s.is_running,
                    'load': s.load,
                }
                for sid, s in self._spindles.items()
            },
            'channels': {
                cid: {
                    'program_name': c.program_name,
                    'block_number': c.block_number,
                    'feed_override': c.feed_override,
                }
                for cid, c in self._channels.items()
            },
            'active_alarms': len(self.get_active_alarms()),
        }

    def get_position(self) -> CncPosition:
        """Get current machine position."""
        return CncPosition(
            x=self._axes.get('X', CncAxis('X', CncAxisType.LINEAR, 'X')).actual_position,
            y=self._axes.get('Y', CncAxis('Y', CncAxisType.LINEAR, 'Y')).actual_position,
            z=self._axes.get('Z', CncAxis('Z', CncAxisType.LINEAR, 'Z')).actual_position,
            a=self._axes.get('A', CncAxis('A', CncAxisType.ROTARY, 'A')).actual_position if 'A' in self._axes else None,
            b=self._axes.get('B', CncAxis('B', CncAxisType.ROTARY, 'B')).actual_position if 'B' in self._axes else None,
            c=self._axes.get('C', CncAxis('C', CncAxisType.ROTARY, 'C')).actual_position if 'C' in self._axes else None,
        )

    # ===================
    # OPC UA Integration
    # ===================

    def get_opcua_nodes(self) -> Dict[str, Any]:
        """
        Get OPC UA node structure per OPC 40501.

        Returns dictionary representing OPC UA address space.
        """
        return {
            'CncInterfaceType': {
                'NodeId': f'ns=2;s={self.machine_id}',
                'BrowseName': 'CncInterface',
                'Children': {
                    'CncAxisList': {
                        'NodeId': f'ns=2;s={self.machine_id}/AxisList',
                        'Children': {
                            axis_id: self._axis_to_opcua(axis)
                            for axis_id, axis in self._axes.items()
                        }
                    },
                    'CncSpindleList': {
                        'NodeId': f'ns=2;s={self.machine_id}/SpindleList',
                        'Children': {
                            spindle_id: self._spindle_to_opcua(spindle)
                            for spindle_id, spindle in self._spindles.items()
                        }
                    },
                    'CncChannelList': {
                        'NodeId': f'ns=2;s={self.machine_id}/ChannelList',
                        'Children': {
                            channel_id: self._channel_to_opcua(channel)
                            for channel_id, channel in self._channels.items()
                        }
                    },
                    'CncAlarmList': {
                        'NodeId': f'ns=2;s={self.machine_id}/AlarmList',
                        'ActiveAlarms': [a.alarm_id for a in self.get_active_alarms()],
                    },
                }
            }
        }

    def _axis_to_opcua(self, axis: CncAxis) -> Dict:
        """Convert axis to OPC UA representation."""
        return {
            'NodeId': f'ns=2;s={self.machine_id}/Axis/{axis.axis_id}',
            'BrowseName': axis.name,
            'Variables': {
                'ActPos': {'Value': axis.actual_position, 'DataType': 'Double'},
                'CmdPos': {'Value': axis.commanded_position, 'DataType': 'Double'},
                'ActVel': {'Value': axis.velocity, 'DataType': 'Double'},
                'IsHomed': {'Value': axis.is_homed, 'DataType': 'Boolean'},
                'InPosition': {'Value': axis.is_in_position, 'DataType': 'Boolean'},
            }
        }

    def _spindle_to_opcua(self, spindle: CncSpindle) -> Dict:
        """Convert spindle to OPC UA representation."""
        return {
            'NodeId': f'ns=2;s={self.machine_id}/Spindle/{spindle.spindle_id}',
            'BrowseName': spindle.name,
            'Variables': {
                'ActSpeed': {'Value': spindle.actual_speed, 'DataType': 'Double'},
                'CmdSpeed': {'Value': spindle.commanded_speed, 'DataType': 'Double'},
                'Load': {'Value': spindle.load, 'DataType': 'Double'},
                'IsRunning': {'Value': spindle.is_running, 'DataType': 'Boolean'},
            }
        }

    def _channel_to_opcua(self, channel: CncChannel) -> Dict:
        """Convert channel to OPC UA representation."""
        return {
            'NodeId': f'ns=2;s={self.machine_id}/Channel/{channel.channel_id}',
            'BrowseName': channel.name,
            'Variables': {
                'OperatingMode': {'Value': channel.operating_mode.value, 'DataType': 'Int32'},
                'ExecutionState': {'Value': channel.execution_state.value, 'DataType': 'Int32'},
                'ProgramName': {'Value': channel.program_name, 'DataType': 'String'},
                'BlockNumber': {'Value': channel.block_number, 'DataType': 'Int32'},
                'FeedOverride': {'Value': channel.feed_override, 'DataType': 'Double'},
            }
        }

    # ===================
    # Callbacks
    # ===================

    def register_state_callback(self, callback: Callable):
        """Register callback for state changes."""
        self._state_callbacks.append(callback)

    def register_alarm_callback(self, callback: Callable):
        """Register callback for alarms."""
        self._alarm_callbacks.append(callback)

    def _notify_state_change(self):
        """Notify registered callbacks of state change."""
        state = self.get_state()
        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"State callback error: {e}")


def create_bantam_cnc_model() -> CncInterfaceModel:
    """Create CNC model for Bantam Tools Desktop CNC."""
    model = CncInterfaceModel(
        machine_id="bantam_cnc",
        vendor="Bantam Tools",
        model_name="Desktop PCB Milling Machine",
    )

    # Configure axes
    model.add_axis('X', CncAxisType.LINEAR, 'X-Axis', max_limit=140.0)
    model.add_axis('Y', CncAxisType.LINEAR, 'Y-Axis', max_limit=102.0)
    model.add_axis('Z', CncAxisType.LINEAR, 'Z-Axis', max_limit=38.0)

    # Configure spindle
    model.add_spindle('S1', 'Main Spindle', max_speed=26000.0)

    return model


def create_grbl_cnc_model(machine_id: str = "grbl_cnc") -> CncInterfaceModel:
    """Create CNC model for generic GRBL machine."""
    model = CncInterfaceModel(
        machine_id=machine_id,
        vendor="Generic",
        model_name="GRBL CNC",
    )

    # Default 3-axis config
    model.add_axis('X', CncAxisType.LINEAR, 'X-Axis', max_limit=300.0)
    model.add_axis('Y', CncAxisType.LINEAR, 'Y-Axis', max_limit=300.0)
    model.add_axis('Z', CncAxisType.LINEAR, 'Z-Axis', max_limit=50.0)

    return model
