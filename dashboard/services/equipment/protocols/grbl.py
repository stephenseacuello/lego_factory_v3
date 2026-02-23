"""
GRBL Protocol - GRBL-based CNC/3D printer controller adapter.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import asyncio
import re

logger = logging.getLogger(__name__)


class GRBLState(Enum):
    """GRBL machine states."""
    IDLE = "Idle"
    RUN = "Run"
    HOLD = "Hold"
    JOG = "Jog"
    ALARM = "Alarm"
    DOOR = "Door"
    CHECK = "Check"
    HOME = "Home"
    SLEEP = "Sleep"


@dataclass
class GRBLPosition:
    """Machine position."""
    x: float
    y: float
    z: float
    # Optional axes
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None


@dataclass
class GRBLStatus:
    """GRBL machine status."""
    state: GRBLState
    machine_position: GRBLPosition
    work_position: GRBLPosition
    feed_rate: float
    spindle_speed: float
    buffer_planner: int
    buffer_rx: int
    overrides: Tuple[int, int, int]  # feed, rapid, spindle %
    pins: Dict[str, bool]


class GRBLProtocol:
    """
    GRBL serial protocol adapter.

    Communicates with GRBL-based controllers via serial port.
    Supports GRBL 1.1+ protocol for CNC mills, laser cutters,
    and some 3D printer controllers (Marlin G-code compatible mode).
    """

    # Status regex pattern
    STATUS_PATTERN = re.compile(
        r"<(\w+)\|"
        r"MPos:([^|]+)\|"
        r"(?:WPos:([^|]+)\|)?"
        r"(?:FS:(\d+),(\d+)\|)?"
        r"(?:Bf:(\d+),(\d+)\|)?"
        r"(?:Ov:(\d+),(\d+),(\d+)\|)?"
        r"(?:Pn:([^>]+))?"
        r">"
    )

    def __init__(self,
                 port: str = "/dev/ttyUSB0",
                 baud_rate: int = 115200,
                 timeout: float = 1.0):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._serial = None
        self._connected = False
        self._status: Optional[GRBLStatus] = None
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Connect to GRBL controller via serial port."""
        try:
            # In production, use pyserial-asyncio
            # import serial_asyncio
            # self._serial, _ = await serial_asyncio.open_serial_connection(
            #     url=self.port,
            #     baudrate=self.baud_rate
            # )

            logger.info(f"Connecting to GRBL at {self.port}")

            # Simulated connection for demonstration
            self._connected = True

            # Send soft reset and wait for welcome message
            await self._send_raw("\x18")  # Ctrl-X
            await asyncio.sleep(2)  # Wait for GRBL startup

            # Request initial status
            await self.get_status()

            logger.info("Connected to GRBL controller")
            return True

        except Exception as e:
            logger.error(f"GRBL connection error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from GRBL controller."""
        if self._read_task:
            self._read_task.cancel()

        if self._serial:
            # Close serial connection
            pass

        self._connected = False
        logger.info("Disconnected from GRBL controller")

    async def _send_raw(self, data: str) -> None:
        """Send raw data to serial port."""
        if self._serial:
            # self._serial.write(data.encode())
            pass
        logger.debug(f"GRBL TX: {repr(data)}")

    async def send_gcode(self, commands: List[str]) -> str:
        """Send G-code commands to controller."""
        if not self._connected:
            raise ConnectionError("Not connected to GRBL")

        responses = []

        for cmd in commands:
            cmd = cmd.strip()
            if not cmd or cmd.startswith(';'):
                continue

            try:
                response = await self._send_command(cmd)
                responses.append(response)

                if response != "ok":
                    return f"Error on '{cmd}': {response}"

            except Exception as e:
                return f"Error: {str(e)}"

        return "OK" if all(r == "ok" for r in responses) else "\n".join(responses)

    async def _send_command(self, command: str, timeout: float = 5.0) -> str:
        """Send single command and wait for response."""
        await self._send_raw(f"{command}\n")

        # Wait for response (ok or error)
        try:
            # Simulated response for demonstration
            await asyncio.sleep(0.01)
            return "ok"

        except asyncio.TimeoutError:
            return "timeout"

    async def get_status(self) -> GRBLStatus:
        """Query real-time status."""
        if not self._connected:
            return GRBLStatus(
                state=GRBLState.ALARM,
                machine_position=GRBLPosition(0, 0, 0),
                work_position=GRBLPosition(0, 0, 0),
                feed_rate=0, spindle_speed=0,
                buffer_planner=0, buffer_rx=0,
                overrides=(100, 100, 100),
                pins={}
            )

        # Send status query (?)
        await self._send_raw("?")

        # Parse response
        # Simulated status for demonstration
        self._status = GRBLStatus(
            state=GRBLState.IDLE,
            machine_position=GRBLPosition(100.0, 100.0, 50.0),
            work_position=GRBLPosition(0.0, 0.0, 0.0),
            feed_rate=3000.0,
            spindle_speed=0,
            buffer_planner=15,
            buffer_rx=127,
            overrides=(100, 100, 100),
            pins={"X": False, "Y": False, "Z": False, "P": False}
        )

        return self._status

    def _parse_status(self, response: str) -> Optional[GRBLStatus]:
        """Parse GRBL status response."""
        match = self.STATUS_PATTERN.match(response)
        if not match:
            return None

        groups = match.groups()

        # Parse state
        state = GRBLState(groups[0])

        # Parse machine position
        mpos_parts = [float(x) for x in groups[1].split(",")]
        machine_pos = GRBLPosition(*mpos_parts[:3])

        # Parse work position if available
        if groups[2]:
            wpos_parts = [float(x) for x in groups[2].split(",")]
            work_pos = GRBLPosition(*wpos_parts[:3])
        else:
            work_pos = machine_pos

        # Parse feed/speed
        feed_rate = float(groups[3]) if groups[3] else 0
        spindle_speed = float(groups[4]) if groups[4] else 0

        # Parse buffer
        buffer_planner = int(groups[5]) if groups[5] else 0
        buffer_rx = int(groups[6]) if groups[6] else 0

        # Parse overrides
        if groups[7]:
            overrides = (int(groups[7]), int(groups[8]), int(groups[9]))
        else:
            overrides = (100, 100, 100)

        # Parse pins
        pins = {}
        if groups[10]:
            for pin in groups[10]:
                pins[pin] = True

        return GRBLStatus(
            state=state,
            machine_position=machine_pos,
            work_position=work_pos,
            feed_rate=feed_rate,
            spindle_speed=spindle_speed,
            buffer_planner=buffer_planner,
            buffer_rx=buffer_rx,
            overrides=overrides,
            pins=pins
        )

    async def home(self, axes: str = "XYZ") -> bool:
        """Home specified axes."""
        # GRBL uses $H for homing
        result = await self.send_gcode(["$H"])
        return result == "OK"

    async def unlock(self) -> bool:
        """Unlock alarm state."""
        result = await self.send_gcode(["$X"])
        return result == "OK"

    async def soft_reset(self) -> None:
        """Perform soft reset."""
        await self._send_raw("\x18")
        await asyncio.sleep(2)

    async def feed_hold(self) -> None:
        """Feed hold (pause motion)."""
        await self._send_raw("!")

    async def cycle_start(self) -> None:
        """Resume from feed hold."""
        await self._send_raw("~")

    async def jog(self,
                  x: Optional[float] = None,
                  y: Optional[float] = None,
                  z: Optional[float] = None,
                  feed_rate: float = 1000,
                  incremental: bool = True) -> bool:
        """Jog to position."""
        parts = []

        if incremental:
            parts.append("G91")
        else:
            parts.append("G90")

        if x is not None:
            parts.append(f"X{x:.3f}")
        if y is not None:
            parts.append(f"Y{y:.3f}")
        if z is not None:
            parts.append(f"Z{z:.3f}")

        if len(parts) <= 1:
            return False

        parts.append(f"F{feed_rate}")

        # GRBL jog command format: $J=G91 X10 Y10 F1000
        jog_cmd = f"$J={' '.join(parts)}"

        result = await self.send_gcode([jog_cmd])
        return result == "OK"

    async def cancel_jog(self) -> None:
        """Cancel jog motion."""
        await self._send_raw("\x85")  # Jog cancel

    async def set_position(self,
                          x: Optional[float] = None,
                          y: Optional[float] = None,
                          z: Optional[float] = None) -> bool:
        """Set work coordinate offset."""
        parts = ["G92"]

        if x is not None:
            parts.append(f"X{x:.3f}")
        if y is not None:
            parts.append(f"Y{y:.3f}")
        if z is not None:
            parts.append(f"Z{z:.3f}")

        if len(parts) <= 1:
            return False

        result = await self.send_gcode([" ".join(parts)])
        return result == "OK"

    async def get_settings(self) -> Dict[str, float]:
        """Get GRBL settings."""
        await self._send_raw("$$\n")

        # Parse settings response
        # Format: $0=10 (step pulse microseconds)
        settings = {}

        # Simulated settings for demonstration
        settings = {
            "$0": 10,    # Step pulse, microseconds
            "$1": 25,    # Step idle delay, msec
            "$2": 0,     # Step port invert, mask
            "$3": 0,     # Direction port invert, mask
            "$4": 0,     # Step enable invert
            "$5": 0,     # Limit pins invert
            "$6": 0,     # Probe pin invert
            "$10": 1,    # Status report
            "$11": 0.01, # Junction deviation, mm
            "$12": 0.002,# Arc tolerance, mm
            "$13": 0,    # Report inches
            "$20": 0,    # Soft limits
            "$21": 0,    # Hard limits
            "$22": 1,    # Homing cycle
            "$23": 0,    # Homing dir invert
            "$24": 25.0, # Homing feed, mm/min
            "$25": 500.0,# Homing seek, mm/min
            "$26": 250,  # Homing debounce, msec
            "$27": 1.0,  # Homing pull-off, mm
            "$30": 1000, # Max spindle speed, RPM
            "$31": 0,    # Min spindle speed
            "$32": 0,    # Laser mode
            "$100": 250.0,# X steps/mm
            "$101": 250.0,# Y steps/mm
            "$102": 250.0,# Z steps/mm
            "$110": 5000.0,# X Max rate, mm/min
            "$111": 5000.0,# Y Max rate
            "$112": 2000.0,# Z Max rate
            "$120": 200.0,# X Acceleration, mm/sec^2
            "$121": 200.0,# Y Acceleration
            "$122": 100.0,# Z Acceleration
            "$130": 200.0,# X Max travel, mm
            "$131": 200.0,# Y Max travel
            "$132": 200.0,# Z Max travel
        }

        return settings

    async def set_setting(self, setting: int, value: float) -> bool:
        """Set GRBL setting."""
        result = await self.send_gcode([f"${setting}={value}"])
        return result == "OK"

    async def set_feed_override(self, percentage: int) -> None:
        """Set feed rate override (10-200%)."""
        percentage = max(10, min(200, percentage))

        if percentage > 100:
            # Increase: 0x91-0x9A for +1% to +10%
            steps = percentage - 100
            while steps > 0:
                await self._send_raw(chr(0x91 + min(steps - 1, 9)))
                steps -= 10
        elif percentage < 100:
            # Decrease: 0x92-0x9B for -1% to -10%
            steps = 100 - percentage
            while steps > 0:
                await self._send_raw(chr(0x92 + min(steps - 1, 9)))
                steps -= 10

    async def set_spindle_override(self, percentage: int) -> None:
        """Set spindle speed override (10-200%)."""
        percentage = max(10, min(200, percentage))

        if percentage > 100:
            steps = percentage - 100
            while steps > 0:
                await self._send_raw(chr(0x9C + min(steps - 1, 9)))
                steps -= 10
        elif percentage < 100:
            steps = 100 - percentage
            while steps > 0:
                await self._send_raw(chr(0x9D + min(steps - 1, 9)))
                steps -= 10

    async def spindle_on(self, speed: int, clockwise: bool = True) -> bool:
        """Turn spindle on."""
        direction = "M3" if clockwise else "M4"
        result = await self.send_gcode([f"{direction} S{speed}"])
        return result == "OK"

    async def spindle_off(self) -> bool:
        """Turn spindle off."""
        result = await self.send_gcode(["M5"])
        return result == "OK"

    async def coolant_on(self, mist: bool = False) -> bool:
        """Turn coolant on."""
        cmd = "M7" if mist else "M8"  # M7=mist, M8=flood
        result = await self.send_gcode([cmd])
        return result == "OK"

    async def coolant_off(self) -> bool:
        """Turn coolant off."""
        result = await self.send_gcode(["M9"])
        return result == "OK"

    async def probe(self,
                   z_target: float = -50,
                   feed_rate: float = 100) -> Optional[float]:
        """Run probe cycle, return Z position where triggered."""
        result = await self.send_gcode([f"G38.2 Z{z_target} F{feed_rate}"])

        if result == "OK":
            status = await self.get_status()
            return status.machine_position.z

        return None
