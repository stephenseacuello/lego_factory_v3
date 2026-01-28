"""
CNC Mill Controller - GRBL-based mill integration.

Supports:
- GRBL over serial (USB)
- GRBL over network (ESP32/WiFi)
- G-code streaming with flow control
- Real-time position and status monitoring
"""

import asyncio
import logging
import re
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

logger = logging.getLogger(__name__)


class GrblState(Enum):
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
class GrblStatus:
    """Parsed GRBL status response."""
    state: GrblState
    machine_position: Dict[str, float]
    work_position: Dict[str, float]
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    buffer_blocks: int = 0
    buffer_chars: int = 0
    line_number: int = 0
    pins: str = ""


class MillController(BaseEquipmentController):
    """
    CNC Mill Controller with GRBL support.

    Connection info structure:
    {
        "connection_type": "serial",  # or "network"
        "port": "/dev/ttyUSB0",       # for serial
        "host": "192.168.1.100",      # for network
        "network_port": 8080,          # for network
        "baud_rate": 115200
    }
    """

    GRBL_OK = "ok"
    GRBL_ERROR_PATTERN = re.compile(r"error:(\d+)")
    GRBL_STATUS_PATTERN = re.compile(
        r"<(\w+)\|"  # State
        r"MPos:([-\d.]+),([-\d.]+),([-\d.]+)\|"  # Machine position
        r"WPos:([-\d.]+),([-\d.]+),([-\d.]+)"  # Work position
        r"(?:\|Bf:(\d+),(\d+))?"  # Buffer
        r"(?:\|Ln:(\d+))?"  # Line number
        r"(?:\|FS:(\d+),(\d+))?"  # Feed and spindle
        r"(?:\|Pn:(\w+))?"  # Pins
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
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._serial = None  # pyserial object for serial connections
        self._current_job_id: Optional[str] = None
        self._job_start_time: Optional[datetime] = None
        self._job_lines_total: int = 0
        self._job_lines_sent: int = 0
        self._gcode_queue: List[str] = []
        self._streaming: bool = False
        self._last_status: Optional[GrblStatus] = None

    async def connect(self) -> bool:
        """Establish connection to CNC mill."""
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

            # Wait for GRBL startup message
            await asyncio.sleep(2)

            # Clear any startup messages
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

            self._connected = True
            logger.info(f"Connected to CNC mill via serial: {port}")
            return True

        except ImportError:
            logger.error("pyserial-asyncio not installed. Run: pip install pyserial-asyncio")
            return False
        except Exception as e:
            logger.error(f"Serial connection failed: {e}")
            return False

    async def _connect_network(self) -> bool:
        """Connect via network (ESP32/WiFi)."""
        try:
            host = self.connection_info.get('host', 'localhost')
            port = self.connection_info.get('network_port', 8080)

            self._reader, self._writer = await asyncio.open_connection(host, port)

            # Wait for GRBL startup
            await asyncio.sleep(1)

            self._connected = True
            logger.info(f"Connected to CNC mill via network: {host}:{port}")
            return True

        except Exception as e:
            logger.error(f"Network connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from CNC mill."""
        self._streaming = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._connected = False
        logger.info(f"Disconnected from CNC mill: {self.name}")

    async def ping(self) -> bool:
        """Check if CNC mill is responsive."""
        if not self._connected or not self._writer:
            return False

        try:
            # Send status query
            self._writer.write(b'?')
            await self._writer.drain()

            response = await asyncio.wait_for(
                self._reader.readline(),
                timeout=2.0
            )
            return b'<' in response  # GRBL status response

        except Exception:
            return False

    async def _send_command(self, command: str, wait_ok: bool = True) -> tuple:
        """
        Send G-code command to GRBL.

        Returns:
            (success: bool, response: str)
        """
        if not self._connected or not self._writer:
            return False, "Not connected"

        try:
            # Send command
            cmd = command.strip() + '\n'
            self._writer.write(cmd.encode())
            await self._writer.drain()

            if not wait_ok:
                return True, ""

            # Wait for response
            response = await asyncio.wait_for(
                self._reader.readline(),
                timeout=30.0
            )
            response = response.decode().strip()

            if response == self.GRBL_OK:
                return True, response

            error_match = self.GRBL_ERROR_PATTERN.match(response)
            if error_match:
                error_code = error_match.group(1)
                return False, f"GRBL error {error_code}"

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

            return self._parse_status(response)

        except Exception as e:
            logger.debug(f"Status query failed: {e}")
            return None

    def _parse_status(self, response: str) -> Optional[GrblStatus]:
        """Parse GRBL status response."""
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
                'z': float(groups[3])
            },
            work_position={
                'x': float(groups[4]),
                'y': float(groups[5]),
                'z': float(groups[6])
            },
            buffer_blocks=int(groups[7]) if groups[7] else 0,
            buffer_chars=int(groups[8]) if groups[8] else 0,
            line_number=int(groups[9]) if groups[9] else 0,
            feed_rate=float(groups[10]) if groups[10] else 0,
            spindle_speed=float(groups[11]) if groups[11] else 0,
            pins=groups[12] or ""
        )

    # Status Monitoring

    async def get_state(self) -> EquipmentState:
        """Get current CNC mill state."""
        status = await self._query_status()
        if not status:
            return EquipmentState(status=EquipmentStatus.OFFLINE)

        self._last_status = status

        # Map GRBL state to equipment status
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

        # Calculate job progress
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
                'spindle_speed': status.spindle_speed
            },
            extra_data={
                'grbl_state': status.state.value,
                'machine_position': status.machine_position,
                'buffer_blocks': status.buffer_blocks,
                'buffer_chars': status.buffer_chars,
                'line_number': status.line_number
            }
        )

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get CNC mill capabilities."""
        # Query GRBL settings
        success, response = await self._send_command('$$', wait_ok=False)

        settings = {}
        if success:
            # Parse settings response (multiple lines)
            try:
                for _ in range(50):  # Read up to 50 setting lines
                    line = await asyncio.wait_for(
                        self._reader.readline(),
                        timeout=0.5
                    )
                    line = line.decode().strip()
                    if line == 'ok':
                        break
                    if line.startswith('$'):
                        parts = line.split('=')
                        if len(parts) == 2:
                            settings[parts[0]] = parts[1]
            except asyncio.TimeoutError:
                pass

        return {
            'grbl_settings': settings,
            'axes': ['X', 'Y', 'Z'],
            'max_travel': {
                'x': float(settings.get('$130', 200)),
                'y': float(settings.get('$131', 200)),
                'z': float(settings.get('$132', 50))
            },
            'max_rate': {
                'x': float(settings.get('$110', 1000)),
                'y': float(settings.get('$111', 1000)),
                'z': float(settings.get('$112', 500))
            }
        }

    # Job Control

    async def submit_job(
        self,
        job_id: str,
        file_path: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Load G-code file for milling."""
        try:
            with open(file_path, 'r') as f:
                gcode = f.read()

            # Parse and clean G-code
            lines = []
            for line in gcode.split('\n'):
                # Remove comments and whitespace
                line = line.split(';')[0].strip()
                line = line.split('(')[0].strip()
                if line:
                    lines.append(line)

            self._gcode_queue = lines
            self._job_lines_total = len(lines)
            self._job_lines_sent = 0
            self._current_job_id = job_id
            self._job_start_time = None

            logger.info(f"Loaded G-code: {len(lines)} lines from {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load G-code: {e}")
            return False

    async def start_job(self) -> bool:
        """Start streaming G-code to the mill."""
        if not self._gcode_queue:
            logger.error("No G-code loaded")
            return False

        if self._streaming:
            logger.warning("Already streaming")
            return False

        self._job_start_time = datetime.utcnow()
        self._streaming = True

        # Start streaming in background
        asyncio.create_task(self._stream_gcode())

        logger.info(f"Started milling job: {self._current_job_id}")
        return True

    async def _stream_gcode(self):
        """Stream G-code to GRBL with flow control."""
        try:
            while self._streaming and self._job_lines_sent < self._job_lines_total:
                line = self._gcode_queue[self._job_lines_sent]

                success, response = await self._send_command(line)
                if not success:
                    logger.error(f"G-code error at line {self._job_lines_sent}: {response}")
                    self._streaming = False
                    break

                self._job_lines_sent += 1

                # Yield to allow other tasks
                await asyncio.sleep(0)

            if self._streaming:
                logger.info(f"Milling job completed: {self._current_job_id}")
                self._streaming = False

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            self._streaming = False

    async def pause_job(self) -> bool:
        """Pause milling operation (feed hold)."""
        try:
            # GRBL feed hold command
            self._writer.write(b'!')
            await self._writer.drain()
            self._streaming = False
            logger.info("Milling paused")
            return True

        except Exception as e:
            logger.error(f"Failed to pause: {e}")
            return False

    async def resume_job(self) -> bool:
        """Resume milling operation."""
        try:
            # GRBL cycle start command
            self._writer.write(b'~')
            await self._writer.drain()

            # Resume streaming
            if self._job_lines_sent < self._job_lines_total:
                self._streaming = True
                asyncio.create_task(self._stream_gcode())

            logger.info("Milling resumed")
            return True

        except Exception as e:
            logger.error(f"Failed to resume: {e}")
            return False

    async def cancel_job(self) -> bool:
        """Cancel milling operation."""
        try:
            self._streaming = False

            # Soft reset GRBL
            self._writer.write(b'\x18')  # Ctrl-X
            await self._writer.drain()

            self._gcode_queue = []
            self._current_job_id = None
            self._job_start_time = None

            logger.info("Milling job cancelled")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel: {e}")
            return False

    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get result of completed milling job."""
        # Job tracking would be in database
        return None

    # Equipment Control

    async def home(self) -> bool:
        """Home all axes."""
        success, response = await self._send_command('$H')
        if success:
            logger.info("Homing started")
        return success

    async def emergency_stop(self) -> bool:
        """Emergency stop (soft reset)."""
        try:
            self._streaming = False
            self._writer.write(b'\x18')  # Ctrl-X soft reset
            await self._writer.drain()
            logger.warning("Emergency stop triggered")
            return True

        except Exception as e:
            logger.error(f"E-stop failed: {e}")
            return False

    # Mill-specific methods

    async def jog(self, axis: str, distance: float, feed_rate: float = 100) -> bool:
        """
        Jog axis by specified distance.

        Args:
            axis: 'X', 'Y', or 'Z'
            distance: Distance in mm (positive or negative)
            feed_rate: Feed rate in mm/min
        """
        axis = axis.upper()
        if axis not in ['X', 'Y', 'Z']:
            return False

        # GRBL jog command
        cmd = f"$J=G91 {axis}{distance} F{feed_rate}"
        success, _ = await self._send_command(cmd)
        return success

    async def set_spindle(self, speed: float, direction: str = 'CW') -> bool:
        """
        Set spindle speed and direction.

        Args:
            speed: RPM (0 to stop)
            direction: 'CW' (clockwise) or 'CCW' (counter-clockwise)
        """
        if speed == 0:
            cmd = 'M5'  # Spindle stop
        elif direction == 'CCW':
            cmd = f'M4 S{speed}'  # Counter-clockwise
        else:
            cmd = f'M3 S{speed}'  # Clockwise

        success, _ = await self._send_command(cmd)
        return success

    async def probe(self, axis: str = 'Z', feed_rate: float = 50) -> Optional[float]:
        """
        Run probe operation to find workpiece.

        Args:
            axis: Axis to probe (usually 'Z')
            feed_rate: Probe feed rate

        Returns:
            Probed position if successful, None otherwise.
        """
        axis = axis.upper()
        cmd = f'G38.2 {axis}-50 F{feed_rate}'  # Probe toward workpiece

        success, _ = await self._send_command(cmd)
        if success:
            # Get current position
            status = await self._query_status()
            if status:
                return status.work_position.get(axis.lower())

        return None

    async def set_work_offset(self, x: float = 0, y: float = 0, z: float = 0) -> bool:
        """Set work coordinate offset (G54)."""
        cmd = f'G10 L20 P1 X{x} Y{y} Z{z}'
        success, _ = await self._send_command(cmd)
        return success

    async def unlock(self) -> bool:
        """Unlock GRBL after alarm."""
        success, _ = await self._send_command('$X')
        return success

    async def reset_alarm(self) -> bool:
        """Reset alarm state."""
        return await self.unlock()
