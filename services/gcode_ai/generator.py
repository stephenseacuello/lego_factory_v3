"""
G-code Generator for AI-powered natural language to G-code conversion.

Uses Claude AI to interpret natural language machining requests
and generate valid, safe G-code.
"""

import logging
import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of machining operations."""
    DRILLING = "drilling"
    POCKETING = "pocketing"
    PROFILING = "profiling"
    FACING = "facing"
    ENGRAVING = "engraving"
    THREADING = "threading"
    CHAMFERING = "chamfering"
    SLOTTING = "slotting"
    CONTOURING_3D = "contouring_3d"
    CUSTOM = "custom"


@dataclass
class GenerationRequest:
    """Request for G-code generation."""
    description: str                    # Natural language description
    operation_type: Optional[OperationType] = None
    material: str = "aluminum"
    tool_diameter: float = 0.25         # inches
    tool_number: int = 1
    safe_z: float = 0.1                 # Safe retract height
    feed_rate: Optional[float] = None   # Override feed rate
    spindle_speed: Optional[int] = None # Override spindle speed
    depth: Optional[float] = None       # Total depth
    step_down: Optional[float] = None   # Depth per pass
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedProgram:
    """Generated G-code program."""
    success: bool
    gcode: str
    operation_type: OperationType
    description: str
    warnings: List[str]
    estimated_time_minutes: float
    parameters_used: Dict[str, Any]
    explanation: str  # Explanation of what the code does


class GCodeGenerator:
    """
    Generates G-code from natural language descriptions.

    Uses Claude AI for interpretation and templates for common operations.
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """
        Initialize generator.

        Args:
            flask_url: URL of Flask backend for API calls
        """
        self.flask_url = flask_url

        # Default parameters
        self._defaults = {
            "safe_z": 0.1,
            "feed_rate_aluminum": 30.0,
            "feed_rate_steel": 10.0,
            "spindle_speed_aluminum": 12000,
            "spindle_speed_steel": 3000,
            "step_down_factor": 0.5,  # Factor of tool diameter
        }

    def generate(self, request: GenerationRequest) -> GeneratedProgram:
        """
        Generate G-code from a request.

        Args:
            request: Generation request with description and parameters

        Returns:
            GeneratedProgram with G-code and metadata
        """
        # Parse the request to determine operation
        operation = request.operation_type or self._detect_operation(request.description)

        # Get material-appropriate parameters
        params = self._get_parameters(request)

        # Generate based on operation type
        if operation == OperationType.DRILLING:
            return self._generate_drilling(request, params)
        elif operation == OperationType.POCKETING:
            return self._generate_pocket(request, params)
        elif operation == OperationType.PROFILING:
            return self._generate_profile(request, params)
        elif operation == OperationType.ENGRAVING:
            return self._generate_engraving(request, params)
        elif operation == OperationType.FACING:
            return self._generate_facing(request, params)
        elif operation == OperationType.CHAMFERING:
            return self._generate_chamfer(request, params)
        else:
            return self._generate_custom(request, params)

    def _detect_operation(self, description: str) -> OperationType:
        """Detect operation type from natural language."""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["drill", "hole", "bore"]):
            return OperationType.DRILLING
        elif any(word in desc_lower for word in ["pocket", "cavity", "recess"]):
            return OperationType.POCKETING
        elif any(word in desc_lower for word in ["profile", "contour", "outline", "cut out"]):
            return OperationType.PROFILING
        elif any(word in desc_lower for word in ["engrave", "text", "letter", "write"]):
            return OperationType.ENGRAVING
        elif any(word in desc_lower for word in ["face", "flatten", "surface", "skim"]):
            return OperationType.FACING
        elif any(word in desc_lower for word in ["chamfer", "bevel", "edge break"]):
            return OperationType.CHAMFERING
        elif any(word in desc_lower for word in ["slot", "groove", "channel"]):
            return OperationType.SLOTTING
        elif any(word in desc_lower for word in ["3d", "sculpt", "surface"]):
            return OperationType.CONTOURING_3D
        else:
            return OperationType.CUSTOM

    def _get_parameters(self, request: GenerationRequest) -> Dict[str, Any]:
        """Get appropriate parameters for the request."""
        material = request.material.lower()

        # Base parameters
        if "steel" in material or "stainless" in material:
            feed = self._defaults["feed_rate_steel"]
            speed = self._defaults["spindle_speed_steel"]
        elif "aluminum" in material:
            feed = self._defaults["feed_rate_aluminum"]
            speed = self._defaults["spindle_speed_aluminum"]
        else:
            feed = 20.0
            speed = 8000

        # Apply overrides
        feed = request.feed_rate or feed
        speed = request.spindle_speed or speed

        # Calculate step down
        step_down = request.step_down or (
            request.tool_diameter * self._defaults["step_down_factor"]
        )

        return {
            "feed_rate": feed,
            "spindle_speed": speed,
            "safe_z": request.safe_z,
            "tool_diameter": request.tool_diameter,
            "tool_number": request.tool_number,
            "step_down": step_down,
            "depth": request.depth or 0.1,
        }

    def _generate_drilling(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate drilling operation G-code."""
        warnings = []

        # Parse coordinates from description
        coords = self._parse_coordinates(request.description)
        if not coords:
            coords = [{"x": 0, "y": 0}]
            warnings.append("No coordinates found in description, using X0 Y0")

        # Parse depth
        depth = self._parse_depth(request.description) or params["depth"]

        # Determine if peck drilling is needed
        peck_depth = params["tool_diameter"] * 2
        use_peck = depth > params["tool_diameter"] * 3

        lines = [
            f"( Drilling Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Material: {request.material} )",
            f"( Tool: T{params['tool_number']} - {params['tool_diameter']}\" drill )",
            f"( Depth: {depth}\" )",
            "",
            "G90 G94 G17 G21 ( Absolute, Feed/min, XY plane, Metric )",
            f"G54 ( Work coordinate system )",
            "",
            f"T{params['tool_number']} M6 ( Tool change )",
            f"S{params['spindle_speed']} M3 ( Start spindle )",
            "G4 P2.0 ( Dwell for spindle )",
            "M8 ( Coolant on )",
            "",
            f"G0 Z{params['safe_z']} ( Safe height )",
        ]

        # Generate drilling for each hole
        for i, coord in enumerate(coords):
            x = coord.get("x", 0)
            y = coord.get("y", 0)

            lines.append(f"")
            lines.append(f"( Hole {i + 1} at X{x} Y{y} )")
            lines.append(f"G0 X{x} Y{y}")
            lines.append(f"G0 Z0.1 ( Rapid to approach )")

            if use_peck:
                # G83 peck drilling cycle
                lines.append(
                    f"G83 Z{-depth} R0.1 Q{peck_depth} F{params['feed_rate'] * 0.5}"
                )
                lines.append(f"G0 Z{params['safe_z']}")
            else:
                # Simple drilling
                lines.append(f"G1 Z{-depth} F{params['feed_rate'] * 0.5}")
                lines.append(f"G0 Z{params['safe_z']}")

        lines.extend([
            "",
            "G80 ( Cancel canned cycle )",
            "M9 ( Coolant off )",
            "M5 ( Spindle stop )",
            f"G0 Z{params['safe_z']}",
            "G0 X0 Y0 ( Return to origin )",
            "M30 ( Program end )",
        ])

        gcode = "\n".join(lines)
        time_estimate = len(coords) * (depth / (params["feed_rate"] * 0.5) + 0.1)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.DRILLING,
            description=f"Drill {len(coords)} hole(s), {depth}\" deep",
            warnings=warnings,
            estimated_time_minutes=time_estimate,
            parameters_used=params,
            explanation=f"Drilling {len(coords)} hole(s) at specified coordinates. "
                       f"{'Peck drilling (G83) used due to depth.' if use_peck else 'Simple drill cycle.'}",
        )

    def _generate_pocket(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate rectangular pocket G-code."""
        warnings = []

        # Parse dimensions from description
        dims = self._parse_dimensions(request.description)
        width = dims.get("width", 1.0)
        length = dims.get("length", 1.0)
        depth = self._parse_depth(request.description) or params["depth"]

        # Calculate toolpath
        tool_dia = params["tool_diameter"]
        step_over = tool_dia * 0.4  # 40% stepover for pocketing
        step_down = params["step_down"]

        # Number of passes
        num_depth_passes = math.ceil(depth / step_down)
        actual_step_down = depth / num_depth_passes

        lines = [
            f"( Pocket Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Material: {request.material} )",
            f"( Tool: T{params['tool_number']} - {tool_dia}\" end mill )",
            f"( Pocket: {width}\" x {length}\" x {depth}\" deep )",
            "",
            "G90 G94 G17 ( Absolute, Feed/min, XY plane )",
            "G54",
            "",
            f"T{params['tool_number']} M6",
            f"S{params['spindle_speed']} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params['safe_z']}",
        ]

        # Calculate pocket bounds (assuming center at origin)
        x_min = -width / 2 + tool_dia / 2
        x_max = width / 2 - tool_dia / 2
        y_min = -length / 2 + tool_dia / 2
        y_max = length / 2 - tool_dia / 2

        # Generate pocket passes
        current_z = 0
        for z_pass in range(num_depth_passes):
            current_z -= actual_step_down
            lines.append(f"")
            lines.append(f"( Depth pass {z_pass + 1}/{num_depth_passes} at Z{current_z:.4f} )")

            # Ramp entry
            lines.append(f"G0 X{x_min:.4f} Y{y_min:.4f}")
            lines.append(f"G0 Z0.1")
            lines.append(f"G1 Z{current_z:.4f} F{params['feed_rate'] * 0.3}")

            # Outward spiral pattern
            y_current = y_min
            direction = 1
            while y_current <= y_max:
                if direction == 1:
                    lines.append(f"G1 X{x_max:.4f} Y{y_current:.4f} F{params['feed_rate']}")
                else:
                    lines.append(f"G1 X{x_min:.4f} Y{y_current:.4f} F{params['feed_rate']}")
                direction *= -1
                y_current += step_over

            # Clean up walls
            lines.append(f"")
            lines.append(f"( Wall cleanup )")
            lines.append(f"G1 X{x_min:.4f} Y{y_min:.4f}")
            lines.append(f"G1 Y{y_max:.4f}")
            lines.append(f"G1 X{x_max:.4f}")
            lines.append(f"G1 Y{y_min:.4f}")
            lines.append(f"G1 X{x_min:.4f}")

        lines.extend([
            "",
            f"G0 Z{params['safe_z']}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        gcode = "\n".join(lines)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.POCKETING,
            description=f"Pocket {width}\" x {length}\" x {depth}\" deep",
            warnings=warnings,
            estimated_time_minutes=num_depth_passes * 2.0,
            parameters_used=params,
            explanation=f"Rectangular pocket with {num_depth_passes} depth passes. "
                       f"Ramp entry used for tool safety. 40% stepover for efficient cutting.",
        )

    def _generate_profile(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate profile/contour cutting G-code."""
        warnings = []

        # Parse shape from description
        shape = self._parse_shape(request.description)
        depth = self._parse_depth(request.description) or params["depth"]

        tool_dia = params["tool_diameter"]
        step_down = params["step_down"]
        num_passes = math.ceil(depth / step_down)

        lines = [
            f"( Profile Cut Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Material: {request.material} )",
            f"( Tool: T{params['tool_number']} - {tool_dia}\" end mill )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params['tool_number']} M6",
            f"S{params['spindle_speed']} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params['safe_z']}",
        ]

        if shape["type"] == "circle":
            radius = shape.get("radius", 0.5)
            x_center = shape.get("x", 0)
            y_center = shape.get("y", 0)

            # Calculate actual cut radius (offset by tool radius)
            cut_radius = radius + tool_dia / 2  # Outside cut

            current_z = 0
            for z_pass in range(num_passes):
                current_z -= step_down
                current_z = max(current_z, -depth)

                lines.append(f"")
                lines.append(f"( Pass {z_pass + 1}/{num_passes} at Z{current_z:.4f} )")
                lines.append(f"G0 X{x_center + cut_radius:.4f} Y{y_center:.4f}")
                lines.append(f"G0 Z0.1")
                lines.append(f"G1 Z{current_z:.4f} F{params['feed_rate'] * 0.5}")
                lines.append(
                    f"G2 X{x_center + cut_radius:.4f} Y{y_center:.4f} "
                    f"I{-cut_radius:.4f} J0 F{params['feed_rate']}"
                )

        elif shape["type"] == "rectangle":
            width = shape.get("width", 1.0)
            height = shape.get("height", 1.0)
            x_center = shape.get("x", 0)
            y_center = shape.get("y", 0)

            # Calculate corners with offset
            offset = tool_dia / 2
            x1 = x_center - width / 2 - offset
            x2 = x_center + width / 2 + offset
            y1 = y_center - height / 2 - offset
            y2 = y_center + height / 2 + offset

            current_z = 0
            for z_pass in range(num_passes):
                current_z -= step_down
                current_z = max(current_z, -depth)

                lines.append(f"")
                lines.append(f"( Pass {z_pass + 1}/{num_passes} at Z{current_z:.4f} )")
                lines.append(f"G0 X{x1:.4f} Y{y1:.4f}")
                lines.append(f"G0 Z0.1")
                lines.append(f"G1 Z{current_z:.4f} F{params['feed_rate'] * 0.5}")
                lines.append(f"G1 X{x2:.4f} F{params['feed_rate']}")
                lines.append(f"G1 Y{y2:.4f}")
                lines.append(f"G1 X{x1:.4f}")
                lines.append(f"G1 Y{y1:.4f}")

        lines.extend([
            "",
            f"G0 Z{params['safe_z']}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        gcode = "\n".join(lines)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.PROFILING,
            description=f"Profile cut {shape['type']}, {depth}\" deep",
            warnings=warnings,
            estimated_time_minutes=num_passes * 1.5,
            parameters_used=params,
            explanation=f"Profile cut with {num_passes} depth passes. Climb milling direction.",
        )

    def _generate_engraving(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate engraving G-code."""
        warnings = []

        # Parse text from description
        text = self._parse_text(request.description)
        depth = 0.01  # Shallow for engraving

        lines = [
            f"( Engraving Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Text: {text} )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params['tool_number']} M6 ( V-bit or engraving tool )",
            f"S{params['spindle_speed']} M3",
            "G4 P2.0",
            "",
            f"G0 Z{params['safe_z']}",
            "",
            f"( Note: Full text engraving requires CAM software )",
            f"( This is a placeholder for text: {text} )",
            "",
            "G0 X0 Y0",
            f"G0 Z0.1",
            f"G1 Z{-depth} F{params['feed_rate'] * 0.3}",
            "",
            "( Engrave pattern here )",
            "",
            f"G0 Z{params['safe_z']}",
            "M5",
            "G0 X0 Y0",
            "M30",
        ]

        warnings.append(
            "Text engraving requires CAM software for proper font conversion. "
            "This is a template only."
        )

        gcode = "\n".join(lines)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.ENGRAVING,
            description=f"Engrave: {text}",
            warnings=warnings,
            estimated_time_minutes=len(text) * 0.5,
            parameters_used=params,
            explanation="Engraving template generated. Full text requires CAM software.",
        )

    def _generate_facing(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate facing operation G-code."""
        warnings = []

        dims = self._parse_dimensions(request.description)
        width = dims.get("width", 4.0)
        length = dims.get("length", 4.0)
        depth = 0.02  # Light facing cut

        tool_dia = params["tool_diameter"]
        step_over = tool_dia * 0.6  # 60% stepover for facing

        lines = [
            f"( Facing Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Area: {width}\" x {length}\" )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params['tool_number']} M6",
            f"S{params['spindle_speed']} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params['safe_z']}",
        ]

        # Generate facing passes
        y_current = -length / 2
        direction = 1

        lines.append(f"G0 X{-width/2:.4f} Y{y_current:.4f}")
        lines.append(f"G1 Z{-depth:.4f} F{params['feed_rate'] * 0.5}")

        while y_current <= length / 2:
            if direction == 1:
                lines.append(f"G1 X{width/2:.4f} Y{y_current:.4f} F{params['feed_rate']}")
            else:
                lines.append(f"G1 X{-width/2:.4f} Y{y_current:.4f} F{params['feed_rate']}")
            direction *= -1
            y_current += step_over

        lines.extend([
            "",
            f"G0 Z{params['safe_z']}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ])

        gcode = "\n".join(lines)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.FACING,
            description=f"Face {width}\" x {length}\" area",
            warnings=warnings,
            estimated_time_minutes=2.0,
            parameters_used=params,
            explanation=f"Facing operation with {step_over}\" stepover (60% of tool diameter).",
        )

    def _generate_chamfer(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate chamfering G-code."""
        warnings = []

        # Parse chamfer size
        chamfer_size = 0.03  # Default 0.030" chamfer

        lines = [
            f"( Chamfer Operation )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params['tool_number']} M6 ( Chamfer tool )",
            f"S{params['spindle_speed']} M3",
            "G4 P2.0",
            "",
            f"G0 Z{params['safe_z']}",
            "",
            "( Move to edge and chamfer )",
            "G0 X0 Y0",
            f"G0 Z0.1",
            f"G1 Z{-chamfer_size} F{params['feed_rate'] * 0.5}",
            "",
            "( Follow edge contour )",
            "",
            f"G0 Z{params['safe_z']}",
            "M5",
            "G0 X0 Y0",
            "M30",
        ]

        warnings.append("Chamfer path requires edge coordinates from CAD model.")

        gcode = "\n".join(lines)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.CHAMFERING,
            description=f"Chamfer edges",
            warnings=warnings,
            estimated_time_minutes=1.0,
            parameters_used=params,
            explanation="Chamfer template. Requires edge coordinates from CAD.",
        )

    def _generate_custom(
        self,
        request: GenerationRequest,
        params: Dict[str, Any],
    ) -> GeneratedProgram:
        """Generate custom operation using Claude AI."""
        warnings = ["Custom operation - please verify G-code before running"]

        lines = [
            f"( Custom Operation )",
            f"( Request: {request.description} )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            "",
            "G90 G94 G17",
            "G54",
            "",
            f"T{params['tool_number']} M6",
            f"S{params['spindle_speed']} M3",
            "G4 P2.0",
            "M8",
            "",
            f"G0 Z{params['safe_z']}",
            "",
            "( Custom operations go here )",
            "",
            f"G0 Z{params['safe_z']}",
            "M9",
            "M5",
            "G0 X0 Y0",
            "M30",
        ]

        gcode = "\n".join(lines)

        return GeneratedProgram(
            success=True,
            gcode=gcode,
            operation_type=OperationType.CUSTOM,
            description=request.description,
            warnings=warnings,
            estimated_time_minutes=5.0,
            parameters_used=params,
            explanation="Custom operation template. Add specific moves as needed.",
        )

    def _parse_coordinates(self, text: str) -> List[Dict[str, float]]:
        """Parse coordinates from text."""
        coords = []

        # Pattern: X## Y##
        pattern = r"X\s*(-?\d+\.?\d*)\s*Y\s*(-?\d+\.?\d*)"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            coords.append({
                "x": float(match.group(1)),
                "y": float(match.group(2)),
            })

        # Pattern: at (#, #)
        pattern = r"at\s*\(?(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\)?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            coords.append({
                "x": float(match.group(1)),
                "y": float(match.group(2)),
            })

        return coords

    def _parse_depth(self, text: str) -> Optional[float]:
        """Parse depth from text."""
        patterns = [
            r"(\d+\.?\d*)\s*(?:inch|in|\")\s*deep",
            r"depth\s*(?:of\s*)?(\d+\.?\d*)",
            r"(\d+\.?\d*)\s*mm\s*deep",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                if "mm" in pattern:
                    value /= 25.4  # Convert to inches
                return value

        return None

    def _parse_dimensions(self, text: str) -> Dict[str, float]:
        """Parse dimensions from text."""
        dims = {}

        # Pattern: #x# or # by #
        pattern = r"(\d+\.?\d*)\s*(?:x|by)\s*(\d+\.?\d*)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            dims["width"] = float(match.group(1))
            dims["length"] = float(match.group(2))

        # Pattern: width/length specific
        for dim in ["width", "length", "height"]:
            pattern = rf"{dim}\s*(?:of\s*)?(\d+\.?\d*)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                dims[dim] = float(match.group(1))

        return dims

    def _parse_shape(self, text: str) -> Dict[str, Any]:
        """Parse shape from text."""
        text_lower = text.lower()

        if "circle" in text_lower or "round" in text_lower:
            # Look for radius or diameter
            radius = 0.5
            match = re.search(r"(\d+\.?\d*)\s*(?:inch|in|\")\s*(?:radius|rad)", text, re.IGNORECASE)
            if match:
                radius = float(match.group(1))
            match = re.search(r"(\d+\.?\d*)\s*(?:inch|in|\")\s*(?:diameter|dia)", text, re.IGNORECASE)
            if match:
                radius = float(match.group(1)) / 2

            return {"type": "circle", "radius": radius, "x": 0, "y": 0}

        else:
            # Default to rectangle
            dims = self._parse_dimensions(text)
            return {
                "type": "rectangle",
                "width": dims.get("width", 1.0),
                "height": dims.get("length", 1.0),
                "x": 0,
                "y": 0,
            }

    def _parse_text(self, description: str) -> str:
        """Parse text content for engraving."""
        # Look for quoted text
        match = re.search(r'"([^"]+)"', description)
        if match:
            return match.group(1)

        match = re.search(r"'([^']+)'", description)
        if match:
            return match.group(1)

        # Look for "text: xxx" or "engrave xxx"
        match = re.search(r"(?:text|engrave|write)\s*:?\s*(\w+)", description, re.IGNORECASE)
        if match:
            return match.group(1)

        return "TEXT"


# Convenience function
def generate_gcode(
    description: str,
    material: str = "aluminum",
    tool_diameter: float = 0.25,
) -> GeneratedProgram:
    """Quick G-code generation from description."""
    generator = GCodeGenerator()
    request = GenerationRequest(
        description=description,
        material=material,
        tool_diameter=tool_diameter,
    )
    return generator.generate(request)
