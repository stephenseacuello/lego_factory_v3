"""
Brick Feature System - Modular Geometry Builder

This module provides a feature-based approach to building LEGO bricks.
Features can be combined to create any standard or custom brick.

Features:
- Base shapes (box, cylinder, cone, wedge)
- Top features (studs, tiles, technic holes)
- Bottom features (tubes, ribs, anti-studs)
- Side features (side studs, clips, bars, hinges)
- Modifications (slopes, curves, chamfers, holes)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union, Callable
from enum import Enum
import math

# Import LEGO dimensions
from .lego_specs import LEGO, brick_dimensions, stud_positions, tube_positions


# ============================================================================
# GEOMETRY PRIMITIVES
# ============================================================================


@dataclass
class Point3D:
    """3D point."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def __add__(self, other: "Point3D") -> "Point3D":
        return Point3D(self.x + other.x, self.y + other.y, self.z + other.z)


@dataclass
class BoundingBox:
    """Axis-aligned bounding box."""

    min_point: Point3D
    max_point: Point3D

    @property
    def width(self) -> float:
        return self.max_point.x - self.min_point.x

    @property
    def depth(self) -> float:
        return self.max_point.y - self.min_point.y

    @property
    def height(self) -> float:
        return self.max_point.z - self.min_point.z


# ============================================================================
# FEATURE OPERATIONS
# ============================================================================


class FeatureOperation(Enum):
    """How a feature modifies the brick."""

    ADD = "add"  # Add material (join)
    SUBTRACT = "subtract"  # Remove material (cut)
    INTERSECT = "intersect"


# ============================================================================
# BASE FEATURES
# ============================================================================


@dataclass
class BaseFeature:
    """Base class for all features."""

    name: str
    operation: FeatureOperation = FeatureOperation.ADD
    enabled: bool = True

    def get_geometry_params(self) -> Dict:
        """Return parameters for geometry generation."""
        raise NotImplementedError


@dataclass
class BoxFeature(BaseFeature):
    """Rectangular box base shape."""

    width: float = 8.0  # mm
    depth: float = 8.0  # mm
    height: float = 9.6  # mm
    origin: Point3D = field(default_factory=Point3D)

    def get_geometry_params(self) -> Dict:
        return {
            "type": "box",
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "origin": self.origin.to_tuple(),
        }


@dataclass
class CylinderFeature(BaseFeature):
    """Cylindrical shape."""

    diameter: float = 8.0
    height: float = 9.6
    center: Point3D = field(default_factory=Point3D)
    hollow: bool = False
    inner_diameter: float = 0.0

    def get_geometry_params(self) -> Dict:
        return {
            "type": "cylinder",
            "diameter": self.diameter,
            "height": self.height,
            "center": self.center.to_tuple(),
            "hollow": self.hollow,
            "inner_diameter": self.inner_diameter,
        }


@dataclass
class ConeFeature(BaseFeature):
    """Cone or truncated cone."""

    bottom_diameter: float = 8.0
    top_diameter: float = 0.0  # 0 = pointed cone
    height: float = 9.6
    center: Point3D = field(default_factory=Point3D)

    def get_geometry_params(self) -> Dict:
        return {
            "type": "cone",
            "bottom_diameter": self.bottom_diameter,
            "top_diameter": self.top_diameter,
            "height": self.height,
            "center": self.center.to_tuple(),
        }


@dataclass
class WedgeFeature(BaseFeature):
    """Triangular wedge shape."""

    width: float = 16.0
    depth: float = 32.0
    height: float = 9.6
    taper_side: str = "right"  # Which side tapers to point
    origin: Point3D = field(default_factory=Point3D)

    def get_geometry_params(self) -> Dict:
        return {
            "type": "wedge",
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "taper_side": self.taper_side,
            "origin": self.origin.to_tuple(),
        }


# ============================================================================
# TOP SURFACE FEATURES
# ============================================================================


