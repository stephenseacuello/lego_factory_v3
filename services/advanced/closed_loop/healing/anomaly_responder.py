"""
Anomaly Responder - Automatic response to detected anomalies.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ResponseAction(Enum):
    """Type of response action."""
    ALERT = "alert"
    ADJUST = "adjust"
    PAUSE = "pause"
    STOP = "stop"
    ESCALATE = "escalate"
    IGNORE = "ignore"


class Severity(Enum):
    """Anomaly severity level."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Anomaly:
    """Detected anomaly."""
    anomaly_id: str
    anomaly_type: str
    severity: Severity
    value: float
    threshold: float
    context: Dict[str, Any]
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Response:
    """Response to anomaly."""
    anomaly_id: str
    action: ResponseAction
    parameters: Dict[str, Any]
    success: bool = False
    executed_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


class AnomalyResponder:
    """
    Automatic response to manufacturing anomalies.

    Features:
    - Rule-based response selection
    - Severity-based escalation
    - Response history tracking
    - Custom response handlers
    """

    def __init__(self):
        self._rules: Dict[str, Dict] = {}
        self._handlers: Dict[ResponseAction, Callable] = {}
        self._response_history: List[Response] = []
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default response rules."""
        # Temperature anomalies
        self._rules["temperature_high"] = {
            Severity.LOW: ResponseAction.ALERT,
            Severity.MEDIUM: ResponseAction.ADJUST,
            Severity.HIGH: ResponseAction.PAUSE,
            Severity.CRITICAL: ResponseAction.STOP,
            "adjustment": {"action": "reduce_temperature", "amount": 5}
        }

        self._rules["temperature_low"] = {
            Severity.LOW: ResponseAction.ALERT,
            Severity.MEDIUM: ResponseAction.ADJUST,
            Severity.HIGH: ResponseAction.PAUSE,
            Severity.CRITICAL: ResponseAction.STOP,
            "adjustment": {"action": "increase_temperature", "amount": 5}
        }

        # Speed anomalies
        self._rules["speed_deviation"] = {
            Severity.LOW: ResponseAction.IGNORE,
            Severity.MEDIUM: ResponseAction.ADJUST,
            Severity.HIGH: ResponseAction.PAUSE,
            Severity.CRITICAL: ResponseAction.STOP,
            "adjustment": {"action": "reset_speed", "target": 100}
        }

        # Quality anomalies
        self._rules["quality_defect"] = {
            Severity.LOW: ResponseAction.ALERT,
            Severity.MEDIUM: ResponseAction.ALERT,
            Severity.HIGH: ResponseAction.PAUSE,
            Severity.CRITICAL: ResponseAction.STOP
        }

        # Equipment anomalies
        self._rules["equipment_vibration"] = {
            Severity.LOW: ResponseAction.ALERT,
            Severity.MEDIUM: ResponseAction.ESCALATE,
            Severity.HIGH: ResponseAction.PAUSE,
            Severity.CRITICAL: ResponseAction.STOP
        }

    def register_handler(self,
                        action: ResponseAction,
                        handler: Callable[[Anomaly, Dict], bool]) -> None:
        """Register handler for response action."""
        self._handlers[action] = handler

    def add_rule(self,
                anomaly_type: str,
                severity_actions: Dict[Severity, ResponseAction],
                adjustment: Optional[Dict] = None) -> None:
        """Add custom response rule."""
        rule = dict(severity_actions)
        if adjustment:
            rule["adjustment"] = adjustment
        self._rules[anomaly_type] = rule

    async def respond(self, anomaly: Anomaly) -> Response:
        """
        Respond to detected anomaly.

        Args:
            anomaly: Detected anomaly

        Returns:
            Response executed
        """
        # Get rule for anomaly type
        rule = self._rules.get(anomaly.anomaly_type, {})

        # Determine action based on severity
        action = rule.get(anomaly.severity, ResponseAction.ALERT)
        parameters = {}

        if action == ResponseAction.ADJUST and "adjustment" in rule:
            parameters = rule["adjustment"].copy()

        # Execute response
        response = Response(
            anomaly_id=anomaly.anomaly_id,
            action=action,
            parameters=parameters
        )

        try:
            success = await self._execute_response(anomaly, response)
            response.success = success

            if success:
                logger.info(f"Response executed: {action.value} for {anomaly.anomaly_type}")
            else:
                logger.warning(f"Response failed: {action.value} for {anomaly.anomaly_type}")

        except Exception as e:
            logger.error(f"Response error: {e}")
            response.notes = str(e)

        self._response_history.append(response)
        return response

    async def _execute_response(self,
                               anomaly: Anomaly,
                               response: Response) -> bool:
        """Execute the response action."""
        action = response.action

        if action == ResponseAction.IGNORE:
            return True

        if action in self._handlers:
            try:
                handler = self._handlers[action]
                return handler(anomaly, response.parameters)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                return False

        # Default handlers
        if action == ResponseAction.ALERT:
            logger.warning(f"ALERT: {anomaly.anomaly_type} - {anomaly.value}")
            return True

        if action == ResponseAction.ESCALATE:
            logger.error(f"ESCALATE: {anomaly.anomaly_type} - severity {anomaly.severity.name}")
            return True

        if action == ResponseAction.PAUSE:
            logger.warning(f"PAUSE requested for: {anomaly.anomaly_type}")
            # Would trigger equipment pause
            return True

        if action == ResponseAction.STOP:
            logger.error(f"STOP requested for: {anomaly.anomaly_type}")
            # Would trigger emergency stop
            return True

        if action == ResponseAction.ADJUST:
            logger.info(f"ADJUST: {response.parameters}")
            # Would trigger parameter adjustment
            return True

        return False

    def get_response_history(self,
                            limit: int = 100,
                            action_filter: Optional[ResponseAction] = None) -> List[Response]:
        """Get response history."""
        history = self._response_history[-limit:]

        if action_filter:
            history = [r for r in history if r.action == action_filter]

        return history

    def get_statistics(self) -> Dict[str, Any]:
        """Get response statistics."""
        if not self._response_history:
            return {'total_responses': 0}

        action_counts = {}
        success_counts = {}

        for response in self._response_history:
            action = response.action.value
            action_counts[action] = action_counts.get(action, 0) + 1

            if response.success:
                success_counts[action] = success_counts.get(action, 0) + 1

        return {
            'total_responses': len(self._response_history),
            'action_counts': action_counts,
            'success_rate': {
                action: success_counts.get(action, 0) / count
                for action, count in action_counts.items()
            }
        }

    def classify_anomaly(self,
                        anomaly_type: str,
                        value: float,
                        thresholds: Dict[str, float]) -> Severity:
        """Classify anomaly severity based on thresholds."""
        deviation = abs(value - thresholds.get('normal', 0))

        if deviation >= thresholds.get('critical', float('inf')):
            return Severity.CRITICAL
        elif deviation >= thresholds.get('high', float('inf')):
            return Severity.HIGH
        elif deviation >= thresholds.get('medium', float('inf')):
            return Severity.MEDIUM
        else:
            return Severity.LOW
