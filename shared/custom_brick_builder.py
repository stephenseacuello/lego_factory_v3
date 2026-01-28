"""
Custom Brick Builder - Create ANY LEGO Element

This module provides a flexible system for creating custom LEGO bricks
by combining features. You can create bricks that don't exist in the
standard catalog by specifying exactly what features you want.

Usage:
    builder = CustomBrickBuilder()

    # Create a custom 3x3 brick with Technic holes
    brick = (builder
        .set_base(3, 3, height_plates=3)
        .add_studs()
        .add_technic_holes(axis='x', rows=[0, 2])
        .hollow_bottom()
        .add_tubes()
        .build("my_custom_brick"))
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Literal, Any
from enum import Enum, auto
import copy

# Import shared specs
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from lego_specs import LEGO, brick_dimensions, stud_positions, tube_positions


# ============================================================================
# CUSTOM BRICK DEFINITION
# ============================================================================


@dataclass
class StudDefinition:
    """Definition of a single stud."""

    x: float  # Position in stud units
    y: float
    type: str = "solid"  # solid, hollow, recessed
    diameter_mm: float = 4.8
    height_mm: float = 1.7


@dataclass
class TubeDefinition:
    """Definition of a bottom tube."""

    x: float  # Position in stud units
    y: float
    outer_diameter_mm: float = 6.51
    inner_diameter_mm: float = 4.8
    height_mm: float = 8.6  # Default: brick height - top thickness


@dataclass
class RibDefinition:
    """Definition of a center rib (for 1xN bricks)."""

    position: float  # Position along length in stud units
    orientation: str  # 'x' or 'y'
    thickness_mm: float = 1.0
    height_mm: float = 8.6


@dataclass
class HoleDefinition:
    """Definition of a Technic-style hole."""

    x: float  # Position in stud units
    y: float
    z: float  # Height position (0 = bottom, 1 = middle of brick)
    axis: str  # 'x', 'y', or 'z' - direction hole goes through
    type: str = "pin"  # pin (round), axle (cross), pin_axle
    diameter_mm: float = 4.8


@dataclass
class SlopeDefinition:
    """Definition of a slope cut."""

    angle_degrees: float = 45.0
    direction: str = "front"  # front, back, left, right
    type: str = "straight"  # straight, curved, inverted
    start_height_mm: float = 0.0  # Where slope starts (from top)


@dataclass
class SideStudDefinition:
    """Definition of a side-mounted stud (SNOT)."""

    face: str  # front, back, left, right
    x: float  # Position on face (stud units along face)
    z: float  # Height position (stud units from bottom)
    type: str = "solid"


@dataclass
class ClipDefinition:
    """Definition of a clip attachment."""

    face: str  # front, back, left, right
    x: float
    z: float
    orientation: str = "horizontal"  # horizontal, vertical


@dataclass
class BarDefinition:
    """Definition of a bar/handle attachment."""

    face: str
    x: float
    z: float
    length_mm: float = 6.0
    diameter_mm: float = 3.18


@dataclass
class CutoutDefinition:
    """Definition of a cutout/hole in the brick."""

    face: str  # front, back, left, right, top, bottom
    shape: str  # rectangle, circle, arch, slot
    x: float  # Center position
    y: float
    width_mm: float
    height_mm: float
    depth_mm: float = 0  # 0 = through hole
    corner_radius_mm: float = 0  # For rounded rectangles


@dataclass
class TextDefinition:
    """Definition of embossed/debossed text."""

    text: str
    face: str
    x: float
    y: float
    height_mm: float = 2.0  # Text height
    depth_mm: float = 0.3  # Positive = embossed, negative = debossed
    font: str = "Arial"


@dataclass
class CustomBrickDefinition:
    """
    Complete definition of a custom LEGO brick.

    This is the output of the CustomBrickBuilder and can be passed
    to the brick generator to create the 3D model.
    """

    name: str

    # Base dimensions
    width_studs: int
    depth_studs: int
    height_plates: int

    # Computed dimensions (mm)
    width_mm: float = 0
    depth_mm: float = 0
    height_mm: float = 0

    # Shape modifiers
    is_round: bool = False
    is_hollow: bool = True

    # Wall structure
    wall_thickness_mm: float = 1.5
    top_thickness_mm: float = 1.0

    # Top features
    studs: List[StudDefinition] = field(default_factory=list)

    # Bottom features
    tubes: List[TubeDefinition] = field(default_factory=list)
    ribs: List[RibDefinition] = field(default_factory=list)

    # Technic features
    holes: List[HoleDefinition] = field(default_factory=list)

    # Slope features
    slopes: List[SlopeDefinition] = field(default_factory=list)

    # Side features (SNOT)
    side_studs: List[SideStudDefinition] = field(default_factory=list)
    clips: List[ClipDefinition] = field(default_factory=list)
    bars: List[BarDefinition] = field(default_factory=list)

    # Modifications
    cutouts: List[CutoutDefinition] = field(default_factory=list)
    text: List[TextDefinition] = field(default_factory=list)

    # Manufacturing
    tolerance_mm: float = 0.1
    notes: str = ""

    def __post_init__(self):
        """Calculate derived dimensions."""
        if self.width_mm == 0:
            self.width_mm = self.width_studs * LEGO.STUD_PITCH
        if self.depth_mm == 0:
            self.depth_mm = self.depth_studs * LEGO.STUD_PITCH
        if self.height_mm == 0:
            self.height_mm = self.height_plates * LEGO.PLATE_HEIGHT


# ============================================================================
# CUSTOM BRICK BUILDER - Fluent API
# ============================================================================


class CustomBrickBuilder:
    """
    Fluent builder for creating custom LEGO bricks.

    Example:
        brick = (CustomBrickBuilder()
            .set_base(2, 4, height_plates=3)
            .add_studs()
            .hollow_bottom()
            .add_tubes()
            .add_technic_hole(0, 0, axis='y')
            .add_technic_hole(0, 1, axis='y')
            .add_slope(45, direction='front')
            .build("custom_technic_slope_2x4"))
    """

    def __init__(self):
        """Initialize builder with defaults."""
        self._width_studs = 2
        self._depth_studs = 4
        self._height_plates = 3
        self._is_round = False
        self._is_hollow = True
        self._wall_thickness = LEGO.WALL_THICKNESS
        self._top_thickness = LEGO.TOP_THICKNESS
        self._studs: List[StudDefinition] = []
        self._tubes: List[TubeDefinition] = []
        self._ribs: List[RibDefinition] = []
        self._holes: List[HoleDefinition] = []
        self._slopes: List[SlopeDefinition] = []
        self._side_studs: List[SideStudDefinition] = []
        self._clips: List[ClipDefinition] = []
        self._bars: List[BarDefinition] = []
        self._cutouts: List[CutoutDefinition] = []
        self._text: List[TextDefinition] = []
        self._tolerance = LEGO.TOLERANCE
        self._notes = ""

    # ========== BASE CONFIGURATION ==========

    def set_base(
        self, width_studs: int, depth_studs: int, height_plates: int = 3
    ) -> "CustomBrickBuilder":
        """
        Set the base dimensions of the brick.

        Args:
            width_studs: Width in stud units (X direction)
            depth_studs: Depth in stud units (Y direction)
            height_plates: Height in plate units (3 = one brick height)
        """
        self._width_studs = max(1, min(width_studs, 48))
        self._depth_studs = max(1, min(depth_studs, 48))
        self._height_plates = max(1, min(height_plates, 36))
        return self

    def set_round(self, is_round: bool = True) -> "CustomBrickBuilder":
        """Make the brick cylindrical/round."""
        self._is_round = is_round
        return self

    def set_hollow(self, is_hollow: bool = True) -> "CustomBrickBuilder":
        """Set whether the brick is hollow inside."""
        self._is_hollow = is_hollow
        return self

    def set_wall_thickness(self, thickness_mm: float) -> "CustomBrickBuilder":
        """Set wall thickness (default: 1.5mm)."""
        self._wall_thickness = max(0.5, min(thickness_mm, 4.0))
        return self

    def set_tolerance(self, tolerance_mm: float) -> "CustomBrickBuilder":
        """Set manufacturing tolerance."""
        self._tolerance = max(0, min(tolerance_mm, 0.5))
        return self

    # ========== STUDS ==========

    def add_studs(
        self, stud_type: str = "solid", positions: Optional[List[Tuple[int, int]]] = None
    ) -> "CustomBrickBuilder":
        """
        Add studs to the top of the brick.

        Args:
            stud_type: "solid", "hollow", or "recessed"
            positions: List of (x, y) positions, or None for all positions
        """
        if positions is None:
            # Add studs at all standard positions
            for x in range(self._width_studs):
                for y in range(self._depth_studs):
                    self._studs.append(StudDefinition(x=x + 0.5, y=y + 0.5, type=stud_type))
        else:
            for x, y in positions:
                if 0 <= x < self._width_studs and 0 <= y < self._depth_studs:
                    self._studs.append(StudDefinition(x=x + 0.5, y=y + 0.5, type=stud_type))
        return self

    def add_stud(
        self, x: float, y: float, stud_type: str = "solid", offset_x: float = 0, offset_y: float = 0
    ) -> "CustomBrickBuilder":
        """
        Add a single stud at a specific position.

        Args:
            x, y: Position in stud units
            stud_type: "solid", "hollow", or "recessed"
            offset_x, offset_y: Offset from grid position (for jumper plates)
        """
        self._studs.append(
            StudDefinition(x=x + 0.5 + offset_x, y=y + 0.5 + offset_y, type=stud_type)
        )
        return self

    def add_jumper_stud(self) -> "CustomBrickBuilder":
        """Add a single centered stud (jumper plate style)."""
        center_x = self._width_studs / 2
        center_y = self._depth_studs / 2
        self._studs.append(StudDefinition(x=center_x, y=center_y, type="solid"))
        return self

    def no_studs(self) -> "CustomBrickBuilder":
        """Remove all studs (tile style)."""
        self._studs = []
        return self

    # ========== BOTTOM STRUCTURE ==========

    def hollow_bottom(self) -> "CustomBrickBuilder":
        """Make the bottom hollow (standard for most bricks)."""
        self._is_hollow = True
        return self

    def solid_bottom(self) -> "CustomBrickBuilder":
        """Make the bottom solid (for baseplates)."""
        self._is_hollow = False
        return self

    def add_tubes(self) -> "CustomBrickBuilder":
        """
        Add bottom tubes for clutch power.
        Automatically positions tubes between studs.
        """
        if self._width_studs < 2 or self._depth_studs < 2:
            return self  # No tubes for 1xN bricks

        tube_height = self._height_plates * LEGO.PLATE_HEIGHT - LEGO.TOP_THICKNESS

        for x in range(self._width_studs - 1):
            for y in range(self._depth_studs - 1):
                self._tubes.append(TubeDefinition(x=x + 1.0, y=y + 1.0, height_mm=tube_height))
        return self

    def add_tube(self, x: float, y: float) -> "CustomBrickBuilder":
        """Add a single tube at specific position."""
        tube_height = self._height_plates * LEGO.PLATE_HEIGHT - LEGO.TOP_THICKNESS
        self._tubes.append(TubeDefinition(x=x, y=y, height_mm=tube_height))
        return self

    def add_ribs(self) -> "CustomBrickBuilder":
        """
        Add center ribs for clutch power (1xN bricks).
        """
        rib_height = self._height_plates * LEGO.PLATE_HEIGHT - LEGO.TOP_THICKNESS

        if self._width_studs == 1 and self._depth_studs > 1:
            # Vertical ribs along Y axis
            for y in range(self._depth_studs - 1):
                self._ribs.append(
                    RibDefinition(position=y + 1.0, orientation="x", height_mm=rib_height)
                )
        elif self._depth_studs == 1 and self._width_studs > 1:
            # Horizontal ribs along X axis
            for x in range(self._width_studs - 1):
                self._ribs.append(
                    RibDefinition(position=x + 1.0, orientation="y", height_mm=rib_height)
                )
        return self

    # ========== TECHNIC FEATURES ==========

    def add_technic_holes(
        self, axis: str = "x", hole_type: str = "pin", rows: Optional[List[int]] = None
    ) -> "CustomBrickBuilder":
        """
        Add Technic holes through the brick.

        Args:
            axis: Direction of holes ('x', 'y', or 'z')
            hole_type: 'pin' (round), 'axle' (cross), or 'pin_axle'
            rows: Which rows to add holes to (None = all)
        """
        if axis == "x":
            # Holes go through in X direction
            positions = range(self._depth_studs) if rows is None else rows
            for y in positions:
                if 0 <= y < self._depth_studs:
                    self._holes.append(
                        HoleDefinition(x=0, y=y + 0.5, z=0.5, axis="x", type=hole_type)
                    )
        elif axis == "y":
            # Holes go through in Y direction
            positions = range(self._width_studs) if rows is None else rows
            for x in positions:
                if 0 <= x < self._width_studs:
                    self._holes.append(
                        HoleDefinition(x=x + 0.5, y=0, z=0.5, axis="y", type=hole_type)
                    )
        elif axis == "z":
            # Vertical holes
            for x in range(self._width_studs):
                for y in range(self._depth_studs):
                    if rows is None or (x in rows or y in rows):
                        self._holes.append(
                            HoleDefinition(x=x + 0.5, y=y + 0.5, z=0, axis="z", type=hole_type)
                        )
        return self

    def add_technic_hole(
        self, x: float, y: float, z: float = 0.5, axis: str = "x", hole_type: str = "pin"
    ) -> "CustomBrickBuilder":
        """Add a single Technic hole at specific position."""
        self._holes.append(HoleDefinition(x=x, y=y, z=z, axis=axis, type=hole_type))
        return self

    # ========== SLOPES ==========

    def add_slope(
        self, angle: float = 45.0, direction: str = "front", slope_type: str = "straight"
    ) -> "CustomBrickBuilder":
        """
        Add a slope to one side of the brick.

        Args:
            angle: Slope angle in degrees (18, 33, 45, 65, 75)
            direction: Which face to slope (front, back, left, right)
            slope_type: 'straight', 'curved', or 'inverted'
        """
        self._slopes.append(
            SlopeDefinition(angle_degrees=angle, direction=direction, type=slope_type)
        )

        # Remove studs from sloped area
        self._remove_studs_for_slope(angle, direction)
        return self

    def _remove_studs_for_slope(self, angle: float, direction: str):
        """Remove studs that would be on the sloped surface."""
        height_mm = self._height_plates * LEGO.PLATE_HEIGHT
        slope_run = height_mm / (angle * 3.14159 / 180)  # Approximate
        studs_affected = int(slope_run / LEGO.STUD_PITCH) + 1

        new_studs = []
        for stud in self._studs:
            remove = False
            if direction == "front" and stud.x <= studs_affected:
                remove = True
            elif direction == "back" and stud.x >= self._width_studs - studs_affected:
                remove = True
            elif direction == "left" and stud.y <= studs_affected:
                remove = True
            elif direction == "right" and stud.y >= self._depth_studs - studs_affected:
                remove = True

            if not remove:
                new_studs.append(stud)
        self._studs = new_studs

    def add_double_slope(self, angle: float = 45.0) -> "CustomBrickBuilder":
        """Add slopes on two opposite sides (roof peak)."""
        self._slopes.append(
            SlopeDefinition(angle_degrees=angle, direction="front", type="straight")
        )
        self._slopes.append(SlopeDefinition(angle_degrees=angle, direction="back", type="straight"))
        self._studs = []  # No studs on roof peak
        return self

    def add_inverted_slope(
        self, angle: float = 45.0, direction: str = "front"
    ) -> "CustomBrickBuilder":
        """Add an inverted slope (on the bottom)."""
        self._slopes.append(
            SlopeDefinition(angle_degrees=angle, direction=direction, type="inverted")
        )
        return self

    # ========== SIDE FEATURES (SNOT) ==========

    def add_side_studs(
        self, face: str, count: int = 1, z_position: float = 0.5
    ) -> "CustomBrickBuilder":
        """
        Add studs on the side of the brick (SNOT style).

        Args:
            face: 'front', 'back', 'left', 'right'
            count: Number of studs to add
            z_position: Height position in brick units
        """
        if face in ["front", "back"]:
            length = self._depth_studs
        else:
            length = self._width_studs

        for i in range(min(count, length)):
            self._side_studs.append(SideStudDefinition(face=face, x=i + 0.5, z=z_position))
        return self

    def add_side_stud(self, face: str, x: float, z: float = 0.5) -> "CustomBrickBuilder":
        """Add a single side stud at specific position."""
        self._side_studs.append(SideStudDefinition(face=face, x=x, z=z))
        return self

    def add_clip(
        self, face: str, x: float, z: float = 0.5, orientation: str = "horizontal"
    ) -> "CustomBrickBuilder":
        """Add a clip attachment."""
        self._clips.append(ClipDefinition(face=face, x=x, z=z, orientation=orientation))
        return self

    def add_bar(
        self, face: str, x: float, z: float = 0.5, length_mm: float = 6.0
    ) -> "CustomBrickBuilder":
        """Add a bar/handle attachment."""
        self._bars.append(BarDefinition(face=face, x=x, z=z, length_mm=length_mm))
        return self

    # ========== MODIFICATIONS ==========

    def add_cutout(
        self,
        face: str,
        shape: str,
        x: float,
        y: float,
        width_mm: float,
        height_mm: float,
        depth_mm: float = 0,
    ) -> "CustomBrickBuilder":
        """
        Add a cutout/hole to the brick.

        Args:
            face: Which face to cut (front, back, left, right, top, bottom)
            shape: 'rectangle', 'circle', 'arch', 'slot'
            x, y: Center position
            width_mm, height_mm: Size
            depth_mm: How deep to cut (0 = through hole)
        """
        self._cutouts.append(
            CutoutDefinition(
                face=face,
                shape=shape,
                x=x,
                y=y,
                width_mm=width_mm,
                height_mm=height_mm,
                depth_mm=depth_mm,
            )
        )
        return self

    def add_arch_cutout(
        self, width_studs: int = 2, height_mm: float = None
    ) -> "CustomBrickBuilder":
        """Add an arch-shaped cutout through the front/back."""
        if height_mm is None:
            height_mm = self._height_plates * LEGO.PLATE_HEIGHT * 0.7

        self._cutouts.append(
            CutoutDefinition(
                face="front",
                shape="arch",
                x=self._depth_studs / 2,
                y=0,
                width_mm=width_studs * LEGO.STUD_PITCH - 2,
                height_mm=height_mm,
                depth_mm=0,  # Through hole
            )
        )
        return self

    def add_text(
        self,
        text: str,
        face: str = "top",
        x: float = None,
        y: float = None,
        height_mm: float = 2.0,
        embossed: bool = True,
    ) -> "CustomBrickBuilder":
        """
        Add embossed or debossed text to the brick.

        Args:
            text: Text to add
            face: Which face to add text on
            x, y: Position (default: centered)
            height_mm: Text character height
            embossed: True for raised, False for recessed
        """
        if x is None:
            x = (self._width_studs * LEGO.STUD_PITCH) / 2
        if y is None:
            y = (self._depth_studs * LEGO.STUD_PITCH) / 2

        self._text.append(
            TextDefinition(
                text=text,
                face=face,
                x=x,
                y=y,
                height_mm=height_mm,
                depth_mm=0.3 if embossed else -0.3,
            )
        )
        return self

    def add_notes(self, notes: str) -> "CustomBrickBuilder":
        """Add manufacturing/design notes."""
        self._notes = notes
        return self

    # ========== BUILD ==========

    def build(self, name: str = "custom_brick") -> CustomBrickDefinition:
        """
        Build the final brick definition.

        Args:
            name: Name for the custom brick

        Returns:
            CustomBrickDefinition ready for the brick generator
        """
        return CustomBrickDefinition(
            name=name,
            width_studs=self._width_studs,
            depth_studs=self._depth_studs,
            height_plates=self._height_plates,
            is_round=self._is_round,
            is_hollow=self._is_hollow,
            wall_thickness_mm=self._wall_thickness,
            top_thickness_mm=self._top_thickness,
            studs=self._studs.copy(),
            tubes=self._tubes.copy(),
            ribs=self._ribs.copy(),
            holes=self._holes.copy(),
            slopes=self._slopes.copy(),
            side_studs=self._side_studs.copy(),
            clips=self._clips.copy(),
            bars=self._bars.copy(),
            cutouts=self._cutouts.copy(),
            text=self._text.copy(),
            tolerance_mm=self._tolerance,
            notes=self._notes,
        )

    def copy(self) -> "CustomBrickBuilder":
        """Create a copy of the builder (for variations)."""
        new_builder = CustomBrickBuilder()
        new_builder._width_studs = self._width_studs
        new_builder._depth_studs = self._depth_studs
        new_builder._height_plates = self._height_plates
        new_builder._is_round = self._is_round
        new_builder._is_hollow = self._is_hollow
        new_builder._wall_thickness = self._wall_thickness
        new_builder._top_thickness = self._top_thickness
        new_builder._studs = copy.deepcopy(self._studs)
        new_builder._tubes = copy.deepcopy(self._tubes)
        new_builder._ribs = copy.deepcopy(self._ribs)
        new_builder._holes = copy.deepcopy(self._holes)
        new_builder._slopes = copy.deepcopy(self._slopes)
        new_builder._side_studs = copy.deepcopy(self._side_studs)
        new_builder._clips = copy.deepcopy(self._clips)
        new_builder._bars = copy.deepcopy(self._bars)
        new_builder._cutouts = copy.deepcopy(self._cutouts)
        new_builder._text = copy.deepcopy(self._text)
        new_builder._tolerance = self._tolerance
        new_builder._notes = self._notes
        return new_builder

    def reset(self) -> "CustomBrickBuilder":
        """Reset the builder to defaults."""
        self.__init__()
        return self


# ============================================================================
# PRESET BUILDERS - Common Custom Patterns
# ============================================================================


def technic_brick(width: int, depth: int, axis: str = "x") -> CustomBrickBuilder:
    """Create a Technic brick with holes."""
    return (
        CustomBrickBuilder()
        .set_base(width, depth, height_plates=3)
        .add_studs()
        .hollow_bottom()
        .add_tubes()
        if width > 1 and depth > 1
        else (
            CustomBrickBuilder().add_ribs()
            if width == 1 or depth == 1
            else CustomBrickBuilder().add_technic_holes(axis=axis)
        )
    )


def slope_brick(
    width: int, depth: int, angle: float = 45, direction: str = "front"
) -> CustomBrickBuilder:
    """Create a slope brick."""
    return (
        CustomBrickBuilder()
        .set_base(width, depth, height_plates=3)
        .add_studs()
        .hollow_bottom()
        .add_tubes()
        if width > 1 and depth > 1
        else CustomBrickBuilder().add_slope(angle, direction)
    )


def snot_brick(width: int, depth: int, faces: List[str] = ["front"]) -> CustomBrickBuilder:
    """Create a brick with side studs."""
    builder = (
        CustomBrickBuilder().set_base(width, depth, height_plates=3).add_studs().hollow_bottom()
    )

    if width > 1 and depth > 1:
        builder.add_tubes()

    for face in faces:
        builder.add_side_studs(face, count=depth if face in ["front", "back"] else width)

    return builder


def tile(width: int, depth: int) -> CustomBrickBuilder:
    """Create a tile (no studs)."""
    return CustomBrickBuilder().set_base(width, depth, height_plates=1).no_studs().hollow_bottom()


def plate(width: int, depth: int) -> CustomBrickBuilder:
    """Create a plate (1/3 height)."""
    builder = (
        CustomBrickBuilder().set_base(width, depth, height_plates=1).add_studs().hollow_bottom()
    )

    if width > 1 and depth > 1:
        builder.add_tubes()
    elif width == 1 or depth == 1:
        builder.add_ribs()

    return builder


def brick(width: int, depth: int, height_bricks: int = 1) -> CustomBrickBuilder:
    """Create a standard brick."""
    builder = (
        CustomBrickBuilder()
        .set_base(width, depth, height_plates=3 * height_bricks)
        .add_studs()
        .hollow_bottom()
    )

    if width > 1 and depth > 1:
        builder.add_tubes()
    elif width == 1 or depth == 1:
        builder.add_ribs()

    return builder


def arch_brick(width: int, depth: int, arch_width_studs: int = None) -> CustomBrickBuilder:
    """Create an arch brick."""
    if arch_width_studs is None:
        arch_width_studs = depth - 2

    return (
        CustomBrickBuilder()
        .set_base(width, depth, height_plates=3)
        .add_studs()
        .hollow_bottom()
        .add_arch_cutout(width_studs=arch_width_studs)
    )


def round_brick(diameter_studs: int, height_bricks: int = 1) -> CustomBrickBuilder:
    """Create a round/cylindrical brick."""
    return (
        CustomBrickBuilder()
        .set_base(diameter_studs, diameter_studs, height_plates=3 * height_bricks)
        .set_round(True)
        .add_stud(diameter_studs / 2 - 0.5, diameter_studs / 2 - 0.5)
        .hollow_bottom()
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Create a custom 3x3 Technic brick with slopes
    custom_brick = (
        CustomBrickBuilder()
        .set_base(3, 3, height_plates=3)
        .add_studs(positions=[(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)])
        .hollow_bottom()
        .add_tubes()
        .add_technic_holes(axis="x", rows=[0, 2])
        .add_slope(45, direction="front")
        .add_side_stud("left", 1.5, 0.5)
        .add_notes("Custom Technic slope brick with side stud")
        .build("custom_technic_slope_3x3")
    )

    print(f"Created: {custom_brick.name}")
    print(
        f"Dimensions: {custom_brick.width_studs}x{custom_brick.depth_studs}x{custom_brick.height_plates} plates"
    )
    print(f"Studs: {len(custom_brick.studs)}")
    print(f"Tubes: {len(custom_brick.tubes)}")
    print(f"Technic holes: {len(custom_brick.holes)}")
    print(f"Slopes: {len(custom_brick.slopes)}")
    print(f"Side studs: {len(custom_brick.side_studs)}")
