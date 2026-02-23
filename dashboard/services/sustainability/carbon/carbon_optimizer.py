"""
Carbon Optimizer for Manufacturing.

Implements carbon-aware production scheduling that minimizes
greenhouse gas emissions while meeting production targets.

Research Value:
- Novel carbon-aware scheduling algorithm
- Real-time grid carbon intensity integration
- Multi-objective optimization with GHG constraints

References:
- GHG Protocol Corporate Standard
- ISO 14064-1:2018 - GHG quantification and reporting
- Science Based Targets initiative (SBTi) methodology
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum, auto
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import math
import random


class EmissionScope(Enum):
    """GHG Protocol emission scopes."""
    SCOPE_1 = auto()  # Direct emissions (on-site fuel combustion)
    SCOPE_2_LOCATION = auto()  # Indirect - location-based electricity
    SCOPE_2_MARKET = auto()  # Indirect - market-based electricity
    SCOPE_3_UPSTREAM = auto()  # Value chain - upstream
    SCOPE_3_DOWNSTREAM = auto()  # Value chain - downstream


class EmissionCategory(Enum):
    """Detailed emission categories."""
    # Scope 1
    STATIONARY_COMBUSTION = auto()
    MOBILE_COMBUSTION = auto()
    PROCESS_EMISSIONS = auto()
    FUGITIVE_EMISSIONS = auto()
    # Scope 2
    PURCHASED_ELECTRICITY = auto()
    PURCHASED_HEAT = auto()
    PURCHASED_COOLING = auto()
    # Scope 3
    PURCHASED_GOODS = auto()
    TRANSPORTATION = auto()
    WASTE = auto()
    EMPLOYEE_COMMUTING = auto()
    BUSINESS_TRAVEL = auto()


@dataclass
class CarbonIntensity:
    """Carbon intensity at a specific time."""

    timestamp: datetime
    intensity_gco2_per_kwh: float
    forecast: bool = False
    renewable_fraction: float = 0.0
    grid_region: str = "default"

    @property
    def is_low_carbon(self) -> bool:
        """Check if current intensity is low carbon (<100g/kWh)."""
        return self.intensity_gco2_per_kwh < 100.0

    @property
    def is_very_low_carbon(self) -> bool:
        """Check if current intensity is very low (<50g/kWh)."""
        return self.intensity_gco2_per_kwh < 50.0


@dataclass
class EmissionFactor:
    """Emission factor for specific activity."""

    activity: str
    value: float  # kg CO2e per unit
    unit: str
    scope: EmissionScope
    source: str = "Default"
    uncertainty: float = 0.1
    gwp_ar: str = "AR6"  # IPCC Assessment Report version


@dataclass
class ProductionJob:
    """Production job with energy requirements."""

    job_id: str
    product_name: str
    energy_kwh: float
    duration_hours: float
    deadline: Optional[datetime] = None
    priority: int = 1
    can_interrupt: bool = True
    min_duration_hours: float = 0.5


@dataclass
class ScheduledJob:
    """Scheduled job with timing and emissions."""

    job: ProductionJob
    start_time: datetime
    end_time: datetime
    carbon_emissions_kg: float
    energy_source_mix: Dict[str, float] = field(default_factory=dict)
    average_intensity: float = 0.0


@dataclass
class ProductionSchedule:
    """Complete production schedule."""

    jobs: List[ScheduledJob]
    total_emissions_kg: float
    total_energy_kwh: float
    renewable_fraction: float
    schedule_start: datetime
    schedule_end: datetime
    optimization_score: float = 0.0

    def get_hourly_emissions(self) -> Dict[datetime, float]:
        """Get emissions by hour."""
        hourly = {}

        for scheduled_job in self.jobs:
            current = scheduled_job.start_time
            while current < scheduled_job.end_time:
                hour_start = current.replace(minute=0, second=0, microsecond=0)
                if hour_start not in hourly:
                    hourly[hour_start] = 0.0

                # Calculate fraction of job in this hour
                hour_end = hour_start + timedelta(hours=1)
                overlap_start = max(current, scheduled_job.start_time)
                overlap_end = min(hour_end, scheduled_job.end_time)
                fraction = (overlap_end - overlap_start).total_seconds() / 3600.0

                job_duration = (scheduled_job.end_time - scheduled_job.start_time).total_seconds() / 3600.0
                if job_duration > 0:
                    hourly[hour_start] += scheduled_job.carbon_emissions_kg * (fraction / job_duration)

                current = hour_end

        return hourly


@dataclass
class CarbonConfig:
    """Configuration for carbon optimizer."""

    planning_horizon_hours: int = 24
    time_resolution_minutes: int = 15
    target_reduction_percent: float = 30.0
    max_delay_hours: float = 4.0
    renewable_priority: bool = True
    allow_carbon_offset: bool = True
    offset_cost_per_ton: float = 50.0


@dataclass
class CarbonResult:
    """Carbon optimization result."""

    schedule: ProductionSchedule
    baseline_emissions_kg: float
    optimized_emissions_kg: float
    reduction_percent: float
    carbon_cost_savings: float
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


class GridCarbonForecast:
    """
    Grid carbon intensity forecasting.

    Simulates real-time and forecast carbon intensity data
    that would come from grid operators or carbon APIs.
    """

    def __init__(self, base_intensity: float = 400.0, region: str = "default"):
        self.base_intensity = base_intensity
        self.region = region

        # Regional baseline intensities (g CO2/kWh)
        self.regional_baselines = {
            "california": 200.0,
            "texas": 380.0,
            "germany": 350.0,
            "france": 60.0,  # Nuclear-dominated
            "china_north": 750.0,
            "china_south": 500.0,
            "india": 700.0,
            "uk": 250.0,
            "australia": 650.0,
            "nordic": 30.0,  # Hydro-dominated
            "default": 400.0,
        }

        self.base_intensity = self.regional_baselines.get(region, 400.0)

    def get_current_intensity(self) -> CarbonIntensity:
        """Get current grid carbon intensity."""
        now = datetime.now()
        intensity = self._calculate_intensity(now)

        return CarbonIntensity(
            timestamp=now,
            intensity_gco2_per_kwh=intensity,
            forecast=False,
            renewable_fraction=self._estimate_renewable_fraction(intensity),
            grid_region=self.region
        )

    def get_forecast(
        self,
        hours_ahead: int = 24,
        resolution_minutes: int = 15
    ) -> List[CarbonIntensity]:
        """Get carbon intensity forecast."""
        forecast = []
        now = datetime.now()
        intervals = (hours_ahead * 60) // resolution_minutes

        for i in range(intervals):
            timestamp = now + timedelta(minutes=i * resolution_minutes)
            intensity = self._calculate_intensity(timestamp)

            # Add forecast uncertainty
            uncertainty = 0.05 + (i * resolution_minutes / 60) * 0.01
            intensity *= (1 + random.gauss(0, uncertainty))

            forecast.append(CarbonIntensity(
                timestamp=timestamp,
                intensity_gco2_per_kwh=max(20, intensity),
                forecast=True,
                renewable_fraction=self._estimate_renewable_fraction(intensity),
                grid_region=self.region
            ))

        return forecast

    def _calculate_intensity(self, timestamp: datetime) -> float:
        """Calculate carbon intensity for given timestamp."""
        hour = timestamp.hour

        # Daily pattern (higher during peak demand)
        if 6 <= hour < 9:
            # Morning ramp-up
            daily_factor = 1.1
        elif 9 <= hour < 17:
            # Daytime (solar helps)
            daily_factor = 0.85
        elif 17 <= hour < 21:
            # Evening peak
            daily_factor = 1.25
        else:
            # Nighttime (baseload)
            daily_factor = 0.95

        # Weekly pattern (lower on weekends)
        weekday = timestamp.weekday()
        if weekday >= 5:  # Weekend
            weekly_factor = 0.85
        else:
            weekly_factor = 1.0

        # Seasonal pattern
        month = timestamp.month
        if month in [12, 1, 2]:  # Winter (heating demand)
            seasonal_factor = 1.15
        elif month in [6, 7, 8]:  # Summer (cooling/solar)
            seasonal_factor = 0.9
        else:
            seasonal_factor = 1.0

        intensity = self.base_intensity * daily_factor * weekly_factor * seasonal_factor
        return intensity

    def _estimate_renewable_fraction(self, intensity: float) -> float:
        """Estimate renewable fraction from intensity."""
        # Simple inverse relationship
        max_intensity = 800.0  # Coal-dominated grid
        min_intensity = 20.0  # Near 100% renewable

        if intensity <= min_intensity:
            return 0.95
        elif intensity >= max_intensity:
            return 0.05
        else:
            return 0.95 - 0.9 * (intensity - min_intensity) / (max_intensity - min_intensity)


class CarbonOptimizer:
    """
    Carbon-aware production scheduler.

    Optimizes production scheduling to minimize carbon emissions
    by shifting flexible loads to low-carbon periods.

    Research Value:
    - Novel carbon-aware scheduling algorithm
    - Integration of grid carbon forecasts
    - Multi-objective optimization balancing carbon/cost/timing
    """

    def __init__(self, config: Optional[CarbonConfig] = None):
        self.config = config or CarbonConfig()
        self.grid_forecast = GridCarbonForecast()
        self.emission_factors = self._initialize_emission_factors()

    def _initialize_emission_factors(self) -> Dict[str, EmissionFactor]:
        """Initialize emission factors for various activities."""
        return {
            "electricity_grid": EmissionFactor(
                activity="Grid Electricity",
                value=0.4,  # kg CO2e/kWh (default)
                unit="kWh",
                scope=EmissionScope.SCOPE_2_LOCATION,
                source="EPA eGRID"
            ),
            "natural_gas": EmissionFactor(
                activity="Natural Gas Combustion",
                value=2.0,  # kg CO2e/m³
                unit="m³",
                scope=EmissionScope.SCOPE_1,
                source="EPA"
            ),
            "diesel": EmissionFactor(
                activity="Diesel Combustion",
                value=2.68,  # kg CO2e/L
                unit="L",
                scope=EmissionScope.SCOPE_1,
                source="EPA"
            ),
            "pla_production": EmissionFactor(
                activity="PLA Production",
                value=3.8,  # kg CO2e/kg
                unit="kg",
                scope=EmissionScope.SCOPE_3_UPSTREAM,
                source="Ecoinvent"
            ),
            "abs_production": EmissionFactor(
                activity="ABS Production",
                value=4.2,
                unit="kg",
                scope=EmissionScope.SCOPE_3_UPSTREAM,
                source="Ecoinvent"
            ),
        }

    def optimize_schedule(
        self,
        jobs: List[ProductionJob],
        start_time: Optional[datetime] = None
    ) -> CarbonResult:
        """
        Optimize production schedule for minimum carbon emissions.

        Args:
            jobs: List of production jobs to schedule
            start_time: Schedule start time (default: now)

        Returns:
            Optimized schedule with carbon analysis
        """
        if start_time is None:
            start_time = datetime.now()

        # Get carbon intensity forecast
        forecast = self.grid_forecast.get_forecast(
            hours_ahead=self.config.planning_horizon_hours,
            resolution_minutes=self.config.time_resolution_minutes
        )

        # Calculate baseline (FIFO scheduling)
        baseline_schedule = self._schedule_fifo(jobs, start_time, forecast)
        baseline_emissions = baseline_schedule.total_emissions_kg

        # Optimize schedule
        optimized_schedule = self._optimize_schedule(jobs, start_time, forecast)

        # Calculate reduction
        optimized_emissions = optimized_schedule.total_emissions_kg
        reduction_percent = 100 * (1 - optimized_emissions / baseline_emissions) if baseline_emissions > 0 else 0

        # Generate recommendations
        recommendations = self._generate_recommendations(
            baseline_schedule,
            optimized_schedule,
            forecast
        )

        # Calculate carbon cost savings
        carbon_price = self.config.offset_cost_per_ton  # $/ton CO2
        savings = (baseline_emissions - optimized_emissions) / 1000 * carbon_price

        return CarbonResult(
            schedule=optimized_schedule,
            baseline_emissions_kg=baseline_emissions,
            optimized_emissions_kg=optimized_emissions,
            reduction_percent=reduction_percent,
            carbon_cost_savings=savings,
            recommendations=recommendations
        )

    def _schedule_fifo(
        self,
        jobs: List[ProductionJob],
        start_time: datetime,
        forecast: List[CarbonIntensity]
    ) -> ProductionSchedule:
        """Schedule jobs in FIFO order (baseline)."""
        scheduled_jobs = []
        current_time = start_time
        total_emissions = 0.0
        total_energy = 0.0
        total_renewable_energy = 0.0

        for job in jobs:
            end_time = current_time + timedelta(hours=job.duration_hours)

            # Calculate emissions for this time period
            emissions, avg_intensity, renewable_frac = self._calculate_job_emissions(
                job, current_time, end_time, forecast
            )

            scheduled_jobs.append(ScheduledJob(
                job=job,
                start_time=current_time,
                end_time=end_time,
                carbon_emissions_kg=emissions,
                average_intensity=avg_intensity,
                energy_source_mix={"renewable": renewable_frac, "fossil": 1 - renewable_frac}
            ))

            total_emissions += emissions
            total_energy += job.energy_kwh
            total_renewable_energy += job.energy_kwh * renewable_frac
            current_time = end_time

        renewable_fraction = total_renewable_energy / total_energy if total_energy > 0 else 0

        return ProductionSchedule(
            jobs=scheduled_jobs,
            total_emissions_kg=total_emissions,
            total_energy_kwh=total_energy,
            renewable_fraction=renewable_fraction,
            schedule_start=start_time,
            schedule_end=current_time
        )

    def _optimize_schedule(
        self,
        jobs: List[ProductionJob],
        start_time: datetime,
        forecast: List[CarbonIntensity]
    ) -> ProductionSchedule:
        """
        Optimize schedule to minimize carbon emissions.

        Uses a greedy heuristic that schedules high-energy jobs
        during low-carbon periods.
        """
        # Identify low-carbon windows
        low_carbon_windows = self._find_low_carbon_windows(forecast)

        # Sort jobs by energy consumption (highest first)
        sorted_jobs = sorted(jobs, key=lambda j: j.energy_kwh, reverse=True)

        # Track scheduled time slots
        scheduled_jobs = []
        scheduled_slots: List[Tuple[datetime, datetime]] = []

        for job in sorted_jobs:
            best_start = None
            best_emissions = float('inf')
            best_end = None

            # Check each potential start time
            for window_start, window_end in low_carbon_windows:
                # Check if job fits in window
                potential_start = max(start_time, window_start)
                potential_end = potential_start + timedelta(hours=job.duration_hours)

                # Check deadline
                if job.deadline and potential_end > job.deadline:
                    continue

                # Check max delay
                max_start = start_time + timedelta(hours=self.config.max_delay_hours)
                if potential_start > max_start:
                    break

                # Check for conflicts with already scheduled jobs
                conflict = False
                for slot_start, slot_end in scheduled_slots:
                    if (potential_start < slot_end and potential_end > slot_start):
                        conflict = True
                        break

                if conflict:
                    continue

                # Calculate emissions
                emissions, _, _ = self._calculate_job_emissions(
                    job, potential_start, potential_end, forecast
                )

                if emissions < best_emissions:
                    best_emissions = emissions
                    best_start = potential_start
                    best_end = potential_end

            # Fallback to earliest available slot if no low-carbon window found
            if best_start is None:
                best_start = start_time
                for slot_start, slot_end in sorted(scheduled_slots):
                    if best_start < slot_end:
                        best_start = slot_end
                best_end = best_start + timedelta(hours=job.duration_hours)
                best_emissions, _, _ = self._calculate_job_emissions(
                    job, best_start, best_end, forecast
                )

            # Schedule the job
            _, avg_intensity, renewable_frac = self._calculate_job_emissions(
                job, best_start, best_end, forecast
            )

            scheduled_jobs.append(ScheduledJob(
                job=job,
                start_time=best_start,
                end_time=best_end,
                carbon_emissions_kg=best_emissions,
                average_intensity=avg_intensity,
                energy_source_mix={"renewable": renewable_frac, "fossil": 1 - renewable_frac}
            ))

            scheduled_slots.append((best_start, best_end))

        # Sort by start time
        scheduled_jobs.sort(key=lambda x: x.start_time)

        # Calculate totals
        total_emissions = sum(j.carbon_emissions_kg for j in scheduled_jobs)
        total_energy = sum(j.job.energy_kwh for j in scheduled_jobs)
        total_renewable = sum(j.job.energy_kwh * j.energy_source_mix.get("renewable", 0)
                              for j in scheduled_jobs)
        renewable_fraction = total_renewable / total_energy if total_energy > 0 else 0

        schedule_end = max(j.end_time for j in scheduled_jobs) if scheduled_jobs else start_time

        return ProductionSchedule(
            jobs=scheduled_jobs,
            total_emissions_kg=total_emissions,
            total_energy_kwh=total_energy,
            renewable_fraction=renewable_fraction,
            schedule_start=start_time,
            schedule_end=schedule_end,
            optimization_score=1 - (total_emissions / (total_energy * 0.5)) if total_energy > 0 else 0
        )

    def _find_low_carbon_windows(
        self,
        forecast: List[CarbonIntensity]
    ) -> List[Tuple[datetime, datetime]]:
        """Find time windows with low carbon intensity."""
        if not forecast:
            return []

        # Calculate threshold (e.g., 25th percentile)
        intensities = [f.intensity_gco2_per_kwh for f in forecast]
        intensities.sort()
        threshold = intensities[len(intensities) // 4]

        windows = []
        window_start = None

        for f in forecast:
            if f.intensity_gco2_per_kwh <= threshold:
                if window_start is None:
                    window_start = f.timestamp
            else:
                if window_start is not None:
                    windows.append((window_start, f.timestamp))
                    window_start = None

        # Handle final window
        if window_start is not None:
            windows.append((window_start, forecast[-1].timestamp + timedelta(minutes=15)))

        return windows

    def _calculate_job_emissions(
        self,
        job: ProductionJob,
        start_time: datetime,
        end_time: datetime,
        forecast: List[CarbonIntensity]
    ) -> Tuple[float, float, float]:
        """Calculate emissions for a job during specified time period."""
        total_emissions = 0.0
        total_intensity = 0.0
        total_renewable = 0.0
        intervals = 0

        current = start_time
        interval = timedelta(minutes=self.config.time_resolution_minutes)

        while current < end_time:
            # Find matching forecast
            intensity_value = self.grid_forecast.base_intensity  # Default
            renewable_frac = 0.2  # Default

            for f in forecast:
                if f.timestamp <= current < f.timestamp + interval:
                    intensity_value = f.intensity_gco2_per_kwh
                    renewable_frac = f.renewable_fraction
                    break

            # Calculate energy for this interval
            interval_fraction = min(
                (interval.total_seconds() / 3600),
                (end_time - current).total_seconds() / 3600
            ) / job.duration_hours

            interval_energy = job.energy_kwh * interval_fraction
            interval_emissions = interval_energy * intensity_value / 1000  # Convert g to kg

            total_emissions += interval_emissions
            total_intensity += intensity_value
            total_renewable += renewable_frac
            intervals += 1

            current += interval

        avg_intensity = total_intensity / intervals if intervals > 0 else 0
        avg_renewable = total_renewable / intervals if intervals > 0 else 0

        return total_emissions, avg_intensity, avg_renewable

    def _generate_recommendations(
        self,
        baseline: ProductionSchedule,
        optimized: ProductionSchedule,
        forecast: List[CarbonIntensity]
    ) -> List[str]:
        """Generate carbon reduction recommendations."""
        recommendations = []

        reduction = baseline.total_emissions_kg - optimized.total_emissions_kg
        reduction_pct = 100 * reduction / baseline.total_emissions_kg if baseline.total_emissions_kg > 0 else 0

        if reduction_pct >= 20:
            recommendations.append(
                f"Significant carbon reduction achieved ({reduction_pct:.1f}%) through "
                f"load shifting to low-carbon periods"
            )

        if optimized.renewable_fraction > 0.5:
            recommendations.append(
                f"Schedule aligns well with renewable energy ({optimized.renewable_fraction*100:.0f}% renewable)"
            )
        else:
            recommendations.append(
                "Consider on-site renewable energy installation to further reduce emissions"
            )

        # Check for overnight opportunities
        night_intensities = [f for f in forecast if 0 <= f.timestamp.hour < 6 or f.timestamp.hour >= 22]
        if night_intensities:
            avg_night = sum(f.intensity_gco2_per_kwh for f in night_intensities) / len(night_intensities)
            avg_day = sum(f.intensity_gco2_per_kwh for f in forecast) / len(forecast)

            if avg_night < avg_day * 0.8:
                recommendations.append(
                    "Overnight production could reduce emissions further (lower grid intensity)"
                )

        # Energy efficiency recommendation
        if optimized.total_energy_kwh > 100:
            recommendations.append(
                "Consider energy efficiency improvements to reduce base load"
            )

        return recommendations

    def calculate_carbon_footprint(
        self,
        material_kg: float,
        material_type: str,
        electricity_kwh: float,
        transport_km: float = 0
    ) -> Dict[str, float]:
        """
        Calculate total carbon footprint for production.

        Args:
            material_kg: Material consumption in kg
            material_type: Type of material (pla, abs, etc.)
            electricity_kwh: Electricity consumption
            transport_km: Transport distance (optional)

        Returns:
            Carbon footprint by scope
        """
        current_intensity = self.grid_forecast.get_current_intensity()

        footprint = {
            "scope_1": 0.0,
            "scope_2": 0.0,
            "scope_3": 0.0,
            "total": 0.0,
        }

        # Scope 2: Electricity
        footprint["scope_2"] = electricity_kwh * current_intensity.intensity_gco2_per_kwh / 1000

        # Scope 3: Materials
        material_ef = self.emission_factors.get(f"{material_type}_production")
        if material_ef:
            footprint["scope_3"] += material_kg * material_ef.value

        # Scope 3: Transport (simplified)
        if transport_km > 0:
            # Assume truck transport: ~0.1 kg CO2/tonne-km
            footprint["scope_3"] += material_kg * transport_km * 0.0001

        footprint["total"] = sum([
            footprint["scope_1"],
            footprint["scope_2"],
            footprint["scope_3"]
        ])

        return footprint


class ManufacturingCarbonOptimizer(CarbonOptimizer):
    """
    Manufacturing-specific carbon optimizer.

    Extends base optimizer with manufacturing process knowledge
    including equipment startup/shutdown costs and process constraints.
    """

    def __init__(self, config: Optional[CarbonConfig] = None):
        super().__init__(config)

        # Manufacturing-specific parameters
        self.equipment_startup_energy = {
            "fdm_printer": 0.1,  # kWh
            "sla_printer": 0.2,
            "cnc_machine": 0.5,
            "injection_molder": 2.0,
        }

        self.equipment_idle_power = {
            "fdm_printer": 0.05,  # kW
            "sla_printer": 0.1,
            "cnc_machine": 0.2,
            "injection_molder": 0.5,
        }

    def optimize_with_equipment(
        self,
        jobs: List[ProductionJob],
        equipment_type: str,
        start_time: Optional[datetime] = None
    ) -> CarbonResult:
        """
        Optimize schedule considering equipment constraints.

        Includes equipment startup energy and idle power in
        carbon calculations.
        """
        if start_time is None:
            start_time = datetime.now()

        # Add startup energy to first job
        if jobs:
            startup_energy = self.equipment_startup_energy.get(equipment_type, 0)
            jobs[0].energy_kwh += startup_energy

        # Run base optimization
        result = self.optimize_schedule(jobs, start_time)

        # Add idle time emissions
        idle_power = self.equipment_idle_power.get(equipment_type, 0)
        if result.schedule.jobs:
            for i in range(len(result.schedule.jobs) - 1):
                current_job = result.schedule.jobs[i]
                next_job = result.schedule.jobs[i + 1]

                idle_time = (next_job.start_time - current_job.end_time).total_seconds() / 3600
                if idle_time > 0:
                    idle_energy = idle_power * idle_time
                    idle_emissions = idle_energy * 0.4  # Assume average grid intensity
                    result.optimized_emissions_kg += idle_emissions

        return result

    def recommend_equipment_schedule(
        self,
        jobs: List[ProductionJob],
        equipment_types: List[str]
    ) -> Dict[str, Any]:
        """
        Recommend optimal equipment scheduling for carbon reduction.

        Compares different equipment options and scheduling strategies.
        """
        results = {}

        for equipment in equipment_types:
            result = self.optimize_with_equipment(jobs, equipment)
            results[equipment] = {
                "total_emissions_kg": result.optimized_emissions_kg,
                "reduction_percent": result.reduction_percent,
                "schedule": result.schedule,
            }

        # Find best option
        best_equipment = min(results, key=lambda x: results[x]["total_emissions_kg"])

        return {
            "recommended_equipment": best_equipment,
            "emissions_comparison": {k: v["total_emissions_kg"] for k, v in results.items()},
            "best_schedule": results[best_equipment]["schedule"],
            "recommendations": [
                f"Use {best_equipment} for lowest carbon emissions",
                f"Potential reduction: {results[best_equipment]['reduction_percent']:.1f}%",
            ]
        }


# Module exports
__all__ = [
    # Enums
    "EmissionScope",
    "EmissionCategory",
    # Data classes
    "CarbonIntensity",
    "EmissionFactor",
    "ProductionJob",
    "ScheduledJob",
    "ProductionSchedule",
    "CarbonConfig",
    "CarbonResult",
    # Classes
    "GridCarbonForecast",
    "CarbonOptimizer",
    "ManufacturingCarbonOptimizer",
]
