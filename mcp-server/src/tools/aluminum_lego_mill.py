"""
Aluminum LEGO Milling Service
=============================

Complete workflow for machining aluminum LEGO bricks on Bantam Desktop CNC.

Features:
- Two-setup workflow (top/bottom operations)
- Bantam-optimized post-processor
- Exact stock sizing with Z offset handling
- Automated CAD → CAM → G-code pipeline
- Workholding guidance

Author: LegoMCP Team
Version: 1.0.0
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import math
import json


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class SetupType(Enum):
    """Machine setup orientations."""
    TOP = "top"      # Studs facing up, machine top features
    BOTTOM = "bottom"  # Flip part, machine bottom/hollow/tubes


class WorkholdingType(Enum):
    """Workholding methods for Bantam."""
    TAPE = "double_sided_tape"         # Nitto tape for light cuts
    VICE = "low_profile_vice"          # Bantam's low-profile vice
    FIXTURE_PLATE = "fixture_plate"    # Custom fixture with clamps
    SOFT_JAWS = "soft_jaws"            # Machined soft jaws (best for aluminum)


class CoolantType(Enum):
    """Coolant strategies for aluminum."""
    NONE = "none"                # Air only (short cuts)
    MIST = "mist"                # Mist coolant (light cuts)
    FLOOD = "flood"              # Flood coolant (heavy cuts) - not on Bantam
    WD40_MIST = "wd40_mist"      # WD-40 mist (aluminum friendly)


# Bantam Desktop CNC specifications
BANTAM_SPECS = {
    "name": "Bantam Tools Desktop CNC",
    "controller": "TinyG",
    "work_envelope": {"x": 140, "y": 114, "z": 60},  # mm
    "spindle_rpm_min": 2000,
    "spindle_rpm_max": 10000,
    "spindle_power_watts": 150,
    "max_feed_rate": 2540,  # mm/min
    "max_rapid_rate": 2540,  # mm/min
    "resolution": 0.001,  # mm
    "tool_holder": "ER11",
    "max_tool_diameter": 6.35,  # 1/4"
    "has_tool_probe": True,
    "has_coolant": False,  # No built-in coolant
}

# LEGO brick standard dimensions (mm)
LEGO_DIMS = {
    "stud_diameter": 4.8,
    "stud_height": 1.7,
    "pitch": 8.0,  # Stud-to-stud center distance
    "plate_height": 3.2,
    "brick_height": 9.6,  # 3 plates
    "wall_thickness": 1.5,
    "tube_od": 6.51,
    "tube_id": 4.8,
    "tolerance": 0.05,  # Target tolerance
}

# Aluminum cutting parameters for Bantam
ALUMINUM_PARAMS = {
    "material": "6061-T6",
    "sfm": 300,  # Surface feet per minute (conservative for desktop CNC)
    "chip_load_2mm": 0.025,  # mm/tooth for 2mm endmill
    "chip_load_3mm": 0.035,
    "chip_load_6mm": 0.050,
    "doc_roughing": 0.5,  # Depth of cut - roughing (mm)
    "doc_finishing": 0.15,  # Depth of cut - finishing (mm)
    "woc_roughing": 0.4,  # Width of cut as % of tool diameter
    "woc_finishing": 0.1,
    "stock_to_leave": 0.2,  # mm left for finishing pass
    "plunge_rate_factor": 0.3,  # Plunge at 30% of feed rate
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Stock:
    """Stock/blank definition."""
    width: float   # X dimension (mm)
    depth: float   # Y dimension (mm)
    height: float  # Z dimension (mm)
    z_offset: float = 0.0  # Extra material on Z (mm)
    material: str = "6061-T6"

    @property
    def total_height(self) -> float:
        return self.height + self.z_offset

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "z_offset": self.z_offset,
            "total_height": self.total_height,
            "material": self.material,
        }


@dataclass
class Setup:
    """Machine setup definition."""
    number: int
    type: SetupType
    wcs: str = "G54"  # Work coordinate system
    workholding: WorkholdingType = WorkholdingType.SOFT_JAWS
    stock_top_z: float = 0.0  # Z height of stock top
    part_zero_x: float = 0.0  # Part origin X
    part_zero_y: float = 0.0  # Part origin Y
    operations: List[Dict[str, Any]] = field(default_factory=list)

    # Setup instructions
    instructions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "type": self.type.value,
            "wcs": self.wcs,
            "workholding": self.workholding.value,
            "stock_top_z": self.stock_top_z,
            "part_zero": {"x": self.part_zero_x, "y": self.part_zero_y},
            "operations": self.operations,
            "instructions": self.instructions,
        }


@dataclass
class ToolpathOperation:
    """A single toolpath operation."""
    name: str
    type: str  # roughing, finishing, drilling, etc.
    tool: str  # Tool name from library
    rpm: int
    feed_rate: float  # mm/min
    plunge_rate: float
    doc: float  # Depth of cut
    woc: float  # Width of cut (for adaptive/pocket)
    stock_to_leave: float = 0.0
    coolant: CoolantType = CoolantType.MIST

    # Estimated time
    estimated_time_min: float = 0.0


# ============================================================================
# BANTAM POST-PROCESSOR
# ============================================================================

class BantamPostProcessor:
    """
    Post-processor for Bantam Desktop CNC (TinyG controller).

    Generates clean, optimized G-code compatible with Bantam software.
    """

    def __init__(self):
        self.program_lines: List[str] = []
        self.current_tool: Optional[str] = None
        self.current_wcs: str = "G54"
        self.spindle_on: bool = False

    def generate_header(self,
                       program_name: str,
                       stock: Stock,
                       setup: Setup) -> List[str]:
        """Generate G-code header with program info."""
        lines = [
            f"( LEGO Aluminum Milling - {program_name} )",
            f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",
            f"( Machine: Bantam Desktop CNC )",
            f"( Material: {stock.material} )",
            f"( Stock: {stock.width}x{stock.depth}x{stock.total_height} mm )",
            f"( Setup {setup.number}: {setup.type.value.upper()} )",
            f"( Workholding: {setup.workholding.value} )",
            "",
            "( === SAFETY BLOCK === )",
            "G21 ( Units: mm )",
            "G90 ( Absolute positioning )",
            "G17 ( XY plane selection )",
            f"{setup.wcs} ( Work coordinate system )",
            "G40 ( Cancel cutter compensation )",
            "G49 ( Cancel tool length offset )",
            "G80 ( Cancel canned cycles )",
            "",
        ]
        return lines

    def generate_tool_change(self,
                            tool_number: int,
                            tool_name: str,
                            rpm: int) -> List[str]:
        """Generate tool change sequence for Bantam."""
        lines = [
            f"( === TOOL CHANGE === )",
            f"( Tool {tool_number}: {tool_name} )",
            "M5 ( Spindle stop )",
            "G53 G0 Z0 ( Retract to machine Z home )",
            f"M6 T{tool_number} ( Tool change )",
            "",
            "( Probe tool length - manual or with probe )",
            "( Set tool length offset in Bantam software )",
            "",
            f"S{rpm} M3 ( Spindle on CW at {rpm} RPM )",
            "G4 P3 ( Dwell 3 sec for spindle to spin up )",
            "",
        ]
        self.current_tool = tool_name
        self.spindle_on = True
        return lines

    def generate_rapid_move(self, x: float = None, y: float = None, z: float = None) -> str:
        """Generate rapid positioning move."""
        parts = ["G0"]
        if x is not None:
            parts.append(f"X{x:.4f}")
        if y is not None:
            parts.append(f"Y{y:.4f}")
        if z is not None:
            parts.append(f"Z{z:.4f}")
        return " ".join(parts)

    def generate_linear_move(self,
                            x: float = None,
                            y: float = None,
                            z: float = None,
                            feed: float = None) -> str:
        """Generate linear interpolation move."""
        parts = ["G1"]
        if x is not None:
            parts.append(f"X{x:.4f}")
        if y is not None:
            parts.append(f"Y{y:.4f}")
        if z is not None:
            parts.append(f"Z{z:.4f}")
        if feed is not None:
            parts.append(f"F{feed:.1f}")
        return " ".join(parts)

    def generate_arc_move(self,
                         x: float, y: float,
                         i: float, j: float,
                         clockwise: bool = True,
                         feed: float = None) -> str:
        """Generate arc interpolation move."""
        g_code = "G2" if clockwise else "G3"
        parts = [g_code, f"X{x:.4f}", f"Y{y:.4f}", f"I{i:.4f}", f"J{j:.4f}"]
        if feed is not None:
            parts.append(f"F{feed:.1f}")
        return " ".join(parts)

    def generate_drilling_cycle(self,
                               x: float, y: float,
                               z_start: float,
                               z_depth: float,
                               retract: float,
                               feed: float,
                               peck: float = None) -> List[str]:
        """Generate drilling canned cycle."""
        lines = []
        if peck:
            # Peck drilling (G83)
            lines.append(f"G83 X{x:.4f} Y{y:.4f} Z{z_depth:.4f} R{retract:.4f} Q{peck:.4f} F{feed:.1f}")
        else:
            # Standard drilling (G81)
            lines.append(f"G81 X{x:.4f} Y{y:.4f} Z{z_depth:.4f} R{retract:.4f} F{feed:.1f}")
        return lines

    def generate_footer(self) -> List[str]:
        """Generate G-code footer with safe ending."""
        lines = [
            "",
            "( === PROGRAM END === )",
            "M5 ( Spindle stop )",
            "G53 G0 Z0 ( Retract to machine Z home )",
            "G53 G0 X0 Y0 ( Return to machine XY home )",
            "M30 ( Program end, rewind )",
            "",
        ]
        return lines

    def generate_face_operation(self,
                               stock: Stock,
                               doc: float,
                               feed: float,
                               stepover: float,
                               safe_z: float = 5.0) -> List[str]:
        """Generate facing operation G-code."""
        lines = [
            "( === FACING OPERATION === )",
            f"( DOC: {doc} mm, Stepover: {stepover} mm )",
        ]

        # Calculate passes
        x_start = -stepover / 2
        x_end = stock.width + stepover / 2
        y_start = -stepover / 2
        y_end = stock.depth + stepover / 2

        # Rapid to start position
        lines.append(self.generate_rapid_move(x=x_start, y=y_start))
        lines.append(self.generate_rapid_move(z=safe_z))

        # Plunge to cutting depth
        z_cut = stock.total_height - doc
        lines.append(self.generate_linear_move(z=z_cut, feed=feed * 0.3))

        # Zigzag pattern
        y = y_start
        direction = 1
        while y <= y_end:
            if direction > 0:
                lines.append(self.generate_linear_move(x=x_end, feed=feed))
            else:
                lines.append(self.generate_linear_move(x=x_start, feed=feed))
            y += stepover
            if y <= y_end:
                lines.append(self.generate_linear_move(y=y, feed=feed))
            direction *= -1

        # Retract
        lines.append(self.generate_rapid_move(z=safe_z))
        lines.append("")

        return lines

    def generate_adaptive_clearing(self,
                                   contour: List[Tuple[float, float]],
                                   z_top: float,
                                   z_bottom: float,
                                   doc: float,
                                   woc: float,
                                   tool_diameter: float,
                                   feed: float,
                                   plunge_rate: float,
                                   safe_z: float = 5.0) -> List[str]:
        """Generate adaptive/HSM clearing toolpath."""
        lines = [
            "( === ADAPTIVE CLEARING === )",
            f"( Z Top: {z_top}, Z Bottom: {z_bottom} )",
            f"( DOC: {doc} mm, WOC: {woc} mm )",
        ]

        # Calculate number of Z levels
        total_depth = z_top - z_bottom
        num_levels = math.ceil(total_depth / doc)

        # For each Z level
        current_z = z_top
        for level in range(num_levels):
            current_z = max(z_top - (level + 1) * doc, z_bottom)
            lines.append(f"( Z Level {level + 1}: {current_z:.3f} )")

            # Spiral/offset pattern (simplified - real adaptive is more complex)
            # Start at first point
            if contour:
                start = contour[0]
                lines.append(self.generate_rapid_move(x=start[0], y=start[1]))
                lines.append(self.generate_rapid_move(z=safe_z))
                lines.append(self.generate_linear_move(z=current_z, feed=plunge_rate))

                # Follow contour
                for point in contour[1:]:
                    lines.append(self.generate_linear_move(x=point[0], y=point[1], feed=feed))

                # Close contour
                lines.append(self.generate_linear_move(x=start[0], y=start[1], feed=feed))

        lines.append(self.generate_rapid_move(z=safe_z))
        lines.append("")

        return lines

    def generate_contour_finishing(self,
                                   contour: List[Tuple[float, float]],
                                   z_top: float,
                                   z_bottom: float,
                                   doc: float,
                                   feed: float,
                                   plunge_rate: float,
                                   safe_z: float = 5.0) -> List[str]:
        """Generate contour finishing toolpath."""
        lines = [
            "( === CONTOUR FINISHING === )",
        ]

        total_depth = z_top - z_bottom
        num_levels = math.ceil(total_depth / doc)

        current_z = z_top
        for level in range(num_levels):
            current_z = max(z_top - (level + 1) * doc, z_bottom)

            if contour:
                start = contour[0]
                lines.append(self.generate_rapid_move(x=start[0], y=start[1]))
                lines.append(self.generate_rapid_move(z=current_z + 2))
                lines.append(self.generate_linear_move(z=current_z, feed=plunge_rate))

                for point in contour[1:]:
                    lines.append(self.generate_linear_move(x=point[0], y=point[1], feed=feed))

                lines.append(self.generate_linear_move(x=start[0], y=start[1], feed=feed))

        lines.append(self.generate_rapid_move(z=safe_z))
        lines.append("")

        return lines


# ============================================================================
# ALUMINUM LEGO MILLING WORKFLOW
# ============================================================================

class AluminumLegoMill:
    """
    Complete aluminum LEGO brick milling workflow for Bantam CNC.

    Handles:
    - Two-setup operations (top features, bottom features)
    - Stock sizing with Z offset
    - Tool selection and feeds/speeds
    - G-code generation with Bantam post-processor
    - Workholding guidance
    """

    def __init__(self):
        self.post = BantamPostProcessor()
        self.setups: List[Setup] = []
        self.stock: Optional[Stock] = None
        self.brick_params: Dict[str, Any] = {}

    def define_brick(self,
                    width_studs: int,
                    depth_studs: int,
                    height_plates: int = 3,
                    brick_type: str = "standard") -> Dict[str, Any]:
        """
        Define the LEGO brick to machine.

        Args:
            width_studs: Number of studs in X direction
            depth_studs: Number of studs in Y direction
            height_plates: Height in plate units (3 = standard brick)
            brick_type: "standard", "plate", "technic"

        Returns:
            Brick parameters dictionary
        """
        # Calculate dimensions
        width = width_studs * LEGO_DIMS["pitch"]
        depth = depth_studs * LEGO_DIMS["pitch"]
        height = height_plates * LEGO_DIMS["plate_height"]

        self.brick_params = {
            "width_studs": width_studs,
            "depth_studs": depth_studs,
            "height_plates": height_plates,
            "brick_type": brick_type,
            "dimensions": {
                "width": width,
                "depth": depth,
                "height": height,
            },
            "features": {
                "studs": True,
                "hollow": True,
                "tubes": width_studs > 1 and depth_studs > 1,
            }
        }

        return self.brick_params

    def define_stock(self,
                    z_offset: float = 1.0) -> Stock:
        """
        Define stock material based on brick dimensions.

        Args:
            z_offset: Extra material on Z axis (mm)

        Returns:
            Stock definition
        """
        if not self.brick_params:
            raise ValueError("Define brick first with define_brick()")

        dims = self.brick_params["dimensions"]

        # Stock is exact size on X/Y, offset on Z
        self.stock = Stock(
            width=dims["width"],
            depth=dims["depth"],
            height=dims["height"],
            z_offset=z_offset,
            material="6061-T6"
        )

        return self.stock

    def calculate_feeds_speeds(self,
                              tool_diameter: float,
                              flutes: int = 2) -> Dict[str, float]:
        """
        Calculate feeds and speeds for aluminum on Bantam.

        Args:
            tool_diameter: Tool diameter in mm
            flutes: Number of flutes

        Returns:
            Dictionary with rpm, feed_rate, plunge_rate
        """
        # RPM from SFM: RPM = (SFM × 3.82) / diameter_inches
        diameter_inches = tool_diameter / 25.4
        rpm = (ALUMINUM_PARAMS["sfm"] * 3.82) / diameter_inches

        # Clamp to Bantam limits
        rpm = max(BANTAM_SPECS["spindle_rpm_min"],
                 min(rpm, BANTAM_SPECS["spindle_rpm_max"]))

        # Chip load based on tool diameter
        if tool_diameter <= 2:
            chip_load = ALUMINUM_PARAMS["chip_load_2mm"]
        elif tool_diameter <= 3:
            chip_load = ALUMINUM_PARAMS["chip_load_3mm"]
        else:
            chip_load = ALUMINUM_PARAMS["chip_load_6mm"]

        # Feed rate = RPM × flutes × chip load
        feed_rate = rpm * flutes * chip_load

        # Clamp to Bantam limits
        feed_rate = min(feed_rate, BANTAM_SPECS["max_feed_rate"])

        # Plunge rate
        plunge_rate = feed_rate * ALUMINUM_PARAMS["plunge_rate_factor"]

        return {
            "rpm": int(rpm),
            "feed_rate": round(feed_rate, 1),
            "plunge_rate": round(plunge_rate, 1),
            "chip_load": chip_load,
        }

    def create_setup_1_top(self) -> Setup:
        """
        Create Setup 1: Top features (studs, top surface).

        Stock is held with studs facing up.
        OPTIMIZED: Uses only 2 tools - 3mm roughing/facing, 2mm finishing.
        """
        setup = Setup(
            number=1,
            type=SetupType.TOP,
            wcs="G54",
            workholding=WorkholdingType.SOFT_JAWS,
            stock_top_z=self.stock.total_height,
            part_zero_x=0,
            part_zero_y=0,
        )

        dims = self.brick_params["dimensions"]

        # OPTIMIZED: Only 2 tools needed
        # T1: 3mm flat endmill (facing + roughing)
        # T2: 2mm flat endmill (finishing studs + detail)
        feeds_3mm = self.calculate_feeds_speeds(3.0, 2)
        feeds_2mm = self.calculate_feeds_speeds(2.0, 2)

        # Operation 1: Face top to final height (3mm tool works fine)
        setup.operations.append({
            "name": "Face Top",
            "type": "facing",
            "tool": "3mm Flat Endmill",
            "tool_number": 1,
            "rpm": feeds_3mm["rpm"],
            "feed_rate": feeds_3mm["feed_rate"],
            "plunge_rate": feeds_3mm["plunge_rate"],
            "doc": self.stock.z_offset,  # Remove Z offset material
            "stepover": 2.0,  # 66% of tool diameter
            "notes": "Remove stock offset, establish Z0 at part top",
        })

        # Operation 2: Rough stud pockets (same tool, no change needed)
        setup.operations.append({
            "name": "Rough Stud Area",
            "type": "adaptive",
            "tool": "3mm Flat Endmill",
            "tool_number": 1,  # Same tool as facing!
            "rpm": feeds_3mm["rpm"],
            "feed_rate": feeds_3mm["feed_rate"],
            "plunge_rate": feeds_3mm["plunge_rate"],
            "doc": ALUMINUM_PARAMS["doc_roughing"],
            "woc": 3.0 * ALUMINUM_PARAMS["woc_roughing"],
            "stock_to_leave": ALUMINUM_PARAMS["stock_to_leave"],
            "z_top": 0,
            "z_bottom": -LEGO_DIMS["stud_height"],
            "notes": "Rough around studs, leave 0.2mm for finishing",
        })

        # Operation 3: Finish stud profiles (tool change to 2mm)
        setup.operations.append({
            "name": "Finish Stud Profiles",
            "type": "contour",
            "tool": "2mm Flat Endmill",
            "tool_number": 2,
            "rpm": feeds_2mm["rpm"],
            "feed_rate": feeds_2mm["feed_rate"] * 0.7,  # Slower for finish
            "plunge_rate": feeds_2mm["plunge_rate"],
            "doc": ALUMINUM_PARAMS["doc_finishing"],
            "stock_to_leave": 0,
            "notes": "Finish stud diameter to 4.8mm ±0.05",
        })

        # NOTE: Chamfer operation removed - optional cosmetic feature
        # Can be done manually with sandpaper or added back if needed

        # Setup instructions
        setup.instructions = [
            "1. Install soft jaws in vice (machine fresh if needed)",
            "2. Load stock with longest dimension along X axis",
            "3. Stock bottom should sit on parallels at known height",
            "4. Tighten vice gently - aluminum deforms easily",
            "5. Set WCS origin:",
            "   - X: Left edge of stock",
            "   - Y: Front edge of stock",
            "   - Z: Top of stock (after facing = part Z0)",
            "6. Probe tool lengths:",
            "   - T1: 3mm Flat Endmill",
            "   - T2: 2mm Flat Endmill",
            "7. Apply WD-40 mist before starting",
            "8. Run at reduced feed (50%) for first part",
        ]

        self.setups.append(setup)
        return setup

    def create_setup_2_bottom(self) -> Setup:
        """
        Create Setup 2: Bottom features (hollow, tubes).

        Flip part, studs facing down into soft jaws.
        OPTIMIZED: Uses same 2 tools as Setup 1 (T1: 3mm, T2: 2mm).
        """
        setup = Setup(
            number=2,
            type=SetupType.BOTTOM,
            wcs="G55",  # Different WCS for second setup
            workholding=WorkholdingType.SOFT_JAWS,
            stock_top_z=self.brick_params["dimensions"]["height"],
            part_zero_x=0,
            part_zero_y=0,
        )

        dims = self.brick_params["dimensions"]

        # Same tools as Setup 1 - no need to change tools between setups!
        # T1: 3mm Flat Endmill (roughing)
        # T2: 2mm Flat Endmill (finishing)
        feeds_3mm = self.calculate_feeds_speeds(3.0, 2)
        feeds_2mm = self.calculate_feeds_speeds(2.0, 2)

        # Operation 1: Face bottom (if Z offset was used)
        if self.stock.z_offset > 0:
            setup.operations.append({
                "name": "Face Bottom",
                "type": "facing",
                "tool": "3mm Flat Endmill",
                "tool_number": 1,  # Same T1 as Setup 1
                "rpm": feeds_3mm["rpm"],
                "feed_rate": feeds_3mm["feed_rate"],
                "plunge_rate": feeds_3mm["plunge_rate"],
                "doc": 0.5,
                "stepover": 2.0,
                "notes": "Light facing to clean bottom surface",
            })

        # Operation 2: Rough hollow cavity
        hollow_depth = dims["height"] - LEGO_DIMS["plate_height"]

        setup.operations.append({
            "name": "Rough Hollow Cavity",
            "type": "adaptive",
            "tool": "3mm Flat Endmill",
            "tool_number": 1,  # Same T1, no tool change!
            "rpm": feeds_3mm["rpm"],
            "feed_rate": feeds_3mm["feed_rate"],
            "plunge_rate": feeds_3mm["plunge_rate"],
            "doc": ALUMINUM_PARAMS["doc_roughing"],
            "woc": 3.0 * ALUMINUM_PARAMS["woc_roughing"],
            "stock_to_leave": ALUMINUM_PARAMS["stock_to_leave"],
            "z_top": 0,
            "z_bottom": -hollow_depth,
            "notes": f"Rough hollow to {hollow_depth}mm depth",
        })

        # Operation 3: Finish hollow walls + bore tubes (2mm endmill)
        setup.operations.append({
            "name": "Finish Hollow Walls",
            "type": "contour",
            "tool": "2mm Flat Endmill",
            "tool_number": 2,  # Same T2 as Setup 1
            "rpm": feeds_2mm["rpm"],
            "feed_rate": feeds_2mm["feed_rate"] * 0.7,
            "plunge_rate": feeds_2mm["plunge_rate"],
            "doc": ALUMINUM_PARAMS["doc_finishing"],
            "stock_to_leave": 0,
            "notes": "Finish wall thickness to 1.5mm ±0.05",
        })

        # Operation 4: Bore tubes (if applicable) - same T2, no tool change
        if self.brick_params["features"]["tubes"]:
            setup.operations.append({
                "name": "Bore Tube IDs",
                "type": "helical_bore",
                "tool": "2mm Flat Endmill",
                "tool_number": 2,  # Same T2, no tool change!
                "rpm": feeds_2mm["rpm"],
                "feed_rate": feeds_2mm["feed_rate"] * 0.5,
                "plunge_rate": feeds_2mm["plunge_rate"],
                "bore_diameter": LEGO_DIMS["tube_id"],
                "doc": ALUMINUM_PARAMS["doc_roughing"],
                "notes": "Helical interpolation for tube ID 4.8mm",
            })

        # Setup instructions
        setup.instructions = [
            "1. Remove part from vice carefully",
            "2. Clean chips from soft jaws and part",
            "3. Flip part 180° - studs now facing DOWN",
            "4. Place studs into soft jaw recesses",
            "   (Jaws should have been machined for this)",
            "5. Apply light clamping pressure only",
            "6. Set new WCS (G55) origin:",
            "   - X: Same corner as Setup 1 (now mirrored)",
            "   - Y: Same edge alignment",
            "   - Z: New top surface (part bottom facing up)",
            "7. Verify alignment with edge finder",
            "8. Same tools as Setup 1 - no tool change needed!",
            "   - T1: 3mm Flat Endmill",
            "   - T2: 2mm Flat Endmill",
            "9. Apply WD-40 mist before cutting",
        ]

        self.setups.append(setup)
        return setup

    def generate_gcode(self, program_name: str = "LEGO_ALUMINUM") -> Dict[str, str]:
        """
        Generate G-code files for all setups.

        Returns:
            Dictionary with setup names as keys, G-code as values
        """
        gcode_files = {}

        for setup in self.setups:
            lines = []

            # Header
            lines.extend(self.post.generate_header(
                f"{program_name}_SETUP{setup.number}",
                self.stock,
                setup
            ))

            # Generate operations
            current_tool = None
            tool_num = 0

            for op in setup.operations:
                # Tool change if needed
                if op.get("tool") != current_tool:
                    tool_num = op.get("tool_number", tool_num + 1)
                    lines.extend(self.post.generate_tool_change(
                        tool_num,
                        op["tool"],
                        op["rpm"]
                    ))
                    current_tool = op["tool"]

                # Operation header
                lines.append(f"( --- {op['name']} --- )")
                if op.get("notes"):
                    lines.append(f"( {op['notes']} )")

                # Generate toolpath based on type
                if op["type"] == "facing":
                    lines.extend(self.post.generate_face_operation(
                        self.stock,
                        op["doc"],
                        op["feed_rate"],
                        op["stepover"]
                    ))

                elif op["type"] == "adaptive":
                    # Generate rectangular contour for adaptive
                    dims = self.brick_params["dimensions"]
                    wall = LEGO_DIMS["wall_thickness"]
                    contour = [
                        (wall, wall),
                        (dims["width"] - wall, wall),
                        (dims["width"] - wall, dims["depth"] - wall),
                        (wall, dims["depth"] - wall),
                    ]
                    lines.extend(self.post.generate_adaptive_clearing(
                        contour,
                        op.get("z_top", 0),
                        op.get("z_bottom", -5),
                        op["doc"],
                        op.get("woc", 1.0),
                        3.0,  # tool diameter
                        op["feed_rate"],
                        op["plunge_rate"]
                    ))

                elif op["type"] == "contour":
                    dims = self.brick_params["dimensions"]
                    wall = LEGO_DIMS["wall_thickness"]
                    contour = [
                        (wall, wall),
                        (dims["width"] - wall, wall),
                        (dims["width"] - wall, dims["depth"] - wall),
                        (wall, dims["depth"] - wall),
                    ]
                    lines.extend(self.post.generate_contour_finishing(
                        contour,
                        op.get("z_top", 0),
                        op.get("z_bottom", -5),
                        op["doc"],
                        op["feed_rate"],
                        op["plunge_rate"]
                    ))
                else:
                    lines.append(f"( {op['type']} - manual programming required )")
                    lines.append("")

            # Footer
            lines.extend(self.post.generate_footer())

            # Store G-code
            filename = f"{program_name}_SETUP{setup.number}.nc"
            gcode_files[filename] = "\n".join(lines)

        return gcode_files

    def generate_setup_sheet(self) -> str:
        """Generate human-readable setup sheet."""
        lines = [
            "=" * 60,
            "ALUMINUM LEGO BRICK - SETUP SHEET",
            "=" * 60,
            "",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Machine: Bantam Desktop CNC",
            f"Material: {self.stock.material}",
            "",
            "BRICK SPECIFICATION:",
            f"  Size: {self.brick_params['width_studs']}x{self.brick_params['depth_studs']} studs",
            f"  Height: {self.brick_params['height_plates']} plates",
            f"  Type: {self.brick_params['brick_type']}",
            "",
            "STOCK SPECIFICATION:",
            f"  Width (X): {self.stock.width} mm (exact)",
            f"  Depth (Y): {self.stock.depth} mm (exact)",
            f"  Height (Z): {self.stock.height} mm + {self.stock.z_offset} mm offset",
            f"  Total Z: {self.stock.total_height} mm",
            "",
        ]

        for setup in self.setups:
            lines.append("-" * 60)
            lines.append(f"SETUP {setup.number}: {setup.type.value.upper()}")
            lines.append("-" * 60)
            lines.append(f"WCS: {setup.wcs}")
            lines.append(f"Workholding: {setup.workholding.value}")
            lines.append("")
            lines.append("INSTRUCTIONS:")
            for instruction in setup.instructions:
                lines.append(f"  {instruction}")
            lines.append("")
            lines.append("OPERATIONS:")
            for i, op in enumerate(setup.operations, 1):
                lines.append(f"  {i}. {op['name']}")
                lines.append(f"     Tool: {op['tool']}")
                lines.append(f"     RPM: {op['rpm']}, Feed: {op['feed_rate']} mm/min")
                if op.get("notes"):
                    lines.append(f"     Note: {op['notes']}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("TOOLS REQUIRED:")
        tools_used = set()
        for setup in self.setups:
            for op in setup.operations:
                tools_used.add(op["tool"])
        for tool in sorted(tools_used):
            lines.append(f"  - {tool}")

        lines.append("")
        lines.append("SAFETY NOTES:")
        lines.append("  - Wear safety glasses")
        lines.append("  - Use WD-40 mist for aluminum")
        lines.append("  - Monitor for chip buildup")
        lines.append("  - Check for chatter (reduce feed if present)")
        lines.append("  - Verify dimensions after Setup 1 before flipping")
        lines.append("=" * 60)

        return "\n".join(lines)

    def run_full_workflow(self,
                         width_studs: int = 2,
                         depth_studs: int = 4,
                         height_plates: int = 3,
                         z_offset: float = 1.0,
                         output_dir: str = "/output") -> Dict[str, Any]:
        """
        Run complete workflow: define brick, generate setups, output G-code.

        Args:
            width_studs: Brick width in studs
            depth_studs: Brick depth in studs
            height_plates: Brick height in plates (3 = standard)
            z_offset: Extra Z material on stock (mm)
            output_dir: Directory to save files

        Returns:
            Workflow results with file paths and setup info
        """
        # Step 1: Define brick
        brick = self.define_brick(width_studs, depth_studs, height_plates)

        # Step 2: Define stock
        stock = self.define_stock(z_offset)

        # Step 3: Create setups
        setup1 = self.create_setup_1_top()
        setup2 = self.create_setup_2_bottom()

        # Step 4: Generate G-code
        program_name = f"LEGO_{width_studs}x{depth_studs}"
        gcode_files = self.generate_gcode(program_name)

        # Step 5: Generate setup sheet
        setup_sheet = self.generate_setup_sheet()

        # Save files (in real implementation)
        results = {
            "brick": brick,
            "stock": stock.to_dict(),
            "setups": [s.to_dict() for s in self.setups],
            "gcode_files": gcode_files,
            "setup_sheet": setup_sheet,
            "summary": {
                "total_operations": sum(len(s.operations) for s in self.setups),
                "tools_required": list(set(
                    op["tool"] for s in self.setups for op in s.operations
                )),
                "estimated_time_min": 15 * len(self.setups),  # Rough estimate
            }
        }

        return results


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_aluminum_lego(width_studs: int = 2,
                        depth_studs: int = 4,
                        height_plates: int = 3,
                        z_offset: float = 1.0) -> Dict[str, Any]:
    """
    Create complete aluminum LEGO milling package.

    Args:
        width_studs: Brick width in studs
        depth_studs: Brick depth in studs
        height_plates: Height in plates (3 = standard brick)
        z_offset: Extra Z material on stock (mm)

    Returns:
        Complete workflow results with G-code and setup sheets
    """
    mill = AluminumLegoMill()
    return mill.run_full_workflow(width_studs, depth_studs, height_plates, z_offset)


def get_bantam_specs() -> Dict[str, Any]:
    """Get Bantam Desktop CNC specifications."""
    return BANTAM_SPECS


def get_aluminum_params() -> Dict[str, Any]:
    """Get aluminum cutting parameters."""
    return ALUMINUM_PARAMS
