#!/usr/bin/env python3
"""
TinyG JSON Protocol Parser
==========================
Parses TinyG's JSON-based serial protocol.

TinyG Response Format:
  Status Report: {"sr":{"posx":0.000,"posy":0.000,"posz":0.000,"stat":3,...}}
  Queue Report:  {"qr":28}
  Response:      {"r":{"gc":"G0X10"},"f":[1,0,0]}
  Footer:        {"f":[1,0,0]}  # [protocol_version, status_code, rx_bytes]

Machine States (stat):
  0 = Initializing
  1 = Ready (idle)
  2 = Alarm
  3 = Stop (program stop)
  4 = End (program end)
  5 = Run
  6 = Hold
  7 = Probe
  8 = Cycle (homing)
  9 = Homing
  10 = Jog

Reference: https://github.com/synthetos/TinyG/wiki/TinyG-Status-Reports
"""

import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import IntEnum


class TinyGState(IntEnum):
    """TinyG machine states."""
    INITIALIZING = 0
    READY = 1
    ALARM = 2
    STOP = 3
    END = 4
    RUN = 5
    HOLD = 6
    PROBE = 7
    CYCLE = 8
    HOMING = 9
    JOG = 10


# State name mapping
TINYG_STATE_NAMES = {
    TinyGState.INITIALIZING: "Initializing",
    TinyGState.READY: "Ready",
    TinyGState.ALARM: "Alarm",
    TinyGState.STOP: "Stop",
    TinyGState.END: "End",
    TinyGState.RUN: "Run",
    TinyGState.HOLD: "Hold",
    TinyGState.PROBE: "Probe",
    TinyGState.CYCLE: "Cycle",
    TinyGState.HOMING: "Homing",
    TinyGState.JOG: "Jog",
}

# TinyG status codes
TINYG_STATUS_CODES = {
    0: "OK",
    1: "Error",
    2: "Eagain",
    3: "Noop",
    4: "Complete",
    5: "Terminate",
    6: "Reset",
    7: "EOL",
    8: "EOF",
    9: "File not open",
    10: "Max file size exceeded",
    11: "No such device",
    12: "Buffer empty",
    13: "Buffer full",
    14: "Buffer full - fatal",
    15: "Initializing",
    16: "Entering boot loader",
    17: "Function is stubbed",
    18: "System alarm",
    19: "Soft limit",
    20: "Hard limit",
    # ... more codes exist
}


@dataclass
class TinyGStatus:
    """Parsed TinyG status report."""
    # Machine state
    stat: TinyGState = TinyGState.INITIALIZING
    state_name: str = "Initializing"

    # Position (machine coordinates)
    posx: float = 0.0
    posy: float = 0.0
    posz: float = 0.0
    posa: float = 0.0
    posb: float = 0.0
    posc: float = 0.0

    # Position (work coordinates - G54 offset applied)
    mpox: float = 0.0  # Machine position X
    mpoy: float = 0.0
    mpoz: float = 0.0

    # Offsets (G54-G59 work coordinate systems)
    g54x: float = 0.0
    g54y: float = 0.0
    g54z: float = 0.0

    # Velocity and motion
    vel: float = 0.0      # Velocity (mm/min)
    feed: float = 0.0     # Feed rate (mm/min)
    momo: int = 0         # Motion mode (0=traverse, 1=feed, 2=arc CW, 3=arc CCW)

    # Units and coordinate system
    unit: int = 1         # Units (0=inches, 1=mm)
    coor: int = 1         # Coordinate system (1=G54, 2=G55, etc.)
    macs: int = 0         # Machine state
    cycs: int = 0         # Cycle state
    mots: int = 0         # Motion state
    hold: int = 0         # Hold state
    dist: int = 0         # Distance mode (0=absolute, 1=incremental)
    frmo: int = 0         # Feed rate mode

    # Spindle
    sps: float = 0.0      # Spindle speed (RPM)
    spmo: int = 0         # Spindle mode (0=off, 1=CW, 2=CCW)

    # Coolant
    coof: int = 0         # Coolant flood (0=off, 1=on)
    coom: int = 0         # Coolant mist (0=off, 1=on)

    # Queue and buffer
    qr: int = 28          # Queue report (available buffers)
    qi: int = 0           # Queue in (buffers added)
    qo: int = 0           # Queue out (buffers removed)

    # Line number
    line: int = 0         # Current line number

    # Homing state
    home: int = 0         # Homing state bitmask
    homx: int = 0
    homy: int = 0
    homz: int = 0

    # Probe
    prbe: int = 0         # Probe state
    prbx: float = 0.0
    prby: float = 0.0
    prbz: float = 0.0

    # Raw response
    raw_response: str = ""


