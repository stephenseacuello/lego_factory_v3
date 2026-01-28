#!/usr/bin/env python3
"""
GRBL v1.1 Protocol Parser
=========================
Parses GRBL status reports, alarm codes, and settings.

GRBL Status Format:
  <Idle|MPos:0.000,0.000,0.000|FS:0,0|WCO:0.000,0.000,0.000>
  <Run|MPos:0.000,0.000,0.000|FS:500,12000|Ov:100,100,100>

Reference: https://github.com/gnea/grbl/wiki/Grbl-v1.1-Interface
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import IntEnum


class GrblState(IntEnum):
    """GRBL machine states."""
    UNKNOWN = 0
    IDLE = 1
    RUN = 2
    HOLD = 3
    JOG = 4
    ALARM = 5
    DOOR = 6
    CHECK = 7
    HOME = 8
    SLEEP = 9


# GRBL Alarm codes
GRBL_ALARMS = {
    1: "Hard limit triggered",
    2: "G-code motion target exceeds machine travel",
    3: "Reset while in motion",
    4: "Probe fail - not in expected initial state",
    5: "Probe fail - did not contact workpiece",
    6: "Homing fail - reset during active homing cycle",
    7: "Homing fail - safety door opened during homing",
    8: "Homing fail - cycle failed to find limit switch",
    9: "Homing fail - could not find second limit switch",
    10: "Homing fail - could not find second limit switch (dual axis)",
}

# GRBL Error codes
GRBL_ERRORS = {
    1: "G-code words consist of letter and value (missing value)",
    2: "Numeric value format is not valid",
    3: "Grbl '$' system command was not recognized",
    4: "Negative value received for an expected positive value",
    5: "Homing cycle is not enabled via settings",
    6: "Min step pulse time must be greater than 3usec",
    7: "EEPROM read failed",
    8: "Grbl '$' command cannot be used unless Grbl is IDLE",
    9: "G-code locked out during alarm or jog state",
    10: "Soft limits cannot be enabled without homing enabled",
    11: "Max characters per line exceeded",
    12: "Grbl '$' setting value exceeds max step rate",
    13: "Safety door detected as opened and door state initiated",
    14: "Build info or startup line exceeds EEPROM line length limit",
    15: "Jog target exceeds machine travel",
    16: "Jog command with no '=' or contains prohibited G-code",
    17: "Laser mode requires PWM output",
    20: "Unsupported or invalid G-code command",
    21: "More than one G-code command in modal group 0 in block",
    22: "Feed rate has not yet been set or is undefined",
    23: "G-code command in block requires an integer value",
    24: "Two G-code commands that require axis words were detected",
    25: "A G-code word was repeated in the block",
    26: "A G-code command implicitly or explicitly requires XYZ axis words",
    27: "N line number value is not within valid range",
    28: "A G-code command was sent but is missing P or L value word",
    29: "Grbl supports six work coordinate systems G54-G59",
    30: "A G or M command value in the block is not an integer",
    31: "Two G-code commands from modal group 0 cannot be on one line",
    32: "A G-code command using an axis word was sent without axis words",
    33: "Line number value is invalid or axis letter is missing",
    34: "G-code command requires axis words and none were sent",
    35: "G2 and G3 arcs require at least one in-plane axis word",
    36: "Motion command target is invalid (out of bounds)",
    37: "Arc radius value is invalid (zero or too small)",
    38: "G2 and G3 arcs require at least one in-plane offset word",
}


@dataclass
class GrblStatus:
    """Parsed GRBL status report."""
    state: GrblState = GrblState.UNKNOWN
    state_text: str = ""

    # Machine position
    mpos_x: float = 0.0
    mpos_y: float = 0.0
    mpos_z: float = 0.0
    mpos_a: float = 0.0

    # Work position
    wpos_x: float = 0.0
    wpos_y: float = 0.0
    wpos_z: float = 0.0
    wpos_a: float = 0.0

    # Work coordinate offset
    wco_x: float = 0.0
    wco_y: float = 0.0
    wco_z: float = 0.0

    # Feed and speed
    feed_rate: float = 0.0
    spindle_speed: float = 0.0

    # Overrides (percentage)
    feed_override: int = 100
    rapid_override: int = 100
    spindle_override: int = 100

    # Buffer status
    planner_buffer: int = 15
    rx_buffer: int = 128

    # Input pins
    limit_x: bool = False
    limit_y: bool = False
    limit_z: bool = False
    probe: bool = False
    door: bool = False
    hold: bool = False
    soft_reset: bool = False
    cycle_start: bool = False

    # Line number
    line_number: int = 0

    # Accessory state
    spindle_cw: bool = False
    spindle_ccw: bool = False
    flood_coolant: bool = False
    mist_coolant: bool = False

    raw_response: str = ""


class GrblParser:
    """Parser for GRBL v1.1 serial protocol."""

    # Status report regex
    STATUS_PATTERN = re.compile(r'<([^|>]+)(.*)>')

    # Field patterns
    MPOS_PATTERN = re.compile(r'MPos:(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*)(?:,(-?\d+\.?\d*))?')
    WPOS_PATTERN = re.compile(r'WPos:(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*)(?:,(-?\d+\.?\d*))?')
    WCO_PATTERN = re.compile(r'WCO:(-?\d+\.?\d*),(-?\d+\.?\d*),(-?\d+\.?\d*)')
    FS_PATTERN = re.compile(r'FS:(\d+),(\d+)')  # Feed, Spindle
    F_PATTERN = re.compile(r'F:(\d+)')  # Feed only
    OV_PATTERN = re.compile(r'Ov:(\d+),(\d+),(\d+)')  # Overrides
    BF_PATTERN = re.compile(r'Bf:(\d+),(\d+)')  # Buffer
    PN_PATTERN = re.compile(r'Pn:([XYZPDHRS]+)')  # Pin states
    LN_PATTERN = re.compile(r'Ln:(\d+)')  # Line number
    A_PATTERN = re.compile(r'A:([SFCM]+)')  # Accessory state

    # State mapping
    STATE_MAP = {
        'Idle': GrblState.IDLE,
        'Run': GrblState.RUN,
        'Hold': GrblState.HOLD,
        'Hold:0': GrblState.HOLD,
        'Hold:1': GrblState.HOLD,
        'Jog': GrblState.JOG,
        'Alarm': GrblState.ALARM,
        'Door': GrblState.DOOR,
        'Door:0': GrblState.DOOR,
        'Door:1': GrblState.DOOR,
        'Door:2': GrblState.DOOR,
        'Door:3': GrblState.DOOR,
        'Check': GrblState.CHECK,
        'Home': GrblState.HOME,
        'Sleep': GrblState.SLEEP,
    }

    def __init__(self):
        # Cache WCO for calculating WPos from MPos
        self._cached_wco = (0.0, 0.0, 0.0)

    def parse_status(self, response: str) -> Optional[GrblStatus]:
        """Parse GRBL status report.

        Args:
            response: Raw status string like '<Idle|MPos:0.000,0.000,0.000|FS:0,0>'

        Returns:
            GrblStatus object or None if parse fails
        """
        match = self.STATUS_PATTERN.match(response.strip())
        if not match:
            return None

        status = GrblStatus(raw_response=response)
        state_text = match.group(1)
        fields = match.group(2) if match.group(2) else ""

        # Parse state
        status.state_text = state_text
        status.state = self.STATE_MAP.get(state_text, GrblState.UNKNOWN)

        # Parse fields
        self._parse_position(status, fields)
        self._parse_feed_speed(status, fields)
        self._parse_overrides(status, fields)
        self._parse_buffer(status, fields)
        self._parse_pins(status, fields)
        self._parse_line_number(status, fields)
        self._parse_accessories(status, fields)

        return status

    def _parse_position(self, status: GrblStatus, fields: str):
        """Parse position fields (MPos or WPos)."""
        # Try MPos first
        mpos_match = self.MPOS_PATTERN.search(fields)
        if mpos_match:
            status.mpos_x = float(mpos_match.group(1))
            status.mpos_y = float(mpos_match.group(2))
            status.mpos_z = float(mpos_match.group(3))
            if mpos_match.group(4):
                status.mpos_a = float(mpos_match.group(4))

            # Calculate WPos from MPos and cached WCO
            status.wpos_x = status.mpos_x - self._cached_wco[0]
            status.wpos_y = status.mpos_y - self._cached_wco[1]
            status.wpos_z = status.mpos_z - self._cached_wco[2]

        # Try WPos
        wpos_match = self.WPOS_PATTERN.search(fields)
        if wpos_match:
            status.wpos_x = float(wpos_match.group(1))
            status.wpos_y = float(wpos_match.group(2))
            status.wpos_z = float(wpos_match.group(3))
            if wpos_match.group(4):
                status.wpos_a = float(wpos_match.group(4))

            # Calculate MPos from WPos and cached WCO
            status.mpos_x = status.wpos_x + self._cached_wco[0]
            status.mpos_y = status.wpos_y + self._cached_wco[1]
            status.mpos_z = status.wpos_z + self._cached_wco[2]

        # Update WCO cache if present
        wco_match = self.WCO_PATTERN.search(fields)
        if wco_match:
            status.wco_x = float(wco_match.group(1))
            status.wco_y = float(wco_match.group(2))
            status.wco_z = float(wco_match.group(3))
            self._cached_wco = (status.wco_x, status.wco_y, status.wco_z)
        else:
            status.wco_x, status.wco_y, status.wco_z = self._cached_wco

    def _parse_feed_speed(self, status: GrblStatus, fields: str):
        """Parse feed rate and spindle speed."""
        fs_match = self.FS_PATTERN.search(fields)
        if fs_match:
            status.feed_rate = float(fs_match.group(1))
            status.spindle_speed = float(fs_match.group(2))
        else:
            f_match = self.F_PATTERN.search(fields)
            if f_match:
                status.feed_rate = float(f_match.group(1))

    def _parse_overrides(self, status: GrblStatus, fields: str):
        """Parse override percentages."""
        ov_match = self.OV_PATTERN.search(fields)
        if ov_match:
            status.feed_override = int(ov_match.group(1))
            status.rapid_override = int(ov_match.group(2))
            status.spindle_override = int(ov_match.group(3))

    def _parse_buffer(self, status: GrblStatus, fields: str):
        """Parse buffer status."""
        bf_match = self.BF_PATTERN.search(fields)
        if bf_match:
            status.planner_buffer = int(bf_match.group(1))
            status.rx_buffer = int(bf_match.group(2))

    def _parse_pins(self, status: GrblStatus, fields: str):
        """Parse input pin states."""
        pn_match = self.PN_PATTERN.search(fields)
        if pn_match:
            pins = pn_match.group(1)
            status.limit_x = 'X' in pins
            status.limit_y = 'Y' in pins
            status.limit_z = 'Z' in pins
            status.probe = 'P' in pins
            status.door = 'D' in pins
            status.hold = 'H' in pins
            status.soft_reset = 'R' in pins
            status.cycle_start = 'S' in pins

    def _parse_line_number(self, status: GrblStatus, fields: str):
        """Parse line number."""
        ln_match = self.LN_PATTERN.search(fields)
        if ln_match:
            status.line_number = int(ln_match.group(1))

    def _parse_accessories(self, status: GrblStatus, fields: str):
        """Parse accessory state (spindle, coolant)."""
        a_match = self.A_PATTERN.search(fields)
        if a_match:
            accessories = a_match.group(1)
            status.spindle_cw = 'S' in accessories
            status.spindle_ccw = 'C' in accessories
            status.flood_coolant = 'F' in accessories
            status.mist_coolant = 'M' in accessories

    def parse_alarm(self, response: str) -> Tuple[int, str]:
        """Parse ALARM message.

        Args:
            response: String like 'ALARM:1'

        Returns:
            Tuple of (alarm_code, description)
        """
        match = re.match(r'ALARM:(\d+)', response)
        if match:
            code = int(match.group(1))
            return code, GRBL_ALARMS.get(code, f"Unknown alarm code {code}")
        return 0, ""

    def parse_error(self, response: str) -> Tuple[int, str]:
        """Parse error message.

        Args:
            response: String like 'error:20'

        Returns:
            Tuple of (error_code, description)
        """
        match = re.match(r'error:(\d+)', response)
        if match:
            code = int(match.group(1))
            return code, GRBL_ERRORS.get(code, f"Unknown error code {code}")
        return 0, ""

    def parse_ok(self, response: str) -> bool:
        """Check if response is 'ok'."""
        return response.strip().lower() == 'ok'

    def parse_settings(self, response: str) -> Optional[Tuple[int, float]]:
        """Parse settings response like '$0=10'.

        Returns:
            Tuple of (setting_number, value) or None
        """
        match = re.match(r'\$(\d+)=(\d+\.?\d*)', response)
        if match:
            return int(match.group(1)), float(match.group(2))
        return None
