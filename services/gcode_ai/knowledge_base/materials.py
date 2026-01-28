"""
Material Database for G-code AI

Contains material properties and recommended cutting parameters
for different materials commonly used in CNC machining.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class MaterialCategory(Enum):
    """Material category classification."""
    ALUMINUM = "aluminum"
    STEEL = "steel"
    STAINLESS = "stainless_steel"
    TITANIUM = "titanium"
    PLASTIC = "plastic"
    WOOD = "wood"
    BRASS = "brass"
    COPPER = "copper"
    COMPOSITE = "composite"
    FOAM = "foam"


class Machinability(Enum):
    """Machinability rating."""
    EXCELLENT = "excellent"  # Easy to machine, high speeds
    GOOD = "good"           # Standard machining
    FAIR = "fair"           # Moderate difficulty
    DIFFICULT = "difficult" # Challenging, special considerations
    VERY_DIFFICULT = "very_difficult"  # Expert level


@dataclass
class CuttingParameters:
    """Recommended cutting parameters for a material."""
    surface_speed_sfm: float      # Surface feet per minute
    feed_per_tooth: float         # Feed per tooth (inches)
    depth_of_cut_factor: float    # Factor of tool diameter for DOC
    width_of_cut_factor: float    # Factor of tool diameter for WOC
    coolant_required: bool = True
    coolant_type: str = "flood"   # flood, mist, air, none
    chip_load_range: tuple = (0.001, 0.010)  # Min/max chip load
    notes: str = ""


@dataclass
class Material:
    """Material definition with properties and cutting parameters."""
    name: str
    category: MaterialCategory
    machinability: Machinability
    hardness_bhn: Optional[float] = None  # Brinell hardness
    density_lb_in3: Optional[float] = None
    tensile_strength_psi: Optional[float] = None

    # Cutting parameters by operation type
    milling_params: Optional[CuttingParameters] = None
    drilling_params: Optional[CuttingParameters] = None
    turning_params: Optional[CuttingParameters] = None

    # Special considerations
    work_hardening: bool = False
    requires_rigid_setup: bool = False
    heat_sensitive: bool = False
    abrasive: bool = False

    # Recommended tooling
    recommended_tool_materials: List[str] = field(default_factory=list)
    recommended_coatings: List[str] = field(default_factory=list)

    # Safety notes
    safety_notes: List[str] = field(default_factory=list)


class MaterialDatabase:
    """
    Database of common machining materials with properties and
    recommended cutting parameters.
    """

    def __init__(self):
        """Initialize material database."""
        self._materials: Dict[str, Material] = {}
        self._load_default_materials()

    def _load_default_materials(self):
        """Load default material database."""
        # Aluminum alloys
        self._materials["6061-T6"] = Material(
            name="Aluminum 6061-T6",
            category=MaterialCategory.ALUMINUM,
            machinability=Machinability.EXCELLENT,
            hardness_bhn=95,
            density_lb_in3=0.098,
            tensile_strength_psi=45000,
            milling_params=CuttingParameters(
                surface_speed_sfm=1000,
                feed_per_tooth=0.004,
                depth_of_cut_factor=1.0,
                width_of_cut_factor=0.5,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.008),
                notes="High speed machining capable"
            ),
            drilling_params=CuttingParameters(
                surface_speed_sfm=500,
                feed_per_tooth=0.004,
                depth_of_cut_factor=3.0,  # 3x diameter depth
                width_of_cut_factor=1.0,
                coolant_required=True,
                coolant_type="flood",
                notes="Peck drilling recommended for deep holes"
            ),
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["Uncoated", "ZrN", "TiB2"],
            safety_notes=["Chips can be sharp", "Avoid chip buildup"]
        )

        self._materials["7075-T6"] = Material(
            name="Aluminum 7075-T6",
            category=MaterialCategory.ALUMINUM,
            machinability=Machinability.EXCELLENT,
            hardness_bhn=150,
            density_lb_in3=0.101,
            tensile_strength_psi=83000,
            milling_params=CuttingParameters(
                surface_speed_sfm=800,
                feed_per_tooth=0.003,
                depth_of_cut_factor=0.8,
                width_of_cut_factor=0.4,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.006),
                notes="Harder than 6061, reduce speeds slightly"
            ),
            recommended_tool_materials=["Carbide"],
            recommended_coatings=["ZrN", "TiB2", "DLC"],
            safety_notes=["Higher strength chips"]
        )

        # Steels
        self._materials["1018"] = Material(
            name="Steel 1018 (Low Carbon)",
            category=MaterialCategory.STEEL,
            machinability=Machinability.GOOD,
            hardness_bhn=126,
            density_lb_in3=0.284,
            tensile_strength_psi=64000,
            milling_params=CuttingParameters(
                surface_speed_sfm=100,
                feed_per_tooth=0.004,
                depth_of_cut_factor=0.5,
                width_of_cut_factor=0.3,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.006),
                notes="Good machinability, may produce stringy chips"
            ),
            drilling_params=CuttingParameters(
                surface_speed_sfm=80,
                feed_per_tooth=0.004,
                depth_of_cut_factor=2.0,
                width_of_cut_factor=1.0,
                coolant_required=True,
                coolant_type="flood",
                notes="Peck drilling for deep holes"
            ),
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["TiN", "TiAlN", "TiCN"],
            safety_notes=["Hot chips", "Sharp edges on parts"]
        )

        self._materials["4140"] = Material(
            name="Steel 4140 (Chrome-Moly)",
            category=MaterialCategory.STEEL,
            machinability=Machinability.FAIR,
            hardness_bhn=197,
            density_lb_in3=0.284,
            tensile_strength_psi=95000,
            milling_params=CuttingParameters(
                surface_speed_sfm=70,
                feed_per_tooth=0.003,
                depth_of_cut_factor=0.3,
                width_of_cut_factor=0.25,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.005),
                notes="Tougher than 1018, use rigid setup"
            ),
            requires_rigid_setup=True,
            recommended_tool_materials=["Carbide"],
            recommended_coatings=["TiAlN", "AlTiN"],
            safety_notes=["Hot chips", "May work harden if dwelling"]
        )

        # Stainless steels
        self._materials["304"] = Material(
            name="Stainless Steel 304",
            category=MaterialCategory.STAINLESS,
            machinability=Machinability.DIFFICULT,
            hardness_bhn=201,
            density_lb_in3=0.289,
            tensile_strength_psi=85000,
            milling_params=CuttingParameters(
                surface_speed_sfm=50,
                feed_per_tooth=0.003,
                depth_of_cut_factor=0.25,
                width_of_cut_factor=0.2,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.004),
                notes="Work hardens easily - maintain constant feed"
            ),
            work_hardening=True,
            requires_rigid_setup=True,
            recommended_tool_materials=["Carbide"],
            recommended_coatings=["TiAlN", "AlCrN"],
            safety_notes=[
                "Work hardens - never dwell or rub",
                "Use sharp tools only",
                "Constant engagement required"
            ]
        )

        self._materials["316"] = Material(
            name="Stainless Steel 316",
            category=MaterialCategory.STAINLESS,
            machinability=Machinability.DIFFICULT,
            hardness_bhn=217,
            density_lb_in3=0.290,
            tensile_strength_psi=84000,
            milling_params=CuttingParameters(
                surface_speed_sfm=40,
                feed_per_tooth=0.002,
                depth_of_cut_factor=0.2,
                width_of_cut_factor=0.15,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.001, 0.003),
                notes="More difficult than 304, reduce speeds"
            ),
            work_hardening=True,
            requires_rigid_setup=True,
            recommended_tool_materials=["Carbide"],
            recommended_coatings=["AlCrN", "nACo"],
            safety_notes=[
                "Severe work hardening",
                "Use positive rake geometry",
                "Never let tool rub"
            ]
        )

        # Plastics
        self._materials["delrin"] = Material(
            name="Delrin (Acetal/POM)",
            category=MaterialCategory.PLASTIC,
            machinability=Machinability.EXCELLENT,
            density_lb_in3=0.052,
            tensile_strength_psi=10000,
            milling_params=CuttingParameters(
                surface_speed_sfm=500,
                feed_per_tooth=0.005,
                depth_of_cut_factor=1.5,
                width_of_cut_factor=0.6,
                coolant_required=False,
                coolant_type="air",
                chip_load_range=(0.003, 0.010),
                notes="Air blast preferred, can melt with flood coolant"
            ),
            heat_sensitive=True,
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["Uncoated", "DLC"],
            safety_notes=["Can melt if overheated", "Use sharp tools"]
        )

        self._materials["hdpe"] = Material(
            name="HDPE (High Density Polyethylene)",
            category=MaterialCategory.PLASTIC,
            machinability=Machinability.EXCELLENT,
            density_lb_in3=0.035,
            tensile_strength_psi=4500,
            milling_params=CuttingParameters(
                surface_speed_sfm=600,
                feed_per_tooth=0.006,
                depth_of_cut_factor=2.0,
                width_of_cut_factor=0.7,
                coolant_required=False,
                coolant_type="air",
                chip_load_range=(0.004, 0.012),
                notes="Very easy to machine, watch for melting"
            ),
            heat_sensitive=True,
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["Uncoated"],
            safety_notes=["Melts easily", "May produce stringy chips"]
        )

        self._materials["acrylic"] = Material(
            name="Acrylic (PMMA)",
            category=MaterialCategory.PLASTIC,
            machinability=Machinability.GOOD,
            density_lb_in3=0.043,
            tensile_strength_psi=10500,
            milling_params=CuttingParameters(
                surface_speed_sfm=400,
                feed_per_tooth=0.004,
                depth_of_cut_factor=1.0,
                width_of_cut_factor=0.4,
                coolant_required=False,
                coolant_type="air",
                chip_load_range=(0.002, 0.008),
                notes="Can crack if stressed, use climb milling"
            ),
            heat_sensitive=True,
            recommended_tool_materials=["Carbide", "O-flute"],
            recommended_coatings=["Uncoated", "DLC"],
            safety_notes=[
                "Can crack or chip",
                "Use single flute or O-flute tools",
                "Avoid aggressive cuts"
            ]
        )

        # Wood
        self._materials["hardwood"] = Material(
            name="Hardwood (General)",
            category=MaterialCategory.WOOD,
            machinability=Machinability.GOOD,
            density_lb_in3=0.025,
            milling_params=CuttingParameters(
                surface_speed_sfm=800,
                feed_per_tooth=0.010,
                depth_of_cut_factor=2.0,
                width_of_cut_factor=0.5,
                coolant_required=False,
                coolant_type="none",
                chip_load_range=(0.005, 0.020),
                notes="Climb milling preferred for clean edges"
            ),
            recommended_tool_materials=["Carbide", "HSS"],
            recommended_coatings=["Uncoated"],
            safety_notes=["Dust extraction required", "Fire hazard with fine dust"]
        )

        self._materials["mdf"] = Material(
            name="MDF (Medium Density Fiberboard)",
            category=MaterialCategory.WOOD,
            machinability=Machinability.EXCELLENT,
            density_lb_in3=0.028,
            milling_params=CuttingParameters(
                surface_speed_sfm=600,
                feed_per_tooth=0.008,
                depth_of_cut_factor=1.5,
                width_of_cut_factor=0.6,
                coolant_required=False,
                coolant_type="none",
                chip_load_range=(0.004, 0.015),
                notes="Produces fine dust, use dust collection"
            ),
            abrasive=True,
            recommended_tool_materials=["Carbide"],
            recommended_coatings=["Uncoated"],
            safety_notes=[
                "Fine dust is hazardous - use extraction",
                "Wear appropriate respiratory protection",
                "Abrasive to tools"
            ]
        )

        # Brass and Copper
        self._materials["brass-360"] = Material(
            name="Brass 360 (Free Machining)",
            category=MaterialCategory.BRASS,
            machinability=Machinability.EXCELLENT,
            hardness_bhn=78,
            density_lb_in3=0.307,
            tensile_strength_psi=58000,
            milling_params=CuttingParameters(
                surface_speed_sfm=300,
                feed_per_tooth=0.004,
                depth_of_cut_factor=0.8,
                width_of_cut_factor=0.4,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.008),
                notes="Free machining, produces small chips"
            ),
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["Uncoated", "TiN"],
            safety_notes=["Sharp chips", "Can grab if tool is dull"]
        )

        self._materials["copper-110"] = Material(
            name="Copper 110 (ETP)",
            category=MaterialCategory.COPPER,
            machinability=Machinability.FAIR,
            hardness_bhn=50,
            density_lb_in3=0.323,
            tensile_strength_psi=32000,
            milling_params=CuttingParameters(
                surface_speed_sfm=200,
                feed_per_tooth=0.003,
                depth_of_cut_factor=0.5,
                width_of_cut_factor=0.3,
                coolant_required=True,
                coolant_type="flood",
                chip_load_range=(0.002, 0.006),
                notes="Soft and gummy, use sharp positive rake tools"
            ),
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["Uncoated"],
            safety_notes=["Gummy chips can wrap around tool"]
        )

        # Composites
        self._materials["carbon-fiber"] = Material(
            name="Carbon Fiber Composite",
            category=MaterialCategory.COMPOSITE,
            machinability=Machinability.DIFFICULT,
            density_lb_in3=0.057,
            tensile_strength_psi=145000,
            milling_params=CuttingParameters(
                surface_speed_sfm=400,
                feed_per_tooth=0.002,
                depth_of_cut_factor=0.3,
                width_of_cut_factor=0.2,
                coolant_required=False,
                coolant_type="air",
                chip_load_range=(0.001, 0.004),
                notes="Very abrasive, use diamond or PCD tooling"
            ),
            abrasive=True,
            requires_rigid_setup=True,
            recommended_tool_materials=["PCD", "Diamond Coated Carbide"],
            recommended_coatings=["Diamond", "CVD Diamond"],
            safety_notes=[
                "Dust is hazardous - use extraction",
                "Wear respiratory protection",
                "Very abrasive to tools",
                "Delamination risk on edges"
            ]
        )

        # Foam
        self._materials["eps-foam"] = Material(
            name="EPS Foam (Expanded Polystyrene)",
            category=MaterialCategory.FOAM,
            machinability=Machinability.EXCELLENT,
            density_lb_in3=0.001,
            milling_params=CuttingParameters(
                surface_speed_sfm=1000,
                feed_per_tooth=0.020,
                depth_of_cut_factor=5.0,
                width_of_cut_factor=1.0,
                coolant_required=False,
                coolant_type="none",
                chip_load_range=(0.010, 0.050),
                notes="Very easy to cut, can use hot wire or milling"
            ),
            heat_sensitive=True,
            recommended_tool_materials=["HSS", "Carbide"],
            recommended_coatings=["Uncoated"],
            safety_notes=["Static buildup", "Dust extraction recommended"]
        )

        logger.info(f"Loaded {len(self._materials)} materials into database")

    def get_material(self, name: str) -> Optional[Material]:
        """Get material by name (case-insensitive, partial match)."""
        name_lower = name.lower()

        # Exact match
        if name_lower in self._materials:
            return self._materials[name_lower]

        # Partial match
        for key, material in self._materials.items():
            if name_lower in key or name_lower in material.name.lower():
                return material

        return None

    def get_materials_by_category(
        self, category: MaterialCategory
    ) -> List[Material]:
        """Get all materials in a category."""
        return [
            m for m in self._materials.values()
            if m.category == category
        ]

    def get_all_materials(self) -> List[Material]:
        """Get all materials."""
        return list(self._materials.values())

    def search_materials(self, query: str) -> List[Material]:
        """Search materials by name or properties."""
        query_lower = query.lower()
        results = []

        for material in self._materials.values():
            if (
                query_lower in material.name.lower() or
                query_lower in material.category.value
            ):
                results.append(material)

        return results

    def add_material(self, key: str, material: Material):
        """Add a custom material to the database."""
        self._materials[key.lower()] = material
        logger.info(f"Added material: {key}")

    def get_cutting_recommendations(
        self,
        material_name: str,
        operation: str = "milling",
        tool_diameter: float = 0.25,
    ) -> Dict[str, Any]:
        """
        Get cutting parameter recommendations for a material and operation.

        Args:
            material_name: Material name to look up
            operation: Type of operation (milling, drilling, turning)
            tool_diameter: Tool diameter in inches

        Returns:
            Dictionary with recommended parameters
        """
        material = self.get_material(material_name)

        if not material:
            return {
                "error": f"Material '{material_name}' not found",
                "available_materials": list(self._materials.keys()),
            }

        # Get operation-specific parameters
        params = None
        if operation == "milling":
            params = material.milling_params
        elif operation == "drilling":
            params = material.drilling_params
        elif operation == "turning":
            params = material.turning_params

        if not params:
            return {
                "error": f"No {operation} parameters for {material.name}",
                "material": material.name,
            }

        # Calculate RPM from surface speed
        # SFM = (π * D * RPM) / 12
        # RPM = (SFM * 12) / (π * D)
        import math
        rpm = (params.surface_speed_sfm * 12) / (math.pi * tool_diameter)

        # Calculate feed rate
        # For milling: Feed = RPM * FPT * number_of_flutes
        # Assume 2 flutes for general calculation
        flutes = 2
        feed_ipm = rpm * params.feed_per_tooth * flutes

        # Calculate depth and width of cut
        depth_of_cut = tool_diameter * params.depth_of_cut_factor
        width_of_cut = tool_diameter * params.width_of_cut_factor

        return {
            "material": material.name,
            "operation": operation,
            "tool_diameter_in": tool_diameter,
            "recommended_parameters": {
                "spindle_rpm": round(rpm),
                "feed_rate_ipm": round(feed_ipm, 1),
                "feed_rate_mmpm": round(feed_ipm * 25.4, 1),
                "depth_of_cut_in": round(depth_of_cut, 4),
                "depth_of_cut_mm": round(depth_of_cut * 25.4, 3),
                "width_of_cut_in": round(width_of_cut, 4),
                "width_of_cut_mm": round(width_of_cut * 25.4, 3),
            },
            "coolant": {
                "required": params.coolant_required,
                "type": params.coolant_type,
            },
            "machinability": material.machinability.value,
            "notes": params.notes,
            "special_considerations": {
                "work_hardening": material.work_hardening,
                "requires_rigid_setup": material.requires_rigid_setup,
                "heat_sensitive": material.heat_sensitive,
                "abrasive": material.abrasive,
            },
            "recommended_tooling": {
                "tool_materials": material.recommended_tool_materials,
                "coatings": material.recommended_coatings,
            },
            "safety": material.safety_notes,
        }


# Global instance
material_db = MaterialDatabase()