@dataclass
class TinyGResponse:
    """Parsed TinyG command response."""
    status_code: int = 0
    status_msg: str = "OK"
    rx_bytes: int = 0
    response_data: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""


class TinyGParser:
    """Parser for TinyG JSON serial protocol."""

    def __init__(self):
        # Cache for incremental status updates
        self._status_cache = TinyGStatus()

    def parse_line(self, line: str) -> Tuple[Optional[TinyGStatus], Optional[TinyGResponse]]:
        """Parse a single line from TinyG.

        Args:
            line: Raw JSON line from TinyG

        Returns:
            Tuple of (TinyGStatus or None, TinyGResponse or None)
        """
        line = line.strip()
        if not line:
            return None, None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None, None

        status = None
        response = None

        # Parse status report
        if 'sr' in data:
            status = self._parse_status_report(data['sr'])
            status.raw_response = line

        # Parse queue report
        if 'qr' in data:
            self._status_cache.qr = data['qr']
            if status is None:
                status = TinyGStatus(qr=data['qr'])

        if 'qi' in data:
            self._status_cache.qi = data['qi']
        if 'qo' in data:
            self._status_cache.qo = data['qo']

        # Parse response with footer
        if 'r' in data:
            response = TinyGResponse(response_data=data['r'], raw_response=line)

        # Parse footer
        if 'f' in data:
            footer = data['f']
            if len(footer) >= 3:
                if response is None:
                    response = TinyGResponse(raw_response=line)
                response.status_code = footer[1]
                response.status_msg = TINYG_STATUS_CODES.get(footer[1], f"Unknown ({footer[1]})")
                response.rx_bytes = footer[2]

        return status, response

    def _parse_status_report(self, sr: Dict[str, Any]) -> TinyGStatus:
        """Parse status report JSON into TinyGStatus.

        TinyG sends incremental updates, so we merge with cached values.
        """
        status = TinyGStatus()

        # Update from cache first
        status.posx = self._status_cache.posx
        status.posy = self._status_cache.posy
        status.posz = self._status_cache.posz
        status.posa = self._status_cache.posa
        status.vel = self._status_cache.vel
        status.feed = self._status_cache.feed
        status.stat = self._status_cache.stat
        status.qr = self._status_cache.qr
        status.sps = self._status_cache.sps
        status.line = self._status_cache.line
        status.unit = self._status_cache.unit
        status.coor = self._status_cache.coor

        # Update with new values
        if 'posx' in sr:
            status.posx = float(sr['posx'])
        if 'posy' in sr:
            status.posy = float(sr['posy'])
        if 'posz' in sr:
            status.posz = float(sr['posz'])
        if 'posa' in sr:
            status.posa = float(sr['posa'])
        if 'posb' in sr:
            status.posb = float(sr['posb'])
        if 'posc' in sr:
            status.posc = float(sr['posc'])

        # Machine position
        if 'mpox' in sr:
            status.mpox = float(sr['mpox'])
        if 'mpoy' in sr:
            status.mpoy = float(sr['mpoy'])
        if 'mpoz' in sr:
            status.mpoz = float(sr['mpoz'])

        # Velocity and feed
        if 'vel' in sr:
            status.vel = float(sr['vel'])
        if 'feed' in sr:
            status.feed = float(sr['feed'])

        # State
        if 'stat' in sr:
            status.stat = TinyGState(int(sr['stat']))
            status.state_name = TINYG_STATE_NAMES.get(status.stat, "Unknown")

        # Motion mode
        if 'momo' in sr:
            status.momo = int(sr['momo'])

        # Units and coordinate system
        if 'unit' in sr:
            status.unit = int(sr['unit'])
        if 'coor' in sr:
            status.coor = int(sr['coor'])
        if 'dist' in sr:
            status.dist = int(sr['dist'])
        if 'frmo' in sr:
            status.frmo = int(sr['frmo'])

        # Machine/cycle/motion state
        if 'macs' in sr:
            status.macs = int(sr['macs'])
        if 'cycs' in sr:
            status.cycs = int(sr['cycs'])
        if 'mots' in sr:
            status.mots = int(sr['mots'])
        if 'hold' in sr:
            status.hold = int(sr['hold'])

        # Spindle
        if 'sps' in sr:
            status.sps = float(sr['sps'])
        if 'spmo' in sr:
            status.spmo = int(sr['spmo'])

        # Coolant
        if 'coof' in sr:
            status.coof = int(sr['coof'])
        if 'coom' in sr:
            status.coom = int(sr['coom'])

        # Line number
        if 'line' in sr:
            status.line = int(sr['line'])

        # Homing
        if 'home' in sr:
            status.home = int(sr['home'])
        if 'homx' in sr:
            status.homx = int(sr['homx'])
        if 'homy' in sr:
            status.homy = int(sr['homy'])
        if 'homz' in sr:
            status.homz = int(sr['homz'])

        # Probe
        if 'prbe' in sr:
            status.prbe = int(sr['prbe'])
        if 'prbx' in sr:
            status.prbx = float(sr['prbx'])
        if 'prby' in sr:
            status.prby = float(sr['prby'])
        if 'prbz' in sr:
            status.prbz = float(sr['prbz'])

        # G54 offsets
        if 'g54x' in sr:
            status.g54x = float(sr['g54x'])
        if 'g54y' in sr:
            status.g54y = float(sr['g54y'])
        if 'g54z' in sr:
            status.g54z = float(sr['g54z'])

        # Update cache
        self._status_cache = status
        return status

    def build_command(self, gcode: str) -> str:
        """Build a TinyG command from G-code.

        Args:
            gcode: G-code command (e.g., "G0 X10 Y20")

        Returns:
            JSON command string for TinyG
        """
        return json.dumps({"gc": gcode})

    def build_status_request(self) -> str:
        """Build a status report request."""
        return '{"sr":null}'

    def build_queue_request(self) -> str:
        """Build a queue report request."""
        return '{"qr":null}'

    def build_settings_request(self, setting: str) -> str:
        """Build a settings request.

        Args:
            setting: Setting key (e.g., "xvm" for X velocity max)

        Returns:
            JSON request string
        """
        return json.dumps({setting: None})

    def build_settings_update(self, setting: str, value: Any) -> str:
        """Build a settings update command.

        Args:
            setting: Setting key
            value: New value

        Returns:
            JSON command string
        """
        return json.dumps({setting: value})

    @staticmethod
    def state_to_ros(tinyg_state: TinyGState) -> int:
        """Convert TinyG state to ROS MachineStatus state constant.

        Maps TinyG states to cnc_interfaces/msg/MachineStatus state values.
        """
        state_map = {
            TinyGState.INITIALIZING: 0,  # UNKNOWN
            TinyGState.READY: 1,         # IDLE
            TinyGState.ALARM: 5,         # ALARM
            TinyGState.STOP: 1,          # IDLE
            TinyGState.END: 1,           # IDLE
            TinyGState.RUN: 2,           # RUN
            TinyGState.HOLD: 3,          # HOLD
            TinyGState.PROBE: 7,         # CHECK
            TinyGState.CYCLE: 8,         # HOME
            TinyGState.HOMING: 8,        # HOME
            TinyGState.JOG: 4,           # JOG
        }
        return state_map.get(tinyg_state, 0)