@dataclass
class StudFeature(BaseFeature):
    """Standard LEGO studs on top surface."""

    positions: List[Tuple[float, float]] = field(default_factory=list)
    diameter: float = LEGO.STUD_DIAMETER
    height: float = LEGO.STUD_HEIGHT
    hollow: bool = False
    base_z: float = 0.0  # Z position of top surface

    @classmethod
    def from_grid(
        cls, studs_x: int, studs_y: int, base_z: float = 9.6, hollow: bool = False
    ) -> "StudFeature":
        """Create studs from grid specification."""
        positions = stud_positions(studs_x, studs_y)
        return cls(name="studs", positions=positions, base_z=base_z, hollow=hollow)

    @classmethod
    def jumper(cls, base_width: float, base_depth: float, base_z: float = 3.2) -> "StudFeature":
        """Create single centered jumper stud."""
        return cls(name="jumper_stud", positions=[(base_width / 2, base_depth / 2)], base_z=base_z)

    def get_geometry_params(self) -> Dict:
        return {
            "type": "studs",
            "positions": self.positions,
            "diameter": self.diameter,
            "height": self.height,
            "hollow": self.hollow,
            "base_z": self.base_z,
        }


@dataclass
class TileSurfaceFeature(BaseFeature):
    """Smooth tile surface (no studs)."""

    width: float = 8.0
    depth: float = 8.0
    groove_width: float = 0.4  # Small groove around edge

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "tile_surface",
            "width": self.width,
            "depth": self.depth,
            "groove_width": self.groove_width,
        }


# ============================================================================
# BOTTOM FEATURES
# ============================================================================


@dataclass
class TubeFeature(BaseFeature):
    """Bottom tubes for clutch mechanism."""

    positions: List[Tuple[float, float]] = field(default_factory=list)
    outer_diameter: float = LEGO.TUBE_OUTER_DIAMETER
    inner_diameter: float = LEGO.TUBE_INNER_DIAMETER
    height: float = 8.6  # From bottom to just below top

    @classmethod
    def from_grid(cls, studs_x: int, studs_y: int, brick_height: float = 9.6) -> "TubeFeature":
        """Create tubes from grid specification."""
        positions = tube_positions(studs_x, studs_y)
        tube_height = brick_height - LEGO.TOP_THICKNESS
        return cls(name="tubes", positions=positions, height=tube_height)

    def get_geometry_params(self) -> Dict:
        return {
            "type": "tubes",
            "positions": self.positions,
            "outer_diameter": self.outer_diameter,
            "inner_diameter": self.inner_diameter,
            "height": self.height,
        }


@dataclass
class RibFeature(BaseFeature):
    """Bottom ribs for 1xN bricks."""

    positions: List[Tuple[float, str]] = field(default_factory=list)  # (position, orientation)
    thickness: float = LEGO.RIB_THICKNESS
    height: float = 8.6
    length: float = 6.0  # Span of rib

    @classmethod
    def from_grid(cls, studs_x: int, studs_y: int, brick_height: float = 9.6) -> "RibFeature":
        """Create ribs for 1xN configuration."""
        positions = []
        rib_height = brick_height - LEGO.TOP_THICKNESS

        if studs_x == 1 and studs_y > 1:
            for i in range(studs_y - 1):
                positions.append(((i + 1) * LEGO.STUD_PITCH, "x"))
            length = LEGO.STUD_PITCH - 2 * LEGO.WALL_THICKNESS
        elif studs_y == 1 and studs_x > 1:
            for i in range(studs_x - 1):
                positions.append(((i + 1) * LEGO.STUD_PITCH, "y"))
            length = LEGO.STUD_PITCH - 2 * LEGO.WALL_THICKNESS
        else:
            return cls(name="ribs", positions=[], height=0)

        return cls(name="ribs", positions=positions, height=rib_height, length=length)

    def get_geometry_params(self) -> Dict:
        return {
            "type": "ribs",
            "positions": self.positions,
            "thickness": self.thickness,
            "height": self.height,
            "length": self.length,
        }


@dataclass
class HollowFeature(BaseFeature):
    """Hollow out the interior of a brick."""

    wall_thickness: float = LEGO.WALL_THICKNESS
    top_thickness: float = LEGO.TOP_THICKNESS
    open_bottom: bool = True

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "hollow",
            "wall_thickness": self.wall_thickness,
            "top_thickness": self.top_thickness,
            "open_bottom": self.open_bottom,
        }


@dataclass
class AntiStudFeature(BaseFeature):
    """Anti-stud (tube) on bottom for single-stud grip."""

    position: Tuple[float, float] = (4.0, 4.0)
    outer_diameter: float = LEGO.TUBE_OUTER_DIAMETER
    inner_diameter: float = LEGO.STUD_DIAMETER
    height: float = 1.7

    def get_geometry_params(self) -> Dict:
        return {
            "type": "anti_stud",
            "position": self.position,
            "outer_diameter": self.outer_diameter,
            "inner_diameter": self.inner_diameter,
            "height": self.height,
        }


# ============================================================================
# SIDE FEATURES
# ============================================================================


