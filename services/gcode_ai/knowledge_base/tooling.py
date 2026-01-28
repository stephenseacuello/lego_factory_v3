"""
Tool Catalog for G-code AI

Contains tool specifications, capabilities, and recommendations
for different machining operations.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Types of cutting tools."""
    END_MILL = "end_mill"
    BALL_END_MILL = "ball_end_mill"
    FACE_MILL = "face_mill"
    DRILL = "drill"
    SPOT_DRILL = "spot_drill"
    CENTER_DRILL = "center_drill"
    REAMER = "reamer"
    TAP = "tap"
    BORING_BAR = "boring_bar"
    CHAMFER_MILL = "chamfer_mill"
    THREAD_MILL = "thread_mill"
    ENGRAVING_BIT = "engraving_bit"
    V_BIT = "v_bit"
    SLOT_DRILL = "slot_drill"
    ROUGHING_END_MILL = "roughing_end_mill"


class ToolMaterial(Enum):
    """Tool material types."""
    HSS = "hss"              # High Speed Steel
    COBALT = "cobalt"        # Cobalt HSS
    CARBIDE = "carbide"      # Solid Carbide
    CERMET = "cermet"        # Ceramic-Metal
    CERAMIC = "ceramic"      # Ceramic
    CBN = "cbn"              # Cubic Boron Nitride
    PCD = "pcd"              # Polycrystalline Diamond


class ToolCoating(Enum):
    """Tool coating types."""
    UNCOATED = "uncoated"
    TIN = "tin"              # Titanium Nitride
    TICN = "ticn"            # Titanium Carbo-Nitride
    TIALN = "tialn"          # Titanium Aluminum Nitride
    ALTIN = "altin"          # Aluminum Titanium Nitride
    ALCRN = "alcrn"          # Aluminum Chrome Nitride
    ZRN = "zrn"              # Zirconium Nitride
    DLC = "dlc"              # Diamond-Like Carbon
    DIAMOND = "diamond"      # CVD Diamond


@dataclass
class ToolGeometry:
    """Tool geometry specifications."""
    diameter: float              # Tool diameter (inches)
    flute_length: float         # Cutting length (inches)
    overall_length: float       # Total length (inches)
    shank_diameter: float       # Shank diameter (inches)
    number_of_flutes: int       # Number of cutting flutes
    helix_angle: float = 30.0   # Helix angle (degrees)
    corner_radius: float = 0.0  # Corner radius (inches)
    tip_angle: float = 0.0      # Tip angle for drills (degrees)


@dataclass
class ToolCapabilities:
    """What a tool can do."""
    can_plunge: bool = False        # Can plunge cut
    can_ramp: bool = True           # Can ramp into material
    can_slot: bool = False          # Can full-slot
    can_interpolate: bool = True    # Can circular interpolate
    max_ramp_angle: float = 3.0     # Maximum ramp angle (degrees)
    max_helix_angle: float = 5.0    # Maximum helix entry angle
    suitable_for_finishing: bool = True
    suitable_for_roughing: bool = True


@dataclass
class ToolLimits:
    """Operating limits for the tool."""
    max_rpm: int = 24000
    min_rpm: int = 1000
    max_feed_ipm: float = 100.0
    max_doc: float = 0.5            # Max depth of cut (factor of diameter)
    max_woc: float = 1.0            # Max width of cut (factor of diameter)
    recommended_sfm_aluminum: float = 800
    recommended_sfm_steel: float = 100
    recommended_sfm_stainless: float = 50


@dataclass
class Tool:
    """Complete tool definition."""
    tool_number: int
    name: str
    tool_type: ToolType
    material: ToolMaterial
    coating: ToolCoating
    geometry: ToolGeometry
    capabilities: ToolCapabilities = field(default_factory=ToolCapabilities)
    limits: ToolLimits = field(default_factory=ToolLimits)
    description: str = ""
    manufacturer: str = ""
    part_number: str = ""

    # Wear tracking
    total_runtime_minutes: float = 0
    estimated_life_minutes: float = 180  # 3 hours typical

    @property
    def remaining_life_percent(self) -> float:
        """Get remaining tool life percentage."""
        if self.estimated_life_minutes <= 0:
            return 0
        remaining = max(0, self.estimated_life_minutes - self.total_runtime_minutes)
        return (remaining / self.estimated_life_minutes) * 100

    @property
    def diameter_mm(self) -> float:
        """Get diameter in mm."""
        return self.geometry.diameter * 25.4


