"""
LEGO Factory v3 - Level 1 PLC Controller
==========================================
Fine-grained machine control for CNC machines.

ISA-95 Level 1 capabilities:
- Direct G-code execution
- Probing cycles (G38.x)
- Work Coordinate Systems (G54-G59, G59.1-G59.3)
- Tool length/diameter offsets
- Datum point management
- Sensor data acquisition
- Real-time position monitoring
- Feed/speed overrides
- Coolant/spindle control
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Tuple

logger = logging.getLogger(__name__)


class WCS(Enum):
    """Work Coordinate Systems (G54-G59, extended)."""
    G53 = 'G53'  # Machine coordinates
    G54 = 'G54'  # WCS 1 (default)
    G55 = 'G55'  # WCS 2
    G56 = 'G56'  # WCS 3
    G57 = 'G57'  # WCS 4
    G58 = 'G58'  # WCS 5
    G59 = 'G59'  # WCS 6
    G59_1 = 'G59.1'  # Extended WCS 7
    G59_2 = 'G59.2'  # Extended WCS 8
    G59_3 = 'G59.3'  # Extended WCS 9


class ProbeType(Enum):
    """Probe cycle types."""
    TOOL_LENGTH = 'tool_length'
    WORK_Z = 'work_z'
    CORNER_XY = 'corner_xy'
    CENTER_X = 'center_x'
    CENTER_Y = 'center_y'
    EDGE_X = 'edge_x'
    EDGE_Y = 'edge_y'
    BORE = 'bore'
    BOSS = 'boss'
    WEB = 'web'
    POCKET = 'pocket'


class MotionMode(Enum):
    """Motion modes."""
    RAPID = 'G0'
    LINEAR = 'G1'
    CW_ARC = 'G2'
    CCW_ARC = 'G3'


class DistanceMode(Enum):
    """Distance modes."""
    ABSOLUTE = 'G90'
    INCREMENTAL = 'G91'


class UnitsMode(Enum):
    """Units modes."""
    INCHES = 'G20'
    MM = 'G21'


class SpindleState(Enum):
    """Spindle states."""
    OFF = 'M5'
    CW = 'M3'
    CCW = 'M4'


class CoolantState(Enum):
    """Coolant states."""
    OFF = 'M9'
    MIST = 'M7'
    FLOOD = 'M8'


@dataclass
class Position:
    """6-axis position."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z, 'a': self.a, 'b': self.b, 'c': self.c}

    def to_gcode(self, axes: str = 'XYZ') -> str:
        parts = []
        if 'X' in axes:
            parts.append(f'X{self.x:.4f}')
        if 'Y' in axes:
            parts.append(f'Y{self.y:.4f}')
        if 'Z' in axes:
            parts.append(f'Z{self.z:.4f}')
        if 'A' in axes:
            parts.append(f'A{self.a:.4f}')
        if 'B' in axes:
            parts.append(f'B{self.b:.4f}')
        if 'C' in axes:
            parts.append(f'C{self.c:.4f}')
        return ' '.join(parts)


@dataclass
class ProbeResult:
    """Result of a probing cycle."""
    success: bool
    probe_type: ProbeType
    timestamp: datetime
    position: Position  # Where probe triggered
    machine_position: Position  # Machine coords at trigger
    wcs: WCS
    probe_value: float  # Primary measured value
    error: Optional[str] = None
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'probe_type': self.probe_type.value,
            'timestamp': self.timestamp.isoformat(),
            'position': self.position.to_dict(),
            'machine_position': self.machine_position.to_dict(),
            'wcs': self.wcs.value,
            'probe_value': self.probe_value,
            'error': self.error,
        }


@dataclass
class ToolOffset:
    """Tool offset entry."""
    tool_number: int
    length_offset: float = 0.0
    diameter: float = 0.0
    x_offset: float = 0.0
    y_offset: float = 0.0
    wear_length: float = 0.0
    wear_diameter: float = 0.0
    description: str = ""
    last_measured: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tool_number': self.tool_number,
            'length_offset': self.length_offset,
            'diameter': self.diameter,
            'x_offset': self.x_offset,
            'y_offset': self.y_offset,
            'wear_length': self.wear_length,
            'wear_diameter': self.wear_diameter,
            'description': self.description,
            'last_measured': self.last_measured.isoformat() if self.last_measured else None,
        }