@dataclass
class SideStudFeature(BaseFeature):
    """Studs on the side of a brick (SNOT)."""

    side: str = "front"  # front, back, left, right
    positions: List[Tuple[float, float]] = field(default_factory=list)  # (along_side, up)
    diameter: float = LEGO.STUD_DIAMETER
    length: float = LEGO.STUD_HEIGHT
    recessed: bool = False  # Headlight brick style

    def get_geometry_params(self) -> Dict:
        return {
            "type": "side_studs",
            "side": self.side,
            "positions": self.positions,
            "diameter": self.diameter,
            "length": self.length,
            "recessed": self.recessed,
        }


@dataclass
class SideAntiStudFeature(BaseFeature):
    """Holes on side to accept studs."""

    side: str = "front"
    positions: List[Tuple[float, float]] = field(default_factory=list)
    diameter: float = LEGO.STUD_DIAMETER + 0.2  # Slightly larger for fit
    depth: float = LEGO.STUD_HEIGHT

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "side_anti_studs",
            "side": self.side,
            "positions": self.positions,
            "diameter": self.diameter,
            "depth": self.depth,
        }


@dataclass
class ClipFeature(BaseFeature):
    """Clip for holding bars."""

    side: str = "front"
    position: Tuple[float, float] = (4.0, 4.8)  # (along_side, up from bottom)
    orientation: str = "vertical"  # vertical or horizontal
    inner_diameter: float = 3.18  # Bar diameter
    outer_diameter: float = 5.0

    def get_geometry_params(self) -> Dict:
        return {
            "type": "clip",
            "side": self.side,
            "position": self.position,
            "orientation": self.orientation,
            "inner_diameter": self.inner_diameter,
            "outer_diameter": self.outer_diameter,
        }


@dataclass
class BarFeature(BaseFeature):
    """Horizontal or vertical bar."""

    side: str = "front"
    position: Tuple[float, float] = (4.0, 4.8)
    orientation: str = "horizontal"
    diameter: float = 3.18
    length: float = 3.0

    def get_geometry_params(self) -> Dict:
        return {
            "type": "bar",
            "side": self.side,
            "position": self.position,
            "orientation": self.orientation,
            "diameter": self.diameter,
            "length": self.length,
        }


# ============================================================================
# MODIFICATION FEATURES
# ============================================================================


@dataclass
class SlopeFeature(BaseFeature):
    """Cut a slope into the brick."""

    angle: float = 45.0
    direction: str = "front"  # front, back, left, right
    start_height: float = 0.0  # Where slope starts (from bottom)
    studs_removed: int = 0  # How many stud rows are removed by slope

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "slope_cut",
            "angle": self.angle,
            "direction": self.direction,
            "start_height": self.start_height,
            "studs_removed": self.studs_removed,
        }


@dataclass
class DoubleSlopeFeature(BaseFeature):
    """Roof ridge - slopes on two opposite sides."""

    angle: float = 45.0
    axis: str = "y"  # Slopes perpendicular to this axis
    ridge_width: float = 0.0  # Flat top width (0 = peak)

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "double_slope_cut",
            "angle": self.angle,
            "axis": self.axis,
            "ridge_width": self.ridge_width,
        }


@dataclass
class CurvedSlopeFeature(BaseFeature):
    """Curved top surface."""

    radius: float = 16.0
    direction: str = "front"
    convex: bool = True  # True = bulges out, False = concave

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "curved_slope",
            "radius": self.radius,
            "direction": self.direction,
            "convex": self.convex,
        }


@dataclass
class HoleFeature(BaseFeature):
    """Holes through the brick (Technic, etc.)."""

    positions: List[Tuple[float, float, float]] = field(default_factory=list)
    hole_type: str = "pin"  # pin, axle, bar
    diameter: float = 4.8  # Pin hole diameter
    axis: str = "x"  # Hole axis
    through: bool = True
    depth: float = 8.0  # If not through

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    # Hole type dimensions
    PIN_HOLE_DIAMETER = 4.8
    AXLE_HOLE_SIZE = 4.8  # Cross-shaped
    BAR_HOLE_DIAMETER = 3.18

    def get_geometry_params(self) -> Dict:
        return {
            "type": "holes",
            "positions": self.positions,
            "hole_type": self.hole_type,
            "diameter": self.diameter,
            "axis": self.axis,
            "through": self.through,
            "depth": self.depth,
        }


