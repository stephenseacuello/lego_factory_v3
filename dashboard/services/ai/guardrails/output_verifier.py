"""
AI Output Verifier for Manufacturing Systems

Verifies AI-generated outputs against physics constraints and
manufacturing domain knowledge.

Features:
- Physics plausibility checks
- Dimensional analysis
- Manufacturing tolerance verification
- G-code validation
- CAM path validation
"""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class VerificationStatus(Enum):
    """Output verification status."""
    VERIFIED = "verified"
    MODIFIED = "modified"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class PhysicsViolation(Enum):
    """Types of physics violations."""
    NONE = "none"
    CONSERVATION_VIOLATION = "conservation_violation"
    DIMENSIONAL_MISMATCH = "dimensional_mismatch"
    IMPOSSIBLE_VALUE = "impossible_value"
    CAUSALITY_VIOLATION = "causality_violation"
    THERMODYNAMIC_VIOLATION = "thermodynamic_violation"


@dataclass
class VerificationResult:
    """
    Result of output verification.

    Attributes:
        status: Verification status
        original_output: Original AI output
        verified_output: Verified/corrected output
        physics_violations: List of physics violations found
        corrections_made: List of corrections applied
        confidence: Verification confidence
    """
    status: VerificationStatus
    original_output: Any
    verified_output: Any
    physics_violations: List[PhysicsViolation] = field(default_factory=list)
    corrections_made: List[str] = field(default_factory=list)
    confidence: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhysicsConstraints:
    """
    Physics constraints for manufacturing verification.

    All values based on physical laws and material properties.
    """
    # Material properties (ABS plastic default)
    material_density_kg_m3: float = 1040.0  # kg/m³
    material_melting_point_c: float = 230.0  # °C
    material_glass_transition_c: float = 105.0  # °C
    material_thermal_conductivity: float = 0.17  # W/(m·K)
    material_specific_heat: float = 1300.0  # J/(kg·K)

    # Physics limits
    max_cooling_rate_c_s: float = 50.0  # °C/s (natural convection)
    min_layer_adhesion_temp_c: float = 180.0  # °C

    # Dimensional limits (LEGO brick tolerances)
    min_wall_thickness_mm: float = 0.8
    max_overhang_angle_deg: float = 45.0
    stud_tolerance_mm: float = 0.01

    # Energy limits
    max_power_consumption_w: float = 1000.0
    efficiency_lower_bound: float = 0.5  # 50% minimum efficiency