@dataclass
class DatumPoint:
    """Saved datum/reference point."""
    name: str
    position: Position
    wcs: WCS
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'position': self.position.to_dict(),
            'wcs': self.wcs.value,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
        }


@dataclass
class SensorReading:
    """Sensor data reading."""
    sensor_id: str
    sensor_type: str  # temperature, vibration, current, pressure, etc.
    value: float
    unit: str
    timestamp: datetime
    quality: str = 'good'  # good, uncertain, bad
    machine_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sensor_id': self.sensor_id,
            'sensor_type': self.sensor_type,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'quality': self.quality,
            'machine_id': self.machine_id,
        }


@dataclass
class WCSOffset:
    """Work coordinate system offset from machine zero."""
    wcs: WCS
    offset: Position
    description: str = ""
    set_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'wcs': self.wcs.value,
            'offset': self.offset.to_dict(),
            'description': self.description,
            'set_at': self.set_at.isoformat() if self.set_at else None,
        }


class PLCController:
    """
    Level 1 PLC Controller for CNC machines.

    Provides fine-grained control including:
    - Probing cycles
    - Work coordinate systems
    - Tool offsets
    - Datum management
    - Sensor data acquisition
    - Real-time monitoring
    """

    def __init__(self, machine_id: str, controller_type: str = 'grbl'):
        """
        Initialize PLC controller.

        Args:
            machine_id: Unique machine identifier
            controller_type: 'grbl', 'grblhal', or 'tinyg'
        """
        self.machine_id = machine_id
        self.controller_type = controller_type.lower()

        # State
        self._connected = False
        self._current_wcs = WCS.G54
        self._distance_mode = DistanceMode.ABSOLUTE
        self._units_mode = UnitsMode.MM
        self._motion_mode = MotionMode.RAPID
        self._spindle_state = SpindleState.OFF
        self._coolant_state = CoolantState.OFF

        # Position tracking
        self._machine_position = Position()
        self._work_position = Position()

        # Rates and overrides
        self._feed_rate = 0.0
        self._spindle_speed = 0.0
        self._feed_override = 100  # percent
        self._rapid_override = 100
        self._spindle_override = 100

        # Tool management
        self._current_tool = 0
        self._tool_table: Dict[int, ToolOffset] = {}

        # WCS offsets
        self._wcs_offsets: Dict[WCS, WCSOffset] = {
            wcs: WCSOffset(wcs=wcs, offset=Position()) for wcs in WCS
        }

        # Datums
        self._datums: Dict[str, DatumPoint] = {}

        # Probe configuration
        self._probe_feed_rate = 100.0  # mm/min
        self._probe_seek_rate = 500.0  # mm/min for initial approach
        self._probe_retract = 2.0  # mm to retract after probe

        # Sensor readings cache
        self._sensor_readings: Dict[str, SensorReading] = {}
        self._sensor_callbacks: List[Callable[[SensorReading], None]] = []

        # Data collection
        self._data_collection_enabled = False
        self._data_collection_interval = 0.1  # seconds
        self._collected_data: List[Dict[str, Any]] = []
        self._data_collection_thread: Optional[threading.Thread] = None

        # Machine controller reference
        self._machine_controller = None

        # Lock for thread safety
        self._lock = threading.Lock()

        logger.info(f"PLCController initialized for {machine_id} ({controller_type})")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def current_wcs(self) -> WCS:
        return self._current_wcs

    @property
    def machine_position(self) -> Position:
        return self._machine_position

    @property
    def work_position(self) -> Position:
        return self._work_position

    def connect(self, machine_controller=None) -> bool:
        """Connect to the machine controller."""
        if machine_controller:
            self._machine_controller = machine_controller

        # Try to get from machine manager if not provided
        if not self._machine_controller:
            try:
                from services.scada.machine_control.machine_service import get_machine_manager
                manager = get_machine_manager()
                self._machine_controller = manager.get_machine(self.machine_id)
            except Exception as e:
                logger.warning(f"Could not get machine controller: {e}")

        self._connected = self._machine_controller is not None
        return self._connected

    async def send_gcode(self, gcode: str) -> Tuple[bool, str]:
        """Send G-code command and wait for response."""
        if not self._machine_controller:
            return False, "Not connected"

        try:
            if hasattr(self._machine_controller, 'send_command'):
                response = await self._machine_controller.send_command(gcode)
                return True, response
            else:
                return False, "Controller doesn't support send_command"
        except Exception as e:
            logger.error(f"Error sending G-code '{gcode}': {e}")
            return False, str(e)

    def send_gcode_sync(self, gcode: str) -> Tuple[bool, str]:
        """Synchronous G-code send."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_gcode(gcode))
        finally:
            loop.close()

    # =========================================================================
    # Work Coordinate Systems (WCS)
    # =========================================================================

    def set_wcs(self, wcs: WCS) -> bool:
        """Switch to a work coordinate system."""
        success, _ = self.send_gcode_sync(wcs.value)
        if success:
            self._current_wcs = wcs
            logger.info(f"Switched to {wcs.value}")
        return success

    def get_wcs_offset(self, wcs: WCS) -> WCSOffset:
        """Get the offset for a WCS."""
        return self._wcs_offsets.get(wcs, WCSOffset(wcs=wcs, offset=Position()))

    def set_wcs_offset(self, wcs: WCS, offset: Position, description: str = "") -> bool:
        """
        Set the offset for a WCS.

        For GRBL: Uses G10 L2 P# to set WCS offset
        For TinyG: Uses G10 L2 P# as well
        """
        # P number: G54=1, G55=2, ... G59=6, G59.1=7, G59.2=8, G59.3=9
        p_map = {
            WCS.G54: 1, WCS.G55: 2, WCS.G56: 3, WCS.G57: 4,
            WCS.G58: 5, WCS.G59: 6, WCS.G59_1: 7, WCS.G59_2: 8, WCS.G59_3: 9
        }
        p_num = p_map.get(wcs, 1)

        gcode = f"G10 L2 P{p_num} {offset.to_gcode()}"
        success, response = self.send_gcode_sync(gcode)

        if success:
            self._wcs_offsets[wcs] = WCSOffset(
                wcs=wcs,
                offset=offset,
                description=description,
                set_at=datetime.now()
            )
            logger.info(f"Set {wcs.value} offset: {offset.to_dict()}")

        return success

    def zero_wcs(self, wcs: WCS = None, axes: str = 'XYZ') -> bool:
        """
        Zero the current position in a WCS (set work zero at current position).

        Uses G10 L20 to set WCS offset relative to current position.
        """
        target_wcs = wcs or self._current_wcs
        p_map = {
            WCS.G54: 1, WCS.G55: 2, WCS.G56: 3, WCS.G57: 4,
            WCS.G58: 5, WCS.G59: 6, WCS.G59_1: 7, WCS.G59_2: 8, WCS.G59_3: 9
        }
        p_num = p_map.get(target_wcs, 1)

        # Build zero command for specified axes
        zeros = []
        if 'X' in axes:
            zeros.append('X0')
        if 'Y' in axes:
            zeros.append('Y0')
        if 'Z' in axes:
            zeros.append('Z0')

        gcode = f"G10 L20 P{p_num} {' '.join(zeros)}"
        success, response = self.send_gcode_sync(gcode)

        if success:
            logger.info(f"Zeroed {target_wcs.value} axes: {axes}")

        return success

    def get_all_wcs_offsets(self) -> Dict[str, Dict]:
        """Get all WCS offsets."""
        return {wcs.value: offset.to_dict() for wcs, offset in self._wcs_offsets.items()}

    # =========================================================================
    # Probing Cycles
    # =========================================================================

    async def probe_z(self, feed_rate: float = None, max_distance: float = 50.0) -> ProbeResult:
        """
        Probe Z axis (touch off work surface).

        Uses G38.2 (probe toward workpiece, stop on contact, error if no contact).
        """
        feed = feed_rate or self._probe_feed_rate

        # Move down (negative Z) looking for contact
        gcode = f"G38.2 Z-{max_distance:.3f} F{feed:.1f}"
        success, response = await self.send_gcode(gcode)

        result = ProbeResult(
            success=success and 'ALARM' not in response.upper(),
            probe_type=ProbeType.WORK_Z,
            timestamp=datetime.now(),
            position=Position(z=self._work_position.z),
            machine_position=Position(z=self._machine_position.z),
            wcs=self._current_wcs,
            probe_value=self._work_position.z,
            raw_response=response
        )

        if not result.success:
            result.error = "Probe did not contact surface"

        # Retract after probe
        if result.success:
            await self.send_gcode(f"G0 Z{self._work_position.z + self._probe_retract:.3f}")

        return result

    async def probe_tool_length(self, tool_setter_z: float, feed_rate: float = None) -> ProbeResult:
        """
        Probe tool length using a tool setter at known Z position.

        Args:
            tool_setter_z: Known Z height of tool setter surface
            feed_rate: Probe feed rate
        """
        feed = feed_rate or self._probe_feed_rate

        # Probe toward tool setter
        gcode = f"G38.2 Z{tool_setter_z - 10:.3f} F{feed:.1f}"
        success, response = await self.send_gcode(gcode)

        tool_length = 0.0
        if success and 'ALARM' not in response.upper():
            # Calculate tool length from machine Z and tool setter position
            tool_length = self._machine_position.z - tool_setter_z

        result = ProbeResult(
            success=success and 'ALARM' not in response.upper(),
            probe_type=ProbeType.TOOL_LENGTH,
            timestamp=datetime.now(),
            position=Position(z=self._work_position.z),
            machine_position=Position(z=self._machine_position.z),
            wcs=self._current_wcs,
            probe_value=tool_length,
            raw_response=response
        )

        # Update tool table
        if result.success and self._current_tool > 0:
            self.set_tool_offset(self._current_tool, length_offset=tool_length)

        # Retract
        if result.success:
            await self.send_gcode(f"G0 Z{self._work_position.z + self._probe_retract:.3f}")

        return result

    async def probe_edge_x(self, direction: int = 1, feed_rate: float = None, max_distance: float = 25.0) -> ProbeResult:
        """
        Probe X edge.

        Args:
            direction: 1 for positive X, -1 for negative X
            feed_rate: Probe feed rate
            max_distance: Maximum probe distance
        """
        feed = feed_rate or self._probe_feed_rate
        target_x = self._work_position.x + (max_distance * direction)

        gcode = f"G38.2 X{target_x:.3f} F{feed:.1f}"
        success, response = await self.send_gcode(gcode)

        result = ProbeResult(
            success=success and 'ALARM' not in response.upper(),
            probe_type=ProbeType.EDGE_X,
            timestamp=datetime.now(),
            position=Position(x=self._work_position.x),
            machine_position=Position(x=self._machine_position.x),
            wcs=self._current_wcs,
            probe_value=self._work_position.x,
            raw_response=response
        )

        # Retract
        if result.success:
            retract_x = self._work_position.x - (self._probe_retract * direction)
            await self.send_gcode(f"G0 X{retract_x:.3f}")

        return result

    async def probe_edge_y(self, direction: int = 1, feed_rate: float = None, max_distance: float = 25.0) -> ProbeResult:
        """Probe Y edge."""
        feed = feed_rate or self._probe_feed_rate
        target_y = self._work_position.y + (max_distance * direction)

        gcode = f"G38.2 Y{target_y:.3f} F{feed:.1f}"
        success, response = await self.send_gcode(gcode)

        result = ProbeResult(
            success=success and 'ALARM' not in response.upper(),
            probe_type=ProbeType.EDGE_Y,
            timestamp=datetime.now(),
            position=Position(y=self._work_position.y),
            machine_position=Position(y=self._machine_position.y),
            wcs=self._current_wcs,
            probe_value=self._work_position.y,
            raw_response=response
        )

        # Retract
        if result.success:
            retract_y = self._work_position.y - (self._probe_retract * direction)
            await self.send_gcode(f"G0 Y{retract_y:.3f}")

        return result

    async def probe_corner(self, corner: str = 'front_left', feed_rate: float = None) -> Dict[str, ProbeResult]:
        """
        Probe a corner to find X and Y edges.

        Args:
            corner: 'front_left', 'front_right', 'back_left', 'back_right'
        """
        results = {}

        # Determine probe directions based on corner
        if corner == 'front_left':
            x_dir, y_dir = 1, 1
        elif corner == 'front_right':
            x_dir, y_dir = -1, 1
        elif corner == 'back_left':
            x_dir, y_dir = 1, -1
        else:  # back_right
            x_dir, y_dir = -1, -1

        # Probe X
        results['x'] = await self.probe_edge_x(direction=x_dir, feed_rate=feed_rate)

        # Return to start, move in Y, probe Y
        if results['x'].success:
            results['y'] = await self.probe_edge_y(direction=y_dir, feed_rate=feed_rate)

        return results

    async def probe_center_x(self, expected_width: float, feed_rate: float = None) -> ProbeResult:
        """Find center of a feature in X by probing both sides."""
        feed = feed_rate or self._probe_feed_rate

        # Probe +X
        result_pos = await self.probe_edge_x(direction=1, feed_rate=feed)
        if not result_pos.success:
            return result_pos

        x_pos = result_pos.probe_value

        # Move over and probe -X
        await self.send_gcode(f"G0 X{self._work_position.x - expected_width - 10:.3f}")
        result_neg = await self.probe_edge_x(direction=-1, feed_rate=feed)

        if not result_neg.success:
            return result_neg

        x_neg = result_neg.probe_value

        # Calculate center
        center_x = (x_pos + x_neg) / 2
        width = abs(x_pos - x_neg)

        return ProbeResult(
            success=True,
            probe_type=ProbeType.CENTER_X,
            timestamp=datetime.now(),
            position=Position(x=center_x),
            machine_position=self._machine_position,
            wcs=self._current_wcs,
            probe_value=center_x,
        )

    # =========================================================================
    # Tool Management
    # =========================================================================

    def get_tool_offset(self, tool_number: int) -> Optional[ToolOffset]:
        """Get tool offset entry."""
        return self._tool_table.get(tool_number)

    def set_tool_offset(
        self,
        tool_number: int,
        length_offset: float = None,
        diameter: float = None,
        x_offset: float = None,
        y_offset: float = None,
        description: str = None
    ) -> bool:
        """Set tool offset."""
        if tool_number not in self._tool_table:
            self._tool_table[tool_number] = ToolOffset(tool_number=tool_number)

        tool = self._tool_table[tool_number]

        if length_offset is not None:
            tool.length_offset = length_offset
        if diameter is not None:
            tool.diameter = diameter
        if x_offset is not None:
            tool.x_offset = x_offset
        if y_offset is not None:
            tool.y_offset = y_offset
        if description is not None:
            tool.description = description

        tool.last_measured = datetime.now()

        # Apply to controller (GRBL uses G43.1 for tool length)
        if length_offset is not None:
            self.send_gcode_sync(f"G43.1 Z{length_offset:.4f}")

        logger.info(f"Set tool {tool_number} offset: L={length_offset}, D={diameter}")
        return True

    def get_tool_table(self) -> Dict[int, Dict]:
        """Get entire tool table."""
        return {num: tool.to_dict() for num, tool in self._tool_table.items()}

    def tool_change(self, tool_number: int) -> bool:
        """Execute tool change."""
        success, _ = self.send_gcode_sync(f"T{tool_number} M6")
        if success:
            self._current_tool = tool_number
            # Apply tool length offset
            tool = self._tool_table.get(tool_number)
            if tool:
                self.send_gcode_sync(f"G43.1 Z{tool.length_offset:.4f}")
        return success

    # =========================================================================
    # Datum Point Management
    # =========================================================================

    def save_datum(self, name: str, position: Position = None, description: str = "") -> DatumPoint:
        """Save current position as a named datum point."""
        pos = position or Position(
            x=self._work_position.x,
            y=self._work_position.y,
            z=self._work_position.z,
            a=self._work_position.a,
            b=self._work_position.b,
            c=self._work_position.c
        )

        datum = DatumPoint(
            name=name,
            position=pos,
            wcs=self._current_wcs,
            description=description
        )
        self._datums[name] = datum
        logger.info(f"Saved datum '{name}' at {pos.to_dict()}")
        return datum

    def get_datum(self, name: str) -> Optional[DatumPoint]:
        """Get a saved datum point."""
        return self._datums.get(name)

    def go_to_datum(self, name: str, feed_rate: float = None) -> bool:
        """Move to a saved datum point."""
        datum = self._datums.get(name)
        if not datum:
            logger.warning(f"Datum '{name}' not found")
            return False

        # Switch to datum's WCS if different
        if datum.wcs != self._current_wcs:
            self.set_wcs(datum.wcs)

        # Move to position
        gcode = f"G0 {datum.position.to_gcode()}"
        if feed_rate:
            gcode = f"G1 {datum.position.to_gcode()} F{feed_rate:.1f}"

        success, _ = self.send_gcode_sync(gcode)
        return success

    def list_datums(self) -> Dict[str, Dict]:
        """List all saved datums."""
        return {name: datum.to_dict() for name, datum in self._datums.items()}

    def delete_datum(self, name: str) -> bool:
        """Delete a datum point."""
        if name in self._datums:
            del self._datums[name]
            return True
        return False

    # =========================================================================
    # Feed/Speed Overrides
    # =========================================================================

    def set_feed_override(self, percent: int) -> bool:
        """Set feed rate override (10-200%)."""
        percent = max(10, min(200, percent))
        self._feed_override = percent

        # GRBL uses real-time commands for overrides
        # These are sent as single bytes
        if self.controller_type == 'grbl':
            # GRBL override commands (sent as raw bytes)
            # For simplicity, we'll use G-code approach if available
            pass

        logger.info(f"Feed override: {percent}%")
        return True

    def set_spindle_override(self, percent: int) -> bool:
        """Set spindle speed override (10-200%)."""
        percent = max(10, min(200, percent))
        self._spindle_override = percent
        logger.info(f"Spindle override: {percent}%")
        return True

    def set_rapid_override(self, percent: int) -> bool:
        """Set rapid motion override (25%, 50%, or 100%)."""
        # GRBL only supports 25%, 50%, 100%
        if percent <= 25:
            self._rapid_override = 25
        elif percent <= 50:
            self._rapid_override = 50
        else:
            self._rapid_override = 100
        logger.info(f"Rapid override: {self._rapid_override}%")
        return True

    # =========================================================================
    # Spindle & Coolant Control
    # =========================================================================

    def spindle_on(self, speed: float, direction: str = 'cw') -> bool:
        """Turn spindle on."""
        cmd = 'M3' if direction.lower() == 'cw' else 'M4'
        success, _ = self.send_gcode_sync(f"{cmd} S{speed:.0f}")
        if success:
            self._spindle_state = SpindleState.CW if direction.lower() == 'cw' else SpindleState.CCW
            self._spindle_speed = speed
        return success

    def spindle_off(self) -> bool:
        """Turn spindle off."""
        success, _ = self.send_gcode_sync("M5")
        if success:
            self._spindle_state = SpindleState.OFF
            self._spindle_speed = 0
        return success

    def coolant_on(self, mode: str = 'flood') -> bool:
        """Turn coolant on."""
        cmd = 'M8' if mode.lower() == 'flood' else 'M7'
        success, _ = self.send_gcode_sync(cmd)
        if success:
            self._coolant_state = CoolantState.FLOOD if mode.lower() == 'flood' else CoolantState.MIST
        return success

    def coolant_off(self) -> bool:
        """Turn coolant off."""
        success, _ = self.send_gcode_sync("M9")
        if success:
            self._coolant_state = CoolantState.OFF
        return success

    # =========================================================================
    # Sensor Data Acquisition
    # =========================================================================

    def register_sensor(self, sensor_id: str, sensor_type: str, unit: str) -> None:
        """Register a sensor for data collection."""
        self._sensor_readings[sensor_id] = SensorReading(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            value=0.0,
            unit=unit,
            timestamp=datetime.now(),
            machine_id=self.machine_id
        )

    def update_sensor(self, sensor_id: str, value: float, quality: str = 'good') -> None:
        """Update sensor reading."""
        if sensor_id in self._sensor_readings:
            reading = SensorReading(
                sensor_id=sensor_id,
                sensor_type=self._sensor_readings[sensor_id].sensor_type,
                value=value,
                unit=self._sensor_readings[sensor_id].unit,
                timestamp=datetime.now(),
                quality=quality,
                machine_id=self.machine_id
            )
            self._sensor_readings[sensor_id] = reading

            # Notify callbacks
            for callback in self._sensor_callbacks:
                try:
                    callback(reading)
                except Exception as e:
                    logger.error(f"Sensor callback error: {e}")

    def get_sensor_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get latest sensor reading."""
        return self._sensor_readings.get(sensor_id)

    def get_all_sensors(self) -> Dict[str, Dict]:
        """Get all sensor readings."""
        return {sid: reading.to_dict() for sid, reading in self._sensor_readings.items()}

    def on_sensor_update(self, callback: Callable[[SensorReading], None]) -> None:
        """Register callback for sensor updates."""
        self._sensor_callbacks.append(callback)

    # =========================================================================
    # Data Collection
    # =========================================================================

    def start_data_collection(self, interval: float = 0.1) -> None:
        """Start collecting machine data at specified interval."""
        self._data_collection_interval = interval
        self._data_collection_enabled = True
        self._collected_data = []

        self._data_collection_thread = threading.Thread(target=self._data_collection_loop, daemon=True)
        self._data_collection_thread.start()
        logger.info(f"Data collection started at {interval}s interval")

    def stop_data_collection(self) -> List[Dict[str, Any]]:
        """Stop data collection and return collected data."""
        self._data_collection_enabled = False
        if self._data_collection_thread:
            self._data_collection_thread.join(timeout=1.0)

        data = self._collected_data.copy()
        self._collected_data = []
        logger.info(f"Data collection stopped. {len(data)} samples collected.")
        return data

    def _data_collection_loop(self) -> None:
        """Background data collection loop."""
        while self._data_collection_enabled:
            try:
                sample = {
                    'timestamp': datetime.now().isoformat(),
                    'machine_position': self._machine_position.to_dict(),
                    'work_position': self._work_position.to_dict(),
                    'feed_rate': self._feed_rate,
                    'spindle_speed': self._spindle_speed,
                    'feed_override': self._feed_override,
                    'spindle_override': self._spindle_override,
                    'wcs': self._current_wcs.value,
                    'tool': self._current_tool,
                    'sensors': {sid: r.value for sid, r in self._sensor_readings.items()},
                }
                self._collected_data.append(sample)
            except Exception as e:
                logger.error(f"Data collection error: {e}")

            time.sleep(self._data_collection_interval)

    def export_collected_data(self, filepath: str) -> bool:
        """Export collected data to JSON file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self._collected_data, f, indent=2)
            logger.info(f"Exported {len(self._collected_data)} samples to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            return False

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive PLC status."""
        return {
            'machine_id': self.machine_id,
            'connected': self._connected,
            'controller_type': self.controller_type,
            'wcs': self._current_wcs.value,
            'distance_mode': self._distance_mode.value,
            'units_mode': self._units_mode.value,
            'machine_position': self._machine_position.to_dict(),
            'work_position': self._work_position.to_dict(),
            'feed_rate': self._feed_rate,
            'spindle_speed': self._spindle_speed,
            'spindle_state': self._spindle_state.value,
            'coolant_state': self._coolant_state.value,
            'current_tool': self._current_tool,
            'feed_override': self._feed_override,
            'rapid_override': self._rapid_override,
            'spindle_override': self._spindle_override,
            'data_collection_enabled': self._data_collection_enabled,
            'samples_collected': len(self._collected_data),
        }


# Global PLC controller registry
_plc_controllers: Dict[str, PLCController] = {}


def get_plc_controller(machine_id: str, controller_type: str = 'grbl') -> PLCController:
    """Get or create a PLC controller for a machine."""
    global _plc_controllers

    if machine_id not in _plc_controllers:
        _plc_controllers[machine_id] = PLCController(machine_id, controller_type)

    return _plc_controllers[machine_id]
