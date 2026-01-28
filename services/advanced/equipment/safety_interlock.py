"""
Safety Interlock - Safety system integration.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Safety levels for actions."""
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    BLOCKED = "blocked"


@dataclass
class SafetyViolation(Exception):
    """Exception raised when safety is violated."""
    rule_id: str
    message: str
    severity: SafetyLevel
    decision_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SafetyRule:
    """Safety rule definition."""
    rule_id: str
    name: str
    description: str
    check_fn: Callable[[Any], bool]
    severity: SafetyLevel
    enabled: bool = True


class SafetyInterlock:
    """
    Multi-layer safety interlocks for equipment control.

    Features:
    - Configurable safety rules
    - Multiple severity levels
    - Human approval gates
    - Emergency stop
    - Audit logging
    """

    def __init__(self):
        self._rules: List[SafetyRule] = []
        self._violations: List[SafetyViolation] = []
        self._approval_required: Dict[str, bool] = {}
        self._emergency_stop = False
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default safety rules."""
        # Temperature limits
        self._rules.append(SafetyRule(
            rule_id="TEMP_MAX",
            name="Maximum Temperature",
            description="Nozzle temperature must not exceed 300C",
            check_fn=lambda d: (
                d.decision_type.value != 'temperature_adjust' or
                d.value <= 300
            ),
            severity=SafetyLevel.BLOCKED
        ))

        self._rules.append(SafetyRule(
            rule_id="TEMP_MIN",
            name="Minimum Temperature",
            description="Nozzle temperature must not go below 150C during print",
            check_fn=lambda d: (
                d.decision_type.value != 'temperature_adjust' or
                d.value >= 150
            ),
            severity=SafetyLevel.WARNING
        ))

        # Speed limits
        self._rules.append(SafetyRule(
            rule_id="SPEED_MAX",
            name="Maximum Speed",
            description="Print speed must not exceed 200%",
            check_fn=lambda d: (
                d.decision_type.value != 'speed_adjust' or
                d.value <= 200
            ),
            severity=SafetyLevel.DANGER
        ))

        # Z offset limits
        self._rules.append(SafetyRule(
            rule_id="Z_OFFSET_LIMIT",
            name="Z Offset Limit",
            description="Z offset adjustment limited to +/- 1mm",
            check_fn=lambda d: (
                d.decision_type.value != 'z_offset_adjust' or
                abs(d.value) <= 1.0
            ),
            severity=SafetyLevel.BLOCKED
        ))

        # Low confidence actions require approval
        self._rules.append(SafetyRule(
            rule_id="LOW_CONFIDENCE",
            name="Low Confidence Approval",
            description="Decisions with confidence < 0.7 require approval",
            check_fn=lambda d: d.confidence >= 0.7 or d.requires_approval,
            severity=SafetyLevel.WARNING
        ))

    async def validate(self, decision: Any) -> Dict[str, Any]:
        """
        Validate a decision against safety rules.

        Args:
            decision: AIDecision to validate

        Returns:
            Validation result
        """
        # Check emergency stop
        if self._emergency_stop:
            return {
                'safe': False,
                'level': SafetyLevel.BLOCKED.value,
                'reason': 'Emergency stop is active'
            }

        # Check approval requirement
        if decision.requires_approval:
            if not self._approval_required.get(decision.decision_id, False):
                return {
                    'safe': False,
                    'level': SafetyLevel.WARNING.value,
                    'reason': 'Human approval required',
                    'approval_needed': True
                }

        # Check all rules
        violations = []
        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                passed = rule.check_fn(decision)
                if not passed:
                    violation = SafetyViolation(
                        rule_id=rule.rule_id,
                        message=rule.description,
                        severity=rule.severity,
                        decision_id=decision.decision_id
                    )
                    violations.append(violation)
                    self._violations.append(violation)
            except Exception as e:
                logger.error(f"Safety rule {rule.rule_id} check failed: {e}")

        if violations:
            # Return worst violation
            worst = max(violations, key=lambda v: list(SafetyLevel).index(v.severity))
            return {
                'safe': worst.severity != SafetyLevel.BLOCKED,
                'level': worst.severity.value,
                'reason': worst.message,
                'violations': [
                    {'rule': v.rule_id, 'message': v.message}
                    for v in violations
                ]
            }

        return {
            'safe': True,
            'level': SafetyLevel.SAFE.value,
            'reason': 'All safety checks passed'
        }

    def add_rule(self, rule: SafetyRule) -> None:
        """Add a custom safety rule."""
        self._rules.append(rule)
        logger.info(f"Added safety rule: {rule.name}")

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a safety rule."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a safety rule (requires authorization)."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = False
                logger.warning(f"Safety rule {rule_id} disabled")
                return True
        return False

    def grant_approval(self, decision_id: str) -> None:
        """Grant human approval for a decision."""
        self._approval_required[decision_id] = True
        logger.info(f"Approval granted for decision {decision_id}")

    def emergency_stop(self) -> None:
        """Activate emergency stop."""
        self._emergency_stop = True
        logger.critical("EMERGENCY STOP ACTIVATED")

    def reset_emergency_stop(self) -> None:
        """Reset emergency stop (requires authorization)."""
        self._emergency_stop = False
        logger.warning("Emergency stop reset")

    def get_violations(self,
                      limit: int = 100,
                      severity: Optional[SafetyLevel] = None) -> List[SafetyViolation]:
        """Get recent safety violations."""
        violations = self._violations[-limit:]
        if severity:
            violations = [v for v in violations if v.severity == severity]
        return violations

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all safety rules."""
        return [
            {
                'rule_id': r.rule_id,
                'name': r.name,
                'description': r.description,
                'severity': r.severity.value,
                'enabled': r.enabled
            }
            for r in self._rules
        ]

    def get_status(self) -> Dict[str, Any]:
        """Get safety system status."""
        return {
            'emergency_stop': self._emergency_stop,
            'rules_enabled': len([r for r in self._rules if r.enabled]),
            'rules_total': len(self._rules),
            'recent_violations': len(self._violations[-100:]),
            'pending_approvals': len([k for k, v in self._approval_required.items() if not v])
        }