class ToolCatalog:
    """
    Catalog of available cutting tools with specifications
    and recommendations.
    """

    def __init__(self):
        """Initialize tool catalog."""
        self._tools: Dict[int, Tool] = {}
        self._load_default_tools()

    def _load_default_tools(self):
        """Load default tool library."""
        # T1: 1/4" 2-flute carbide end mill (general purpose)
        self._tools[1] = Tool(
            tool_number=1,
            name="1/4\" Carbide End Mill",
            tool_type=ToolType.END_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIALN,
            geometry=ToolGeometry(
                diameter=0.250,
                flute_length=0.750,
                overall_length=2.500,
                shank_diameter=0.250,
                number_of_flutes=2,
                helix_angle=30.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=False,
                can_ramp=True,
                can_slot=False,
                max_ramp_angle=3.0,
            ),
            limits=ToolLimits(
                max_rpm=18000,
                recommended_sfm_aluminum=800,
                recommended_sfm_steel=100,
            ),
            description="General purpose 2-flute for aluminum and soft materials",
            manufacturer="Harvey Tool",
        )

        # T2: 1/4" 4-flute carbide end mill (steel)
        self._tools[2] = Tool(
            tool_number=2,
            name="1/4\" 4-Flute Carbide End Mill",
            tool_type=ToolType.END_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.ALTIN,
            geometry=ToolGeometry(
                diameter=0.250,
                flute_length=0.750,
                overall_length=2.500,
                shank_diameter=0.250,
                number_of_flutes=4,
                helix_angle=35.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=False,
                can_ramp=True,
                can_slot=False,
                max_ramp_angle=2.0,
            ),
            limits=ToolLimits(
                max_rpm=15000,
                recommended_sfm_aluminum=600,
                recommended_sfm_steel=150,
            ),
            description="4-flute for steel and harder materials",
            manufacturer="Harvey Tool",
        )

        # T3: 1/8" 2-flute end mill (detail work)
        self._tools[3] = Tool(
            tool_number=3,
            name="1/8\" Carbide End Mill",
            tool_type=ToolType.END_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIALN,
            geometry=ToolGeometry(
                diameter=0.125,
                flute_length=0.375,
                overall_length=1.500,
                shank_diameter=0.125,
                number_of_flutes=2,
                helix_angle=30.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=False,
                can_ramp=True,
                can_slot=True,  # Smaller tools can slot
                max_ramp_angle=3.0,
            ),
            limits=ToolLimits(
                max_rpm=24000,
                recommended_sfm_aluminum=600,
                recommended_sfm_steel=80,
            ),
            description="Detail end mill for fine features",
            manufacturer="Harvey Tool",
        )

        # T4: 1/4" ball end mill
        self._tools[4] = Tool(
            tool_number=4,
            name="1/4\" Ball End Mill",
            tool_type=ToolType.BALL_END_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIALN,
            geometry=ToolGeometry(
                diameter=0.250,
                flute_length=0.750,
                overall_length=2.500,
                shank_diameter=0.250,
                number_of_flutes=2,
                helix_angle=30.0,
                corner_radius=0.125,  # Ball radius
            ),
            capabilities=ToolCapabilities(
                can_plunge=True,  # Ball end can plunge
                can_ramp=True,
                can_slot=False,
                max_ramp_angle=90.0,  # Can plunge
            ),
            limits=ToolLimits(
                max_rpm=18000,
                recommended_sfm_aluminum=700,
                recommended_sfm_steel=90,
            ),
            description="Ball end for 3D contours and fillets",
            manufacturer="Harvey Tool",
        )

        # T5: 3/8" roughing end mill
        self._tools[5] = Tool(
            tool_number=5,
            name="3/8\" Roughing End Mill",
            tool_type=ToolType.ROUGHING_END_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIALN,
            geometry=ToolGeometry(
                diameter=0.375,
                flute_length=1.000,
                overall_length=3.000,
                shank_diameter=0.375,
                number_of_flutes=4,
                helix_angle=35.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=False,
                can_ramp=True,
                can_slot=False,
                max_ramp_angle=2.0,
                suitable_for_finishing=False,
                suitable_for_roughing=True,
            ),
            limits=ToolLimits(
                max_rpm=12000,
                max_doc=0.75,
                max_woc=0.50,
                recommended_sfm_aluminum=700,
                recommended_sfm_steel=80,
            ),
            description="Roughing cutter for heavy material removal",
            manufacturer="Niagara Cutter",
        )

        # T6: 1/4" spot drill
        self._tools[6] = Tool(
            tool_number=6,
            name="1/4\" 90° Spot Drill",
            tool_type=ToolType.SPOT_DRILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIN,
            geometry=ToolGeometry(
                diameter=0.250,
                flute_length=0.250,
                overall_length=2.000,
                shank_diameter=0.250,
                number_of_flutes=2,
                tip_angle=90.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=True,
                can_ramp=False,
                can_slot=False,
            ),
            limits=ToolLimits(
                max_rpm=10000,
                recommended_sfm_aluminum=300,
                recommended_sfm_steel=60,
            ),
            description="Spot drill for hole starts and chamfers",
            manufacturer="Guhring",
        )

        # T7-T12: Standard drill sizes
        drill_sizes = [
            (7, 0.125, "#30 Drill", "Letter/Number drill for 6-32 tap"),
            (8, 0.1562, "5/32\" Drill", "Clearance for #6 screw"),
            (9, 0.1875, "3/16\" Drill", "General purpose drill"),
            (10, 0.250, "1/4\" Drill", "General purpose drill"),
            (11, 0.3125, "5/16\" Drill", "Clearance for 1/4\" screw"),
            (12, 0.375, "3/8\" Drill", "General purpose drill"),
        ]

        for t_num, dia, name, desc in drill_sizes:
            self._tools[t_num] = Tool(
                tool_number=t_num,
                name=name,
                tool_type=ToolType.DRILL,
                material=ToolMaterial.CARBIDE,
                coating=ToolCoating.TIN,
                geometry=ToolGeometry(
                    diameter=dia,
                    flute_length=dia * 4,
                    overall_length=dia * 8,
                    shank_diameter=dia,
                    number_of_flutes=2,
                    tip_angle=118.0,
                ),
                capabilities=ToolCapabilities(
                    can_plunge=True,
                    can_ramp=False,
                    can_slot=False,
                ),
                limits=ToolLimits(
                    max_rpm=int(8000 / dia),  # Smaller = faster
                    recommended_sfm_aluminum=400,
                    recommended_sfm_steel=80,
                ),
                description=desc,
                manufacturer="OSG",
            )

        # T13: V-bit for engraving
        self._tools[13] = Tool(
            tool_number=13,
            name="60° V-Bit",
            tool_type=ToolType.V_BIT,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.UNCOATED,
            geometry=ToolGeometry(
                diameter=0.250,
                flute_length=0.500,
                overall_length=2.000,
                shank_diameter=0.250,
                number_of_flutes=2,
                tip_angle=60.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=True,
                can_ramp=True,
                can_slot=False,
            ),
            limits=ToolLimits(
                max_rpm=20000,
                max_doc=0.1,
                recommended_sfm_aluminum=500,
                recommended_sfm_steel=60,
            ),
            description="V-bit for engraving and chamfering",
            manufacturer="Amana Tool",
        )

        # T14: Chamfer mill
        self._tools[14] = Tool(
            tool_number=14,
            name="1/4\" 45° Chamfer Mill",
            tool_type=ToolType.CHAMFER_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIALN,
            geometry=ToolGeometry(
                diameter=0.250,
                flute_length=0.375,
                overall_length=2.000,
                shank_diameter=0.250,
                number_of_flutes=4,
                tip_angle=45.0,
            ),
            capabilities=ToolCapabilities(
                can_plunge=True,
                can_ramp=True,
                can_slot=False,
            ),
            limits=ToolLimits(
                max_rpm=15000,
                recommended_sfm_aluminum=600,
                recommended_sfm_steel=100,
            ),
            description="Chamfer mill for edge breaks",
            manufacturer="Harvey Tool",
        )

        # T15: Thread mill
        self._tools[15] = Tool(
            tool_number=15,
            name="1/4-20 Thread Mill",
            tool_type=ToolType.THREAD_MILL,
            material=ToolMaterial.CARBIDE,
            coating=ToolCoating.TIALN,
            geometry=ToolGeometry(
                diameter=0.200,
                flute_length=0.400,
                overall_length=2.000,
                shank_diameter=0.250,
                number_of_flutes=3,
            ),
            capabilities=ToolCapabilities(
                can_plunge=False,
                can_ramp=True,
                can_slot=False,
                can_interpolate=True,
            ),
            limits=ToolLimits(
                max_rpm=8000,
                recommended_sfm_aluminum=200,
                recommended_sfm_steel=40,
            ),
            description="Single-point thread mill for 1/4-20 threads",
            manufacturer="Scientific Cutting Tools",
        )

        logger.info(f"Loaded {len(self._tools)} tools into catalog")

    def get_tool(self, tool_number: int) -> Optional[Tool]:
        """Get tool by number."""
        return self._tools.get(tool_number)

    def get_tools_by_type(self, tool_type: ToolType) -> List[Tool]:
        """Get all tools of a specific type."""
        return [t for t in self._tools.values() if t.tool_type == tool_type]

    def get_all_tools(self) -> List[Tool]:
        """Get all tools."""
        return list(self._tools.values())

    def add_tool(self, tool: Tool):
        """Add a tool to the catalog."""
        self._tools[tool.tool_number] = tool
        logger.info(f"Added tool T{tool.tool_number}: {tool.name}")

    def remove_tool(self, tool_number: int) -> bool:
        """Remove a tool from the catalog."""
        if tool_number in self._tools:
            del self._tools[tool_number]
            logger.info(f"Removed tool T{tool_number}")
            return True
        return False

    def find_tool_for_operation(
        self,
        operation: str,
        min_diameter: float = 0,
        max_diameter: float = 1.0,
        material_type: str = "aluminum",
    ) -> List[Tool]:
        """
        Find suitable tools for an operation.

        Args:
            operation: Type of operation (drilling, milling, roughing, etc.)
            min_diameter: Minimum tool diameter
            max_diameter: Maximum tool diameter
            material_type: Workpiece material type

        Returns:
            List of suitable tools, sorted by preference
        """
        suitable_tools = []

        # Map operation to tool types
        operation_tool_map = {
            "drilling": [ToolType.DRILL],
            "spot_drilling": [ToolType.SPOT_DRILL, ToolType.CENTER_DRILL],
            "milling": [ToolType.END_MILL, ToolType.SLOT_DRILL],
            "roughing": [ToolType.ROUGHING_END_MILL, ToolType.END_MILL],
            "finishing": [ToolType.END_MILL, ToolType.BALL_END_MILL],
            "3d_contouring": [ToolType.BALL_END_MILL],
            "chamfering": [ToolType.CHAMFER_MILL, ToolType.V_BIT],
            "engraving": [ToolType.ENGRAVING_BIT, ToolType.V_BIT],
            "threading": [ToolType.THREAD_MILL, ToolType.TAP],
            "facing": [ToolType.FACE_MILL, ToolType.END_MILL],
        }

        target_types = operation_tool_map.get(
            operation.lower(),
            [ToolType.END_MILL]  # Default
        )

        for tool in self._tools.values():
            # Check type
            if tool.tool_type not in target_types:
                continue

            # Check diameter
            if not (min_diameter <= tool.geometry.diameter <= max_diameter):
                continue

            # Check material compatibility
            if material_type.lower() in ["steel", "stainless"]:
                # For steel, prefer coated carbide
                if tool.material in [ToolMaterial.HSS] and tool.coating == ToolCoating.UNCOATED:
                    continue  # Skip uncoated HSS for steel

            suitable_tools.append(tool)

        # Sort by diameter (smaller first for detail, larger for roughing)
        if operation in ["roughing", "facing"]:
            suitable_tools.sort(key=lambda t: -t.geometry.diameter)
        else:
            suitable_tools.sort(key=lambda t: t.geometry.diameter)

        return suitable_tools

    def get_tool_recommendations(
        self,
        feature: str,
        dimensions: Dict[str, float],
        material: str = "aluminum",
    ) -> Dict[str, Any]:
        """
        Get tool recommendations for a machining feature.

        Args:
            feature: Feature type (pocket, hole, profile, etc.)
            dimensions: Feature dimensions (width, depth, diameter, etc.)
            material: Workpiece material

        Returns:
            Dictionary with tool recommendations
        """
        recommendations = {
            "feature": feature,
            "dimensions": dimensions,
            "material": material,
            "tools": [],
        }

        if feature == "hole":
            diameter = dimensions.get("diameter", 0.25)
            depth = dimensions.get("depth", 0.5)

            # Spot drill first
            spot_tools = self.get_tools_by_type(ToolType.SPOT_DRILL)
            if spot_tools:
                recommendations["tools"].append({
                    "operation": "spot_drill",
                    "tool": spot_tools[0],
                    "purpose": "Create starting point for drill",
                })

            # Find drill
            drills = self.find_tool_for_operation(
                "drilling",
                min_diameter=diameter * 0.95,
                max_diameter=diameter * 1.05,
            )
            if drills:
                recommendations["tools"].append({
                    "operation": "drill",
                    "tool": drills[0],
                    "purpose": f"Drill {diameter}\" diameter hole",
                    "peck_depth": diameter * 3 if depth > diameter * 3 else None,
                })
            else:
                # Suggest helical interpolation
                end_mills = self.find_tool_for_operation(
                    "milling",
                    max_diameter=diameter * 0.6,
                )
                if end_mills:
                    recommendations["tools"].append({
                        "operation": "helical_interpolate",
                        "tool": end_mills[0],
                        "purpose": f"Helical interpolate {diameter}\" hole",
                    })

        elif feature == "pocket":
            width = dimensions.get("width", 1.0)
            depth = dimensions.get("depth", 0.25)
            corner_radius = dimensions.get("corner_radius", 0.125)

            # Roughing tool (larger)
            roughing = self.find_tool_for_operation(
                "roughing",
                max_diameter=min(width * 0.6, corner_radius * 1.8),
            )
            if roughing:
                recommendations["tools"].append({
                    "operation": "rough_pocket",
                    "tool": roughing[0],
                    "purpose": "Remove bulk material",
                })

            # Finishing tool (matches corner radius)
            finishing = self.find_tool_for_operation(
                "finishing",
                min_diameter=corner_radius * 1.9,
                max_diameter=corner_radius * 2.1,
            )
            if finishing:
                recommendations["tools"].append({
                    "operation": "finish_pocket",
                    "tool": finishing[0],
                    "purpose": "Finish walls and corners",
                })

        elif feature == "profile":
            depth = dimensions.get("depth", 0.25)

            # End mill for profiling
            end_mills = self.find_tool_for_operation("milling")
            if end_mills:
                recommendations["tools"].append({
                    "operation": "profile",
                    "tool": end_mills[0],
                    "purpose": "Profile cut",
                    "passes": max(1, int(depth / (end_mills[0].geometry.diameter * 0.5))),
                })

        elif feature == "chamfer":
            angle = dimensions.get("angle", 45)
            chamfer_tools = self.find_tool_for_operation("chamfering")
            if chamfer_tools:
                recommendations["tools"].append({
                    "operation": "chamfer",
                    "tool": chamfer_tools[0],
                    "purpose": f"Chamfer edges at {angle}°",
                })

        return recommendations


# Global instance
tool_catalog = ToolCatalog()
