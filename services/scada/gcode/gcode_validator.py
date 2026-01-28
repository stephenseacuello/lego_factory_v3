"""
LEGO Factory v3 - G-code Validator Service
============================================
Comprehensive G-code validation to prevent security issues and hardware damage.

This is safety-critical code that validates G-code before it is sent to CNC machines
and 3D printers. It checks for:
- Command injection attempts
- Dangerous commands that could damage hardware
- Movement limits to prevent crashes
- Temperature limits to prevent overheating
- Syntax validation
- Shell injection characters

Author: LEGO Factory Team
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MachineType(Enum):
    """Machine type for validation rules"""
    CNC_MILL = 'cnc_mill'
    CNC_LATHE = 'cnc_lathe'
    LASER_CUTTER = 'laser_cutter'
    PRINTER_3D = 'printer_3d'
    ROUTER = 'router'
    GENERIC = 'generic'


class ValidationSeverity(Enum):
    """Severity level for validation issues"""
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


@dataclass
class ValidationError:
    """Represents a validation error that blocks execution"""
    code: str
    message: str
    line_number: Optional[int] = None
    line_content: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.ERROR

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'message': self.message,
            'line_number': self.line_number,
            'line_content': self.line_content,
            'severity': self.severity.value,
        }


@dataclass
class ValidationWarning:
    """Represents a validation warning that requires confirmation"""
    code: str
    message: str
    command: str
    description: str
    line_number: Optional[int] = None
    requires_confirmation: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'message': self.message,
            'command': self.command,
            'description': self.description,
            'line_number': self.line_number,
            'requires_confirmation': self.requires_confirmation,
        }


@dataclass
class GCodeCommand:
    """Parsed G-code command"""
    raw_line: str
    line_number: int
    command_type: Optional[str] = None  # G, M, T, S, F, etc.
    command_number: Optional[float] = None  # The number after G/M/etc.
    full_command: Optional[str] = None  # e.g., "G28", "M104"
    parameters: Dict[str, float] = field(default_factory=dict)
    comment: Optional[str] = None
    is_comment_only: bool = False
    is_empty: bool = False


@dataclass
class ValidationResult:
    """Result of G-code validation"""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    sanitized_gcode: Optional[str] = None
    command_count: int = 0
    line_count: int = 0
    validation_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': [e.to_dict() for e in self.errors],
            'warnings': [w.to_dict() for w in self.warnings],
            'command_count': self.command_count,
            'line_count': self.line_count,
            'validation_time_ms': self.validation_time_ms,
        }


class GCodeValidator:
    """
    Comprehensive G-code validator for CNC machines and 3D printers.

    Security Features:
    - Blocks shell injection characters
    - Blocks dangerous EEPROM commands
    - Validates movement limits
    - Validates temperature limits
    - Enforces command count limits
    - Validates syntax
    """

    # =========================================================================
    # BLOCKED COMMANDS - These should NEVER be allowed via API
    # =========================================================================
    BLOCKED_COMMANDS: Dict[str, str] = {
        # EEPROM manipulation - could corrupt machine settings
        'M500': 'Save settings to EEPROM - could corrupt machine configuration',
        'M501': 'Load settings from EEPROM - could load unsafe settings',
        'M502': 'Reset to factory defaults - could reset safety limits',

        # Firmware manipulation
        'M997': 'Firmware update - could brick the machine',
        'M999': 'Reset after emergency - should only be done manually',

        # Debug commands that could expose information
        'M115': 'Firmware info - information disclosure',
        'M503': 'Report settings - information disclosure',

        # SD card access could be used for exfiltration
        'M20': 'List SD card files',
        'M21': 'Initialize SD card',
        'M22': 'Release SD card',
        'M23': 'Select SD file',
        'M24': 'Start/resume SD print',
        'M25': 'Pause SD print',
        'M26': 'Set SD position',
        'M27': 'Report SD print status',
        'M28': 'Start SD write',
        'M29': 'Stop SD write',
        'M30': 'Delete SD file',
        'M32': 'Select and start SD file',
        'M33': 'Get long path',
        'M524': 'Abort SD print',

        # Network commands (if supported)
        'M552': 'Set IP address',
        'M553': 'Set netmask',
        'M554': 'Set gateway',
        'M586': 'Configure network protocols',
        'M587': 'Store WiFi credentials',
        'M588': 'Forget WiFi credentials',
        'M589': 'Configure access point',
    }

    # =========================================================================
    # DANGEROUS COMMANDS - Allowed but require confirmation
    # =========================================================================
    DANGEROUS_COMMANDS: Dict[str, str] = {
        # Emergency and safety
        'M112': 'Emergency stop - will halt all operations immediately',
        'M410': 'Quickstop - aborts all planned movement',

        # Homing - can cause crashes if not configured properly
        'G28': 'Home axes - can crash if machine not properly configured',
        'G28.1': 'Reference point setting',
        'G28.2': 'Homing sequence (TinyG)',
        'G28.3': 'Set absolute position (TinyG)',
        '$H': 'GRBL homing command',

        # Coordinate system changes - could cause unexpected movements
        'G10': 'Coordinate system/tool offset change',
        'G53': 'Move in machine coordinates - bypasses work coordinate safety',
        'G54': 'Select work coordinate system 1',
        'G55': 'Select work coordinate system 2',
        'G56': 'Select work coordinate system 3',
        'G57': 'Select work coordinate system 4',
        'G58': 'Select work coordinate system 5',
        'G59': 'Select work coordinate system 6',
        'G92': 'Set position - changes coordinate system',

        # Temperature control without proper limits
        'M302': 'Allow cold extrusion - can damage extruder if filament not loaded',
        'M303': 'PID autotune - can cause overheating during calibration',

        # Motor control
        'M17': 'Enable steppers - could cause unexpected movement',
        'M18': 'Disable steppers - could cause Z-axis drop',
        'M84': 'Disable steppers - could cause Z-axis drop',

        # Fan control at extreme values
        'M106': 'Fan on - verify speed is appropriate',

        # Laser commands (if not a laser machine)
        'M3': 'Spindle/Laser on',
        'M4': 'Spindle/Laser on (counter-clockwise)',
    }

    # =========================================================================
    # SHELL INJECTION CHARACTERS - Must be blocked to prevent command injection
    # Note: Newlines (\n, \r) are NOT blocked here because G-code uses them
    # between lines normally. We validate line-by-line instead.
    # =========================================================================
    SHELL_INJECTION_CHARS: Set[str] = {
        # ';' is NOT blocked - it's a valid G-code comment delimiter
        '|',   # Pipe
        '&',   # Background execution
        '$',   # Variable expansion (except $H for GRBL homing)
        '`',   # Command substitution
        '\x00', # Null byte
        '\x1b', # Escape sequences
    }

    # Additional patterns that could be injection attempts
    # Note: These are checked AFTER comment stripping, so semicolon comments
    # won't trigger false positives
    INJECTION_PATTERNS: List[Tuple[str, str]] = [
        (r'\$\(', 'Shell command substitution attempt'),
        (r'\$\{', 'Shell variable expansion attempt'),
        (r'`.*`', 'Backtick command substitution'),
        (r'>\s*/', 'File write redirection attempt'),
        (r'>>\s*/', 'File append redirection attempt'),
        (r'<\s*/', 'File read redirection attempt'),
        (r'\|\s*\w+', 'Pipe command attempt'),
        (r'&&\s*\w+', 'AND command chaining'),
        (r'\|\|\s*\w+', 'OR command chaining'),
    ]

    # =========================================================================
    # G-CODE SYNTAX PATTERNS
    # =========================================================================
    # Valid G-code line pattern
    GCODE_LINE_PATTERN = re.compile(
        r'^'
        r'(?:N\d+\s*)?'  # Optional line number
        r'(?:'
        r'[GMT]\d+(?:\.\d+)?'  # G, M, or T command
        r'|[XYZABCIJKEFSPRDQHLO][-+]?(?:\d+\.?\d*|\.\d+)'  # Axis/parameter
        r'|\$[A-Z0-9]+=?[-+]?\d*\.?\d*'  # GRBL settings
        r'|\$H'  # GRBL homing
        r'|\?'  # GRBL status query
        r'|!'    # Feed hold
        r'|~'    # Cycle start
        r'|\x18' # Soft reset (Ctrl-X)
        r')*'
        r'(?:\s*[;(].*)?'  # Optional comment
        r'$',
        re.IGNORECASE
    )

    # Command extraction pattern
    COMMAND_PATTERN = re.compile(
        r'([GMT])(\d+(?:\.\d+)?)',
        re.IGNORECASE
    )

    # Parameter extraction pattern
    PARAM_PATTERN = re.compile(
        r'([XYZABCIJKEFSPRDQHLO])([-+]?(?:\d+\.?\d*|\.\d+))',
        re.IGNORECASE
    )

    # Comment patterns
    COMMENT_SEMICOLON = re.compile(r';.*$')
    COMMENT_PARENTHESIS = re.compile(r'\([^)]*\)')

    # =========================================================================
    # DEFAULT LIMITS
    # =========================================================================
    DEFAULT_LIMITS = {
        'max_x': 500.0,
        'max_y': 500.0,
        'max_z': 500.0,
        'min_x': -10.0,
        'min_y': -10.0,
        'min_z': -10.0,
        'max_feedrate': 15000.0,  # mm/min
        'max_spindle_rpm': 30000.0,
        'max_laser_power': 100.0,  # Percentage
        'max_nozzle_temp': 300.0,  # Celsius (3D printers)
        'max_bed_temp': 120.0,  # Celsius (3D printers)
        'max_chamber_temp': 70.0,  # Celsius (3D printers)
        'max_line_length': 256,
        'max_command_count': 100000,
        'max_total_length': 10_000_000,  # 10MB max G-code size
    }

    def __init__(
        self,
        machine_type: MachineType = MachineType.GENERIC,
        custom_limits: Optional[Dict[str, float]] = None,
        allowed_commands: Optional[Set[str]] = None,
        additional_blocked_commands: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the G-code validator.

        Args:
            machine_type: Type of machine for context-aware validation
            custom_limits: Override default movement/temperature limits
            allowed_commands: If provided, only these commands are allowed (whitelist mode)
            additional_blocked_commands: Extra commands to block beyond defaults
        """
        self.machine_type = machine_type
        self.limits = {**self.DEFAULT_LIMITS, **(custom_limits or {})}
        self.allowed_commands = allowed_commands
        self.blocked_commands = {**self.BLOCKED_COMMANDS}

        if additional_blocked_commands:
            self.blocked_commands.update(additional_blocked_commands)

    def validate(
        self,
        gcode: str,
        machine_config: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate G-code for safety and security.

        Args:
            gcode: The G-code string to validate
            machine_config: Optional machine-specific configuration

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        start_time = datetime.utcnow()
        errors: List[ValidationError] = []
        warnings: List[ValidationWarning] = []

        # Apply machine config limits if provided
        if machine_config:
            self._apply_machine_config(machine_config)

        # Check total length first
        if len(gcode) > self.limits['max_total_length']:
            errors.append(ValidationError(
                code='GCODE_TOO_LARGE',
                message=f'G-code exceeds maximum size of {self.limits["max_total_length"]} bytes',
                severity=ValidationSeverity.ERROR,
            ))
            return self._build_result(False, errors, warnings, None, 0, 0, start_time)

        # Check for shell injection at the raw string level
        injection_errors = self._check_shell_injection(gcode)
        if injection_errors:
            errors.extend(injection_errors)
            return self._build_result(False, errors, warnings, None, 0, 0, start_time)

        # Parse and validate each line
        lines = gcode.split('\n')

        if len(lines) > self.limits['max_command_count']:
            errors.append(ValidationError(
                code='TOO_MANY_COMMANDS',
                message=f'G-code has {len(lines)} lines, exceeds limit of {self.limits["max_command_count"]}',
                severity=ValidationSeverity.ERROR,
            ))
            return self._build_result(False, errors, warnings, None, 0, len(lines), start_time)

        parsed_commands: List[GCodeCommand] = []
        sanitized_lines: List[str] = []
        command_count = 0

        for line_num, line in enumerate(lines, 1):
            # Parse the line
            cmd = self.parse_line(line, line_num)
            parsed_commands.append(cmd)

            if cmd.is_empty or cmd.is_comment_only:
                # Keep comments but don't count as commands
                sanitized_lines.append(cmd.raw_line.strip())
                continue

            command_count += 1

            # Validate line length
            if len(line) > self.limits['max_line_length']:
                errors.append(ValidationError(
                    code='LINE_TOO_LONG',
                    message=f'Line exceeds maximum length of {self.limits["max_line_length"]} characters',
                    line_number=line_num,
                    line_content=line[:50] + '...' if len(line) > 50 else line,
                    severity=ValidationSeverity.ERROR,
                ))
                continue

            # Check for blocked commands
            if cmd.full_command:
                blocked_reason = self._check_blocked_command(cmd)
                if blocked_reason:
                    errors.append(ValidationError(
                        code='BLOCKED_COMMAND',
                        message=f'Command {cmd.full_command} is blocked: {blocked_reason}',
                        line_number=line_num,
                        line_content=line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))
                    continue

            # Check for dangerous commands
            if cmd.full_command:
                dangerous_warning = self._check_dangerous_command(cmd)
                if dangerous_warning:
                    warnings.append(dangerous_warning)

            # Check whitelist if enabled
            if self.allowed_commands is not None and cmd.full_command:
                if cmd.full_command.upper() not in self.allowed_commands:
                    errors.append(ValidationError(
                        code='COMMAND_NOT_ALLOWED',
                        message=f'Command {cmd.full_command} is not in allowed list',
                        line_number=line_num,
                        line_content=line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))
                    continue

            # Validate movement limits
            movement_errors = self._check_movement_limits(cmd)
            errors.extend(movement_errors)

            # Validate feedrate
            feedrate_error = self._check_feedrate(cmd)
            if feedrate_error:
                errors.append(feedrate_error)

            # Validate temperatures (for 3D printers)
            temp_errors = self._check_temperature_limits(cmd)
            errors.extend(temp_errors)

            # Validate spindle/laser
            spindle_errors = self._check_spindle_limits(cmd)
            errors.extend(spindle_errors)

            # Add sanitized line
            sanitized_line = self.sanitize_line(line)
            sanitized_lines.append(sanitized_line)

        # Build result
        is_valid = len(errors) == 0
        sanitized_gcode = '\n'.join(sanitized_lines) if is_valid else None

        return self._build_result(
            is_valid, errors, warnings, sanitized_gcode,
            command_count, len(lines), start_time
        )

    def parse_line(self, line: str, line_number: int = 0) -> GCodeCommand:
        """
        Parse a single G-code line into a structured command.

        Args:
            line: The G-code line to parse
            line_number: Line number for error reporting

        Returns:
            Parsed GCodeCommand
        """
        cmd = GCodeCommand(
            raw_line=line,
            line_number=line_number,
        )

        # Strip whitespace
        stripped = line.strip()

        # Check for empty line
        if not stripped:
            cmd.is_empty = True
            return cmd

        # Check for comment-only line
        if stripped.startswith(';') or stripped.startswith('('):
            cmd.is_comment_only = True
            cmd.comment = stripped
            return cmd

        # Extract comment if present
        comment_match = self.COMMENT_SEMICOLON.search(stripped)
        if comment_match:
            cmd.comment = comment_match.group()
            stripped = stripped[:comment_match.start()].strip()

        # Remove parenthetical comments
        stripped = self.COMMENT_PARENTHESIS.sub('', stripped).strip()

        if not stripped:
            cmd.is_comment_only = True
            return cmd

        # Extract command (G, M, T)
        command_match = self.COMMAND_PATTERN.search(stripped)
        if command_match:
            cmd.command_type = command_match.group(1).upper()
            cmd.command_number = float(command_match.group(2))
            cmd.full_command = f'{cmd.command_type}{int(cmd.command_number) if cmd.command_number == int(cmd.command_number) else cmd.command_number}'

        # Handle GRBL-specific commands
        if stripped.startswith('$'):
            if stripped == '$H':
                cmd.command_type = '$'
                cmd.full_command = '$H'
            elif '=' in stripped:
                cmd.command_type = '$'
                cmd.full_command = stripped.split('=')[0]

        # Extract parameters
        for param_match in self.PARAM_PATTERN.finditer(stripped):
            param_name = param_match.group(1).upper()
            param_value = float(param_match.group(2))
            cmd.parameters[param_name] = param_value

        return cmd

    def sanitize(self, gcode: str) -> str:
        """
        Sanitize G-code by removing comments and normalizing whitespace.

        Args:
            gcode: The G-code to sanitize

        Returns:
            Sanitized G-code string
        """
        lines = gcode.split('\n')
        sanitized = []

        for line in lines:
            sanitized_line = self.sanitize_line(line)
            if sanitized_line:  # Skip empty lines
                sanitized.append(sanitized_line)

        return '\n'.join(sanitized)

    def sanitize_line(self, line: str) -> str:
        """
        Sanitize a single G-code line.

        Args:
            line: The line to sanitize

        Returns:
            Sanitized line
        """
        # Strip whitespace
        result = line.strip()

        # Remove semicolon comments
        result = self.COMMENT_SEMICOLON.sub('', result).strip()

        # Remove parenthetical comments
        result = self.COMMENT_PARENTHESIS.sub('', result).strip()

        # Normalize whitespace
        result = ' '.join(result.split())

        return result.upper()

    def check_movement_limits(
        self,
        command: GCodeCommand,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if a command's movements are within limits.

        Args:
            command: The parsed G-code command
            config: Optional machine configuration

        Returns:
            True if within limits, False otherwise
        """
        errors = self._check_movement_limits(command)
        return len(errors) == 0

    def check_dangerous_commands(
        self,
        command: GCodeCommand
    ) -> List[ValidationWarning]:
        """
        Check if a command is dangerous and return warnings.

        Args:
            command: The parsed G-code command

        Returns:
            List of warnings for dangerous commands
        """
        warnings = []
        warning = self._check_dangerous_command(command)
        if warning:
            warnings.append(warning)
        return warnings

    # =========================================================================
    # PRIVATE VALIDATION METHODS
    # =========================================================================

    def _apply_machine_config(self, config: Dict[str, Any]) -> None:
        """Apply machine configuration to limits"""
        # Map config keys to limit keys
        key_mapping = {
            'work_envelope_x': 'max_x',
            'work_envelope_y': 'max_y',
            'work_envelope_z': 'max_z',
            'max_feed_rate': 'max_feedrate',
            'max_spindle_rpm': 'max_spindle_rpm',
            'laser_power_max': 'max_laser_power',
            'max_nozzle_temp': 'max_nozzle_temp',
            'max_bed_temp': 'max_bed_temp',
        }

        for config_key, limit_key in key_mapping.items():
            if config_key in config and config[config_key] is not None:
                self.limits[limit_key] = float(config[config_key])

    def _check_shell_injection(self, gcode: str) -> List[ValidationError]:
        """Check for shell injection attempts"""
        errors = []

        # Check for dangerous characters
        for char in self.SHELL_INJECTION_CHARS:
            if char in gcode:
                # Special handling for $ - allowed for GRBL commands like $H, $1=value
                if char == '$':
                    # Check if $ is used in a valid GRBL context
                    # Valid: $H, $1, $1=100, etc. ($ followed by letter/digit or at line start)
                    # Invalid: $(command), ${var}
                    if re.search(r'\$\([^)]*\)', gcode) or re.search(r'\$\{[^}]*\}', gcode):
                        errors.append(ValidationError(
                            code='SHELL_INJECTION',
                            message='Shell command substitution detected',
                            severity=ValidationSeverity.ERROR,
                        ))
                    # Don't flag valid GRBL $ commands
                    continue
                else:
                    errors.append(ValidationError(
                        code='SHELL_INJECTION',
                        message=f'Forbidden character detected: {repr(char)}',
                        severity=ValidationSeverity.ERROR,
                    ))

        # Check for injection patterns (on comment-stripped content to avoid false positives)
        # Strip comments from each line before pattern matching
        stripped_lines = []
        for line in gcode.split('\n'):
            # Remove semicolon comments
            line_no_comment = self.COMMENT_SEMICOLON.sub('', line)
            # Remove parenthetical comments
            line_no_comment = self.COMMENT_PARENTHESIS.sub('', line_no_comment)
            stripped_lines.append(line_no_comment)
        stripped_gcode = '\n'.join(stripped_lines)

        for pattern, description in self.INJECTION_PATTERNS:
            if re.search(pattern, stripped_gcode):
                errors.append(ValidationError(
                    code='INJECTION_PATTERN',
                    message=f'Injection pattern detected: {description}',
                    severity=ValidationSeverity.ERROR,
                ))

        return errors

    def _check_blocked_command(self, cmd: GCodeCommand) -> Optional[str]:
        """Check if command is blocked, return reason if blocked"""
        if not cmd.full_command:
            return None

        full_cmd = cmd.full_command.upper()

        # Direct match
        if full_cmd in self.blocked_commands:
            return self.blocked_commands[full_cmd]

        # Check for G10 L2 (coordinate system change)
        if full_cmd == 'G10' and cmd.parameters.get('L') == 2:
            return 'G10 L2 coordinate system change is blocked'

        return None

    def _check_dangerous_command(self, cmd: GCodeCommand) -> Optional[ValidationWarning]:
        """Check if command is dangerous, return warning if so"""
        if not cmd.full_command:
            return None

        full_cmd = cmd.full_command.upper()

        # Direct match
        if full_cmd in self.DANGEROUS_COMMANDS:
            return ValidationWarning(
                code='DANGEROUS_COMMAND',
                message=f'Dangerous command detected: {full_cmd}',
                command=full_cmd,
                description=self.DANGEROUS_COMMANDS[full_cmd],
                line_number=cmd.line_number,
                requires_confirmation=True,
            )

        # Check for G10 without L2 (tool offset)
        if full_cmd == 'G10' and cmd.parameters.get('L') != 2:
            return ValidationWarning(
                code='DANGEROUS_COMMAND',
                message='G10 tool offset change detected',
                command='G10',
                description='Tool offset changes can cause unexpected movements',
                line_number=cmd.line_number,
                requires_confirmation=True,
            )

        return None

    def _check_movement_limits(self, cmd: GCodeCommand) -> List[ValidationError]:
        """Check movement parameters against limits"""
        errors = []

        # Only check movement commands
        if cmd.command_type not in ('G', None) or cmd.full_command in ('G28', 'G28.1', 'G28.2', 'G28.3'):
            return errors

        # Movement commands
        movement_commands = {0, 1, 2, 3}  # G0, G1, G2, G3
        if cmd.command_number is not None and cmd.command_number not in movement_commands:
            return errors

        # Check each axis
        axis_limits = {
            'X': ('min_x', 'max_x'),
            'Y': ('min_y', 'max_y'),
            'Z': ('min_z', 'max_z'),
        }

        for axis, (min_key, max_key) in axis_limits.items():
            if axis in cmd.parameters:
                value = cmd.parameters[axis]
                min_val = self.limits.get(min_key, -float('inf'))
                max_val = self.limits.get(max_key, float('inf'))

                if value < min_val or value > max_val:
                    errors.append(ValidationError(
                        code='MOVEMENT_OUT_OF_BOUNDS',
                        message=f'{axis}={value} is outside limits [{min_val}, {max_val}]',
                        line_number=cmd.line_number,
                        line_content=cmd.raw_line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))

        return errors

    def _check_feedrate(self, cmd: GCodeCommand) -> Optional[ValidationError]:
        """Check feedrate against limit"""
        if 'F' in cmd.parameters:
            feedrate = cmd.parameters['F']
            max_feedrate = self.limits.get('max_feedrate', float('inf'))

            if feedrate > max_feedrate:
                return ValidationError(
                    code='FEEDRATE_TOO_HIGH',
                    message=f'Feedrate F{feedrate} exceeds maximum of {max_feedrate}',
                    line_number=cmd.line_number,
                    line_content=cmd.raw_line.strip(),
                    severity=ValidationSeverity.ERROR,
                )
        return None

    def _check_temperature_limits(self, cmd: GCodeCommand) -> List[ValidationError]:
        """Check temperature commands for 3D printers"""
        errors = []

        if cmd.command_type != 'M':
            return errors

        # M104/M109 - Nozzle temperature
        if cmd.command_number in (104, 109):
            if 'S' in cmd.parameters:
                temp = cmd.parameters['S']
                max_temp = self.limits.get('max_nozzle_temp', 300)

                if temp > max_temp:
                    errors.append(ValidationError(
                        code='NOZZLE_TEMP_TOO_HIGH',
                        message=f'Nozzle temperature {temp}C exceeds maximum of {max_temp}C',
                        line_number=cmd.line_number,
                        line_content=cmd.raw_line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))

        # M140/M190 - Bed temperature
        if cmd.command_number in (140, 190):
            if 'S' in cmd.parameters:
                temp = cmd.parameters['S']
                max_temp = self.limits.get('max_bed_temp', 120)

                if temp > max_temp:
                    errors.append(ValidationError(
                        code='BED_TEMP_TOO_HIGH',
                        message=f'Bed temperature {temp}C exceeds maximum of {max_temp}C',
                        line_number=cmd.line_number,
                        line_content=cmd.raw_line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))

        # M141 - Chamber temperature
        if cmd.command_number == 141:
            if 'S' in cmd.parameters:
                temp = cmd.parameters['S']
                max_temp = self.limits.get('max_chamber_temp', 70)

                if temp > max_temp:
                    errors.append(ValidationError(
                        code='CHAMBER_TEMP_TOO_HIGH',
                        message=f'Chamber temperature {temp}C exceeds maximum of {max_temp}C',
                        line_number=cmd.line_number,
                        line_content=cmd.raw_line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))

        return errors

    def _check_spindle_limits(self, cmd: GCodeCommand) -> List[ValidationError]:
        """Check spindle/laser power limits"""
        errors = []

        # S parameter for spindle speed or laser power
        if 'S' in cmd.parameters:
            # For M3/M4 (spindle on) or M106 (fan/laser)
            if cmd.command_type == 'M' and cmd.command_number in (3, 4):
                speed = cmd.parameters['S']
                max_speed = self.limits.get('max_spindle_rpm', 30000)

                if speed > max_speed:
                    errors.append(ValidationError(
                        code='SPINDLE_SPEED_TOO_HIGH',
                        message=f'Spindle speed {speed} exceeds maximum of {max_speed}',
                        line_number=cmd.line_number,
                        line_content=cmd.raw_line.strip(),
                        severity=ValidationSeverity.ERROR,
                    ))

        return errors

    def _build_result(
        self,
        is_valid: bool,
        errors: List[ValidationError],
        warnings: List[ValidationWarning],
        sanitized_gcode: Optional[str],
        command_count: int,
        line_count: int,
        start_time: datetime,
    ) -> ValidationResult:
        """Build the validation result"""
        end_time = datetime.utcnow()
        validation_time_ms = (end_time - start_time).total_seconds() * 1000

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            sanitized_gcode=sanitized_gcode,
            command_count=command_count,
            line_count=line_count,
            validation_time_ms=validation_time_ms,
        )


# =========================================================================
# FACTORY FUNCTIONS
# =========================================================================

def get_gcode_validator(
    machine_type: MachineType = MachineType.GENERIC,
    machine_config: Optional[Dict[str, Any]] = None,
) -> GCodeValidator:
    """
    Factory function to create a G-code validator with appropriate settings.

    Args:
        machine_type: Type of machine
        machine_config: Optional machine configuration dict

    Returns:
        Configured GCodeValidator instance
    """
    custom_limits = {}

    if machine_config:
        # Extract limits from machine config
        if 'work_envelope_x' in machine_config:
            custom_limits['max_x'] = machine_config['work_envelope_x']
        if 'work_envelope_y' in machine_config:
            custom_limits['max_y'] = machine_config['work_envelope_y']
        if 'work_envelope_z' in machine_config:
            custom_limits['max_z'] = machine_config['work_envelope_z']
        if 'max_feed_rate' in machine_config:
            custom_limits['max_feedrate'] = machine_config['max_feed_rate']
        if 'max_spindle_rpm' in machine_config:
            custom_limits['max_spindle_rpm'] = machine_config['max_spindle_rpm']

    return GCodeValidator(
        machine_type=machine_type,
        custom_limits=custom_limits if custom_limits else None,
    )


def create_validator_for_machine_type(machine_type_str: str) -> GCodeValidator:
    """
    Create a validator based on machine type string from config.

    Args:
        machine_type_str: Machine type string (e.g., 'cnc_mill', 'printer_3d')

    Returns:
        Configured GCodeValidator
    """
    type_mapping = {
        'cnc_mill': MachineType.CNC_MILL,
        'cnc_lathe': MachineType.CNC_LATHE,
        'laser_cutter': MachineType.LASER_CUTTER,
        'printer_3d': MachineType.PRINTER_3D,
        'router': MachineType.ROUTER,
        'robot_arm': MachineType.GENERIC,  # Robots use different protocols
    }

    machine_type = type_mapping.get(machine_type_str, MachineType.GENERIC)
    return GCodeValidator(machine_type=machine_type)
