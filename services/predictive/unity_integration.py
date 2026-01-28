"""
Predictive Maintenance Unity Integration
==========================================
Formats predictive maintenance data for Unity Digital Twin visualization.

Provides:
- Tool wear predictions with 3D overlay positions
- Maintenance calendar for AR display
- Health score gauges and indicators
- Anomaly markers in 3D space
- Trend visualization data

Author: Flask CNC SCADA System
"""

import logging
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from config import get_config

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class AlertSeverity(str, Enum):
    """Severity levels for predictive alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MaintenanceType(str, Enum):
    """Types of maintenance."""
    PREVENTIVE = "preventive"
    PREDICTIVE = "predictive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"


class ComponentType(str, Enum):
    """Machine component types."""
    SPINDLE = "spindle"
    TOOL = "tool"
    BEARING = "bearing"
    MOTOR = "motor"
    BALLSCREW = "ballscrew"
    COOLANT = "coolant"
    ELECTRICAL = "electrical"


class HealthStatus(str, Enum):
    """Component health status."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Position3D:
    """3D position for Unity overlay placement."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class HealthScore:
    """Health score for Unity gauge display."""
    component: ComponentType
    score: float  # 0-100
    status: HealthStatus
    trend: str  # "improving", "stable", "declining"
    confidence: float  # 0-1
    last_updated: float


@dataclass
class ToolWearPrediction:
    """Tool wear prediction for Unity visualization."""
    tool_number: int
    tool_name: str
    current_wear_percent: float  # 0-100
    predicted_life_remaining_hours: float
    predicted_failure_time: Optional[datetime]
    confidence: float
    recommendation: str
    severity: AlertSeverity

    # Unity overlay position (near tool in 3D space)
    overlay_position: Position3D = field(default_factory=Position3D)

    # Visual properties
    color_rgb: Tuple[int, int, int] = (255, 255, 0)  # Yellow default
    pulse_animation: bool = False
    show_trend_arrow: bool = True


@dataclass
class MaintenanceEvent:
    """Scheduled maintenance event for Unity calendar."""
    event_id: str
    machine_id: str
    component: ComponentType
    maintenance_type: MaintenanceType
    scheduled_start: datetime
    scheduled_duration_hours: float
    description: str
    priority: int  # 1-5
    requires_shutdown: bool = False
    parts_needed: List[str] = field(default_factory=list)

    # AR overlay properties
    show_in_ar: bool = True
    ar_icon: str = "wrench"
    ar_color_rgb: Tuple[int, int, int] = (0, 150, 255)


@dataclass
class AnomalyMarker:
    """Anomaly marker for 3D visualization."""
    anomaly_id: str
    machine_id: str
    component: ComponentType
    anomaly_type: str
    severity: AlertSeverity
    detected_at: datetime
    description: str

    # 3D position in machine coordinates
    position: Position3D = field(default_factory=Position3D)

    # Visual properties
    marker_type: str = "sphere"  # sphere, cube, exclamation
    color_rgb: Tuple[int, int, int] = (255, 0, 0)
    size: float = 10.0  # mm
    pulse: bool = True
    show_label: bool = True


@dataclass
class TrendData:
    """Trend data for Unity charts."""
    metric_name: str
    unit: str
    timestamps: List[float]
    values: List[float]
    prediction_timestamps: List[float] = field(default_factory=list)
    prediction_values: List[float] = field(default_factory=list)
    upper_limit: Optional[float] = None
    lower_limit: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


@dataclass
class UnityPredictiveState:
    """Complete predictive state for Unity Digital Twin."""
    machine_id: str
    timestamp: float

    # Health overview
    overall_health_score: float
    health_scores: Dict[str, HealthScore] = field(default_factory=dict)

    # Tool wear
    tool_predictions: List[ToolWearPrediction] = field(default_factory=list)

    # Maintenance
    upcoming_maintenance: List[MaintenanceEvent] = field(default_factory=list)

    # Anomalies
    active_anomalies: List[AnomalyMarker] = field(default_factory=list)

    # Trends (for charts)
    trends: Dict[str, TrendData] = field(default_factory=dict)


# =============================================================================
# Unity Predictive Integration Service
# =============================================================================

class UnityPredictiveIntegration:
    """
    Formats predictive maintenance data for Unity Digital Twin.

    Aggregates predictions from various sources and formats them
    for efficient rendering in Unity with 3D overlays and AR.
    """

    # Color schemes for severity
    SEVERITY_COLORS = {
        AlertSeverity.INFO: (100, 200, 255),      # Light blue
        AlertSeverity.WARNING: (255, 200, 0),     # Yellow
        AlertSeverity.CRITICAL: (255, 100, 0),    # Orange
        AlertSeverity.EMERGENCY: (255, 0, 0),     # Red
    }

    # Component 3D positions (relative to machine origin)
    COMPONENT_POSITIONS = {
        ComponentType.SPINDLE: Position3D(0, 0, 200),
        ComponentType.TOOL: Position3D(0, 0, 150),
        ComponentType.BEARING: Position3D(0, 0, 180),
        ComponentType.MOTOR: Position3D(-100, 0, 100),
        ComponentType.BALLSCREW: Position3D(0, 100, 50),
        ComponentType.COOLANT: Position3D(100, 0, 50),
        ComponentType.ELECTRICAL: Position3D(-100, -100, 100),
    }

    def __init__(self):
        self.config = get_config()
        self._states: Dict[str, UnityPredictiveState] = {}
        self._lock = threading.Lock()

        # Prediction update callbacks
        self._callbacks: List[callable] = []

        logger.info("UnityPredictiveIntegration initialized")

    # =========================================================================
    # State Management
    # =========================================================================

    def get_predictive_state(
        self,
        machine_id: str
    ) -> Optional[UnityPredictiveState]:
        """Get current predictive state for a machine."""
        with self._lock:
            return self._states.get(machine_id)

    def update_health_scores(
        self,
        machine_id: str,
        scores: Dict[str, float],
        trends: Dict[str, str] = None
    ) -> None:
        """
        Update health scores for Unity gauges.

        Args:
            machine_id: Machine identifier
            scores: Dict of component -> score (0-100)
            trends: Dict of component -> trend ("improving", "stable", "declining")
        """
        with self._lock:
            if machine_id not in self._states:
                self._states[machine_id] = UnityPredictiveState(
                    machine_id=machine_id,
                    timestamp=time.time(),
                    overall_health_score=100.0
                )

            state = self._states[machine_id]
            state.timestamp = time.time()

            for component_name, score in scores.items():
                try:
                    component = ComponentType(component_name.lower())
                except ValueError:
                    continue

                status = self._score_to_status(score)
                trend = (trends or {}).get(component_name, "stable")

                state.health_scores[component_name] = HealthScore(
                    component=component,
                    score=score,
                    status=status,
                    trend=trend,
                    confidence=0.9,
                    last_updated=time.time()
                )

            # Calculate overall health
            if state.health_scores:
                state.overall_health_score = sum(
                    hs.score for hs in state.health_scores.values()
                ) / len(state.health_scores)

    def update_tool_predictions(
        self,
        machine_id: str,
        predictions: List[Dict[str, Any]]
    ) -> None:
        """
        Update tool wear predictions for Unity overlay.

        Args:
            machine_id: Machine identifier
            predictions: List of tool prediction dicts
        """
        with self._lock:
            if machine_id not in self._states:
                self._states[machine_id] = UnityPredictiveState(
                    machine_id=machine_id,
                    timestamp=time.time(),
                    overall_health_score=100.0
                )

            state = self._states[machine_id]
            state.timestamp = time.time()
            state.tool_predictions = []

            for pred in predictions:
                wear_pct = pred.get('wear_percent', 0)
                severity = self._wear_to_severity(wear_pct)

                # Calculate failure time
                remaining_hours = pred.get('life_remaining_hours', 0)
                failure_time = None
                if remaining_hours > 0:
                    failure_time = datetime.now() + timedelta(hours=remaining_hours)

                tool_pred = ToolWearPrediction(
                    tool_number=pred.get('tool_number', 0),
                    tool_name=pred.get('tool_name', f"T{pred.get('tool_number', 0)}"),
                    current_wear_percent=wear_pct,
                    predicted_life_remaining_hours=remaining_hours,
                    predicted_failure_time=failure_time,
                    confidence=pred.get('confidence', 0.8),
                    recommendation=self._get_tool_recommendation(wear_pct, remaining_hours),
                    severity=severity,
                    overlay_position=self.COMPONENT_POSITIONS[ComponentType.TOOL],
                    color_rgb=self.SEVERITY_COLORS[severity],
                    pulse_animation=severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
                )

                state.tool_predictions.append(tool_pred)

    def add_anomaly(
        self,
        machine_id: str,
        component: str,
        anomaly_type: str,
        severity: str,
        description: str,
        position: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Add anomaly marker for 3D visualization.

        Returns:
            Anomaly ID
        """
        anomaly_id = f"anomaly-{machine_id}-{int(time.time() * 1000)}"

        with self._lock:
            if machine_id not in self._states:
                self._states[machine_id] = UnityPredictiveState(
                    machine_id=machine_id,
                    timestamp=time.time(),
                    overall_health_score=100.0
                )

            state = self._states[machine_id]

            try:
                comp_type = ComponentType(component.lower())
            except ValueError:
                comp_type = ComponentType.ELECTRICAL

            sev = AlertSeverity(severity.lower()) if severity else AlertSeverity.WARNING

            # Determine position
            if position:
                pos = Position3D(
                    x=position.get('x', 0),
                    y=position.get('y', 0),
                    z=position.get('z', 0)
                )
            else:
                pos = self.COMPONENT_POSITIONS.get(comp_type, Position3D())

            marker = AnomalyMarker(
                anomaly_id=anomaly_id,
                machine_id=machine_id,
                component=comp_type,
                anomaly_type=anomaly_type,
                severity=sev,
                detected_at=datetime.now(),
                description=description,
                position=pos,
                color_rgb=self.SEVERITY_COLORS[sev],
                pulse=sev in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
            )

            state.active_anomalies.append(marker)

            # Keep only last 20 anomalies
            state.active_anomalies = state.active_anomalies[-20:]

        return anomaly_id

    def clear_anomaly(self, machine_id: str, anomaly_id: str) -> bool:
        """Clear an anomaly marker."""
        with self._lock:
            if machine_id not in self._states:
                return False

            state = self._states[machine_id]
            original_len = len(state.active_anomalies)
            state.active_anomalies = [
                a for a in state.active_anomalies
                if a.anomaly_id != anomaly_id
            ]

            return len(state.active_anomalies) < original_len

    def update_maintenance_schedule(
        self,
        machine_id: str,
        events: List[Dict[str, Any]]
    ) -> None:
        """
        Update maintenance schedule for Unity calendar.

        Args:
            machine_id: Machine identifier
            events: List of maintenance event dicts
        """
        with self._lock:
            if machine_id not in self._states:
                self._states[machine_id] = UnityPredictiveState(
                    machine_id=machine_id,
                    timestamp=time.time(),
                    overall_health_score=100.0
                )

            state = self._states[machine_id]
            state.upcoming_maintenance = []

            for evt in events:
                try:
                    comp_type = ComponentType(evt.get('component', 'electrical').lower())
                    maint_type = MaintenanceType(evt.get('maintenance_type', 'preventive').lower())
                except ValueError:
                    continue

                # Parse scheduled time
                scheduled = evt.get('scheduled_start')
                if isinstance(scheduled, str):
                    scheduled = datetime.fromisoformat(scheduled)
                elif not isinstance(scheduled, datetime):
                    scheduled = datetime.now() + timedelta(days=1)

                event = MaintenanceEvent(
                    event_id=evt.get('event_id', f"maint-{int(time.time())}"),
                    machine_id=machine_id,
                    component=comp_type,
                    maintenance_type=maint_type,
                    scheduled_start=scheduled,
                    scheduled_duration_hours=evt.get('duration_hours', 2.0),
                    description=evt.get('description', 'Scheduled maintenance'),
                    priority=evt.get('priority', 3),
                    requires_shutdown=evt.get('requires_shutdown', False),
                    parts_needed=evt.get('parts_needed', [])
                )

                state.upcoming_maintenance.append(event)

            # Sort by scheduled time
            state.upcoming_maintenance.sort(key=lambda e: e.scheduled_start)

    def update_trend_data(
        self,
        machine_id: str,
        metric_name: str,
        timestamps: List[float],
        values: List[float],
        predictions: Optional[Dict[str, List[float]]] = None,
        thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Update trend data for Unity charts.

        Args:
            machine_id: Machine identifier
            metric_name: Name of the metric
            timestamps: List of timestamps
            values: List of values
            predictions: Optional dict with prediction_timestamps and prediction_values
            thresholds: Optional dict with warning/critical thresholds
        """
        with self._lock:
            if machine_id not in self._states:
                self._states[machine_id] = UnityPredictiveState(
                    machine_id=machine_id,
                    timestamp=time.time(),
                    overall_health_score=100.0
                )

            state = self._states[machine_id]

            trend = TrendData(
                metric_name=metric_name,
                unit=self._get_metric_unit(metric_name),
                timestamps=timestamps,
                values=values,
                prediction_timestamps=(predictions or {}).get('timestamps', []),
                prediction_values=(predictions or {}).get('values', []),
                warning_threshold=(thresholds or {}).get('warning'),
                critical_threshold=(thresholds or {}).get('critical')
            )

            state.trends[metric_name] = trend

    # =========================================================================
    # Unity Format Output
    # =========================================================================

    def get_unity_state_dict(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """
        Get predictive state formatted for Unity JSON serialization.

        Returns dict optimized for Unity consumption with all necessary
        visualization data.
        """
        state = self.get_predictive_state(machine_id)
        if not state:
            return None

        return {
            'machine_id': state.machine_id,
            'timestamp': state.timestamp,
            'overall_health': {
                'score': state.overall_health_score,
                'status': self._score_to_status(state.overall_health_score).value,
                'color': self._score_to_color(state.overall_health_score)
            },
            'health_scores': {
                name: {
                    'component': hs.component.value,
                    'score': hs.score,
                    'status': hs.status.value,
                    'trend': hs.trend,
                    'confidence': hs.confidence
                }
                for name, hs in state.health_scores.items()
            },
            'tool_predictions': [
                {
                    'tool_number': tp.tool_number,
                    'tool_name': tp.tool_name,
                    'wear_percent': tp.current_wear_percent,
                    'life_remaining_hours': tp.predicted_life_remaining_hours,
                    'failure_time': tp.predicted_failure_time.isoformat() if tp.predicted_failure_time else None,
                    'confidence': tp.confidence,
                    'recommendation': tp.recommendation,
                    'severity': tp.severity.value,
                    'overlay': {
                        'position': asdict(tp.overlay_position),
                        'color': list(tp.color_rgb),
                        'pulse': tp.pulse_animation,
                        'show_trend': tp.show_trend_arrow
                    }
                }
                for tp in state.tool_predictions
            ],
            'maintenance': [
                {
                    'event_id': me.event_id,
                    'component': me.component.value,
                    'type': me.maintenance_type.value,
                    'scheduled_start': me.scheduled_start.isoformat(),
                    'duration_hours': me.scheduled_duration_hours,
                    'description': me.description,
                    'priority': me.priority,
                    'requires_shutdown': me.requires_shutdown,
                    'ar': {
                        'show': me.show_in_ar,
                        'icon': me.ar_icon,
                        'color': list(me.ar_color_rgb)
                    }
                }
                for me in state.upcoming_maintenance[:10]  # Limit to 10
            ],
            'anomalies': [
                {
                    'anomaly_id': am.anomaly_id,
                    'component': am.component.value,
                    'type': am.anomaly_type,
                    'severity': am.severity.value,
                    'detected_at': am.detected_at.isoformat(),
                    'description': am.description,
                    'marker': {
                        'position': asdict(am.position),
                        'type': am.marker_type,
                        'color': list(am.color_rgb),
                        'size': am.size,
                        'pulse': am.pulse,
                        'show_label': am.show_label
                    }
                }
                for am in state.active_anomalies
            ],
            'trends': {
                name: {
                    'metric': td.metric_name,
                    'unit': td.unit,
                    'data': {
                        'timestamps': td.timestamps[-100:],  # Last 100 points
                        'values': td.values[-100:]
                    },
                    'predictions': {
                        'timestamps': td.prediction_timestamps,
                        'values': td.prediction_values
                    },
                    'thresholds': {
                        'warning': td.warning_threshold,
                        'critical': td.critical_threshold
                    }
                }
                for name, td in state.trends.items()
            }
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _score_to_status(self, score: float) -> HealthStatus:
        """Convert health score to status."""
        if score >= 90:
            return HealthStatus.EXCELLENT
        elif score >= 75:
            return HealthStatus.GOOD
        elif score >= 50:
            return HealthStatus.FAIR
        elif score >= 25:
            return HealthStatus.POOR
        else:
            return HealthStatus.CRITICAL

    def _score_to_color(self, score: float) -> List[int]:
        """Convert health score to RGB color."""
        if score >= 90:
            return [0, 200, 100]    # Green
        elif score >= 75:
            return [100, 200, 0]    # Yellow-green
        elif score >= 50:
            return [255, 200, 0]    # Yellow
        elif score >= 25:
            return [255, 100, 0]    # Orange
        else:
            return [255, 0, 0]      # Red

    def _wear_to_severity(self, wear_percent: float) -> AlertSeverity:
        """Convert wear percentage to severity."""
        if wear_percent < 50:
            return AlertSeverity.INFO
        elif wear_percent < 75:
            return AlertSeverity.WARNING
        elif wear_percent < 90:
            return AlertSeverity.CRITICAL
        else:
            return AlertSeverity.EMERGENCY

    def _get_tool_recommendation(
        self,
        wear_percent: float,
        remaining_hours: float
    ) -> str:
        """Get tool recommendation based on wear."""
        if wear_percent >= 90:
            return "Replace immediately - tool at end of life"
        elif wear_percent >= 75:
            return "Schedule replacement soon"
        elif wear_percent >= 50:
            return "Monitor closely - approaching replacement window"
        elif remaining_hours < 8:
            return f"~{remaining_hours:.1f} hours remaining - plan replacement"
        else:
            return "Tool in good condition"

    def _get_metric_unit(self, metric_name: str) -> str:
        """Get unit for metric name."""
        units = {
            'temperature': '°C',
            'vibration': 'mm/s',
            'current': 'A',
            'power': 'W',
            'rpm': 'RPM',
            'wear': '%',
            'pressure': 'bar',
            'load': '%'
        }
        for key, unit in units.items():
            if key in metric_name.lower():
                return unit
        return ''


# =============================================================================
# Singleton Access
# =============================================================================

_unity_predictive: Optional[UnityPredictiveIntegration] = None


def get_unity_predictive() -> UnityPredictiveIntegration:
    """Get the Unity predictive integration singleton."""
    global _unity_predictive
    if _unity_predictive is None:
        _unity_predictive = UnityPredictiveIntegration()
    return _unity_predictive
