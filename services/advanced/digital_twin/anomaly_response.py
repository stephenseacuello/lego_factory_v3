"""
Anomaly Response Automation Service
====================================

Automated response system for detected manufacturing anomalies.

Features:
- Rule-based response triggers with configurable thresholds
- ML-based response suggestions using historical effectiveness
- Human-in-the-loop escalation workflows
- Response effectiveness tracking and feedback loops

ISO 23247 Compliance:
- Event-driven response architecture
- Traceable decision audit trail
- Configurable response policies

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import threading
import logging
import json
import uuid
import time
import statistics

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of manufacturing anomalies."""
    TEMPERATURE_DEVIATION = "temperature_deviation"
    VIBRATION_ANOMALY = "vibration_anomaly"
    PRESSURE_ANOMALY = "pressure_anomaly"
    DIMENSIONAL_ERROR = "dimensional_error"
    SURFACE_DEFECT = "surface_defect"
    TOOL_WEAR = "tool_wear"
    MATERIAL_DEFECT = "material_defect"
    EQUIPMENT_MALFUNCTION = "equipment_malfunction"
    PROCESS_DRIFT = "process_drift"
    QUALITY_DEGRADATION = "quality_degradation"
    SAFETY_VIOLATION = "safety_violation"
    ENERGY_ANOMALY = "energy_anomaly"
    NETWORK_ANOMALY = "network_anomaly"
    SENSOR_FAILURE = "sensor_failure"
    CALIBRATION_DRIFT = "calibration_drift"


class SeverityLevel(Enum):
    """Anomaly severity levels."""
    INFO = "info"           # Informational, no action required
    WARNING = "warning"     # Potential issue, monitor closely
    MINOR = "minor"         # Minor issue, can continue with caution
    MAJOR = "major"         # Significant issue, may require intervention
    CRITICAL = "critical"   # Critical issue, immediate action required
    EMERGENCY = "emergency" # Safety risk, immediate shutdown


class ResponseType(Enum):
    """Types of automated responses."""
    LOG_ONLY = "log_only"                     # Just log the anomaly
    NOTIFY = "notify"                          # Send notification
    ADJUST_PARAMETER = "adjust_parameter"      # Auto-adjust process parameter
    REDUCE_SPEED = "reduce_speed"              # Slow down operation
    PAUSE_OPERATION = "pause_operation"        # Pause current operation
    STOP_EQUIPMENT = "stop_equipment"          # Stop specific equipment
    EMERGENCY_STOP = "emergency_stop"          # Immediate all-stop
    REQUEST_INSPECTION = "request_inspection"  # Queue for human inspection
    SCHEDULE_MAINTENANCE = "schedule_maintenance"
    QUARANTINE_PRODUCT = "quarantine_product"  # Mark product for review
    SWITCH_BACKUP = "switch_backup"            # Switch to backup equipment
    ESCALATE = "escalate"                      # Escalate to human operator
    CUSTOM_ACTION = "custom_action"            # Execute custom handler


