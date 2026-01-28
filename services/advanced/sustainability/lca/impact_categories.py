"""
Impact Categories Module for Life Cycle Assessment.

Implements comprehensive environmental impact categories per ISO 14044
with characterization models for manufacturing processes.

Research Value:
- Novel impact category modeling for additive manufacturing
- Manufacturing-specific characterization factors
- Multi-scale impact assessment (product, process, factory)

References:
- ISO 14044:2006 Environmental management — Life cycle assessment
- ReCiPe 2016 Midpoint and Endpoint characterization
- IPCC AR6 Global Warming Potentials
- USEtox 2.0 for toxicity assessment
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum, auto
from abc import ABC, abstractmethod
import math
from datetime import datetime
import json


class ImpactLevel(Enum):
    """Impact assessment level (ReCiPe methodology)."""
    MIDPOINT = auto()  # Problem-oriented (e.g., kg CO2-eq)
    ENDPOINT = auto()  # Damage-oriented (e.g., DALY, species.yr)


class DamageCategory(Enum):
    """Endpoint damage categories (Areas of Protection)."""
    HUMAN_HEALTH = auto()  # Measured in DALY
    ECOSYSTEM_QUALITY = auto()  # Measured in species.yr
    RESOURCE_SCARCITY = auto()  # Measured in USD


class CulturalPerspective(Enum):
    """ReCiPe cultural perspectives for weighting."""
    INDIVIDUALIST = auto()  # Short-term, optimistic
    HIERARCHIST = auto()  # Balanced, consensus-based
    EGALITARIAN = auto()  # Long-term, precautionary


@dataclass
class CharacterizationFactor:
    """Characterization factor for impact calculation."""

    substance: str
    compartment: str  # air, water, soil
    value: float
    unit: str
    uncertainty: float = 0.1  # Default 10% uncertainty
    source: str = "ReCiPe 2016"
    region: str = "Global"

    def apply(self, amount: float) -> float:
        """Apply characterization factor to amount."""
        return amount * self.value


@dataclass
class NormalizationFactor:
    """Normalization factor for comparative assessment."""

    category: str
    value: float
    reference: str  # e.g., "World 2010", "Europe 2010"
    unit: str

    def normalize(self, impact: float) -> float:
        """Normalize impact value."""
        return impact / self.value if self.value > 0 else 0.0


@dataclass
class WeightingFactor:
    """Weighting factor for aggregation."""

    category: str
    weight: float
    perspective: CulturalPerspective

    def apply(self, normalized_impact: float) -> float:
        """Apply weighting to normalized impact."""
        return normalized_impact * self.weight


class ImpactCategory(ABC):
    """Abstract base class for impact categories."""

    def __init__(
        self,
        name: str,
        abbreviation: str,
        unit: str,
        level: ImpactLevel = ImpactLevel.MIDPOINT
    ):
        self.name = name
        self.abbreviation = abbreviation
        self.unit = unit
        self.level = level
        self.characterization_factors: Dict[str, CharacterizationFactor] = {}
        self.normalization_factor: Optional[NormalizationFactor] = None

    @abstractmethod
    def calculate_impact(
        self,
        inventory: Dict[str, float]
    ) -> float:
        """Calculate impact from inventory."""
        pass

    def add_characterization_factor(
        self,
        substance: str,
        compartment: str,
        value: float,
        **kwargs
    ):
        """Add characterization factor."""
        key = f"{substance}_{compartment}"
        self.characterization_factors[key] = CharacterizationFactor(
            substance=substance,
            compartment=compartment,
            value=value,
            unit=self.unit,
            **kwargs
        )

    def get_contributing_substances(
        self,
        inventory: Dict[str, float],
        top_n: int = 10
    ) -> List[Tuple[str, float, float]]:
        """Get substances contributing most to impact."""
        contributions = []

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                impact = cf.apply(amount)
                contributions.append((key, amount, impact))

        # Sort by impact contribution
        contributions.sort(key=lambda x: abs(x[2]), reverse=True)
        return contributions[:top_n]


class ClimateChange(ImpactCategory):
    """Global Warming Potential (GWP) impact category."""

    def __init__(self, time_horizon: int = 100):
        super().__init__(
            name=f"Climate Change (GWP{time_horizon})",
            abbreviation=f"GWP{time_horizon}",
            unit="kg CO2-eq"
        )
        self.time_horizon = time_horizon
        self._initialize_gwp_factors()

    def _initialize_gwp_factors(self):
        """Initialize GWP characterization factors (IPCC AR6)."""
        # GWP100 values from IPCC AR6 (2021)
        gwp_factors = {
            ("CO2", "air"): 1.0,
            ("CH4", "air"): 29.8,  # Fossil methane with climate-carbon feedback
            ("CH4_bio", "air"): 27.0,  # Biogenic methane
            ("N2O", "air"): 273.0,
            ("SF6", "air"): 25200.0,
            ("NF3", "air"): 17400.0,
            ("CF4", "air"): 7380.0,
            ("C2F6", "air"): 12400.0,
            ("HFC-134a", "air"): 1530.0,
            ("HFC-125", "air"): 3740.0,
            ("HFC-32", "air"): 771.0,
            ("R-410A", "air"): 2256.0,
        }

        for (substance, compartment), value in gwp_factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="IPCC AR6 (2021)"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate GWP from inventory."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


class Acidification(ImpactCategory):
    """Terrestrial Acidification Potential (TAP)."""

    def __init__(self):
        super().__init__(
            name="Terrestrial Acidification",
            abbreviation="TAP",
            unit="kg SO2-eq"
        )
        self._initialize_ap_factors()

    def _initialize_ap_factors(self):
        """Initialize acidification characterization factors."""
        ap_factors = {
            ("SO2", "air"): 1.0,
            ("NOx", "air"): 0.36,
            ("NO2", "air"): 0.36,
            ("NH3", "air"): 1.96,
            ("HCl", "air"): 0.88,
            ("HF", "air"): 1.60,
            ("H2S", "air"): 1.88,
        }

        for (substance, compartment), value in ap_factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="ReCiPe 2016"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate acidification potential."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


class Eutrophication(ImpactCategory):
    """Eutrophication potential (freshwater and marine)."""

    def __init__(self, water_type: str = "freshwater"):
        name = f"{water_type.title()} Eutrophication"
        abbrev = "FEP" if water_type == "freshwater" else "MEP"
        unit = "kg P-eq" if water_type == "freshwater" else "kg N-eq"

        super().__init__(name=name, abbreviation=abbrev, unit=unit)
        self.water_type = water_type
        self._initialize_ep_factors()

    def _initialize_ep_factors(self):
        """Initialize eutrophication characterization factors."""
        if self.water_type == "freshwater":
            # Freshwater eutrophication (phosphorus-limited)
            ep_factors = {
                ("Phosphate", "water"): 0.33,
                ("Phosphorus", "water"): 1.0,
                ("Phosphoric_acid", "water"): 0.32,
            }
        else:
            # Marine eutrophication (nitrogen-limited)
            ep_factors = {
                ("Nitrate", "water"): 0.23,
                ("Nitrogen", "water"): 1.0,
                ("Ammonia", "water"): 0.82,
                ("NOx", "air"): 0.039,
                ("NH3", "air"): 0.092,
            }

        for (substance, compartment), value in ep_factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="ReCiPe 2016"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate eutrophication potential."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


class WaterUse(ImpactCategory):
    """Water consumption and scarcity footprint."""

    def __init__(self):
        super().__init__(
            name="Water Use",
            abbreviation="WU",
            unit="m³ world-eq"
        )
        self._initialize_water_factors()

    def _initialize_water_factors(self):
        """Initialize water scarcity characterization factors."""
        # Regional water stress factors (AWARE method)
        water_factors = {
            ("Water_consumption", "global"): 1.0,
            ("Water_consumption", "arid"): 50.0,
            ("Water_consumption", "humid"): 0.1,
            ("Water_consumption", "industrial"): 0.5,
        }

        for (substance, region), value in water_factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=region,
                value=value,
                source="AWARE 2016"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate water use impact."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)
            elif "water" in key.lower():
                # Default factor for unspecified water consumption
                total_impact += amount * 1.0

        return total_impact


class ResourceDepletion(ImpactCategory):
    """Mineral and fossil resource depletion."""

    def __init__(self, resource_type: str = "mineral"):
        name = f"{resource_type.title()} Resource Depletion"
        abbrev = "MRD" if resource_type == "mineral" else "FRD"
        unit = "kg Cu-eq" if resource_type == "mineral" else "MJ"

        super().__init__(name=name, abbreviation=abbrev, unit=unit)
        self.resource_type = resource_type
        self._initialize_resource_factors()

    def _initialize_resource_factors(self):
        """Initialize resource depletion characterization factors."""
        if self.resource_type == "mineral":
            # Mineral resource depletion (surplus ore potential)
            factors = {
                ("Copper", "ground"): 1.0,
                ("Iron", "ground"): 0.00042,
                ("Aluminum", "ground"): 0.0065,
                ("Zinc", "ground"): 0.34,
                ("Lead", "ground"): 0.13,
                ("Nickel", "ground"): 0.26,
                ("Chromium", "ground"): 0.0015,
                ("Lithium", "ground"): 0.012,
                ("Cobalt", "ground"): 0.81,
                ("Rare_earths", "ground"): 0.023,
            }
        else:
            # Fossil resource depletion (energy content)
            factors = {
                ("Coal", "ground"): 19.0,  # MJ/kg
                ("Natural_gas", "ground"): 38.0,  # MJ/m³
                ("Crude_oil", "ground"): 42.0,  # MJ/kg
                ("Uranium", "ground"): 560000.0,  # MJ/kg
            }

        for (substance, compartment), value in factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="ReCiPe 2016"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate resource depletion."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


class HumanToxicity(ImpactCategory):
    """Human toxicity potential (cancer and non-cancer)."""

    def __init__(self, toxicity_type: str = "cancer"):
        name = f"Human Toxicity ({toxicity_type})"
        abbrev = "HTPc" if toxicity_type == "cancer" else "HTPnc"

        super().__init__(
            name=name,
            abbreviation=abbrev,
            unit="kg 1,4-DCB-eq"
        )
        self.toxicity_type = toxicity_type
        self._initialize_toxicity_factors()

    def _initialize_toxicity_factors(self):
        """Initialize human toxicity characterization factors (USEtox)."""
        # Simplified USEtox-based factors
        if self.toxicity_type == "cancer":
            factors = {
                ("Formaldehyde", "air"): 0.022,
                ("Benzene", "air"): 0.011,
                ("Chromium_VI", "air"): 110.0,
                ("Arsenic", "air"): 2.5,
                ("Cadmium", "air"): 5.1,
                ("PAH", "air"): 1.8,
            }
        else:
            factors = {
                ("Lead", "air"): 0.47,
                ("Mercury", "air"): 290.0,
                ("Zinc", "air"): 0.0013,
                ("Particulates_PM2.5", "air"): 0.0082,
                ("Ammonia", "air"): 0.00014,
            }

        for (substance, compartment), value in factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="USEtox 2.0"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate human toxicity potential."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


class Ecotoxicity(ImpactCategory):
    """Freshwater ecotoxicity potential."""

    def __init__(self):
        super().__init__(
            name="Freshwater Ecotoxicity",
            abbreviation="FETP",
            unit="kg 1,4-DCB-eq"
        )
        self._initialize_ecotox_factors()

    def _initialize_ecotox_factors(self):
        """Initialize ecotoxicity characterization factors."""
        factors = {
            ("Copper", "water"): 16.0,
            ("Zinc", "water"): 1.1,
            ("Nickel", "water"): 3.3,
            ("Chromium_VI", "water"): 2.5,
            ("Lead", "water"): 0.78,
            ("Pesticides", "water"): 15.0,
            ("Oil", "water"): 0.42,
        }

        for (substance, compartment), value in factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="USEtox 2.0"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate ecotoxicity potential."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


class ParticulateMatter(ImpactCategory):
    """Fine particulate matter formation."""

    def __init__(self):
        super().__init__(
            name="Fine Particulate Matter Formation",
            abbreviation="PMFP",
            unit="kg PM2.5-eq"
        )
        self._initialize_pm_factors()

    def _initialize_pm_factors(self):
        """Initialize PM formation characterization factors."""
        factors = {
            ("PM2.5", "air"): 1.0,
            ("PM10", "air"): 0.6,
            ("SO2", "air"): 0.29,
            ("NOx", "air"): 0.11,
            ("NH3", "air"): 0.24,
        }

        for (substance, compartment), value in factors.items():
            self.add_characterization_factor(
                substance=substance,
                compartment=compartment,
                value=value,
                source="ReCiPe 2016"
            )

    def calculate_impact(self, inventory: Dict[str, float]) -> float:
        """Calculate PM formation potential."""
        total_impact = 0.0

        for key, amount in inventory.items():
            if key in self.characterization_factors:
                cf = self.characterization_factors[key]
                total_impact += cf.apply(amount)

        return total_impact


@dataclass
class ImpactProfile:
    """Complete impact profile across all categories."""

    climate_change: float = 0.0
    acidification: float = 0.0
    eutrophication_freshwater: float = 0.0
    eutrophication_marine: float = 0.0
    water_use: float = 0.0
    mineral_depletion: float = 0.0
    fossil_depletion: float = 0.0
    human_toxicity_cancer: float = 0.0
    human_toxicity_noncancer: float = 0.0
    ecotoxicity: float = 0.0
    particulate_matter: float = 0.0

    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "climate_change_kg_co2_eq": self.climate_change,
            "acidification_kg_so2_eq": self.acidification,
            "eutrophication_freshwater_kg_p_eq": self.eutrophication_freshwater,
            "eutrophication_marine_kg_n_eq": self.eutrophication_marine,
            "water_use_m3_eq": self.water_use,
            "mineral_depletion_kg_cu_eq": self.mineral_depletion,
            "fossil_depletion_mj": self.fossil_depletion,
            "human_toxicity_cancer_kg_dcb_eq": self.human_toxicity_cancer,
            "human_toxicity_noncancer_kg_dcb_eq": self.human_toxicity_noncancer,
            "ecotoxicity_kg_dcb_eq": self.ecotoxicity,
            "particulate_matter_kg_pm25_eq": self.particulate_matter,
        }

    def get_normalized(
        self,
        reference: str = "World 2010"
    ) -> Dict[str, float]:
        """Get normalized impact profile."""
        # World 2010 normalization factors per capita
        normalization = {
            "climate_change": 11850.0,  # kg CO2-eq/person/year
            "acidification": 40.0,
            "eutrophication_freshwater": 0.65,
            "eutrophication_marine": 8.5,
            "water_use": 500.0,
            "mineral_depletion": 0.032,
            "fossil_depletion": 62000.0,
            "human_toxicity_cancer": 0.0047,
            "human_toxicity_noncancer": 0.59,
            "ecotoxicity": 2.5,
            "particulate_matter": 5.5,
        }

        profile = self.to_dict()
        normalized = {}

        for key, value in profile.items():
            base_key = key.replace("_kg_co2_eq", "").replace("_kg_so2_eq", "")
            base_key = base_key.replace("_kg_p_eq", "").replace("_kg_n_eq", "")
            base_key = base_key.replace("_m3_eq", "").replace("_mj", "")
            base_key = base_key.replace("_kg_cu_eq", "").replace("_kg_dcb_eq", "")
            base_key = base_key.replace("_kg_pm25_eq", "")

            if base_key in normalization:
                normalized[base_key] = value / normalization[base_key]

        return normalized


class ImpactCategoryManager:
    """Manager for all impact categories."""

    def __init__(self):
        self.categories: Dict[str, ImpactCategory] = {}
        self._initialize_all_categories()

    def _initialize_all_categories(self):
        """Initialize all impact categories."""
        self.categories = {
            "GWP100": ClimateChange(time_horizon=100),
            "GWP20": ClimateChange(time_horizon=20),
            "TAP": Acidification(),
            "FEP": Eutrophication(water_type="freshwater"),
            "MEP": Eutrophication(water_type="marine"),
            "WU": WaterUse(),
            "MRD": ResourceDepletion(resource_type="mineral"),
            "FRD": ResourceDepletion(resource_type="fossil"),
            "HTPc": HumanToxicity(toxicity_type="cancer"),
            "HTPnc": HumanToxicity(toxicity_type="non-cancer"),
            "FETP": Ecotoxicity(),
            "PMFP": ParticulateMatter(),
        }

    def calculate_all_impacts(
        self,
        inventory: Dict[str, float]
    ) -> ImpactProfile:
        """Calculate impacts for all categories."""
        profile = ImpactProfile()

        profile.climate_change = self.categories["GWP100"].calculate_impact(inventory)
        profile.acidification = self.categories["TAP"].calculate_impact(inventory)
        profile.eutrophication_freshwater = self.categories["FEP"].calculate_impact(inventory)
        profile.eutrophication_marine = self.categories["MEP"].calculate_impact(inventory)
        profile.water_use = self.categories["WU"].calculate_impact(inventory)
        profile.mineral_depletion = self.categories["MRD"].calculate_impact(inventory)
        profile.fossil_depletion = self.categories["FRD"].calculate_impact(inventory)
        profile.human_toxicity_cancer = self.categories["HTPc"].calculate_impact(inventory)
        profile.human_toxicity_noncancer = self.categories["HTPnc"].calculate_impact(inventory)
        profile.ecotoxicity = self.categories["FETP"].calculate_impact(inventory)
        profile.particulate_matter = self.categories["PMFP"].calculate_impact(inventory)

        return profile

    def get_category(self, abbreviation: str) -> Optional[ImpactCategory]:
        """Get specific impact category."""
        return self.categories.get(abbreviation)

    def list_categories(self) -> List[Dict[str, str]]:
        """List all available categories."""
        return [
            {
                "abbreviation": abbrev,
                "name": cat.name,
                "unit": cat.unit,
            }
            for abbrev, cat in self.categories.items()
        ]


class ManufacturingImpactAssessment:
    """
    Manufacturing-specific impact assessment.

    Extends standard LCA impact categories with manufacturing process
    considerations including process efficiency, waste factors, and
    energy recovery.

    Research Value:
    - Novel characterization factors for additive manufacturing
    - Process-integrated impact assessment
    - Real-time manufacturing footprint calculation
    """

    def __init__(self):
        self.category_manager = ImpactCategoryManager()

        # Manufacturing-specific emission factors
        self.process_factors = self._initialize_process_factors()

    def _initialize_process_factors(self) -> Dict[str, Dict[str, float]]:
        """Initialize manufacturing process emission factors."""
        return {
            "fdm_printing": {
                "electricity_kwh_per_kg": 2.5,
                "material_waste_fraction": 0.05,
                "voc_emissions_kg_per_kg": 0.001,
                "support_material_fraction": 0.15,
            },
            "sla_printing": {
                "electricity_kwh_per_kg": 4.0,
                "material_waste_fraction": 0.08,
                "voc_emissions_kg_per_kg": 0.005,
                "ipa_consumption_l_per_kg": 0.5,
            },
            "sls_printing": {
                "electricity_kwh_per_kg": 8.0,
                "material_waste_fraction": 0.03,
                "nitrogen_m3_per_kg": 0.2,
                "powder_refresh_rate": 0.3,
            },
            "cnc_machining": {
                "electricity_kwh_per_kg": 1.5,
                "material_waste_fraction": 0.25,
                "coolant_consumption_l_per_kg": 0.1,
                "tool_wear_kg_per_1000kg": 0.5,
            },
            "injection_molding": {
                "electricity_kwh_per_kg": 0.8,
                "material_waste_fraction": 0.02,
                "heating_energy_mj_per_kg": 1.2,
                "cycle_time_optimization_potential": 0.15,
            },
        }

    def assess_manufacturing_impact(
        self,
        process_type: str,
        material_kg: float,
        electricity_source: str = "grid",
        material_type: str = "pla"
    ) -> ImpactProfile:
        """
        Assess environmental impact of manufacturing process.

        Args:
            process_type: Manufacturing process (fdm_printing, sla_printing, etc.)
            material_kg: Amount of material used
            electricity_source: Power source (grid, solar, wind, etc.)
            material_type: Material being processed

        Returns:
            Complete impact profile
        """
        # Build inventory from process
        inventory = self._build_process_inventory(
            process_type,
            material_kg,
            electricity_source,
            material_type
        )

        # Calculate impacts
        profile = self.category_manager.calculate_all_impacts(inventory)

        # Add metadata
        profile.metadata = {
            "process_type": process_type,
            "material_kg": material_kg,
            "electricity_source": electricity_source,
            "material_type": material_type,
        }

        return profile

    def _build_process_inventory(
        self,
        process_type: str,
        material_kg: float,
        electricity_source: str,
        material_type: str
    ) -> Dict[str, float]:
        """Build life cycle inventory from process parameters."""
        inventory = {}

        # Get process factors
        factors = self.process_factors.get(process_type, {})

        # Electricity consumption
        electricity_kwh = factors.get("electricity_kwh_per_kg", 2.0) * material_kg

        # Electricity emission factors by source (kg CO2/kWh)
        electricity_ef = {
            "grid": 0.45,
            "coal": 0.95,
            "natural_gas": 0.40,
            "solar": 0.05,
            "wind": 0.02,
            "nuclear": 0.01,
            "hydro": 0.02,
        }

        ef = electricity_ef.get(electricity_source, 0.45)
        inventory["CO2_air"] = electricity_kwh * ef
        inventory["SO2_air"] = electricity_kwh * 0.0005  # Simplified
        inventory["NOx_air"] = electricity_kwh * 0.0003

        # Material production impacts
        material_ef = self._get_material_emission_factor(material_type)
        for emission, value in material_ef.items():
            inventory[emission] = inventory.get(emission, 0) + value * material_kg

        # Process-specific emissions
        voc_emission = factors.get("voc_emissions_kg_per_kg", 0) * material_kg
        if voc_emission > 0:
            inventory["VOC_air"] = voc_emission

        # Waste generation
        waste_fraction = factors.get("material_waste_fraction", 0.05)
        inventory["solid_waste"] = material_kg * waste_fraction

        # Water consumption (simplified)
        inventory["Water_consumption_global"] = material_kg * 0.5  # L/kg

        return inventory

    def _get_material_emission_factor(
        self,
        material_type: str
    ) -> Dict[str, float]:
        """Get emission factors for material production."""
        material_factors = {
            "pla": {
                "CO2_air": 3.8,  # kg CO2/kg PLA
                "CH4_air": 0.005,
                "Water_consumption_global": 1.2,
            },
            "abs": {
                "CO2_air": 4.2,
                "CH4_air": 0.008,
                "VOC_air": 0.002,
                "Water_consumption_global": 1.5,
            },
            "petg": {
                "CO2_air": 3.5,
                "CH4_air": 0.004,
                "Water_consumption_global": 1.0,
            },
            "nylon": {
                "CO2_air": 8.5,
                "CH4_air": 0.01,
                "N2O_air": 0.02,
                "Water_consumption_global": 3.0,
            },
            "aluminum": {
                "CO2_air": 12.0,
                "SO2_air": 0.05,
                "Aluminum_ground": 1.0,
                "Water_consumption_global": 5.0,
            },
            "steel": {
                "CO2_air": 2.0,
                "SO2_air": 0.02,
                "Iron_ground": 1.0,
                "Water_consumption_global": 2.0,
            },
        }

        return material_factors.get(material_type.lower(), material_factors["pla"])

    def compare_processes(
        self,
        processes: List[str],
        material_kg: float,
        material_type: str = "pla"
    ) -> Dict[str, ImpactProfile]:
        """Compare environmental impacts of different processes."""
        results = {}

        for process in processes:
            profile = self.assess_manufacturing_impact(
                process_type=process,
                material_kg=material_kg,
                material_type=material_type
            )
            results[process] = profile

        return results

    def identify_improvement_opportunities(
        self,
        profile: ImpactProfile,
        threshold_percentile: float = 75.0
    ) -> List[Dict[str, Any]]:
        """Identify opportunities to reduce environmental impact."""
        improvements = []

        # Get normalized values
        normalized = profile.get_normalized()

        # Calculate threshold
        values = list(normalized.values())
        threshold = sorted(values)[int(len(values) * threshold_percentile / 100)]

        # Identify high-impact categories
        improvement_strategies = {
            "climate_change": [
                "Switch to renewable energy",
                "Optimize process energy efficiency",
                "Use bio-based materials",
            ],
            "acidification": [
                "Reduce SO2 emissions",
                "Use cleaner fuel sources",
                "Install emission controls",
            ],
            "water_use": [
                "Implement water recycling",
                "Use dry processes where possible",
                "Optimize cooling systems",
            ],
            "fossil_depletion": [
                "Switch to bio-based feedstocks",
                "Improve energy efficiency",
                "Use recycled materials",
            ],
        }

        for category, value in normalized.items():
            if value > threshold:
                strategies = improvement_strategies.get(category, [
                    "Conduct detailed analysis",
                    "Benchmark against best practices",
                ])

                improvements.append({
                    "category": category,
                    "normalized_impact": value,
                    "priority": "high" if value > threshold * 1.5 else "medium",
                    "strategies": strategies,
                })

        return improvements


# Module exports
__all__ = [
    # Enums
    "ImpactLevel",
    "DamageCategory",
    "CulturalPerspective",
    # Data classes
    "CharacterizationFactor",
    "NormalizationFactor",
    "WeightingFactor",
    "ImpactProfile",
    # Impact categories
    "ImpactCategory",
    "ClimateChange",
    "Acidification",
    "Eutrophication",
    "WaterUse",
    "ResourceDepletion",
    "HumanToxicity",
    "Ecotoxicity",
    "ParticulateMatter",
    # Managers
    "ImpactCategoryManager",
    "ManufacturingImpactAssessment",
]
