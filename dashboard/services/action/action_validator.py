"""
Action Validator - Pre-execution validation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """Validation rule for actions."""
    rule_id: str
    name: str
    action_types: List[str]  # Action types this applies to
    check_fn: Callable[[Any], Dict[str, Any]]
    enabled: bool = True


class ActionValidator:
    """
    Validate actions before execution.

    Features:
    - Type-specific validation
    - Parameter bounds checking
    - State prerequisite verification
    - Custom rule support
    """

    def __init__(self):
        self._rules: List[ValidationRule] = []
        self._state_provider: Optional[Callable[[], Dict]] = None
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        """Load default validation rules."""
        # Temperature range validation
        self._rules.append(ValidationRule(
            rule_id="TEMP_RANGE",
            name="Temperature Range",
            action_types=["temperature_adjust"],
            check_fn=self._check_temp_range
        ))

        # Speed range validation
        self._rules.append(ValidationRule(
            rule_id="SPEED_RANGE",
            name="Speed Range",
            action_types=["speed_adjust"],
            check_fn=self._check_speed_range
        ))

        # Parameter presence validation
        self._rules.append(ValidationRule(
            rule_id="PARAMS_PRESENT",
            name="Required Parameters",
            action_types=["*"],
            check_fn=self._check_params_present
        ))

    def _check_temp_range(self, action: Any) -> Dict[str, Any]:
        """Check temperature is in valid range."""
        params = action.parameters
        temp = params.get('value', params.get('temperature', 0))

        if temp < 0:
            return {'valid': False, 'reason': 'Temperature cannot be negative'}
        if temp > 350:
            return {'valid': False, 'reason': 'Temperature exceeds maximum (350C)'}

        return {'valid': True}

    def _check_speed_range(self, action: Any) -> Dict[str, Any]:
        """Check speed is in valid range."""
        params = action.parameters
        speed = params.get('value', params.get('speed', 100))

        if speed < 10:
            return {'valid': False, 'reason': 'Speed too low (minimum 10%)'}
        if speed > 300:
            return {'valid': False, 'reason': 'Speed exceeds maximum (300%)'}

        return {'valid': True}

    def _check_params_present(self, action: Any) -> Dict[str, Any]:
        """Check required parameters are present."""
        required_params = {
            'temperature_adjust': ['value'],
            'speed_adjust': ['value'],
            'z_offset_adjust': ['value'],
        }

        action_type = action.action_type
        required = required_params.get(action_type, [])

        params = action.parameters
        missing = [p for p in required if p not in params]

        if missing:
            return {'valid': False, 'reason': f'Missing parameters: {missing}'}

        return {'valid': True}

    def set_state_provider(self, provider: Callable[[], Dict]) -> None:
        """Set function to get current system state."""
        self._state_provider = provider

    def add_rule(self, rule: ValidationRule) -> None:
        """Add custom validation rule."""
        self._rules.append(rule)

    async def validate(self, action: Any) -> Dict[str, Any]:
        """
        Validate an action.

        Args:
            action: ActionStep to validate

        Returns:
            Validation result
        """
        action_type = getattr(action, 'action_type', 'unknown')

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check if rule applies to this action type
            if '*' not in rule.action_types and action_type not in rule.action_types:
                continue

            try:
                result = rule.check_fn(action)
                if not result.get('valid', True):
                    logger.warning(f"Validation failed - {rule.name}: {result.get('reason')}")
                    return result
            except Exception as e:
                logger.error(f"Validation rule {rule.rule_id} error: {e}")
                return {'valid': False, 'reason': f'Validation error: {str(e)}'}

        return {'valid': True}

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all validation rules."""
        return [
            {
                'rule_id': r.rule_id,
                'name': r.name,
                'action_types': r.action_types,
                'enabled': r.enabled
            }
            for r in self._rules
        ]
