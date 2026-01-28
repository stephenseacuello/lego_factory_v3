"""
LEGO Factory v3 - Bambu Lab Printer Controller
===============================================
MQTT-based controller for Bambu Lab 3D printers (X1C, P1P, P1S, A1).

Bambu Lab printers use MQTT over TLS for communication:
- Port 8883 for secure MQTT
- Uses device serial number and access code for authentication
- Subscribes to device/SERIAL/report for status updates
- Publishes to device/SERIAL/request for commands
"""

import json
import ssl
import threading
import time
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import paho-mqtt
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logger.warning("paho-mqtt not installed. Bambu controller will run in simulation mode.")


class PrinterState(Enum):
    """Bambu printer states."""
    OFFLINE = 'offline'
    IDLE = 'idle'
    PRINTING = 'printing'
    PAUSED = 'paused'
    FINISHED = 'finished'
    FAILED = 'failed'
    PREPARING = 'preparing'
    SLICING = 'slicing'
    HEATING = 'heating'
    CLEANING = 'cleaning'


@dataclass
class PrintStatus:
    """Current print job status."""
    state: PrinterState = PrinterState.OFFLINE
    progress_pct: float = 0.0
    layer_current: int = 0
    layer_total: int = 0
    time_remaining_min: int = 0
    time_elapsed_min: int = 0
    filename: str = ""
    gcode_state: str = ""
    subtask_name: str = ""
    print_error: int = 0


@dataclass
class PrinterTemperatures:
    """Printer temperature readings."""
    nozzle_target: float = 0.0
    nozzle_actual: float = 0.0
    bed_target: float = 0.0
    bed_actual: float = 0.0
    chamber_target: float = 0.0
    chamber_actual: float = 0.0


@dataclass
class AMSStatus:
    """AMS (Automatic Material System) status."""
    humidity: int = 0
    tray_now: int = 0
    tray_tar: int = 0
    slots: List[Dict[str, Any]] = field(default_factory=list)