class OutputVerifier:
    """
    Verifies AI outputs against physics and manufacturing constraints.

    Performs multiple verification layers:
    1. Dimensional analysis (units consistency)
    2. Physics plausibility (conservation laws)
    3. Manufacturing feasibility (tolerances, capabilities)
    4. Domain-specific validation (G-code, CAM paths)

    Usage:
        >>> verifier = OutputVerifier(constraints)
        >>> result = verifier.verify(ai_output, output_type="gcode")
        >>> if result.status == VerificationStatus.VERIFIED:
        ...     execute(result.verified_output)
    """

    # Physical constants
    ABSOLUTE_ZERO_K = 0.0
    STEFAN_BOLTZMANN = 5.67e-8  # W/(m²·K⁴)
    SPEED_OF_LIGHT_M_S = 299792458.0

    # Unit patterns for dimensional analysis
    UNIT_PATTERNS = {
        "length": r"(\d+(?:\.\d+)?)\s*(mm|cm|m|in|inch|inches)",
        "temperature": r"(\d+(?:\.\d+)?)\s*(°?[CFK]|celsius|fahrenheit|kelvin)",
        "speed": r"(\d+(?:\.\d+)?)\s*(mm/s|m/s|in/s|mm/min)",
        "force": r"(\d+(?:\.\d+)?)\s*(N|newtons?|lbf|kgf)",
        "pressure": r"(\d+(?:\.\d+)?)\s*(Pa|bar|psi|atm)",
        "power": r"(\d+(?:\.\d+)?)\s*(W|watts?|kW|hp)",
    }

    def __init__(
        self,
        constraints: Optional[PhysicsConstraints] = None,
        strict_mode: bool = True
    ):
        """
        Initialize output verifier.

        Args:
            constraints: Physics constraints configuration
            strict_mode: If True, reject on any physics violation
        """
        self.constraints = constraints or PhysicsConstraints()
        self.strict_mode = strict_mode

        # Compile patterns
        self._unit_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.UNIT_PATTERNS.items()
        }

        # Custom validators
        self._custom_validators: List[Callable] = []

        logger.info(f"OutputVerifier initialized (strict_mode={strict_mode})")

    def verify(
        self,
        output: Any,
        output_type: str = "generic",
        context: Optional[Dict] = None
    ) -> VerificationResult:
        """
        Verify AI-generated output.

        Args:
            output: AI-generated output
            output_type: Type of output ("gcode", "dimensions", "temperature", etc.)
            context: Additional context for verification

        Returns:
            VerificationResult with status and details
        """
        context = context or {}
        violations: List[PhysicsViolation] = []
        corrections: List[str] = []
        verified_output = output

        # Type-specific verification
        if output_type == "gcode":
            result = self._verify_gcode(output)
            violations.extend(result["violations"])
            corrections.extend(result["corrections"])
            verified_output = result["output"]

        elif output_type == "dimensions":
            result = self._verify_dimensions(output)
            violations.extend(result["violations"])
            corrections.extend(result["corrections"])
            verified_output = result["output"]

        elif output_type == "temperature":
            result = self._verify_temperature(output)
            violations.extend(result["violations"])
            corrections.extend(result["corrections"])
            verified_output = result["output"]

        elif output_type == "toolpath":
            result = self._verify_toolpath(output)
            violations.extend(result["violations"])
            corrections.extend(result["corrections"])
            verified_output = result["output"]

        else:
            # Generic verification
            result = self._verify_generic(output)
            violations.extend(result["violations"])
            corrections.extend(result["corrections"])
            verified_output = result["output"]

        # Run custom validators
        for validator in self._custom_validators:
            try:
                custom_result = validator(verified_output, context)
                if custom_result.get("violation"):
                    violations.append(custom_result["violation"])
                if custom_result.get("correction"):
                    corrections.append(custom_result["correction"])
                    verified_output = custom_result.get("output", verified_output)
            except Exception as e:
                logger.warning(f"Custom validator error: {e}")

        # Determine final status
        if violations:
            if self.strict_mode and any(
                v in [PhysicsViolation.CONSERVATION_VIOLATION,
                      PhysicsViolation.THERMODYNAMIC_VIOLATION]
                for v in violations
            ):
                status = VerificationStatus.REJECTED
            elif corrections:
                status = VerificationStatus.MODIFIED
            else:
                status = VerificationStatus.UNCERTAIN
        else:
            status = VerificationStatus.VERIFIED

        return VerificationResult(
            status=status,
            original_output=output,
            verified_output=verified_output,
            physics_violations=violations,
            corrections_made=corrections,
            confidence=self._compute_confidence(violations),
            details={"output_type": output_type, "context": context}
        )

    def _verify_gcode(self, gcode: str) -> Dict[str, Any]:
        """Verify G-code for physics plausibility."""
        violations = []
        corrections = []
        output = gcode

        lines = gcode.strip().split('\n')
        corrected_lines = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                corrected_lines.append(line)
                continue

            corrected_line = line

            # Check feed rate
            feed_match = re.search(r'F(\d+(?:\.\d+)?)', line, re.IGNORECASE)
            if feed_match:
                feed_rate = float(feed_match.group(1))
                max_feed = 10000  # mm/min typical max
                if feed_rate > max_feed:
                    violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                    corrected_line = re.sub(
                        r'F\d+(?:\.\d+)?',
                        f'F{max_feed}',
                        corrected_line
                    )
                    corrections.append(f"Reduced feed rate from {feed_rate} to {max_feed}")

            # Check extrusion temperature
            temp_match = re.search(r'S(\d+(?:\.\d+)?)', line, re.IGNORECASE)
            if 'M104' in line.upper() or 'M109' in line.upper():
                if temp_match:
                    temp = float(temp_match.group(1))
                    if temp > 350:  # Max safe hotend temp
                        violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                        corrected_line = re.sub(
                            r'S\d+(?:\.\d+)?',
                            f'S{self.constraints.material_melting_point_c}',
                            corrected_line
                        )
                        corrections.append(f"Reduced temperature from {temp}°C to safe limit")

            # Check Z movements for negative values
            z_match = re.search(r'Z(-?\d+(?:\.\d+)?)', line, re.IGNORECASE)
            if z_match:
                z_val = float(z_match.group(1))
                if z_val < 0:
                    violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                    corrected_line = re.sub(r'Z-?\d+(?:\.\d+)?', 'Z0', corrected_line)
                    corrections.append(f"Corrected negative Z position {z_val} to 0")

            corrected_lines.append(corrected_line)

        output = '\n'.join(corrected_lines)

        return {"violations": violations, "corrections": corrections, "output": output}

    def _verify_dimensions(self, dimensions: Dict) -> Dict[str, Any]:
        """Verify dimensional outputs."""
        violations = []
        corrections = []
        output = dimensions.copy() if isinstance(dimensions, dict) else dimensions

        if isinstance(dimensions, dict):
            # Check for negative dimensions
            for key, value in dimensions.items():
                if isinstance(value, (int, float)):
                    if 'length' in key.lower() or 'width' in key.lower() or 'height' in key.lower():
                        if value < 0:
                            violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                            output[key] = abs(value)
                            corrections.append(f"Corrected negative {key}: {value} -> {abs(value)}")

                        # Check for impossibly small values
                        if 0 < value < self.constraints.min_wall_thickness_mm:
                            violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                            output[key] = self.constraints.min_wall_thickness_mm
                            corrections.append(
                                f"{key} below minimum wall thickness: "
                                f"{value} -> {self.constraints.min_wall_thickness_mm}"
                            )

            # Check volume conservation if applicable
            if all(k in dimensions for k in ['length', 'width', 'height', 'volume']):
                calculated_volume = dimensions['length'] * dimensions['width'] * dimensions['height']
                stated_volume = dimensions['volume']
                if abs(calculated_volume - stated_volume) / max(stated_volume, 1e-10) > 0.01:
                    violations.append(PhysicsViolation.CONSERVATION_VIOLATION)
                    output['volume'] = calculated_volume
                    corrections.append(f"Corrected volume: {stated_volume} -> {calculated_volume}")

        return {"violations": violations, "corrections": corrections, "output": output}

    def _verify_temperature(self, temp_data: Any) -> Dict[str, Any]:
        """Verify temperature-related outputs."""
        violations = []
        corrections = []
        output = temp_data

        if isinstance(temp_data, dict):
            output = temp_data.copy()

            for key, value in temp_data.items():
                if isinstance(value, (int, float)):
                    # Absolute zero check
                    if value < -273.15:
                        violations.append(PhysicsViolation.THERMODYNAMIC_VIOLATION)
                        output[key] = -273.15
                        corrections.append(f"Temperature below absolute zero: {value} -> -273.15°C")

                    # Unreasonably high temperature
                    if value > 1500:  # Above typical manufacturing temps
                        violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                        corrections.append(f"Temperature suspiciously high: {value}°C")

            # Check temperature gradient if present
            if 'gradient' in temp_data and 'dt' in temp_data:
                gradient = temp_data['gradient']
                dt = temp_data['dt']
                if dt > 0:
                    cooling_rate = abs(gradient) / dt
                    if cooling_rate > self.constraints.max_cooling_rate_c_s * 10:
                        violations.append(PhysicsViolation.THERMODYNAMIC_VIOLATION)
                        corrections.append(f"Cooling rate {cooling_rate}°C/s exceeds physical limit")

        elif isinstance(temp_data, (int, float)):
            if temp_data < -273.15:
                violations.append(PhysicsViolation.THERMODYNAMIC_VIOLATION)
                output = -273.15
                corrections.append(f"Temperature below absolute zero: {temp_data} -> -273.15°C")

        return {"violations": violations, "corrections": corrections, "output": output}

    def _verify_toolpath(self, toolpath: List) -> Dict[str, Any]:
        """Verify toolpath for physics plausibility."""
        violations = []
        corrections = []
        output = toolpath

        if not isinstance(toolpath, list) or len(toolpath) < 2:
            return {"violations": violations, "corrections": corrections, "output": output}

        output = list(toolpath)

        for i in range(1, len(toolpath)):
            prev_point = toolpath[i-1]
            curr_point = toolpath[i]

            if not isinstance(prev_point, dict) or not isinstance(curr_point, dict):
                continue

            # Check for instantaneous position jumps (teleportation)
            if all(k in prev_point and k in curr_point for k in ['x', 'y', 'z', 'time']):
                dx = curr_point['x'] - prev_point['x']
                dy = curr_point['y'] - prev_point['y']
                dz = curr_point['z'] - prev_point['z']
                dt = curr_point['time'] - prev_point['time']

                distance = math.sqrt(dx**2 + dy**2 + dz**2)

                if dt > 0:
                    speed = distance / dt  # mm/s
                    max_speed = 500  # mm/s typical max

                    if speed > max_speed:
                        violations.append(PhysicsViolation.IMPOSSIBLE_VALUE)
                        corrections.append(
                            f"Point {i}: speed {speed:.1f} mm/s exceeds max {max_speed} mm/s"
                        )
                elif dt == 0 and distance > 0:
                    violations.append(PhysicsViolation.CAUSALITY_VIOLATION)
                    corrections.append(f"Point {i}: instantaneous movement detected")
                elif dt < 0:
                    violations.append(PhysicsViolation.CAUSALITY_VIOLATION)
                    corrections.append(f"Point {i}: time going backwards")

        return {"violations": violations, "corrections": corrections, "output": output}

    def _verify_generic(self, output: Any) -> Dict[str, Any]:
        """Generic output verification."""
        violations = []
        corrections = []

        if isinstance(output, str):
            # Check for dimensional consistency
            for unit_type, pattern in self._unit_patterns.items():
                matches = pattern.findall(output)
                if len(matches) > 1:
                    # Multiple values of same unit type - check consistency
                    values = [float(m[0]) for m in matches]
                    if max(values) / max(min(values), 1e-10) > 1000:
                        violations.append(PhysicsViolation.DIMENSIONAL_MISMATCH)
                        corrections.append(f"Large {unit_type} discrepancy: {values}")

        return {"violations": violations, "corrections": corrections, "output": output}

    def _compute_confidence(self, violations: List[PhysicsViolation]) -> float:
        """Compute verification confidence based on violations."""
        if not violations:
            return 1.0

        confidence = 1.0
        for violation in violations:
            if violation == PhysicsViolation.CONSERVATION_VIOLATION:
                confidence *= 0.3
            elif violation == PhysicsViolation.THERMODYNAMIC_VIOLATION:
                confidence *= 0.2
            elif violation == PhysicsViolation.CAUSALITY_VIOLATION:
                confidence *= 0.1
            elif violation == PhysicsViolation.IMPOSSIBLE_VALUE:
                confidence *= 0.5
            elif violation == PhysicsViolation.DIMENSIONAL_MISMATCH:
                confidence *= 0.7

        return max(0.0, min(1.0, confidence))

    def add_custom_validator(self, validator: Callable) -> None:
        """Add a custom validation function."""
        self._custom_validators.append(validator)

    def verify_batch(self, outputs: List[Any], output_type: str = "generic") -> List[VerificationResult]:
        """Verify multiple outputs."""
        return [self.verify(output, output_type) for output in outputs]
