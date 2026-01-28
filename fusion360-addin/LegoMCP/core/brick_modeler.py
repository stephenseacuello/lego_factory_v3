"""
BrickModeler - Parametric LEGO brick generation for Fusion 360

This module creates accurate LEGO-compatible bricks using the Fusion 360 API.
All dimensions follow official LEGO specifications.

Manufacturing-style operation routing ensures correct build order:
    Op 010 - Create base block
    Op 020 - Hollow interior
    Op 030 - Add tubes (for 2x2+ bricks)
    Op 040 - Add ribs (for 1xN bricks)
    Op 050 - Add studs
"""

import adsk.core
import adsk.fusion
import math
import sys
import traceback
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass


def _log(message: str, error: bool = False):
    """Log message to Fusion 360 console."""
    stream = sys.stderr if error else sys.stdout
    try:
        print(f"[BrickModeler] {message}", file=stream, flush=True)
    except:
        pass


# === LEGO Dimension Constants (mm) ===
# Duplicated here to avoid import issues in Fusion 360 environment
# Updated to v2.0 specifications based on official LEGO measurements

# Fundamental unit
LDU = 1.6  # LEGO Design Unit - base measurement (all dims are multiples)
STUD_PITCH = 8.0  # Distance between stud centers (5 LDU)

# Stud dimensions
STUD_DIAMETER = 4.8  # Cylinder on top (3 LDU)
STUD_HEIGHT = 1.7  # Height above brick surface

# Heights
BRICK_HEIGHT = 9.6  # Standard brick (6 LDU, 3 plates)
PLATE_HEIGHT = 3.2  # Plate = 1/3 brick height (2 LDU)

# CORRECTED: Wall structure (v2.0)
WALL_THICKNESS = 1.6  # CORRECTED: 1.5 -> 1.6 (1 LDU) per official specs
TOP_THICKNESS = 1.0  # Top surface thickness

# CORRECTED: Inter-brick clearance (v2.0)
CLEARANCE_PER_SIDE = 0.1  # NEW: Gap per brick side for proper fit
INTER_BRICK_GAP = 0.2  # NEW: Total gap between adjacent bricks

# Bottom tubes (for clutch power)
TUBE_OD = 6.51  # Tube outer diameter
TUBE_ID = 4.8  # Tube inner diameter (matches stud for grip)

# CORRECTED: Bottom ribs (v2.0)
RIB_THICKNESS = 1.0
RIB_BOTTOM_RECESS = 0.0  # CORRECTED: 2.0 -> 0.0 (ribs extend full height)

# CORRECTED: Technic dimensions (v2.0)
TECHNIC_PIN_HOLE_DIAMETER = 4.9  # CORRECTED: 4.8 -> 4.9 (for bearing fit)
TECHNIC_AXLE_HOLE_SIZE = 4.8  # Cross-shaped axle hole

# NEW: Bar/rod constants (v2.0)
BAR_DIAMETER = 3.18  # Standard bar diameter (minifig hand grip)

# LEGO Color Map - RGB values for classic LEGO colors
# Format: (R, G, B) where values are 0-255
LEGO_COLORS = {
    "red": (196, 40, 27),
    "bright_red": (196, 40, 27),
    "blue": (0, 85, 165),
    "bright_blue": (0, 85, 165),
    "yellow": (242, 205, 55),
    "bright_yellow": (242, 205, 55),
    "green": (35, 120, 65),
    "dark_green": (0, 69, 26),
    "bright_green": (75, 151, 74),
    "lime": (154, 202, 60),
    "black": (33, 33, 33),
    "white": (244, 244, 244),
    "orange": (254, 138, 24),
    "bright_orange": (254, 138, 24),
    "dark_orange": (169, 85, 0),
    "tan": (228, 205, 158),
    "brick_yellow": (228, 205, 158),
    "brown": (88, 57, 39),
    "reddish_brown": (88, 57, 39),
    "dark_brown": (53, 33, 0),
    "light_gray": (160, 165, 169),
    "light_bluish_gray": (160, 165, 169),
    "dark_gray": (99, 95, 97),
    "dark_bluish_gray": (99, 95, 97),
    "pink": (252, 151, 172),
    "bright_pink": (252, 151, 172),
    "magenta": (200, 80, 155),
    "purple": (129, 0, 123),
    "dark_purple": (63, 26, 98),
    "lavender": (180, 168, 209),
    "sand_blue": (96, 116, 161),
    "sand_green": (118, 149, 136),
    "dark_azure": (0, 138, 189),
    "medium_azure": (54, 174, 191),
    "light_aqua": (173, 221, 237),
    "coral": (255, 109, 119),
    "neon_orange": (255, 128, 13),
    "neon_green": (216, 255, 68),
    "trans_clear": (252, 252, 252),
    "trans_red": (196, 40, 27),
    "trans_blue": (0, 85, 165),
    "trans_yellow": (242, 205, 55),
    "trans_green": (35, 120, 65),
    "trans_orange": (254, 138, 24),
}


@dataclass
class BrickResult:
    """Result of brick creation operation."""
    success: bool
    brick_id: str
    component_name: str
    dimensions: Dict[str, float]
    volume_mm3: float
    error: Optional[str] = None


