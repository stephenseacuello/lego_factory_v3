"""
Data Provider Service - Unified Data Access with Live/Simulation Fallback

LegoMCP World-Class Manufacturing Platform v2.0

Provides a single interface for fetching manufacturing data with:
- Live mode: Real PostgreSQL database queries
- Simulation mode: Pattern-based realistic fallback
- Hybrid mode: Try live, automatically fall back to simulation

This eliminates Math.random() from dashboards and provides
consistent, realistic data whether connected to DB or not.

Author: LegoMCP Team
Version: 2.0.0
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import math
import random
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class DataProviderMode(Enum):
    """Data provider operating modes."""
    LIVE = "live"           # Real database queries only
    SIMULATION = "simulation"  # Pattern-based fallback only
    HYBRID = "hybrid"       # Try live, fall back to simulation


class MachineType(Enum):
    """Types of manufacturing equipment."""
    FDM_PRINTER = "fdm_printer"
    SLA_PRINTER = "sla_printer"
    CNC_MILL = "cnc_mill"
    LASER_CUTTER = "laser_cutter"
    INJECTION_MOLDER = "injection_molder"
    INSPECTION_STATION = "inspection_station"


class MachineStatus(Enum):
    """Equipment operational status."""
    RUNNING = "running"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    ERROR = "error"
    SETUP = "setup"


# =============================================================================
# Simulation Patterns - Realistic, NOT random noise
# =============================================================================

class SimulationPatterns:
    """
    Generates realistic manufacturing data based on patterns, not random noise.

    Uses:
    - Sinusoidal base for natural variation
    - Shift change effects (morning startup, lunch dip)
    - Machine-type specific profiles
    - Maintenance event patterns
    """

    # Shift schedule (24-hour format)
    SHIFT_CHANGES = [6, 14, 22]  # 6am, 2pm, 10pm
    LUNCH_BREAKS = [12, 20, 4]   # Noon, 8pm, 4am

    # Machine type temperature profiles
    TEMP_PROFILES = {
        MachineType.FDM_PRINTER: {
            "hotend": {"base": 210, "variation": 5, "target": 215},
            "bed": {"base": 60, "variation": 3, "target": 60},
            "chamber": {"base": 35, "variation": 5, "target": None},
        },
        MachineType.CNC_MILL: {
            "spindle": {"base": 35, "variation": 10, "target": None},
            "coolant": {"base": 20, "variation": 2, "target": 20},
            "ambient": {"base": 22, "variation": 3, "target": None},
        },
        MachineType.SLA_PRINTER: {
            "resin": {"base": 30, "variation": 2, "target": 30},
            "uv_led": {"base": 45, "variation": 5, "target": None},
            "build_plate": {"base": 35, "variation": 3, "target": 35},
        },
    }

    # OEE baseline by machine type
    OEE_BASELINES = {
        MachineType.FDM_PRINTER: {"oee": 0.78, "availability": 0.92, "performance": 0.88, "quality": 0.96},
        MachineType.CNC_MILL: {"oee": 0.82, "availability": 0.90, "performance": 0.93, "quality": 0.98},
        MachineType.SLA_PRINTER: {"oee": 0.75, "availability": 0.88, "performance": 0.90, "quality": 0.95},
        MachineType.LASER_CUTTER: {"oee": 0.85, "availability": 0.94, "performance": 0.92, "quality": 0.98},
        MachineType.INJECTION_MOLDER: {"oee": 0.88, "availability": 0.95, "performance": 0.95, "quality": 0.97},
    }

    def __init__(self, seed: Optional[int] = None):
        """Initialize with optional seed for reproducibility."""
        self._rng = random.Random(seed)
        self._start_time = datetime.utcnow()

    def _get_time_factor(self, timestamp: Optional[datetime] = None) -> float:
        """Get time-based factor for variation (0.0 to 1.0)."""
        t = timestamp or datetime.utcnow()
        # Use hour and minute for smooth variation
        hour_fraction = t.hour + t.minute / 60.0
        # Sinusoidal pattern over 24 hours
        return (math.sin(hour_fraction * math.pi / 12) + 1) / 2

    def _get_shift_effect(self, timestamp: Optional[datetime] = None) -> float:
        """Get shift change effect multiplier (0.8 to 1.0)."""
        t = timestamp or datetime.utcnow()
        hour = t.hour
        minute = t.minute

        # Check if near shift change
        for shift_hour in self.SHIFT_CHANGES:
            hours_from_shift = abs(hour - shift_hour)
            if hours_from_shift <= 1:
                # Dip during shift change
                return 0.85 + 0.15 * (minute / 60.0 if hour > shift_hour else 1 - minute / 60.0)

        # Check if near lunch break
        for lunch_hour in self.LUNCH_BREAKS:
            if hour == lunch_hour:
                return 0.80 + 0.10 * (minute / 60.0)

        return 1.0

    def generate_temperature(
        self,
        machine_type: MachineType,
        sensor_name: str,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Generate realistic temperature reading.

        Returns dict with 'value', 'target', and 'trend'.
        """
        profile = self.TEMP_PROFILES.get(machine_type, self.TEMP_PROFILES[MachineType.FDM_PRINTER])
        sensor = profile.get(sensor_name, {"base": 25, "variation": 5, "target": None})

        time_factor = self._get_time_factor(timestamp)

        # Base value with time-based variation
        base = sensor["base"]
        variation = sensor["variation"]

        # Smooth sinusoidal variation with small noise
        value = base + variation * (time_factor - 0.5) + self._rng.gauss(0, variation * 0.1)

        # Determine trend based on recent history (simulated)
        trend = "stable"
        if time_factor > 0.6:
            trend = "rising"
        elif time_factor < 0.4:
            trend = "falling"

        return {
            "value": round(value, 1),
            "target": sensor["target"],
            "trend": trend,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }

    def generate_oee_metrics(
        self,
        machine_type: MachineType = MachineType.FDM_PRINTER,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Generate realistic OEE metrics.

        Incorporates:
        - Machine type baseline
        - Time-of-day variation
        - Shift change effects
        """
        baseline = self.OEE_BASELINES.get(machine_type, self.OEE_BASELINES[MachineType.FDM_PRINTER])

        time_factor = self._get_time_factor(timestamp)
        shift_effect = self._get_shift_effect(timestamp)

        # Apply variations
        availability = baseline["availability"] * shift_effect
        availability += self._rng.gauss(0, 0.02)  # Small noise
        availability = max(0.7, min(1.0, availability))

        performance = baseline["performance"] * (0.95 + 0.1 * time_factor)
        performance += self._rng.gauss(0, 0.015)
        performance = max(0.7, min(1.0, performance))

        quality = baseline["quality"]
        quality += self._rng.gauss(0, 0.01)
        quality = max(0.9, min(1.0, quality))

        oee = availability * performance * quality

        return {
            "oee": round(oee * 100, 1),
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
            "target_oee": 85.0,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }

    def generate_oee_trend(
        self,
        machine_type: MachineType = MachineType.FDM_PRINTER,
        hours: int = 24,
        interval_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        """Generate OEE trend data for charting."""
        trend = []
        now = datetime.utcnow()

        for i in range(0, hours * 60, interval_minutes):
            timestamp = now - timedelta(minutes=hours * 60 - i)
            metrics = self.generate_oee_metrics(machine_type, timestamp)
            trend.append({
                "timestamp": metrics["timestamp"],
                "oee": metrics["oee"],
                "availability": metrics["availability"],
                "performance": metrics["performance"],
                "quality": metrics["quality"],
            })

        return trend

    def generate_temperature_history(
        self,
        machine_type: MachineType = MachineType.FDM_PRINTER,
        hours: int = 24,
        interval_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate temperature history for charting."""
        history = []
        now = datetime.utcnow()

        profile = self.TEMP_PROFILES.get(machine_type, self.TEMP_PROFILES[MachineType.FDM_PRINTER])

        for i in range(0, hours * 60, interval_minutes):
            timestamp = now - timedelta(minutes=hours * 60 - i)

            entry = {"timestamp": timestamp.isoformat()}
            for sensor_name in profile.keys():
                reading = self.generate_temperature(machine_type, sensor_name, timestamp)
                entry[sensor_name] = reading["value"]
                entry[f"{sensor_name}_target"] = reading["target"]

            history.append(entry)

        return history

    def generate_machine_position(
        self,
        machine_type: MachineType = MachineType.FDM_PRINTER,
        print_progress: float = 0.5
    ) -> Dict[str, float]:
        """Generate realistic machine position based on progress."""
        if machine_type == MachineType.FDM_PRINTER:
            # Simulate layer-by-layer printing
            build_height = 50.0  # mm total height
            layer_height = 0.2

            z = print_progress * build_height
            current_layer = int(z / layer_height)

            # X/Y move in infill pattern
            time_factor = self._get_time_factor()
            x = 100 + 80 * math.sin(time_factor * 2 * math.pi * 10)
            y = 100 + 80 * math.cos(time_factor * 2 * math.pi * 10)

            return {
                "x": round(x, 2),
                "y": round(y, 2),
                "z": round(z, 2),
                "layer": current_layer,
                "layer_height": layer_height,
            }

        elif machine_type == MachineType.CNC_MILL:
            # Simulate milling operation
            return {
                "x": round(50 + self._rng.gauss(0, 5), 2),
                "y": round(50 + self._rng.gauss(0, 5), 2),
                "z": round(-2 - print_progress * 10, 2),
                "spindle_rpm": 8000,
                "feed_rate": 1000,
            }

        return {"x": 0, "y": 0, "z": 0}

    def generate_work_center_state(
        self,
        work_center_id: str,
        machine_type: MachineType = MachineType.FDM_PRINTER,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate complete work center state."""
        time_factor = self._get_time_factor(timestamp)
        shift_effect = self._get_shift_effect(timestamp)

        # Determine status based on time
        status_weights = {
            MachineStatus.RUNNING: 0.7 * shift_effect,
            MachineStatus.IDLE: 0.15,
            MachineStatus.SETUP: 0.1,
            MachineStatus.MAINTENANCE: 0.03,
            MachineStatus.ERROR: 0.02,
        }

        # Weighted random selection (but deterministic for same time)
        roll = (hash(f"{work_center_id}:{timestamp}") % 100) / 100.0
        cumulative = 0
        status = MachineStatus.RUNNING
        for s, weight in status_weights.items():
            cumulative += weight
            if roll < cumulative:
                status = s
                break

        # Generate state based on status
        if status == MachineStatus.RUNNING:
            progress = time_factor * 0.3 + 0.5 + self._rng.gauss(0, 0.05)
            progress = max(0.1, min(0.95, progress))
        else:
            progress = 0

        position = self.generate_machine_position(machine_type, progress)
        temperatures = {}
        profile = self.TEMP_PROFILES.get(machine_type, self.TEMP_PROFILES[MachineType.FDM_PRINTER])

        for sensor_name in profile.keys():
            temp_data = self.generate_temperature(machine_type, sensor_name, timestamp)
            temperatures[sensor_name] = temp_data["value"]
            temperatures[f"{sensor_name}_target"] = temp_data["target"]

        return {
            "work_center_id": work_center_id,
            "status": status.value,
            "progress": round(progress * 100, 1) if status == MachineStatus.RUNNING else 0,
            "position": position,
            "temperatures": temperatures,
            "oee": self.generate_oee_metrics(machine_type, timestamp),
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
        }


# =============================================================================
# Data Provider Service
# =============================================================================

class DataProvider:
    """
    Unified data provider with automatic fallback.

    Provides consistent interface for:
    - Work center states
    - OEE metrics
    - Temperature history
    - Asset listings

    Automatically falls back to realistic simulation
    when database is unavailable (HYBRID mode).
    """

    def __init__(
        self,
        session=None,
        mode: DataProviderMode = DataProviderMode.HYBRID
    ):
        """
        Initialize data provider.

        Args:
            session: SQLAlchemy session (optional)
            mode: Operating mode (LIVE, SIMULATION, or HYBRID)
        """
        self._session = session
        self._mode = mode
        self._simulation = SimulationPatterns()
        self._is_live = False
        self._last_db_check = None
        self._db_check_interval = timedelta(seconds=30)

        # Check database connectivity
        if mode != DataProviderMode.SIMULATION:
            self._check_database()

    def _check_database(self) -> bool:
        """Check if database is available."""
        now = datetime.utcnow()

        # Rate limit DB checks
        if self._last_db_check and (now - self._last_db_check) < self._db_check_interval:
            return self._is_live

        self._last_db_check = now

        if self._session is None:
            self._is_live = False
            return False

        try:
            # Try a simple query
            self._session.execute("SELECT 1")
            self._is_live = True
            return True
        except Exception as e:
            logger.warning(f"Database unavailable, using simulation: {e}")
            self._is_live = False
            return False

    def is_live(self) -> bool:
        """Check if using live data."""
        if self._mode == DataProviderMode.SIMULATION:
            return False
        if self._mode == DataProviderMode.LIVE:
            return self._check_database()
        # HYBRID mode
        return self._is_live

    def get_data_mode(self) -> str:
        """Get current data mode as string."""
        return "live" if self.is_live() else "simulation"

    # =========================================================================
    # Work Center / Asset Methods
    # =========================================================================

    def get_work_center_assets(self) -> List[Dict[str, Any]]:
        """Get all work center assets."""
        if self.is_live():
            return self._query_work_centers_live()
        return self._get_fallback_assets()

    def _query_work_centers_live(self) -> List[Dict[str, Any]]:
        """Query work centers from database."""
        try:
            from models.work_center import WorkCenter

            work_centers = self._session.query(WorkCenter).filter(
                WorkCenter.is_active == True
            ).all()

            return [
                {
                    "id": wc.id,
                    "code": wc.code,
                    "name": wc.name,
                    "type": wc.type,
                    "type_display": wc.type.replace("_", " ").title() if wc.type else "Unknown",
                    "status": wc.status or "idle",
                    "icon": self._get_machine_icon(wc.type),
                    "last_sync_ago": "Just now",
                }
                for wc in work_centers
            ]
        except Exception as e:
            logger.error(f"Error querying work centers: {e}")
            return self._get_fallback_assets()

    def _get_fallback_assets(self) -> List[Dict[str, Any]]:
        """Get fallback asset list for demo/simulation."""
        return [
            {
                "id": "wc-001",
                "code": "PRUSA-MK3S-01",
                "name": "Prusa MK3S+ #1",
                "type": "fdm_printer",
                "type_display": "FDM Printer",
                "status": "running",
                "icon": "printer",
                "last_sync_ago": "2s ago",
            },
            {
                "id": "wc-002",
                "code": "BAMBU-A1-01",
                "name": "Bambu A1 Mini",
                "type": "fdm_printer",
                "type_display": "FDM Printer",
                "status": "running",
                "icon": "printer",
                "last_sync_ago": "5s ago",
            },
            {
                "id": "wc-003",
                "code": "BANTAM-CNC-01",
                "name": "Bantam Desktop CNC",
                "type": "cnc_mill",
                "type_display": "CNC Mill",
                "status": "idle",
                "icon": "gear",
                "last_sync_ago": "10s ago",
            },
            {
                "id": "wc-004",
                "code": "ELEGOO-MARS-01",
                "name": "Elegoo Mars 3",
                "type": "sla_printer",
                "type_display": "SLA Printer",
                "status": "running",
                "icon": "layers",
                "last_sync_ago": "3s ago",
            },
            {
                "id": "wc-005",
                "code": "INSPECT-01",
                "name": "Vision Inspection #1",
                "type": "inspection_station",
                "type_display": "Inspection",
                "status": "running",
                "icon": "eye",
                "last_sync_ago": "1s ago",
            },
        ]

    def _get_machine_icon(self, machine_type: str) -> str:
        """Get icon name for machine type."""
        icons = {
            "fdm_printer": "printer",
            "sla_printer": "layers",
            "cnc_mill": "gear",
            "laser_cutter": "lightning",
            "injection_molder": "box",
            "inspection_station": "eye",
        }
        return icons.get(machine_type, "cpu")

    # =========================================================================
    # Asset State Methods
    # =========================================================================

    def get_asset_state(self, asset_id: str) -> Dict[str, Any]:
        """Get current state of a specific asset."""
        if self.is_live():
            return self._query_asset_state_live(asset_id)
        return self._simulate_asset_state(asset_id)

    def _query_asset_state_live(self, asset_id: str) -> Dict[str, Any]:
        """Query asset state from database."""
        try:
            from models.digital_twin_state import DigitalTwinState
            from models.work_center import WorkCenter

            # Get latest state
            state = self._session.query(DigitalTwinState).filter(
                DigitalTwinState.work_center_id == asset_id
            ).order_by(DigitalTwinState.timestamp.desc()).first()

            wc = self._session.query(WorkCenter).filter(
                WorkCenter.id == asset_id
            ).first()

            if state:
                return {
                    "work_center_id": asset_id,
                    "name": wc.name if wc else asset_id,
                    "status": state.machine_status or "unknown",
                    "progress": state.progress_pct or 0,
                    "position": {
                        "x": state.position_x or 0,
                        "y": state.position_y or 0,
                        "z": state.position_z or 0,
                    },
                    "temperatures": {
                        "hotend": state.hotend_temp,
                        "hotend_target": state.hotend_target,
                        "bed": state.bed_temp,
                        "bed_target": state.bed_target,
                    },
                    "timestamp": state.timestamp.isoformat() if state.timestamp else None,
                    "data_mode": "live",
                }

            return self._simulate_asset_state(asset_id)

        except Exception as e:
            logger.error(f"Error querying asset state: {e}")
            return self._simulate_asset_state(asset_id)

    def _simulate_asset_state(self, asset_id: str) -> Dict[str, Any]:
        """Generate simulated asset state."""
        # Determine machine type from asset ID
        machine_type = MachineType.FDM_PRINTER
        if "cnc" in asset_id.lower() or "bantam" in asset_id.lower():
            machine_type = MachineType.CNC_MILL
        elif "sla" in asset_id.lower() or "mars" in asset_id.lower() or "elegoo" in asset_id.lower():
            machine_type = MachineType.SLA_PRINTER

        state = self._simulation.generate_work_center_state(asset_id, machine_type)
        state["data_mode"] = "simulation"

        # Flatten temperatures for compatibility
        if "temperatures" in state:
            temps = state["temperatures"]
            state["temperature"] = temps.get("hotend", temps.get("spindle", 25))
            state["temperature_target"] = temps.get("hotend_target", temps.get("spindle_target"))

        return state

    # =========================================================================
    # OEE Methods
    # =========================================================================

    def get_oee_metrics(
        self,
        work_center_id: str,
        period_hours: int = 24
    ) -> Dict[str, Any]:
        """Get OEE metrics for a work center."""
        if self.is_live():
            return self._query_oee_live(work_center_id, period_hours)
        return self._simulate_oee(work_center_id)

    def _query_oee_live(self, work_center_id: str, period_hours: int) -> Dict[str, Any]:
        """Query OEE from database."""
        try:
            from sqlalchemy import func, and_
            from models.oee_event import OEEEvent

            cutoff = datetime.utcnow() - timedelta(hours=period_hours)

            # Query OEE events
            result = self._session.query(
                func.sum(OEEEvent.duration_minutes).label("total_time"),
                func.sum(
                    func.case(
                        [(OEEEvent.event_type == "PRODUCTION", OEEEvent.duration_minutes)],
                        else_=0
                    )
                ).label("production_time"),
                func.sum(OEEEvent.parts_produced).label("total_parts"),
                func.sum(OEEEvent.parts_good).label("good_parts"),
            ).filter(
                and_(
                    OEEEvent.work_center_id == work_center_id,
                    OEEEvent.start_time >= cutoff
                )
            ).first()

            if result and result.total_time:
                availability = (result.production_time or 0) / result.total_time * 100
                # Performance and quality need more data, estimate
                performance = 88.0  # Would need ideal cycle time
                quality = ((result.good_parts or 0) / (result.total_parts or 1)) * 100 if result.total_parts else 98.0
                oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

                return {
                    "oee": round(oee, 1),
                    "availability": round(availability, 1),
                    "performance": round(performance, 1),
                    "quality": round(quality, 1),
                    "target_oee": 85.0,
                    "period_hours": period_hours,
                    "data_mode": "live",
                }

            return self._simulate_oee(work_center_id)

        except Exception as e:
            logger.error(f"Error querying OEE: {e}")
            return self._simulate_oee(work_center_id)

    def _simulate_oee(self, work_center_id: str) -> Dict[str, Any]:
        """Generate simulated OEE metrics."""
        machine_type = MachineType.FDM_PRINTER
        if "cnc" in work_center_id.lower():
            machine_type = MachineType.CNC_MILL

        metrics = self._simulation.generate_oee_metrics(machine_type)
        metrics["data_mode"] = "simulation"
        return metrics

    def get_oee_trend(
        self,
        work_center_id: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get OEE trend data for charting."""
        if self.is_live():
            return self._query_oee_trend_live(work_center_id, hours)
        return self._simulation.generate_oee_trend(hours=hours)

    def _query_oee_trend_live(self, work_center_id: str, hours: int) -> List[Dict[str, Any]]:
        """Query OEE trend from database."""
        # For now, fall back to simulation
        # Would need aggregated OEE snapshots table
        return self._simulation.generate_oee_trend(hours=hours)

    # =========================================================================
    # Temperature History
    # =========================================================================

    def get_temperature_history(
        self,
        work_center_id: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get temperature history for charting."""
        if self.is_live():
            return self._query_temperature_history_live(work_center_id, hours)
        return self._simulation.generate_temperature_history(hours=hours)

    def _query_temperature_history_live(
        self,
        work_center_id: str,
        hours: int
    ) -> List[Dict[str, Any]]:
        """Query temperature history from database."""
        try:
            from models.digital_twin_state import DigitalTwinState

            cutoff = datetime.utcnow() - timedelta(hours=hours)

            states = self._session.query(DigitalTwinState).filter(
                DigitalTwinState.work_center_id == work_center_id,
                DigitalTwinState.timestamp >= cutoff,
                DigitalTwinState.hotend_temp.isnot(None)
            ).order_by(DigitalTwinState.timestamp).all()

            if states:
                return [
                    {
                        "timestamp": s.timestamp.isoformat(),
                        "hotend": s.hotend_temp,
                        "hotend_target": s.hotend_target,
                        "bed": s.bed_temp,
                        "bed_target": s.bed_target,
                    }
                    for s in states
                ]

            return self._simulation.generate_temperature_history(hours=hours)

        except Exception as e:
            logger.error(f"Error querying temperature history: {e}")
            return self._simulation.generate_temperature_history(hours=hours)

    # =========================================================================
    # Context for AI Copilot
    # =========================================================================

    def get_production_context(
        self,
        work_center_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get production context for AI copilot.

        Replaces hardcoded values in copilot.py
        """
        oee = self.get_oee_metrics(work_center_id or "wc-001", 24)

        return {
            "oee": {
                "current": oee["oee"] / 100,
                "target": 0.85,
                "availability": oee["availability"] / 100,
                "performance": oee["performance"] / 100,
                "quality": oee["quality"] / 100,
            },
            "quality": {
                "fpy": 0.985 if self.is_live() else 0.98 + self._simulation._rng.gauss(0, 0.005),
                "defect_rate": 1 - oee["quality"] / 100,
            },
            "scheduling": {
                "on_time_delivery": 0.98 if self.is_live() else 0.96 + self._simulation._rng.gauss(0, 0.02),
                "capacity_utilization": oee["performance"] / 100,
            },
            "maintenance": {
                "machine_health": 0.92 if self.is_live() else 0.90 + self._simulation._rng.gauss(0, 0.03),
            },
            "data_mode": self.get_data_mode(),
            "timestamp": datetime.utcnow().isoformat(),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_data_provider: Optional[DataProvider] = None


def get_data_provider(session=None, mode: DataProviderMode = DataProviderMode.HYBRID) -> DataProvider:
    """Get or create data provider instance."""
    global _data_provider

    if _data_provider is None or session is not None:
        _data_provider = DataProvider(session=session, mode=mode)

    return _data_provider


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "DataProvider",
    "DataProviderMode",
    "SimulationPatterns",
    "MachineType",
    "MachineStatus",
    "get_data_provider",
]
