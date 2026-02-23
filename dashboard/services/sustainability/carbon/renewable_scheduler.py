"""
Renewable Energy Scheduler for Manufacturing.

Aligns production schedules with renewable energy availability
to maximize use of clean energy and minimize carbon emissions.

Research Value:
- Novel renewable-aligned scheduling algorithm
- Solar/wind forecast integration
- Grid flexibility and demand response

References:
- Bird, L., et al. (2016). Wind and Solar Energy Curtailment
- Denholm, P., et al. (2010). Role of Energy Storage in Electricity Grid
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
from datetime import datetime, timedelta
import math
import random


class EnergySource(Enum):
    """Types of energy sources."""
    SOLAR = auto()
    WIND = auto()
    HYDRO = auto()
    NUCLEAR = auto()
    NATURAL_GAS = auto()
    COAL = auto()
    BIOMASS = auto()
    GEOTHERMAL = auto()
    BATTERY_STORAGE = auto()


@dataclass
class EnergySourceProfile:
    """Profile for an energy source."""

    source: EnergySource
    capacity_kw: float
    carbon_intensity: float  # g CO2/kWh
    availability_factor: float = 1.0
    cost_per_kwh: float = 0.10
    is_renewable: bool = True
    is_dispatchable: bool = False


@dataclass
class GridForecast:
    """Grid energy mix forecast."""

    timestamp: datetime
    total_demand_mw: float
    renewable_fraction: float
    solar_fraction: float
    wind_fraction: float
    carbon_intensity: float  # g CO2/kWh
    price_per_mwh: float = 50.0
    curtailment_mw: float = 0.0  # Renewable curtailment


@dataclass
class RenewableWindow:
    """Time window with high renewable availability."""

    start_time: datetime
    end_time: datetime
    average_renewable_fraction: float
    peak_renewable_fraction: float
    average_carbon_intensity: float
    energy_available_kwh: float
    priority_score: float = 0.0

    @property
    def duration_hours(self) -> float:
        """Window duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600


@dataclass
class SolarForecast:
    """Solar generation forecast."""

    timestamp: datetime
    irradiance_w_m2: float
    generation_kw: float
    capacity_factor: float
    cloud_cover: float = 0.0


@dataclass
class WindForecast:
    """Wind generation forecast."""

    timestamp: datetime
    wind_speed_m_s: float
    generation_kw: float
    capacity_factor: float
    direction_degrees: float = 0.0


@dataclass
class RenewableConfig:
    """Configuration for renewable scheduler."""

    planning_horizon_hours: int = 48
    time_resolution_minutes: int = 15
    min_renewable_fraction: float = 0.5
    solar_capacity_kw: float = 100.0
    wind_capacity_kw: float = 50.0
    battery_capacity_kwh: float = 200.0
    battery_power_kw: float = 50.0
    latitude: float = 37.0
    longitude: float = -122.0


class SolarForecaster:
    """
    Solar energy forecaster.

    Simulates solar generation based on location, time, and weather.
    """

    def __init__(self, config: RenewableConfig):
        self.config = config
        self.capacity_kw = config.solar_capacity_kw

    def get_forecast(
        self,
        hours_ahead: int = 48,
        resolution_minutes: int = 15
    ) -> List[SolarForecast]:
        """Generate solar forecast."""
        forecast = []
        now = datetime.now()
        intervals = (hours_ahead * 60) // resolution_minutes

        for i in range(intervals):
            timestamp = now + timedelta(minutes=i * resolution_minutes)

            # Calculate solar position (simplified)
            hour = timestamp.hour + timestamp.minute / 60
            day_of_year = timestamp.timetuple().tm_yday

            # Sunrise/sunset model (simplified)
            declination = 23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365))
            hour_angle = 15 * (hour - 12)

            # Solar altitude
            lat_rad = math.radians(self.config.latitude)
            decl_rad = math.radians(declination)
            ha_rad = math.radians(hour_angle)

            sin_altitude = (
                    math.sin(lat_rad) * math.sin(decl_rad) +
                    math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad)
            )
            altitude = math.degrees(math.asin(max(-1, min(1, sin_altitude))))

            # Clear sky irradiance
            if altitude > 0:
                air_mass = 1 / math.sin(math.radians(altitude))
                clear_sky_irradiance = 1361 * 0.7 ** (air_mass ** 0.678)
            else:
                clear_sky_irradiance = 0

            # Add cloud cover (random simulation)
            cloud_cover = random.uniform(0, 0.5)  # 0-50% cloud cover
            irradiance = clear_sky_irradiance * (1 - 0.75 * cloud_cover)

            # Calculate generation
            efficiency = 0.18  # Panel efficiency
            system_losses = 0.85  # Inverter, wiring, etc.
            area_m2 = self.capacity_kw / (1.0 * efficiency)  # Approximate panel area

            generation_kw = irradiance * area_m2 * efficiency * system_losses / 1000
            generation_kw = min(generation_kw, self.capacity_kw)

            capacity_factor = generation_kw / self.capacity_kw if self.capacity_kw > 0 else 0

            forecast.append(SolarForecast(
                timestamp=timestamp,
                irradiance_w_m2=irradiance,
                generation_kw=max(0, generation_kw),
                capacity_factor=capacity_factor,
                cloud_cover=cloud_cover
            ))

        return forecast


