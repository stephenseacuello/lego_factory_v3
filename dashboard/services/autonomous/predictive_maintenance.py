"""
V8 Predictive Maintenance Engine
=================================

AI-powered predictive maintenance for equipment:
- Remaining Useful Life (RUL) prediction
- Anomaly detection in sensor data
- Automatic work order generation
- Maintenance scheduling optimization
- Failure mode prediction

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import logging
import math
import random
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================
# Enums
# ============================================

class MaintenanceType(Enum):
    """Types of maintenance."""
    PREVENTIVE = "preventive"
    PREDICTIVE = "predictive"
    CORRECTIVE = "corrective"
    CONDITION_BASED = "condition_based"
    EMERGENCY = "emergency"


class MaintenancePriority(Enum):
    """Maintenance priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class EquipmentCondition(Enum):
    """Equipment condition states."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    FAILED = "failed"


class FailureMode(Enum):
    """Common equipment failure modes."""
    WEAR = "wear"
    FATIGUE = "fatigue"
    CORROSION = "corrosion"
    OVERHEATING = "overheating"
    VIBRATION = "vibration"
    CONTAMINATION = "contamination"
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"


class SensorType(Enum):
    """Types of monitoring sensors."""
    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    PRESSURE = "pressure"
    CURRENT = "current"
    VOLTAGE = "voltage"
    ACOUSTIC = "acoustic"
    OIL_ANALYSIS = "oil_analysis"
    CYCLE_COUNT = "cycle_count"


# ============================================
# Data Classes
# ============================================

@dataclass
class SensorReading:
    """Individual sensor reading."""
    sensor_id: str
    sensor_type: SensorType
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    quality: float = 1.0  # Data quality 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "quality": self.quality,
        }


@dataclass
class EquipmentHealth:
    """Equipment health assessment."""
    equipment_id: str
    name: str
    condition: EquipmentCondition
    health_score: float  # 0-100
    remaining_useful_life_hours: float
    confidence: float  # 0-1
    last_assessment: datetime = field(default_factory=datetime.now)
    sensor_readings: Dict[str, float] = field(default_factory=dict)
    degradation_rate: float = 0.0  # % per hour
    failure_probability_24h: float = 0.0
    failure_probability_7d: float = 0.0
    predicted_failure_modes: List[FailureMode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "equipment_id": self.equipment_id,
            "name": self.name,
            "condition": self.condition.value,
            "health_score": round(self.health_score, 1),
            "remaining_useful_life_hours": round(self.remaining_useful_life_hours, 1),
            "confidence": round(self.confidence, 2),
            "last_assessment": self.last_assessment.isoformat(),
            "sensor_readings": self.sensor_readings,
            "degradation_rate": round(self.degradation_rate, 4),
            "failure_probability_24h": round(self.failure_probability_24h, 3),
            "failure_probability_7d": round(self.failure_probability_7d, 3),
            "predicted_failure_modes": [m.value for m in self.predicted_failure_modes],
        }


@dataclass
class MaintenanceWorkOrder:
    """Maintenance work order."""
    work_order_id: str
    equipment_id: str
    equipment_name: str
    maintenance_type: MaintenanceType
    priority: MaintenancePriority
    title: str
    description: str
    estimated_duration_hours: float
    required_parts: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_for: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    failure_modes: List[FailureMode] = field(default_factory=list)
    predicted_rul_at_creation: float = 0.0
    auto_generated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "equipment_id": self.equipment_id,
            "equipment_name": self.equipment_name,
            "maintenance_type": self.maintenance_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "estimated_duration_hours": self.estimated_duration_hours,
            "required_parts": self.required_parts,
            "required_skills": self.required_skills,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "assigned_to": self.assigned_to,
            "failure_modes": [m.value for m in self.failure_modes],
            "auto_generated": self.auto_generated,
        }


@dataclass
class AnomalyDetection:
    """Detected anomaly in sensor data."""
    anomaly_id: str
    equipment_id: str
    sensor_type: SensorType
    anomaly_score: float  # 0-1, higher = more anomalous
    expected_value: float
    actual_value: float
    deviation_percentage: float
    timestamp: datetime = field(default_factory=datetime.now)
    is_critical: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "equipment_id": self.equipment_id,
            "sensor_type": self.sensor_type.value,
            "anomaly_score": round(self.anomaly_score, 3),
            "expected_value": round(self.expected_value, 2),
            "actual_value": round(self.actual_value, 2),
            "deviation_percentage": round(self.deviation_percentage, 1),
            "timestamp": self.timestamp.isoformat(),
            "is_critical": self.is_critical,
        }


# ============================================
# Predictive Maintenance Engine
# ============================================

class PredictiveMaintenanceEngine:
    """
    AI-powered predictive maintenance engine.

    Capabilities:
    - Real-time equipment health monitoring
    - Remaining Useful Life prediction
    - Anomaly detection
    - Automatic work order generation
    - Maintenance schedule optimization
    """

    def __init__(self):
        self._equipment: Dict[str, EquipmentHealth] = {}
        self._sensor_history: Dict[str, deque] = {}
        self._work_orders: Dict[str, MaintenanceWorkOrder] = {}
        self._anomalies: Dict[str, AnomalyDetection] = {}
        self._lock = threading.RLock()

        # Configuration
        self._sensor_history_size = 1000
        self._anomaly_threshold = 0.7
        self._auto_work_order_rul_threshold = 168  # 7 days in hours

        # Baseline parameters for different equipment types
        self._equipment_baselines: Dict[str, Dict[str, Any]] = {
            "printer": {
                "temperature": {"mean": 45.0, "std": 5.0, "max": 70.0},
                "vibration": {"mean": 0.5, "std": 0.1, "max": 2.0},
                "cycle_count": {"mtbf": 50000},
            },
            "cnc": {
                "temperature": {"mean": 35.0, "std": 3.0, "max": 55.0},
                "vibration": {"mean": 1.0, "std": 0.2, "max": 3.0},
                "current": {"mean": 15.0, "std": 2.0, "max": 25.0},
            },
            "robot": {
                "temperature": {"mean": 40.0, "std": 4.0, "max": 60.0},
                "vibration": {"mean": 0.3, "std": 0.05, "max": 1.0},
                "cycle_count": {"mtbf": 100000},
            },
            "conveyor": {
                "temperature": {"mean": 30.0, "std": 3.0, "max": 50.0},
                "vibration": {"mean": 0.8, "std": 0.15, "max": 2.5},
            },
        }

        # Failure mode mappings
        self._failure_mode_indicators: Dict[SensorType, List[FailureMode]] = {
            SensorType.TEMPERATURE: [FailureMode.OVERHEATING, FailureMode.ELECTRICAL],
            SensorType.VIBRATION: [FailureMode.WEAR, FailureMode.MECHANICAL, FailureMode.FATIGUE],
            SensorType.CURRENT: [FailureMode.ELECTRICAL, FailureMode.MECHANICAL],
            SensorType.PRESSURE: [FailureMode.WEAR, FailureMode.CONTAMINATION],
            SensorType.ACOUSTIC: [FailureMode.MECHANICAL, FailureMode.WEAR],
            SensorType.OIL_ANALYSIS: [FailureMode.CONTAMINATION, FailureMode.WEAR],
        }

        logger.info("PredictiveMaintenanceEngine initialized")

    # ============================================
    # Equipment Registration
    # ============================================

    def register_equipment(
        self,
        equipment_id: str,
        name: str,
        equipment_type: str = "generic",
        initial_health_score: float = 100.0,
    ) -> EquipmentHealth:
        """Register equipment for predictive maintenance monitoring."""
        with self._lock:
            health = EquipmentHealth(
                equipment_id=equipment_id,
                name=name,
                condition=EquipmentCondition.EXCELLENT,
                health_score=initial_health_score,
                remaining_useful_life_hours=8760,  # 1 year default
                confidence=0.5,  # Low confidence initially
            )

            self._equipment[equipment_id] = health
            self._sensor_history[equipment_id] = deque(maxlen=self._sensor_history_size)

            logger.info(f"Registered equipment for PdM: {name} ({equipment_id})")
            return health

    def get_equipment_health(self, equipment_id: str) -> Optional[EquipmentHealth]:
        """Get current equipment health assessment."""
        return self._equipment.get(equipment_id)

    # ============================================
    # Sensor Data Ingestion
    # ============================================

    def ingest_sensor_data(
        self,
        equipment_id: str,
        sensor_type: SensorType,
        value: float,
        unit: str = "",
        quality: float = 1.0,
    ) -> Optional[AnomalyDetection]:
        """
        Ingest sensor reading and check for anomalies.

        Returns anomaly detection if anomaly found, None otherwise.
        """
        if equipment_id not in self._equipment:
            return None

        reading = SensorReading(
            sensor_id=f"{equipment_id}_{sensor_type.value}",
            sensor_type=sensor_type,
            value=value,
            unit=unit,
            quality=quality,
        )

        with self._lock:
            # Store reading
            self._sensor_history[equipment_id].append(reading)

            # Update health metrics
            health = self._equipment[equipment_id]
            health.sensor_readings[sensor_type.value] = value

            # Check for anomaly
            anomaly = self._detect_anomaly(equipment_id, reading)

            # Update health assessment
            self._update_health_assessment(equipment_id)

            return anomaly

    def ingest_batch_readings(
        self,
        equipment_id: str,
        readings: List[Tuple[SensorType, float, str]],
    ) -> List[AnomalyDetection]:
        """Ingest multiple sensor readings at once."""
        anomalies = []
        for sensor_type, value, unit in readings:
            anomaly = self.ingest_sensor_data(equipment_id, sensor_type, value, unit)
            if anomaly:
                anomalies.append(anomaly)
        return anomalies

    # ============================================
    # Anomaly Detection
    # ============================================

    def _detect_anomaly(
        self,
        equipment_id: str,
        reading: SensorReading,
    ) -> Optional[AnomalyDetection]:
        """Detect anomalies in sensor readings."""
        history = list(self._sensor_history[equipment_id])
        sensor_history = [
            r for r in history
            if r.sensor_type == reading.sensor_type
        ]

        if len(sensor_history) < 10:
            return None  # Not enough data

        # Calculate statistics from recent history
        values = [r.value for r in sensor_history[-100:]]
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 1.0

        # Calculate z-score
        z_score = abs(reading.value - mean) / std if std > 0 else 0

        # Calculate anomaly score (0-1)
        anomaly_score = min(1.0, z_score / 4)  # Normalize to 0-1

        if anomaly_score >= self._anomaly_threshold:
            deviation = ((reading.value - mean) / mean * 100) if mean != 0 else 0

            anomaly = AnomalyDetection(
                anomaly_id=f"anomaly-{uuid.uuid4().hex[:8]}",
                equipment_id=equipment_id,
                sensor_type=reading.sensor_type,
                anomaly_score=anomaly_score,
                expected_value=mean,
                actual_value=reading.value,
                deviation_percentage=deviation,
                is_critical=anomaly_score >= 0.9,
            )

            self._anomalies[anomaly.anomaly_id] = anomaly

            # Update failure mode predictions
            health = self._equipment[equipment_id]
            failure_modes = self._failure_mode_indicators.get(reading.sensor_type, [])
            for mode in failure_modes:
                if mode not in health.predicted_failure_modes:
                    health.predicted_failure_modes.append(mode)

            logger.warning(
                f"Anomaly detected: {equipment_id} - {reading.sensor_type.value} "
                f"= {reading.value} (expected {mean:.2f})"
            )

            # Auto-generate work order for critical anomalies
            if anomaly.is_critical:
                self._auto_generate_work_order(equipment_id, anomaly)

            return anomaly

        return None

    # ============================================
    # Health Assessment
    # ============================================

    def _update_health_assessment(self, equipment_id: str):
        """Update equipment health assessment based on sensor data."""
        health = self._equipment.get(equipment_id)
        if not health:
            return

        # Calculate health score based on sensor readings and anomalies
        base_score = 100.0
        degradation_factors = []

        # Check recent anomalies
        recent_anomalies = [
            a for a in self._anomalies.values()
            if a.equipment_id == equipment_id
            and (datetime.now() - a.timestamp).total_seconds() < 3600
        ]

        for anomaly in recent_anomalies:
            degradation_factors.append(anomaly.anomaly_score * 20)

        # Check sensor values against thresholds
        for sensor_type, value in health.sensor_readings.items():
            # Simple threshold check (would use ML model in production)
            if sensor_type == "temperature" and value > 60:
                degradation_factors.append((value - 60) / 10 * 15)
            elif sensor_type == "vibration" and value > 1.5:
                degradation_factors.append((value - 1.5) * 20)

        # Calculate final health score
        total_degradation = sum(degradation_factors)
        health.health_score = max(0, base_score - total_degradation)

        # Update condition
        if health.health_score >= 90:
            health.condition = EquipmentCondition.EXCELLENT
        elif health.health_score >= 75:
            health.condition = EquipmentCondition.GOOD
        elif health.health_score >= 50:
            health.condition = EquipmentCondition.FAIR
        elif health.health_score >= 25:
            health.condition = EquipmentCondition.POOR
        elif health.health_score > 0:
            health.condition = EquipmentCondition.CRITICAL
        else:
            health.condition = EquipmentCondition.FAILED

        # Calculate RUL (simplified exponential degradation model)
        if total_degradation > 0:
            health.degradation_rate = total_degradation / 100  # % per hour
            health.remaining_useful_life_hours = health.health_score / health.degradation_rate
        else:
            health.degradation_rate = 0.001  # Minimal degradation
            health.remaining_useful_life_hours = 8760  # 1 year

        # Calculate failure probabilities
        health.failure_probability_24h = self._calculate_failure_probability(health, 24)
        health.failure_probability_7d = self._calculate_failure_probability(health, 168)

        # Update confidence based on data availability
        history_size = len(self._sensor_history.get(equipment_id, []))
        health.confidence = min(0.95, history_size / 500)

        health.last_assessment = datetime.now()

        # Auto-generate work order if RUL is low
        if health.remaining_useful_life_hours < self._auto_work_order_rul_threshold:
            self._auto_generate_preventive_work_order(equipment_id)

    def _calculate_failure_probability(
        self,
        health: EquipmentHealth,
        hours: float,
    ) -> float:
        """Calculate probability of failure within given hours."""
        if health.health_score >= 90:
            base_prob = 0.001
        elif health.health_score >= 75:
            base_prob = 0.01
        elif health.health_score >= 50:
            base_prob = 0.05
        elif health.health_score >= 25:
            base_prob = 0.15
        else:
            base_prob = 0.4

        # Adjust by time horizon
        time_factor = hours / 168  # Normalized to 7 days
        return min(0.99, base_prob * time_factor * (1 + health.degradation_rate * 10))

    # ============================================
    # RUL Prediction
    # ============================================

    def predict_rul(
        self,
        equipment_id: str,
        include_uncertainty: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict Remaining Useful Life with uncertainty bounds.

        Returns prediction with confidence intervals.
        """
        health = self._equipment.get(equipment_id)
        if not health:
            return {"error": "Equipment not found"}

        base_rul = health.remaining_useful_life_hours
        confidence = health.confidence

        if include_uncertainty:
            # Calculate uncertainty bounds
            uncertainty = base_rul * (1 - confidence) * 0.5
            lower_bound = max(0, base_rul - uncertainty)
            upper_bound = base_rul + uncertainty

            return {
                "equipment_id": equipment_id,
                "predicted_rul_hours": round(base_rul, 1),
                "lower_bound_hours": round(lower_bound, 1),
                "upper_bound_hours": round(upper_bound, 1),
                "confidence": round(confidence, 2),
                "predicted_failure_date": (
                    datetime.now() + timedelta(hours=base_rul)
                ).isoformat(),
                "failure_modes": [m.value for m in health.predicted_failure_modes],
                "health_score": round(health.health_score, 1),
            }
        else:
            return {
                "equipment_id": equipment_id,
                "predicted_rul_hours": round(base_rul, 1),
                "confidence": round(confidence, 2),
            }

    # ============================================
    # Work Order Management
    # ============================================

    def _auto_generate_work_order(
        self,
        equipment_id: str,
        anomaly: AnomalyDetection,
    ):
        """Auto-generate work order for critical anomaly."""
        health = self._equipment.get(equipment_id)
        if not health:
            return

        # Check for existing open work order
        existing = [
            wo for wo in self._work_orders.values()
            if wo.equipment_id == equipment_id and wo.completed_at is None
        ]
        if existing:
            return  # Already has open work order

        work_order = MaintenanceWorkOrder(
            work_order_id=f"WO-{uuid.uuid4().hex[:8]}",
            equipment_id=equipment_id,
            equipment_name=health.name,
            maintenance_type=MaintenanceType.CONDITION_BASED,
            priority=MaintenancePriority.HIGH if anomaly.is_critical else MaintenancePriority.MEDIUM,
            title=f"Investigate {anomaly.sensor_type.value} anomaly on {health.name}",
            description=(
                f"Anomaly detected in {anomaly.sensor_type.value} readings. "
                f"Expected: {anomaly.expected_value:.2f}, Actual: {anomaly.actual_value:.2f}. "
                f"Deviation: {anomaly.deviation_percentage:.1f}%"
            ),
            estimated_duration_hours=2.0,
            failure_modes=health.predicted_failure_modes.copy(),
            predicted_rul_at_creation=health.remaining_useful_life_hours,
            auto_generated=True,
        )

        self._work_orders[work_order.work_order_id] = work_order
        logger.info(f"Auto-generated work order: {work_order.work_order_id}")

    def _auto_generate_preventive_work_order(self, equipment_id: str):
        """Auto-generate preventive work order for low RUL."""
        health = self._equipment.get(equipment_id)
        if not health:
            return

        # Check for existing open work order
        existing = [
            wo for wo in self._work_orders.values()
            if wo.equipment_id == equipment_id and wo.completed_at is None
        ]
        if existing:
            return

        if health.condition == EquipmentCondition.CRITICAL:
            priority = MaintenancePriority.CRITICAL
        elif health.condition == EquipmentCondition.POOR:
            priority = MaintenancePriority.HIGH
        else:
            priority = MaintenancePriority.MEDIUM

        work_order = MaintenanceWorkOrder(
            work_order_id=f"WO-{uuid.uuid4().hex[:8]}",
            equipment_id=equipment_id,
            equipment_name=health.name,
            maintenance_type=MaintenanceType.PREDICTIVE,
            priority=priority,
            title=f"Predictive maintenance for {health.name}",
            description=(
                f"Predicted RUL: {health.remaining_useful_life_hours:.1f} hours. "
                f"Health score: {health.health_score:.1f}%. "
                f"Predicted failure modes: {', '.join(m.value for m in health.predicted_failure_modes)}"
            ),
            estimated_duration_hours=4.0,
            failure_modes=health.predicted_failure_modes.copy(),
            predicted_rul_at_creation=health.remaining_useful_life_hours,
            auto_generated=True,
            scheduled_for=datetime.now() + timedelta(hours=health.remaining_useful_life_hours * 0.5),
        )

        self._work_orders[work_order.work_order_id] = work_order
        logger.info(f"Auto-generated predictive work order: {work_order.work_order_id}")

    def create_work_order(
        self,
        equipment_id: str,
        maintenance_type: MaintenanceType,
        title: str,
        description: str,
        priority: MaintenancePriority = MaintenancePriority.MEDIUM,
        estimated_duration_hours: float = 2.0,
        scheduled_for: Optional[datetime] = None,
    ) -> Optional[MaintenanceWorkOrder]:
        """Manually create a work order."""
        health = self._equipment.get(equipment_id)
        if not health:
            return None

        work_order = MaintenanceWorkOrder(
            work_order_id=f"WO-{uuid.uuid4().hex[:8]}",
            equipment_id=equipment_id,
            equipment_name=health.name,
            maintenance_type=maintenance_type,
            priority=priority,
            title=title,
            description=description,
            estimated_duration_hours=estimated_duration_hours,
            scheduled_for=scheduled_for,
            predicted_rul_at_creation=health.remaining_useful_life_hours,
            auto_generated=False,
        )

        self._work_orders[work_order.work_order_id] = work_order
        return work_order

    def complete_work_order(
        self,
        work_order_id: str,
        notes: str = "",
    ) -> bool:
        """Mark a work order as complete."""
        work_order = self._work_orders.get(work_order_id)
        if not work_order:
            return False

        work_order.completed_at = datetime.now()

        # Reset equipment health after maintenance
        health = self._equipment.get(work_order.equipment_id)
        if health:
            # Partial reset based on maintenance type
            if work_order.maintenance_type in [MaintenanceType.CORRECTIVE, MaintenanceType.EMERGENCY]:
                health.health_score = min(100, health.health_score + 40)
            else:
                health.health_score = min(100, health.health_score + 20)

            health.predicted_failure_modes = []
            self._update_health_assessment(work_order.equipment_id)

        logger.info(f"Completed work order: {work_order_id}")
        return True

    def get_pending_work_orders(
        self,
        equipment_id: Optional[str] = None,
        priority: Optional[MaintenancePriority] = None,
    ) -> List[MaintenanceWorkOrder]:
        """Get pending work orders with optional filtering."""
        orders = [
            wo for wo in self._work_orders.values()
            if wo.completed_at is None
        ]

        if equipment_id:
            orders = [wo for wo in orders if wo.equipment_id == equipment_id]

        if priority:
            orders = [wo for wo in orders if wo.priority == priority]

        # Sort by priority (critical first) then scheduled date
        priority_order = {
            MaintenancePriority.EMERGENCY: 0,
            MaintenancePriority.CRITICAL: 1,
            MaintenancePriority.HIGH: 2,
            MaintenancePriority.MEDIUM: 3,
            MaintenancePriority.LOW: 4,
        }
        orders.sort(key=lambda x: (priority_order.get(x.priority, 5), x.created_at))

        return orders

    # ============================================
    # Statistics and Reporting
    # ============================================

    def get_fleet_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all equipment."""
        condition_counts = {}
        for condition in EquipmentCondition:
            condition_counts[condition.value] = 0

        total_health = 0
        critical_equipment = []

        for health in self._equipment.values():
            condition_counts[health.condition.value] += 1
            total_health += health.health_score

            if health.condition in [EquipmentCondition.CRITICAL, EquipmentCondition.POOR]:
                critical_equipment.append({
                    "equipment_id": health.equipment_id,
                    "name": health.name,
                    "health_score": health.health_score,
                    "rul_hours": health.remaining_useful_life_hours,
                })

        avg_health = total_health / len(self._equipment) if self._equipment else 0

        return {
            "total_equipment": len(self._equipment),
            "average_health_score": round(avg_health, 1),
            "condition_distribution": condition_counts,
            "critical_equipment": critical_equipment,
            "pending_work_orders": len(self.get_pending_work_orders()),
            "recent_anomalies": sum(
                1 for a in self._anomalies.values()
                if (datetime.now() - a.timestamp).total_seconds() < 86400
            ),
        }

    def get_maintenance_schedule(
        self,
        days_ahead: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get maintenance schedule for upcoming period."""
        cutoff = datetime.now() + timedelta(days=days_ahead)

        scheduled = []
        for wo in self._work_orders.values():
            if wo.completed_at is None and wo.scheduled_for:
                if wo.scheduled_for <= cutoff:
                    scheduled.append({
                        "work_order_id": wo.work_order_id,
                        "equipment_name": wo.equipment_name,
                        "type": wo.maintenance_type.value,
                        "priority": wo.priority.value,
                        "scheduled_for": wo.scheduled_for.isoformat(),
                        "duration_hours": wo.estimated_duration_hours,
                    })

        # Add predicted maintenance needs
        for health in self._equipment.values():
            if health.remaining_useful_life_hours < days_ahead * 24:
                predicted_date = datetime.now() + timedelta(
                    hours=health.remaining_useful_life_hours * 0.7
                )
                scheduled.append({
                    "work_order_id": None,
                    "equipment_name": health.name,
                    "type": "predicted",
                    "priority": "medium",
                    "scheduled_for": predicted_date.isoformat(),
                    "duration_hours": 4.0,
                    "predicted": True,
                })

        scheduled.sort(key=lambda x: x["scheduled_for"])
        return scheduled


# ============================================
# Singleton Instance
# ============================================

_engine: Optional[PredictiveMaintenanceEngine] = None
_engine_lock = threading.Lock()


def get_predictive_maintenance_engine() -> PredictiveMaintenanceEngine:
    """Get or create the predictive maintenance engine singleton."""
    global _engine

    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = PredictiveMaintenanceEngine()

    return _engine


__all__ = [
    'MaintenanceType',
    'MaintenancePriority',
    'EquipmentCondition',
    'FailureMode',
    'SensorType',
    'SensorReading',
    'EquipmentHealth',
    'MaintenanceWorkOrder',
    'AnomalyDetection',
    'PredictiveMaintenanceEngine',
    'get_predictive_maintenance_engine',
]
