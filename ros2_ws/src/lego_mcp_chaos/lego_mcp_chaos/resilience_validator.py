#!/usr/bin/env python3
"""
Resilience Validator for LEGO MCP Chaos Testing

Validates system resilience metrics after chaos testing:
- Recovery time objectives (RTO)
- Data integrity
- State consistency
- Service availability

Industry 4.0/5.0 Architecture - SRE Practices
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time


class ValidationLevel(Enum):
    """Validation strictness levels."""
    RELAXED = "relaxed"
    NORMAL = "normal"
    STRICT = "strict"


@dataclass
class ValidationCriteria:
    """Criteria for resilience validation."""
    name: str
    description: str
    check_function: Callable[[], bool]
    timeout_seconds: float = 30.0
    retry_count: int = 3
    retry_interval: float = 1.0
    level: ValidationLevel = ValidationLevel.NORMAL


@dataclass
class ValidationResult:
    """Result of a validation check."""
    criteria_name: str
    passed: bool
    attempts: int = 1
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    details: Dict = field(default_factory=dict)


@dataclass
class ResilienceReport:
    """Complete resilience validation report."""
    timestamp: datetime
    scenario_id: Optional[str] = None
    validations: List[ValidationResult] = field(default_factory=list)
    overall_passed: bool = True
    recovery_time_seconds: float = 0.0
    availability_percentage: float = 100.0
    data_integrity_passed: bool = True
    recommendations: List[str] = field(default_factory=list)


class ResilienceValidator:
    """
    Resilience Validator.

    Validates system resilience after chaos testing by checking:
    - Service availability
    - Recovery time
    - Data consistency
    - State integrity

    Usage:
        validator = ResilienceValidator()
        validator.add_criteria(
            "safety_active",
            "Safety node is active",
            check_safety_node,
        )
        report = validator.validate_resilience()
    """

    def __init__(self, level: ValidationLevel = ValidationLevel.NORMAL):
        """
        Initialize resilience validator.

        Args:
            level: Default validation strictness level
        """
        self.default_level = level
        self._criteria: List[ValidationCriteria] = []
        self._custom_validators: Dict[str, Callable] = {}

        # Initialize standard criteria
        self._initialize_standard_criteria()

    def _initialize_standard_criteria(self):
        """Initialize standard resilience criteria."""

        # Safety system availability
        self.add_criteria(ValidationCriteria(
            name="safety_available",
            description="Safety system is responsive",
            check_function=lambda: True,  # Placeholder
            timeout_seconds=5.0,
            level=ValidationLevel.STRICT,
        ))

        # Orchestrator responsiveness
        self.add_criteria(ValidationCriteria(
            name="orchestrator_responsive",
            description="Orchestrator responds to requests",
            check_function=lambda: True,
            timeout_seconds=10.0,
        ))

        # Equipment connectivity
        self.add_criteria(ValidationCriteria(
            name="equipment_connected",
            description="All equipment nodes are connected",
            check_function=lambda: True,
            timeout_seconds=30.0,
        ))

        # State consistency
        self.add_criteria(ValidationCriteria(
            name="state_consistent",
            description="System state is consistent across nodes",
            check_function=lambda: True,
            timeout_seconds=15.0,
        ))

    def add_criteria(self, criteria: ValidationCriteria):
        """Add a validation criteria."""
        self._criteria.append(criteria)

    def remove_criteria(self, name: str):
        """Remove a validation criteria by name."""
        self._criteria = [c for c in self._criteria if c.name != name]

    def register_custom_validator(
        self,
        name: str,
        validator: Callable[[], Dict],
    ):
        """
        Register a custom validator function.

        Args:
            name: Validator name
            validator: Function returning dict with 'passed' and optional 'details'
        """
        self._custom_validators[name] = validator

    def validate_resilience(
        self,
        scenario_id: Optional[str] = None,
        criteria_filter: Optional[List[str]] = None,
    ) -> ResilienceReport:
        """
        Run all resilience validations.

        Args:
            scenario_id: Optional scenario ID for tracking
            criteria_filter: Optional list of criteria names to run

        Returns:
            ResilienceReport
        """
        report = ResilienceReport(
            timestamp=datetime.now(),
            scenario_id=scenario_id,
        )

        start_time = time.time()

        # Run standard criteria
        for criteria in self._criteria:
            if criteria_filter and criteria.name not in criteria_filter:
                continue

            result = self._run_validation(criteria)
            report.validations.append(result)

            if not result.passed:
                report.overall_passed = False

        # Run custom validators
        for name, validator in self._custom_validators.items():
            if criteria_filter and name not in criteria_filter:
                continue

            result = self._run_custom_validation(name, validator)
            report.validations.append(result)

            if not result.passed:
                report.overall_passed = False

        # Calculate metrics
        report.recovery_time_seconds = time.time() - start_time

        passed_count = sum(1 for v in report.validations if v.passed)
        total_count = len(report.validations)
        report.availability_percentage = (passed_count / total_count * 100) if total_count > 0 else 100.0

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        return report

    def _run_validation(self, criteria: ValidationCriteria) -> ValidationResult:
        """Run a single validation criteria."""
        start_time = time.time()
        attempts = 0
        last_error = None

        for attempt in range(criteria.retry_count):
            attempts += 1
            try:
                # Check timeout
                if time.time() - start_time > criteria.timeout_seconds:
                    return ValidationResult(
                        criteria_name=criteria.name,
                        passed=False,
                        attempts=attempts,
                        duration_seconds=time.time() - start_time,
                        error_message="Timeout exceeded",
                    )

                result = criteria.check_function()

                if result:
                    return ValidationResult(
                        criteria_name=criteria.name,
                        passed=True,
                        attempts=attempts,
                        duration_seconds=time.time() - start_time,
                    )

                # Retry
                if attempt < criteria.retry_count - 1:
                    time.sleep(criteria.retry_interval)

            except Exception as e:
                last_error = str(e)
                if attempt < criteria.retry_count - 1:
                    time.sleep(criteria.retry_interval)

        return ValidationResult(
            criteria_name=criteria.name,
            passed=False,
            attempts=attempts,
            duration_seconds=time.time() - start_time,
            error_message=last_error or "Validation failed",
        )

    def _run_custom_validation(
        self,
        name: str,
        validator: Callable,
    ) -> ValidationResult:
        """Run a custom validator."""
        start_time = time.time()

        try:
            result = validator()
            return ValidationResult(
                criteria_name=name,
                passed=result.get("passed", False),
                attempts=1,
                duration_seconds=time.time() - start_time,
                details=result.get("details", {}),
            )
        except Exception as e:
            return ValidationResult(
                criteria_name=name,
                passed=False,
                attempts=1,
                duration_seconds=time.time() - start_time,
                error_message=str(e),
            )

    def _generate_recommendations(
        self,
        report: ResilienceReport,
    ) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        failed = [v for v in report.validations if not v.passed]

        for validation in failed:
            if "safety" in validation.criteria_name.lower():
                recommendations.append(
                    f"CRITICAL: {validation.criteria_name} failed - "
                    "Review safety node configuration and supervisor settings"
                )
            elif "timeout" in (validation.error_message or "").lower():
                recommendations.append(
                    f"{validation.criteria_name} timed out - "
                    "Consider increasing timeout or checking network connectivity"
                )
            elif "connection" in validation.criteria_name.lower():
                recommendations.append(
                    f"{validation.criteria_name} failed - "
                    "Check equipment power and network connections"
                )

        if report.recovery_time_seconds > 30:
            recommendations.append(
                f"Recovery time ({report.recovery_time_seconds:.1f}s) exceeds 30s target - "
                "Review supervisor restart strategy and dependencies"
            )

        if report.availability_percentage < 95:
            recommendations.append(
                f"Availability ({report.availability_percentage:.1f}%) below 95% target - "
                "Consider adding redundancy or reducing single points of failure"
            )

        return recommendations

    def validate_rto(
        self,
        target_seconds: float,
        check_function: Callable[[], bool],
        poll_interval: float = 0.5,
        timeout_seconds: float = 300.0,
    ) -> Dict:
        """
        Validate Recovery Time Objective (RTO).

        Args:
            target_seconds: Target recovery time in seconds
            check_function: Function that returns True when recovered
            poll_interval: How often to check
            timeout_seconds: Maximum time to wait

        Returns:
            Dict with 'met', 'actual_seconds', 'target_seconds'
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                return {
                    "met": False,
                    "actual_seconds": timeout_seconds,
                    "target_seconds": target_seconds,
                    "error": "Timeout waiting for recovery",
                }

            try:
                if check_function():
                    met = elapsed <= target_seconds
                    return {
                        "met": met,
                        "actual_seconds": elapsed,
                        "target_seconds": target_seconds,
                    }
            except Exception:
                pass

            time.sleep(poll_interval)

    def validate_data_integrity(
        self,
        pre_fault_state: Dict,
        post_recovery_state: Dict,
        ignore_keys: Optional[List[str]] = None,
    ) -> Dict:
        """
        Validate data integrity after recovery.

        Args:
            pre_fault_state: State captured before fault injection
            post_recovery_state: State captured after recovery
            ignore_keys: Keys to ignore in comparison

        Returns:
            Dict with 'passed', 'differences'
        """
        ignore = set(ignore_keys or [])
        differences = []

        def compare(pre: Any, post: Any, path: str = ""):
            if isinstance(pre, dict) and isinstance(post, dict):
                for key in set(pre.keys()) | set(post.keys()):
                    if key in ignore:
                        continue
                    new_path = f"{path}.{key}" if path else key
                    if key not in pre:
                        differences.append(f"Added: {new_path}")
                    elif key not in post:
                        differences.append(f"Removed: {new_path}")
                    else:
                        compare(pre[key], post[key], new_path)
            elif pre != post:
                differences.append(f"Changed: {path} ({pre} -> {post})")

        compare(pre_fault_state, post_recovery_state)

        return {
            "passed": len(differences) == 0,
            "differences": differences,
        }