class WindForecaster:
    """
    Wind energy forecaster.

    Simulates wind generation based on location and weather patterns.
    """

    def __init__(self, config: RenewableConfig):
        self.config = config
        self.capacity_kw = config.wind_capacity_kw

        # Turbine parameters
        self.cut_in_speed = 3.0  # m/s
        self.rated_speed = 12.0  # m/s
        self.cut_out_speed = 25.0  # m/s

    def get_forecast(
        self,
        hours_ahead: int = 48,
        resolution_minutes: int = 15
    ) -> List[WindForecast]:
        """Generate wind forecast."""
        forecast = []
        now = datetime.now()
        intervals = (hours_ahead * 60) // resolution_minutes

        # Base wind speed with diurnal pattern
        base_wind_speed = 6.0  # m/s average

        for i in range(intervals):
            timestamp = now + timedelta(minutes=i * resolution_minutes)

            # Diurnal pattern (stronger afternoon winds)
            hour = timestamp.hour
            diurnal_factor = 1.0 + 0.3 * math.sin(math.radians((hour - 6) * 15))

            # Random variation
            variation = random.gauss(0, 0.3)

            wind_speed = base_wind_speed * diurnal_factor * (1 + variation)
            wind_speed = max(0, wind_speed)

            # Power curve
            if wind_speed < self.cut_in_speed:
                generation_kw = 0
            elif wind_speed < self.rated_speed:
                # Cubic relationship below rated speed
                generation_kw = self.capacity_kw * (
                        (wind_speed - self.cut_in_speed) /
                        (self.rated_speed - self.cut_in_speed)
                ) ** 3
            elif wind_speed < self.cut_out_speed:
                generation_kw = self.capacity_kw
            else:
                generation_kw = 0  # Cut-out protection

            capacity_factor = generation_kw / self.capacity_kw if self.capacity_kw > 0 else 0

            forecast.append(WindForecast(
                timestamp=timestamp,
                wind_speed_m_s=wind_speed,
                generation_kw=generation_kw,
                capacity_factor=capacity_factor,
                direction_degrees=random.uniform(0, 360)
            ))

        return forecast


class BatteryStorage:
    """
    Battery energy storage system.

    Models battery for shifting renewable energy to production needs.
    """

    def __init__(self, config: RenewableConfig):
        self.capacity_kwh = config.battery_capacity_kwh
        self.power_kw = config.battery_power_kw
        self.efficiency = 0.90  # Round-trip efficiency
        self.current_soc = 0.5  # State of charge (0-1)
        self.min_soc = 0.1
        self.max_soc = 0.9

    @property
    def available_energy_kwh(self) -> float:
        """Available energy to discharge."""
        return (self.current_soc - self.min_soc) * self.capacity_kwh

    @property
    def available_capacity_kwh(self) -> float:
        """Available capacity to charge."""
        return (self.max_soc - self.current_soc) * self.capacity_kwh

    def charge(self, energy_kwh: float, duration_hours: float) -> float:
        """
        Charge battery.

        Returns actual energy stored.
        """
        max_power = min(self.power_kw, energy_kwh / duration_hours)
        max_energy = max_power * duration_hours * math.sqrt(self.efficiency)

        actual_energy = min(max_energy, self.available_capacity_kwh)
        self.current_soc += actual_energy / self.capacity_kwh

        return actual_energy

    def discharge(self, energy_kwh: float, duration_hours: float) -> float:
        """
        Discharge battery.

        Returns actual energy delivered.
        """
        max_power = min(self.power_kw, energy_kwh / duration_hours)
        max_energy = max_power * duration_hours * math.sqrt(self.efficiency)

        actual_energy = min(max_energy, self.available_energy_kwh)
        self.current_soc -= actual_energy / self.capacity_kwh

        return actual_energy


