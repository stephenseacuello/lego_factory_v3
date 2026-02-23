"""
Scope 3 Emissions Tracker.

Comprehensive tracking of value chain (Scope 3) greenhouse gas
emissions per GHG Protocol Corporate Value Chain Standard.

Research Value:
- Complete Scope 3 emissions modeling
- Supply chain carbon footprint tracking
- Transportation and logistics emissions

References:
- GHG Protocol Corporate Value Chain (Scope 3) Standard
- ISO 14064-1:2018 - GHG quantification
- GLEC Framework for logistics emissions
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
from datetime import datetime, timedelta
import math


class Scope3Category(Enum):
    """
    GHG Protocol Scope 3 Categories.

    Upstream categories (1-8) and downstream categories (9-15).
    """
    # Upstream
    PURCHASED_GOODS_SERVICES = 1
    CAPITAL_GOODS = 2
    FUEL_ENERGY_ACTIVITIES = 3
    UPSTREAM_TRANSPORT = 4
    WASTE_GENERATED = 5
    BUSINESS_TRAVEL = 6
    EMPLOYEE_COMMUTING = 7
    UPSTREAM_LEASED_ASSETS = 8
    # Downstream
    DOWNSTREAM_TRANSPORT = 9
    PROCESSING_SOLD_PRODUCTS = 10
    USE_OF_SOLD_PRODUCTS = 11
    END_OF_LIFE_TREATMENT = 12
    DOWNSTREAM_LEASED_ASSETS = 13
    FRANCHISES = 14
    INVESTMENTS = 15


@dataclass
class EmissionSource:
    """Source of emissions with activity data."""

    source_id: str
    description: str
    category: Scope3Category
    activity_data: float
    activity_unit: str
    emission_factor: float
    emission_factor_unit: str
    emissions_kg_co2e: float = 0.0
    uncertainty_percent: float = 20.0
    data_quality_score: float = 3.0  # 1-5 scale
    calculation_method: str = "average-data"


@dataclass
class SupplyChainEmission:
    """Supply chain emission from purchased goods/services."""

    supplier_id: str
    supplier_name: str
    material_type: str
    quantity_kg: float
    emission_factor: float  # kg CO2e/kg
    emissions_kg: float
    country_of_origin: str = "unknown"
    transport_mode: str = "truck"
    transport_distance_km: float = 0.0
    transport_emissions_kg: float = 0.0

    @property
    def total_emissions_kg(self) -> float:
        """Total including transport."""
        return self.emissions_kg + self.transport_emissions_kg


@dataclass
class TransportEmission:
    """Transport and distribution emission."""

    transport_id: str
    origin: str
    destination: str
    distance_km: float
    weight_kg: float
    mode: str  # truck, rail, ship, air
    emission_factor: float  # kg CO2e/tonne-km
    emissions_kg: float
    is_upstream: bool = True
    carrier: str = "unknown"


@dataclass
class WasteEmission:
    """Waste treatment emission."""

    waste_type: str
    quantity_kg: float
    treatment_method: str  # landfill, recycling, incineration, composting
    emission_factor: float  # kg CO2e/kg
    emissions_kg: float
    recycling_credit_kg: float = 0.0

    @property
    def net_emissions_kg(self) -> float:
        """Net emissions after recycling credit."""
        return self.emissions_kg - self.recycling_credit_kg


@dataclass
class EmissionInventory:
    """Complete Scope 3 emission inventory."""

    period_start: datetime
    period_end: datetime
    emissions_by_category: Dict[Scope3Category, float]
    total_upstream_kg: float = 0.0
    total_downstream_kg: float = 0.0
    total_scope3_kg: float = 0.0
    data_coverage_percent: float = 0.0
    sources: List[EmissionSource] = field(default_factory=list)

    def get_category_breakdown(self) -> Dict[str, float]:
        """Get emissions by category name."""
        return {
            cat.name: value
            for cat, value in self.emissions_by_category.items()
        }


class EmissionFactorDatabase:
    """
    Database of emission factors.

    Contains emission factors for various activities, materials,
    and transport modes based on standard databases.
    """

    def __init__(self):
        self.material_factors = self._initialize_material_factors()
        self.transport_factors = self._initialize_transport_factors()
        self.waste_factors = self._initialize_waste_factors()
        self.energy_factors = self._initialize_energy_factors()

    def _initialize_material_factors(self) -> Dict[str, float]:
        """Initialize material emission factors (kg CO2e/kg)."""
        return {
            # Plastics
            "pla": 3.8,
            "abs": 4.2,
            "petg": 3.5,
            "nylon": 8.5,
            "pc": 6.0,
            "pp": 2.0,
            "pe": 1.9,
            "pvc": 2.4,
            "recycled_pla": 1.5,
            "recycled_abs": 1.8,
            # Metals
            "aluminum": 12.0,
            "steel": 2.0,
            "stainless_steel": 5.5,
            "copper": 3.5,
            "brass": 3.8,
            "titanium": 35.0,
            # Packaging
            "cardboard": 0.9,
            "paper": 1.0,
            "wood": 0.3,
            "glass": 0.9,
            # Electronics
            "pcb": 50.0,
            "battery_lithium": 150.0,
            "semiconductor": 500.0,
        }

    def _initialize_transport_factors(self) -> Dict[str, float]:
        """Initialize transport emission factors (kg CO2e/tonne-km)."""
        return {
            # Road
            "truck_small": 0.180,
            "truck_medium": 0.120,
            "truck_large": 0.080,
            "truck_average": 0.100,
            "van": 0.250,
            # Rail
            "rail_freight": 0.025,
            "rail_electric": 0.015,
            # Maritime
            "ship_container": 0.015,
            "ship_bulk": 0.008,
            "ship_tanker": 0.010,
            # Air
            "air_cargo": 0.600,
            "air_express": 0.800,
            # Multimodal
            "intermodal": 0.050,
        }

    def _initialize_waste_factors(self) -> Dict[str, Dict[str, float]]:
        """Initialize waste treatment emission factors (kg CO2e/kg)."""
        return {
            "landfill": {
                "plastic": 0.04,
                "paper": 1.50,
                "organic": 0.85,
                "metal": 0.02,
                "mixed": 0.50,
            },
            "incineration": {
                "plastic": 2.80,
                "paper": 0.05,
                "organic": 0.05,
                "metal": 0.02,
                "mixed": 1.00,
            },
            "recycling": {
                "plastic": -1.50,  # Credit (avoided virgin production)
                "paper": -0.80,
                "metal": -1.80,
                "glass": -0.30,
            },
            "composting": {
                "organic": 0.10,
                "paper": 0.15,
            },
        }

    def _initialize_energy_factors(self) -> Dict[str, float]:
        """Initialize energy emission factors (kg CO2e/kWh or unit)."""
        return {
            # Electricity by source
            "electricity_grid_us": 0.42,
            "electricity_grid_eu": 0.30,
            "electricity_grid_china": 0.55,
            "electricity_solar": 0.05,
            "electricity_wind": 0.02,
            "electricity_hydro": 0.02,
            "electricity_nuclear": 0.01,
            # Fuels
            "natural_gas_kwh": 0.18,
            "diesel_liter": 2.68,
            "gasoline_liter": 2.31,
            "lpg_liter": 1.51,
        }

    def get_material_factor(self, material: str) -> float:
        """Get emission factor for material."""
        return self.material_factors.get(material.lower(), 3.0)

    def get_transport_factor(self, mode: str) -> float:
        """Get emission factor for transport mode."""
        return self.transport_factors.get(mode.lower(), 0.100)

    def get_waste_factor(self, waste_type: str, treatment: str) -> float:
        """Get emission factor for waste treatment."""
        treatment_factors = self.waste_factors.get(treatment.lower(), {})
        return treatment_factors.get(waste_type.lower(), 0.5)


class Scope3Tracker:
    """
    Comprehensive Scope 3 emissions tracker.

    Tracks all 15 categories of Scope 3 emissions per
    GHG Protocol Corporate Value Chain Standard.

    Research Value:
    - Complete value chain emissions modeling
    - Supplier-specific carbon tracking
    - LCA integration for product carbon footprint
    """

    def __init__(self):
        self.ef_database = EmissionFactorDatabase()
        self.supply_chain_emissions: List[SupplyChainEmission] = []
        self.transport_emissions: List[TransportEmission] = []
        self.waste_emissions: List[WasteEmission] = []

    def track_purchased_material(
        self,
        supplier_id: str,
        supplier_name: str,
        material_type: str,
        quantity_kg: float,
        country_of_origin: str = "unknown",
        transport_mode: str = "truck",
        transport_distance_km: float = 500
    ) -> SupplyChainEmission:
        """
        Track emissions from purchased materials.

        Category 1: Purchased Goods and Services
        """
        # Material production emissions
        ef_material = self.ef_database.get_material_factor(material_type)
        material_emissions = quantity_kg * ef_material

        # Transport emissions
        ef_transport = self.ef_database.get_transport_factor(transport_mode)
        transport_emissions = (quantity_kg / 1000) * transport_distance_km * ef_transport

        emission = SupplyChainEmission(
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            material_type=material_type,
            quantity_kg=quantity_kg,
            emission_factor=ef_material,
            emissions_kg=material_emissions,
            country_of_origin=country_of_origin,
            transport_mode=transport_mode,
            transport_distance_km=transport_distance_km,
            transport_emissions_kg=transport_emissions
        )

        self.supply_chain_emissions.append(emission)
        return emission

    def track_transport(
        self,
        origin: str,
        destination: str,
        distance_km: float,
        weight_kg: float,
        mode: str = "truck",
        is_upstream: bool = True,
        carrier: str = "unknown"
    ) -> TransportEmission:
        """
        Track transport emissions.

        Category 4: Upstream Transportation
        Category 9: Downstream Transportation
        """
        ef = self.ef_database.get_transport_factor(mode)
        emissions = (weight_kg / 1000) * distance_km * ef

        transport_id = f"T{len(self.transport_emissions) + 1:04d}"

        emission = TransportEmission(
            transport_id=transport_id,
            origin=origin,
            destination=destination,
            distance_km=distance_km,
            weight_kg=weight_kg,
            mode=mode,
            emission_factor=ef,
            emissions_kg=emissions,
            is_upstream=is_upstream,
            carrier=carrier
        )

        self.transport_emissions.append(emission)
        return emission

    def track_waste(
        self,
        waste_type: str,
        quantity_kg: float,
        treatment_method: str = "landfill"
    ) -> WasteEmission:
        """
        Track waste treatment emissions.

        Category 5: Waste Generated in Operations
        """
        ef = self.ef_database.get_waste_factor(waste_type, treatment_method)
        emissions = quantity_kg * max(0, ef)  # Avoid negative for credits

        # Calculate recycling credit if applicable
        recycling_credit = 0.0
        if treatment_method == "recycling":
            recycling_credit = abs(quantity_kg * ef)

        emission = WasteEmission(
            waste_type=waste_type,
            quantity_kg=quantity_kg,
            treatment_method=treatment_method,
            emission_factor=ef,
            emissions_kg=emissions,
            recycling_credit_kg=recycling_credit
        )

        self.waste_emissions.append(emission)
        return emission

    def calculate_business_travel(
        self,
        mode: str,
        distance_km: float,
        passengers: int = 1
    ) -> float:
        """
        Calculate business travel emissions.

        Category 6: Business Travel
        """
        factors = {
            "car": 0.17,  # kg CO2e/km
            "train": 0.04,
            "bus": 0.08,
            "domestic_flight": 0.25,
            "short_haul_flight": 0.15,
            "long_haul_flight": 0.12,
        }

        ef = factors.get(mode.lower(), 0.17)
        return distance_km * ef * passengers

    def calculate_employee_commuting(
        self,
        employees: int,
        avg_distance_km: float,
        working_days: int = 250,
        car_fraction: float = 0.7,
        transit_fraction: float = 0.2,
        wfh_fraction: float = 0.1
    ) -> float:
        """
        Calculate employee commuting emissions.

        Category 7: Employee Commuting
        """
        # Daily commute (round trip)
        daily_distance = avg_distance_km * 2

        car_emissions = (employees * car_fraction * daily_distance *
                         working_days * 0.17)  # kg CO2e/km for car

        transit_emissions = (employees * transit_fraction * daily_distance *
                             working_days * 0.05)  # kg CO2e/km for transit

        # WFH has small emissions (electricity)
        wfh_emissions = (employees * wfh_fraction * working_days *
                         0.5)  # kg CO2e/day for home office

        return car_emissions + transit_emissions + wfh_emissions

    def estimate_product_use_emissions(
        self,
        product_lifetime_years: float,
        annual_energy_kwh: float,
        electricity_ef: float = 0.4
    ) -> float:
        """
        Estimate emissions from product use phase.

        Category 11: Use of Sold Products
        """
        total_energy = annual_energy_kwh * product_lifetime_years
        return total_energy * electricity_ef

    def estimate_end_of_life_emissions(
        self,
        product_weight_kg: float,
        material_composition: Dict[str, float],
        recycling_rate: float = 0.3
    ) -> float:
        """
        Estimate end-of-life treatment emissions.

        Category 12: End-of-Life Treatment of Sold Products
        """
        total_emissions = 0.0

        for material, fraction in material_composition.items():
            material_weight = product_weight_kg * fraction

            # Recycled portion
            recycled_weight = material_weight * recycling_rate
            recycled_ef = self.ef_database.get_waste_factor(material, "recycling")
            total_emissions += recycled_weight * recycled_ef

            # Landfilled portion
            landfill_weight = material_weight * (1 - recycling_rate)
            landfill_ef = self.ef_database.get_waste_factor(material, "landfill")
            total_emissions += landfill_weight * landfill_ef

        return max(0, total_emissions)  # Recycling credits may make this negative

    def generate_inventory(
        self,
        period_start: datetime,
        period_end: datetime,
        include_estimates: bool = True
    ) -> EmissionInventory:
        """
        Generate comprehensive Scope 3 inventory.

        Aggregates all tracked emissions by category.
        """
        emissions_by_category: Dict[Scope3Category, float] = {cat: 0.0 for cat in Scope3Category}

        # Category 1: Purchased goods
        for sc in self.supply_chain_emissions:
            emissions_by_category[Scope3Category.PURCHASED_GOODS_SERVICES] += sc.emissions_kg

        # Category 4 & 9: Transport
        for te in self.transport_emissions:
            if te.is_upstream:
                emissions_by_category[Scope3Category.UPSTREAM_TRANSPORT] += te.emissions_kg
            else:
                emissions_by_category[Scope3Category.DOWNSTREAM_TRANSPORT] += te.emissions_kg

        # Category 5: Waste
        for we in self.waste_emissions:
            emissions_by_category[Scope3Category.WASTE_GENERATED] += we.net_emissions_kg

        # Calculate totals
        upstream_cats = [Scope3Category.PURCHASED_GOODS_SERVICES, Scope3Category.CAPITAL_GOODS,
                         Scope3Category.FUEL_ENERGY_ACTIVITIES, Scope3Category.UPSTREAM_TRANSPORT,
                         Scope3Category.WASTE_GENERATED, Scope3Category.BUSINESS_TRAVEL,
                         Scope3Category.EMPLOYEE_COMMUTING, Scope3Category.UPSTREAM_LEASED_ASSETS]

        total_upstream = sum(emissions_by_category.get(cat, 0) for cat in upstream_cats)
        total_downstream = sum(emissions_by_category.values()) - total_upstream
        total_scope3 = sum(emissions_by_category.values())

        # Calculate data coverage
        categories_with_data = sum(1 for v in emissions_by_category.values() if v > 0)
        data_coverage = 100 * categories_with_data / len(Scope3Category)

        return EmissionInventory(
            period_start=period_start,
            period_end=period_end,
            emissions_by_category=emissions_by_category,
            total_upstream_kg=total_upstream,
            total_downstream_kg=total_downstream,
            total_scope3_kg=total_scope3,
            data_coverage_percent=data_coverage
        )

    def get_supplier_ranking(self) -> List[Dict[str, Any]]:
        """
        Rank suppliers by carbon intensity.

        Helps identify high-emission suppliers for engagement.
        """
        supplier_emissions: Dict[str, Dict[str, float]] = {}

        for sc in self.supply_chain_emissions:
            if sc.supplier_id not in supplier_emissions:
                supplier_emissions[sc.supplier_id] = {
                    "name": sc.supplier_name,
                    "total_emissions_kg": 0,
                    "total_quantity_kg": 0,
                }

            supplier_emissions[sc.supplier_id]["total_emissions_kg"] += sc.total_emissions_kg
            supplier_emissions[sc.supplier_id]["total_quantity_kg"] += sc.quantity_kg

        # Calculate intensity and rank
        rankings = []
        for supplier_id, data in supplier_emissions.items():
            intensity = (data["total_emissions_kg"] / data["total_quantity_kg"]
                         if data["total_quantity_kg"] > 0 else 0)

            rankings.append({
                "supplier_id": supplier_id,
                "supplier_name": data["name"],
                "total_emissions_kg": data["total_emissions_kg"],
                "total_quantity_kg": data["total_quantity_kg"],
                "carbon_intensity": intensity,
            })

        rankings.sort(key=lambda x: x["total_emissions_kg"], reverse=True)
        return rankings

    def get_reduction_opportunities(self) -> List[Dict[str, Any]]:
        """
        Identify Scope 3 reduction opportunities.

        Analyzes emission data to find high-impact reduction strategies.
        """
        opportunities = []

        # Analyze suppliers
        supplier_rankings = self.get_supplier_ranking()
        if supplier_rankings:
            top_supplier = supplier_rankings[0]
            opportunities.append({
                "category": "Supplier Engagement",
                "description": f"Engage with {top_supplier['supplier_name']} to reduce emissions",
                "potential_reduction_kg": top_supplier["total_emissions_kg"] * 0.2,
                "priority": "high",
                "actions": [
                    "Request supplier carbon data",
                    "Explore alternative low-carbon materials",
                    "Negotiate renewable energy commitments",
                ]
            })

        # Analyze transport
        transport_by_mode: Dict[str, float] = {}
        for te in self.transport_emissions:
            mode = te.mode
            transport_by_mode[mode] = transport_by_mode.get(mode, 0) + te.emissions_kg

        if transport_by_mode:
            worst_mode = max(transport_by_mode, key=transport_by_mode.get)
            if worst_mode in ["truck", "air"]:
                opportunities.append({
                    "category": "Transport Optimization",
                    "description": f"Shift from {worst_mode} to rail/ship where possible",
                    "potential_reduction_kg": transport_by_mode[worst_mode] * 0.5,
                    "priority": "medium",
                    "actions": [
                        "Map current logistics routes",
                        "Identify intermodal opportunities",
                        "Consolidate shipments",
                    ]
                })

        # Analyze waste
        waste_total = sum(we.emissions_kg for we in self.waste_emissions)
        recycling_total = sum(we.recycling_credit_kg for we in self.waste_emissions)

        if waste_total > 0:
            opportunities.append({
                "category": "Waste Reduction",
                "description": "Increase recycling and waste diversion",
                "potential_reduction_kg": waste_total * 0.3,
                "priority": "medium",
                "actions": [
                    "Implement waste segregation",
                    "Partner with recycling facilities",
                    "Design for recyclability",
                ]
            })

        return opportunities

    def export_cdp_format(self) -> Dict[str, Any]:
        """
        Export emissions in CDP (Carbon Disclosure Project) format.

        Structures data for CDP climate change questionnaire submission.
        """
        inventory = self.generate_inventory(
            datetime.now() - timedelta(days=365),
            datetime.now()
        )

        return {
            "reporting_year": datetime.now().year - 1,
            "scope_3_emissions": {
                "total_tco2e": inventory.total_scope3_kg / 1000,
                "upstream_tco2e": inventory.total_upstream_kg / 1000,
                "downstream_tco2e": inventory.total_downstream_kg / 1000,
                "by_category": {
                    cat.name: value / 1000
                    for cat, value in inventory.emissions_by_category.items()
                    if value > 0
                },
            },
            "data_quality": {
                "coverage_percent": inventory.data_coverage_percent,
                "calculation_methods": ["spend-based", "average-data", "supplier-specific"],
            },
            "verification_status": "Not verified",
        }


# Module exports
__all__ = [
    # Enums
    "Scope3Category",
    # Data classes
    "EmissionSource",
    "SupplyChainEmission",
    "TransportEmission",
    "WasteEmission",
    "EmissionInventory",
    # Classes
    "EmissionFactorDatabase",
    "Scope3Tracker",
]