@dataclass
class AxleHoleFeature(BaseFeature):
    """Cross-shaped axle holes."""

    positions: List[Tuple[float, float, float]] = field(default_factory=list)
    size: float = 4.8  # Cross size
    axis: str = "x"

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "axle_holes",
            "positions": self.positions,
            "size": self.size,
            "axis": self.axis,
        }


@dataclass
class ChamferFeature(BaseFeature):
    """Chamfer edges."""

    edges: str = "all_top"  # all_top, all_bottom, all, specific
    size: float = 0.3

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {"type": "chamfer", "edges": self.edges, "size": self.size}


@dataclass
class FilletFeature(BaseFeature):
    """Fillet (round) edges."""

    edges: str = "all_vertical"
    radius: float = 0.5

    def get_geometry_params(self) -> Dict:
        return {"type": "fillet", "edges": self.edges, "radius": self.radius}


@dataclass
class ArchCutFeature(BaseFeature):
    """Cut an arch opening."""

    width: float = 8.0
    height: float = 6.0
    depth: float = 8.0  # Through the brick
    position: Tuple[float, float] = (0.0, 0.0)  # Bottom center of arch

    operation: FeatureOperation = FeatureOperation.SUBTRACT

    def get_geometry_params(self) -> Dict:
        return {
            "type": "arch_cut",
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "position": self.position,
        }


# ============================================================================
# CUSTOM BRICK BUILDER
# ============================================================================


@dataclass
class CustomBrickSpec:
    """
    Specification for building a custom LEGO brick.

    Combines base shape with features to create any brick type.
    """

    name: str
    description: str = ""

    # Base dimensions (in studs)
    studs_x: int = 1
    studs_y: int = 1
    height_units: float = 1.0  # 1 = brick, 0.333 = plate

    # Base shape override (default: box based on dimensions)
    base_shape: Optional[BaseFeature] = None

    # Features to apply
    features: List[BaseFeature] = field(default_factory=list)

    # Computed dimensions
    @property
    def width_mm(self) -> float:
        return self.studs_x * LEGO.STUD_PITCH

    @property
    def depth_mm(self) -> float:
        return self.studs_y * LEGO.STUD_PITCH

    @property
    def height_mm(self) -> float:
        return self.height_units * LEGO.BRICK_HEIGHT

    def get_base_shape(self) -> BaseFeature:
        """Get the base shape feature."""
        if self.base_shape:
            return self.base_shape
        return BoxFeature(
            name="base", width=self.width_mm, depth=self.depth_mm, height=self.height_mm
        )

    def get_all_features(self) -> List[BaseFeature]:
        """Get all features including base shape."""
        return [self.get_base_shape()] + self.features


