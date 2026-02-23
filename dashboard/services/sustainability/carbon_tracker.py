"""
Carbon Tracker - Sustainability and Carbon Footprint

LegoMCP World-Class Manufacturing System v5.0
Phase 19: Sustainability & Carbon Tracking

ISO 14001 environmental management:
- CO2 tracking per unit
- Energy consumption optimization
- Scope 1/2/3 emissions
- Circular economy metrics
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class CarbonFootprint:
    """Carbon footprint for a production run."""
    footprint_id: str
    part_id: str
    quantity: int
    timestamp: datetime

    # Scope 1: Direct emissions (on-site fuel combustion)
    scope_1_kg: float = 0.0

    # Scope 2: Indirect emissions (electricity, heating)
    scope_2_kg: float = 0.0

    # Scope 3: Value chain emissions
    scope_3_kg: float = 0.0

    @property
    def total_co2e(self) -> float:
        """Total CO2 equivalent."""
        return self.scope_1_kg + self.scope_2_kg + self.scope_3_kg

    @property
    def co2e_per_unit(self) -> float:
        """CO2e per unit produced."""
        return self.total_co2e / self.quantity if self.quantity > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'footprint_id': self.footprint_id,
            'part_id': self.part_id,
            'quantity': self.quantity,
            'timestamp': self.timestamp.isoformat(),
            'scope_1_kg': self.scope_1_kg,
            'scope_2_kg': self.scope_2_kg,
            'scope_3_kg': self.scope_3_kg,
            'total_co2e': self.total_co2e,
            'co2e_per_unit': self.co2e_per_unit,
        }


@dataclass
class EnergyConsumption:
    """Energy consumption record."""
    record_id: str
    work_center_id: str
    timestamp: datetime

    # Energy usage
    electricity_kwh: float = 0.0
    natural_gas_m3: float = 0.0

    # Duration
    duration_hours: float = 0.0

    # Production
    parts_produced: int = 0

    @property
    def kwh_per_unit(self) -> float:
        """Energy per unit."""
        return self.electricity_kwh / self.parts_produced if self.parts_produced > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'record_id': self.record_id,
            'work_center_id': self.work_center_id,
            'timestamp': self.timestamp.isoformat(),
            'electricity_kwh': self.electricity_kwh,
            'duration_hours': self.duration_hours,
            'parts_produced': self.parts_produced,
            'kwh_per_unit': self.kwh_per_unit,
        }


@dataclass
class MaterialLifecycle:
    """Material lifecycle for circular economy."""
    lifecycle_id: str
    part_id: str
    timestamp: datetime

    # Material usage (kg)
    virgin_material_kg: float = 0.0
    recycled_material_kg: float = 0.0

    # Output
    recyclable_output_kg: float = 0.0
    waste_kg: float = 0.0

    @property
    def recycled_content_percent(self) -> float:
        """Percentage of recycled content."""
        total = self.virgin_material_kg + self.recycled_material_kg
        return (self.recycled_material_kg / total * 100) if total > 0 else 0

    @property
    def circularity_index(self) -> float:
        """Circularity index (0-1, higher = more circular)."""
        total_output = self.recyclable_output_kg + self.waste_kg
        if total_output == 0:
            return 0
        recyclable_ratio = self.recyclable_output_kg / total_output
        recycled_ratio = self.recycled_content_percent / 100
        return (recyclable_ratio + recycled_ratio) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lifecycle_id': self.lifecycle_id,
            'part_id': self.part_id,
            'virgin_material_kg': self.virgin_material_kg,
            'recycled_material_kg': self.recycled_material_kg,
            'recyclable_output_kg': self.recyclable_output_kg,
            'waste_kg': self.waste_kg,
            'recycled_content_percent': self.recycled_content_percent,
            'circularity_index': self.circularity_index,
        }


class CarbonTracker:
    """
    Carbon Footprint Tracking Service.

    Tracks emissions, energy, and sustainability metrics.
    """

    # Emission factors (kg CO2e per unit)
    EMISSION_FACTORS = {
        'electricity_kwh': 0.5,  # Varies by grid mix
        'natural_gas_m3': 2.0,
        'pla_kg': 2.1,  # PLA filament
        'abs_kg': 3.5,  # ABS filament
        'petg_kg': 2.8,  # PETG filament
        'transport_km': 0.1,  # Per kg-km
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Storage
        self._footprints: Dict[str, CarbonFootprint] = {}
        self._energy_records: Dict[str, EnergyConsumption] = {}
        self._lifecycle_records: Dict[str, MaterialLifecycle] = {}

        # Totals by period
        self._daily_totals: Dict[str, Dict[str, float]] = {}

    def calculate_production_footprint(
        self,
        part_id: str,
        quantity: int,
        material_kg: float,
        material_type: str,
        electricity_kwh: float,
        transport_km: float = 0,
    ) -> CarbonFootprint:
        """
        Calculate carbon footprint for a production run.

        Args:
            part_id: Part produced
            quantity: Quantity produced
            material_kg: Material used (kg)
            material_type: Type of material (pla, abs, petg)
            electricity_kwh: Electricity consumed
            transport_km: Transport distance (optional)

        Returns:
            CarbonFootprint record
        """
        footprint = CarbonFootprint(
            footprint_id=str(uuid4()),
            part_id=part_id,
            quantity=quantity,
            timestamp=datetime.utcnow(),
        )

        # Scope 2: Electricity
        footprint.scope_2_kg = (
            electricity_kwh * self.EMISSION_FACTORS['electricity_kwh']
        )

        # Scope 3: Materials and transport
        material_factor = self.EMISSION_FACTORS.get(f'{material_type}_kg', 2.5)
        footprint.scope_3_kg = material_kg * material_factor

        if transport_km > 0:
            footprint.scope_3_kg += material_kg * transport_km * self.EMISSION_FACTORS['transport_km']

        self._footprints[footprint.footprint_id] = footprint

        # Update daily totals
        today = date.today().isoformat()
        if today not in self._daily_totals:
            self._daily_totals[today] = {'total_co2e': 0, 'units': 0}
        self._daily_totals[today]['total_co2e'] += footprint.total_co2e
        self._daily_totals[today]['units'] += quantity

        logger.info(f"Carbon footprint: {footprint.total_co2e:.2f} kg CO2e for {quantity} units")

        return footprint

    def record_energy(
        self,
        work_center_id: str,
        electricity_kwh: float,
        duration_hours: float,
        parts_produced: int,
    ) -> EnergyConsumption:
        """Record energy consumption."""
        record = EnergyConsumption(
            record_id=str(uuid4()),
            work_center_id=work_center_id,
            timestamp=datetime.utcnow(),
            electricity_kwh=electricity_kwh,
            duration_hours=duration_hours,
            parts_produced=parts_produced,
        )

        self._energy_records[record.record_id] = record
        return record

    def record_material_lifecycle(
        self,
        part_id: str,
        virgin_kg: float,
        recycled_kg: float,
        recyclable_output_kg: float,
        waste_kg: float,
    ) -> MaterialLifecycle:
        """Record material lifecycle data."""
        record = MaterialLifecycle(
            lifecycle_id=str(uuid4()),
            part_id=part_id,
            timestamp=datetime.utcnow(),
            virgin_material_kg=virgin_kg,
            recycled_material_kg=recycled_kg,
            recyclable_output_kg=recyclable_output_kg,
            waste_kg=waste_kg,
        )

        self._lifecycle_records[record.lifecycle_id] = record
        return record

    def get_daily_summary(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Get daily carbon summary."""
        if target_date is None:
            target_date = date.today()

        date_str = target_date.isoformat()
        totals = self._daily_totals.get(date_str, {'total_co2e': 0, 'units': 0})

        return {
            'date': date_str,
            'total_co2e_kg': totals['total_co2e'],
            'total_units': totals['units'],
            'co2e_per_unit': (
                totals['total_co2e'] / totals['units']
                if totals['units'] > 0 else 0
            ),
        }

    def get_part_footprint(self, part_id: str) -> Dict[str, Any]:
        """Get average footprint for a part."""
        footprints = [
            f for f in self._footprints.values()
            if f.part_id == part_id
        ]

        if not footprints:
            return {'part_id': part_id, 'records': 0}

        total_co2e = sum(f.total_co2e for f in footprints)
        total_units = sum(f.quantity for f in footprints)

        return {
            'part_id': part_id,
            'records': len(footprints),
            'total_co2e_kg': total_co2e,
            'total_units': total_units,
            'avg_co2e_per_unit': total_co2e / total_units if total_units > 0 else 0,
        }

    def get_sustainability_kpis(self) -> Dict[str, Any]:
        """Get sustainability KPIs."""
        total_co2e = sum(f.total_co2e for f in self._footprints.values())
        total_units = sum(f.quantity for f in self._footprints.values())

        total_energy = sum(e.electricity_kwh for e in self._energy_records.values())
        total_produced = sum(e.parts_produced for e in self._energy_records.values())

        lifecycle = list(self._lifecycle_records.values())
        avg_circularity = (
            sum(l.circularity_index for l in lifecycle) / len(lifecycle)
            if lifecycle else 0
        )

        return {
            'carbon': {
                'total_co2e_kg': total_co2e,
                'total_units': total_units,
                'co2e_per_unit': total_co2e / total_units if total_units > 0 else 0,
            },
            'energy': {
                'total_kwh': total_energy,
                'kwh_per_unit': total_energy / total_produced if total_produced > 0 else 0,
            },
            'circularity': {
                'records': len(lifecycle),
                'avg_circularity_index': avg_circularity,
            },
            'net_zero_progress': self._calculate_net_zero_progress(total_co2e),
        }

    def _calculate_net_zero_progress(self, total_co2e: float) -> Dict[str, Any]:
        """Calculate progress toward net zero."""
        # Example target: 1000 kg CO2e per month
        monthly_target = self.config.get('monthly_target_kg', 1000)
        current_month = total_co2e

        return {
            'target_kg': monthly_target,
            'current_kg': current_month,
            'percent_of_target': (current_month / monthly_target * 100) if monthly_target > 0 else 0,
            'on_track': current_month <= monthly_target,
        }

    def get_emission_reduction_opportunities(self) -> List[Dict[str, Any]]:
        """Identify emission reduction opportunities."""
        opportunities = []

        # Analyze energy by work center
        by_wc: Dict[str, List[EnergyConsumption]] = {}
        for record in self._energy_records.values():
            if record.work_center_id not in by_wc:
                by_wc[record.work_center_id] = []
            by_wc[record.work_center_id].append(record)

        for wc_id, records in by_wc.items():
            avg_kwh = sum(r.kwh_per_unit for r in records) / len(records)
            if avg_kwh > 0.5:  # High energy threshold
                opportunities.append({
                    'type': 'energy_efficiency',
                    'work_center_id': wc_id,
                    'current_kwh_per_unit': avg_kwh,
                    'potential_savings_percent': 20,
                    'action': 'Optimize process parameters to reduce energy consumption',
                })

        # Check material circularity
        for lifecycle in self._lifecycle_records.values():
            if lifecycle.circularity_index < 0.3:
                opportunities.append({
                    'type': 'circularity',
                    'part_id': lifecycle.part_id,
                    'current_index': lifecycle.circularity_index,
                    'action': 'Increase recycled content or improve recyclability',
                })

        return opportunities


# Singleton instance
_carbon_tracker: Optional[CarbonTracker] = None


def get_carbon_tracker() -> CarbonTracker:
    """Get singleton CarbonTracker instance."""
    global _carbon_tracker
    if _carbon_tracker is None:
        _carbon_tracker = CarbonTracker()
    return _carbon_tracker
