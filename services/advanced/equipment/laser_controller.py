"""
Laser Engraver Controller - GRBL laser mode integration.

Supports:
- GRBL with laser mode ($32=1)
- LightBurn compatible machines
- Diode lasers and CO2 lasers
- Power/speed control and safety interlocks
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from .base_controller import (
    BaseEquipmentController,
    EquipmentState,
    EquipmentStatus,
    JobStatus,
    JobResult
)
from .mill_controller import GrblState, GrblStatus

logger = logging.getLogger(__name__)


class LaserMode(Enum):
    """Laser operating modes."""
    OFF = "off"
    CONSTANT = "constant"  # M3 - constant power
    DYNAMIC = "dynamic"    # M4 - dynamic power (varies with speed)


@dataclass
class LaserSafetyState:
    """Laser safety interlock state."""
    lid_closed: bool = True
    enclosure_ok: bool = True
    water_flow_ok: bool = True  # For CO2 lasers
    exhaust_ok: bool = True
    emergency_stop: bool = False

    @property
    def safe_to_fire(self) -> bool:
        """Check if all safety interlocks are satisfied."""
        return (
            self.lid_closed and
            self.enclosure_ok and
            self.water_flow_ok and
            self.exhaust_ok and
            not self.emergency_stop
        )


class LaserController(BaseEquipmentController):
    """
    Laser Engraver Controller with GRBL laser mode support.

    Connection info structure:
    {
        "connection_type": "serial",  # or "network"
        "port": "/dev/ttyUSB0",
        "host": "192.168.1.100",
        "network_port": 8080,
        "baud_rate": 115200,
        "laser_type": "diode",  # or "co2"
        "max_power": 5000,      # Max S value (mW for diode, % for CO2)
        "has_air_assist": true,
        "has_rotary": false
    }
    """

    # GRBL status pattern (same as mill)
    GRBL_STATUS_PATTERN = __import__('re').compile(
        r"<(\w+)\|"
        r"MPos:([-\d.]+),([-\d.]+),([-\d.]+)\|"
        r"WPos:([-\d.]+),([-\d.]+),([-\d.]+)"
        r"(?:\|Bf:(\d+),(\d+))?"
        r"(?:\|Ln:(\d+))?"
        r"(?:\|FS:(\d+),(\d+))?"
        r"(?:\|Pn:(\w+))?"
        r">"
    )

    def __init__(
        self,
        work_center_id: str,
        name: str,
        connection_info: Dict[str, Any]
    ):
        super().__init__(work_center_id, name, connection_info)
        self.connection_type = connection_info.get('connection_type', 'serial')
        self.laser_type = connection_info.get('laser_type', 'diode')
        self.max_power = connection_info.get('max_power', 1000)
        self.has_air_assist = connection_info.get('has_air_assist', False)
        self.has_rotary = connection_info.get('has_rotary', False)

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._current_job_id: Optional[str] = None
        self._job_start_time: Optional[datetime] = None
        self._job_lines_total: int = 0
        self._job_lines_sent: int = 0
        self._gcode_queue: List[str] = []
        self._streaming: bool = False
        self._laser_mode: LaserMode = LaserMode.OFF
        self._current_power: float = 0
        self._safety_state = LaserSafetyState()

    async def connect(self) -> bool:
        """Establish connection to laser engraver."""
        try:
            if self.connection_type == 'serial':
                return await self._connect_serial()
            else:
                return await self._connect_network()

        except Exception as e:
            logger.error(f"Failed to connect to {self.name}: {e}")
            self._connected = False
            return False

    async def _connect_serial(self) -> bool:
        """Connect via serial port."""
        try:
            import serial_asyncio

            port = self.connection_info.get('port', '/dev/ttyUSB0')
            baud = self.connection_info.get('baud_rate', 115200)

            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=port,
                baudrate=baud
            )

            # Wait for GRBL startup
            await asyncio.sleep(2)

            # Clear startup messages
            while True:
                try:
                    line = await asyncio.wait_for(
                        self._reader.readline(),
                        timeout=0.5
                    )
                    line = line.decode().strip()
                    if 'Grbl' in line:
                        logger.info(f"GRBL version: {line}")
                except asyncio.TimeoutError:
                    break

            # Verify laser mode is enabled
            await self._verify_laser_mode()

            self._connected = True
            logger.info(f"Connected to laser via serial: {port}")
            return True

        except ImportError:
            logger.error("pyserial-asyncio not installed")
            return False
        except Exception as e:
            logger.error(f"Serial connection failed: {e}")
            return False

    async def _connect_network(self) -> bool:
        """Connect via network."""
        try:
            host = self.connection_info.get('host', 'localhost')
            port = self.connection_info.get('network_port', 8080)

            self._reader, self._writer = await asyncio.open_connection(host, port)
            await asyncio.sleep(1)

            await self._verify_laser_mode()

            self._connected = True
            logger.info(f"Connected to laser via network: {host}:{port}")
            return True

        except Exception as e:
            logger.error(f"Network connection failed: {e}")
            return False

    async def _verify_laser_mode(self):
        """Verify GRBL laser mode is enabled ($32=1)."""
        try:
            self._writer.write(b'$$\n')
            await self._writer.drain()

            laser_mode_enabled = False
            while True:
                try:
                    line = await asyncio.wait_for(
                        self._reader.readline(),
                        timeout=0.5
                    )
                    line = line.decode().strip()
                    if line == 'ok':
                        break
                    if '$32=1' in line:
                        laser_mode_enabled = True
                except asyncio.TimeoutError:
                    break

            if not laser_mode_enabled:
                logger.warning("GRBL laser mode not enabled. Send $32=1 to enable.")

        except Exception as e:
            logger.debug(f"Could not verify laser mode: {e}")

    async def disconnect(self):
        """Disconnect from laser engraver."""
        # Turn off laser before disconnecting
        await self.set_laser_power(0)

        self._streaming = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._connected = False
        logger.info(f"Disconnected from laser: {self.name}")

    async def ping(self) -> bool:
        """Check if laser is responsive."""
        if not self._connected or not self._writer:
            return False

        try:
            self._writer.write(b'?')
            await self._writer.drain()

            response = await asyncio.wait_for(
                self._reader.readline(),
                timeout=2.0
            )
            return b'<' in response

        except Exception:
            return False

    async def _send_command(self, command: str, wait_ok: bool = True) -> tuple:
        """Send G-code command to laser."""
        if not self._connected or not self._writer:
            return False, "Not connected"

        try:
            cmd = command.strip() + '\n'
            self._writer.write(cmd.encode())
            await self._writer.drain()

            if not wait_ok:
                return True, ""

            response = await asyncio.wait_for(
                self._reader.readline(),
                timeout=30.0
            )
            response = response.decode().strip()

            if response == 'ok':
                return True, response

            if response.startswith('error'):
                return False, response

            return True, response

        except asyncio.TimeoutError:
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)

    async def _query_status(self) -> Optional[GrblStatus]:
        """Query GRBL status."""
        if not self._connected or not self._writer:
            return None

        try:
            self._writer.write(b'?')
            await self._writer.drain()

            response = await asyncio.wait_for(
                self._reader.readline(),
                timeout=2.0
            )
            response = response.decode().strip()

            match = self.GRBL_STATUS_PATTERN.match(response)
            if not match:
                return None

            groups = match.groups()
            try:
                state = GrblState(groups[0])
            except ValueError:
                state = GrblState.IDLE

            return GrblStatus(
                state=state,
                machine_position={
                    'x': float(groups[1]),
                    'y': float(groups[2]),
                    'z': float(groups[3]) if groups[3] else 0
                },
                work_position={
                    'x': float(groups[4]),
                    'y': float(groups[5]),
                    'z': float(groups[6]) if groups[6] else 0
                },
                buffer_blocks=int(groups[7]) if groups[7] else 0,
                buffer_chars=int(groups[8]) if groups[8] else 0,
                line_number=int(groups[9]) if groups[9] else 0,
                feed_rate=float(groups[10]) if groups[10] else 0,
                spindle_speed=float(groups[11]) if groups[11] else 0,
                pins=groups[12] or ""
            )

        except Exception as e:
            logger.debug(f"Status query failed: {e}")
            return None

    # Status Monitoring

    async def get_state(self) -> EquipmentState:
        """Get current laser engraver state."""
        status = await self._query_status()
        if not status:
            return EquipmentState(status=EquipmentStatus.OFFLINE)

        # Map GRBL state
        status_map = {
            GrblState.IDLE: EquipmentStatus.IDLE,
            GrblState.RUN: EquipmentStatus.RUNNING,
            GrblState.HOLD: EquipmentStatus.PAUSED,
            GrblState.JOG: EquipmentStatus.RUNNING,
            GrblState.ALARM: EquipmentStatus.ERROR,
            GrblState.DOOR: EquipmentStatus.ERROR,
            GrblState.CHECK: EquipmentStatus.SETUP,
            GrblState.HOME: EquipmentStatus.SETUP,
            GrblState.SLEEP: EquipmentStatus.IDLE
        }

        eq_status = status_map.get(status.state, EquipmentStatus.OFFLINE)

        # Check safety interlocks
        if not self._safety_state.safe_to_fire:
            eq_status = EquipmentStatus.ERROR

        progress = 0.0
        if self._job_lines_total > 0:
            progress = (self._job_lines_sent / self._job_lines_total) * 100

        return EquipmentState(
            status=eq_status,
            current_job_id=self._current_job_id,
            job_progress_percent=progress,
            job_elapsed_seconds=(
                (datetime.utcnow() - self._job_start_time).total_seconds()
                if self._job_start_time else 0
            ),
            positions=status.work_position,
            speeds={
                'feed_rate': status.feed_rate,
                'laser_power': status.spindle_speed
            },
            extra_data={
                'grbl_state': status.state.value,
                'laser_mode': self._laser_mode.value,
                'laser_type': self.laser_type,
                'safety_state': {
                    'lid_closed': self._safety_state.lid_closed,
                    'enclosure_ok': self._safety_state.enclosure_ok,
                    'safe_to_fire': self._safety_state.safe_to_fire
                }
            }
        )

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get laser engraver capabilities."""
        return {
            'laser_type': self.laser_type,
            'max_power': self.max_power,
            'has_air_assist': self.has_air_assist,
            'has_rotary': self.has_rotary,
            'axes': ['X', 'Y'] + (['Z'] if self.laser_type == 'co2' else []),
            'supported_materials': self._get_supported_materials()
        }

    def _get_supported_materials(self) -> List[str]:
        """Get list of supported materials based on laser type."""
        if self.laser_type == 'co2':
            return [
                'wood', 'acrylic', 'leather', 'paper', 'cardboard',
                'fabric', 'cork', 'rubber', 'glass_engrave', 'stone_engrave'
            ]
        else:  # diode
            return [
                'wood', 'leather', 'paper', 'cardboard', 'fabric',
                'cork', 'anodized_aluminum', 'painted_metal', 'dark_plastics'
            ]

    # Job Control

    async def submit_job(
        self,
        job_id: str,
        file_path: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Load G-code file for laser engraving/cutting."""
        try:
            with open(file_path, 'r') as f:
                gcode = f.read()

            # Parse and validate G-code
            lines = []
            for line in gcode.split('\n'):
                line = line.split(';')[0].strip()
                line = line.split('(')[0].strip()
                if line:
                    # Safety check: limit power to max
                    if 'S' in line.upper():
                        line = self._limit_power_in_gcode(line)
                    lines.append(line)

            self._gcode_queue = lines
            self._job_lines_total = len(lines)
            self._job_lines_sent = 0
            self._current_job_id = job_id
            self._job_start_time = None

            logger.info(f"Loaded laser G-code: {len(lines)} lines")
            return True

        except Exception as e:
            logger.error(f"Failed to load G-code: {e}")
            return False

    def _limit_power_in_gcode(self, line: str) -> str:
        """Limit laser power in G-code line to max_power."""
        import re
        pattern = re.compile(r'S(\d+\.?\d*)')

        def replace_power(match):
            power = float(match.group(1))
            if power > self.max_power:
                logger.warning(f"Limiting power from {power} to {self.max_power}")
                power = self.max_power
            return f'S{power}'

        return pattern.sub(replace_power, line)

    async def start_job(self) -> bool:
        """Start laser engraving/cutting job."""
        if not self._gcode_queue:
            logger.error("No G-code loaded")
            return False

        if self._streaming:
            logger.warning("Already running")
            return False

        # Safety check
        if not self._safety_state.safe_to_fire:
            logger.error("Safety interlock not satisfied")
            return False

        self._job_start_time = datetime.utcnow()
        self._streaming = True

        # Enable air assist if available
        if self.has_air_assist:
            await self._send_command('M8')  # Coolant/air on

        asyncio.create_task(self._stream_gcode())

        logger.info(f"Started laser job: {self._current_job_id}")
        return True

    async def _stream_gcode(self):
        """Stream G-code to laser with flow control."""
        try:
            while self._streaming and self._job_lines_sent < self._job_lines_total:
                # Check safety before each line
                if not self._safety_state.safe_to_fire:
                    logger.error("Safety interlock triggered during job")
                    await self.set_laser_power(0)
                    self._streaming = False
                    break

                line = self._gcode_queue[self._job_lines_sent]

                success, response = await self._send_command(line)
                if not success:
                    logger.error(f"G-code error at line {self._job_lines_sent}: {response}")
                    await self.set_laser_power(0)
                    self._streaming = False
                    break

                self._job_lines_sent += 1
                await asyncio.sleep(0)

            if self._streaming:
                logger.info(f"Laser job completed: {self._current_job_id}")
                self._streaming = False

            # Turn off laser and air
            await self.set_laser_power(0)
            if self.has_air_assist:
                await self._send_command('M9')  # Air off

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            await self.set_laser_power(0)
            self._streaming = False

    async def pause_job(self) -> bool:
        """Pause laser operation."""
        try:
            # Turn off laser immediately
            await self.set_laser_power(0)

            # Feed hold
            self._writer.write(b'!')
            await self._writer.drain()
            self._streaming = False

            logger.info("Laser paused")
            return True

        except Exception as e:
            logger.error(f"Failed to pause: {e}")
            return False

    async def resume_job(self) -> bool:
        """Resume laser operation."""
        try:
            if not self._safety_state.safe_to_fire:
                logger.error("Cannot resume: safety interlock")
                return False

            # Cycle start
            self._writer.write(b'~')
            await self._writer.drain()

            if self._job_lines_sent < self._job_lines_total:
                self._streaming = True
                asyncio.create_task(self._stream_gcode())

            logger.info("Laser resumed")
            return True

        except Exception as e:
            logger.error(f"Failed to resume: {e}")
            return False

    async def cancel_job(self) -> bool:
        """Cancel laser operation."""
        try:
            # Turn off laser first
            await self.set_laser_power(0)

            self._streaming = False

            # Soft reset
            self._writer.write(b'\x18')
            await self._writer.drain()

            # Turn off air assist
            if self.has_air_assist:
                await asyncio.sleep(0.5)
                await self._send_command('M9')

            self._gcode_queue = []
            self._current_job_id = None

            logger.info("Laser job cancelled")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel: {e}")
            return False

    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get result of completed job."""
        return None

    # Equipment Control

    async def home(self) -> bool:
        """Home laser axes."""
        success, _ = await self._send_command('$H')
        return success

    async def emergency_stop(self) -> bool:
        """Emergency stop - turn off laser and halt motion."""
        try:
            self._streaming = False
            self._safety_state.emergency_stop = True

            # Turn off laser
            self._writer.write(b'M5\n')
            await self._writer.drain()

            # Soft reset
            self._writer.write(b'\x18')
            await self._writer.drain()

            logger.warning("LASER EMERGENCY STOP")
            return True

        except Exception as e:
            logger.error(f"E-stop failed: {e}")
            return False

    # Laser-specific methods

    async def set_laser_power(self, power: float, mode: LaserMode = LaserMode.DYNAMIC) -> bool:
        """
        Set laser power.

        Args:
            power: Power level (0 to max_power)
            mode: LaserMode.CONSTANT (M3) or LaserMode.DYNAMIC (M4)
        """
        power = max(0, min(power, self.max_power))

        if power == 0:
            cmd = 'M5'  # Laser off
            self._laser_mode = LaserMode.OFF
        elif mode == LaserMode.CONSTANT:
            cmd = f'M3 S{power}'
            self._laser_mode = LaserMode.CONSTANT
        else:
            cmd = f'M4 S{power}'
            self._laser_mode = LaserMode.DYNAMIC

        self._current_power = power
        success, _ = await self._send_command(cmd)
        return success

    async def test_fire(self, power: float = 10, duration_ms: int = 100) -> bool:
        """
        Fire laser briefly for alignment.

        Args:
            power: Power level (low for testing)
            duration_ms: Duration in milliseconds
        """
        if not self._safety_state.safe_to_fire:
            logger.error("Cannot test fire: safety interlock")
            return False

        power = min(power, self.max_power * 0.1)  # Max 10% for test

        await self.set_laser_power(power, LaserMode.CONSTANT)
        await asyncio.sleep(duration_ms / 1000.0)
        await self.set_laser_power(0)

        return True

    async def frame_job(self, speed: float = 1000) -> bool:
        """
        Trace the job boundary without firing laser.

        This moves the laser head around the bounding box of the loaded job.
        """
        if not self._gcode_queue:
            logger.error("No job loaded to frame")
            return False

        # Parse bounding box from G-code
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        import re
        coord_pattern = re.compile(r'[XY]([-\d.]+)')

        for line in self._gcode_queue:
            if 'G0' in line or 'G1' in line:
                for match in coord_pattern.finditer(line):
                    val = float(match.group(1))
                    axis = line[match.start()]
                    if axis == 'X':
                        min_x = min(min_x, val)
                        max_x = max(max_x, val)
                    elif axis == 'Y':
                        min_y = min(min_y, val)
                        max_y = max(max_y, val)

        if min_x == float('inf'):
            logger.error("Could not determine job bounds")
            return False

        # Trace rectangle
        frame_gcode = [
            f'G0 X{min_x} Y{min_y} F{speed}',
            f'G0 X{max_x} Y{min_y}',
            f'G0 X{max_x} Y{max_y}',
            f'G0 X{min_x} Y{max_y}',
            f'G0 X{min_x} Y{min_y}'
        ]

        for cmd in frame_gcode:
            success, _ = await self._send_command(cmd)
            if not success:
                return False

        logger.info(f"Framed job: ({min_x},{min_y}) to ({max_x},{max_y})")
        return True

    async def set_focus(self, z_height: float) -> bool:
        """Set laser focus height (Z axis if available)."""
        success, _ = await self._send_command(f'G0 Z{z_height} F500')
        return success

    async def jog(self, axis: str, distance: float, feed_rate: float = 1000) -> bool:
        """Jog laser head."""
        axis = axis.upper()
        if axis not in ['X', 'Y', 'Z']:
            return False

        cmd = f"$J=G91 {axis}{distance} F{feed_rate}"
        success, _ = await self._send_command(cmd)
        return success

    def update_safety_state(
        self,
        lid_closed: Optional[bool] = None,
        enclosure_ok: Optional[bool] = None,
        water_flow_ok: Optional[bool] = None,
        exhaust_ok: Optional[bool] = None
    ):
        """Update safety interlock state (called by external sensors)."""
        if lid_closed is not None:
            self._safety_state.lid_closed = lid_closed
        if enclosure_ok is not None:
            self._safety_state.enclosure_ok = enclosure_ok
        if water_flow_ok is not None:
            self._safety_state.water_flow_ok = water_flow_ok
        if exhaust_ok is not None:
            self._safety_state.exhaust_ok = exhaust_ok

        if not self._safety_state.safe_to_fire and self._streaming:
            logger.warning("Safety interlock triggered - stopping laser")
            asyncio.create_task(self.set_laser_power(0))

    async def unlock(self) -> bool:
        """Unlock GRBL after alarm."""
        self._safety_state.emergency_stop = False
        success, _ = await self._send_command('$X')
        return success