class CustomBrickBuilder:
    """
    Builder class for creating custom LEGO bricks.

    Usage:
        brick = (CustomBrickBuilder("my_brick")
            .set_size(2, 4, 1.0)
            .add_studs()
            .add_hollow()
            .add_tubes()
            .add_slope(45, "front")
            .build())
    """

    def __init__(self, name: str, description: str = ""):
        self.spec = CustomBrickSpec(name=name, description=description)

    def set_size(
        self, studs_x: int, studs_y: int, height_units: float = 1.0
    ) -> "CustomBrickBuilder":
        """Set brick dimensions."""
        self.spec.studs_x = studs_x
        self.spec.studs_y = studs_y
        self.spec.height_units = height_units
        return self

    def set_base_cylinder(self, diameter_studs: int = 1) -> "CustomBrickBuilder":
        """Use cylindrical base instead of box."""
        self.spec.studs_x = diameter_studs
        self.spec.studs_y = diameter_studs
        self.spec.base_shape = CylinderFeature(
            name="base_cylinder",
            diameter=diameter_studs * LEGO.STUD_PITCH,
            height=self.spec.height_mm,
            center=Point3D(
                diameter_studs * LEGO.STUD_PITCH / 2, diameter_studs * LEGO.STUD_PITCH / 2, 0
            ),
        )
        return self

    def set_base_cone(self, bottom_studs: int, top_studs: int = 0) -> "CustomBrickBuilder":
        """Use cone base."""
        self.spec.studs_x = bottom_studs
        self.spec.studs_y = bottom_studs
        self.spec.base_shape = ConeFeature(
            name="base_cone",
            bottom_diameter=bottom_studs * LEGO.STUD_PITCH,
            top_diameter=top_studs * LEGO.STUD_PITCH,
            height=self.spec.height_mm,
            center=Point3D(
                bottom_studs * LEGO.STUD_PITCH / 2, bottom_studs * LEGO.STUD_PITCH / 2, 0
            ),
        )
        return self

    def add_studs(self, hollow: bool = False) -> "CustomBrickBuilder":
        """Add standard studs on top."""
        self.spec.features.append(
            StudFeature.from_grid(self.spec.studs_x, self.spec.studs_y, self.spec.height_mm, hollow)
        )
        return self

    def add_jumper_stud(self) -> "CustomBrickBuilder":
        """Add centered jumper stud."""
        self.spec.features.append(
            StudFeature.jumper(self.spec.width_mm, self.spec.depth_mm, self.spec.height_mm)
        )
        return self

    def add_no_studs(self) -> "CustomBrickBuilder":
        """Tile surface - no studs."""
        self.spec.features.append(
            TileSurfaceFeature(
                name="tile_surface", width=self.spec.width_mm, depth=self.spec.depth_mm
            )
        )
        return self

    def add_hollow(self, wall_thickness: float = LEGO.WALL_THICKNESS) -> "CustomBrickBuilder":
        """Hollow out the interior."""
        self.spec.features.append(HollowFeature(name="hollow", wall_thickness=wall_thickness))
        return self

    def add_tubes(self) -> "CustomBrickBuilder":
        """Add bottom tubes for clutch."""
        if self.spec.studs_x > 1 and self.spec.studs_y > 1:
            self.spec.features.append(
                TubeFeature.from_grid(self.spec.studs_x, self.spec.studs_y, self.spec.height_mm)
            )
        return self

    def add_ribs(self) -> "CustomBrickBuilder":
        """Add bottom ribs for 1xN bricks."""
        if self.spec.studs_x == 1 or self.spec.studs_y == 1:
            self.spec.features.append(
                RibFeature.from_grid(self.spec.studs_x, self.spec.studs_y, self.spec.height_mm)
            )
        return self

    def add_auto_bottom(self) -> "CustomBrickBuilder":
        """Automatically add tubes or ribs based on size."""
        if self.spec.studs_x > 1 and self.spec.studs_y > 1:
            return self.add_tubes()
        else:
            return self.add_ribs()

    def add_slope(self, angle: float = 45.0, direction: str = "front") -> "CustomBrickBuilder":
        """Add a slope cut."""
        self.spec.features.append(
            SlopeFeature(name=f"slope_{angle}", angle=angle, direction=direction)
        )
        return self

    def add_double_slope(self, angle: float = 45.0, axis: str = "y") -> "CustomBrickBuilder":
        """Add roof ridge double slope."""
        self.spec.features.append(
            DoubleSlopeFeature(name=f"double_slope_{angle}", angle=angle, axis=axis)
        )
        return self

    def add_curved_slope(
        self, radius: float = 16.0, direction: str = "front"
    ) -> "CustomBrickBuilder":
        """Add curved slope."""
        self.spec.features.append(
            CurvedSlopeFeature(name="curved_slope", radius=radius, direction=direction)
        )
        return self

    def add_side_studs(self, side: str, count: int = 1) -> "CustomBrickBuilder":
        """Add studs on a side (SNOT)."""
        positions = [(4.0 + i * 8.0, 4.8) for i in range(count)]
        self.spec.features.append(
            SideStudFeature(name=f"side_studs_{side}", side=side, positions=positions)
        )
        return self

    def add_clip(self, side: str = "front", orientation: str = "vertical") -> "CustomBrickBuilder":
        """Add a clip."""
        self.spec.features.append(
            ClipFeature(name=f"clip_{side}", side=side, orientation=orientation)
        )
        return self

    def add_bar(self, side: str = "front", orientation: str = "horizontal") -> "CustomBrickBuilder":
        """Add a bar."""
        self.spec.features.append(
            BarFeature(name=f"bar_{side}", side=side, orientation=orientation)
        )
        return self

    def add_pin_holes(self, count: int, axis: str = "x") -> "CustomBrickBuilder":
        """Add Technic pin holes."""
        positions = []
        for i in range(count):
            if axis == "x":
                positions.append((4.0, (i + 0.5) * 8.0, 4.8))
            else:
                positions.append(((i + 0.5) * 8.0, 4.0, 4.8))

        self.spec.features.append(
            HoleFeature(
                name="pin_holes", positions=positions, hole_type="pin", diameter=4.8, axis=axis
            )
        )
        return self

    def add_axle_holes(self, count: int, axis: str = "x") -> "CustomBrickBuilder":
        """Add Technic axle holes."""
        positions = []
        for i in range(count):
            if axis == "x":
                positions.append((4.0, (i + 0.5) * 8.0, 4.8))
            else:
                positions.append(((i + 0.5) * 8.0, 4.0, 4.8))

        self.spec.features.append(
            AxleHoleFeature(name="axle_holes", positions=positions, axis=axis)
        )
        return self

    def add_arch(self, width: float = None, height: float = None) -> "CustomBrickBuilder":
        """Add arch cutout."""
        arch_width = width or (self.spec.depth_mm - 2 * LEGO.WALL_THICKNESS)
        arch_height = height or (self.spec.height_mm - LEGO.TOP_THICKNESS - 2)

        self.spec.features.append(
            ArchCutFeature(
                name="arch", width=arch_width, height=arch_height, depth=self.spec.width_mm
            )
        )
        return self

    def add_chamfer(self, size: float = 0.3, edges: str = "all_top") -> "CustomBrickBuilder":
        """Add edge chamfers."""
        self.spec.features.append(ChamferFeature(name="chamfer", size=size, edges=edges))
        return self

    def add_fillet(self, radius: float = 0.5, edges: str = "all_vertical") -> "CustomBrickBuilder":
        """Add edge fillets."""
        self.spec.features.append(FilletFeature(name="fillet", radius=radius, edges=edges))
        return self

    def add_custom_feature(self, feature: BaseFeature) -> "CustomBrickBuilder":
        """Add any custom feature."""
        self.spec.features.append(feature)
        return self

    def build(self) -> CustomBrickSpec:
        """Build and return the brick specification."""
        return self.spec


