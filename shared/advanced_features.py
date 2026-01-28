"""
Advanced Brick Features - Complex Geometry Definitions

This module provides advanced features for custom brick building:
- Ball joints and sockets
- Complex clips and connectors
- Curved surfaces and profiles
- Patterns and textures
- Advanced Technic features
- Chamfers and fillets
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any, Literal
from enum import Enum, auto
import math


# ============================================================================
# DIMENSIONS (mm) - LEGO Standard
# ============================================================================


class Dims:
    """Standard LEGO dimensions in mm."""

    # Core dimensions
    STUD_PITCH = 8.0
    STUD_DIAMETER = 4.8
    STUD_HEIGHT = 1.7
    PLATE_HEIGHT = 3.2
    BRICK_HEIGHT = 9.6

    # Wall structure
    WALL_THICKNESS = 1.5
    TOP_THICKNESS = 1.0

    # Bottom structure
    TUBE_OUTER = 6.51
    TUBE_INNER = 4.8
    RIB_THICKNESS = 1.0

    # Technic
    PIN_HOLE = 4.8
    AXLE_CROSS = 4.8
    AXLE_ARM_WIDTH = 1.8
    AXLE_ARM_DEPTH = 0.8

    # Connectors
    BAR_DIAMETER = 3.18
    BAR_CLIP_INNER = 3.2
    CLIP_WIDTH = 4.0

    # Ball joints
    BALL_DIAMETER = 5.9  # Standard towball
    BALL_DIAMETER_SMALL = 5.0
    SOCKET_INNER = 6.0
    SOCKET_OPENING = 4.0

    # Tolerances
    INTERFERENCE_FIT = 0.1
    CLEARANCE_FIT = 0.1
    FDM_TOLERANCE = 0.2
    CNC_TOLERANCE = 0.05


# ============================================================================
# ENUMS - Feature Types
# ============================================================================


class BallType(Enum):
    """Types of ball joints."""

    STANDARD = "standard"  # Normal towball (5.9mm)
    SMALL = "small"  # Small ball (5.0mm)
    TECHNIC = "technic"  # Technic ball
    BIONICLE = "bionicle"  # Bionicle-style ball


class SocketType(Enum):
    """Types of ball sockets."""

    STANDARD = "standard"  # Normal socket
    FRICTION = "friction"  # High-friction socket
    CLICK = "click"  # Click-stop socket
    SWIVEL = "swivel"  # Free-rotating socket


class ClipType(Enum):
    """Types of clips."""

    HORIZONTAL = "horizontal"  # Horizontal O-clip
    VERTICAL = "vertical"  # Vertical O-clip
    THICK = "thick"  # Thick bar clip
    PLATE = "plate"  # Plate-height clip
    MODIFIED = "modified"  # Modified clip (various)


class PatternType(Enum):
    """Types of surface patterns."""

    GRILLE = "grille"  # Grille/vent pattern
    LATTICE = "lattice"  # Lattice pattern
    BRICK = "brick"  # Brick texture (masonry)
    LOG = "log"  # Log texture
    TILE = "tile"  # Tile pattern
    DIAMOND = "diamond"  # Diamond plate
    RIBBED = "ribbed"  # Ribbed surface
    SMOOTH = "smooth"  # Smooth (default)


class EdgeTreatment(Enum):
    """Types of edge treatments."""

    SHARP = "sharp"  # Sharp 90° edge
    CHAMFER = "chamfer"  # 45° chamfer
    FILLET = "fillet"  # Rounded fillet
    ROUND = "round"  # Full round


class CurveProfile(Enum):
    """Types of curve profiles."""

    ARC = "arc"  # Simple arc
    QUARTER = "quarter"  # Quarter circle (macaroni)
    HALF = "half"  # Half circle
    OGEE = "ogee"  # S-curve
    BEZIER = "bezier"  # Bezier curve
    PARABOLIC = "parabolic"  # Parabolic curve


# ============================================================================
# DATA CLASSES - Advanced Features
# ============================================================================


@dataclass
class BallJoint:
    """Ball joint specification."""

    type: BallType = BallType.STANDARD
    position: Tuple[float, float, float] = (0.5, 0.5, 1.0)  # x, y, z in stud units
    direction: str = "up"  # up, down, front, back, left, right
    neck_length: float = 2.0  # mm
    neck_diameter: float = 2.5  # mm

    @property
    def ball_diameter(self) -> float:
        if self.type == BallType.STANDARD:
            return 5.9
        elif self.type == BallType.SMALL:
            return 5.0
        elif self.type == BallType.TECHNIC:
            return 6.0
        else:
            return 5.5


@dataclass
class BallSocket:
    """Ball socket specification."""

    type: SocketType = SocketType.STANDARD
    position: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    direction: str = "front"
    ball_diameter: float = 5.9
    opening_angle: float = 80  # degrees - how wide the opening is
    depth: float = 0  # 0 = calculated from ball size

    @property
    def inner_diameter(self) -> float:
        return self.ball_diameter + Dims.CLEARANCE_FIT

    @property
    def opening_diameter(self) -> float:
        # Calculate opening that allows ball to snap in
        return self.ball_diameter * 0.7


@dataclass
class AdvancedClip:
    """Advanced clip specification."""

    type: ClipType = ClipType.HORIZONTAL
    position: Tuple[float, float, float] = (0.5, 0.0, 0.5)
    face: str = "front"
    bar_diameter: float = Dims.BAR_DIAMETER
    thickness: float = 1.5  # Wall thickness of clip

    # Clip geometry
    opening_angle: float = 90  # degrees
    spring_tabs: bool = True  # Has spring retention tabs

    @property
    def inner_diameter(self) -> float:
        return self.bar_diameter + Dims.CLEARANCE_FIT


@dataclass
class AdvancedBar:
    """Advanced bar/handle specification."""

    position: Tuple[float, float, float] = (0.5, 0.0, 0.5)
    face: str = "front"
    direction: str = "out"  # out, up, down
    length: float = 6.0  # mm
    diameter: float = Dims.BAR_DIAMETER
    end_type: str = "flat"  # flat, round, stud


@dataclass
class TechnicAxleHole:
    """Technic axle hole (cross-shaped) specification."""

    position: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    axis: str = "x"  # x, y, z
    depth: float = 0  # 0 = through hole

    # Axle cross dimensions
    cross_width: float = Dims.AXLE_CROSS
    arm_width: float = Dims.AXLE_ARM_WIDTH
    arm_depth: float = Dims.AXLE_ARM_DEPTH

    # Features
    has_center_slot: bool = False  # For axle with stop


@dataclass
class TechnicPinHole:
    """Technic pin hole specification."""

    position: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    axis: str = "x"
    depth: float = 0  # 0 = through hole

    diameter: float = Dims.PIN_HOLE

    # Pin retention
    friction_ridges: bool = True
    ridge_count: int = 4
    ridge_height: float = 0.1


@dataclass
class SurfacePattern:
    """Surface pattern/texture specification."""

    type: PatternType = PatternType.SMOOTH
    face: str = "front"  # front, back, left, right, top, bottom, all

    # Pattern parameters (varies by type)
    spacing: float = 2.0  # mm between elements
    depth: float = 0.5  # mm depth of pattern
    element_size: float = 1.0  # mm size of pattern elements
    angle: float = 0  # degrees rotation of pattern


@dataclass
class Chamfer:
    """Edge chamfer specification."""

    edges: str = "all"  # all, top, bottom, vertical, or specific edge IDs
    size: float = 0.3  # mm chamfer size
    angle: float = 45  # degrees


@dataclass
class Fillet:
    """Edge fillet (round) specification."""

    edges: str = "all"  # all, top, bottom, vertical, or specific
    radius: float = 0.5  # mm fillet radius


@dataclass
class CurvedSection:
    """Curved section specification for macaroni bricks etc."""

    profile: CurveProfile = CurveProfile.QUARTER

    # Curve geometry
    inner_radius: float = 1.0  # studs
    outer_radius: float = 2.0  # studs
    angle: float = 90  # degrees of arc

    # Section shape
    section_width: float = 1.0  # studs (wall width)
    section_height: float = 1.0  # plates

    # Direction
    plane: str = "xy"  # xy, xz, yz
    start_angle: float = 0  # starting angle in plane
    direction: str = "ccw"  # ccw or cw


@dataclass
class HollowStud:
    """Hollow stud specification (for bar insertion)."""

    position: Tuple[float, float] = (0.5, 0.5)
    outer_diameter: float = Dims.STUD_DIAMETER
    inner_diameter: float = Dims.BAR_DIAMETER + Dims.CLEARANCE_FIT
    height: float = Dims.STUD_HEIGHT
    wall_thickness: float = 0.8


@dataclass
class AntiStud:
    """Anti-stud (stud receptacle) specification."""

    position: Tuple[float, float] = (0.5, 0.5)
    diameter: float = Dims.STUD_DIAMETER + Dims.INTERFERENCE_FIT
    depth: float = Dims.STUD_HEIGHT + 0.1
    face: str = "bottom"  # bottom, top (for inverted), or side face


@dataclass
class ClickHinge:
    """Click hinge specification with positions."""

    type: str = "finger"  # finger, fork, clip
    position: Tuple[float, float, float] = (1.0, 0.0, 0.5)
    face: str = "front"

    # Hinge geometry
    finger_width: float = 3.0
    finger_height: float = 3.0
    finger_spacing: float = 2.0
    pin_diameter: float = 1.8

    # Click mechanism
    click_positions: int = 0  # 0 = free rotation, >0 = number of stops


@dataclass
class TechnicConnector:
    """Advanced Technic connector specification."""

    type: str = "perpendicular"  # perpendicular, inline, cv, universal
    position: Tuple[float, float, float] = (0.5, 0.5, 0.5)

    # First axis
    axis1: str = "x"
    hole1_type: str = "axle"  # axle, pin, pin_axle

    # Second axis
    axis2: str = "z"
    hole2_type: str = "axle"

    # Angle between axes
    angle: float = 90  # degrees


@dataclass
class WedgeCut:
    """Wedge-shaped cut from brick corner."""

    corner: str = "front_left"  # which corner to cut
    cut_x: int = 1  # studs to cut in x
    cut_y: int = 1  # studs to cut in y
    angle: float = 45  # cut angle


# ============================================================================
# ADVANCED CUSTOM BRICK DEFINITION
# ============================================================================


@dataclass
class AdvancedBrickDefinition:
    """
    Extended brick definition with all advanced features.

    This is a superset of CustomBrickDefinition with additional
    complex features for expert brick building.
    """

    # Base definition
    name: str
    width_studs: int
    depth_studs: int
    height_plates: int

    # Standard features (from CustomBrickDefinition)
    is_hollow: bool = True
    is_round: bool = False
    wall_thickness: float = Dims.WALL_THICKNESS
    top_thickness: float = Dims.TOP_THICKNESS

    # Stud configuration
    stud_type: str = "solid"  # solid, hollow, none
    stud_positions: Optional[List[Tuple[int, int]]] = None  # None = all

    # Bottom structure
    has_tubes: bool = True
    has_ribs: bool = False  # For 1xN bricks
    bottom_type: str = "standard"  # standard, anti_stud, solid, open

    # ============ Advanced Features ============

    # Ball joints
    ball_joints: List[BallJoint] = field(default_factory=list)
    ball_sockets: List[BallSocket] = field(default_factory=list)

    # Clips and bars
    clips: List[AdvancedClip] = field(default_factory=list)
    bars: List[AdvancedBar] = field(default_factory=list)

    # Technic features
    axle_holes: List[TechnicAxleHole] = field(default_factory=list)
    pin_holes: List[TechnicPinHole] = field(default_factory=list)
    technic_connectors: List[TechnicConnector] = field(default_factory=list)

    # Surface features
    patterns: List[SurfacePattern] = field(default_factory=list)
    hollow_studs: List[HollowStud] = field(default_factory=list)
    anti_studs: List[AntiStud] = field(default_factory=list)

    # Edge treatments
    chamfers: List[Chamfer] = field(default_factory=list)
    fillets: List[Fillet] = field(default_factory=list)

    # Curved elements
    curves: List[CurvedSection] = field(default_factory=list)

    # Hinges
    hinges: List[ClickHinge] = field(default_factory=list)

    # Wedges
    wedge_cuts: List[WedgeCut] = field(default_factory=list)

    # Manufacturing
    tolerance: float = Dims.CNC_TOLERANCE
    target_process: str = "cnc"  # cnc, fdm, sla
    notes: str = ""

    def dimensions_mm(self) -> Tuple[float, float, float]:
        """Get dimensions in mm."""
        return (
            self.width_studs * Dims.STUD_PITCH,
            self.depth_studs * Dims.STUD_PITCH,
            self.height_plates * Dims.PLATE_HEIGHT,
        )

    def total_features(self) -> int:
        """Count total number of features."""
        return (
            len(self.ball_joints)
            + len(self.ball_sockets)
            + len(self.clips)
            + len(self.bars)
            + len(self.axle_holes)
            + len(self.pin_holes)
            + len(self.technic_connectors)
            + len(self.patterns)
            + len(self.hollow_studs)
            + len(self.anti_studs)
            + len(self.chamfers)
            + len(self.fillets)
            + len(self.curves)
            + len(self.hinges)
            + len(self.wedge_cuts)
        )


# ============================================================================
# ADVANCED BUILDER CLASS
# ============================================================================


class AdvancedBrickBuilder:
    """
    Advanced fluent builder for complex LEGO brick designs.

    Example:
        brick = (AdvancedBrickBuilder()
            .base(2, 2, 3)
            .studs()
            .hollow()
            .add_ball_joint("up", position=(1, 1, 1))
            .add_socket("front", position=(0.5, 0, 0.5))
            .add_clip("right", ClipType.HORIZONTAL)
            .pattern("front", PatternType.GRILLE)
            .chamfer_all(0.3)
            .build("ball_socket_brick"))
    """

    def __init__(self):
        self._reset()

    def _reset(self):
        """Reset builder state."""
        self._width = 2
        self._depth = 2
        self._height = 3
        self._hollow = True
        self._round = False
        self._wall = Dims.WALL_THICKNESS
        self._top = Dims.TOP_THICKNESS
        self._stud_type = "solid"
        self._stud_positions = None
        self._tubes = True
        self._ribs = False
        self._bottom = "standard"

        # Advanced features
        self._ball_joints: List[BallJoint] = []
        self._sockets: List[BallSocket] = []
        self._clips: List[AdvancedClip] = []
        self._bars: List[AdvancedBar] = []
        self._axle_holes: List[TechnicAxleHole] = []
        self._pin_holes: List[TechnicPinHole] = []
        self._connectors: List[TechnicConnector] = []
        self._patterns: List[SurfacePattern] = []
        self._hollow_studs: List[HollowStud] = []
        self._anti_studs: List[AntiStud] = []
        self._chamfers: List[Chamfer] = []
        self._fillets: List[Fillet] = []
        self._curves: List[CurvedSection] = []
        self._hinges: List[ClickHinge] = []
        self._wedges: List[WedgeCut] = []

        self._tolerance = Dims.CNC_TOLERANCE
        self._process = "cnc"
        self._notes = ""

    # ============ Base Configuration ============

    def base(self, width: int, depth: int, height_plates: int = 3) -> "AdvancedBrickBuilder":
        """Set base dimensions."""
        self._width = max(1, min(width, 48))
        self._depth = max(1, min(depth, 48))
        self._height = max(1, min(height_plates, 36))
        return self

    def hollow(self, is_hollow: bool = True) -> "AdvancedBrickBuilder":
        """Set hollow state."""
        self._hollow = is_hollow
        return self

    def solid(self) -> "AdvancedBrickBuilder":
        """Make brick solid."""
        self._hollow = False
        return self

    def round(self, is_round: bool = True) -> "AdvancedBrickBuilder":
        """Make brick cylindrical."""
        self._round = is_round
        return self

    def wall_thickness(self, thickness: float) -> "AdvancedBrickBuilder":
        """Set wall thickness."""
        self._wall = max(0.5, min(thickness, 4.0))
        return self

    # ============ Studs ============

    def studs(self, stud_type: str = "solid") -> "AdvancedBrickBuilder":
        """Add studs (all positions)."""
        self._stud_type = stud_type
        self._stud_positions = None
        return self

    def studs_at(self, positions: List[Tuple[int, int]]) -> "AdvancedBrickBuilder":
        """Add studs at specific positions."""
        self._stud_positions = positions
        return self

    def no_studs(self) -> "AdvancedBrickBuilder":
        """Remove studs (tile)."""
        self._stud_type = "none"
        return self

    def hollow_studs(self) -> "AdvancedBrickBuilder":
        """Make all studs hollow."""
        self._stud_type = "hollow"
        return self

    # ============ Bottom Structure ============

    def tubes(self, has_tubes: bool = True) -> "AdvancedBrickBuilder":
        """Add bottom tubes."""
        self._tubes = has_tubes
        self._ribs = not has_tubes
        return self

    def ribs(self, has_ribs: bool = True) -> "AdvancedBrickBuilder":
        """Add center ribs (for 1xN)."""
        self._ribs = has_ribs
        self._tubes = not has_ribs
        return self

    def anti_stud_bottom(self) -> "AdvancedBrickBuilder":
        """Add anti-stud pattern on bottom."""
        self._bottom = "anti_stud"
        return self

    # ============ Ball Joints ============

    def add_ball(
        self,
        direction: str = "up",
        position: Tuple[float, float, float] = None,
        ball_type: BallType = BallType.STANDARD,
    ) -> "AdvancedBrickBuilder":
        """Add a ball joint."""
        if position is None:
            position = (self._width / 2, self._depth / 2, 1.0)

        self._ball_joints.append(BallJoint(type=ball_type, position=position, direction=direction))
        return self

    def add_socket(
        self,
        direction: str = "front",
        position: Tuple[float, float, float] = None,
        socket_type: SocketType = SocketType.STANDARD,
    ) -> "AdvancedBrickBuilder":
        """Add a ball socket."""
        if position is None:
            if direction == "front":
                position = (self._width / 2, 0, 0.5)
            elif direction == "back":
                position = (self._width / 2, self._depth, 0.5)
            elif direction == "left":
                position = (0, self._depth / 2, 0.5)
            elif direction == "right":
                position = (self._width, self._depth / 2, 0.5)
            else:
                position = (self._width / 2, self._depth / 2, 0.5)

        self._sockets.append(BallSocket(type=socket_type, position=position, direction=direction))
        return self

    # ============ Clips and Bars ============

    def add_clip(
        self,
        face: str = "front",
        clip_type: ClipType = ClipType.HORIZONTAL,
        position: Tuple[float, float, float] = None,
    ) -> "AdvancedBrickBuilder":
        """Add a clip."""
        if position is None:
            position = (self._width / 2, 0, 0.5) if face == "front" else (0.5, 0.0, 0.5)

        self._clips.append(AdvancedClip(type=clip_type, position=position, face=face))
        return self

    def add_bar(
        self, face: str = "front", length: float = 6.0, position: Tuple[float, float, float] = None
    ) -> "AdvancedBrickBuilder":
        """Add a bar/handle."""
        if position is None:
            position = (self._width / 2, 0, 0.5)

        self._bars.append(AdvancedBar(position=position, face=face, length=length))
        return self

    # ============ Technic Holes ============

    def add_axle_hole(
        self, axis: str = "x", position: Tuple[float, float, float] = None
    ) -> "AdvancedBrickBuilder":
        """Add an axle hole."""
        if position is None:
            position = (0.5, 0.5, 0.5)

        self._axle_holes.append(TechnicAxleHole(position=position, axis=axis))
        return self

    def add_pin_hole(
        self, axis: str = "x", position: Tuple[float, float, float] = None, friction: bool = True
    ) -> "AdvancedBrickBuilder":
        """Add a pin hole."""
        if position is None:
            position = (0.5, 0.5, 0.5)

        self._pin_holes.append(
            TechnicPinHole(position=position, axis=axis, friction_ridges=friction)
        )
        return self

    def add_technic_holes_row(
        self, axis: str = "x", hole_type: str = "pin"
    ) -> "AdvancedBrickBuilder":
        """Add a row of Technic holes."""
        if axis == "x":
            for y in range(self._depth):
                pos = (0.5, y + 0.5, 0.5)
                if hole_type == "pin":
                    self._pin_holes.append(TechnicPinHole(position=pos, axis=axis))
                else:
                    self._axle_holes.append(TechnicAxleHole(position=pos, axis=axis))
        elif axis == "y":
            for x in range(self._width):
                pos = (x + 0.5, 0.5, 0.5)
                if hole_type == "pin":
                    self._pin_holes.append(TechnicPinHole(position=pos, axis=axis))
                else:
                    self._axle_holes.append(TechnicAxleHole(position=pos, axis=axis))
        return self

    # ============ Surface Patterns ============

    def pattern(
        self, face: str = "front", pattern_type: PatternType = PatternType.GRILLE
    ) -> "AdvancedBrickBuilder":
        """Add a surface pattern."""
        self._patterns.append(SurfacePattern(type=pattern_type, face=face))
        return self

    def grille(self, face: str = "front") -> "AdvancedBrickBuilder":
        """Add grille pattern."""
        return self.pattern(face, PatternType.GRILLE)

    def lattice(self, face: str = "front") -> "AdvancedBrickBuilder":
        """Add lattice pattern."""
        return self.pattern(face, PatternType.LATTICE)

    def masonry(self, face: str = "front") -> "AdvancedBrickBuilder":
        """Add masonry/brick texture."""
        return self.pattern(face, PatternType.BRICK)

    # ============ Edge Treatments ============

    def chamfer(self, edges: str = "all", size: float = 0.3) -> "AdvancedBrickBuilder":
        """Add chamfers to edges."""
        self._chamfers.append(Chamfer(edges=edges, size=size))
        return self

    def chamfer_all(self, size: float = 0.3) -> "AdvancedBrickBuilder":
        """Chamfer all edges."""
        return self.chamfer("all", size)

    def chamfer_top(self, size: float = 0.3) -> "AdvancedBrickBuilder":
        """Chamfer top edges only."""
        return self.chamfer("top", size)

    def fillet(self, edges: str = "all", radius: float = 0.5) -> "AdvancedBrickBuilder":
        """Add fillets to edges."""
        self._fillets.append(Fillet(edges=edges, radius=radius))
        return self

    def fillet_all(self, radius: float = 0.5) -> "AdvancedBrickBuilder":
        """Fillet all edges."""
        return self.fillet("all", radius)

    # ============ Curved Sections ============

    def add_curve(
        self,
        profile: CurveProfile = CurveProfile.QUARTER,
        inner_radius: float = 1.0,
        outer_radius: float = 2.0,
        angle: float = 90,
    ) -> "AdvancedBrickBuilder":
        """Add a curved section (for macaroni etc)."""
        self._curves.append(
            CurvedSection(
                profile=profile, inner_radius=inner_radius, outer_radius=outer_radius, angle=angle
            )
        )
        return self

    def macaroni(self, inner_radius: float = 1.0, angle: float = 90) -> "AdvancedBrickBuilder":
        """Make a macaroni brick (quarter circle)."""
        outer_radius = inner_radius + self._width
        return self.add_curve(CurveProfile.QUARTER, inner_radius, outer_radius, angle)

    # ============ Hinges ============

    def add_hinge_fingers(
        self, face: str = "front", position: Tuple[float, float, float] = None
    ) -> "AdvancedBrickBuilder":
        """Add hinge fingers."""
        if position is None:
            position = (self._width / 2, 0, 0.5)

        self._hinges.append(ClickHinge(type="finger", position=position, face=face))
        return self

    def add_hinge_fork(
        self, face: str = "front", position: Tuple[float, float, float] = None
    ) -> "AdvancedBrickBuilder":
        """Add hinge fork."""
        if position is None:
            position = (self._width / 2, 0, 0.5)

        self._hinges.append(ClickHinge(type="fork", position=position, face=face))
        return self

    # ============ Wedge Cuts ============

    def wedge_cut(
        self, corner: str = "front_left", cut_x: int = 1, cut_y: int = 1
    ) -> "AdvancedBrickBuilder":
        """Add a wedge cut to a corner."""
        self._wedges.append(WedgeCut(corner=corner, cut_x=cut_x, cut_y=cut_y))
        return self

    # ============ Manufacturing ============

    def for_cnc(self) -> "AdvancedBrickBuilder":
        """Optimize for CNC machining."""
        self._process = "cnc"
        self._tolerance = Dims.CNC_TOLERANCE
        return self

    def for_fdm(self) -> "AdvancedBrickBuilder":
        """Optimize for FDM 3D printing."""
        self._process = "fdm"
        self._tolerance = Dims.FDM_TOLERANCE
        return self

    def for_sla(self) -> "AdvancedBrickBuilder":
        """Optimize for SLA/resin printing."""
        self._process = "sla"
        self._tolerance = Dims.CNC_TOLERANCE  # SLA is very precise
        return self

    def notes(self, text: str) -> "AdvancedBrickBuilder":
        """Add manufacturing notes."""
        self._notes = text
        return self

    # ============ Build ============

    def build(self, name: str = "advanced_brick") -> AdvancedBrickDefinition:
        """Build the advanced brick definition."""
        return AdvancedBrickDefinition(
            name=name,
            width_studs=self._width,
            depth_studs=self._depth,
            height_plates=self._height,
            is_hollow=self._hollow,
            is_round=self._round,
            wall_thickness=self._wall,
            top_thickness=self._top,
            stud_type=self._stud_type,
            stud_positions=self._stud_positions,
            has_tubes=self._tubes,
            has_ribs=self._ribs,
            bottom_type=self._bottom,
            ball_joints=self._ball_joints.copy(),
            ball_sockets=self._sockets.copy(),
            clips=self._clips.copy(),
            bars=self._bars.copy(),
            axle_holes=self._axle_holes.copy(),
            pin_holes=self._pin_holes.copy(),
            technic_connectors=self._connectors.copy(),
            patterns=self._patterns.copy(),
            hollow_studs=self._hollow_studs.copy(),
            anti_studs=self._anti_studs.copy(),
            chamfers=self._chamfers.copy(),
            fillets=self._fillets.copy(),
            curves=self._curves.copy(),
            hinges=self._hinges.copy(),
            wedge_cuts=self._wedges.copy(),
            tolerance=self._tolerance,
            target_process=self._process,
            notes=self._notes,
        )

    def reset(self) -> "AdvancedBrickBuilder":
        """Reset builder to defaults."""
        self._reset()
        return self


# ============================================================================
# PRESET ADVANCED BUILDERS
# ============================================================================


def ball_joint_brick(width: int = 1, depth: int = 1, direction: str = "up") -> AdvancedBrickBuilder:
    """Create a brick with a ball joint."""
    return AdvancedBrickBuilder().base(width, depth, 3).studs().hollow().add_ball(direction)


def socket_brick(width: int = 1, depth: int = 2, direction: str = "front") -> AdvancedBrickBuilder:
    """Create a brick with a ball socket."""
    return AdvancedBrickBuilder().base(width, depth, 3).studs().hollow().add_socket(direction)


def grille_tile(width: int = 1, depth: int = 2) -> AdvancedBrickBuilder:
    """Create a grille tile."""
    return AdvancedBrickBuilder().base(width, depth, 1).no_studs().hollow().grille("top")


def technic_beam(length: int = 5) -> AdvancedBrickBuilder:
    """Create a Technic beam."""
    return (
        AdvancedBrickBuilder()
        .base(1, length, 2)
        .no_studs()
        .hollow()
        .add_technic_holes_row("z", "pin")
    )


def hinge_base_brick(width: int = 1, depth: int = 2) -> AdvancedBrickBuilder:
    """Create a hinge base brick."""
    return AdvancedBrickBuilder().base(width, depth, 3).studs().hollow().add_hinge_fingers("front")


def clip_brick(
    width: int = 1, depth: int = 1, clip_type: ClipType = ClipType.HORIZONTAL
) -> AdvancedBrickBuilder:
    """Create a brick with a clip."""
    return (
        AdvancedBrickBuilder().base(width, depth, 3).studs().hollow().add_clip("front", clip_type)
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Complex ball-and-socket connector
    connector = (
        AdvancedBrickBuilder()
        .base(2, 2, 3)
        .studs()
        .hollow()
        .tubes()
        .add_ball("up", position=(1.0, 1.0, 1.0))
        .add_socket("front", position=(1.0, 0, 0.5))
        .add_socket("right", position=(2.0, 1.0, 0.5))
        .chamfer_all(0.3)
        .for_cnc()
        .notes("Complex connector with ball joint and two sockets")
        .build("ball_dual_socket_connector")
    )

    print(f"Created: {connector.name}")
    print(
        f"Dimensions: {connector.width_studs}x{connector.depth_studs}x{connector.height_plates} plates"
    )
    print(f"Total features: {connector.total_features()}")
    print(f"Ball joints: {len(connector.ball_joints)}")
    print(f"Sockets: {len(connector.ball_sockets)}")
    print(f"Target process: {connector.target_process}")