class BambuController:
    """
    Controller for Bambu Lab 3D printers via MQTT.

    Supports:
    - X1 Carbon
    - P1P / P1S
    - A1 / A1 Mini

    Usage:
        controller = BambuController(
            ip="192.168.1.100",
            serial="00M00A123456789",
            access_code="12345678"
        )
        controller.connect()
        controller.start_print("file.3mf")
    """

    _instances: Dict[str, 'BambuController'] = {}

    def __init__(
        self,
        ip: str,
        serial: str,
        access_code: str,
        port: int = 8883,
        machine_id: str = None
    ):
        """
        Initialize Bambu controller.

        Args:
            ip: Printer IP address
            serial: Printer serial number (from printer settings)
            access_code: LAN access code (from printer settings)
            port: MQTT port (default 8883 for TLS)
            machine_id: Optional machine ID for tracking
        """
        self.ip = ip
        self.serial = serial
        self.access_code = access_code
        self.port = port
        self.machine_id = machine_id or f"bambu-{serial[-6:]}"

        # MQTT client
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._simulation_mode = not MQTT_AVAILABLE

        # State
        self._print_status = PrintStatus()
        self._temperatures = PrinterTemperatures()
        self._ams_status = AMSStatus()
        self._fans = {'part': 0, 'aux': 0, 'chamber': 0}
        self._lights = {'chamber': False, 'work': False}
        self._speed_profile = 'standard'

        # Callbacks
        self._status_callbacks: List[Callable[[PrintStatus], None]] = []
        self._temp_callbacks: List[Callable[[PrinterTemperatures], None]] = []

        # Thread lock
        self._lock = threading.Lock()

        # Store instance
        BambuController._instances[self.machine_id] = self

        logger.info(f"BambuController initialized for {self.machine_id} at {ip}")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> PrinterState:
        return self._print_status.state

    @property
    def print_status(self) -> PrintStatus:
        return self._print_status

    @property
    def temperatures(self) -> PrinterTemperatures:
        return self._temperatures

    @property
    def ams_status(self) -> AMSStatus:
        return self._ams_status

    def connect(self) -> bool:
        """Connect to the printer via MQTT."""
        if self._simulation_mode:
            logger.info(f"[SIM] Connecting to Bambu printer {self.machine_id}")
            self._connected = True
            self._print_status.state = PrinterState.IDLE
            return True

        if self._connected:
            return True

        try:
            # Create MQTT client with protocol version 3.1.1
            self._client = mqtt.Client(
                client_id=f"lego_factory_{self.machine_id}",
                protocol=mqtt.MQTTv311
            )

            # Set credentials
            self._client.username_pw_set("bblp", self.access_code)

            # Configure TLS (Bambu uses self-signed certs)
            self._client.tls_set(cert_reqs=ssl.CERT_NONE)
            self._client.tls_insecure_set(True)

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Connect
            self._client.connect(self.ip, self.port, keepalive=60)

            # Start network loop in background thread
            self._client.loop_start()

            # Wait for connection
            timeout = 10.0
            start = time.time()
            while not self._connected and time.time() - start < timeout:
                time.sleep(0.1)

            return self._connected

        except Exception as e:
            logger.error(f"Failed to connect to Bambu printer: {e}")
            return False

    def disconnect(self):
        """Disconnect from the printer."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False
        self._print_status.state = PrinterState.OFFLINE
        logger.info(f"Disconnected from Bambu printer {self.machine_id}")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback."""
        if rc == 0:
            logger.info(f"Connected to Bambu printer {self.machine_id}")
            self._connected = True
            self._print_status.state = PrinterState.IDLE

            # Subscribe to status reports
            topic = f"device/{self.serial}/report"
            self._client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")

            # Request initial status
            self._send_command({"pushing": {"sequence_id": "0", "command": "pushall"}})
        else:
            logger.error(f"Bambu MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback."""
        logger.info(f"Disconnected from Bambu printer {self.machine_id}: {rc}")
        self._connected = False
        self._print_status.state = PrinterState.OFFLINE

    def _on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            self._process_report(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bambu message: {e}")
        except Exception as e:
            logger.error(f"Error processing Bambu message: {e}")

    def _process_report(self, data: Dict[str, Any]):
        """Process status report from printer."""
        with self._lock:
            # Print info
            if 'print' in data:
                p = data['print']

                # State
                gcode_state = p.get('gcode_state', '')
                if gcode_state == 'RUNNING':
                    self._print_status.state = PrinterState.PRINTING
                elif gcode_state == 'PAUSE':
                    self._print_status.state = PrinterState.PAUSED
                elif gcode_state == 'FINISH':
                    self._print_status.state = PrinterState.FINISHED
                elif gcode_state == 'FAILED':
                    self._print_status.state = PrinterState.FAILED
                elif gcode_state == 'PREPARE':
                    self._print_status.state = PrinterState.PREPARING
                elif gcode_state == 'SLICING':
                    self._print_status.state = PrinterState.SLICING
                elif gcode_state == 'IDLE':
                    self._print_status.state = PrinterState.IDLE

                self._print_status.gcode_state = gcode_state

                # Progress
                self._print_status.progress_pct = p.get('mc_percent', 0)
                self._print_status.layer_current = p.get('layer_num', 0)
                self._print_status.layer_total = p.get('total_layer_num', 0)
                self._print_status.time_remaining_min = p.get('mc_remaining_time', 0)

                # Temperatures
                self._temperatures.nozzle_target = p.get('nozzle_temper', 0)
                self._temperatures.nozzle_actual = p.get('nozzle_temper', 0)  # Sometimes reported differently
                self._temperatures.bed_target = p.get('bed_target_temper', 0)
                self._temperatures.bed_actual = p.get('bed_temper', 0)
                self._temperatures.chamber_actual = p.get('chamber_temper', 0)

                # Filename
                self._print_status.subtask_name = p.get('subtask_name', '')
                self._print_status.filename = p.get('gcode_file', '')

                # Fans
                self._fans['part'] = p.get('cooling_fan_speed', 0)
                self._fans['aux'] = p.get('big_fan1_speed', 0)
                self._fans['chamber'] = p.get('big_fan2_speed', 0)

                # Lights
                lights = p.get('lights_report', [])
                for light in lights:
                    if light.get('node') == 'chamber_light':
                        self._lights['chamber'] = light.get('mode') == 'on'
                    elif light.get('node') == 'work_light':
                        self._lights['work'] = light.get('mode') == 'on'

                # Speed profile
                spd = p.get('spd_lvl', 0)
                self._speed_profile = ['silent', 'standard', 'sport', 'ludicrous'][min(spd, 3)]

                # Error
                self._print_status.print_error = p.get('print_error', 0)

            # AMS info
            if 'ams' in data:
                ams = data['ams']
                self._ams_status.humidity = ams.get('humidity', 0)
                self._ams_status.tray_now = ams.get('tray_now', 0)
                self._ams_status.tray_tar = ams.get('tray_tar', 0)
                self._ams_status.slots = ams.get('ams', [])

        # Notify callbacks
        for callback in self._status_callbacks:
            try:
                callback(self._print_status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    def _send_command(self, command: Dict[str, Any]) -> bool:
        """Send command to printer."""
        if self._simulation_mode:
            logger.debug(f"[SIM] Sending command: {command}")
            return True

        if not self._connected:
            logger.warning("Cannot send command: not connected")
            return False

        try:
            topic = f"device/{self.serial}/request"
            payload = json.dumps(command)
            self._client.publish(topic, payload)
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False

    # =========================================================================
    # Print Control Commands
    # =========================================================================

    def start_print(self, filename: str, plate_idx: int = 0, use_ams: bool = True) -> bool:
        """
        Start printing a file.

        Args:
            filename: File on SD card or sent via FTP
            plate_idx: Build plate index (for multi-plate prints)
            use_ams: Whether to use AMS
        """
        if self._simulation_mode:
            logger.info(f"[SIM] Starting print: {filename}")
            self._print_status.state = PrinterState.PREPARING
            self._print_status.filename = filename
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "project_file",
                "param": f"Metadata/plate_{plate_idx}.gcode",
                "subtask_name": filename,
                "url": f"file:///sdcard/{filename}",
                "bed_type": "auto",
                "timelapse": False,
                "bed_leveling": True,
                "flow_cali": True,
                "vibration_cali": True,
                "layer_inspect": False,
                "use_ams": use_ams,
            }
        }
        return self._send_command(command)

    def pause_print(self) -> bool:
        """Pause current print."""
        if self._simulation_mode:
            self._print_status.state = PrinterState.PAUSED
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "pause"
            }
        }
        return self._send_command(command)

    def resume_print(self) -> bool:
        """Resume paused print."""
        if self._simulation_mode:
            self._print_status.state = PrinterState.PRINTING
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "resume"
            }
        }
        return self._send_command(command)

    def stop_print(self) -> bool:
        """Stop/cancel current print."""
        if self._simulation_mode:
            self._print_status.state = PrinterState.IDLE
            self._print_status.progress_pct = 0
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "stop"
            }
        }
        return self._send_command(command)

    # =========================================================================
    # Temperature Control
    # =========================================================================

    def set_nozzle_temp(self, temp: float) -> bool:
        """Set nozzle target temperature."""
        if self._simulation_mode:
            self._temperatures.nozzle_target = temp
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "gcode_line",
                "param": f"M104 S{int(temp)}"
            }
        }
        return self._send_command(command)

    def set_bed_temp(self, temp: float) -> bool:
        """Set bed target temperature."""
        if self._simulation_mode:
            self._temperatures.bed_target = temp
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "gcode_line",
                "param": f"M140 S{int(temp)}"
            }
        }
        return self._send_command(command)

    def preheat_pla(self) -> bool:
        """Preheat for PLA (nozzle: 220°C, bed: 55°C)."""
        return self.set_nozzle_temp(220) and self.set_bed_temp(55)

    def preheat_petg(self) -> bool:
        """Preheat for PETG (nozzle: 245°C, bed: 70°C)."""
        return self.set_nozzle_temp(245) and self.set_bed_temp(70)

    def preheat_abs(self) -> bool:
        """Preheat for ABS (nozzle: 270°C, bed: 100°C)."""
        return self.set_nozzle_temp(270) and self.set_bed_temp(100)

    def cooldown(self) -> bool:
        """Cool down all heaters."""
        return self.set_nozzle_temp(0) and self.set_bed_temp(0)

    # =========================================================================
    # Speed & Fan Control
    # =========================================================================

    def set_speed_profile(self, profile: str) -> bool:
        """
        Set speed profile.

        Args:
            profile: 'silent', 'standard', 'sport', or 'ludicrous'
        """
        profiles = {'silent': 1, 'standard': 2, 'sport': 3, 'ludicrous': 4}
        level = profiles.get(profile.lower(), 2)

        if self._simulation_mode:
            self._speed_profile = profile
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "print_speed",
                "param": str(level)
            }
        }
        return self._send_command(command)

    def set_fan_speed(self, fan: str, speed: int) -> bool:
        """
        Set fan speed.

        Args:
            fan: 'part', 'aux', or 'chamber'
            speed: 0-100 percent
        """
        fan_codes = {'part': 'P1', 'aux': 'P2', 'chamber': 'P3'}
        fan_code = fan_codes.get(fan.lower(), 'P1')
        pwm = int(speed * 255 / 100)

        if self._simulation_mode:
            self._fans[fan] = speed
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "gcode_line",
                "param": f"M106 {fan_code} S{pwm}"
            }
        }
        return self._send_command(command)

    # =========================================================================
    # Light Control
    # =========================================================================

    def set_chamber_light(self, on: bool) -> bool:
        """Turn chamber light on/off."""
        if self._simulation_mode:
            self._lights['chamber'] = on
            return True

        command = {
            "system": {
                "sequence_id": str(int(time.time())),
                "command": "ledctrl",
                "led_node": "chamber_light",
                "led_mode": "on" if on else "off",
                "led_on_time": 500,
                "led_off_time": 500,
                "loop_times": 0,
                "interval_time": 0
            }
        }
        return self._send_command(command)

    def set_work_light(self, on: bool) -> bool:
        """Turn work light (nozzle light) on/off."""
        if self._simulation_mode:
            self._lights['work'] = on
            return True

        command = {
            "system": {
                "sequence_id": str(int(time.time())),
                "command": "ledctrl",
                "led_node": "work_light",
                "led_mode": "on" if on else "off"
            }
        }
        return self._send_command(command)

    # =========================================================================
    # Movement Control
    # =========================================================================

    def home(self) -> bool:
        """Home all axes."""
        return self.send_gcode("G28")

    def move_to(self, x: float = None, y: float = None, z: float = None, speed: float = 3000) -> bool:
        """Move to position (absolute)."""
        parts = ["G0"]
        if x is not None:
            parts.append(f"X{x:.2f}")
        if y is not None:
            parts.append(f"Y{y:.2f}")
        if z is not None:
            parts.append(f"Z{z:.2f}")
        parts.append(f"F{speed:.0f}")

        return self.send_gcode(" ".join(parts))

    def send_gcode(self, gcode: str) -> bool:
        """Send raw G-code command."""
        if self._simulation_mode:
            logger.debug(f"[SIM] G-code: {gcode}")
            return True

        command = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": "gcode_line",
                "param": gcode
            }
        }
        return self._send_command(command)

    # =========================================================================
    # AMS Control
    # =========================================================================

    def load_filament(self, slot: int) -> bool:
        """Load filament from AMS slot (0-3)."""
        return self.send_gcode(f"M620 S{slot}A")

    def unload_filament(self) -> bool:
        """Unload current filament."""
        return self.send_gcode("M620 S255")

    # =========================================================================
    # Status & Callbacks
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive printer status."""
        return {
            'machine_id': self.machine_id,
            'connected': self._connected,
            'state': self._print_status.state.value,
            'print': {
                'progress_pct': self._print_status.progress_pct,
                'layer_current': self._print_status.layer_current,
                'layer_total': self._print_status.layer_total,
                'time_remaining_min': self._print_status.time_remaining_min,
                'filename': self._print_status.filename,
                'subtask': self._print_status.subtask_name,
            },
            'temperatures': {
                'nozzle': {'target': self._temperatures.nozzle_target, 'actual': self._temperatures.nozzle_actual},
                'bed': {'target': self._temperatures.bed_target, 'actual': self._temperatures.bed_actual},
                'chamber': {'target': self._temperatures.chamber_target, 'actual': self._temperatures.chamber_actual},
            },
            'fans': self._fans.copy(),
            'lights': self._lights.copy(),
            'speed_profile': self._speed_profile,
            'ams': {
                'humidity': self._ams_status.humidity,
                'current_tray': self._ams_status.tray_now,
            },
        }

    def on_status_update(self, callback: Callable[[PrintStatus], None]):
        """Register callback for status updates."""
        self._status_callbacks.append(callback)

    def on_temperature_update(self, callback: Callable[[PrinterTemperatures], None]):
        """Register callback for temperature updates."""
        self._temp_callbacks.append(callback)


# Global instance cache
_controllers: Dict[str, BambuController] = {}


def get_bambu_controller(
    machine_id: str = None,
    ip: str = None,
    serial: str = None,
    access_code: str = None
) -> Optional[BambuController]:
    """
    Get or create a Bambu controller.

    Args:
        machine_id: Machine ID to retrieve existing controller
        ip: Printer IP address (for new controller)
        serial: Printer serial number (for new controller)
        access_code: LAN access code (for new controller)

    Returns:
        BambuController instance or None
    """
    global _controllers

    if machine_id and machine_id in _controllers:
        return _controllers[machine_id]

    if ip and serial and access_code:
        controller = BambuController(ip, serial, access_code, machine_id=machine_id)
        _controllers[controller.machine_id] = controller
        return controller

    return None
