"""
Energy Optimizer - Sustainability Service

LegoMCP World-Class Manufacturing System v5.0
Phase 19: Sustainability & Carbon Tracking

Provides energy optimization capabilities:
- Real-time energy monitoring
- Peak demand management
- Energy-aware scheduling
- Renewable energy integration
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import uuid


class EnergySource(Enum):
    """Types of energy sources."""
    GRID = "grid"
    SOLAR = "solar"
    WIND = "wind"
    BATTERY = "battery"
    GENERATOR = "generator"


class LoadPriority(Enum):
    """Priority levels for loads."""
    CRITICAL = "critical"      # Cannot be shed
    HIGH = "high"              # Prefer not to shed
    MEDIUM = "medium"          # Can be shifted
    LOW = "low"                # Can be shed if needed
    DEFERRABLE = "deferrable"  # Can run anytime


@dataclass
class EnergyLoad:
    """An energy-consuming load."""
    load_id: str
    name: str
    power_kw: float
    priority: LoadPriority
    flexible: bool = False
    min_runtime_hours: float = 0.0
    can_interrupt: bool = True
    current_state: str = "off"  # on, off, standby


@dataclass
class EnergyReading:
    """Real-time energy reading."""
    timestamp: datetime
    total_consumption_kw: float
    by_source: Dict[str, float]
    by_load: Dict[str, float]
    grid_price_per_kwh: float
    carbon_intensity_kg_per_kwh: float


@dataclass
class OptimizationResult:
    """Result of energy optimization."""
    optimization_id: str
    period_hours: float
    actions: List[Dict]
    projected_savings_kwh: float
    projected_cost_savings: float
    projected_carbon_savings_kg: float
    peak_reduction_kw: float
    renewable_utilization_pct: float
    schedule: List[Dict]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EnergyOptimizer:
    """
    Optimizes energy consumption in the manufacturing facility.

    Manages loads, integrates renewables, and minimizes costs
    while meeting production requirements.
    """

    def __init__(self):
        self.loads: Dict[str, EnergyLoad] = {}
        self.readings: List[EnergyReading] = []
        self.sources: Dict[EnergySource, Dict] = {}
        self._setup_default_loads()
        self._setup_sources()

    def _setup_default_loads(self):
        """Set up default manufacturing loads."""
        self.loads = {
            'PRINT-01': EnergyLoad(
                load_id='PRINT-01',
                name='3D Printer 1',
                power_kw=0.35,
                priority=LoadPriority.HIGH,
                flexible=False,
                can_interrupt=False,
            ),
            'PRINT-02': EnergyLoad(
                load_id='PRINT-02',
                name='3D Printer 2',
                power_kw=0.35,
                priority=LoadPriority.HIGH,
                flexible=True,
                can_interrupt=False,
            ),
            'HVAC': EnergyLoad(
                load_id='HVAC',
                name='HVAC System',
                power_kw=5.0,
                priority=LoadPriority.MEDIUM,
                flexible=True,
                can_interrupt=True,
            ),
            'LIGHTING': EnergyLoad(
                load_id='LIGHTING',
                name='Facility Lighting',
                power_kw=2.0,
                priority=LoadPriority.LOW,
                flexible=True,
                can_interrupt=True,
            ),
            'COMPRESSOR': EnergyLoad(
                load_id='COMPRESSOR',
                name='Air Compressor',
                power_kw=3.5,
                priority=LoadPriority.MEDIUM,
                flexible=True,
                min_runtime_hours=0.5,
                can_interrupt=True,
            ),
            'DRYER': EnergyLoad(
                load_id='DRYER',
                name='Filament Dryer',
                power_kw=0.5,
                priority=LoadPriority.DEFERRABLE,
                flexible=True,
                can_interrupt=True,
            ),
        }

    def _setup_sources(self):
        """Set up energy sources."""
        self.sources = {
            EnergySource.GRID: {
                'available': True,
                'capacity_kw': 50.0,
                'current_price': 0.12,
                'carbon_intensity': 0.4,
            },
            EnergySource.SOLAR: {
                'available': True,
                'capacity_kw': 10.0,
                'current_output': 0.0,
                'carbon_intensity': 0.0,
            },
            EnergySource.BATTERY: {
                'available': True,
                'capacity_kwh': 20.0,
                'current_soc': 0.8,  # State of charge
                'max_discharge_kw': 5.0,
                'carbon_intensity': 0.0,
            },
        }

    def get_current_reading(self) -> EnergyReading:
        """Get current energy reading."""
        import random

        # Simulate readings
        active_loads = {
            load_id: load.power_kw * (0.8 + random.random() * 0.4)
            for load_id, load in self.loads.items()
            if load.current_state == 'on' or random.random() > 0.3
        }

        total = sum(active_loads.values())

        # Simulate source breakdown
        solar_output = min(
            self.sources[EnergySource.SOLAR]['capacity_kw'],
            self.sources[EnergySource.SOLAR]['capacity_kw'] * random.random()
        )

        by_source = {
            'solar': min(solar_output, total),
            'grid': max(0, total - solar_output),
            'battery': 0,
        }

        reading = EnergyReading(
            timestamp=datetime.utcnow(),
            total_consumption_kw=total,
            by_source=by_source,
            by_load=active_loads,
            grid_price_per_kwh=0.10 + random.random() * 0.10,
            carbon_intensity_kg_per_kwh=0.3 + random.random() * 0.2,
        )

        self.readings.append(reading)
        return reading

    def optimize(
        self,
        horizon_hours: float = 24.0,
        objective: str = 'cost'  # 'cost', 'carbon', 'balanced'
    ) -> OptimizationResult:
        """
        Optimize energy usage over a time horizon.

        Args:
            horizon_hours: Optimization horizon
            objective: Optimization objective

        Returns:
            Optimization result with recommended actions
        """
        import random

        actions = []
        schedule = []

        # Get current state
        current = self.get_current_reading()

        # Identify optimization opportunities
        if current.grid_price_per_kwh > 0.15:
            # High price period - shed deferrable loads
            for load_id, load in self.loads.items():
                if load.priority == LoadPriority.DEFERRABLE and load.current_state == 'on':
                    actions.append({
                        'action': 'defer',
                        'load_id': load_id,
                        'reason': 'High grid price',
                        'savings_per_hour': load.power_kw * current.grid_price_per_kwh,
                    })

        # Peak shaving opportunities
        if current.total_consumption_kw > 10.0:
            # Use battery to reduce peak
            battery = self.sources[EnergySource.BATTERY]
            if battery['current_soc'] > 0.3:
                discharge = min(
                    battery['max_discharge_kw'],
                    current.total_consumption_kw - 10.0
                )
                actions.append({
                    'action': 'battery_discharge',
                    'power_kw': discharge,
                    'duration_hours': 1.0,
                    'reason': 'Peak shaving',
                })

        # Solar charging opportunity
        solar = self.sources[EnergySource.SOLAR]
        if current.by_source.get('solar', 0) > current.total_consumption_kw:
            excess = current.by_source['solar'] - current.total_consumption_kw
            actions.append({
                'action': 'battery_charge',
                'power_kw': min(excess, 5.0),
                'reason': 'Excess solar',
            })

        # Generate schedule
        for hour in range(int(horizon_hours)):
            hour_time = datetime.utcnow() + timedelta(hours=hour)
            is_peak = 9 <= hour_time.hour <= 17

            schedule.append({
                'hour': hour,
                'timestamp': hour_time.isoformat(),
                'expected_load_kw': 8.0 if is_peak else 4.0,
                'solar_forecast_kw': 8.0 if 10 <= hour_time.hour <= 14 else 0,
                'grid_price_forecast': 0.18 if is_peak else 0.10,
                'recommended_battery': 'discharge' if is_peak else 'charge',
            })

        # Calculate projected savings
        savings_kwh = len(actions) * 2.0  # Rough estimate
        cost_savings = savings_kwh * 0.15
        carbon_savings = savings_kwh * 0.4

        return OptimizationResult(
            optimization_id=str(uuid.uuid4()),
            period_hours=horizon_hours,
            actions=actions,
            projected_savings_kwh=savings_kwh,
            projected_cost_savings=cost_savings,
            projected_carbon_savings_kg=carbon_savings,
            peak_reduction_kw=2.0 if actions else 0,
            renewable_utilization_pct=current.by_source.get('solar', 0) / max(1, current.total_consumption_kw) * 100,
            schedule=schedule,
        )

    def get_energy_dashboard_data(self) -> Dict:
        """Get data for energy dashboard."""
        current = self.get_current_reading()

        # Calculate daily totals (simulated)
        import random
        daily_kwh = sum(
            load.power_kw * random.uniform(4, 12)
            for load in self.loads.values()
        )

        return {
            'current': {
                'total_kw': current.total_consumption_kw,
                'by_source': current.by_source,
                'grid_price': current.grid_price_per_kwh,
                'carbon_intensity': current.carbon_intensity_kg_per_kwh,
            },
            'daily': {
                'consumption_kwh': daily_kwh,
                'cost': daily_kwh * 0.12,
                'carbon_kg': daily_kwh * 0.4,
                'renewable_pct': random.uniform(20, 40),
            },
            'sources': {
                source.value: info
                for source, info in self.sources.items()
            },
            'loads': [
                {
                    'id': load.load_id,
                    'name': load.name,
                    'power_kw': load.power_kw,
                    'priority': load.priority.value,
                }
                for load in self.loads.values()
            ],
        }

    def set_load_state(self, load_id: str, state: str) -> bool:
        """Set the state of a load."""
        load = self.loads.get(load_id)
        if load:
            load.current_state = state
            return True
        return False


# Singleton instance
_energy_optimizer: Optional[EnergyOptimizer] = None


def get_energy_optimizer() -> EnergyOptimizer:
    """Get or create the energy optimizer instance."""
    global _energy_optimizer
    if _energy_optimizer is None:
        _energy_optimizer = EnergyOptimizer()
    return _energy_optimizer