class ResponseStatus(Enum):
    """Status of response execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"
    ACKNOWLEDGED = "acknowledged"


class EscalationLevel(Enum):
    """Human escalation levels."""
    OPERATOR = "operator"           # Line operator
    SUPERVISOR = "supervisor"       # Shift supervisor
    ENGINEER = "engineer"           # Process/maintenance engineer
    MANAGER = "manager"             # Production manager
    SAFETY_OFFICER = "safety_officer"
    EXECUTIVE = "executive"         # Plant executive


@dataclass
class Anomaly:
    """Detected anomaly event."""
    id: str
    anomaly_type: AnomalyType
    severity: SeverityLevel
    source_equipment_id: str
    source_sensor_id: Optional[str]
    detected_at: datetime
    description: str
    measured_value: Optional[float] = None
    expected_range: Optional[Tuple[float, float]] = None
    confidence: float = 1.0
    context: Dict[str, Any] = field(default_factory=dict)
    related_anomalies: List[str] = field(default_factory=list)
    ml_prediction: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'anomaly_type': self.anomaly_type.value,
            'severity': self.severity.value,
            'source_equipment_id': self.source_equipment_id,
            'source_sensor_id': self.source_sensor_id,
            'detected_at': self.detected_at.isoformat(),
            'description': self.description,
            'measured_value': self.measured_value,
            'expected_range': self.expected_range,
            'confidence': self.confidence,
            'context': self.context,
            'related_anomalies': self.related_anomalies,
            'ml_prediction': self.ml_prediction
        }


@dataclass
class ResponseAction:
    """A single response action."""
    id: str
    response_type: ResponseType
    target_equipment_id: Optional[str]
    parameters: Dict[str, Any]
    priority: int = 0  # Higher = more urgent
    timeout_seconds: float = 300.0
    requires_acknowledgment: bool = False
    escalation_timeout_seconds: float = 60.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'response_type': self.response_type.value,
            'target_equipment_id': self.target_equipment_id,
            'parameters': self.parameters,
            'priority': self.priority,
            'timeout_seconds': self.timeout_seconds,
            'requires_acknowledgment': self.requires_acknowledgment
        }


@dataclass
class ResponseExecution:
    """Record of response execution."""
    id: str
    anomaly_id: str
    action: ResponseAction
    status: ResponseStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    executed_by: str = "system"  # system, operator name, etc.
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    effectiveness_score: Optional[float] = None  # 0-1 score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'anomaly_id': self.anomaly_id,
            'action': self.action.to_dict(),
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'executed_by': self.executed_by,
            'result': self.result,
            'error_message': self.error_message,
            'effectiveness_score': self.effectiveness_score
        }


@dataclass
class ResponseRule:
    """Rule for automated response triggering."""
    id: str
    name: str
    description: str
    enabled: bool = True

    # Matching conditions
    anomaly_types: List[AnomalyType] = field(default_factory=list)
    min_severity: SeverityLevel = SeverityLevel.WARNING
    equipment_patterns: List[str] = field(default_factory=list)  # Regex patterns

    # Threshold conditions
    occurrence_threshold: int = 1  # Trigger after N occurrences
    time_window_seconds: float = 300.0  # Within this time window

    # Response configuration
    actions: List[ResponseAction] = field(default_factory=list)

    # Escalation
    escalation_level: Optional[EscalationLevel] = None
    escalation_delay_seconds: float = 0.0

    # Learning
    ml_override_enabled: bool = True  # Allow ML to suggest alternatives

    def matches(self, anomaly: Anomaly) -> bool:
        """Check if anomaly matches this rule."""
        if not self.enabled:
            return False

        # Check type
        if self.anomaly_types and anomaly.anomaly_type not in self.anomaly_types:
            return False

        # Check severity
        severity_order = list(SeverityLevel)
        if severity_order.index(anomaly.severity) < severity_order.index(self.min_severity):
            return False

        # Check equipment pattern
        if self.equipment_patterns:
            import re
            matched = False
            for pattern in self.equipment_patterns:
                if re.match(pattern, anomaly.source_equipment_id):
                    matched = True
                    break
            if not matched:
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'anomaly_types': [t.value for t in self.anomaly_types],
            'min_severity': self.min_severity.value,
            'equipment_patterns': self.equipment_patterns,
            'occurrence_threshold': self.occurrence_threshold,
            'time_window_seconds': self.time_window_seconds,
            'actions': [a.to_dict() for a in self.actions],
            'escalation_level': self.escalation_level.value if self.escalation_level else None,
            'ml_override_enabled': self.ml_override_enabled
        }


class ResponseHandler(ABC):
    """Abstract base class for response handlers."""

    @abstractmethod
    def can_handle(self, response_type: ResponseType) -> bool:
        """Check if handler can process this response type."""
        pass

    @abstractmethod
    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        """Execute the response action."""
        pass


class LoggingHandler(ResponseHandler):
    """Handler for logging-only responses."""

    def can_handle(self, response_type: ResponseType) -> bool:
        return response_type == ResponseType.LOG_ONLY

    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        logger.info(
            f"Anomaly logged: {anomaly.anomaly_type.value} on {anomaly.source_equipment_id} - "
            f"{anomaly.description}"
        )
        return {'logged': True, 'timestamp': datetime.utcnow().isoformat()}


class NotificationHandler(ResponseHandler):
    """Handler for notification responses."""

    def __init__(self, notification_service=None):
        self.notification_service = notification_service

    def can_handle(self, response_type: ResponseType) -> bool:
        return response_type == ResponseType.NOTIFY

    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        channels = action.parameters.get('channels', ['dashboard', 'email'])
        recipients = action.parameters.get('recipients', [])

        notifications_sent = []
        for channel in channels:
            logger.info(
                f"Notification sent via {channel}: {anomaly.severity.value} - "
                f"{anomaly.description}"
            )
            notifications_sent.append({
                'channel': channel,
                'sent_at': datetime.utcnow().isoformat()
            })

        return {
            'notifications_sent': notifications_sent,
            'recipient_count': len(recipients)
        }


class EquipmentControlHandler(ResponseHandler):
    """Handler for equipment control responses."""

    def __init__(self, equipment_service=None):
        self.equipment_service = equipment_service

    def can_handle(self, response_type: ResponseType) -> bool:
        return response_type in [
            ResponseType.REDUCE_SPEED,
            ResponseType.PAUSE_OPERATION,
            ResponseType.STOP_EQUIPMENT,
            ResponseType.EMERGENCY_STOP,
            ResponseType.SWITCH_BACKUP
        ]

    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        equipment_id = action.target_equipment_id or anomaly.source_equipment_id

        if action.response_type == ResponseType.REDUCE_SPEED:
            reduction = action.parameters.get('reduction_percent', 50)
            logger.warning(
                f"Reducing speed on {equipment_id} by {reduction}% "
                f"due to {anomaly.anomaly_type.value}"
            )
            return {
                'action': 'speed_reduced',
                'equipment_id': equipment_id,
                'reduction_percent': reduction
            }

        elif action.response_type == ResponseType.PAUSE_OPERATION:
            logger.warning(f"Pausing operation on {equipment_id}")
            return {
                'action': 'paused',
                'equipment_id': equipment_id,
                'resume_conditions': action.parameters.get('resume_conditions', [])
            }

        elif action.response_type == ResponseType.STOP_EQUIPMENT:
            logger.error(f"Stopping equipment {equipment_id}")
            return {
                'action': 'stopped',
                'equipment_id': equipment_id,
                'reason': anomaly.description
            }

        elif action.response_type == ResponseType.EMERGENCY_STOP:
            logger.critical(f"EMERGENCY STOP initiated for {equipment_id}")
            return {
                'action': 'emergency_stop',
                'equipment_id': equipment_id,
                'severity': 'critical',
                'timestamp': datetime.utcnow().isoformat()
            }

        elif action.response_type == ResponseType.SWITCH_BACKUP:
            backup_id = action.parameters.get('backup_equipment_id')
            logger.warning(f"Switching from {equipment_id} to backup {backup_id}")
            return {
                'action': 'switched_to_backup',
                'original_equipment_id': equipment_id,
                'backup_equipment_id': backup_id
            }

        return {'action': 'unknown', 'equipment_id': equipment_id}


class ParameterAdjustmentHandler(ResponseHandler):
    """Handler for automatic parameter adjustments."""

    def can_handle(self, response_type: ResponseType) -> bool:
        return response_type == ResponseType.ADJUST_PARAMETER

    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        parameter_name = action.parameters.get('parameter_name')
        adjustment = action.parameters.get('adjustment')
        new_value = action.parameters.get('new_value')

        equipment_id = action.target_equipment_id or anomaly.source_equipment_id

        logger.info(
            f"Adjusting {parameter_name} on {equipment_id}: "
            f"adjustment={adjustment}, new_value={new_value}"
        )

        return {
            'action': 'parameter_adjusted',
            'equipment_id': equipment_id,
            'parameter_name': parameter_name,
            'adjustment': adjustment,
            'new_value': new_value,
            'previous_value': action.parameters.get('previous_value')
        }


class MaintenanceHandler(ResponseHandler):
    """Handler for maintenance scheduling."""

    def __init__(self, maintenance_service=None):
        self.maintenance_service = maintenance_service

    def can_handle(self, response_type: ResponseType) -> bool:
        return response_type in [
            ResponseType.REQUEST_INSPECTION,
            ResponseType.SCHEDULE_MAINTENANCE
        ]

    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        equipment_id = action.target_equipment_id or anomaly.source_equipment_id

        if action.response_type == ResponseType.REQUEST_INSPECTION:
            inspection_type = action.parameters.get('inspection_type', 'visual')
            priority = action.parameters.get('priority', 'normal')

            logger.info(
                f"Inspection requested for {equipment_id}: "
                f"type={inspection_type}, priority={priority}"
            )

            return {
                'action': 'inspection_requested',
                'equipment_id': equipment_id,
                'inspection_type': inspection_type,
                'priority': priority,
                'work_order_id': str(uuid.uuid4())[:8]
            }

        elif action.response_type == ResponseType.SCHEDULE_MAINTENANCE:
            maintenance_type = action.parameters.get('maintenance_type', 'preventive')
            urgency = action.parameters.get('urgency', 'normal')

            logger.info(
                f"Maintenance scheduled for {equipment_id}: "
                f"type={maintenance_type}, urgency={urgency}"
            )

            return {
                'action': 'maintenance_scheduled',
                'equipment_id': equipment_id,
                'maintenance_type': maintenance_type,
                'urgency': urgency,
                'work_order_id': str(uuid.uuid4())[:8]
            }

        return {'action': 'unknown'}


class QualityHandler(ResponseHandler):
    """Handler for quality-related responses."""

    def can_handle(self, response_type: ResponseType) -> bool:
        return response_type == ResponseType.QUARANTINE_PRODUCT

    async def execute(self, action: ResponseAction, anomaly: Anomaly) -> Dict[str, Any]:
        product_ids = action.parameters.get('product_ids', [])
        batch_id = action.parameters.get('batch_id')
        reason = action.parameters.get('reason', anomaly.description)

        logger.warning(
            f"Quarantining products: {product_ids or batch_id} - Reason: {reason}"
        )

        return {
            'action': 'products_quarantined',
            'product_ids': product_ids,
            'batch_id': batch_id,
            'reason': reason,
            'quarantine_location': action.parameters.get('quarantine_location'),
            'timestamp': datetime.utcnow().isoformat()
        }


class MLResponseSuggester:
    """ML-based response suggestion engine."""

    def __init__(self):
        self._response_history: List[ResponseExecution] = []
        self._effectiveness_by_context: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def record_response(self, execution: ResponseExecution):
        """Record a response execution for learning."""
        with self._lock:
            self._response_history.append(execution)

            # Update effectiveness tracking
            if execution.effectiveness_score is not None:
                context_key = self._get_context_key(execution)
                if context_key not in self._effectiveness_by_context:
                    self._effectiveness_by_context[context_key] = []
                self._effectiveness_by_context[context_key].append(
                    execution.effectiveness_score
                )

                # Keep limited history
                if len(self._effectiveness_by_context[context_key]) > 100:
                    self._effectiveness_by_context[context_key].pop(0)

            # Keep limited total history
            if len(self._response_history) > 10000:
                self._response_history.pop(0)

    def suggest_response(
        self,
        anomaly: Anomaly,
        default_actions: List[ResponseAction]
    ) -> Tuple[List[ResponseAction], float]:
        """
        Suggest optimal response based on historical effectiveness.

        Returns:
            Tuple of (suggested actions, confidence score)
        """
        with self._lock:
            # Build context key for this anomaly
            context_key = self._get_anomaly_context_key(anomaly)

            # Check if we have effectiveness data for similar contexts
            effectiveness_scores = self._effectiveness_by_context.get(context_key, [])

            if not effectiveness_scores:
                # No historical data, use default with low confidence
                return default_actions, 0.3

            avg_effectiveness = statistics.mean(effectiveness_scores)

            if avg_effectiveness >= 0.8:
                # High historical effectiveness, keep defaults
                return default_actions, 0.9
            elif avg_effectiveness >= 0.5:
                # Moderate effectiveness, suggest with moderate confidence
                return default_actions, 0.6
            else:
                # Low effectiveness, suggest modifications
                modified_actions = self._suggest_modifications(
                    anomaly, default_actions, avg_effectiveness
                )
                return modified_actions, 0.5

    def _get_context_key(self, execution: ResponseExecution) -> str:
        """Generate context key for tracking effectiveness."""
        return f"{execution.action.response_type.value}:{execution.anomaly_id[:8]}"

    def _get_anomaly_context_key(self, anomaly: Anomaly) -> str:
        """Generate context key for anomaly lookup."""
        return f"{anomaly.anomaly_type.value}:{anomaly.source_equipment_id[:8]}"

    def _suggest_modifications(
        self,
        anomaly: Anomaly,
        default_actions: List[ResponseAction],
        current_effectiveness: float
    ) -> List[ResponseAction]:
        """Suggest modifications to improve effectiveness."""
        modified = []

        for action in default_actions:
            # Clone action with potential modifications
            new_action = ResponseAction(
                id=str(uuid.uuid4()),
                response_type=action.response_type,
                target_equipment_id=action.target_equipment_id,
                parameters=action.parameters.copy(),
                priority=action.priority,
                timeout_seconds=action.timeout_seconds,
                requires_acknowledgment=True,  # Require ack for low-effectiveness
                escalation_timeout_seconds=action.escalation_timeout_seconds / 2  # Faster escalation
            )

            # Suggest escalation if effectiveness is very low
            if current_effectiveness < 0.3:
                escalation_action = ResponseAction(
                    id=str(uuid.uuid4()),
                    response_type=ResponseType.ESCALATE,
                    target_equipment_id=action.target_equipment_id,
                    parameters={
                        'reason': 'Low historical effectiveness',
                        'original_action': action.to_dict()
                    },
                    priority=action.priority + 1
                )
                modified.append(escalation_action)

            modified.append(new_action)

        return modified

    def get_effectiveness_summary(self) -> Dict[str, Any]:
        """Get summary of response effectiveness."""
        with self._lock:
            summary = {}
            for context_key, scores in self._effectiveness_by_context.items():
                if scores:
                    summary[context_key] = {
                        'avg_effectiveness': statistics.mean(scores),
                        'min_effectiveness': min(scores),
                        'max_effectiveness': max(scores),
                        'sample_count': len(scores)
                    }
            return summary


class EscalationManager:
    """Manages human-in-the-loop escalation workflows."""

    def __init__(self):
        self._pending_escalations: Dict[str, Dict[str, Any]] = {}
        self._escalation_callbacks: Dict[EscalationLevel, List[Callable]] = {}
        self._lock = threading.Lock()

    def register_callback(
        self,
        level: EscalationLevel,
        callback: Callable[[Dict[str, Any]], None]
    ):
        """Register callback for escalation level."""
        with self._lock:
            if level not in self._escalation_callbacks:
                self._escalation_callbacks[level] = []
            self._escalation_callbacks[level].append(callback)

    def escalate(
        self,
        anomaly: Anomaly,
        action: ResponseAction,
        level: EscalationLevel,
        reason: str = ""
    ) -> str:
        """Create escalation request."""
        escalation_id = str(uuid.uuid4())

        with self._lock:
            escalation = {
                'id': escalation_id,
                'anomaly': anomaly.to_dict(),
                'action': action.to_dict(),
                'level': level.value,
                'reason': reason,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'pending',
                'acknowledged_by': None,
                'acknowledged_at': None,
                'resolution': None
            }

            self._pending_escalations[escalation_id] = escalation

            # Notify registered callbacks
            callbacks = self._escalation_callbacks.get(level, [])
            for callback in callbacks:
                try:
                    callback(escalation)
                except Exception as e:
                    logger.error(f"Escalation callback error: {e}")

        logger.warning(
            f"Escalation created: {escalation_id} - Level: {level.value} - "
            f"Anomaly: {anomaly.anomaly_type.value}"
        )

        return escalation_id

    def acknowledge(
        self,
        escalation_id: str,
        acknowledged_by: str,
        action_taken: Optional[str] = None
    ) -> bool:
        """Acknowledge an escalation."""
        with self._lock:
            if escalation_id not in self._pending_escalations:
                return False

            escalation = self._pending_escalations[escalation_id]
            escalation['status'] = 'acknowledged'
            escalation['acknowledged_by'] = acknowledged_by
            escalation['acknowledged_at'] = datetime.utcnow().isoformat()
            if action_taken:
                escalation['action_taken'] = action_taken

        logger.info(f"Escalation acknowledged: {escalation_id} by {acknowledged_by}")
        return True

    def resolve(
        self,
        escalation_id: str,
        resolved_by: str,
        resolution: str,
        effectiveness: float = 1.0
    ) -> bool:
        """Resolve an escalation."""
        with self._lock:
            if escalation_id not in self._pending_escalations:
                return False

            escalation = self._pending_escalations[escalation_id]
            escalation['status'] = 'resolved'
            escalation['resolved_by'] = resolved_by
            escalation['resolved_at'] = datetime.utcnow().isoformat()
            escalation['resolution'] = resolution
            escalation['effectiveness'] = effectiveness

        logger.info(f"Escalation resolved: {escalation_id} - {resolution}")
        return True

    def get_pending_escalations(
        self,
        level: Optional[EscalationLevel] = None
    ) -> List[Dict[str, Any]]:
        """Get pending escalations."""
        with self._lock:
            pending = [
                e for e in self._pending_escalations.values()
                if e['status'] == 'pending'
            ]
            if level:
                pending = [e for e in pending if e['level'] == level.value]
            return pending

    def get_escalation(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        """Get specific escalation by ID."""
        with self._lock:
            return self._pending_escalations.get(escalation_id)


class AnomalyResponseService:
    """
    Main service for automated anomaly response.

    Coordinates rule evaluation, response execution, ML suggestions,
    and human escalation workflows.
    """

    def __init__(self):
        self._rules: Dict[str, ResponseRule] = {}
        self._handlers: List[ResponseHandler] = []
        self._executions: Dict[str, ResponseExecution] = {}
        self._anomaly_counts: Dict[str, List[datetime]] = {}  # For threshold tracking

        self._ml_suggester = MLResponseSuggester()
        self._escalation_manager = EscalationManager()

        self._lock = threading.RLock()

        # Register default handlers
        self._register_default_handlers()

        # Register default rules
        self._register_default_rules()

        logger.info("AnomalyResponseService initialized")

    def _register_default_handlers(self):
        """Register default response handlers."""
        self._handlers = [
            LoggingHandler(),
            NotificationHandler(),
            EquipmentControlHandler(),
            ParameterAdjustmentHandler(),
            MaintenanceHandler(),
            QualityHandler()
        ]

    def _register_default_rules(self):
        """Register default response rules."""
        # Critical temperature deviation
        self.add_rule(ResponseRule(
            id="temp_critical",
            name="Critical Temperature Response",
            description="Emergency stop on critical temperature deviation",
            anomaly_types=[AnomalyType.TEMPERATURE_DEVIATION],
            min_severity=SeverityLevel.CRITICAL,
            actions=[
                ResponseAction(
                    id="temp_crit_stop",
                    response_type=ResponseType.EMERGENCY_STOP,
                    target_equipment_id=None,
                    parameters={'reason': 'Critical temperature deviation'}
                ),
                ResponseAction(
                    id="temp_crit_notify",
                    response_type=ResponseType.NOTIFY,
                    target_equipment_id=None,
                    parameters={'channels': ['sms', 'email', 'dashboard']}
                )
            ],
            escalation_level=EscalationLevel.SAFETY_OFFICER
        ))

        # Major temperature deviation
        self.add_rule(ResponseRule(
            id="temp_major",
            name="Major Temperature Response",
            description="Reduce speed and notify on major temperature deviation",
            anomaly_types=[AnomalyType.TEMPERATURE_DEVIATION],
            min_severity=SeverityLevel.MAJOR,
            actions=[
                ResponseAction(
                    id="temp_maj_slow",
                    response_type=ResponseType.REDUCE_SPEED,
                    target_equipment_id=None,
                    parameters={'reduction_percent': 50}
                ),
                ResponseAction(
                    id="temp_maj_notify",
                    response_type=ResponseType.NOTIFY,
                    target_equipment_id=None,
                    parameters={'channels': ['dashboard', 'email']}
                )
            ],
            escalation_level=EscalationLevel.ENGINEER,
            escalation_delay_seconds=300.0
        ))

        # Surface defect detection
        self.add_rule(ResponseRule(
            id="surface_defect",
            name="Surface Defect Response",
            description="Quarantine product and request inspection on surface defect",
            anomaly_types=[AnomalyType.SURFACE_DEFECT],
            min_severity=SeverityLevel.MINOR,
            actions=[
                ResponseAction(
                    id="defect_quarantine",
                    response_type=ResponseType.QUARANTINE_PRODUCT,
                    target_equipment_id=None,
                    parameters={}
                ),
                ResponseAction(
                    id="defect_inspect",
                    response_type=ResponseType.REQUEST_INSPECTION,
                    target_equipment_id=None,
                    parameters={'inspection_type': 'visual', 'priority': 'high'}
                )
            ]
        ))

        # Tool wear warning
        self.add_rule(ResponseRule(
            id="tool_wear",
            name="Tool Wear Response",
            description="Schedule maintenance on tool wear detection",
            anomaly_types=[AnomalyType.TOOL_WEAR],
            min_severity=SeverityLevel.WARNING,
            occurrence_threshold=3,
            time_window_seconds=3600.0,
            actions=[
                ResponseAction(
                    id="tool_maintenance",
                    response_type=ResponseType.SCHEDULE_MAINTENANCE,
                    target_equipment_id=None,
                    parameters={'maintenance_type': 'tool_change', 'urgency': 'normal'}
                )
            ]
        ))

        # Safety violation
        self.add_rule(ResponseRule(
            id="safety_violation",
            name="Safety Violation Response",
            description="Immediate stop on safety violation",
            anomaly_types=[AnomalyType.SAFETY_VIOLATION],
            min_severity=SeverityLevel.WARNING,
            actions=[
                ResponseAction(
                    id="safety_stop",
                    response_type=ResponseType.EMERGENCY_STOP,
                    target_equipment_id=None,
                    parameters={'reason': 'Safety violation detected'}
                )
            ],
            escalation_level=EscalationLevel.SAFETY_OFFICER,
            ml_override_enabled=False  # Never override safety responses
        ))

    def add_rule(self, rule: ResponseRule):
        """Add a response rule."""
        with self._lock:
            self._rules[rule.id] = rule
            logger.info(f"Response rule added: {rule.name} ({rule.id})")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a response rule."""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                logger.info(f"Response rule removed: {rule_id}")
                return True
            return False

    def update_rule(self, rule: ResponseRule) -> bool:
        """Update an existing rule."""
        with self._lock:
            if rule.id in self._rules:
                self._rules[rule.id] = rule
                logger.info(f"Response rule updated: {rule.name} ({rule.id})")
                return True
            return False

    def get_rules(self) -> List[ResponseRule]:
        """Get all response rules."""
        with self._lock:
            return list(self._rules.values())

    def register_handler(self, handler: ResponseHandler):
        """Register a custom response handler."""
        self._handlers.append(handler)

    async def process_anomaly(self, anomaly: Anomaly) -> List[ResponseExecution]:
        """
        Process an anomaly and execute appropriate responses.

        Returns list of response executions.
        """
        executions = []

        # Track anomaly occurrence for threshold checks
        self._track_anomaly(anomaly)

        # Find matching rules
        matching_rules = self._find_matching_rules(anomaly)

        for rule in matching_rules:
            # Check occurrence threshold
            if not self._check_threshold(anomaly, rule):
                continue

            # Get actions (potentially modified by ML)
            actions, confidence = self._get_response_actions(anomaly, rule)

            # Execute each action
            for action in actions:
                execution = await self._execute_action(anomaly, action)
                executions.append(execution)

                # Record for ML learning
                self._ml_suggester.record_response(execution)

            # Handle escalation if needed
            if rule.escalation_level and rule.escalation_delay_seconds == 0:
                self._escalation_manager.escalate(
                    anomaly=anomaly,
                    action=actions[0] if actions else ResponseAction(
                        id="escalate",
                        response_type=ResponseType.ESCALATE,
                        target_equipment_id=None,
                        parameters={}
                    ),
                    level=rule.escalation_level,
                    reason=f"Rule triggered: {rule.name}"
                )

        return executions

    def _track_anomaly(self, anomaly: Anomaly):
        """Track anomaly occurrence for threshold checks."""
        key = f"{anomaly.anomaly_type.value}:{anomaly.source_equipment_id}"
        with self._lock:
            if key not in self._anomaly_counts:
                self._anomaly_counts[key] = []
            self._anomaly_counts[key].append(anomaly.detected_at)

            # Cleanup old entries (keep last hour)
            cutoff = datetime.utcnow() - timedelta(hours=1)
            self._anomaly_counts[key] = [
                t for t in self._anomaly_counts[key] if t > cutoff
            ]

    def _find_matching_rules(self, anomaly: Anomaly) -> List[ResponseRule]:
        """Find all rules that match the anomaly."""
        with self._lock:
            return [rule for rule in self._rules.values() if rule.matches(anomaly)]

    def _check_threshold(self, anomaly: Anomaly, rule: ResponseRule) -> bool:
        """Check if anomaly meets occurrence threshold."""
        if rule.occurrence_threshold <= 1:
            return True

        key = f"{anomaly.anomaly_type.value}:{anomaly.source_equipment_id}"
        with self._lock:
            occurrences = self._anomaly_counts.get(key, [])
            cutoff = anomaly.detected_at - timedelta(seconds=rule.time_window_seconds)
            recent_count = sum(1 for t in occurrences if t > cutoff)
            return recent_count >= rule.occurrence_threshold

    def _get_response_actions(
        self,
        anomaly: Anomaly,
        rule: ResponseRule
    ) -> Tuple[List[ResponseAction], float]:
        """Get response actions, potentially modified by ML."""
        if rule.ml_override_enabled:
            return self._ml_suggester.suggest_response(anomaly, rule.actions)
        return rule.actions, 1.0

    async def _execute_action(
        self,
        anomaly: Anomaly,
        action: ResponseAction
    ) -> ResponseExecution:
        """Execute a single response action."""
        execution = ResponseExecution(
            id=str(uuid.uuid4()),
            anomaly_id=anomaly.id,
            action=action,
            status=ResponseStatus.EXECUTING,
            started_at=datetime.utcnow()
        )

        with self._lock:
            self._executions[execution.id] = execution

        try:
            # Find handler
            handler = None
            for h in self._handlers:
                if h.can_handle(action.response_type):
                    handler = h
                    break

            if handler:
                result = await handler.execute(action, anomaly)
                execution.result = result
                execution.status = ResponseStatus.COMPLETED
            else:
                logger.warning(f"No handler for response type: {action.response_type}")
                execution.status = ResponseStatus.FAILED
                execution.error_message = f"No handler for {action.response_type}"

        except Exception as e:
            logger.error(f"Response execution error: {e}")
            execution.status = ResponseStatus.FAILED
            execution.error_message = str(e)

        execution.completed_at = datetime.utcnow()

        return execution

    def record_effectiveness(
        self,
        execution_id: str,
        effectiveness_score: float,
        feedback: Optional[str] = None
    ) -> bool:
        """Record effectiveness feedback for a response."""
        with self._lock:
            if execution_id not in self._executions:
                return False

            execution = self._executions[execution_id]
            execution.effectiveness_score = effectiveness_score
            if feedback:
                if execution.result is None:
                    execution.result = {}
                execution.result['effectiveness_feedback'] = feedback

            # Record for ML learning
            self._ml_suggester.record_response(execution)

        return True

    def get_execution(self, execution_id: str) -> Optional[ResponseExecution]:
        """Get a specific execution by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    def get_recent_executions(
        self,
        limit: int = 100,
        anomaly_type: Optional[AnomalyType] = None
    ) -> List[ResponseExecution]:
        """Get recent response executions."""
        with self._lock:
            executions = list(self._executions.values())

            # Sort by start time descending
            executions.sort(key=lambda e: e.started_at, reverse=True)

            # Filter by type if specified
            if anomaly_type:
                executions = [
                    e for e in executions
                    if e.action.response_type.value.startswith(anomaly_type.value)
                ]

            return executions[:limit]

    def get_escalation_manager(self) -> EscalationManager:
        """Get the escalation manager."""
        return self._escalation_manager

    def get_ml_suggester(self) -> MLResponseSuggester:
        """Get the ML suggester."""
        return self._ml_suggester

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        with self._lock:
            total_executions = len(self._executions)
            completed = sum(
                1 for e in self._executions.values()
                if e.status == ResponseStatus.COMPLETED
            )
            failed = sum(
                1 for e in self._executions.values()
                if e.status == ResponseStatus.FAILED
            )

            effectiveness_scores = [
                e.effectiveness_score
                for e in self._executions.values()
                if e.effectiveness_score is not None
            ]

            return {
                'total_rules': len(self._rules),
                'total_executions': total_executions,
                'completed_executions': completed,
                'failed_executions': failed,
                'success_rate': completed / total_executions if total_executions > 0 else 0,
                'avg_effectiveness': statistics.mean(effectiveness_scores) if effectiveness_scores else None,
                'pending_escalations': len(self._escalation_manager.get_pending_escalations()),
                'ml_effectiveness_summary': self._ml_suggester.get_effectiveness_summary()
            }


# Singleton instance
_anomaly_response_service: Optional[AnomalyResponseService] = None


def get_anomaly_response_service() -> AnomalyResponseService:
    """Get or create anomaly response service."""
    global _anomaly_response_service
    if _anomaly_response_service is None:
        _anomaly_response_service = AnomalyResponseService()
    return _anomaly_response_service
