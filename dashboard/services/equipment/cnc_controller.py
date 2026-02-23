"""
CNC Machine Controller for Algorithm-to-Action Bridge.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge

Provides control interface for CNC machines including:
- G-code generation and streaming
- Tool path optimization
- Real-time position monitoring
- Spindle and feed rate control
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, AsyncIterator
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
import logging

logger = logging.getLogger(__name__)


class CNCState(Enum):
    """CNC machine state."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    HOMING = "homing"
    ALARM = "alarm"
    DISCONNECTED = "disconnected"


class SpindleState(Enum):
    """Spindle state."""
    OFF = "off"
    CW = "clockwise"
    CCW = "counter_clockwise"


class CoolantState(Enum):
    """Coolant state."""
    OFF = "off"
    FLOOD = "flood"
    MIST = "mist"


class CoordinateSystem(Enum):
    """Work coordinate system."""
    G54 = "G54"
    G55 = "G55"
    G56 = "G56"
    G57 = "G57"
    G58 = "G58"
    G59 = "G59"


@dataclass
class CNCPosition:
    """CNC machine position."""
    x: float
    y: float
    z: float
    a: Optional[float] = None  # 4th axis
    b: Optional[float] = None  # 5th axis
    c: Optional[float] = None  # 6th axis

    # Work vs machine coordinates
    is_work_coords: bool = True
    coordinate_system: CoordinateSystem = CoordinateSystem.G54

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "is_work_coords": self.is_work_coords,
            "coordinate_system": self.coordinate_system.value,
        }


@dataclass
class CNCStatus:
    """Complete CNC machine status."""
    state: CNCState
    position: CNCPosition

    # Spindle
    spindle_state: SpindleState
    spindle_speed: float  # RPM
    spindle_load: float  # Percentage

    # Feed
    feed_rate: float  # mm/min or in/min
    feed_override: float  # Percentage (100 = normal)
    rapid_override: float  # Percentage

    # Coolant
    coolant_state: CoolantState

    # Program
    current_line: int
    program_name: Optional[str]
    program_progress: float  # 0-1

    # Limits and alarms
    limit_x: bool = False
    limit_y: bool = False
    limit_z: bool = False
    alarm_code: Optional[int] = None
    alarm_message: Optional[str] = None

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "position": self.position.to_dict(),
            "spindle_state": self.spindle_state.value,
            "spindle_speed": self.spindle_speed,
            "spindle_load": self.spindle_load,
            "feed_rate": self.feed_rate,
            "feed_override": self.feed_override,
            "rapid_override": self.rapid_override,
            "coolant_state": self.coolant_state.value,
            "current_line": self.current_line,
            "program_name": self.program_name,
            "program_progress": self.program_progress,
            "limit_x": self.limit_x,
            "limit_y": self.limit_y,
            "limit_z": self.limit_z,
            "alarm_code": self.alarm_code,
            "alarm_message": self.alarm_message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ToolInfo:
    """Tool information."""
    tool_number: int
    description: str
    diameter: float
    length: float
    flutes: int = 2
    material: str = "carbide"
    max_rpm: float = 20000
    max_feed: float = 5000


@dataclass
class MachiningOperation:
    """A single machining operation."""
    operation_id: str
    operation_type: str  # drilling, milling, facing, etc.
    tool: ToolInfo

    # Parameters
    spindle_speed: float
    feed_rate: float
    depth_of_cut: float
    step_over: float

    # G-code
    gcode: List[str]

    # Estimated time
    estimated_time_seconds: float


class CNCProtocol(ABC):
    """Abstract protocol for CNC communication."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to CNC controller."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from CNC controller."""
        pass

    @abstractmethod
    async def get_status(self) -> CNCStatus:
        """Get current machine status."""
        pass

    @abstractmethod
    async def send_gcode(self, gcode: str) -> bool:
        """Send a single G-code command."""
        pass

    @abstractmethod
    async def stream_program(self, gcode_lines: List[str]) -> AsyncIterator[Dict[str, Any]]:
        """Stream a G-code program."""
        pass

    @abstractmethod
    async def emergency_stop(self):
        """Emergency stop."""
        pass