class BrickModeler:
    """
    Creates parametric LEGO bricks in Fusion 360.
    
    Usage:
        modeler = BrickModeler(app)
        result = modeler.create_standard_brick(2, 4)  # 2x4 brick
    """
    
    def __init__(self, app: adsk.core.Application):
        self.app = app
        self._brick_counter = 0
        
    @property
    def design(self) -> adsk.fusion.Design:
        """Get active design, create if needed."""
        product = self.app.activeProduct
        if not product or product.objectType != adsk.fusion.Design.classType():
            # Create new design
            doc = self.app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            product = self.app.activeProduct
        return adsk.fusion.Design.cast(product)
    
    @property
    def root(self) -> adsk.fusion.Component:
        """Get root component."""
        return self.design.rootComponent
    
    def _cm(self, mm: float) -> float:
        """Convert mm to cm (Fusion 360 uses cm internally)."""
        return mm / 10.0
    
    def _generate_brick_id(self, prefix: str = "brick") -> str:
        """Generate unique brick ID."""
        self._brick_counter += 1
        return f"{prefix}_{self._brick_counter:04d}"
    
    def create_standard_brick(
        self,
        studs_x: int,
        studs_y: int,
        height_units: float = 1.0,
        hollow: bool = True,
        center_rib: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a standard LEGO brick using manufacturing-style operation routing.

        Operation Sequence (BOM Style):
            Op 010 - Create base block (NEW)
            Op 020 - Hollow interior (CUT)
            Op 030 - Add tubes for 2x2+ bricks (JOIN)
            Op 035 - Add center rib/spine for 2xN bricks (JOIN)
            Op 040 - Add ribs for 1xN bricks (JOIN)
            Op 050 - Add studs (JOIN)
            Op 060 - Apply color (APPEARANCE)

        Args:
            studs_x: Number of studs in X direction (1-16)
            studs_y: Number of studs in Y direction (1-16)
            height_units: Height in brick units (1.0 = standard, 0.333 = plate)
            hollow: Whether to hollow out the bottom
            center_rib: Whether to add center rib/spine (like real LEGO 2xN bricks)
            name: Custom component name
            color: LEGO color name (red, blue, yellow, green, black, white, orange, etc.)

        Returns:
            BrickResult with brick info and any operation errors
        """
        errors = []  # Collect all operation errors

        _log(f"=== Creating brick: {studs_x}x{studs_y}, height={height_units}, hollow={hollow} ===")

        try:
            # Calculate dimensions
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            _log(f"Dimensions: {width}mm x {depth}mm x {height}mm")

            # Generate IDs/names
            brick_id = self._generate_brick_id()
            comp_name = name or (f"Plate_{studs_x}x{studs_y}" if height_units < 0.5
                                else f"Brick_{studs_x}x{studs_y}")

            # Create new component
            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # ══════════════════════════════════════════════════════════
            # Op 010: CREATE BASE BLOCK (NewBodyFeatureOperation)
            # ══════════════════════════════════════════════════════════
            _log("Op 010: Creating base block...")
            op_010_success = self._op_010_create_base(comp, width, depth, height)
            if not op_010_success:
                _log("Op 010 FAILED: Base block creation", error=True)
                errors.append("Op 010 FAILED: Base block creation")
                raise Exception("Cannot proceed without base body")

            # Validate: Must have exactly 1 body
            if comp.bRepBodies.count != 1:
                _log(f"Op 010 VALIDATION FAILED: Expected 1 body, got {comp.bRepBodies.count}", error=True)
                errors.append(f"Op 010 VALIDATION FAILED: Expected 1 body, got {comp.bRepBodies.count}")
                raise Exception("Base body validation failed")

            initial_volume = comp.bRepBodies.item(0).volume
            _log(f"Op 010 SUCCESS: Created base body, volume={initial_volume:.4f} cm³")

            # ══════════════════════════════════════════════════════════
            # Op 020: HOLLOW INTERIOR (CutFeatureOperation)
            # Must happen BEFORE tubes/ribs (they fill the cavity)
            # ══════════════════════════════════════════════════════════
            if hollow and height_units >= 0.333:
                _log("Op 020: Hollowing interior...")
                op_020_success = self._op_020_hollow(comp, width, depth, height)
                if not op_020_success:
                    _log("Op 020 FAILED: Hollow interior cut", error=True)
                    errors.append("Op 020 FAILED: Hollow interior cut")
                else:
                    current_volume = comp.bRepBodies.item(0).volume
                    volume_reduction = (1 - current_volume / initial_volume) * 100
                    _log(f"Op 020 SUCCESS: Hollowed, volume reduced by {volume_reduction:.1f}%")

                # ══════════════════════════════════════════════════════
                # Op 030/040: INTERNAL STRUCTURE (JoinFeatureOperation)
                # Must happen AFTER hollow, BEFORE studs
                # ══════════════════════════════════════════════════════
                if studs_x > 1 and studs_y > 1:
                    # Op 030: Add tubes for 2x2+ bricks
                    expected_tubes = (studs_x - 1) * (studs_y - 1)
                    _log(f"Op 030: Adding {expected_tubes} tubes for {studs_x}x{studs_y} brick...")
                    op_030_success = self._op_030_add_tubes(comp, studs_x, studs_y, height)
                    if not op_030_success:
                        _log("Op 030 WARNING: Some tubes may not have been created", error=True)
                        errors.append("Op 030 WARNING: Some tubes may not have been created")
                    else:
                        _log(f"Op 030 SUCCESS: Tubes added")

                    # Op 035: Add center rib/spine for 2xN bricks (connects tubes)
                    if center_rib and (studs_x == 2 or studs_y == 2) and max(studs_x, studs_y) >= 3:
                        _log(f"Op 035: Adding center rib for 2xN brick...")
                        op_035_success = self._op_035_add_center_rib(comp, studs_x, studs_y, height)
                        if not op_035_success:
                            _log("Op 035 WARNING: Center rib may not have been created", error=True)
                            errors.append("Op 035 WARNING: Center rib may not have been created")
                        else:
                            _log(f"Op 035 SUCCESS: Center rib added")

                elif studs_x == 1 or studs_y == 1:
                    # Op 040: Add ribs for 1xN bricks
                    rib_count = max(studs_x, studs_y) - 1
                    _log(f"Op 040: Adding {rib_count} ribs for 1xN brick...")
                    op_040_success = self._op_040_add_ribs(comp, studs_x, studs_y, height)
                    if not op_040_success:
                        _log("Op 040 WARNING: Some ribs may not have been created", error=True)
                        errors.append("Op 040 WARNING: Some ribs may not have been created")
                    else:
                        _log(f"Op 040 SUCCESS: Ribs added")

                elif studs_x >= 3 and studs_y >= 3:
                    # Op 036: Add cross-ribs for larger bricks (3x3, 4x4, etc.)
                    # These bricks have a grid of tubes and need cross-ribs connecting them
                    _log(f"Op 036: Adding cross-ribs for {studs_x}x{studs_y} brick...")
                    op_036_success = self._op_036_add_cross_ribs(comp, studs_x, studs_y, height)
                    if not op_036_success:
                        _log("Op 036 WARNING: Cross-ribs may not have been created", error=True)
                        errors.append("Op 036 WARNING: Cross-ribs may not have been created")
                    else:
                        _log(f"Op 036 SUCCESS: Cross-ribs added")

            # ══════════════════════════════════════════════════════════
            # Op 050: ADD STUDS (JoinFeatureOperation)
            # Must be LAST geometry operation (top face is final)
            # ══════════════════════════════════════════════════════════
            expected_studs = studs_x * studs_y
            _log(f"Op 050: Adding {expected_studs} studs on top...")
            op_050_success = self._op_050_add_studs(comp, studs_x, studs_y, height)
            if not op_050_success:
                _log("Op 050 FAILED: Stud creation", error=True)
                errors.append("Op 050 FAILED: Stud creation")
            else:
                _log(f"Op 050 SUCCESS: Studs added")

            # ══════════════════════════════════════════════════════════
            # Op 060: APPLY COLOR (Appearance)
            # Apply LEGO color to the brick bodies
            # ══════════════════════════════════════════════════════════
            if color:
                _log(f"Op 060: Applying color '{color}'...")
                op_060_success = self._op_060_apply_color(comp, color)
                if not op_060_success:
                    _log(f"Op 060 WARNING: Color '{color}' could not be applied", error=True)
                    errors.append(f"Op 060 WARNING: Color '{color}' could not be applied")
                else:
                    _log(f"Op 060 SUCCESS: Color '{color}' applied")

            # Calculate final volume
            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width,
                    "depth_mm": depth,
                    "height_mm": height,
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(
                success=False,
                brick_id="",
                component_name="",
                dimensions={},
                volume_mm3=0,
                error="; ".join(errors)
            )

    def create_slope_brick(
        self,
        studs_x: int,
        studs_y: int,
        height_units: float = 1.0,
        slope_angle: int = 45,
        slope_direction: str = "front",
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO slope brick with angled top surface.

        Operation Sequence:
            Op 010 - Create base block (NEW)
            Op 020 - Hollow interior (CUT)
            Op 070 - Cut slope angle (CUT)
            Op 050 - Add studs on flat portion (JOIN)
            Op 060 - Apply color (APPEARANCE)

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            height_units: Height in brick units (1.0 = standard)
            slope_angle: Angle of slope (18, 25, 33, 45, 65, 75 degrees)
            slope_direction: Direction of slope (front, back, left, right)
            hollow: Whether to hollow out the bottom
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with brick info
        """
        errors = []
        _log(f"=== Creating slope brick: {studs_x}x{studs_y}, angle={slope_angle}°, dir={slope_direction} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("slope")
            comp_name = name or f"Slope_{slope_angle}_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base block
            _log("Op 010: Creating base block...")
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow interior
            if hollow:
                _log("Op 020: Hollowing interior...")
                if not self._op_020_hollow(comp, width, depth, height):
                    errors.append("Op 020 WARNING: Hollow failed")

            # Op 070: Cut slope
            _log(f"Op 070: Cutting {slope_angle}° slope...")
            if not self._op_070_cut_slope(comp, width, depth, height, slope_angle, slope_direction):
                errors.append("Op 070 FAILED: Slope cut")
            else:
                _log("Op 070 SUCCESS: Slope cut complete")

            # Op 050: Add studs (only on flat portion)
            stud_rows = max(1, studs_y - 1) if slope_direction in ["front", "back"] else studs_y
            stud_cols = max(1, studs_x - 1) if slope_direction in ["left", "right"] else studs_x
            _log(f"Op 050: Adding studs on flat area ({stud_cols}x{stud_rows})...")
            # For slopes, we add studs at the back (non-sloped) portion
            self._op_050_add_studs_slope(comp, studs_x, studs_y, height, slope_direction)

            # Op 060: Apply color
            if color:
                _log(f"Op 060: Applying color '{color}'...")
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width,
                    "depth_mm": depth,
                    "height_mm": height,
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "slope_angle": slope_angle,
                    "slope_direction": slope_direction,
                    "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(
                success=False,
                brick_id="",
                component_name="",
                dimensions={},
                volume_mm3=0,
                error="; ".join(errors)
            )

    def create_arch_brick(
        self,
        studs_x: int,
        studs_y: int,
        height_units: float = 1.0,
        arch_height_studs: int = 1,
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO arch brick with curved cutout.

        Operation Sequence:
            Op 010 - Create base block (NEW)
            Op 080 - Cut arch opening (CUT)
            Op 050 - Add studs on top (JOIN)
            Op 060 - Apply color (APPEARANCE)

        Args:
            studs_x: Number of studs in X direction (width of arch span)
            studs_y: Number of studs in Y direction (depth/thickness)
            height_units: Height in brick units
            arch_height_studs: Height of arch opening in stud units
            hollow: Whether to hollow non-arch areas
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with brick info
        """
        errors = []
        _log(f"=== Creating arch brick: {studs_x}x{studs_y}, arch_height={arch_height_studs} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT
            arch_height = arch_height_studs * STUD_PITCH

            brick_id = self._generate_brick_id("arch")
            comp_name = name or f"Arch_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base block
            _log("Op 010: Creating base block...")
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 080: Cut arch
            _log(f"Op 080: Cutting arch opening...")
            if not self._op_080_cut_arch(comp, width, depth, height, arch_height):
                errors.append("Op 080 WARNING: Arch cut failed")
            else:
                _log("Op 080 SUCCESS: Arch cut complete")

            # Op 050: Add studs
            _log(f"Op 050: Adding studs...")
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                _log(f"Op 060: Applying color '{color}'...")
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width,
                    "depth_mm": depth,
                    "height_mm": height,
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "arch_height": arch_height,
                    "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(
                success=False,
                brick_id="",
                component_name="",
                dimensions={},
                volume_mm3=0,
                error="; ".join(errors)
            )

    def create_round_brick(
        self,
        diameter_studs: int,
        height_units: float = 1.0,
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a cylindrical LEGO brick (round 1x1, 2x2, etc).

        Operation Sequence:
            Op 010 - Create cylinder base (NEW)
            Op 020 - Hollow interior (CUT)
            Op 050 - Add central stud(s) (JOIN)
            Op 060 - Apply color (APPEARANCE)

        Args:
            diameter_studs: Diameter in stud units (1, 2, 4)
            height_units: Height in brick units
            hollow: Whether to hollow out the bottom
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with brick info
        """
        errors = []
        _log(f"=== Creating round brick: {diameter_studs}x{diameter_studs}, height={height_units} ===")

        try:
            diameter = diameter_studs * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("round")
            comp_name = name or f"Round_{diameter_studs}x{diameter_studs}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create cylinder base
            _log("Op 010: Creating cylinder base...")
            if not self._op_010_create_cylinder(comp, diameter, height):
                errors.append("Op 010 FAILED")
                raise Exception("Cylinder base failed")

            # Op 020: Hollow interior
            if hollow and diameter_studs >= 2:
                _log("Op 020: Hollowing interior...")
                if not self._op_020_hollow_cylinder(comp, diameter, height):
                    errors.append("Op 020 WARNING: Hollow failed")

            # Op 035: Add internal tube for stud grip
            if hollow and diameter_studs >= 1:
                _log("Op 035: Adding internal tube...")
                if not self._op_035_add_tube_round(comp, diameter, height):
                    errors.append("Op 035 WARNING: Tube failed")

            # Op 050: Add studs
            _log(f"Op 050: Adding studs...")
            self._op_050_add_studs_round(comp, diameter_studs, height)

            # Op 060: Apply color
            if color:
                _log(f"Op 060: Applying color '{color}'...")
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "diameter_mm": diameter,
                    "height_mm": height,
                    "diameter_studs": diameter_studs,
                    "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(
                success=False,
                brick_id="",
                component_name="",
                dimensions={},
                volume_mm3=0,
                error="; ".join(errors)
            )

    def create_technic_brick(
        self,
        studs_x: int,
        studs_y: int,
        height_units: float = 1.0,
        hole_axis: str = "x",
        hole_type: str = "pin",
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO Technic brick with holes.

        Operation Sequence:
            Op 010 - Create base block (NEW)
            Op 020 - Hollow interior (CUT)
            Op 100 - Add Technic holes (CUT)
            Op 050 - Add studs on top (JOIN)
            Op 060 - Apply color (APPEARANCE)

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            height_units: Height in brick units
            hole_axis: Axis for holes (x, y)
            hole_type: Type of holes (pin, axle, both)
            hollow: Whether to hollow out the bottom
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with brick info
        """
        errors = []
        _log(f"=== Creating Technic brick: {studs_x}x{studs_y}, holes along {hole_axis} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("technic")
            comp_name = name or f"Technic_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base block
            _log("Op 010: Creating base block...")
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow interior
            if hollow:
                _log("Op 020: Hollowing interior...")
                if not self._op_020_hollow(comp, width, depth, height):
                    errors.append("Op 020 WARNING: Hollow failed")

            # Op 030/040: Internal structure
            if studs_x > 1 and studs_y > 1:
                self._op_030_add_tubes(comp, studs_x, studs_y, height)
            elif studs_x == 1 or studs_y == 1:
                self._op_040_add_ribs(comp, studs_x, studs_y, height)

            # Op 100: Add Technic holes
            _log(f"Op 100: Adding Technic holes along {hole_axis} axis...")
            if not self._op_100_add_technic_holes(comp, studs_x, studs_y, height, hole_axis, hole_type):
                errors.append("Op 100 WARNING: Some holes failed")
            else:
                _log("Op 100 SUCCESS: Technic holes added")

            # Op 050: Add studs
            _log(f"Op 050: Adding studs...")
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                _log(f"Op 060: Applying color '{color}'...")
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width,
                    "depth_mm": depth,
                    "height_mm": height,
                    "studs_x": studs_x,
                    "studs_y": studs_y,
                    "hole_axis": hole_axis,
                    "hole_type": hole_type,
                    "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(
                success=False,
                brick_id="",
                component_name="",
                dimensions={},
                volume_mm3=0,
                error="; ".join(errors)
            )

    def create_wedge_brick(
        self,
        studs_x: int,
        studs_y: int,
        height_units: float = 1.0,
        wedge_direction: str = "right",
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO wedge brick (tapers to a point on one side).

        Operation Sequence:
            Op 010 - Create base block (NEW)
            Op 020 - Hollow interior (CUT)
            Op 075 - Cut wedge angle (CUT)
            Op 050 - Add studs (JOIN)
            Op 060 - Apply color (APPEARANCE)

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            height_units: Height in brick units
            wedge_direction: Direction of taper (left, right, front, back)
            hollow: Whether to hollow out the bottom
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with brick info
        """
        errors = []
        _log(f"=== Creating wedge brick: {studs_x}x{studs_y}, wedge={wedge_direction} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("wedge")
            comp_name = name or f"Wedge_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base block
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow interior
            if hollow:
                self._op_020_hollow(comp, width, depth, height)

            # Op 075: Cut wedge
            _log(f"Op 075: Cutting wedge taper...")
            if not self._op_075_cut_wedge(comp, width, depth, height, wedge_direction):
                errors.append("Op 075 WARNING: Wedge cut failed")

            # Op 050: Add studs
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "studs_x": studs_x, "studs_y": studs_y,
                    "wedge_direction": wedge_direction, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_inverted_slope(
        self,
        studs_x: int,
        studs_y: int,
        height_units: float = 1.0,
        slope_angle: int = 45,
        slope_direction: str = "front",
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create an inverted slope brick (slope on bottom instead of top).

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            height_units: Height in brick units
            slope_angle: Angle of slope (33, 45, 65 degrees)
            slope_direction: Direction of slope
            hollow: Whether to hollow out
            name: Custom component name
            color: LEGO color name
        """
        errors = []
        _log(f"=== Creating inverted slope: {studs_x}x{studs_y}, angle={slope_angle}° ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("inv_slope")
            comp_name = name or f"InvSlope_{slope_angle}_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base block
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 076: Cut inverted slope (from bottom)
            _log(f"Op 076: Cutting inverted slope...")
            if not self._op_076_cut_inverted_slope(comp, width, depth, height, slope_angle, slope_direction):
                errors.append("Op 076 WARNING: Inverted slope cut failed")

            # Op 050: Add studs on top
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "studs_x": studs_x, "studs_y": studs_y,
                    "slope_angle": slope_angle, "slope_direction": slope_direction,
                    "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_jumper_plate(
        self,
        studs_x: int = 1,
        studs_y: int = 2,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a jumper plate (1x2 plate with centered single stud).

        This allows half-stud offset positioning in LEGO builds.
        """
        errors = []
        _log(f"=== Creating jumper plate: {studs_x}x{studs_y} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = PLATE_HEIGHT

            brick_id = self._generate_brick_id("jumper")
            comp_name = name or f"Jumper_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow
            self._op_020_hollow(comp, width, depth, height)

            # Op 051: Add centered single stud
            _log("Op 051: Adding centered stud...")
            self._op_051_add_centered_stud(comp, width, depth, height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=True,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "studs_x": studs_x, "studs_y": studs_y, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_hinge_brick(
        self,
        studs_x: int,
        studs_y: int,
        hinge_type: str = "top",
        height_units: float = 1.0,
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a hinge brick with cylindrical hinge point.

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            hinge_type: Type of hinge (top, bottom, side)
            height_units: Height in brick units
            hollow: Whether to hollow out
            name: Custom component name
            color: LEGO color name
        """
        errors = []
        _log(f"=== Creating hinge brick: {studs_x}x{studs_y}, type={hinge_type} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("hinge")
            comp_name = name or f"Hinge_{hinge_type}_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow
            if hollow:
                self._op_020_hollow(comp, width, depth, height)

            # Op 110: Add hinge cylinder
            _log(f"Op 110: Adding hinge mechanism...")
            if not self._op_110_add_hinge(comp, width, depth, height, hinge_type):
                errors.append("Op 110 WARNING: Hinge creation failed")

            # Op 050: Add studs
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "studs_x": studs_x, "studs_y": studs_y,
                    "hinge_type": hinge_type, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_modified_brick(
        self,
        studs_x: int,
        studs_y: int,
        modification: str = "grille",
        height_units: float = 1.0,
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a modified brick with special features.

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            modification: Type of modification (grille, log, masonry, smooth)
            height_units: Height in brick units
            hollow: Whether to hollow out
            name: Custom component name
            color: LEGO color name
        """
        errors = []
        _log(f"=== Creating modified brick: {studs_x}x{studs_y}, mod={modification} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("modified")
            comp_name = name or f"Modified_{modification}_{studs_x}x{studs_y}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow
            if hollow:
                self._op_020_hollow(comp, width, depth, height)

            # Internal structure
            if studs_x > 1 and studs_y > 1:
                self._op_030_add_tubes(comp, studs_x, studs_y, height)
            elif studs_x == 1 or studs_y == 1:
                self._op_040_add_ribs(comp, studs_x, studs_y, height)

            # Op 120: Apply modification to front face
            _log(f"Op 120: Applying {modification} modification...")
            if not self._op_120_apply_modification(comp, width, depth, height, modification):
                errors.append(f"Op 120 WARNING: {modification} modification failed")

            # Op 050: Add studs
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "studs_x": studs_x, "studs_y": studs_y,
                    "modification": modification, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 5: ADVANCED BRICK TYPES - Manufacturing-Optimized Elements
    # ═══════════════════════════════════════════════════════════════════════════

    def create_snot_brick(
        self,
        studs_x: int,
        studs_y: int,
        side_studs: str = "both",
        height_units: float = 1.0,
        hollow: bool = True,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a SNOT (Studs Not On Top) brick with side studs.

        SNOT bricks are essential for advanced LEGO techniques allowing
        sideways building. Common examples: 1x4 brick with 4 side studs.

        Args:
            studs_x: Number of studs in X direction
            studs_y: Number of studs in Y direction
            side_studs: Which sides get studs (front, back, both, left, right, all)
            height_units: Height in brick units
            hollow: Whether to hollow out the bottom
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with brick info
        """
        errors = []
        _log(f"=== Creating SNOT brick: {studs_x}x{studs_y}, sides={side_studs} ===")

        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = height_units * BRICK_HEIGHT

            brick_id = self._generate_brick_id("snot")
            comp_name = name or f"SNOT_{studs_x}x{studs_y}_{side_studs}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Op 010: Create base
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base block failed")

            # Op 020: Hollow
            if hollow:
                self._op_020_hollow(comp, width, depth, height)

            # Op 030/040: Internal structure
            if studs_x > 1 and studs_y > 1:
                self._op_030_add_tubes(comp, studs_x, studs_y, height)
            elif studs_x == 1 or studs_y == 1:
                self._op_040_add_ribs(comp, studs_x, studs_y, height)

            # Op 130: Add side studs
            _log(f"Op 130: Adding side studs ({side_studs})...")
            if not self._op_130_add_side_studs(comp, studs_x, studs_y, height, side_studs):
                errors.append("Op 130 WARNING: Side studs failed")

            # Op 050: Add top studs
            self._op_050_add_studs(comp, studs_x, studs_y, height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "studs_x": studs_x, "studs_y": studs_y,
                    "side_studs": side_studs, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_bracket(
        self,
        base_studs: int = 1,
        side_studs: int = 2,
        bracket_type: str = "1x2-1x2",
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO bracket piece for sideways building.

        Brackets are L-shaped elements that allow changing build direction.
        Common types: 1x2-1x2, 1x2-1x4, 1x2-2x2.

        Args:
            base_studs: Studs on base section
            side_studs: Studs on side section
            bracket_type: Bracket configuration
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with bracket info
        """
        errors = []
        _log(f"=== Creating bracket: {bracket_type} ===")

        try:
            brick_id = self._generate_brick_id("bracket")
            comp_name = name or f"Bracket_{bracket_type}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Base dimensions
            base_width = base_studs * STUD_PITCH
            base_depth = 2 * STUD_PITCH
            base_height = PLATE_HEIGHT

            # Side dimensions
            side_width = WALL_THICKNESS * 2
            side_height = side_studs * STUD_PITCH

            # Op 010: Create base section
            _log("Op 010: Creating base section...")
            if not self._op_010_create_base(comp, base_width, base_depth, base_height):
                errors.append("Op 010 FAILED")
                raise Exception("Base section failed")

            # Op 011: Create side section (L-shape extension)
            _log("Op 011: Creating side section...")
            self._op_011_create_bracket_side(comp, base_width, base_depth, side_width, side_height)

            # Op 050: Add studs on base
            self._op_050_add_studs(comp, base_studs, 2, base_height)

            # Op 060: Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "base_width_mm": base_width, "side_height_mm": side_height,
                    "bracket_type": bracket_type, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_cheese_slope(
        self,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a 1x1 cheese slope (30 deg) - one of the most popular LEGO elements.

        The cheese slope is iconic for detail work and smooth surfaces.

        Returns:
            BrickResult with cheese slope info
        """
        errors = []
        _log("=== Creating cheese slope (1x1 30 deg) ===")

        try:
            width = STUD_PITCH
            depth = STUD_PITCH
            height = PLATE_HEIGHT * 2 / 3  # Cheese is 2/3 plate height

            brick_id = self._generate_brick_id("cheese")
            comp_name = name or "Cheese_Slope_1x1"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Create wedge profile
            sketch = comp.sketches.add(comp.xZConstructionPlane)
            lines = sketch.sketchCurves.sketchLines

            # Triangular wedge profile (30 deg slope)
            p1 = adsk.core.Point3D.create(0, 0, 0)
            p2 = adsk.core.Point3D.create(self._cm(width), 0, 0)
            p3 = adsk.core.Point3D.create(self._cm(width), self._cm(height), 0)

            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p1)

            if sketch.profiles.count == 0:
                errors.append("Op 010 FAILED")
                raise Exception("Profile failed")

            # Extrude wedge
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(depth)))
            extrudes.add(ext_input)

            # Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=True,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "angle": 30, "color": color
                },
                volume_mm3=volume,
                error=None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_headlight_brick(
        self,
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a 1x1 headlight brick (Erling brick).

        The headlight brick has a recessed stud socket on the front face,
        allowing attachment of tiles and other elements at 90 degrees.

        Returns:
            BrickResult with headlight brick info
        """
        errors = []
        _log("=== Creating headlight brick (1x1) ===")

        try:
            width = STUD_PITCH
            depth = STUD_PITCH
            height = BRICK_HEIGHT

            brick_id = self._generate_brick_id("headlight")
            comp_name = name or "Headlight_1x1"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Create base block
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base failed")

            # Cut recessed socket on front face
            _log("Op 131: Cutting front socket...")
            sketch = comp.sketches.add(comp.xZConstructionPlane)
            circles = sketch.sketchCurves.sketchCircles
            circles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(width/2), self._cm(height/2), 0),
                self._cm(STUD_DIAMETER/2 + 0.1)  # Slightly larger than stud
            )

            if sketch.profiles.count > 0:
                extrudes = comp.features.extrudeFeatures
                ext_input = extrudes.createInput(
                    sketch.profiles.item(0),
                    adsk.fusion.FeatureOperations.CutFeatureOperation
                )
                # Cut only into front face
                ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(2.0)))
                try:
                    extrudes.add(ext_input)
                except:
                    errors.append("Op 131 WARNING: Socket cut failed")

            # Add stud on top
            self._op_050_add_studs(comp, 1, 1, height)

            # Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth, "height_mm": height,
                    "type": "headlight", "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_bar(
        self,
        length_studs: int = 4,
        bar_type: str = "straight",
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO bar/rod element.

        Bars fit in minifig hands and clip elements. Standard bar diameter is 3.18mm.

        Args:
            length_studs: Length in stud units
            bar_type: Type of bar (straight, curved, antenna)
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with bar info
        """
        errors = []
        _log(f"=== Creating bar: length={length_studs}, type={bar_type} ===")

        try:
            length = length_studs * STUD_PITCH
            diameter = BAR_DIAMETER

            brick_id = self._generate_brick_id("bar")
            comp_name = name or f"Bar_{length_studs}L"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Create cylinder
            sketch = comp.sketches.add(comp.xYConstructionPlane)
            circles = sketch.sketchCurves.sketchCircles
            circles.addByCenterRadius(
                adsk.core.Point3D.create(0, 0, 0),
                self._cm(diameter/2)
            )

            if sketch.profiles.count == 0:
                errors.append("Op 010 FAILED")
                raise Exception("Circle profile failed")

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(length)))
            extrudes.add(ext_input)

            # Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=True,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "length_mm": length, "diameter_mm": diameter,
                    "length_studs": length_studs, "bar_type": bar_type,
                    "color": color
                },
                volume_mm3=volume,
                error=None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    def create_clip(
        self,
        clip_type: str = "bar_holder",
        name: Optional[str] = None,
        color: Optional[str] = None
    ) -> BrickResult:
        """
        Create a LEGO clip element for attaching to bars.

        Args:
            clip_type: Type of clip (bar_holder, horizontal_clip, vertical_clip)
            name: Custom component name
            color: LEGO color name

        Returns:
            BrickResult with clip info
        """
        errors = []
        _log(f"=== Creating clip: type={clip_type} ===")

        try:
            width = STUD_PITCH
            depth = STUD_PITCH
            height = PLATE_HEIGHT

            brick_id = self._generate_brick_id("clip")
            comp_name = name or f"Clip_{clip_type}"

            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name

            # Create base plate
            if not self._op_010_create_base(comp, width, depth, height):
                errors.append("Op 010 FAILED")
                raise Exception("Base failed")

            # Add clip arm with bar holder hole
            _log("Op 132: Adding clip arm...")
            clip_height = STUD_PITCH
            clip_width = width * 0.8

            sketch = comp.sketches.add(comp.xZConstructionPlane)
            lines = sketch.sketchCurves.sketchLines
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(self._cm((width - clip_width)/2), self._cm(height), 0),
                adsk.core.Point3D.create(self._cm((width + clip_width)/2), self._cm(height + clip_height), 0)
            )

            if sketch.profiles.count > 0:
                extrudes = comp.features.extrudeFeatures
                ext_input = extrudes.createInput(
                    sketch.profiles.item(0),
                    adsk.fusion.FeatureOperations.JoinFeatureOperation
                )
                ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(depth)))
                try:
                    extrudes.add(ext_input)
                except:
                    errors.append("Op 132 WARNING: Clip arm failed")

            # Apply color
            if color:
                self._op_060_apply_color(comp, color)

            volume = sum(body.volume * 1000 for body in comp.bRepBodies)

            return BrickResult(
                success=len([e for e in errors if "FAILED" in e]) == 0,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width, "depth_mm": depth,
                    "clip_type": clip_type, "color": color
                },
                volume_mm3=volume,
                error="; ".join(errors) if errors else None
            )

        except Exception as e:
            errors.append(str(e))
            return BrickResult(success=False, brick_id="", component_name="",
                             dimensions={}, volume_mm3=0, error="; ".join(errors))

    # ═══════════════════════════════════════════════════════════════════════════
    # MANUFACTURING ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze_manufacturability(
        self,
        brick_result: BrickResult,
        process: str = "fdm"
    ) -> Dict[str, Any]:
        """
        Analyze brick for manufacturing feasibility.

        Args:
            brick_result: Result from brick creation
            process: Manufacturing process (fdm, sla, injection, cnc)

        Returns:
            Manufacturing analysis with recommendations
        """
        analysis = {
            "brick_id": brick_result.brick_id,
            "process": process,
            "feasible": True,
            "issues": [],
            "recommendations": [],
            "estimated_time_min": 0,
            "estimated_cost_usd": 0
        }

        dims = brick_result.dimensions
        volume = brick_result.volume_mm3

        if process == "fdm":
            # FDM-specific analysis
            if dims.get("height_mm", 0) < 1.0:
                analysis["issues"].append("Height too small for FDM (min 1mm)")
                analysis["feasible"] = False

            # Estimate print time (rough: 10mm3/min for FDM)
            analysis["estimated_time_min"] = max(5, volume / 10)

            # Cost estimate ($0.02/gram, PLA density ~1.25 g/cm3)
            mass_g = (volume / 1000) * 1.25  # cm3 * g/cm3
            analysis["estimated_cost_usd"] = round(mass_g * 0.02, 2)

            analysis["recommendations"].append("Print with 0.2mm layer height")
            analysis["recommendations"].append("Orient studs facing up for best quality")

        elif process == "sla":
            # SLA for high detail
            analysis["estimated_time_min"] = max(15, volume / 5)
            analysis["estimated_cost_usd"] = round((volume / 1000) * 1.25 * 0.10, 2)
            analysis["recommendations"].append("Use 0.05mm layers for stud detail")

        elif process == "injection":
            # Injection molding
            min_wall = 0.8  # mm
            if dims.get("width_mm", 0) / dims.get("studs_x", 1) < min_wall * 2:
                analysis["issues"].append(f"Wall thickness may be too thin (min {min_wall}mm)")

            # Per-part cost for injection (amortized tooling)
            analysis["estimated_cost_usd"] = round(0.01 + (volume / 1000) * 0.005, 3)
            analysis["estimated_time_min"] = 0.5  # Cycle time

            analysis["recommendations"].append("Draft angles of 1-2 deg required")
            analysis["recommendations"].append("Uniform wall thickness recommended")

        elif process == "cnc":
            # CNC milling
            analysis["estimated_time_min"] = max(30, volume / 2)
            analysis["estimated_cost_usd"] = round(analysis["estimated_time_min"] * 1.0, 2)
            analysis["recommendations"].append("Multiple setups required for undercuts")

        return analysis

    def get_material_requirements(
        self,
        brick_result: BrickResult,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate material requirements for brick production.

        Args:
            brick_result: Result from brick creation
            quantity: Number of parts to produce

        Returns:
            Material requirements breakdown
        """
        volume_mm3 = brick_result.volume_mm3
        volume_cm3 = volume_mm3 / 1000

        # ABS density: 1.04 g/cm3 (LEGO standard)
        abs_density = 1.04

        return {
            "brick_id": brick_result.brick_id,
            "quantity": quantity,
            "per_part": {
                "volume_mm3": volume_mm3,
                "volume_cm3": volume_cm3,
                "mass_grams": round(volume_cm3 * abs_density, 3)
            },
            "total": {
                "volume_cm3": round(volume_cm3 * quantity, 2),
                "mass_grams": round(volume_cm3 * abs_density * quantity, 2),
                "mass_kg": round(volume_cm3 * abs_density * quantity / 1000, 4)
            },
            "material_spec": {
                "type": "ABS",
                "density_g_cm3": abs_density,
                "color": brick_result.dimensions.get("color", "unspecified"),
                "grade": "LEGO-compatible high-impact ABS"
            }
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # NEW OPERATION METHODS FOR ADVANCED BRICK TYPES
    # ═══════════════════════════════════════════════════════════════════════════

    def _op_011_create_bracket_side(
        self,
        comp: adsk.fusion.Component,
        base_width: float,
        base_depth: float,
        side_width: float,
        side_height: float
    ) -> bool:
        """Op 011: Create bracket side extension."""
        try:
            sketch = comp.sketches.add(comp.xZConstructionPlane)
            lines = sketch.sketchCurves.sketchLines

            # Create side section on front face
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(-self._cm(side_width), 0, 0),
                adsk.core.Point3D.create(0, self._cm(side_height), 0)
            )

            if sketch.profiles.count == 0:
                return False

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(base_depth)))
            extrudes.add(ext_input)

            return True
        except:
            return False

    def _op_130_add_side_studs(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float,
        side_studs: str
    ) -> bool:
        """
        Op 130: Add studs on side faces (SNOT configuration).

        Creates studs perpendicular to the normal stud direction.
        """
        try:
            stud_radius = self._cm(STUD_DIAMETER / 2)
            stud_length = self._cm(STUD_HEIGHT)

            # Determine which sides get studs
            add_front = side_studs in ["front", "both", "all"]
            add_back = side_studs in ["back", "both", "all"]

            extrudes = comp.features.extrudeFeatures
            success = True

            if add_front:
                # Front face (XZ plane at Y=0)
                sketch = comp.sketches.add(comp.xZConstructionPlane)
                circles = sketch.sketchCurves.sketchCircles
                for i in range(studs_x):
                    center_x = self._cm((i + 0.5) * STUD_PITCH)
                    center_z = self._cm(height / 2)
                    circles.addByCenterRadius(
                        adsk.core.Point3D.create(center_x, center_z, 0),
                        stud_radius
                    )

                for i in range(sketch.profiles.count):
                    try:
                        ext_input = extrudes.createInput(
                            sketch.profiles.item(i),
                            adsk.fusion.FeatureOperations.JoinFeatureOperation
                        )
                        # Extrude in -Y direction
                        ext_input.setDistanceExtent(
                            False,
                            adsk.core.ValueInput.createByReal(-stud_length)
                        )
                        extrudes.add(ext_input)
                    except:
                        success = False

            return success
        except Exception as e:
            _log(f"Op 130 Exception: {e}", error=True)
            return False

    def _op_010_create_base(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float
    ) -> bool:
        """
        Op 010: Create solid rectangular base block.

        Type: NewBodyFeatureOperation
        Input: None
        Output: Solid rectangular body
        Validation: bRepBodies.count == 1
        """
        try:
            sketch = comp.sketches.add(comp.xYConstructionPlane)
            lines = sketch.sketchCurves.sketchLines
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(0, 0, 0),
                adsk.core.Point3D.create(self._cm(width), self._cm(depth), 0)
            )

            if sketch.profiles.count == 0:
                _log("Op 010: No profiles created in sketch", error=True)
                return False

            profile = sketch.profiles.item(0)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(height))
            )
            extrudes.add(ext_input)

            return comp.bRepBodies.count == 1
        except Exception as e:
            _log(f"Op 010 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False
    
    def _op_050_add_studs(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float
    ) -> bool:
        """
        Op 050: Add studs on top face.

        Type: JoinFeatureOperation
        Input: Complete body (after hollow and internal structure)
        Output: Final brick with studs
        Validation: Stud count matches studs_x * studs_y

        Strategy: Create an offset construction plane at brick height, sketch circles,
        and extrude upward. This avoids face coordinate system issues.
        """
        try:
            if comp.bRepBodies.count == 0:
                return False

            # Create offset construction plane at top of brick (height from XY plane)
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            offset_value = adsk.core.ValueInput.createByReal(self._cm(height))
            plane_input.setByOffset(comp.xYConstructionPlane, offset_value)
            top_plane = planes.add(plane_input)

            studs_created = 0
            expected_studs = studs_x * studs_y
            stud_radius = self._cm(STUD_DIAMETER / 2)
            stud_height_cm = self._cm(STUD_HEIGHT)

            # Create ALL stud circles in ONE sketch for efficiency
            sketch = comp.sketches.add(top_plane)
            circles = sketch.sketchCurves.sketchCircles

            for i in range(studs_x):
                for j in range(studs_y):
                    center_x = self._cm((i + 0.5) * STUD_PITCH)
                    center_y = self._cm((j + 0.5) * STUD_PITCH)
                    circles.addByCenterRadius(
                        adsk.core.Point3D.create(center_x, center_y, 0),
                        stud_radius
                    )

            # Now extrude each circle profile individually
            # Each circle creates its own profile (the inner area)
            extrudes = comp.features.extrudeFeatures
            expected_stud_area = math.pi * (stud_radius ** 2)

            _log(f"Op 050: Found {sketch.profiles.count} profiles, expected stud area={expected_stud_area:.6f} cm²")

            for i in range(sketch.profiles.count):
                profile = sketch.profiles.item(i)
                # Only extrude small circular profiles (studs), not the outer frame
                area = profile.areaProperties().area

                # Allow 100% tolerance for area matching (more permissive)
                # Studs are small circles, outer frame is the entire top face
                if area < expected_stud_area * 2.0:
                    _log(f"  Profile {i}: area={area:.6f} cm² -> stud (creating)")
                    ext_input = extrudes.createInput(
                        profile,
                        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                    )
                    ext_input.setDistanceExtent(
                        False,
                        adsk.core.ValueInput.createByReal(stud_height_cm)
                    )
                    extrudes.add(ext_input)
                    studs_created += 1

            # Now combine all stud bodies with the main body
            if studs_created > 0:
                main_body = None
                stud_bodies = []

                for body in comp.bRepBodies:
                    # Main body is much larger
                    if body.volume > 0.001:  # Threshold for main body vs studs
                        if main_body is None or body.volume > main_body.volume:
                            if main_body:
                                stud_bodies.append(main_body)
                            main_body = body
                        else:
                            stud_bodies.append(body)
                    else:
                        stud_bodies.append(body)

                # Combine studs with main body
                if main_body and stud_bodies:
                    combine_features = comp.features.combineFeatures
                    tool_bodies = adsk.core.ObjectCollection.create()
                    for stud_body in stud_bodies:
                        tool_bodies.add(stud_body)

                    combine_input = combine_features.createInput(main_body, tool_bodies)
                    combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
                    combine_features.add(combine_input)

            _log(f"Op 050: Created {studs_created}/{expected_studs} studs")
            return studs_created == expected_studs
        except Exception as e:
            _log(f"Op 050 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_060_apply_color(
        self,
        comp: adsk.fusion.Component,
        color_name: str
    ) -> bool:
        """
        Op 060: Apply LEGO color to brick bodies.

        Type: Appearance assignment
        Input: Complete brick with all bodies combined
        Output: Colored brick

        Uses Fusion 360's appearance library or creates custom color.
        """
        try:
            # Normalize color name (lowercase, replace spaces with underscores)
            color_key = color_name.lower().strip().replace(" ", "_").replace("-", "_")

            # Get RGB values from LEGO color map
            if color_key not in LEGO_COLORS:
                _log(f"Op 060: Unknown color '{color_name}', available: {list(LEGO_COLORS.keys())[:10]}...", error=True)
                return False

            r, g, b = LEGO_COLORS[color_key]
            _log(f"Op 060: Applying color '{color_key}' RGB({r}, {g}, {b})")

            # Get the design's appearances
            design = self.design
            app_lib = self.app.materialLibraries.itemByName("Fusion 360 Appearance Library")

            # Try to find a plastic appearance to use as base
            plastic_appearance = None
            if app_lib:
                for i in range(app_lib.appearances.count):
                    app = app_lib.appearances.item(i)
                    if "plastic" in app.name.lower() or "abs" in app.name.lower():
                        plastic_appearance = app
                        break

            # Create a custom appearance in the design
            appearances = design.appearances

            # Check if we already have this color appearance
            custom_name = f"LEGO_{color_key}"
            existing = None
            for i in range(appearances.count):
                if appearances.item(i).name == custom_name:
                    existing = appearances.item(i)
                    break

            if existing:
                appearance = existing
            elif plastic_appearance:
                # Copy plastic appearance and modify color
                appearance = appearances.addByCopy(plastic_appearance, custom_name)
            else:
                # Create from first available appearance
                if app_lib and app_lib.appearances.count > 0:
                    base = app_lib.appearances.item(0)
                    appearance = appearances.addByCopy(base, custom_name)
                else:
                    _log("Op 060: No appearance library available", error=True)
                    return False

            # Set the color on the appearance
            # Find color property (usually named "Color" or in diffuse properties)
            for prop in appearance.appearanceProperties:
                if hasattr(prop, 'value') and hasattr(prop, 'name'):
                    if 'color' in prop.name.lower() or prop.name == 'Color':
                        try:
                            # Create color object
                            prop.value = adsk.core.Color.create(r, g, b, 255)
                            _log(f"Op 060: Set color property '{prop.name}'")
                        except:
                            pass

            # Apply appearance to all bodies in the component
            for body in comp.bRepBodies:
                body.appearance = appearance
                _log(f"Op 060: Applied appearance to body '{body.name}'")

            return True

        except Exception as e:
            _log(f"Op 060 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_020_hollow(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float
    ) -> bool:
        """
        Op 020: Cut hollow interior from bottom.

        Type: CutFeatureOperation
        Input: Solid base block
        Output: Shell with walls (WALL_THICKNESS) and top (TOP_THICKNESS)

        Strategy: Use Fusion's Shell feature for reliable hollowing, or fall back
        to sketching on XY plane and cutting upward into the body.
        """
        try:
            inner_width = width - 2 * WALL_THICKNESS
            inner_depth = depth - 2 * WALL_THICKNESS
            cut_depth = height - TOP_THICKNESS

            # If too small to hollow, return success (not an error)
            if inner_width <= 0 or inner_depth <= 0 or cut_depth <= 0:
                _log(f"Op 020: Brick too small to hollow, skipping")
                return True

            if comp.bRepBodies.count == 0:
                _log(f"Op 020: No body found", error=True)
                return False

            # Sketch on XY construction plane (Z=0, bottom of brick)
            sketch = comp.sketches.add(comp.xYConstructionPlane)
            sketch.name = "Op020_Hollow_Sketch"
            lines = sketch.sketchCurves.sketchLines

            # Draw inner rectangle for hollow cavity
            _log(f"Op 020: Drawing hollow rectangle: wall={WALL_THICKNESS}mm, inner={inner_width}x{inner_depth}mm")
            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(self._cm(WALL_THICKNESS), self._cm(WALL_THICKNESS), 0),
                adsk.core.Point3D.create(self._cm(width - WALL_THICKNESS), self._cm(depth - WALL_THICKNESS), 0)
            )

            if sketch.profiles.count == 0:
                _log(f"Op 020: No profiles created in sketch", error=True)
                return False

            # Find the inner rectangle profile (smaller area = the hollow cavity)
            inner_profile = None
            smallest_area = float('inf')
            expected_area = self._cm(inner_width) * self._cm(inner_depth)

            _log(f"Op 020: Looking for profile with area ~{expected_area:.4f} cm², found {sketch.profiles.count} profiles")

            for i in range(sketch.profiles.count):
                prof = sketch.profiles.item(i)
                area = prof.areaProperties().area
                _log(f"Op 020:   Profile {i}: area={area:.4f} cm²")
                if area < smallest_area:
                    smallest_area = area
                    inner_profile = prof

            if not inner_profile:
                _log(f"Op 020: Could not find inner profile", error=True)
                return False

            # Cut upward into the body (from Z=0 going up)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                inner_profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(cut_depth))
            )

            feature = extrudes.add(ext_input)
            feature.name = "Op020_Hollow_Cut"

            _log(f"Op 020: Hollow cut complete - removed {inner_width}x{inner_depth}x{cut_depth}mm cavity")
            return True

        except Exception as e:
            _log(f"Op 020 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_030_add_tubes(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float
    ) -> bool:
        """
        Op 030: Add hollow tubes at stud intersections.

        Type: JoinFeatureOperation + CutFeatureOperation
        Input: Hollowed shell
        Output: Shell with tubes
        Validation: Tube count matches (studs_x-1) * (studs_y-1)

        Tubes are located at the intersection points between studs (center of 4 studs).
        For a 2x2 brick: 1 tube at center
        For a 2x4 brick: 3 tubes along center line

        Strategy: Sketch on XY plane, create tube cylinders, join to body, then cut centers.
        """
        try:
            if studs_x < 2 or studs_y < 2:
                _log(f"Op 030: No tubes needed for {studs_x}x{studs_y} brick")
                return True

            tube_height = height - TOP_THICKNESS
            expected_tubes = (studs_x - 1) * (studs_y - 1)

            if comp.bRepBodies.count == 0:
                _log(f"Op 030: No body found", error=True)
                return False

            _log(f"Op 030: Adding {expected_tubes} tubes for {studs_x}x{studs_y} brick")
            _log(f"Op 030: Tube dimensions: OD={TUBE_OD}mm, ID={TUBE_ID}mm, height={tube_height}mm")

            # Step 1: Create outer tube cylinders on XY plane
            sketch_outer = comp.sketches.add(comp.xYConstructionPlane)
            sketch_outer.name = "Op030_Tubes_Outer"
            circles = sketch_outer.sketchCurves.sketchCircles

            tube_positions = []
            for i in range(studs_x - 1):
                for j in range(studs_y - 1):
                    # Tubes are centered between studs
                    center_x = (i + 1) * STUD_PITCH  # mm
                    center_y = (j + 1) * STUD_PITCH  # mm
                    tube_positions.append((center_x, center_y))
                    circles.addByCenterRadius(
                        adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0),
                        self._cm(TUBE_OD / 2)
                    )

            _log(f"Op 030: Created {len(tube_positions)} outer circles at positions: {tube_positions}")

            # Step 2: Extrude outer tubes (join to main body)
            extrudes = comp.features.extrudeFeatures
            tube_height_cm = self._cm(tube_height)
            outer_area = math.pi * (self._cm(TUBE_OD / 2) ** 2)
            tubes_joined = 0

            for i in range(sketch_outer.profiles.count):
                profile = sketch_outer.profiles.item(i)
                area = profile.areaProperties().area
                # Match circular profiles (within 50% tolerance)
                if abs(area - outer_area) < outer_area * 0.5:
                    ext_input = extrudes.createInput(
                        profile,
                        adsk.fusion.FeatureOperations.JoinFeatureOperation
                    )
                    ext_input.setDistanceExtent(
                        False,
                        adsk.core.ValueInput.createByReal(tube_height_cm)
                    )
                    feature = extrudes.add(ext_input)
                    feature.name = f"Op030_Tube_Outer_{tubes_joined + 1}"
                    tubes_joined += 1

            _log(f"Op 030: Joined {tubes_joined} outer tube cylinders")

            # Step 3: Cut inner holes to make tubes hollow
            sketch_inner = comp.sketches.add(comp.xYConstructionPlane)
            sketch_inner.name = "Op030_Tubes_Inner"
            inner_circles = sketch_inner.sketchCurves.sketchCircles

            for center_x, center_y in tube_positions:
                inner_circles.addByCenterRadius(
                    adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0),
                    self._cm(TUBE_ID / 2)
                )

            inner_area = math.pi * (self._cm(TUBE_ID / 2) ** 2)
            tubes_cut = 0

            for i in range(sketch_inner.profiles.count):
                profile = sketch_inner.profiles.item(i)
                area = profile.areaProperties().area
                if abs(area - inner_area) < inner_area * 0.5:
                    cut_input = extrudes.createInput(
                        profile,
                        adsk.fusion.FeatureOperations.CutFeatureOperation
                    )
                    cut_input.setDistanceExtent(
                        False,
                        adsk.core.ValueInput.createByReal(tube_height_cm)
                    )
                    feature = extrudes.add(cut_input)
                    feature.name = f"Op030_Tube_Inner_{tubes_cut + 1}"
                    tubes_cut += 1

            _log(f"Op 030: Cut {tubes_cut}/{expected_tubes} tube inner holes")
            return tubes_cut == expected_tubes

        except Exception as e:
            _log(f"Op 030 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_035_add_center_rib(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float
    ) -> bool:
        """
        Op 035: Add center rib for 2xN bricks (passes through tubes).

        Type: JoinFeatureOperation
        Input: Hollowed shell with tubes
        Output: Shell with center rib passing through specific tubes

        Real LEGO internal structure for 2xN bricks:
        - The rib runs down the CENTER (lengthwise) of the brick
        - It passes THROUGH specific tubes (every other tube starting from #2)
        - Where it intersects a tube, there's a 2mm recess/notch

        For 2x4 brick (3 tubes at positions 8, 16, 24mm):
            - 1 rib passes through tube #2 (at Y=16mm)
            - Rib has 2mm notch where it crosses the tube

        For 2x6 brick (5 tubes at positions 8, 16, 24, 32, 40mm):
            - 2 ribs pass through tubes #2 and #4 (at Y=16mm and Y=32mm)

        Tube numbering: tubes are at Y = 8, 16, 24, ... (every 8mm)
        Pattern: ribs at tubes 2, 4, 6, ... (even-numbered tubes)

        Real LEGO 2x4 underside (top view):
            ════════════════════════════════
            ║                              ║
            ║    ○        ○        ○       ║  <- 3 tubes
            ║    │        ║        │       ║
            ║    │════════╬════════│       ║  <- rib through middle tube
            ║    │        ║        │       ║
            ║                              ║
            ════════════════════════════════
        """
        try:
            rib_thickness = 1.0  # 1mm thick rib
            rib_notch_depth = 2.0  # 2mm notch where rib passes through tube

            if comp.bRepBodies.count == 0:
                _log("Op 035: No body found", error=True)
                return False

            # Determine which dimension is 2 studs (the narrow dimension)
            if studs_x == 2:
                narrow_dim = studs_x
                long_dim = studs_y
                rib_runs_along = "y"  # Rib runs along Y axis (lengthwise)
            elif studs_y == 2:
                narrow_dim = studs_y
                long_dim = studs_x
                rib_runs_along = "x"  # Rib runs along X axis (lengthwise)
            else:
                _log("Op 035: Not a 2xN brick, skipping center rib")
                return True

            # Number of tubes = long_dim - 1 (for 2x4: 3 tubes)
            num_tubes = long_dim - 1
            if num_tubes < 1:
                _log("Op 035: No tubes to add ribs through")
                return True

            # Determine which tubes get ribs (every other tube starting from #2)
            # Tube indices: 1, 2, 3, ... (1-based)
            # Ribs through: 2, 4, 6, ...
            rib_tube_indices = [i for i in range(2, num_tubes + 1, 2)]  # 2, 4, 6, ...

            if len(rib_tube_indices) == 0:
                _log("Op 035: No tubes to add ribs through (too few tubes)")
                return True

            _log(f"Op 035: {num_tubes} tubes, adding ribs through tubes {rib_tube_indices}")

            # Calculate rib dimensions
            # Rib runs down the center, spanning from wall to wall across the 2-stud width
            if rib_runs_along == "y":
                # Rib runs along Y, centered on X
                rib_center_x = narrow_dim * STUD_PITCH / 2  # Center X position (8mm for 2-wide)
                rib_start_y = WALL_THICKNESS
                rib_end_y = long_dim * STUD_PITCH - WALL_THICKNESS
                rib_length = rib_end_y - rib_start_y
            else:
                # Rib runs along X, centered on Y
                rib_center_y = narrow_dim * STUD_PITCH / 2
                rib_start_x = WALL_THICKNESS
                rib_end_x = long_dim * STUD_PITCH - WALL_THICKNESS
                rib_length = rib_end_x - rib_start_x

            # Rib height (from bottom to underside of top, with 2mm recess at bottom)
            rib_height = height - TOP_THICKNESS - RIB_BOTTOM_RECESS

            _log(f"Op 035: Creating center rib, length={rib_length:.1f}mm, height={rib_height:.1f}mm")

            # Create the main rib body
            sketch = comp.sketches.add(comp.xYConstructionPlane)
            sketch.name = "Op035_CenterRib_Sketch"
            lines = sketch.sketchCurves.sketchLines

            if rib_runs_along == "y":
                # Rib profile: rectangle centered on X, spanning Y
                x1 = rib_center_x - rib_thickness / 2
                x2 = rib_center_x + rib_thickness / 2
                y1 = rib_start_y
                y2 = rib_end_y
            else:
                # Rib profile: rectangle centered on Y, spanning X
                x1 = rib_start_x
                x2 = rib_end_x
                y1 = rib_center_y - rib_thickness / 2
                y2 = rib_center_y + rib_thickness / 2

            lines.addTwoPointRectangle(
                adsk.core.Point3D.create(self._cm(x1), self._cm(y1), 0),
                adsk.core.Point3D.create(self._cm(x2), self._cm(y2), 0)
            )

            if sketch.profiles.count == 0:
                _log("Op 035: No profile created for rib", error=True)
                return False

            # Extrude the rib from Z=RIB_BOTTOM_RECESS to Z=height-TOP_THICKNESS
            extrudes = comp.features.extrudeFeatures

            # Find the rib profile (should be the only one)
            rib_profile = sketch.profiles.item(0)

            ext_input = extrudes.createInput(
                rib_profile,
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            # Start extrusion at Z=RIB_BOTTOM_RECESS (2mm up from bottom)
            start_offset = adsk.fusion.OffsetStartDefinition.create(
                adsk.core.ValueInput.createByReal(self._cm(RIB_BOTTOM_RECESS))
            )
            ext_input.startExtent = start_offset
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(rib_height))
            )
            rib_feature = extrudes.add(ext_input)
            rib_feature.name = "Op035_CenterRib"

            _log(f"Op 035: Created center rib")

            # Now create notches where the rib passes through tubes
            # The notch is cut from the BOTTOM of the rib (at Z=RIB_BOTTOM_RECESS)
            # going UP by 2mm. This creates clearance for the tube opening.
            #
            # Real LEGO cross-section at tube intersection:
            #     ─────────────  <- top of brick interior
            #     │           │
            #     │    rib    │  <- rib continues up to top
            #     │           │
            #     │   ┌───┐   │  <- tube wall
            #     │   │   │   │
            #     ════╧═══╧════  <- notch cut here (bottom 2mm of rib removed)
            #         2mm gap     <- rib starts 2mm up from brick bottom
            #     ──────────────  <- bottom of brick (Z=0)
            #
            notch_height = rib_notch_depth  # 2mm notch depth
            notch_z_start = RIB_BOTTOM_RECESS  # Start at bottom of rib (2mm up from brick bottom)

            for tube_idx in rib_tube_indices:
                # Tube position (center)
                if rib_runs_along == "y":
                    tube_center_y = tube_idx * STUD_PITCH
                    # Notch is centered on tube, spans tube diameter
                    notch_x1 = rib_center_x - rib_thickness / 2 - 0.1  # Slightly wider
                    notch_x2 = rib_center_x + rib_thickness / 2 + 0.1
                    notch_y1 = tube_center_y - TUBE_OD / 2
                    notch_y2 = tube_center_y + TUBE_OD / 2
                else:
                    tube_center_x = tube_idx * STUD_PITCH
                    notch_x1 = tube_center_x - TUBE_OD / 2
                    notch_x2 = tube_center_x + TUBE_OD / 2
                    notch_y1 = rib_center_y - rib_thickness / 2 - 0.1
                    notch_y2 = rib_center_y + rib_thickness / 2 + 0.1

                # Create sketch for notch at the bottom of the rib
                planes = comp.constructionPlanes
                plane_input = planes.createInput()
                plane_input.setByOffset(
                    comp.xYConstructionPlane,
                    adsk.core.ValueInput.createByReal(self._cm(notch_z_start))
                )
                notch_plane = planes.add(plane_input)
                notch_plane.name = f"Op035_NotchPlane_{tube_idx}"

                notch_sketch = comp.sketches.add(notch_plane)
                notch_sketch.name = f"Op035_Notch_{tube_idx}_Sketch"

                notch_sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                    adsk.core.Point3D.create(self._cm(notch_x1), self._cm(notch_y1), 0),
                    adsk.core.Point3D.create(self._cm(notch_x2), self._cm(notch_y2), 0)
                )

                if notch_sketch.profiles.count > 0:
                    notch_profile = notch_sketch.profiles.item(0)
                    cut_input = extrudes.createInput(
                        notch_profile,
                        adsk.fusion.FeatureOperations.CutFeatureOperation
                    )
                    # Cut upward from the bottom of the rib
                    cut_input.setDistanceExtent(
                        False,
                        adsk.core.ValueInput.createByReal(self._cm(notch_height))
                    )
                    cut_feature = extrudes.add(cut_input)
                    cut_feature.name = f"Op035_Notch_{tube_idx}"
                    _log(f"Op 035: Created notch at tube {tube_idx} (bottom 2mm of rib)")

            _log(f"Op 035 SUCCESS: Created center rib with {len(rib_tube_indices)} notches")
            return True

        except Exception as e:
            _log(f"Op 035 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_036_add_cross_ribs(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float
    ) -> bool:
        """
        Op 036: Add cross-ribs for larger bricks (3x3, 4x4, 4x6, etc.).

        Type: JoinFeatureOperation
        Input: Hollowed shell with tubes
        Output: Shell with cross-ribs connecting tubes

        For bricks 3x3 and larger, there's a grid of tubes underneath.
        Cross-ribs run between the tubes in both X and Y directions,
        forming a grid pattern that strengthens the brick.

        Real LEGO 4x4 underside (top view):
            ════════════════════════════════════
            ║                                  ║
            ║    ○────○────○                   ║  <- 3x3 grid of tubes
            ║    │    │    │                   ║     connected by ribs
            ║    ○────○────○                   ║
            ║    │    │    │                   ║
            ║    ○────○────○                   ║
            ║                                  ║
            ════════════════════════════════════

        Ribs are recessed 2mm from the bottom of the brick.
        """
        try:
            rib_thickness = RIB_THICKNESS  # 1mm

            if comp.bRepBodies.count == 0:
                _log("Op 036: No body found", error=True)
                return False

            # Number of tubes in each direction
            tubes_x = studs_x - 1  # e.g., 4x4 has 3 tubes in X
            tubes_y = studs_y - 1  # e.g., 4x4 has 3 tubes in Y

            if tubes_x < 2 or tubes_y < 2:
                _log(f"Op 036: Not enough tubes for cross-ribs ({tubes_x}x{tubes_y})")
                return True

            # Rib height (from 2mm recess to underside of top)
            rib_height = height - TOP_THICKNESS - RIB_BOTTOM_RECESS

            _log(f"Op 036: Creating cross-ribs for {studs_x}x{studs_y} brick")
            _log(f"Op 036: Tube grid is {tubes_x}x{tubes_y}, rib height={rib_height:.1f}mm")

            extrudes = comp.features.extrudeFeatures
            ribs_created = 0

            # Create ribs running in X direction (connecting tubes horizontally)
            # For each row of tubes, create ribs between adjacent tubes
            for row in range(tubes_y):
                tube_y = (row + 1) * STUD_PITCH  # Y position of this row of tubes

                for col in range(tubes_x - 1):
                    # Rib from tube at (col, row) to tube at (col+1, row)
                    tube_x1 = (col + 1) * STUD_PITCH
                    tube_x2 = (col + 2) * STUD_PITCH

                    # Rib starts at edge of first tube, ends at edge of second tube
                    rib_x1 = tube_x1 + TUBE_OD / 2
                    rib_x2 = tube_x2 - TUBE_OD / 2
                    rib_y1 = tube_y - rib_thickness / 2
                    rib_y2 = tube_y + rib_thickness / 2

                    # Skip if rib would be too short
                    if rib_x2 - rib_x1 < 0.5:
                        continue

                    # Create sketch on XY plane
                    sketch = comp.sketches.add(comp.xYConstructionPlane)
                    sketch.name = f"Op036_RibX_{row}_{col}_Sketch"

                    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                        adsk.core.Point3D.create(self._cm(rib_x1), self._cm(rib_y1), 0),
                        adsk.core.Point3D.create(self._cm(rib_x2), self._cm(rib_y2), 0)
                    )

                    if sketch.profiles.count > 0:
                        profile = sketch.profiles.item(0)
                        ext_input = extrudes.createInput(
                            profile,
                            adsk.fusion.FeatureOperations.JoinFeatureOperation
                        )
                        # Start at 2mm recess
                        start_offset = adsk.fusion.OffsetStartDefinition.create(
                            adsk.core.ValueInput.createByReal(self._cm(RIB_BOTTOM_RECESS))
                        )
                        ext_input.startExtent = start_offset
                        ext_input.setDistanceExtent(
                            False,
                            adsk.core.ValueInput.createByReal(self._cm(rib_height))
                        )
                        rib_feature = extrudes.add(ext_input)
                        rib_feature.name = f"Op036_RibX_{row}_{col}"
                        ribs_created += 1

            # Create ribs running in Y direction (connecting tubes vertically)
            for col in range(tubes_x):
                tube_x = (col + 1) * STUD_PITCH  # X position of this column of tubes

                for row in range(tubes_y - 1):
                    # Rib from tube at (col, row) to tube at (col, row+1)
                    tube_y1 = (row + 1) * STUD_PITCH
                    tube_y2 = (row + 2) * STUD_PITCH

                    # Rib starts at edge of first tube, ends at edge of second tube
                    rib_x1 = tube_x - rib_thickness / 2
                    rib_x2 = tube_x + rib_thickness / 2
                    rib_y1 = tube_y1 + TUBE_OD / 2
                    rib_y2 = tube_y2 - TUBE_OD / 2

                    # Skip if rib would be too short
                    if rib_y2 - rib_y1 < 0.5:
                        continue

                    # Create sketch on XY plane
                    sketch = comp.sketches.add(comp.xYConstructionPlane)
                    sketch.name = f"Op036_RibY_{row}_{col}_Sketch"

                    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
                        adsk.core.Point3D.create(self._cm(rib_x1), self._cm(rib_y1), 0),
                        adsk.core.Point3D.create(self._cm(rib_x2), self._cm(rib_y2), 0)
                    )

                    if sketch.profiles.count > 0:
                        profile = sketch.profiles.item(0)
                        ext_input = extrudes.createInput(
                            profile,
                            adsk.fusion.FeatureOperations.JoinFeatureOperation
                        )
                        # Start at 2mm recess
                        start_offset = adsk.fusion.OffsetStartDefinition.create(
                            adsk.core.ValueInput.createByReal(self._cm(RIB_BOTTOM_RECESS))
                        )
                        ext_input.startExtent = start_offset
                        ext_input.setDistanceExtent(
                            False,
                            adsk.core.ValueInput.createByReal(self._cm(rib_height))
                        )
                        rib_feature = extrudes.add(ext_input)
                        rib_feature.name = f"Op036_RibY_{row}_{col}"
                        ribs_created += 1

            _log(f"Op 036 SUCCESS: Created {ribs_created} cross-ribs")
            return True

        except Exception as e:
            _log(f"Op 036 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_040_add_ribs(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float
    ) -> bool:
        """
        Op 040: Add ribs for 1xN bricks.

        Type: JoinFeatureOperation
        Input: Hollowed shell
        Output: Shell with ribs
        Validation: Rib count matches expected

        For 1xN bricks (where one dimension is 1 stud), tubes don't fit.
        Thin ribs run perpendicular to the length at stud junctions.

        For a 1x4 brick: 3 ribs at positions 8mm, 16mm, 24mm along length
        Ribs span from wall to wall inside the cavity.

        Strategy: Create ribs as NewBody on TOP face and extrude DOWNWARD into cavity,
        then join to main body. This avoids the empty space at Z=0 issue.

        IMPORTANT: Real LEGO ribs don't touch the bottom - they are recessed by ~2mm.
        This allows for slight variations in stacking and improves clutch.
        """
        try:
            # Ribs are recessed 2mm from the bottom of the cavity
            rib_height = height - TOP_THICKNESS - RIB_BOTTOM_RECESS
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH

            if studs_x == 1 and studs_y > 1:
                rib_count = studs_y - 1
                is_along_y = True  # Ribs are positioned along Y axis
            elif studs_y == 1 and studs_x > 1:
                rib_count = studs_x - 1
                is_along_y = False  # Ribs are positioned along X axis
            else:
                _log(f"Op 040: No ribs needed for {studs_x}x{studs_y} brick")
                return True

            if comp.bRepBodies.count == 0:
                _log(f"Op 040: No body found", error=True)
                return False

            _log(f"Op 040: Adding {rib_count} ribs for {studs_x}x{studs_y} brick")
            _log(f"Op 040: Rib dimensions: thickness={RIB_THICKNESS}mm, height={rib_height}mm")

            # Get the main body for joining
            main_body = comp.bRepBodies.item(0)

            # Find or create an offset plane at the TOP of the brick (at height Z)
            # This is where the cavity ceiling is - we'll extrude DOWN from here
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                comp.xYConstructionPlane,
                adsk.core.ValueInput.createByReal(self._cm(height - TOP_THICKNESS))
            )
            rib_plane = planes.add(plane_input)
            rib_plane.name = "Op040_Rib_Plane"

            extrudes = comp.features.extrudeFeatures
            combine_features = comp.features.combineFeatures
            ribs_created = 0

            # Create ONE SKETCH PER RIB to avoid profile selection ambiguity
            for i in range(rib_count):
                # Create new sketch on the offset plane (at cavity ceiling)
                sketch = comp.sketches.add(rib_plane)
                sketch.name = f"Op040_Rib_{i+1}_Sketch"
                lines = sketch.sketchCurves.sketchLines

                if is_along_y:
                    # 1xN brick: ribs run along X (width), positioned at Y junctions
                    rib_center_y = (i + 1) * STUD_PITCH
                    x1 = WALL_THICKNESS
                    x2 = width - WALL_THICKNESS
                    y1 = rib_center_y - RIB_THICKNESS / 2
                    y2 = rib_center_y + RIB_THICKNESS / 2
                else:
                    # Nx1 brick: ribs run along Y (depth), positioned at X junctions
                    rib_center_x = (i + 1) * STUD_PITCH
                    x1 = rib_center_x - RIB_THICKNESS / 2
                    x2 = rib_center_x + RIB_THICKNESS / 2
                    y1 = WALL_THICKNESS
                    y2 = depth - WALL_THICKNESS

                # Draw single rib rectangle
                lines.addTwoPointRectangle(
                    adsk.core.Point3D.create(self._cm(x1), self._cm(y1), 0),
                    adsk.core.Point3D.create(self._cm(x2), self._cm(y2), 0)
                )

                # With a single rectangle in an isolated sketch, there should be exactly 1 profile
                if sketch.profiles.count >= 1:
                    # Use the first (and should be only) profile
                    profile = sketch.profiles.item(0)

                    # Create as NEW BODY first, extruding DOWNWARD (negative direction)
                    ext_input = extrudes.createInput(
                        profile,
                        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                    )
                    # Extrude in negative Z direction (downward into cavity)
                    ext_input.setDistanceExtent(
                        False,  # Symmetric = False
                        adsk.core.ValueInput.createByReal(self._cm(rib_height))
                    )
                    # Set to extrude in negative direction
                    ext_input.setOneSideExtent(
                        adsk.fusion.DistanceExtentDefinition.create(
                            adsk.core.ValueInput.createByReal(self._cm(rib_height))
                        ),
                        adsk.fusion.ExtentDirections.NegativeExtentDirection
                    )

                    feature = extrudes.add(ext_input)
                    feature.name = f"Op040_Rib_{ribs_created + 1}"

                    # Find the newly created rib body and join it to main body
                    if comp.bRepBodies.count > 1:
                        rib_body = None
                        for body in comp.bRepBodies:
                            if body != main_body:
                                rib_body = body
                                break

                        if rib_body:
                            # Combine (join) the rib to main body
                            tool_bodies = adsk.core.ObjectCollection.create()
                            tool_bodies.add(rib_body)
                            combine_input = combine_features.createInput(main_body, tool_bodies)
                            combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
                            combine_features.add(combine_input)

                    ribs_created += 1
                    _log(f"Op 040: Created rib {ribs_created} at position {i+1}")
                else:
                    _log(f"Op 040: No profile created for rib {i+1}", error=True)

            _log(f"Op 040: Created {ribs_created}/{rib_count} ribs")
            return ribs_created == rib_count

        except Exception as e:
            _log(f"Op 040 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_070_cut_slope(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float,
        angle: int,
        direction: str
    ) -> bool:
        """
        Op 070: Cut slope angle into brick using triangular cutting body.

        Type: CutFeatureOperation via Combine
        Input: Brick body (solid or hollowed)
        Output: Brick with angled top surface

        Strategy: Create a triangular prism cutting body on top of the brick, then subtract.
        Draw triangle on XY plane at Z=height, extrude downward.
        """
        try:
            _log(f"Op 070: Cutting {angle}° slope in {direction} direction")

            # Calculate how far the slope extends horizontally
            slope_run = height / math.tan(math.radians(angle))
            _log(f"Op 070: Slope run = {slope_run:.2f}mm for {angle}° angle")

            # Get the main body
            if comp.bRepBodies.count == 0:
                _log("Op 070: No body to cut", error=True)
                return False

            main_body = comp.bRepBodies.item(0)

            # Create construction plane at top of brick (Z = height)
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                comp.xYConstructionPlane,
                adsk.core.ValueInput.createByReal(self._cm(height))
            )
            top_plane = planes.add(plane_input)
            top_plane.name = "Op070_TopPlane"

            sketch = comp.sketches.add(top_plane)
            sketch.name = "Op070_SlopeProfile"
            lines = sketch.sketchCurves.sketchLines

            # Draw triangular cutting profile on XY plane at Z=height
            # The triangle will be extruded DOWN to cut the slope
            if direction == "front":
                # Slope goes down toward front (Y=0)
                # Cut triangle: front portion from Y=0 to Y=slope_run
                slope_run = min(slope_run, depth)
                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(width), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(width), self._cm(slope_run), 0)
                p4 = adsk.core.Point3D.create(0, self._cm(slope_run), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

            elif direction == "back":
                # Slope goes down toward back (Y=depth)
                slope_run = min(slope_run, depth)
                p1 = adsk.core.Point3D.create(0, self._cm(depth - slope_run), 0)
                p2 = adsk.core.Point3D.create(self._cm(width), self._cm(depth - slope_run), 0)
                p3 = adsk.core.Point3D.create(self._cm(width), self._cm(depth), 0)
                p4 = adsk.core.Point3D.create(0, self._cm(depth), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

            elif direction == "left":
                # Slope goes down toward left (X=0)
                slope_run = min(slope_run, width)
                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(slope_run), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(slope_run), self._cm(depth), 0)
                p4 = adsk.core.Point3D.create(0, self._cm(depth), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

            else:  # right
                # Slope goes down toward right (X=width)
                slope_run = min(slope_run, width)
                p1 = adsk.core.Point3D.create(self._cm(width - slope_run), 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(width), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(width), self._cm(depth), 0)
                p4 = adsk.core.Point3D.create(self._cm(width - slope_run), self._cm(depth), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

            if sketch.profiles.count == 0:
                _log("Op 070: No profile created", error=True)
                return False

            profile = sketch.profiles.item(0)

            # Extrude DOWN with taper to create slope cut
            # Taper angle = slope angle (makes it go from rectangle at top to line at bottom)
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )

            # Use one-side extent going negative (down)
            ext_input.setOneSideExtent(
                adsk.fusion.DistanceExtentDefinition.create(
                    adsk.core.ValueInput.createByReal(self._cm(height))
                ),
                adsk.fusion.ExtentDirections.NegativeExtentDirection
            )

            # Set taper angle to create the slope
            # Taper of (90 - angle) degrees makes it slope at 'angle' degrees
            taper_rad = math.radians(90 - angle)
            ext_input.taperAngle = adsk.core.ValueInput.createByReal(taper_rad)

            feature = extrudes.add(ext_input)
            feature.name = "Op070_SlopeCut"

            _log(f"Op 070: Slope cut complete with taper angle {90-angle}°")
            return True

        except Exception as e:
            _log(f"Op 070 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_080_cut_arch(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float,
        arch_height: float
    ) -> bool:
        """
        Op 080: Cut arch opening through brick.

        Type: CutFeatureOperation
        Input: Solid brick body
        Output: Brick with arch-shaped opening

        Creates a semi-circular arch cut through the brick.
        """
        try:
            _log(f"Op 080: Cutting arch with height {arch_height}mm")

            # Arch radius (half of width for semicircle)
            arch_radius = width / 2
            arch_center_x = width / 2
            arch_center_z = arch_height  # Base of arch

            # Sketch on YZ plane to draw arch profile
            sketch = comp.sketches.add(comp.yZConstructionPlane)
            sketch.name = "Op080_Arch"

            # Draw arch as a combination of rectangle + semicircle
            lines = sketch.sketchCurves.sketchLines
            arcs = sketch.sketchCurves.sketchArcs

            # Rectangle below arch
            if arch_center_z > 0:
                lines.addTwoPointRectangle(
                    adsk.core.Point3D.create(0, 0, 0),
                    adsk.core.Point3D.create(self._cm(width), self._cm(arch_center_z), 0)
                )

            # Semicircular arc on top
            center = adsk.core.Point3D.create(self._cm(arch_center_x), self._cm(arch_center_z), 0)
            start = adsk.core.Point3D.create(0, self._cm(arch_center_z), 0)
            end = adsk.core.Point3D.create(self._cm(width), self._cm(arch_center_z), 0)

            arcs.addByCenterStartEnd(center, start, end)

            if sketch.profiles.count == 0:
                _log("Op 080: No profile created", error=True)
                return False

            # Extrude cut through entire depth
            extrudes = comp.features.extrudeFeatures
            profile = sketch.profiles.item(0)
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(depth))
            )

            feature = extrudes.add(ext_input)
            feature.name = "Op080_Arch_Cut"

            _log(f"Op 080: Arch cut complete")
            return True

        except Exception as e:
            _log(f"Op 080 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_010_create_cylinder(
        self,
        comp: adsk.fusion.Component,
        diameter: float,
        height: float
    ) -> bool:
        """
        Op 010: Create cylindrical base for round bricks.

        Type: NewBodyFeatureOperation
        Input: None
        Output: Cylindrical body
        """
        try:
            _log(f"Op 010: Creating cylinder - diameter={diameter}mm, height={height}mm")

            sketch = comp.sketches.add(comp.xYConstructionPlane)
            sketch.name = "Op010_Cylinder_Base"
            circles = sketch.sketchCurves.sketchCircles

            # Draw circle at center
            center = adsk.core.Point3D.create(self._cm(diameter/2), self._cm(diameter/2), 0)
            circles.addByCenterRadius(center, self._cm(diameter/2))

            if sketch.profiles.count == 0:
                _log("Op 010: No profile created", error=True)
                return False

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(height))
            )

            feature = extrudes.add(ext_input)
            feature.name = "Op010_Cylinder"

            _log(f"Op 010: Cylinder base created")
            return True

        except Exception as e:
            _log(f"Op 010 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_020_hollow_cylinder(
        self,
        comp: adsk.fusion.Component,
        diameter: float,
        height: float
    ) -> bool:
        """
        Op 020: Hollow out cylindrical brick.

        Type: CutFeatureOperation
        Input: Solid cylinder
        Output: Hollow cylinder tube
        """
        try:
            inner_diameter = diameter - 2 * WALL_THICKNESS
            cut_depth = height - TOP_THICKNESS

            if inner_diameter <= 0 or cut_depth <= 0:
                _log("Op 020: Cylinder too small to hollow")
                return True

            _log(f"Op 020: Hollowing cylinder - inner_d={inner_diameter}mm")

            sketch = comp.sketches.add(comp.xYConstructionPlane)
            sketch.name = "Op020_Hollow_Cylinder"
            circles = sketch.sketchCurves.sketchCircles

            center = adsk.core.Point3D.create(self._cm(diameter/2), self._cm(diameter/2), 0)
            circles.addByCenterRadius(center, self._cm(inner_diameter/2))

            if sketch.profiles.count == 0:
                return False

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(cut_depth))
            )

            feature = extrudes.add(ext_input)
            feature.name = "Op020_Hollow_Cylinder"

            _log("Op 020: Cylinder hollowed")
            return True

        except Exception as e:
            _log(f"Op 020 Exception: {e}", error=True)
            return False

    def _op_035_add_tube_round(
        self,
        comp: adsk.fusion.Component,
        diameter: float,
        height: float
    ) -> bool:
        """
        Op 035: Add internal tube to round brick for stud grip.

        Type: JoinFeatureOperation
        Input: Hollow cylinder
        Output: Hollow cylinder with central tube for gripping studs

        The tube allows the round brick to grip onto studs from bricks below.
        Tube outer diameter (TUBE_OD) = 6.51mm grips the 4.8mm stud
        Tube inner diameter (TUBE_ID) = 4.8mm allows stacking
        """
        try:
            # Tube is at center of brick
            center_x = diameter / 2
            center_y = diameter / 2
            tube_height = height - TOP_THICKNESS  # Tube goes from bottom to underside of top

            if tube_height <= 0:
                _log("Op 035: No room for tube - brick too short")
                return True

            _log(f"Op 035: Adding central tube OD={TUBE_OD}mm, ID={TUBE_ID}mm")

            # Draw tube profile (annular ring)
            sketch = comp.sketches.add(comp.xYConstructionPlane)
            sketch.name = "Op035_Round_Tube"
            circles = sketch.sketchCurves.sketchCircles

            center = adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0)
            circles.addByCenterRadius(center, self._cm(TUBE_OD / 2))  # Outer circle
            circles.addByCenterRadius(center, self._cm(TUBE_ID / 2))  # Inner circle

            if sketch.profiles.count < 2:
                _log("Op 035: Could not create tube profile", error=True)
                return False

            # Find the annular ring profile (the one between the two circles)
            # It's typically the second profile (index 1) - the ring between circles
            tube_profile = None
            for i in range(sketch.profiles.count):
                profile = sketch.profiles.item(i)
                # The ring profile has 2 loops (inner and outer)
                if profile.profileLoops.count == 2:
                    tube_profile = profile
                    break

            if not tube_profile:
                # Fallback: try the first profile that's not the center hole
                tube_profile = sketch.profiles.item(0) if sketch.profiles.count > 0 else None

            if not tube_profile:
                _log("Op 035: Could not find tube profile", error=True)
                return False

            # Extrude tube
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                tube_profile,
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(tube_height))
            )

            feature = extrudes.add(ext_input)
            feature.name = "Op035_Central_Tube"

            _log(f"Op 035: Central tube added, height={tube_height}mm")
            return True

        except Exception as e:
            _log(f"Op 035 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_050_add_studs_round(
        self,
        comp: adsk.fusion.Component,
        diameter_studs: int,
        height: float
    ) -> bool:
        """
        Op 050: Add studs to round brick.

        For round 1x1: single center stud
        For round 2x2: 4 studs in standard pattern
        """
        try:
            diameter = diameter_studs * STUD_PITCH
            stud_z = height

            sketch = comp.sketches.add(comp.xYConstructionPlane)
            sketch.name = "Op050_Round_Studs"
            circles = sketch.sketchCurves.sketchCircles

            if diameter_studs == 1:
                # Single center stud
                center = adsk.core.Point3D.create(self._cm(diameter/2), self._cm(diameter/2), self._cm(stud_z))
                circles.addByCenterRadius(center, self._cm(STUD_DIAMETER/2))
            else:
                # Standard stud pattern
                for i in range(diameter_studs):
                    for j in range(diameter_studs):
                        cx = (i + 0.5) * STUD_PITCH
                        cy = (j + 0.5) * STUD_PITCH
                        center = adsk.core.Point3D.create(self._cm(cx), self._cm(cy), 0)
                        circles.addByCenterRadius(center, self._cm(STUD_DIAMETER/2))

            # Create offset plane at top
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                comp.xYConstructionPlane,
                adsk.core.ValueInput.createByReal(self._cm(height))
            )
            top_plane = planes.add(plane_input)

            stud_sketch = comp.sketches.add(top_plane)
            stud_circles = stud_sketch.sketchCurves.sketchCircles

            if diameter_studs == 1:
                stud_circles.addByCenterRadius(
                    adsk.core.Point3D.create(self._cm(diameter/2), self._cm(diameter/2), 0),
                    self._cm(STUD_DIAMETER/2)
                )
            else:
                for i in range(diameter_studs):
                    for j in range(diameter_studs):
                        cx = (i + 0.5) * STUD_PITCH
                        cy = (j + 0.5) * STUD_PITCH
                        stud_circles.addByCenterRadius(
                            adsk.core.Point3D.create(self._cm(cx), self._cm(cy), 0),
                            self._cm(STUD_DIAMETER/2)
                        )

            # Extrude studs
            extrudes = comp.features.extrudeFeatures
            for i in range(stud_sketch.profiles.count):
                ext_input = extrudes.createInput(
                    stud_sketch.profiles.item(i),
                    adsk.fusion.FeatureOperations.JoinFeatureOperation
                )
                ext_input.setDistanceExtent(
                    False,
                    adsk.core.ValueInput.createByReal(self._cm(STUD_HEIGHT))
                )
                extrudes.add(ext_input)

            return True

        except Exception as e:
            _log(f"Op 050 Exception: {e}", error=True)
            return False

    def _op_050_add_studs_slope(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float,
        slope_direction: str
    ) -> bool:
        """
        Op 050: Add studs to slope brick (only on flat portion).

        For front/back slopes: studs on back row(s)
        For left/right slopes: studs on opposite side
        """
        try:
            # Determine which studs to add based on slope direction
            if slope_direction == "front":
                # Add studs at back only (last row)
                stud_range_x = range(studs_x)
                stud_range_y = range(max(1, studs_y - 1), studs_y)
            elif slope_direction == "back":
                # Add studs at front only
                stud_range_x = range(studs_x)
                stud_range_y = range(min(1, studs_y))
            elif slope_direction == "left":
                # Add studs at right only
                stud_range_x = range(max(1, studs_x - 1), studs_x)
                stud_range_y = range(studs_y)
            else:  # right
                # Add studs at left only
                stud_range_x = range(min(1, studs_x))
                stud_range_y = range(studs_y)

            # Create offset plane at top
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                comp.xYConstructionPlane,
                adsk.core.ValueInput.createByReal(self._cm(height))
            )
            top_plane = planes.add(plane_input)

            sketch = comp.sketches.add(top_plane)
            sketch.name = "Op050_Slope_Studs"
            circles = sketch.sketchCurves.sketchCircles

            for i in stud_range_x:
                for j in stud_range_y:
                    cx = (i + 0.5) * STUD_PITCH
                    cy = (j + 0.5) * STUD_PITCH
                    circles.addByCenterRadius(
                        adsk.core.Point3D.create(self._cm(cx), self._cm(cy), 0),
                        self._cm(STUD_DIAMETER/2)
                    )

            # Extrude studs
            extrudes = comp.features.extrudeFeatures
            for i in range(sketch.profiles.count):
                ext_input = extrudes.createInput(
                    sketch.profiles.item(i),
                    adsk.fusion.FeatureOperations.JoinFeatureOperation
                )
                ext_input.setDistanceExtent(
                    False,
                    adsk.core.ValueInput.createByReal(self._cm(STUD_HEIGHT))
                )
                extrudes.add(ext_input)

            return True

        except Exception as e:
            _log(f"Op 050 Exception: {e}", error=True)
            return False

    def _op_100_add_technic_holes(
        self,
        comp: adsk.fusion.Component,
        studs_x: int,
        studs_y: int,
        height: float,
        hole_axis: str,
        hole_type: str
    ) -> bool:
        """
        Op 100: Add Technic holes through brick.

        Type: CutFeatureOperation
        Input: Brick body
        Output: Brick with pin/axle holes

        Holes are positioned at center height, at each stud position.
        hole_axis specifies which direction holes run ALONG:
        - "x": holes run along X axis (through brick width), one hole per Y stud position
        - "y": holes run along Y axis (through brick depth), one hole per X stud position

        For typical 1x6 Technic brick: holes along Y go through the long dimension.
        """
        try:
            hole_diameter = 4.8 if hole_type == "pin" else 5.0  # Pin vs axle
            hole_z = height / 2  # Center height
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH

            _log(f"Op 100: Creating technic holes along {hole_axis} axis")
            _log(f"  Brick dims: {width}x{depth}x{height}mm, studs: {studs_x}x{studs_y}")

            # Determine hole positions and cut direction
            if hole_axis == "x":
                # Holes run ALONG X axis (through the width)
                # One hole for each stud position along Y
                # Sketch on YZ plane (perpendicular to X)
                num_holes = studs_y
                cut_distance = width  # Through the X dimension

                # Create offset plane at X=0 to ensure proper direction
                sketch = comp.sketches.add(comp.yZConstructionPlane)
                sketch.name = "Op100_Technic_Holes_X"
                circles = sketch.sketchCurves.sketchCircles

                # On YZ plane: first coord = Y, second coord = Z
                for j in range(studs_y):
                    cy = (j + 0.5) * STUD_PITCH
                    center = adsk.core.Point3D.create(self._cm(cy), self._cm(hole_z), 0)
                    circles.addByCenterRadius(center, self._cm(hole_diameter/2))
                    _log(f"  Hole at Y={cy}mm, Z={hole_z}mm")

            else:
                # Holes run ALONG Y axis (through the depth)
                # One hole for each stud position along X
                # Sketch on XZ plane (perpendicular to Y)
                num_holes = studs_x
                cut_distance = depth  # Through the Y dimension

                sketch = comp.sketches.add(comp.xZConstructionPlane)
                sketch.name = "Op100_Technic_Holes_Y"
                circles = sketch.sketchCurves.sketchCircles

                # On XZ plane: first coord = X, second coord = Z
                for i in range(studs_x):
                    cx = (i + 0.5) * STUD_PITCH
                    center = adsk.core.Point3D.create(self._cm(cx), self._cm(hole_z), 0)
                    circles.addByCenterRadius(center, self._cm(hole_diameter/2))
                    _log(f"  Hole at X={cx}mm, Z={hole_z}mm")

            _log(f"Op 100: Created {num_holes} hole circles, cut distance={cut_distance}mm")

            if sketch.profiles.count == 0:
                _log("Op 100: No profiles created - holes may be outside brick", error=True)
                return False

            # Cut holes through brick using TwoSidesExtent to ensure we go all the way through
            # The construction planes are at origin, so we need to cut in BOTH directions
            extrudes = comp.features.extrudeFeatures
            holes_cut = 0

            # Use a large distance to ensure we cut through the entire brick
            # This is more reliable than AllExtent which can be tricky
            large_distance = adsk.core.ValueInput.createByReal(self._cm(max(width, depth) + 10))

            for i in range(sketch.profiles.count):
                profile = sketch.profiles.item(i)
                ext_input = extrudes.createInput(
                    profile,
                    adsk.fusion.FeatureOperations.CutFeatureOperation
                )
                # Use symmetric extent - cuts equal distance in both directions from sketch plane
                # Since sketch is at origin (edge of brick), we cut from -distance to +distance
                ext_input.setSymmetricExtent(large_distance, True)  # True = symmetric

                try:
                    feature = extrudes.add(ext_input)
                    feature.name = f"Op100_Hole_{holes_cut + 1}"
                    holes_cut += 1
                except Exception as e:
                    _log(f"Op 100: Failed to cut hole {i}: {e}", error=True)

            _log(f"Op 100: Cut {holes_cut}/{num_holes} holes")
            return holes_cut == num_holes

        except Exception as e:
            _log(f"Op 100 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_075_cut_wedge(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float,
        direction: str
    ) -> bool:
        """
        Op 075: Cut wedge shape using triangular cutting body.

        Type: CutFeatureOperation via Combine
        Input: Solid brick body
        Output: Wedge-shaped brick (tapers from full height to zero)

        A wedge tapers from full height on one edge to zero height on the opposite edge.
        Strategy: Create triangular prism cutting body, then use Combine to subtract.
        """
        try:
            _log(f"Op 075: Cutting wedge in {direction} direction")

            # Get the main body
            if comp.bRepBodies.count == 0:
                _log("Op 075: No body to cut", error=True)
                return False

            main_body = comp.bRepBodies.item(0)

            # Wedge is like a 45° slope that cuts all the way through
            # Draw triangle on side plane, extrude across width/depth

            if direction == "front":
                # Wedge tapers toward front (Y=0 is lowest, Y=depth is full height)
                sketch = comp.sketches.add(comp.xZConstructionPlane)
                sketch.name = "Op075_WedgeProfile"
                lines = sketch.sketchCurves.sketchLines

                # Triangle: full width at top, comes to edge at bottom
                p1 = adsk.core.Point3D.create(0, 0, 0)  # Bottom front
                p2 = adsk.core.Point3D.create(self._cm(width), 0, 0)  # Bottom front (other side)
                p3 = adsk.core.Point3D.create(self._cm(width), self._cm(height), 0)  # Top
                p4 = adsk.core.Point3D.create(0, self._cm(height), 0)  # Top

                # Draw full rectangle profile for cutting body
                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

                extrude_dist = depth

            elif direction == "back":
                # Need offset plane at Y=depth
                planes = comp.constructionPlanes
                plane_input = planes.createInput()
                plane_input.setByOffset(
                    comp.xZConstructionPlane,
                    adsk.core.ValueInput.createByReal(self._cm(depth))
                )
                back_plane = planes.add(plane_input)
                back_plane.name = "Op075_BackPlane"

                sketch = comp.sketches.add(back_plane)
                sketch.name = "Op075_WedgeProfile"
                lines = sketch.sketchCurves.sketchLines

                # Rectangle for wedge cutting
                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(width), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(width), self._cm(height), 0)
                p4 = adsk.core.Point3D.create(0, self._cm(height), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

                extrude_dist = depth

            elif direction == "left":
                # Wedge tapers toward left (X=0 is lowest)
                sketch = comp.sketches.add(comp.yZConstructionPlane)
                sketch.name = "Op075_WedgeProfile"
                lines = sketch.sketchCurves.sketchLines

                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(depth), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(depth), self._cm(height), 0)
                p4 = adsk.core.Point3D.create(0, self._cm(height), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

                extrude_dist = width

            else:  # right
                # Need offset plane at X=width
                planes = comp.constructionPlanes
                plane_input = planes.createInput()
                plane_input.setByOffset(
                    comp.yZConstructionPlane,
                    adsk.core.ValueInput.createByReal(self._cm(width))
                )
                right_plane = planes.add(plane_input)
                right_plane.name = "Op075_RightPlane"

                sketch = comp.sketches.add(right_plane)
                sketch.name = "Op075_WedgeProfile"
                lines = sketch.sketchCurves.sketchLines

                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(depth), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(depth), self._cm(height), 0)
                p4 = adsk.core.Point3D.create(0, self._cm(height), 0)

                lines.addByTwoPoints(p1, p2)
                lines.addByTwoPoints(p2, p3)
                lines.addByTwoPoints(p3, p4)
                lines.addByTwoPoints(p4, p1)

                extrude_dist = width

            if sketch.profiles.count == 0:
                _log("Op 075: No profile created", error=True)
                return False

            profile = sketch.profiles.item(0)

            # Create cutting body as NewBody first
            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                profile,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )

            # Calculate taper for wedge: from full height to zero
            if direction in ["left", "right"]:
                taper_rad = math.atan(height / width)
            else:
                taper_rad = math.atan(height / depth)

            ext_input.setDistanceExtent(
                False,
                adsk.core.ValueInput.createByReal(self._cm(extrude_dist))
            )

            # Add taper to create wedge shape
            ext_input.taperAngle = adsk.core.ValueInput.createByReal(-taper_rad)

            cut_feature = extrudes.add(ext_input)
            cut_feature.name = "Op075_CuttingBody"

            if cut_feature.bodies.count == 0:
                _log("Op 075: No cutting body created", error=True)
                return False

            cutting_body = cut_feature.bodies.item(0)

            # Use Combine to subtract
            combines = comp.features.combineFeatures
            combine_input = combines.createInput(main_body, adsk.core.ObjectCollection.create())
            combine_input.toolBodies.add(cutting_body)
            combine_input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
            combine_input.isKeepToolBodies = False

            combine = combines.add(combine_input)
            combine.name = "Op075_WedgeCut"

            _log(f"Op 075: Wedge cut complete using combine operation")
            return True

        except Exception as e:
            _log(f"Op 075 Exception: {e}", error=True)
            _log(traceback.format_exc(), error=True)
            return False

    def _op_076_cut_inverted_slope(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float,
        angle: int,
        direction: str
    ) -> bool:
        """
        Op 076: Cut inverted slope from bottom of brick.

        Type: CutFeatureOperation
        Input: Solid brick body
        Output: Brick with inverted slope on bottom
        """
        try:
            _log(f"Op 076: Cutting inverted {angle}° slope in {direction} direction")

            slope_run = height / math.tan(math.radians(angle))

            if direction in ["front", "back"]:
                sketch = comp.sketches.add(comp.xZConstructionPlane)
                cut_extent = width
            else:
                sketch = comp.sketches.add(comp.yZConstructionPlane)
                cut_extent = depth

            sketch.name = f"Op076_InvSlope_{direction}"
            lines = sketch.sketchCurves.sketchLines

            # Inverted slope cuts from bottom
            if direction == "front":
                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(min(slope_run, depth)), 0, 0)
                p3 = adsk.core.Point3D.create(0, self._cm(height), 0)
            elif direction == "back":
                p1 = adsk.core.Point3D.create(self._cm(depth), 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(depth - min(slope_run, depth)), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(depth), self._cm(height), 0)
            elif direction == "left":
                p1 = adsk.core.Point3D.create(0, 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(min(slope_run, width)), 0, 0)
                p3 = adsk.core.Point3D.create(0, self._cm(height), 0)
            else:  # right
                p1 = adsk.core.Point3D.create(self._cm(width), 0, 0)
                p2 = adsk.core.Point3D.create(self._cm(width - min(slope_run, width)), 0, 0)
                p3 = adsk.core.Point3D.create(self._cm(width), self._cm(height), 0)

            lines.addByTwoPoints(p1, p2)
            lines.addByTwoPoints(p2, p3)
            lines.addByTwoPoints(p3, p1)

            if sketch.profiles.count == 0:
                return False

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(cut_extent)))
            extrudes.add(ext_input)

            _log("Op 076: Inverted slope cut complete")
            return True

        except Exception as e:
            _log(f"Op 076 Exception: {e}", error=True)
            return False

    def _op_051_add_centered_stud(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float
    ) -> bool:
        """
        Op 051: Add single centered stud for jumper plates.

        Type: JoinFeatureOperation
        Input: Brick body
        Output: Brick with single centered stud
        """
        try:
            _log("Op 051: Adding centered stud")

            # Create offset plane at top
            planes = comp.constructionPlanes
            plane_input = planes.createInput()
            plane_input.setByOffset(
                comp.xYConstructionPlane,
                adsk.core.ValueInput.createByReal(self._cm(height))
            )
            top_plane = planes.add(plane_input)

            sketch = comp.sketches.add(top_plane)
            sketch.name = "Op051_Centered_Stud"
            circles = sketch.sketchCurves.sketchCircles

            # Centered stud
            center_x = width / 2
            center_y = depth / 2
            circles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0),
                self._cm(STUD_DIAMETER / 2)
            )

            if sketch.profiles.count == 0:
                return False

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(STUD_HEIGHT)))
            extrudes.add(ext_input)

            _log("Op 051: Centered stud added")
            return True

        except Exception as e:
            _log(f"Op 051 Exception: {e}", error=True)
            return False

    def _op_110_add_hinge(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float,
        hinge_type: str
    ) -> bool:
        """
        Op 110: Add hinge cylinder to brick.

        Type: JoinFeatureOperation
        Input: Brick body
        Output: Brick with hinge protrusion
        """
        try:
            _log(f"Op 110: Adding {hinge_type} hinge")

            hinge_radius = 2.0  # mm
            hinge_length = 4.0  # mm

            if hinge_type == "top":
                # Hinge on top edge
                planes = comp.constructionPlanes
                plane_input = planes.createInput()
                plane_input.setByOffset(
                    comp.xYConstructionPlane,
                    adsk.core.ValueInput.createByReal(self._cm(height))
                )
                hinge_plane = planes.add(plane_input)
                sketch = comp.sketches.add(hinge_plane)
                center_x = width / 2
                center_y = depth + hinge_radius
            elif hinge_type == "bottom":
                sketch = comp.sketches.add(comp.xYConstructionPlane)
                center_x = width / 2
                center_y = -hinge_radius
            else:  # side
                sketch = comp.sketches.add(comp.yZConstructionPlane)
                center_x = depth / 2
                center_y = height / 2

            sketch.name = f"Op110_Hinge_{hinge_type}"
            circles = sketch.sketchCurves.sketchCircles
            circles.addByCenterRadius(
                adsk.core.Point3D.create(self._cm(center_x), self._cm(center_y), 0),
                self._cm(hinge_radius)
            )

            if sketch.profiles.count == 0:
                return False

            extrudes = comp.features.extrudeFeatures
            ext_input = extrudes.createInput(
                sketch.profiles.item(0),
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )
            ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(hinge_length)))
            extrudes.add(ext_input)

            _log("Op 110: Hinge added")
            return True

        except Exception as e:
            _log(f"Op 110 Exception: {e}", error=True)
            return False

    def _op_120_apply_modification(
        self,
        comp: adsk.fusion.Component,
        width: float,
        depth: float,
        height: float,
        modification: str
    ) -> bool:
        """
        Op 120: Apply decorative modification to brick face.

        Type: CutFeatureOperation
        Input: Brick body
        Output: Brick with decorative pattern
        """
        try:
            _log(f"Op 120: Applying {modification} modification")

            sketch = comp.sketches.add(comp.xZConstructionPlane)
            sketch.name = f"Op120_{modification}"
            lines = sketch.sketchCurves.sketchLines

            if modification == "grille":
                # Horizontal grooves
                groove_spacing = height / 4
                groove_depth = 1.0
                for i in range(1, 4):
                    y = i * groove_spacing
                    lines.addTwoPointRectangle(
                        adsk.core.Point3D.create(-self._cm(groove_depth), self._cm(y - 0.5), 0),
                        adsk.core.Point3D.create(0, self._cm(y + 0.5), 0)
                    )

            elif modification == "log":
                # Rounded log pattern (simplified as groove)
                lines.addTwoPointRectangle(
                    adsk.core.Point3D.create(-self._cm(1.5), self._cm(height * 0.2), 0),
                    adsk.core.Point3D.create(0, self._cm(height * 0.8), 0)
                )

            elif modification == "masonry":
                # Brick pattern grooves
                groove_depth = 0.5
                for row in range(2):
                    y = (row + 0.5) * (height / 2)
                    lines.addTwoPointRectangle(
                        adsk.core.Point3D.create(-self._cm(groove_depth), self._cm(y - 0.3), 0),
                        adsk.core.Point3D.create(0, self._cm(y + 0.3), 0)
                    )

            else:  # smooth - no modification
                return True

            if sketch.profiles.count == 0:
                return True  # No profiles is ok for some modifications

            extrudes = comp.features.extrudeFeatures
            for i in range(sketch.profiles.count):
                try:
                    ext_input = extrudes.createInput(
                        sketch.profiles.item(i),
                        adsk.fusion.FeatureOperations.CutFeatureOperation
                    )
                    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(self._cm(width)))
                    extrudes.add(ext_input)
                except:
                    pass

            _log(f"Op 120: {modification} modification applied")
            return True

        except Exception as e:
            _log(f"Op 120 Exception: {e}", error=True)
            return False

    def _get_top_face(
        self,
        body: adsk.fusion.BRepBody,
        height: float
    ) -> Optional[adsk.fusion.BRepFace]:
        """Find the top face of a body at given height."""
        target_z = self._cm(height)
        for face in body.faces:
            centroid = face.centroid
            if abs(centroid.z - target_z) < 0.001:
                return face
        return None

    def _get_top_face_by_normal(
        self,
        body: adsk.fusion.BRepBody
    ) -> Optional[adsk.fusion.BRepFace]:
        """Find the top face by checking face normal (pointing in +Z direction)."""
        best_face = None
        highest_z = -float('inf')

        for face in body.faces:
            # Check if this is a planar face with normal pointing up
            geom = face.geometry
            if geom.objectType == adsk.core.Plane.classType():
                plane = adsk.core.Plane.cast(geom)
                normal = plane.normal
                # Normal pointing up (+Z) with tolerance
                if abs(normal.x) < 0.01 and abs(normal.y) < 0.01 and normal.z > 0.9:
                    # Get the Z coordinate of this face
                    centroid = face.centroid
                    if centroid.z > highest_z:
                        highest_z = centroid.z
                        best_face = face

        return best_face
    
    def _get_bottom_face(
        self,
        body: adsk.fusion.BRepBody
    ) -> Optional[adsk.fusion.BRepFace]:
        """Find the bottom face of a body (z=0)."""
        for face in body.faces:
            centroid = face.centroid
            if abs(centroid.z) < 0.001:
                return face
        return None
    
    # === Additional Brick Types ===
    
    def create_plate(
        self,
        studs_x: int,
        studs_y: int,
        name: Optional[str] = None
    ) -> BrickResult:
        """Create a plate (1/3 height brick)."""
        return self.create_standard_brick(
            studs_x=studs_x,
            studs_y=studs_y,
            height_units=1/3,
            hollow=True,
            name=name or f"Plate_{studs_x}x{studs_y}"
        )
    
    def create_tile(
        self,
        studs_x: int,
        studs_y: int,
        name: Optional[str] = None
    ) -> BrickResult:
        """Create a tile (flat, no studs)."""
        try:
            width = studs_x * STUD_PITCH
            depth = studs_y * STUD_PITCH
            height = PLATE_HEIGHT
            
            brick_id = self._generate_brick_id("tile")
            comp_name = name or f"Tile_{studs_x}x{studs_y}"
            
            # Create component
            occ = self.root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            comp = occ.component
            comp.name = comp_name
            
            # Just a flat box, no studs
            self._op_010_create_base(comp, width, depth, height)
            
            # Small groove on top edge (like real tiles)
            # This helps with removal - skip for simplicity
            
            volume = 0.0
            for body in comp.bRepBodies:
                volume += body.volume * 1000
            
            return BrickResult(
                success=True,
                brick_id=brick_id,
                component_name=comp_name,
                dimensions={
                    "width_mm": width,
                    "depth_mm": depth,
                    "height_mm": height,
                    "studs_x": studs_x,
                    "studs_y": studs_y
                },
                volume_mm3=volume
            )
        except Exception as e:
            return BrickResult(
                success=False,
                brick_id="",
                component_name="",
                dimensions={},
                volume_mm3=0,
                error=str(e)
            )

    # === Export Functions ===
    
    def export_stl(
        self,
        component_name: str,
        output_path: str,
        resolution: str = "high"
    ) -> Dict[str, Any]:
        """
        Export a component as STL file.

        Args:
            component_name: Name of component to export
            output_path: Full path for output STL file
            resolution: "low", "medium", "high"

        Returns:
            Dict with path, size, triangle count
        """
        import os
        import traceback

        # Find component - check both occurrences and root
        comp = None

        # First check if it's the root component
        if self.root.name == component_name:
            comp = self.root
        else:
            # Check occurrences
            for occ in self.root.occurrences:
                if occ.component.name == component_name:
                    comp = occ.component
                    break

        if not comp:
            available = [self.root.name] + [occ.component.name for occ in self.root.occurrences]
            raise Exception(f"Component not found: {component_name}. Available: {available}")

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            # Set up export
            export_mgr = self.design.exportManager

            # STL export options
            stl_options = export_mgr.createSTLExportOptions(comp)
            stl_options.filename = output_path

            # Resolution settings
            if resolution == "low":
                stl_options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementLow
            elif resolution == "medium":
                stl_options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementMedium
            else:
                stl_options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh

            # Export with error checking
            result = export_mgr.execute(stl_options)

            if not result:
                raise Exception("Export failed - Fusion 360 returned False")

            # Verify file was created
            if not os.path.exists(output_path):
                raise Exception(f"Export completed but file not found at: {output_path}")

            # Get file info
            file_size = os.path.getsize(output_path) / 1024  # KB

            # Estimate triangle count (rough approximation)
            triangle_count = int(file_size * 15)  # ~15 triangles per KB for STL

            return {
                "path": output_path,
                "size_kb": file_size,
                "triangle_count": triangle_count
            }

        except Exception as e:
            error_msg = f"STL export failed: {str(e)}\n{traceback.format_exc()}"
            raise Exception(error_msg)
    
    def get_component_by_name(self, name: str) -> Optional[adsk.fusion.Component]:
        """Find a component by name."""
        for occ in self.root.occurrences:
            if occ.component.name == name:
                return occ.component
        return None
    
    def list_components(self) -> List[str]:
        """List all component names in the design."""
        return [occ.component.name for occ in self.root.occurrences]
