"""
Maintenance Predictor for CNC Manufacturing.

Predicts maintenance needs based on:
- Machine runtime and usage patterns
- Sensor trends (vibration, temperature, load)
- Component lifecycles
- Historical maintenance data
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import math

logger = logging.getLogger(__name__)


class MaintenanceType(Enum):
    """Types of maintenance."""
    PREVENTIVE = "preventive"      # Scheduled maintenance
    PREDICTIVE = "predictive"      # Based on condition monitoring
    CORRECTIVE = "corrective"      # Fix after failure
    OPPORTUNISTIC = "opportunistic" # When convenient


class MaintenancePriority(Enum):
    """Maintenance priority levels."""
    LOW = "low"           # Can wait
    MEDIUM = "medium"     # Schedule soon
    HIGH = "high"         # Schedule this week
    CRITICAL = "critical" # Immediate attention


@dataclass
class MaintenanceTask:
    """A maintenance task."""
    task_id: str
    name: str
    component: str
    maintenance_type: MaintenanceType
    priority: MaintenancePriority
    estimated_duration_minutes: int
    due_date: Optional[datetime] = None
    last_performed: Optional[datetime] = None
    interval_hours: float = 0.0
    confidence: float = 0.8

    # Trigger conditions
    triggered_by: str = ""  # runtime, sensor, calendar
    trigger_value: float = 0.0

    # Cost/impact
    estimated_cost: float = 0.0
    downtime_risk_if_skipped: str = ""

    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "component": self.component,
            "type": self.maintenance_type.value,
            "priority": self.priority.value,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "last_performed": self.last_performed.isoformat() if self.last_performed else None,
            "interval_hours": self.interval_hours,
            "confidence": self.confidence,
            "triggered_by": self.triggered_by,
            "trigger_value": self.trigger_value,
            "estimated_cost": self.estimated_cost,
            "downtime_risk_if_skipped": self.downtime_risk_if_skipped,
            "notes": self.notes,
        }


@dataclass
class MaintenanceSchedule:
    """Recommended maintenance schedule."""
    machine_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    tasks: List[MaintenanceTask] = field(default_factory=list)

    # Summary metrics
    total_tasks: int = 0
    critical_tasks: int = 0
    total_estimated_hours: float = 0.0
    health_score: float = 100.0

    # Next actions
    next_maintenance_date: Optional[datetime] = None
    maintenance_window_recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "machine_id": self.machine_id,
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_tasks": self.total_tasks,
                "critical_tasks": self.critical_tasks,
                "total_estimated_hours": self.total_estimated_hours,
                "health_score": self.health_score,
            },
            "next_maintenance_date": (
                self.next_maintenance_date.isoformat()
                if self.next_maintenance_date else None
            ),
            "window_recommendation": self.maintenance_window_recommendation,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class MaintenancePrediction:
    """Overall maintenance prediction for a machine."""
    machine_id: str
    health_score: float  # 0-100
    failure_risk: float  # 0-1
    days_until_maintenance: float
    confidence: float

    # Component health
    component_health: Dict[str, float] = field(default_factory=dict)

    # Upcoming maintenance
    schedule: Optional[MaintenanceSchedule] = None

    # Anomalies detected
    anomalies: List[str] = field(default_factory=list)

    # Recommendations
    immediate_actions: List[str] = field(default_factory=list)
    planned_actions: List[str] = field(default_factory=list)

    predicted_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "machine_id": self.machine_id,
            "health_score": self.health_score,
            "failure_risk": self.failure_risk,
            "days_until_maintenance": self.days_until_maintenance,
            "confidence": self.confidence,
            "component_health": self.component_health,
            "anomalies": self.anomalies,
            "immediate_actions": self.immediate_actions,
            "planned_actions": self.planned_actions,
            "schedule": self.schedule.to_dict() if self.schedule else None,
            "predicted_at": self.predicted_at.isoformat(),
        }


@dataclass
class MachineState:
    """Current state of a machine."""
    machine_id: str
    machine_type: str  # mill, lathe, router, etc.

    # Runtime metrics
    total_runtime_hours: float = 0.0
    runtime_since_last_maintenance: float = 0.0
    power_cycles: int = 0

    # Current sensor readings
    spindle_vibration: float = 0.0  # g
    x_axis_vibration: float = 0.0
    y_axis_vibration: float = 0.0
    z_axis_vibration: float = 0.0
    spindle_temperature: float = 0.0  # °C
    coolant_temperature: float = 0.0
    coolant_level: float = 100.0  # %
    air_pressure: float = 0.0  # bar

    # Axis backlash measurements
    x_backlash: float = 0.0  # mm
    y_backlash: float = 0.0
    z_backlash: float = 0.0

    # Error counts
    alarm_count_30d: int = 0
    servo_error_count_30d: int = 0
    spindle_overload_count_30d: int = 0

    # Last maintenance dates
    last_maintenance: Optional[datetime] = None
    last_spindle_service: Optional[datetime] = None
    last_way_lubrication: Optional[datetime] = None
    last_coolant_change: Optional[datetime] = None


class MaintenancePredictor:
    """
    Predicts maintenance needs for CNC machines.

    Uses multiple signals:
    - Runtime-based scheduling
    - Condition-based monitoring
    - Failure pattern recognition
    - Component lifecycle tracking
    """

    # Standard maintenance intervals (hours)
    MAINTENANCE_INTERVALS = {
        "spindle_lubrication": 500,
        "way_lubrication": 100,
        "coolant_check": 40,
        "coolant_change": 2000,
        "filter_check": 250,
        "filter_change": 1000,
        "spindle_service": 5000,
        "ballscrew_check": 2000,
        "axis_calibration": 3000,
        "full_service": 10000,
    }

    # Component failure indicators
    FAILURE_THRESHOLDS = {
        "spindle_vibration": {"warning": 1.0, "critical": 2.0},
        "axis_vibration": {"warning": 0.5, "critical": 1.0},
        "backlash": {"warning": 0.02, "critical": 0.05},  # mm
        "temperature_rise": {"warning": 20, "critical": 35},  # °C above ambient
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_ml: bool = False,
    ):
        """
        Initialize maintenance predictor.

        Args:
            model_path: Path to ML model
            use_ml: Whether to use ML predictions
        """
        self.model_path = model_path
        self.use_ml = use_ml
        self._model = None

        # Historical data for trend analysis
        self._sensor_history: Dict[str, List[Dict[str, Any]]] = {}
        self._maintenance_history: Dict[str, List[Dict[str, Any]]] = {}

        if use_ml and model_path:
            self._load_model()

    def _load_model(self):
        """Load ML model from disk."""
        try:
            import joblib
            self._model = joblib.load(f"{self.model_path}/maintenance_model.pkl")
            logger.info("Loaded maintenance prediction ML model")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")
            self.use_ml = False

    def predict(
        self,
        state: MachineState,
        planning_horizon_days: int = 30,
    ) -> MaintenancePrediction:
        """
        Predict maintenance needs for a machine.

        Args:
            state: Current machine state
            planning_horizon_days: Days to plan ahead

        Returns:
            Maintenance prediction
        """
        # Calculate component health scores
        component_health = self._assess_component_health(state)

        # Calculate overall health score
        health_score = sum(component_health.values()) / len(component_health) if component_health else 100.0

        # Detect anomalies
        anomalies = self._detect_anomalies(state)

        # Calculate failure risk
        failure_risk = self._calculate_failure_risk(state, anomalies)

        # Generate maintenance schedule
        schedule = self._generate_schedule(state, planning_horizon_days)

        # Calculate days until maintenance needed
        if schedule.tasks:
            urgent_tasks = [
                t for t in schedule.tasks
                if t.priority in [MaintenancePriority.CRITICAL, MaintenancePriority.HIGH]
            ]
            if urgent_tasks:
                earliest = min(t.due_date for t in urgent_tasks if t.due_date)
                days_until = (earliest - datetime.now()).days if earliest else 0
            else:
                days_until = 30
        else:
            days_until = 30

        # Generate recommendations
        immediate_actions, planned_actions = self._generate_recommendations(
            state, anomalies, schedule
        )

        # Calculate confidence
        confidence = self._calculate_confidence(state)

        return MaintenancePrediction(
            machine_id=state.machine_id,
            health_score=health_score,
            failure_risk=failure_risk,
            days_until_maintenance=max(0, days_until),
            confidence=confidence,
            component_health=component_health,
            schedule=schedule,
            anomalies=anomalies,
            immediate_actions=immediate_actions,
            planned_actions=planned_actions,
        )

    def _assess_component_health(
        self,
        state: MachineState,
    ) -> Dict[str, float]:
        """Assess health of individual components."""
        health = {}

        # Spindle health
        spindle_health = 100.0
        if state.spindle_vibration > self.FAILURE_THRESHOLDS["spindle_vibration"]["critical"]:
            spindle_health -= 50
        elif state.spindle_vibration > self.FAILURE_THRESHOLDS["spindle_vibration"]["warning"]:
            spindle_health -= 25

        if state.spindle_temperature > 60:
            spindle_health -= (state.spindle_temperature - 60) * 2

        health["spindle"] = max(0, spindle_health)

        # X-axis health
        x_health = 100.0
        if state.x_axis_vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["critical"]:
            x_health -= 40
        elif state.x_axis_vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["warning"]:
            x_health -= 20

        if state.x_backlash > self.FAILURE_THRESHOLDS["backlash"]["critical"]:
            x_health -= 40
        elif state.x_backlash > self.FAILURE_THRESHOLDS["backlash"]["warning"]:
            x_health -= 20

        health["x_axis"] = max(0, x_health)

        # Y-axis health
        y_health = 100.0
        if state.y_axis_vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["critical"]:
            y_health -= 40
        elif state.y_axis_vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["warning"]:
            y_health -= 20

        if state.y_backlash > self.FAILURE_THRESHOLDS["backlash"]["critical"]:
            y_health -= 40
        elif state.y_backlash > self.FAILURE_THRESHOLDS["backlash"]["warning"]:
            y_health -= 20

        health["y_axis"] = max(0, y_health)

        # Z-axis health
        z_health = 100.0
        if state.z_axis_vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["critical"]:
            z_health -= 40
        elif state.z_axis_vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["warning"]:
            z_health -= 20

        if state.z_backlash > self.FAILURE_THRESHOLDS["backlash"]["critical"]:
            z_health -= 40
        elif state.z_backlash > self.FAILURE_THRESHOLDS["backlash"]["warning"]:
            z_health -= 20

        health["z_axis"] = max(0, z_health)

        # Coolant system health
        coolant_health = 100.0
        if state.coolant_level < 50:
            coolant_health -= (50 - state.coolant_level)
        if state.coolant_temperature > 30:
            coolant_health -= (state.coolant_temperature - 30) * 2

        health["coolant_system"] = max(0, coolant_health)

        # General health based on error counts
        error_health = 100.0
        error_health -= state.alarm_count_30d * 2
        error_health -= state.servo_error_count_30d * 5
        error_health -= state.spindle_overload_count_30d * 10

        health["error_rate"] = max(0, error_health)

        return health

    def _detect_anomalies(self, state: MachineState) -> List[str]:
        """Detect anomalies in machine state."""
        anomalies = []

        # Vibration anomalies
        if state.spindle_vibration > self.FAILURE_THRESHOLDS["spindle_vibration"]["critical"]:
            anomalies.append(f"Critical spindle vibration: {state.spindle_vibration:.2f}g")
        elif state.spindle_vibration > self.FAILURE_THRESHOLDS["spindle_vibration"]["warning"]:
            anomalies.append(f"Elevated spindle vibration: {state.spindle_vibration:.2f}g")

        # Axis anomalies
        for axis, vibration in [
            ("X", state.x_axis_vibration),
            ("Y", state.y_axis_vibration),
            ("Z", state.z_axis_vibration),
        ]:
            if vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["critical"]:
                anomalies.append(f"Critical {axis}-axis vibration: {vibration:.2f}g")
            elif vibration > self.FAILURE_THRESHOLDS["axis_vibration"]["warning"]:
                anomalies.append(f"Elevated {axis}-axis vibration: {vibration:.2f}g")

        # Backlash anomalies
        for axis, backlash in [
            ("X", state.x_backlash),
            ("Y", state.y_backlash),
            ("Z", state.z_backlash),
        ]:
            if backlash > self.FAILURE_THRESHOLDS["backlash"]["critical"]:
                anomalies.append(f"Critical {axis}-axis backlash: {backlash:.3f}mm")
            elif backlash > self.FAILURE_THRESHOLDS["backlash"]["warning"]:
                anomalies.append(f"Elevated {axis}-axis backlash: {backlash:.3f}mm")

        # Temperature anomalies
        if state.spindle_temperature > 80:
            anomalies.append(f"High spindle temperature: {state.spindle_temperature:.1f}°C")

        # Coolant anomalies
        if state.coolant_level < 30:
            anomalies.append(f"Low coolant level: {state.coolant_level:.0f}%")

        # Error rate anomalies
        if state.servo_error_count_30d > 10:
            anomalies.append(f"High servo error rate: {state.servo_error_count_30d} in 30 days")
        if state.spindle_overload_count_30d > 5:
            anomalies.append(f"Frequent spindle overloads: {state.spindle_overload_count_30d} in 30 days")

        return anomalies

    def _calculate_failure_risk(
        self,
        state: MachineState,
        anomalies: List[str],
    ) -> float:
        """Calculate probability of failure."""
        risk = 0.0

        # Base risk from runtime
        runtime_factor = state.runtime_since_last_maintenance / 1000
        risk += min(0.3, runtime_factor * 0.1)

        # Risk from anomalies
        critical_anomalies = sum(1 for a in anomalies if "critical" in a.lower())
        warning_anomalies = len(anomalies) - critical_anomalies

        risk += critical_anomalies * 0.15
        risk += warning_anomalies * 0.05

        # Risk from error patterns
        if state.servo_error_count_30d > 5:
            risk += 0.1
        if state.spindle_overload_count_30d > 3:
            risk += 0.1

        # Risk from time since maintenance
        if state.last_maintenance:
            days_since = (datetime.now() - state.last_maintenance).days
            if days_since > 180:  # 6 months
                risk += 0.15
            elif days_since > 90:  # 3 months
                risk += 0.08

        return min(1.0, risk)

    def _generate_schedule(
        self,
        state: MachineState,
        planning_horizon_days: int,
    ) -> MaintenanceSchedule:
        """Generate maintenance schedule."""
        tasks = []
        now = datetime.now()
        horizon_end = now + timedelta(days=planning_horizon_days)

        # Check each maintenance type
        for task_name, interval_hours in self.MAINTENANCE_INTERVALS.items():
            # Estimate next due date based on runtime
            hours_until_due = interval_hours - (state.runtime_since_last_maintenance % interval_hours)

            # Assume 8 operating hours per day
            days_until_due = hours_until_due / 8
            due_date = now + timedelta(days=days_until_due)

            if due_date <= horizon_end:
                # Determine priority
                if days_until_due <= 3:
                    priority = MaintenancePriority.HIGH
                elif days_until_due <= 7:
                    priority = MaintenancePriority.MEDIUM
                else:
                    priority = MaintenancePriority.LOW

                # Override priority for critical tasks
                if task_name in ["spindle_service", "full_service"] and days_until_due <= 14:
                    priority = MaintenancePriority.HIGH

                tasks.append(MaintenanceTask(
                    task_id=f"{state.machine_id}_{task_name}",
                    name=task_name.replace("_", " ").title(),
                    component=self._get_component_for_task(task_name),
                    maintenance_type=MaintenanceType.PREVENTIVE,
                    priority=priority,
                    estimated_duration_minutes=self._get_duration_for_task(task_name),
                    due_date=due_date,
                    interval_hours=interval_hours,
                    triggered_by="runtime",
                    trigger_value=state.runtime_since_last_maintenance,
                ))

        # Add condition-based tasks from anomalies
        anomalies = self._detect_anomalies(state)
        for anomaly in anomalies:
            if "spindle" in anomaly.lower():
                tasks.append(MaintenanceTask(
                    task_id=f"{state.machine_id}_spindle_inspection",
                    name="Spindle Inspection",
                    component="spindle",
                    maintenance_type=MaintenanceType.PREDICTIVE,
                    priority=MaintenancePriority.HIGH if "critical" in anomaly.lower() else MaintenancePriority.MEDIUM,
                    estimated_duration_minutes=60,
                    due_date=now + timedelta(days=1 if "critical" in anomaly.lower() else 7),
                    triggered_by="sensor",
                    notes=[anomaly],
                ))

            if "backlash" in anomaly.lower():
                axis = anomaly.split("-")[0][-1]  # Extract X, Y, or Z
                tasks.append(MaintenanceTask(
                    task_id=f"{state.machine_id}_{axis}_axis_adjustment",
                    name=f"{axis}-Axis Backlash Adjustment",
                    component=f"{axis.lower()}_axis",
                    maintenance_type=MaintenanceType.PREDICTIVE,
                    priority=MaintenancePriority.HIGH if "critical" in anomaly.lower() else MaintenancePriority.MEDIUM,
                    estimated_duration_minutes=120,
                    due_date=now + timedelta(days=3 if "critical" in anomaly.lower() else 14),
                    triggered_by="sensor",
                    notes=[anomaly],
                ))

        # Sort by priority and due date
        priority_order = {
            MaintenancePriority.CRITICAL: 0,
            MaintenancePriority.HIGH: 1,
            MaintenancePriority.MEDIUM: 2,
            MaintenancePriority.LOW: 3,
        }
        tasks.sort(key=lambda t: (priority_order.get(t.priority, 4), t.due_date or now))

        # Create schedule
        total_minutes = sum(t.estimated_duration_minutes for t in tasks)
        critical_count = sum(1 for t in tasks if t.priority == MaintenancePriority.CRITICAL)

        schedule = MaintenanceSchedule(
            machine_id=state.machine_id,
            tasks=tasks,
            total_tasks=len(tasks),
            critical_tasks=critical_count,
            total_estimated_hours=total_minutes / 60,
            health_score=sum(self._assess_component_health(state).values()) / 6,
        )

        if tasks:
            schedule.next_maintenance_date = tasks[0].due_date
            if critical_count > 0:
                schedule.maintenance_window_recommendation = "Schedule maintenance immediately"
            elif any(t.priority == MaintenancePriority.HIGH for t in tasks):
                schedule.maintenance_window_recommendation = "Schedule maintenance within this week"
            else:
                schedule.maintenance_window_recommendation = "Schedule during next planned downtime"

        return schedule

    def _get_component_for_task(self, task_name: str) -> str:
        """Get component name for a maintenance task."""
        component_map = {
            "spindle_lubrication": "spindle",
            "way_lubrication": "ways",
            "coolant_check": "coolant_system",
            "coolant_change": "coolant_system",
            "filter_check": "coolant_system",
            "filter_change": "coolant_system",
            "spindle_service": "spindle",
            "ballscrew_check": "ballscrews",
            "axis_calibration": "axes",
            "full_service": "machine",
        }
        return component_map.get(task_name, "general")

    def _get_duration_for_task(self, task_name: str) -> int:
        """Get estimated duration for a maintenance task."""
        duration_map = {
            "spindle_lubrication": 15,
            "way_lubrication": 30,
            "coolant_check": 15,
            "coolant_change": 120,
            "filter_check": 20,
            "filter_change": 45,
            "spindle_service": 480,  # 8 hours
            "ballscrew_check": 60,
            "axis_calibration": 240,
            "full_service": 960,  # 16 hours
        }
        return duration_map.get(task_name, 60)

    def _generate_recommendations(
        self,
        state: MachineState,
        anomalies: List[str],
        schedule: MaintenanceSchedule,
    ) -> Tuple[List[str], List[str]]:
        """Generate maintenance recommendations."""
        immediate = []
        planned = []

        # Critical anomalies require immediate attention
        for anomaly in anomalies:
            if "critical" in anomaly.lower():
                immediate.append(f"Investigate: {anomaly}")

        # Check coolant
        if state.coolant_level < 30:
            immediate.append("Refill coolant immediately")
        elif state.coolant_level < 50:
            planned.append("Schedule coolant refill")

        # Check maintenance backlog
        if schedule.critical_tasks > 0:
            immediate.append(f"Address {schedule.critical_tasks} critical maintenance task(s)")

        # Runtime-based recommendations
        if state.runtime_since_last_maintenance > 500:
            planned.append("Schedule preventive maintenance (>500 hours since last)")

        # Error pattern recommendations
        if state.servo_error_count_30d > 5:
            planned.append("Investigate servo error pattern - may indicate alignment issue")

        if state.spindle_overload_count_30d > 3:
            planned.append("Review spindle load parameters - may need derating or service")

        return immediate, planned

    def _calculate_confidence(self, state: MachineState) -> float:
        """Calculate prediction confidence."""
        confidence = 0.7  # Base confidence

        # More sensor data = higher confidence
        sensor_count = sum([
            state.spindle_vibration > 0,
            state.x_axis_vibration > 0,
            state.y_axis_vibration > 0,
            state.z_axis_vibration > 0,
            state.spindle_temperature > 0,
        ])
        confidence += sensor_count * 0.04

        # Maintenance history improves confidence
        if state.last_maintenance:
            confidence += 0.05

        # Long runtime history improves confidence
        if state.total_runtime_hours > 1000:
            confidence += 0.05

        return min(0.95, confidence)

    def record_sensor_reading(
        self,
        machine_id: str,
        readings: Dict[str, float],
    ):
        """Record sensor readings for trend analysis."""
        if machine_id not in self._sensor_history:
            self._sensor_history[machine_id] = []

        self._sensor_history[machine_id].append({
            "timestamp": datetime.now().isoformat(),
            **readings,
        })

        # Keep last 10000 readings
        if len(self._sensor_history[machine_id]) > 10000:
            self._sensor_history[machine_id] = self._sensor_history[machine_id][-10000:]

    def record_maintenance(
        self,
        machine_id: str,
        task_name: str,
        performed_at: datetime,
        duration_minutes: int,
        notes: str = "",
    ):
        """Record completed maintenance."""
        if machine_id not in self._maintenance_history:
            self._maintenance_history[machine_id] = []

        self._maintenance_history[machine_id].append({
            "task": task_name,
            "performed_at": performed_at.isoformat(),
            "duration_minutes": duration_minutes,
            "notes": notes,
        })

    def get_maintenance_history(
        self,
        machine_id: str,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """Get maintenance history for a machine."""
        if machine_id not in self._maintenance_history:
            return []

        cutoff = datetime.now() - timedelta(days=days)
        return [
            m for m in self._maintenance_history[machine_id]
            if datetime.fromisoformat(m["performed_at"]) >= cutoff
        ]