class RenewableScheduler:
    """
    Renewable-aligned production scheduler.

    Optimizes production schedules to maximize use of on-site
    and grid renewable energy.

    Research Value:
    - Novel renewable-aligned scheduling algorithm
    - Integration of solar/wind forecasts
    - Battery storage optimization
    """

    def __init__(self, config: Optional[RenewableConfig] = None):
        self.config = config or RenewableConfig()
        self.solar_forecaster = SolarForecaster(self.config)
        self.wind_forecaster = WindForecaster(self.config)
        self.battery = BatteryStorage(self.config)

    def find_renewable_windows(
        self,
        min_renewable_fraction: Optional[float] = None,
        min_duration_hours: float = 1.0
    ) -> List[RenewableWindow]:
        """
        Find time windows with high renewable availability.

        Args:
            min_renewable_fraction: Minimum renewable fraction required
            min_duration_hours: Minimum window duration

        Returns:
            List of renewable windows
        """
        if min_renewable_fraction is None:
            min_renewable_fraction = self.config.min_renewable_fraction

        # Get forecasts
        solar_forecast = self.solar_forecaster.get_forecast(
            hours_ahead=self.config.planning_horizon_hours,
            resolution_minutes=self.config.time_resolution_minutes
        )
        wind_forecast = self.wind_forecaster.get_forecast(
            hours_ahead=self.config.planning_horizon_hours,
            resolution_minutes=self.config.time_resolution_minutes
        )

        # Combine forecasts
        combined = []
        for solar, wind in zip(solar_forecast, wind_forecast):
            total_renewable = solar.generation_kw + wind.generation_kw
            total_capacity = self.config.solar_capacity_kw + self.config.wind_capacity_kw
            renewable_fraction = total_renewable / total_capacity if total_capacity > 0 else 0

            combined.append({
                "timestamp": solar.timestamp,
                "solar_kw": solar.generation_kw,
                "wind_kw": wind.generation_kw,
                "total_kw": total_renewable,
                "renewable_fraction": renewable_fraction,
                "carbon_intensity": 50 + 350 * (1 - renewable_fraction),  # Simplified
            })

        # Find windows above threshold
        windows = []
        window_start = None
        window_data = []

        for point in combined:
            if point["renewable_fraction"] >= min_renewable_fraction:
                if window_start is None:
                    window_start = point["timestamp"]
                window_data.append(point)
            else:
                if window_start is not None:
                    # Check duration
                    duration = (point["timestamp"] - window_start).total_seconds() / 3600
                    if duration >= min_duration_hours:
                        windows.append(self._create_window(window_start, point["timestamp"], window_data))

                    window_start = None
                    window_data = []

        # Handle final window
        if window_start is not None and window_data:
            end_time = window_data[-1]["timestamp"] + timedelta(
                minutes=self.config.time_resolution_minutes
            )
            duration = (end_time - window_start).total_seconds() / 3600
            if duration >= min_duration_hours:
                windows.append(self._create_window(window_start, end_time, window_data))

        # Sort by priority score
        windows.sort(key=lambda w: w.priority_score, reverse=True)

        return windows

    def _create_window(
        self,
        start_time: datetime,
        end_time: datetime,
        data: List[Dict]
    ) -> RenewableWindow:
        """Create renewable window from data points."""
        avg_renewable = sum(d["renewable_fraction"] for d in data) / len(data)
        peak_renewable = max(d["renewable_fraction"] for d in data)
        avg_carbon = sum(d["carbon_intensity"] for d in data) / len(data)

        # Calculate available energy
        duration_hours = (end_time - start_time).total_seconds() / 3600
        avg_power = sum(d["total_kw"] for d in data) / len(data)
        energy_kwh = avg_power * duration_hours

        # Priority score based on renewable fraction and duration
        priority_score = avg_renewable * math.log(1 + duration_hours)

        return RenewableWindow(
            start_time=start_time,
            end_time=end_time,
            average_renewable_fraction=avg_renewable,
            peak_renewable_fraction=peak_renewable,
            average_carbon_intensity=avg_carbon,
            energy_available_kwh=energy_kwh,
            priority_score=priority_score
        )

    def get_grid_forecast(
        self,
        hours_ahead: int = 48
    ) -> List[GridForecast]:
        """
        Get combined grid forecast.

        Combines on-site renewable forecasts with simulated grid data.
        """
        solar_forecast = self.solar_forecaster.get_forecast(hours_ahead=hours_ahead)
        wind_forecast = self.wind_forecaster.get_forecast(hours_ahead=hours_ahead)

        grid_forecast = []

        for solar, wind in zip(solar_forecast, wind_forecast):
            # Simulated grid-level data
            hour = solar.timestamp.hour

            # Demand pattern (higher during day)
            if 6 <= hour < 22:
                demand = 50000 + 10000 * math.sin(math.radians((hour - 6) * 11.25))
            else:
                demand = 40000

            # Grid renewable fraction (varies with time)
            grid_renewable = 0.3 + 0.2 * math.sin(math.radians((hour - 6) * 15))

            # On-site contribution
            onsite_renewable = (solar.generation_kw + wind.generation_kw)
            onsite_demand = 100  # Assumed facility demand in kW

            # Combined renewable fraction
            total_renewable = grid_renewable + (onsite_renewable / onsite_demand if onsite_demand > 0 else 0)
            total_renewable = min(1.0, total_renewable)

            # Carbon intensity
            carbon_intensity = 50 + 400 * (1 - total_renewable)

            # Price (simplified - lower during high renewable)
            price = 40 + 20 * (1 - total_renewable)

            grid_forecast.append(GridForecast(
                timestamp=solar.timestamp,
                total_demand_mw=demand / 1000,
                renewable_fraction=total_renewable,
                solar_fraction=solar.capacity_factor * 0.3,
                wind_fraction=wind.capacity_factor * 0.15,
                carbon_intensity=carbon_intensity,
                price_per_mwh=price
            ))

        return grid_forecast

    def optimize_battery_schedule(
        self,
        production_load_kw: float,
        hours_ahead: int = 24
    ) -> Dict[str, Any]:
        """
        Optimize battery charging/discharging schedule.

        Charges during high renewable periods, discharges during production.
        """
        solar_forecast = self.solar_forecaster.get_forecast(hours_ahead=hours_ahead)
        wind_forecast = self.wind_forecaster.get_forecast(hours_ahead=hours_ahead)

        schedule = []
        total_charged = 0.0
        total_discharged = 0.0
        interval_hours = self.config.time_resolution_minutes / 60

        for solar, wind in zip(solar_forecast, wind_forecast):
            total_renewable = solar.generation_kw + wind.generation_kw
            excess = total_renewable - production_load_kw

            if excess > 0:
                # Charge battery with excess renewable
                charged = self.battery.charge(excess * interval_hours, interval_hours)
                total_charged += charged
                schedule.append({
                    "timestamp": solar.timestamp,
                    "action": "charge",
                    "energy_kwh": charged,
                    "soc": self.battery.current_soc,
                })
            elif excess < 0:
                # Discharge battery to meet demand
                needed = abs(excess) * interval_hours
                discharged = self.battery.discharge(needed, interval_hours)
                total_discharged += discharged
                schedule.append({
                    "timestamp": solar.timestamp,
                    "action": "discharge",
                    "energy_kwh": discharged,
                    "soc": self.battery.current_soc,
                })
            else:
                schedule.append({
                    "timestamp": solar.timestamp,
                    "action": "idle",
                    "energy_kwh": 0,
                    "soc": self.battery.current_soc,
                })

        return {
            "schedule": schedule,
            "total_charged_kwh": total_charged,
            "total_discharged_kwh": total_discharged,
            "final_soc": self.battery.current_soc,
            "efficiency": total_discharged / total_charged if total_charged > 0 else 0,
        }

    def recommend_production_timing(
        self,
        energy_required_kwh: float,
        duration_hours: float,
        deadline: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Recommend optimal production timing for maximum renewable use.

        Args:
            energy_required_kwh: Total energy needed
            duration_hours: Production duration
            deadline: Optional deadline

        Returns:
            Recommended timing and expected renewable fraction
        """
        windows = self.find_renewable_windows(min_duration_hours=duration_hours)

        # Filter by deadline
        if deadline:
            windows = [w for w in windows if w.end_time <= deadline]

        if not windows:
            # No good windows, find best available
            now = datetime.now()
            return {
                "recommended_start": now,
                "recommended_end": now + timedelta(hours=duration_hours),
                "expected_renewable_fraction": 0.3,
                "expected_carbon_kg": energy_required_kwh * 0.35,
                "recommendation": "No optimal renewable window available. Consider delaying if possible.",
            }

        best_window = windows[0]  # Already sorted by priority

        return {
            "recommended_start": best_window.start_time,
            "recommended_end": min(
                best_window.end_time,
                best_window.start_time + timedelta(hours=duration_hours)
            ),
            "expected_renewable_fraction": best_window.average_renewable_fraction,
            "expected_carbon_kg": energy_required_kwh * best_window.average_carbon_intensity / 1000,
            "window_energy_available_kwh": best_window.energy_available_kwh,
            "recommendation": f"Schedule production during {best_window.start_time.strftime('%H:%M')} - "
                              f"{best_window.end_time.strftime('%H:%M')} for {best_window.average_renewable_fraction * 100:.0f}% "
                              f"renewable energy",
        }


# Module exports
__all__ = [
    # Enums
    "EnergySource",
    # Data classes
    "EnergySourceProfile",
    "GridForecast",
    "RenewableWindow",
    "SolarForecast",
    "WindForecast",
    "RenewableConfig",
    # Classes
    "SolarForecaster",
    "WindForecaster",
    "BatteryStorage",
    "RenewableScheduler",
]
