"""
LEGO Factory v3 - Machine Control Service
==========================================
Unified interface for TinyG, GRBL, Marlin, and Bambu controllers.
"""

import asyncio
import json
import re
import time
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)


def _emit_machine_event(event_type: str, data: Dict[str, Any]):
    """
    Emit machine event to WebSocket clients.
    Gracefully handles case where SocketIO isn't initialized.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace, emit_to_room

        # Emit to /dashboard namespace for dashboard subscribers
        emit_to_namespace(event_type, data, namespace='/dashboard')

        # Also notify SCADA users room
        emit_to_room(event_type, data, room='scada', namespace='/')

        # Emit to /unity namespace for digital twin updates
        emit_to_namespace(event_type, data, namespace='/unity')

        logger.debug(f"Emitted machine event: {event_type} for machine {data.get('machine_id')}")
    except ImportError:
        logger.debug("WebSocket service not available, skipping machine emit")
    except Exception as e:
        logger.warning(f"Failed to emit machine event: {e}")


class MachineState(Enum):
    DISCONNECTED = 'disconnected'
    IDLE = 'idle'
    RUNNING = 'running'
    HOLD = 'hold'
    HOMING = 'homing'
    ALARM = 'alarm'
    ERROR = 'error'


class ControllerType(Enum):
    TINYG = 'tinyg'
    GRBL = 'grbl'
    MARLIN = 'marlin'
    BAMBU = 'bambu'
    ROS2 = 'ros2'
    SIMULATION = 'simulation'


@dataclass
class Position:
    """Machine position"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0


