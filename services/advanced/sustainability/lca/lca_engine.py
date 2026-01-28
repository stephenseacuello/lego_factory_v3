"""
Life Cycle Assessment Engine (ISO 14040/14044).

This module implements comprehensive LCA calculations:
- Goal and scope definition
- Life cycle inventory analysis
- Life cycle impact assessment
- Interpretation and reporting

Research Contributions:
- Real-time LCA for additive manufacturing
- Dynamic environmental impact tracking
- Integration with production planning

References:
- ISO 14040:2006 - LCA Principles and Framework
- ISO 14044:2006 - LCA Requirements and Guidelines
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LifeCyclePhase(Enum):
    """Life cycle phases according to ISO 14040."""
    RAW_MATERIAL_EXTRACTION = "raw_material_extraction"
    MATERIAL_PROCESSING = "material_processing"
    MANUFACTURING = "manufacturing"
    DISTRIBUTION = "distribution"
    USE = "use"
    END_OF_LIFE = "end_of_life"
    # Sub-phases for manufacturing
    PRINTING = "printing"
    POST_PROCESSING = "post_processing"
    QUALITY_CONTROL = "quality_control"
    PACKAGING = "packaging"


class ImpactCategory(Enum):
    """Environmental impact categories."""
    GWP = "global_warming_potential"  # kg CO2-eq
    AP = "acidification_potential"  # kg SO2-eq
    EP = "eutrophication_potential"  # kg PO4-eq
    ODP = "ozone_depletion_potential"  # kg CFC-11-eq
    POCP = "photochemical_ozone_creation"  # kg C2H4-eq
    ADP_ELEMENTS = "abiotic_depletion_elements"  # kg Sb-eq
    ADP_FOSSIL = "abiotic_depletion_fossil"  # MJ
    WDP = "water_depletion_potential"  # m³
    HTP = "human_toxicity_potential"  # kg 1,4-DB-eq
    FAETP = "freshwater_aquatic_ecotoxicity"  # kg 1,4-DB-eq
    MAETP = "marine_aquatic_ecotoxicity"  # kg 1,4-DB-eq
    TETP = "terrestrial_ecotoxicity"  # kg 1,4-DB-eq
    LAND_USE = "land_use"  # m²·year
    PM = "particulate_matter"  # kg PM2.5-eq


class FlowType(Enum):
    """Types of flows in LCI."""
    ELEMENTARY_INPUT = "elementary_input"  # From nature
    ELEMENTARY_OUTPUT = "elementary_output"  # To nature
    PRODUCT_INPUT = "product_input"  # From technosphere
    PRODUCT_OUTPUT = "product_output"  # To technosphere
    WASTE_OUTPUT = "waste_output"


@dataclass
class InventoryItem:
    """Life Cycle Inventory item."""
    item_id: str
    name: str
    flow_type: FlowType
    amount: float
    unit: str
    phase: LifeCyclePhase
    compartment: Optional[str] = None  # air, water, soil
    sub_compartment: Optional[str] = None
    characterization_factors: Dict[ImpactCategory, float] = field(default_factory=dict)
    uncertainty: Optional[float] = None  # Standard deviation
    data_quality: Optional[str] = None  # e.g., "measured", "estimated", "literature"

    def to_dict(self) -> Dict:
        return {
            'item_id': self.item_id,
            'name': self.name,
            'flow_type': self.flow_type.value,
            'amount': float(self.amount),
            'unit': self.unit,
            'phase': self.phase.value,
            'compartment': self.compartment,
            'uncertainty': self.uncertainty,
            'data_quality': self.data_quality
        }


@dataclass
class LCAConfig:
    """Configuration for LCA study."""
    study_name: str
    functional_unit: str = "1 LEGO brick produced"
    system_boundary: List[LifeCyclePhase] = field(default_factory=lambda: [
        LifeCyclePhase.RAW_MATERIAL_EXTRACTION,
        LifeCyclePhase.MATERIAL_PROCESSING,
        LifeCyclePhase.MANUFACTURING,
        LifeCyclePhase.DISTRIBUTION,
        LifeCyclePhase.USE,
        LifeCyclePhase.END_OF_LIFE
    ])
    impact_categories: List[ImpactCategory] = field(default_factory=lambda: [
        ImpactCategory.GWP,
        ImpactCategory.AP,
        ImpactCategory.EP,
        ImpactCategory.WDP
    ])
    allocation_method: str = "mass"  # mass, economic, physical
    cut_off_threshold: float = 0.01  # 1% cut-off
    time_horizon: int = 100  # years for GWP
    include_capital_goods: bool = False
    include_infrastructure: bool = False


@dataclass
class ImpactResult:
    """Impact assessment result for one category."""
    category: ImpactCategory
    value: float
    unit: str
    contribution_by_phase: Dict[LifeCyclePhase, float]
    contribution_by_process: Dict[str, float]
    uncertainty: Optional[float] = None
    normalized_value: Optional[float] = None
    weighted_value: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            'category': self.category.value,
            'value': float(self.value),
            'unit': self.unit,
            'contribution_by_phase': {p.value: float(v) for p, v in self.contribution_by_phase.items()},
            'contribution_by_process': {k: float(v) for k, v in self.contribution_by_process.items()},
            'uncertainty': self.uncertainty,
            'normalized_value': self.normalized_value,
            'weighted_value': self.weighted_value
        }


@dataclass
class LCAResult:
    """Complete LCA result."""
    study_id: str
    config: LCAConfig
    inventory: List[InventoryItem]
    impact_results: Dict[ImpactCategory, ImpactResult]
    total_weighted_score: Optional[float] = None
    hotspots: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'study_id': self.study_id,
            'functional_unit': self.config.functional_unit,
            'impact_results': {k.value: v.to_dict() for k, v in self.impact_results.items()},
            'total_weighted_score': self.total_weighted_score,
            'hotspots': self.hotspots,
            'recommendations': self.recommendations,
            'timestamp': self.timestamp.isoformat()
        }

    def get_environmental_profile(self) -> Dict[str, float]:
        """Get simplified environmental profile."""
        return {
            cat.value: result.value
            for cat, result in self.impact_results.items()
        }


class LCAEngine:
    """
    Life Cycle Assessment Engine.

    Performs comprehensive LCA according to ISO 14040/14044.
    """

    def __init__(self, config: Optional[LCAConfig] = None):
        self.config = config or LCAConfig(study_name="Default LCA Study")
        self.inventory: List[InventoryItem] = []

        # Standard characterization factors (simplified database)
        self._init_characterization_factors()

        # Normalization factors (CML 2001)
        self._normalization_factors = {
            ImpactCategory.GWP: 4.22e+13,  # kg CO2-eq
            ImpactCategory.AP: 2.39e+11,  # kg SO2-eq
            ImpactCategory.EP: 1.58e+11,  # kg PO4-eq
            ImpactCategory.ODP: 2.27e+08,  # kg CFC-11-eq
            ImpactCategory.POCP: 3.68e+10,  # kg C2H4-eq
            ImpactCategory.WDP: 9.00e+12,  # m³
        }

        # Weighting factors (equal weighting by default)
        self._weighting_factors = {cat: 1.0 / len(ImpactCategory) for cat in ImpactCategory}

    def _init_characterization_factors(self):
        """Initialize characterization factor database."""
        self._cf_database = {
            # Electricity (kWh)
            'electricity_grid': {
                ImpactCategory.GWP: 0.5,  # kg CO2-eq/kWh
                ImpactCategory.AP: 0.002,
                ImpactCategory.EP: 0.0003,
                ImpactCategory.WDP: 0.02
            },
            'electricity_renewable': {
                ImpactCategory.GWP: 0.05,
                ImpactCategory.AP: 0.0002,
                ImpactCategory.EP: 0.00003,
                ImpactCategory.WDP: 0.005
            },
            # Materials (kg)
            'abs_plastic': {
                ImpactCategory.GWP: 3.2,
                ImpactCategory.AP: 0.012,
                ImpactCategory.EP: 0.002,
                ImpactCategory.ADP_FOSSIL: 80.0
            },
            'pla_bioplastic': {
                ImpactCategory.GWP: 1.8,
                ImpactCategory.AP: 0.008,
                ImpactCategory.EP: 0.003,
                ImpactCategory.ADP_FOSSIL: 55.0
            },
            'petg_plastic': {
                ImpactCategory.GWP: 2.5,
                ImpactCategory.AP: 0.010,
                ImpactCategory.EP: 0.0018,
                ImpactCategory.ADP_FOSSIL: 70.0
            },
            # Transport (tonne-km)
            'truck_transport': {
                ImpactCategory.GWP: 0.089,
                ImpactCategory.AP: 0.0004,
                ImpactCategory.EP: 0.0001,
            },
            'ship_transport': {
                ImpactCategory.GWP: 0.016,
                ImpactCategory.AP: 0.00015,
                ImpactCategory.EP: 0.00002,
            },
            # Waste treatment
            'landfill_plastic': {
                ImpactCategory.GWP: 0.02,
                ImpactCategory.EP: 0.001
            },
            'incineration_plastic': {
                ImpactCategory.GWP: 2.8,
                ImpactCategory.AP: 0.008
            },
            'recycling_plastic': {
                ImpactCategory.GWP: -1.5,  # Credit
                ImpactCategory.AP: -0.005
            },
            # Emissions
            'co2_emission': {
                ImpactCategory.GWP: 1.0
            },
            'ch4_emission': {
                ImpactCategory.GWP: 28.0  # 100-year GWP
            },
            'n2o_emission': {
                ImpactCategory.GWP: 265.0
            },
            'so2_emission': {
                ImpactCategory.AP: 1.0
            },
            'nox_emission': {
                ImpactCategory.AP: 0.5,
                ImpactCategory.EP: 0.13
            }
        }

    def add_inventory_item(
        self,
        name: str,
        amount: float,
        unit: str,
        phase: LifeCyclePhase,
        flow_type: FlowType = FlowType.ELEMENTARY_INPUT,
        process_name: Optional[str] = None,
        characterization_factors: Optional[Dict[ImpactCategory, float]] = None
    ) -> InventoryItem:
        """Add an item to the life cycle inventory."""
        # Get characterization factors from database or use provided
        if characterization_factors is None:
            cf = self._cf_database.get(name.lower().replace(' ', '_'), {})
        else:
            cf = characterization_factors

        item = InventoryItem(
            item_id=f"item_{len(self.inventory)}",
            name=name,
            flow_type=flow_type,
            amount=amount,
            unit=unit,
            phase=phase,
            characterization_factors=cf
        )

        self.inventory.append(item)
        return item

    def add_process(
        self,
        process_name: str,
        phase: LifeCyclePhase,
        inputs: Dict[str, Tuple[float, str]],  # name -> (amount, unit)
        outputs: Dict[str, Tuple[float, str]],
        emissions: Optional[Dict[str, Tuple[float, str]]] = None
    ):
        """Add a complete process with inputs and outputs."""
        for name, (amount, unit) in inputs.items():
            self.add_inventory_item(
                name=name,
                amount=amount,
                unit=unit,
                phase=phase,
                flow_type=FlowType.PRODUCT_INPUT
            )

        for name, (amount, unit) in outputs.items():
            self.add_inventory_item(
                name=name,
                amount=amount,
                unit=unit,
                phase=phase,
                flow_type=FlowType.PRODUCT_OUTPUT
            )

        if emissions:
            for name, (amount, unit) in emissions.items():
                self.add_inventory_item(
                    name=name,
                    amount=amount,
                    unit=unit,
                    phase=phase,
                    flow_type=FlowType.ELEMENTARY_OUTPUT
                )

    def calculate_impacts(self) -> Dict[ImpactCategory, ImpactResult]:
        """Calculate life cycle impact assessment."""
        impact_results = {}

        for category in self.config.impact_categories:
            # Calculate total impact
            total = 0.0
            by_phase: Dict[LifeCyclePhase, float] = {p: 0.0 for p in LifeCyclePhase}
            by_process: Dict[str, float] = {}

            for item in self.inventory:
                cf = item.characterization_factors.get(category, 0.0)
                impact = item.amount * cf

                total += impact
                by_phase[item.phase] += impact

                if item.name not in by_process:
                    by_process[item.name] = 0.0
                by_process[item.name] += impact

            # Get unit
            unit = self._get_impact_unit(category)

            # Calculate normalized value
            norm_factor = self._normalization_factors.get(category)
            normalized = total / norm_factor if norm_factor else None

            # Calculate weighted value
            weight = self._weighting_factors.get(category, 1.0)
            weighted = (normalized or total) * weight

            impact_results[category] = ImpactResult(
                category=category,
                value=total,
                unit=unit,
                contribution_by_phase=by_phase,
                contribution_by_process=by_process,
                normalized_value=normalized,
                weighted_value=weighted
            )

        return impact_results

    def _get_impact_unit(self, category: ImpactCategory) -> str:
        """Get unit for impact category."""
        units = {
            ImpactCategory.GWP: "kg CO2-eq",
            ImpactCategory.AP: "kg SO2-eq",
            ImpactCategory.EP: "kg PO4-eq",
            ImpactCategory.ODP: "kg CFC-11-eq",
            ImpactCategory.POCP: "kg C2H4-eq",
            ImpactCategory.ADP_ELEMENTS: "kg Sb-eq",
            ImpactCategory.ADP_FOSSIL: "MJ",
            ImpactCategory.WDP: "m³",
            ImpactCategory.HTP: "kg 1,4-DB-eq",
            ImpactCategory.LAND_USE: "m²·year",
            ImpactCategory.PM: "kg PM2.5-eq"
        }
        return units.get(category, "units")

    def identify_hotspots(
        self,
        impact_results: Dict[ImpactCategory, ImpactResult],
        threshold: float = 0.1
    ) -> List[Dict]:
        """Identify environmental hotspots."""
        hotspots = []

        for category, result in impact_results.items():
            # Find significant processes (>threshold contribution)
            for process, impact in result.contribution_by_process.items():
                contribution = abs(impact) / abs(result.value) if result.value != 0 else 0

                if contribution >= threshold:
                    hotspots.append({
                        'category': category.value,
                        'process': process,
                        'impact': float(impact),
                        'contribution': float(contribution),
                        'phase': self._get_process_phase(process).value
                    })

        # Sort by contribution
        hotspots.sort(key=lambda x: x['contribution'], reverse=True)

        return hotspots

    def _get_process_phase(self, process_name: str) -> LifeCyclePhase:
        """Get phase for a process."""
        for item in self.inventory:
            if item.name == process_name:
                return item.phase
        return LifeCyclePhase.MANUFACTURING

    def generate_recommendations(
        self,
        impact_results: Dict[ImpactCategory, ImpactResult],
        hotspots: List[Dict]
    ) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []

        # Analyze hotspots
        for hs in hotspots[:5]:
            category = hs['category']
            process = hs['process']
            contribution = hs['contribution']

            if 'electricity' in process.lower():
                recommendations.append(
                    f"Switch to renewable electricity to reduce {category} "
                    f"(current contribution: {contribution:.1%})"
                )
            elif 'transport' in process.lower():
                recommendations.append(
                    f"Optimize logistics or use lower-emission transport for {process} "
                    f"(current contribution: {contribution:.1%})"
                )
            elif 'plastic' in process.lower() or 'material' in process.lower():
                recommendations.append(
                    f"Consider bio-based or recycled materials to reduce {process} impact "
                    f"(current contribution: {contribution:.1%})"
                )

        # General recommendations based on impact profile
        if ImpactCategory.GWP in impact_results:
            gwp = impact_results[ImpactCategory.GWP].value
            if gwp > 10:  # High carbon footprint
                recommendations.append(
                    "Consider carbon offset programs or process efficiency improvements"
                )

        if ImpactCategory.WDP in impact_results:
            wdp = impact_results[ImpactCategory.WDP].value
            if wdp > 1:
                recommendations.append(
                    "Implement water recycling or closed-loop cooling systems"
                )

        return recommendations

    def run_lca(self, study_id: Optional[str] = None) -> LCAResult:
        """Run complete LCA study."""
        if study_id is None:
            study_id = f"lca_{int(datetime.now().timestamp())}"

        logger.info(f"Running LCA study: {study_id}")

        # Calculate impacts
        impact_results = self.calculate_impacts()

        # Identify hotspots
        hotspots = self.identify_hotspots(impact_results)

        # Generate recommendations
        recommendations = self.generate_recommendations(impact_results, hotspots)

        # Calculate total weighted score
        total_weighted = sum(r.weighted_value or 0 for r in impact_results.values())

        result = LCAResult(
            study_id=study_id,
            config=self.config,
            inventory=self.inventory,
            impact_results=impact_results,
            total_weighted_score=total_weighted,
            hotspots=hotspots,
            recommendations=recommendations
        )

        logger.info(f"LCA complete. GWP: {impact_results.get(ImpactCategory.GWP, {}).value if ImpactCategory.GWP in impact_results else 'N/A'}")

        return result

    def compare_scenarios(
        self,
        scenarios: Dict[str, List[InventoryItem]]
    ) -> Dict[str, Dict]:
        """Compare multiple LCA scenarios."""
        results = {}

        for scenario_name, inventory in scenarios.items():
            # Temporarily replace inventory
            original_inventory = self.inventory
            self.inventory = inventory

            # Run LCA
            lca_result = self.run_lca(scenario_name)

            results[scenario_name] = {
                'impacts': lca_result.get_environmental_profile(),
                'total_score': lca_result.total_weighted_score,
                'hotspots': lca_result.hotspots[:3]
            }

            # Restore original
            self.inventory = original_inventory

        return results


class ManufacturingLCA(LCAEngine):
    """
    Manufacturing-specific LCA for 3D printing.

    Specialized for additive manufacturing processes.
    """

    def __init__(self, config: Optional[LCAConfig] = None):
        if config is None:
            config = LCAConfig(
                study_name="LEGO Brick Manufacturing LCA",
                functional_unit="1 kg of printed LEGO bricks"
            )
        super().__init__(config)

        # Manufacturing-specific parameters
        self.machine_power_kw: float = 0.5
        self.print_speed_kg_per_hour: float = 0.1
        self.material_density: float = 1.25  # kg/m³

    def model_fdm_printing(
        self,
        material_kg: float,
        print_time_hours: float,
        electricity_source: str = "grid",
        waste_rate: float = 0.05
    ):
        """Model FDM 3D printing process."""
        # Material input
        material_with_waste = material_kg * (1 + waste_rate)
        self.add_inventory_item(
            name="PLA_bioplastic",
            amount=material_with_waste,
            unit="kg",
            phase=LifeCyclePhase.MANUFACTURING,
            flow_type=FlowType.PRODUCT_INPUT
        )

        # Electricity consumption
        electricity_kwh = self.machine_power_kw * print_time_hours
        self.add_inventory_item(
            name=f"electricity_{electricity_source}",
            amount=electricity_kwh,
            unit="kWh",
            phase=LifeCyclePhase.MANUFACTURING,
            flow_type=FlowType.PRODUCT_INPUT
        )

        # Waste output
        waste_kg = material_kg * waste_rate
        self.add_inventory_item(
            name="plastic_waste",
            amount=waste_kg,
            unit="kg",
            phase=LifeCyclePhase.MANUFACTURING,
            flow_type=FlowType.WASTE_OUTPUT,
            characterization_factors={
                ImpactCategory.GWP: 0.02,  # Minor landfill emissions
                ImpactCategory.EP: 0.001
            }
        )

        # Product output
        self.add_inventory_item(
            name="printed_parts",
            amount=material_kg,
            unit="kg",
            phase=LifeCyclePhase.MANUFACTURING,
            flow_type=FlowType.PRODUCT_OUTPUT
        )

    def model_post_processing(
        self,
        parts_kg: float,
        cleaning_water_liters: float = 1.0,
        curing_electricity_kwh: float = 0.1
    ):
        """Model post-processing steps."""
        # Cleaning water
        self.add_inventory_item(
            name="tap_water",
            amount=cleaning_water_liters / 1000,  # Convert to m³
            unit="m³",
            phase=LifeCyclePhase.POST_PROCESSING,
            flow_type=FlowType.PRODUCT_INPUT,
            characterization_factors={
                ImpactCategory.WDP: 1.0
            }
        )

        # Curing electricity
        if curing_electricity_kwh > 0:
            self.add_inventory_item(
                name="electricity_grid",
                amount=curing_electricity_kwh,
                unit="kWh",
                phase=LifeCyclePhase.POST_PROCESSING,
                flow_type=FlowType.PRODUCT_INPUT
            )

        # Wastewater
        self.add_inventory_item(
            name="wastewater",
            amount=cleaning_water_liters / 1000,
            unit="m³",
            phase=LifeCyclePhase.POST_PROCESSING,
            flow_type=FlowType.ELEMENTARY_OUTPUT,
            characterization_factors={
                ImpactCategory.EP: 0.05
            }
        )

    def model_distribution(
        self,
        distance_km: float,
        weight_kg: float,
        transport_mode: str = "truck"
    ):
        """Model distribution phase."""
        # Convert to tonne-km
        tkm = weight_kg * distance_km / 1000

        self.add_inventory_item(
            name=f"{transport_mode}_transport",
            amount=tkm,
            unit="tkm",
            phase=LifeCyclePhase.DISTRIBUTION,
            flow_type=FlowType.PRODUCT_INPUT
        )

    def model_end_of_life(
        self,
        weight_kg: float,
        recycling_rate: float = 0.3,
        incineration_rate: float = 0.4
    ):
        """Model end-of-life phase."""
        landfill_rate = 1 - recycling_rate - incineration_rate

        # Recycling
        if recycling_rate > 0:
            self.add_inventory_item(
                name="recycling_plastic",
                amount=weight_kg * recycling_rate,
                unit="kg",
                phase=LifeCyclePhase.END_OF_LIFE,
                flow_type=FlowType.WASTE_OUTPUT
            )

        # Incineration
        if incineration_rate > 0:
            self.add_inventory_item(
                name="incineration_plastic",
                amount=weight_kg * incineration_rate,
                unit="kg",
                phase=LifeCyclePhase.END_OF_LIFE,
                flow_type=FlowType.WASTE_OUTPUT
            )

        # Landfill
        if landfill_rate > 0:
            self.add_inventory_item(
                name="landfill_plastic",
                amount=weight_kg * landfill_rate,
                unit="kg",
                phase=LifeCyclePhase.END_OF_LIFE,
                flow_type=FlowType.WASTE_OUTPUT
            )

    def run_full_manufacturing_lca(
        self,
        material_kg: float,
        print_time_hours: float,
        distribution_distance_km: float = 100,
        electricity_source: str = "grid"
    ) -> LCAResult:
        """Run complete manufacturing LCA."""
        # Clear previous inventory
        self.inventory = []

        # Model each phase
        self.model_fdm_printing(
            material_kg=material_kg,
            print_time_hours=print_time_hours,
            electricity_source=electricity_source
        )

        self.model_post_processing(
            parts_kg=material_kg,
            cleaning_water_liters=material_kg * 2
        )

        self.model_distribution(
            distance_km=distribution_distance_km,
            weight_kg=material_kg
        )

        self.model_end_of_life(weight_kg=material_kg)

        # Run LCA
        return self.run_lca()