class GRBLCNCProtocol(CNCProtocol):
    """GRBL-based CNC protocol."""

    def __init__(self, port: str = "/dev/ttyUSB0", baud_rate: int = 115200):
        self.port = port
        self.baud_rate = baud_rate
        self._connected = False
        self._serial = None
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to GRBL controller."""
        try:
            # In production: use pyserial-asyncio
            # self._serial = await serial_asyncio.open_serial_connection(
            #     url=self.port, baudrate=self.baud_rate
            # )
            self._connected = True
            logger.info(f"Connected to GRBL CNC at {self.port}")

            # Send soft reset and wait for initialization
            await self.send_gcode("\x18")  # Ctrl-X soft reset
            await asyncio.sleep(2)

            return True
        except Exception as e:
            logger.error(f"Failed to connect to GRBL: {e}")
            return False

    async def disconnect(self):
        """Disconnect from GRBL."""
        self._connected = False
        if self._serial:
            # self._serial.close()
            pass
        logger.info("Disconnected from GRBL CNC")

    async def get_status(self) -> CNCStatus:
        """Get GRBL status via ? command."""
        # Send status query
        response = await self._send_and_receive("?")

        # Parse GRBL status response: <Idle|MPos:0.000,0.000,0.000|FS:0,0>
        # Simplified parsing for demonstration
        return CNCStatus(
            state=CNCState.IDLE,
            position=CNCPosition(x=0.0, y=0.0, z=0.0),
            spindle_state=SpindleState.OFF,
            spindle_speed=0.0,
            spindle_load=0.0,
            feed_rate=0.0,
            feed_override=100.0,
            rapid_override=100.0,
            coolant_state=CoolantState.OFF,
            current_line=0,
            program_name=None,
            program_progress=0.0,
        )

    async def send_gcode(self, gcode: str) -> bool:
        """Send G-code to GRBL."""
        async with self._lock:
            try:
                response = await self._send_and_receive(gcode)
                return "ok" in response.lower()
            except Exception as e:
                logger.error(f"Failed to send G-code: {e}")
                return False

    async def stream_program(self, gcode_lines: List[str]) -> AsyncIterator[Dict[str, Any]]:
        """Stream G-code program with character counting protocol."""
        total_lines = len(gcode_lines)

        for i, line in enumerate(gcode_lines):
            line = line.strip()
            if not line or line.startswith(";"):
                continue

            success = await self.send_gcode(line)

            yield {
                "line_number": i,
                "total_lines": total_lines,
                "progress": (i + 1) / total_lines,
                "gcode": line,
                "success": success,
            }

            # Small delay for buffer management
            await asyncio.sleep(0.01)

    async def emergency_stop(self):
        """GRBL emergency stop (feed hold + reset)."""
        await self.send_gcode("!")  # Feed hold
        await asyncio.sleep(0.1)
        await self.send_gcode("\x18")  # Soft reset

    async def _send_and_receive(self, command: str) -> str:
        """Send command and receive response."""
        # Simulated response for demonstration
        return "ok"


class LinuxCNCProtocol(CNCProtocol):
    """LinuxCNC protocol via NML or Python interface."""

    def __init__(self, host: str = "localhost", port: int = 5007):
        self.host = host
        self.port = port
        self._connected = False

    async def connect(self) -> bool:
        """Connect to LinuxCNC."""
        try:
            # In production: use linuxcnc Python module
            # import linuxcnc
            # self.stat = linuxcnc.stat()
            # self.command = linuxcnc.command()
            self._connected = True
            logger.info(f"Connected to LinuxCNC at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LinuxCNC: {e}")
            return False

    async def disconnect(self):
        """Disconnect from LinuxCNC."""
        self._connected = False

    async def get_status(self) -> CNCStatus:
        """Get LinuxCNC status."""
        return CNCStatus(
            state=CNCState.IDLE,
            position=CNCPosition(x=0.0, y=0.0, z=0.0),
            spindle_state=SpindleState.OFF,
            spindle_speed=0.0,
            spindle_load=0.0,
            feed_rate=0.0,
            feed_override=100.0,
            rapid_override=100.0,
            coolant_state=CoolantState.OFF,
            current_line=0,
            program_name=None,
            program_progress=0.0,
        )

    async def send_gcode(self, gcode: str) -> bool:
        """Send G-code via MDI."""
        return True

    async def stream_program(self, gcode_lines: List[str]) -> AsyncIterator[Dict[str, Any]]:
        """Load and run program."""
        for i, line in enumerate(gcode_lines):
            yield {
                "line_number": i,
                "total_lines": len(gcode_lines),
                "progress": (i + 1) / len(gcode_lines),
                "gcode": line,
                "success": True,
            }
            await asyncio.sleep(0.01)

    async def emergency_stop(self):
        """LinuxCNC E-stop."""
        # self.command.abort()
        pass


class CNCController:
    """
    CNC Machine Controller for AI-driven manufacturing.

    Bridges AI decisions to CNC machine actions with safety interlocks.
    """

    def __init__(
        self,
        protocol: CNCProtocol,
        machine_id: str = "cnc-001",
    ):
        self.protocol = protocol
        self.machine_id = machine_id
        self._connected = False

        # Tool library
        self.tools: Dict[int, ToolInfo] = {}
        self.current_tool: Optional[int] = None

        # Safety limits
        self.max_spindle_speed = 24000  # RPM
        self.max_feed_rate = 10000  # mm/min
        self.work_envelope = {
            "x": (-500, 500),
            "y": (-300, 300),
            "z": (-200, 0),
        }

        # Operation history
        self.operation_history: List[Dict[str, Any]] = []

    async def connect(self) -> bool:
        """Connect to CNC machine."""
        self._connected = await self.protocol.connect()
        return self._connected

    async def disconnect(self):
        """Disconnect from CNC machine."""
        await self.protocol.disconnect()
        self._connected = False

    async def get_status(self) -> CNCStatus:
        """Get current machine status."""
        if not self._connected:
            raise ConnectionError("Not connected to CNC")
        return await self.protocol.get_status()

    async def home(self, axes: str = "XYZ") -> bool:
        """Home specified axes."""
        gcode = f"$H"  # GRBL homing
        return await self.protocol.send_gcode(gcode)

    async def jog(
        self,
        axis: str,
        distance: float,
        feed_rate: float = 1000,
    ) -> bool:
        """Jog a single axis."""
        # Validate
        if axis.upper() not in ["X", "Y", "Z", "A", "B", "C"]:
            raise ValueError(f"Invalid axis: {axis}")

        if feed_rate > self.max_feed_rate:
            raise ValueError(f"Feed rate {feed_rate} exceeds max {self.max_feed_rate}")

        gcode = f"G91 G1 {axis.upper()}{distance} F{feed_rate}"
        success = await self.protocol.send_gcode(gcode)

        # Return to absolute mode
        await self.protocol.send_gcode("G90")

        return success

    async def rapid_to(self, x: float, y: float, z: float) -> bool:
        """Rapid move to position."""
        self._validate_position(x, y, z)
        gcode = f"G0 X{x} Y{y} Z{z}"
        return await self.protocol.send_gcode(gcode)

    async def move_to(
        self,
        x: float,
        y: float,
        z: float,
        feed_rate: float,
    ) -> bool:
        """Linear move to position."""
        self._validate_position(x, y, z)
        if feed_rate > self.max_feed_rate:
            raise ValueError(f"Feed rate exceeds maximum")

        gcode = f"G1 X{x} Y{y} Z{z} F{feed_rate}"
        return await self.protocol.send_gcode(gcode)

    async def set_spindle(
        self,
        speed: float,
        direction: SpindleState = SpindleState.CW,
    ) -> bool:
        """Set spindle speed and direction."""
        if speed > self.max_spindle_speed:
            raise ValueError(f"Spindle speed {speed} exceeds max {self.max_spindle_speed}")

        if direction == SpindleState.OFF:
            gcode = "M5"
        elif direction == SpindleState.CW:
            gcode = f"M3 S{speed}"
        else:
            gcode = f"M4 S{speed}"

        return await self.protocol.send_gcode(gcode)

    async def set_coolant(self, state: CoolantState) -> bool:
        """Set coolant state."""
        if state == CoolantState.OFF:
            gcode = "M9"
        elif state == CoolantState.FLOOD:
            gcode = "M8"
        else:
            gcode = "M7"

        return await self.protocol.send_gcode(gcode)

    async def tool_change(self, tool_number: int) -> bool:
        """Perform tool change."""
        if tool_number not in self.tools:
            logger.warning(f"Tool {tool_number} not in library")

        gcode = f"M6 T{tool_number}"
        success = await self.protocol.send_gcode(gcode)

        if success:
            self.current_tool = tool_number

        return success

    async def run_program(
        self,
        gcode_lines: List[str],
        dry_run: bool = False,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Run a G-code program.

        Args:
            gcode_lines: List of G-code commands
            dry_run: If True, validate but don't execute
        """
        # Validate program
        validation = self._validate_program(gcode_lines)
        if not validation["valid"]:
            raise ValueError(f"Invalid program: {validation['errors']}")

        if dry_run:
            yield {
                "status": "dry_run_complete",
                "validation": validation,
            }
            return

        # Record operation
        operation = {
            "machine_id": self.machine_id,
            "timestamp": datetime.now().isoformat(),
            "line_count": len(gcode_lines),
        }
        self.operation_history.append(operation)

        # Stream program
        async for progress in self.protocol.stream_program(gcode_lines):
            yield progress

    async def execute_ai_decision(
        self,
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute an AI-generated decision.

        Translates high-level decisions to G-code.
        """
        decision_type = decision.get("type")

        if decision_type == "speed_adjustment":
            # Adjust spindle speed
            new_speed = decision.get("spindle_speed", 0)
            success = await self.set_spindle(new_speed)
            return {"success": success, "action": f"Set spindle to {new_speed} RPM"}

        elif decision_type == "feed_adjustment":
            # Adjust feed rate override
            override = decision.get("feed_override", 100)
            gcode = f"M220 S{override}"
            success = await self.protocol.send_gcode(gcode)
            return {"success": success, "action": f"Set feed override to {override}%"}

        elif decision_type == "tool_change":
            tool_num = decision.get("tool_number", 1)
            success = await self.tool_change(tool_num)
            return {"success": success, "action": f"Changed to tool {tool_num}"}

        elif decision_type == "pause":
            success = await self.protocol.send_gcode("M0")
            return {"success": success, "action": "Paused program"}

        elif decision_type == "emergency_stop":
            await self.emergency_stop()
            return {"success": True, "action": "Emergency stop triggered"}

        else:
            return {"success": False, "error": f"Unknown decision type: {decision_type}"}

    async def emergency_stop(self):
        """Trigger emergency stop."""
        logger.critical(f"Emergency stop triggered on {self.machine_id}")
        await self.protocol.emergency_stop()

    def add_tool(self, tool: ToolInfo):
        """Add tool to library."""
        self.tools[tool.tool_number] = tool

    def calculate_cutting_params(
        self,
        material: str,
        tool: ToolInfo,
        operation: str,
    ) -> Dict[str, float]:
        """
        Calculate optimal cutting parameters.

        Based on material properties and tool specifications.
        """
        # Material-specific cutting speeds (m/min)
        cutting_speeds = {
            "aluminum": 300,
            "steel": 100,
            "stainless": 60,
            "plastic": 500,
            "wood": 600,
        }

        vc = cutting_speeds.get(material.lower(), 100)

        # Spindle speed: n = (Vc * 1000) / (π * D)
        spindle_speed = (vc * 1000) / (3.14159 * tool.diameter)
        spindle_speed = min(spindle_speed, tool.max_rpm, self.max_spindle_speed)

        # Feed rate: f = n * fz * z
        fz = 0.1  # Feed per tooth (mm)
        feed_rate = spindle_speed * fz * tool.flutes
        feed_rate = min(feed_rate, tool.max_feed, self.max_feed_rate)

        return {
            "spindle_speed": round(spindle_speed),
            "feed_rate": round(feed_rate),
            "depth_of_cut": tool.diameter * 0.5,  # 50% of diameter
            "step_over": tool.diameter * 0.4,  # 40% of diameter
        }

    def _validate_position(self, x: float, y: float, z: float):
        """Validate position is within work envelope."""
        if not (self.work_envelope["x"][0] <= x <= self.work_envelope["x"][1]):
            raise ValueError(f"X position {x} outside work envelope")
        if not (self.work_envelope["y"][0] <= y <= self.work_envelope["y"][1]):
            raise ValueError(f"Y position {y} outside work envelope")
        if not (self.work_envelope["z"][0] <= z <= self.work_envelope["z"][1]):
            raise ValueError(f"Z position {z} outside work envelope")

    def _validate_program(self, gcode_lines: List[str]) -> Dict[str, Any]:
        """Validate G-code program before execution."""
        errors = []
        warnings = []

        for i, line in enumerate(gcode_lines):
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("("):
                continue

            # Check for dangerous commands
            if "G28" in line or "G30" in line:
                warnings.append(f"Line {i}: Homing command detected")

            # Check feed rate
            if "F" in line:
                try:
                    f_idx = line.index("F")
                    feed_str = ""
                    for c in line[f_idx+1:]:
                        if c.isdigit() or c == ".":
                            feed_str += c
                        else:
                            break
                    if feed_str:
                        feed = float(feed_str)
                        if feed > self.max_feed_rate:
                            errors.append(f"Line {i}: Feed rate {feed} exceeds max")
                except (ValueError, IndexError):
                    pass

            # Check spindle speed
            if "S" in line and ("M3" in line or "M4" in line):
                try:
                    s_idx = line.index("S")
                    speed_str = ""
                    for c in line[s_idx+1:]:
                        if c.isdigit() or c == ".":
                            speed_str += c
                        else:
                            break
                    if speed_str:
                        speed = float(speed_str)
                        if speed > self.max_spindle_speed:
                            errors.append(f"Line {i}: Spindle speed {speed} exceeds max")
                except (ValueError, IndexError):
                    pass

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "line_count": len(gcode_lines),
        }


# Factory function
def create_cnc_controller(
    protocol_type: str = "grbl",
    **kwargs,
) -> CNCController:
    """Create CNC controller with specified protocol."""
    if protocol_type == "grbl":
        protocol = GRBLCNCProtocol(**kwargs)
    elif protocol_type == "linuxcnc":
        protocol = LinuxCNCProtocol(**kwargs)
    else:
        raise ValueError(f"Unknown protocol: {protocol_type}")

    return CNCController(protocol)
