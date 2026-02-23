"""
KPI Engine - Real-Time Analytics

LegoMCP World-Class Manufacturing System v5.0
Phase 23: Real-Time Analytics & Business Intelligence

Comprehensive KPI calculation:
- OEE and TEEP
- Quality metrics (FPY, DPMO, Cpk)
- Delivery metrics (OTIF)
- Cost metrics
- Sustainability metrics
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class KPIValue:
    """A single KPI measurement."""
    kpi_id: str
    kpi_name: str
    value: float
    unit: str
    timestamp: datetime

    # Targets
    target: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None

    # Status
    status: str = "normal"  # normal, warning, critical

    def __post_init__(self):
        self._evaluate_status()

    def _evaluate_status(self) -> None:
        """Evaluate KPI status against thresholds."""
        if self.critical_threshold and self.value < self.critical_threshold:
            self.status = "critical"
        elif self.warning_threshold and self.value < self.warning_threshold:
            self.status = "warning"
        else:
            self.status = "normal"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'kpi_id': self.kpi_id,
            'kpi_name': self.kpi_name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'target': self.target,
            'status': self.status,
        }


@dataclass
class OEEBreakdown:
    """OEE calculation breakdown."""
    availability: float  # Run time / Planned time
    performance: float  # (Ideal cycle × Count) / Run time
    quality: float  # Good count / Total count
    oee: float  # A × P × Q

    # Raw data
    planned_time_min: float = 0
    run_time_min: float = 0
    ideal_cycle_time_min: float = 0
    total_count: int = 0
    good_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'availability': self.availability,
            'performance': self.performance,
            'quality': self.quality,
            'oee': self.oee,
            'planned_time_min': self.planned_time_min,
            'run_time_min': self.run_time_min,
            'total_count': self.total_count,
            'good_count': self.good_count,
        }


class KPIEngine:
    """
    KPI Calculation Engine.

    Calculates and tracks manufacturing KPIs.
    """

    # World-class targets
    WORLD_CLASS_TARGETS = {
        'oee': 85.0,
        'availability': 90.0,
        'performance': 95.0,
        'quality': 99.9,
        'fpy': 99.5,
        'otif': 98.0,
        'dpmo': 3.4,  # Six Sigma
        'inventory_turns': 20.0,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._kpi_history: Dict[str, List[KPIValue]] = {}

    def calculate_oee(
        self,
        planned_time_min: float,
        run_time_min: float,
        ideal_cycle_time_min: float,
        total_count: int,
        good_count: int,
    ) -> OEEBreakdown:
        """
        Calculate OEE (Overall Equipment Effectiveness).

        OEE = Availability × Performance × Quality
        """
        # Availability
        availability = run_time_min / planned_time_min if planned_time_min > 0 else 0

        # Performance
        ideal_run_time = ideal_cycle_time_min * total_count
        performance = ideal_run_time / run_time_min if run_time_min > 0 else 0
        performance = min(performance, 1.0)  # Cap at 100%

        # Quality
        quality = good_count / total_count if total_count > 0 else 0

        # OEE
        oee = availability * performance * quality

        result = OEEBreakdown(
            availability=availability * 100,
            performance=performance * 100,
            quality=quality * 100,
            oee=oee * 100,
            planned_time_min=planned_time_min,
            run_time_min=run_time_min,
            ideal_cycle_time_min=ideal_cycle_time_min,
            total_count=total_count,
            good_count=good_count,
        )

        self._record_kpi('oee', result.oee, '%', target=self.WORLD_CLASS_TARGETS['oee'])

        return result

    def calculate_fpy(self, total_units: int, first_pass_good: int) -> float:
        """Calculate First Pass Yield."""
        fpy = (first_pass_good / total_units * 100) if total_units > 0 else 100
        self._record_kpi('fpy', fpy, '%', target=self.WORLD_CLASS_TARGETS['fpy'])
        return fpy

    def calculate_dpmo(self, defects: int, opportunities_per_unit: int, units: int) -> float:
        """Calculate Defects Per Million Opportunities."""
        total_opportunities = opportunities_per_unit * units
        dpmo = (defects / total_opportunities * 1_000_000) if total_opportunities > 0 else 0
        self._record_kpi('dpmo', dpmo, 'DPMO', target=self.WORLD_CLASS_TARGETS['dpmo'])
        return dpmo

    def calculate_otif(self, on_time_complete: int, total_orders: int) -> float:
        """Calculate On-Time In-Full delivery."""
        otif = (on_time_complete / total_orders * 100) if total_orders > 0 else 100
        self._record_kpi('otif', otif, '%', target=self.WORLD_CLASS_TARGETS['otif'])
        return otif

    def calculate_cpk(self, mean: float, std: float, usl: float, lsl: float) -> float:
        """Calculate Process Capability Index (Cpk)."""
        if std == 0:
            return float('inf')
        cpu = (usl - mean) / (3 * std)
        cpl = (mean - lsl) / (3 * std)
        cpk = min(cpu, cpl)
        self._record_kpi('cpk', cpk, '', target=1.33)
        return cpk

    def calculate_inventory_turns(
        self,
        cogs: float,
        avg_inventory_value: float,
    ) -> float:
        """Calculate Inventory Turns."""
        turns = cogs / avg_inventory_value if avg_inventory_value > 0 else 0
        self._record_kpi('inventory_turns', turns, 'turns', target=self.WORLD_CLASS_TARGETS['inventory_turns'])
        return turns

    def _record_kpi(
        self,
        name: str,
        value: float,
        unit: str,
        target: Optional[float] = None,
    ) -> None:
        """Record a KPI value."""
        kpi = KPIValue(
            kpi_id=str(uuid4()),
            kpi_name=name,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            target=target,
            warning_threshold=target * 0.9 if target else None,
            critical_threshold=target * 0.8 if target else None,
        )

        if name not in self._kpi_history:
            self._kpi_history[name] = []
        self._kpi_history[name].append(kpi)

        # Keep last 1000 values
        if len(self._kpi_history[name]) > 1000:
            self._kpi_history[name] = self._kpi_history[name][-1000:]

    def get_kpi(self, name: str) -> Optional[KPIValue]:
        """Get latest KPI value."""
        history = self._kpi_history.get(name, [])
        return history[-1] if history else None

    def get_all_kpis(self) -> Dict[str, KPIValue]:
        """Get latest value for all KPIs."""
        return {
            name: history[-1]
            for name, history in self._kpi_history.items()
            if history
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for executive dashboard."""
        kpis = self.get_all_kpis()

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'kpis': {name: kpi.to_dict() for name, kpi in kpis.items()},
            'world_class_targets': self.WORLD_CLASS_TARGETS,
            'summary': {
                'total_kpis': len(kpis),
                'normal': sum(1 for k in kpis.values() if k.status == 'normal'),
                'warning': sum(1 for k in kpis.values() if k.status == 'warning'),
                'critical': sum(1 for k in kpis.values() if k.status == 'critical'),
            },
        }

    def get_trend(self, kpi_name: str, periods: int = 30) -> List[Dict[str, Any]]:
        """Get KPI trend over time."""
        history = self._kpi_history.get(kpi_name, [])
        return [
            {'timestamp': k.timestamp.isoformat(), 'value': k.value}
            for k in history[-periods:]
        ]