# ============================================================================
# PRESET BUILDERS
# ============================================================================


def standard_brick(studs_x: int, studs_y: int, height_units: float = 1.0) -> CustomBrickSpec:
    """Create a standard brick specification."""
    return (
        CustomBrickBuilder(f"brick_{studs_x}x{studs_y}")
        .set_size(studs_x, studs_y, height_units)
        .add_studs()
        .add_hollow()
        .add_auto_bottom()
        .build()
    )


def standard_plate(studs_x: int, studs_y: int) -> CustomBrickSpec:
    """Create a standard plate specification."""
    return (
        CustomBrickBuilder(f"plate_{studs_x}x{studs_y}")
        .set_size(studs_x, studs_y, 1 / 3)
        .add_studs()
        .add_hollow()
        .add_auto_bottom()
        .build()
    )


def standard_tile(studs_x: int, studs_y: int) -> CustomBrickSpec:
    """Create a standard tile specification."""
    return (
        CustomBrickBuilder(f"tile_{studs_x}x{studs_y}")
        .set_size(studs_x, studs_y, 1 / 3)
        .add_no_studs()
        .build()
    )


def slope_brick(studs_x: int, studs_y: int, angle: float = 45.0) -> CustomBrickSpec:
    """Create a slope brick specification."""
    return (
        CustomBrickBuilder(f"slope_{angle}_{studs_x}x{studs_y}")
        .set_size(studs_x, studs_y, 1.0)
        .add_studs()
        .add_hollow()
        .add_auto_bottom()
        .add_slope(angle, "front")
        .build()
    )


def technic_brick(studs_x: int, studs_y: int) -> CustomBrickSpec:
    """Create a Technic brick with pin holes."""
    builder = (
        CustomBrickBuilder(f"technic_{studs_x}x{studs_y}")
        .set_size(studs_x, studs_y, 1.0)
        .add_studs()
        .add_hollow()
    )

    # Add pin holes along the longer side
    hole_count = max(studs_x, studs_y)
    axis = "y" if studs_y > studs_x else "x"
    builder.add_pin_holes(hole_count, axis)

    return builder.build()


def round_brick(diameter_studs: int, height_units: float = 1.0) -> CustomBrickSpec:
    """Create a round brick specification."""
    return (
        CustomBrickBuilder(f"round_{diameter_studs}x{diameter_studs}")
        .set_base_cylinder(diameter_studs)
        .set_size(diameter_studs, diameter_studs, height_units)
        .add_studs(hollow=diameter_studs == 1)
        .add_hollow()
        .build()
    )


def cone(diameter_studs: int, height_units: float = 1.0) -> CustomBrickSpec:
    """Create a cone specification."""
    return (
        CustomBrickBuilder(f"cone_{diameter_studs}x{diameter_studs}")
        .set_base_cone(diameter_studs, 0)
        .set_size(diameter_studs, diameter_studs, height_units)
        .build()
    )