@dataclass
class MachineStatus:
    """Current machine status"""
    state: MachineState = MachineState.DISCONNECTED
    position: Position = field(default_factory=Position)
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    current_line: int = 0
    total_lines: int = 0
    progress_pct: float = 0.0
    error_message: str = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MachineController(ABC):
    """Abstract base class for machine controllers"""

    def __init__(self, machine_id: str, config: Dict[str, Any]):
        self.machine_id = machine_id
        self.config = config
        self.status = MachineStatus()
        self._status_callbacks: List[Callable[[MachineStatus], None]] = []
        self._response_callbacks: List[Callable[[str], None]] = []

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the machine"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from the machine"""
        pass

    @abstractmethod
    async def send_command(self, command: str) -> str:
        """Send a command and wait for response"""
        pass

    @abstractmethod
    async def home(self, axes: str = 'XYZ') -> bool:
        """Home the machine"""
        pass

    @abstractmethod
    async def zero(self, axes: str = 'XYZ') -> bool:
        """Zero work coordinates"""
        pass

    @abstractmethod
    async def jog(self, axis: str, distance: float, feed_rate: float) -> bool:
        """Jog an axis"""
        pass

    @abstractmethod
    async def run_gcode(self, gcode: str, on_line: Callable[[int, str], None] = None) -> bool:
        """Run G-code program"""
        pass

    @abstractmethod
    async def pause(self) -> bool:
        """Pause execution"""
        pass

    @abstractmethod
    async def resume(self) -> bool:
        """Resume execution"""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """Stop execution"""
        pass

    @abstractmethod
    async def reset(self) -> bool:
        """Reset the machine"""
        pass

    def on_status_change(self, callback: Callable[[MachineStatus], None]):
        """Register callback for status changes"""
        self._status_callbacks.append(callback)

    def on_response(self, callback: Callable[[str], None]):
        """Register callback for responses"""
        self._response_callbacks.append(callback)

    def _notify_status(self, event_type: str = None):
        """Notify status change callbacks and emit WebSocket events"""
        for cb in self._status_callbacks:
            try:
                cb(self.status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

        # Emit WebSocket event for machine status change
        status_data = {
            'machine_id': self.machine_id,
            'state': self.status.state.value,
            'position': {
                'x': self.status.position.x,
                'y': self.status.position.y,
                'z': self.status.position.z,
                'a': self.status.position.a,
                'b': self.status.position.b,
                'c': self.status.position.c,
            },
            'feed_rate': self.status.feed_rate,
            'spindle_speed': self.status.spindle_speed,
            'current_line': self.status.current_line,
            'total_lines': self.status.total_lines,
            'progress_pct': self.status.progress_pct,
            'error_message': self.status.error_message,
            'timestamp': self.status.timestamp.isoformat(),
        }

        # Use specific event type if provided, otherwise default to status_changed
        ws_event_type = event_type or 'machine_status_changed'
        _emit_machine_event(ws_event_type, status_data)

    def _notify_response(self, response: str):
        """Notify response callbacks"""
        for cb in self._response_callbacks:
            try:
                cb(response)
            except Exception as e:
                logger.error(f"Response callback error: {e}")


class TinyGController(MachineController):
    """
    TinyG Controller
    JSON-based communication protocol
    """

    def __init__(self, machine_id: str, config: Dict[str, Any]):
        super().__init__(machine_id, config)
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baud_rate = config.get('baud_rate', 115200)
        self._serial: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._response_queue = asyncio.Queue()
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to TinyG"""
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1,
                xonxoff=True  # TinyG uses software flow control
            )

            # Start reader thread
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            # Wait for startup message
            await asyncio.sleep(2)

            # Request status
            await self.send_command('{"sr":""}')

            self.status.state = MachineState.IDLE
            self._notify_status('machine_connected')

            logger.info(f"Connected to TinyG on {self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to TinyG: {e}")
            self.status.state = MachineState.ERROR
            self.status.error_message = str(e)
            return False

    async def disconnect(self) -> bool:
        """Disconnect from TinyG"""
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
        if self._serial:
            self._serial.close()
            self._serial = None

        self.status.state = MachineState.DISCONNECTED
        self._notify_status('machine_disconnected')
        logger.info(f"Disconnected from TinyG")
        return True

    def _read_loop(self):
        """Background thread to read serial responses"""
        while self._running and self._serial:
            try:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode('utf-8').strip()
                    if line:
                        self._process_response(line)
            except Exception as e:
                logger.error(f"TinyG read error: {e}")
                time.sleep(0.1)

    def _process_response(self, line: str):
        """Process a response line from TinyG"""
        self._notify_response(line)

        try:
            if line.startswith('{'):
                data = json.loads(line)

                # Status report
                if 'sr' in data:
                    sr = data['sr']
                    if 'posx' in sr:
                        self.status.position.x = sr['posx']
                    if 'posy' in sr:
                        self.status.position.y = sr['posy']
                    if 'posz' in sr:
                        self.status.position.z = sr['posz']
                    if 'posa' in sr:
                        self.status.position.a = sr['posa']
                    if 'vel' in sr:
                        self.status.feed_rate = sr['vel']
                    if 'stat' in sr:
                        stat_map = {
                            0: MachineState.IDLE,
                            1: MachineState.ALARM,
                            2: MachineState.ERROR,
                            3: MachineState.IDLE,
                            4: MachineState.IDLE,
                            5: MachineState.RUNNING,
                            6: MachineState.HOLD,
                            7: MachineState.HOMING,
                            8: MachineState.RUNNING,
                            9: MachineState.HOLD
                        }
                        self.status.state = stat_map.get(sr['stat'], MachineState.IDLE)

                    self.status.timestamp = datetime.utcnow()
                    self._notify_status()

                # Response acknowledgment
                if 'r' in data:
                    asyncio.run_coroutine_threadsafe(
                        self._response_queue.put(data),
                        asyncio.get_event_loop()
                    )

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Error processing TinyG response: {e}")

    async def send_command(self, command: str, timeout: float = 5.0) -> str:
        """Send command and wait for response"""
        async with self._lock:
            if not self._serial:
                raise ConnectionError("Not connected to TinyG")

            # Clear any pending responses
            while not self._response_queue.empty():
                await self._response_queue.get()

            # Send command
            self._serial.write(f"{command}\n".encode('utf-8'))

            # Wait for response
            try:
                response = await asyncio.wait_for(
                    self._response_queue.get(),
                    timeout=timeout
                )
                return json.dumps(response)
            except asyncio.TimeoutError:
                logger.warning(f"TinyG command timeout: {command}")
                return ""

    async def home(self, axes: str = 'XYZ') -> bool:
        """Home specified axes"""
        self.status.state = MachineState.HOMING
        self._notify_status()

        for axis in axes.upper():
            cmd = f'{{"gc":"G28.2 {axis}0"}}'
            await self.send_command(cmd)

        return True

    async def zero(self, axes: str = 'XYZ') -> bool:
        """Zero work coordinates"""
        cmd = f'{{"gc":"G28.3 {" ".join([f"{a}0" for a in axes.upper()])}"}}'
        await self.send_command(cmd)
        return True

    async def jog(self, axis: str, distance: float, feed_rate: float) -> bool:
        """Jog an axis"""
        cmd = f'{{"gc":"G91 G1 {axis.upper()}{distance} F{feed_rate}"}}'
        await self.send_command(cmd)
        await self.send_command('{"gc":"G90"}')  # Return to absolute mode
        return True

    async def run_gcode(self, gcode: str, on_line: Callable[[int, str], None] = None) -> bool:
        """Run G-code program"""
        lines = [l.strip() for l in gcode.split('\n') if l.strip() and not l.strip().startswith(';')]
        self.status.total_lines = len(lines)
        self.status.current_line = 0
        self.status.state = MachineState.RUNNING
        self._notify_status()

        for i, line in enumerate(lines):
            if self.status.state != MachineState.RUNNING:
                break

            self.status.current_line = i + 1
            self.status.progress_pct = (i + 1) / len(lines) * 100

            if on_line:
                on_line(i + 1, line)

            cmd = f'{{"gc":"{line}"}}'
            await self.send_command(cmd)
            self._notify_status()

        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def pause(self) -> bool:
        """Pause execution (feed hold)"""
        await self.send_command('!')
        self.status.state = MachineState.HOLD
        self._notify_status()
        return True

    async def resume(self) -> bool:
        """Resume execution (cycle start)"""
        await self.send_command('~')
        self.status.state = MachineState.RUNNING
        self._notify_status()
        return True

    async def stop(self) -> bool:
        """Stop execution"""
        await self.send_command('{"clear":""}')
        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def reset(self) -> bool:
        """Reset TinyG"""
        await self.send_command('\x18')  # Ctrl-X
        await asyncio.sleep(2)
        self.status.state = MachineState.IDLE
        self._notify_status()
        return True


class GRBLController(MachineController):
    """
    GRBL Controller
    Simple text-based protocol
    """

    def __init__(self, machine_id: str, config: Dict[str, Any]):
        super().__init__(machine_id, config)
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baud_rate = config.get('baud_rate', 115200)
        self._serial: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._response_queue = asyncio.Queue()
        self._lock = asyncio.Lock()

        # GRBL state pattern
        self._state_pattern = re.compile(
            r'<(\w+)\|MPos:([0-9.-]+),([0-9.-]+),([0-9.-]+)'
        )

    async def connect(self) -> bool:
        """Connect to GRBL"""
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1
            )

            # Wake up GRBL
            self._serial.write(b'\r\n\r\n')
            await asyncio.sleep(2)
            self._serial.flushInput()

            # Start reader thread
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            # Request status
            await self.send_command('?')

            self.status.state = MachineState.IDLE
            self._notify_status('machine_connected')

            logger.info(f"Connected to GRBL on {self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to GRBL: {e}")
            self.status.state = MachineState.ERROR
            self.status.error_message = str(e)
            return False

    async def disconnect(self) -> bool:
        """Disconnect from GRBL"""
        self._running = False
        if self._reader_thread:
            self._reader_thread.join(timeout=2)
        if self._serial:
            self._serial.close()
            self._serial = None

        self.status.state = MachineState.DISCONNECTED
        self._notify_status('machine_disconnected')
        return True

    def _read_loop(self):
        """Background thread to read serial responses"""
        while self._running and self._serial:
            try:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode('utf-8').strip()
                    if line:
                        self._process_response(line)
            except Exception as e:
                logger.error(f"GRBL read error: {e}")
                time.sleep(0.1)

    def _process_response(self, line: str):
        """Process a response line from GRBL"""
        self._notify_response(line)

        # Parse status report
        match = self._state_pattern.match(line)
        if match:
            state_str = match.group(1)
            state_map = {
                'Idle': MachineState.IDLE,
                'Run': MachineState.RUNNING,
                'Hold': MachineState.HOLD,
                'Home': MachineState.HOMING,
                'Alarm': MachineState.ALARM,
                'Check': MachineState.IDLE
            }
            self.status.state = state_map.get(state_str, MachineState.IDLE)
            self.status.position.x = float(match.group(2))
            self.status.position.y = float(match.group(3))
            self.status.position.z = float(match.group(4))
            self.status.timestamp = datetime.utcnow()
            self._notify_status()

        # Queue response for send_command
        if line in ['ok', 'error']:
            asyncio.run_coroutine_threadsafe(
                self._response_queue.put(line),
                asyncio.get_event_loop()
            )

    async def send_command(self, command: str, timeout: float = 5.0) -> str:
        """Send command and wait for ok/error"""
        async with self._lock:
            if not self._serial:
                raise ConnectionError("Not connected to GRBL")

            # Clear queue
            while not self._response_queue.empty():
                await self._response_queue.get()

            # Send
            self._serial.write(f"{command}\n".encode('utf-8'))

            # Wait for ok/error
            try:
                response = await asyncio.wait_for(
                    self._response_queue.get(),
                    timeout=timeout
                )
                return response
            except asyncio.TimeoutError:
                return ""

    async def home(self, axes: str = 'XYZ') -> bool:
        """Home GRBL"""
        self.status.state = MachineState.HOMING
        self._notify_status()
        await self.send_command('$H')
        return True

    async def zero(self, axes: str = 'XYZ') -> bool:
        """Zero work coordinates"""
        await self.send_command('G92 X0 Y0 Z0')
        return True

    async def jog(self, axis: str, distance: float, feed_rate: float) -> bool:
        """Jog using GRBL jog command"""
        await self.send_command(f'$J=G91 {axis.upper()}{distance} F{feed_rate}')
        return True

    async def run_gcode(self, gcode: str, on_line: Callable[[int, str], None] = None) -> bool:
        """Run G-code program"""
        lines = [l.strip() for l in gcode.split('\n') if l.strip() and not l.strip().startswith(';')]
        self.status.total_lines = len(lines)
        self.status.current_line = 0
        self.status.state = MachineState.RUNNING
        self._notify_status()

        for i, line in enumerate(lines):
            if self.status.state != MachineState.RUNNING:
                break

            self.status.current_line = i + 1
            self.status.progress_pct = (i + 1) / len(lines) * 100

            if on_line:
                on_line(i + 1, line)

            await self.send_command(line)
            self._notify_status()

        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def pause(self) -> bool:
        """Feed hold"""
        await self.send_command('!')
        self.status.state = MachineState.HOLD
        self._notify_status()
        return True

    async def resume(self) -> bool:
        """Cycle start"""
        await self.send_command('~')
        self.status.state = MachineState.RUNNING
        self._notify_status()
        return True

    async def stop(self) -> bool:
        """Stop"""
        await self.send_command('\x18')  # Ctrl-X soft reset
        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def reset(self) -> bool:
        """Reset GRBL"""
        await self.send_command('\x18')
        await asyncio.sleep(2)
        return True


class SimulationController(MachineController):
    """
    Simulation Controller for testing without hardware.
    """

    def __init__(self, machine_id: str, config: Dict[str, Any]):
        super().__init__(machine_id, config)
        self._running = False

    async def connect(self) -> bool:
        self._running = True
        self.status.state = MachineState.IDLE
        self._notify_status('machine_connected')
        logger.info(f"Simulation controller {self.machine_id} connected")
        return True

    async def disconnect(self) -> bool:
        self._running = False
        self.status.state = MachineState.DISCONNECTED
        self._notify_status('machine_disconnected')
        return True

    async def send_command(self, command: str) -> str:
        await asyncio.sleep(0.01)  # Simulate latency
        return "ok"

    async def home(self, axes: str = 'XYZ') -> bool:
        self.status.state = MachineState.HOMING
        self._notify_status()
        await asyncio.sleep(1)  # Simulate homing time
        self.status.position = Position()  # Zero position
        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def zero(self, axes: str = 'XYZ') -> bool:
        self.status.position = Position()
        self._notify_status()
        return True

    async def jog(self, axis: str, distance: float, feed_rate: float) -> bool:
        axis_lower = axis.lower()
        current = getattr(self.status.position, axis_lower, 0)
        setattr(self.status.position, axis_lower, current + distance)
        self._notify_status()
        return True

    async def run_gcode(self, gcode: str, on_line: Callable[[int, str], None] = None) -> bool:
        lines = [l.strip() for l in gcode.split('\n') if l.strip() and not l.strip().startswith(';')]
        self.status.total_lines = len(lines)
        self.status.state = MachineState.RUNNING
        self._notify_status()

        for i, line in enumerate(lines):
            if self.status.state != MachineState.RUNNING:
                break

            self.status.current_line = i + 1
            self.status.progress_pct = (i + 1) / len(lines) * 100

            if on_line:
                on_line(i + 1, line)

            await asyncio.sleep(0.01)  # Simulate execution time
            self._notify_status()

        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def pause(self) -> bool:
        self.status.state = MachineState.HOLD
        self._notify_status()
        return True

    async def resume(self) -> bool:
        self.status.state = MachineState.RUNNING
        self._notify_status()
        return True

    async def stop(self) -> bool:
        self.status.state = MachineState.IDLE
        self._notify_status()
        return True

    async def reset(self) -> bool:
        self.status = MachineStatus()
        self.status.state = MachineState.IDLE
        self._notify_status()
        return True


# =============================================================================
# MACHINE MANAGER
# =============================================================================

class MachineManager:
    """
    Manages multiple machine controllers.
    Provides unified interface for machine operations.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._machines: Dict[str, MachineController] = {}
        return cls._instance

    def register_machine(
        self,
        machine_id: str,
        controller_type: ControllerType,
        config: Dict[str, Any]
    ) -> MachineController:
        """Register a new machine"""
        controller_class = {
            ControllerType.TINYG: TinyGController,
            ControllerType.GRBL: GRBLController,
            ControllerType.SIMULATION: SimulationController,
        }.get(controller_type)

        if not controller_class:
            raise ValueError(f"Unknown controller type: {controller_type}")

        controller = controller_class(machine_id, config)
        self._machines[machine_id] = controller

        logger.info(f"Registered machine {machine_id} with {controller_type.value} controller")
        return controller

    def unregister_machine(self, machine_id: str) -> bool:
        """Unregister a machine"""
        if machine_id in self._machines:
            del self._machines[machine_id]
            return True
        return False

    def get_machine(self, machine_id: str) -> Optional[MachineController]:
        """Get a machine controller"""
        return self._machines.get(machine_id)

    def list_machines(self) -> List[str]:
        """List all registered machines"""
        return list(self._machines.keys())

    def get_all_status(self) -> Dict[str, MachineStatus]:
        """Get status of all machines"""
        return {mid: m.status for mid, m in self._machines.items()}

    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all machines"""
        results = {}
        for machine_id, controller in self._machines.items():
            results[machine_id] = await controller.connect()
        return results

    async def disconnect_all(self) -> Dict[str, bool]:
        """Disconnect from all machines"""
        results = {}
        for machine_id, controller in self._machines.items():
            results[machine_id] = await controller.disconnect()
        return results

    @staticmethod
    def list_serial_ports() -> List[Dict[str, str]]:
        """List available serial ports"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid
            })
        return ports


# Global machine manager instance
machine_manager = MachineManager()


def get_machine_manager() -> MachineManager:
    """Get the global machine manager instance"""
    return machine_manager


def get_machine(machine_id: str) -> Optional[MachineController]:
    """Get a machine controller"""
    return machine_manager.get_machine(machine_id)


def list_machines() -> List[str]:
    """List all registered machines"""
    return machine_manager.list_machines()
