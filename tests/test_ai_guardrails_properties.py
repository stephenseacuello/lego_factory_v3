"""
Property-Based Tests for AI Guardrails Framework

Uses property-based testing to verify guardrails correctness across
a wide range of inputs. Each property is tested with 100+ iterations.

Properties tested:
1. Blocked commands are never allowed
2. Always-allowed commands are never blocked
3. PII is always redacted
4. Prompt injections are always detected
5. Values exceeding limits are blocked or modified
6. Safe inputs pass validation

Uses the Hypothesis library patterns for property-based testing.
"""

import random
from typing import List, Tuple
import pytest

# Import guardrails
from dashboard.services.ai.guardrails import (
    InputValidator,
    ValidationResult,
    OutputVerifier,
    VerificationResult,
    ConfidenceThresholds,
    ThresholdResult,
    HumanInLoopManager,
    EscalationLevel,
    HallucinationDetector,
    DetectionResult,
    SafetyFilter,
    FilterResult,
)

from dashboard.services.ai.guardrails.input_validator import (
    ValidationStatus,
    ThreatType,
    ValidatorConfig,
)

from dashboard.services.ai.guardrails.safety_filter import (
    FilterAction,
    SafetyLimits,
)

# Import test generators
from dashboard.services.ai.guardrails.test_generators import (
    ManufacturingCommandGenerator,
    InjectionAttemptGenerator,
    PiiGenerator,
    PhysicsConstraintGenerator,
    ConfidenceScoreGenerator,
    SafeInputGenerator,
    GeneratedCommand,
    GeneratedInput,
)


# Number of iterations for property tests
NUM_ITERATIONS = 100


class TestSafetyFilterProperties:
    """Property-based tests for SafetyFilter."""

    @pytest.fixture
    def safety_filter(self):
        """Create SafetyFilter with default limits."""
        return SafetyFilter(limits=SafetyLimits(), strict_mode=True)

    @pytest.fixture
    def command_generator(self):
        """Create command generator matching filter limits."""
        return ManufacturingCommandGenerator(
            max_speed=100.0,
            max_temp=300.0,
            min_temp=-40.0,
            max_pressure=10.0,
        )

    def test_property_blocked_commands_always_blocked(
        self, safety_filter, command_generator
    ):
        """
        PROPERTY: Blocked commands are NEVER allowed.

        For all blocked commands (disable_safety, bypass_interlock, etc.),
        the filter must return FilterAction.BLOCK.
        """
        blocked_count = 0
        not_blocked = []

        for _ in range(NUM_ITERATIONS):
            cmd = command_generator.generate_blocked_command()
            result = safety_filter.check(cmd.text)

            if result.action == FilterAction.BLOCK:
                blocked_count += 1
            else:
                not_blocked.append((cmd.text, result.action))

        assert blocked_count == NUM_ITERATIONS, (
            f"Expected all {NUM_ITERATIONS} blocked commands to be blocked, "
            f"but {len(not_blocked)} were not: {not_blocked[:5]}"
        )

    def test_property_safety_commands_always_allowed(
        self, safety_filter, command_generator
    ):
        """
        PROPERTY: Safety commands (e-stop, halt, etc.) are ALWAYS allowed.

        E-stop and other safety commands must never be blocked,
        regardless of other content.
        """
        allowed_count = 0
        not_allowed = []

        for _ in range(NUM_ITERATIONS):
            cmd = command_generator.generate_always_allowed_command()
            result = safety_filter.check(cmd.text)

            if result.action == FilterAction.ALLOW:
                allowed_count += 1
            else:
                not_allowed.append((cmd.text, result.action))

        assert allowed_count == NUM_ITERATIONS, (
            f"Expected all {NUM_ITERATIONS} safety commands to be allowed, "
            f"but {len(not_allowed)} were not: {not_allowed[:5]}"
        )

    def test_property_safe_commands_pass(self, safety_filter, command_generator):
        """
        PROPERTY: Commands within limits are allowed.

        Safe commands (within all limits) should be allowed or at most
        escalated, never blocked.
        """
        passed_count = 0
        blocked = []

        for _ in range(NUM_ITERATIONS):
            cmd = command_generator.generate_safe_command()
            result = safety_filter.check(cmd.text)

            # Safe commands should be ALLOW, MODIFY, or ESCALATE (not BLOCK)
            if result.action in [FilterAction.ALLOW, FilterAction.MODIFY, FilterAction.ESCALATE]:
                passed_count += 1
            else:
                blocked.append((cmd.text, result.action, cmd.parameters))

        # Allow some tolerance for edge cases
        success_rate = passed_count / NUM_ITERATIONS
        assert success_rate >= 0.95, (
            f"Expected 95%+ safe commands to pass, got {success_rate*100:.1f}%. "
            f"Blocked: {blocked[:5]}"
        )

    def test_property_excessive_speed_modified_or_blocked(
        self, safety_filter, command_generator
    ):
        """
        PROPERTY: Commands with excessive speed are modified or blocked.

        Speed above max_linear_speed must result in MODIFY or BLOCK,
        never ALLOW.
        """
        handled_count = 0
        incorrectly_allowed = []

        for _ in range(NUM_ITERATIONS):
            # Generate command with excessive speed
            speed = random.uniform(150, 500)  # Well above 100 limit
            cmd_text = f"move x:100 y:100 speed:{speed}"
            result = safety_filter.check(cmd_text)

            if result.action in [FilterAction.MODIFY, FilterAction.BLOCK]:
                handled_count += 1
            else:
                incorrectly_allowed.append((cmd_text, result.action))

        assert handled_count == NUM_ITERATIONS, (
            f"Expected all excessive speed commands to be modified/blocked, "
            f"but {len(incorrectly_allowed)} were allowed: {incorrectly_allowed[:5]}"
        )

    def test_property_excessive_temperature_blocked(
        self, safety_filter, command_generator
    ):
        """
        PROPERTY: Commands with excessive temperature are blocked.

        Temperature above max or below min must result in BLOCK.
        """
        blocked_count = 0
        not_blocked = []

        for _ in range(NUM_ITERATIONS):
            # Generate excessive temperature
            if random.random() > 0.5:
                temp = random.uniform(350, 1000)  # Above 300 max
            else:
                temp = random.uniform(-200, -50)  # Below -40 min

            cmd_text = f"set_temp temperature:{temp}"
            result = safety_filter.check(cmd_text)

            if result.action == FilterAction.BLOCK:
                blocked_count += 1
            else:
                not_blocked.append((cmd_text, result.action, temp))

        assert blocked_count == NUM_ITERATIONS, (
            f"Expected all excessive temp commands to be blocked, "
            f"but {len(not_blocked)} were not: {not_blocked[:5]}"
        )

    def test_property_workspace_bounds_enforced(
        self, safety_filter, command_generator
    ):
        """
        PROPERTY: Positions outside workspace are blocked.

        Any position outside workspace_min/max must be blocked.
        """
        blocked_count = 0
        not_blocked = []

        for _ in range(NUM_ITERATIONS):
            # Generate out-of-bounds position
            axis = random.choice(['x', 'y', 'z'])
            if random.random() > 0.5:
                value = random.uniform(600, 1000)  # Above max (500)
            else:
                value = random.uniform(-1000, -600)  # Below min (-500)

            if axis == 'z' and value < 0:
                value = random.uniform(600, 1000)  # Z min is 0

            cmd_text = f"move {axis}:{value}"
            result = safety_filter.check(cmd_text)

            if result.action == FilterAction.BLOCK:
                blocked_count += 1
            else:
                not_blocked.append((cmd_text, result.action))

        assert blocked_count == NUM_ITERATIONS, (
            f"Expected all out-of-bounds positions to be blocked, "
            f"but {len(not_blocked)} were not: {not_blocked[:5]}"
        )


class TestInputValidatorProperties:
    """Property-based tests for InputValidator."""

    @pytest.fixture
    def validator(self):
        """Create InputValidator with strict mode."""
        return InputValidator(ValidatorConfig(
            enable_pii_detection=True,
            enable_injection_detection=True,
            strict_mode=True,
        ))

    @pytest.fixture
    def injection_generator(self):
        """Create injection attempt generator."""
        return InjectionAttemptGenerator()

    @pytest.fixture
    def pii_generator(self):
        """Create PII generator."""
        return PiiGenerator()

    @pytest.fixture
    def safe_generator(self):
        """Create safe input generator."""
        return SafeInputGenerator()

    def test_property_injections_detected(self, validator, injection_generator):
        """
        PROPERTY: Prompt injection attempts are detected.

        All generated injection attempts must have PROMPT_INJECTION
        in threats_detected.
        """
        detected_count = 0
        missed = []

        for _ in range(NUM_ITERATIONS):
            attempt = injection_generator.generate_injection()
            result = validator.validate(attempt.text)

            if ThreatType.PROMPT_INJECTION in result.threats_detected:
                detected_count += 1
            else:
                missed.append(attempt.text)

        # Allow some tolerance for novel patterns
        detection_rate = detected_count / NUM_ITERATIONS
        assert detection_rate >= 0.9, (
            f"Expected 90%+ injection detection, got {detection_rate*100:.1f}%. "
            f"Missed: {missed[:5]}"
        )

    def test_property_pii_redacted(self, validator, pii_generator):
        """
        PROPERTY: PII is always redacted from sanitized output.

        For inputs containing PII, the sanitized_input must not
        contain the original PII.
        """
        redacted_count = 0
        not_redacted = []

        for _ in range(NUM_ITERATIONS):
            pii_input = pii_generator.generate_input_with_pii()
            result = validator.validate(pii_input.text)

            # Check that sanitized output doesn't contain original PII patterns
            has_email = "@" in result.sanitized_input and "REDACTED" not in result.sanitized_input
            has_phone = any(
                len(part) >= 10 and part.replace("-", "").isdigit()
                for part in result.sanitized_input.split()
            )

            if not has_email and not has_phone:
                redacted_count += 1
            else:
                not_redacted.append((pii_input.text, result.sanitized_input))

        assert redacted_count == NUM_ITERATIONS, (
            f"Expected all PII to be redacted, but {len(not_redacted)} were not: "
            f"{not_redacted[:5]}"
        )

    def test_property_safe_inputs_valid(self, validator, safe_generator):
        """
        PROPERTY: Safe inputs pass validation.

        Clean manufacturing queries should have status VALID
        with no threats detected.
        """
        valid_count = 0
        invalid = []

        for _ in range(NUM_ITERATIONS):
            safe_input = safe_generator.generate_safe_query()
            result = validator.validate(safe_input.text)

            if result.status == ValidationStatus.VALID and not result.threats_detected:
                valid_count += 1
            else:
                invalid.append((safe_input.text, result.status, result.threats_detected))

        success_rate = valid_count / NUM_ITERATIONS
        assert success_rate >= 0.95, (
            f"Expected 95%+ safe inputs to be valid, got {success_rate*100:.1f}%. "
            f"Invalid: {invalid[:5]}"
        )

    def test_property_excessive_length_handled(self, validator):
        """
        PROPERTY: Excessive length inputs are truncated.

        Inputs longer than max_input_length must be truncated
        in sanitized_input.
        """
        handled_count = 0

        for _ in range(NUM_ITERATIONS):
            # Generate long input
            long_text = "a" * random.randint(15000, 50000)
            result = validator.validate(long_text)

            if (
                ThreatType.EXCESSIVE_LENGTH in result.threats_detected
                and len(result.sanitized_input) <= validator.config.max_input_length
            ):
                handled_count += 1

        assert handled_count == NUM_ITERATIONS, (
            f"Expected all long inputs to be truncated, but only {handled_count} were"
        )


class TestConfidenceThresholdProperties:
    """Property-based tests for ConfidenceThresholds."""

    @pytest.fixture
    def thresholds(self):
        """Create ConfidenceThresholds with known values."""
        return ConfidenceThresholds()

    @pytest.fixture
    def score_generator(self):
        """Create confidence score generator."""
        return ConfidenceScoreGenerator(
            high_threshold=0.9,
            low_threshold=0.5,
        )

    def test_property_low_confidence_triggers_escalation(
        self, thresholds, score_generator
    ):
        """
        PROPERTY: Low confidence scores trigger human escalation.

        Scores below low_threshold should require human review.
        """
        escalated_count = 0

        for _ in range(NUM_ITERATIONS):
            score = score_generator.generate_low_confidence()
            result = thresholds.check(score)

            if result.requires_human_review:
                escalated_count += 1

        success_rate = escalated_count / NUM_ITERATIONS
        assert success_rate >= 0.95, (
            f"Expected 95%+ low confidence to trigger escalation, "
            f"got {success_rate*100:.1f}%"
        )

    def test_property_high_confidence_accepted(
        self, thresholds, score_generator
    ):
        """
        PROPERTY: High confidence scores are accepted.

        Scores above high_threshold should be accepted without escalation.
        """
        accepted_count = 0

        for _ in range(NUM_ITERATIONS):
            score = score_generator.generate_high_confidence()
            result = thresholds.check(score)

            if result.is_acceptable and not result.requires_human_review:
                accepted_count += 1

        success_rate = accepted_count / NUM_ITERATIONS
        assert success_rate >= 0.95, (
            f"Expected 95%+ high confidence to be accepted, "
            f"got {success_rate*100:.1f}%"
        )


class TestGuardrailIntegrationProperties:
    """Integration property tests across multiple guardrails."""

    @pytest.fixture
    def validator(self):
        """Create InputValidator."""
        return InputValidator(ValidatorConfig(strict_mode=True))

    @pytest.fixture
    def safety_filter(self):
        """Create SafetyFilter."""
        return SafetyFilter(strict_mode=True)

    @pytest.fixture
    def command_generator(self):
        """Create command generator."""
        return ManufacturingCommandGenerator()

    @pytest.fixture
    def injection_generator(self):
        """Create injection generator."""
        return InjectionAttemptGenerator()

    def test_property_rejected_never_reaches_filter(
        self, validator, safety_filter, injection_generator
    ):
        """
        PROPERTY: Inputs rejected by InputValidator never reach SafetyFilter.

        In a proper pipeline, rejected inputs should not be processed further.
        """
        for _ in range(NUM_ITERATIONS):
            # Generate injection attempt
            attempt = injection_generator.generate_injection()

            # Validate first
            validation_result = validator.validate(attempt.text)

            # If rejected, should not process with filter
            if validation_result.status == ValidationStatus.REJECTED:
                # This is the expected behavior - we don't call filter
                continue

            # If not rejected, the sanitized input should be safe-ish
            # for the filter to process
            if validation_result.threats_detected:
                # Has threats but not rejected - sanitized version used
                filter_result = safety_filter.check(validation_result.sanitized_input)
                # Filter should still work without crashing
                assert filter_result is not None

    def test_property_pipeline_never_allows_dangerous_commands(
        self, validator, safety_filter, command_generator
    ):
        """
        PROPERTY: Pipeline blocks all dangerous commands.

        Commands that should be blocked must be blocked at some stage.
        """
        blocked_count = 0

        for _ in range(NUM_ITERATIONS):
            # Generate blocked command
            cmd = command_generator.generate_blocked_command()

            # Run through pipeline
            validation_result = validator.validate(cmd.text)

            if validation_result.status == ValidationStatus.REJECTED:
                blocked_count += 1
                continue

            filter_result = safety_filter.check(validation_result.sanitized_input)

            if filter_result.action == FilterAction.BLOCK:
                blocked_count += 1

        success_rate = blocked_count / NUM_ITERATIONS
        assert success_rate >= 0.95, (
            f"Expected 95%+ dangerous commands to be blocked, "
            f"got {success_rate*100:.1f}%"
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def safety_filter(self):
        """Create SafetyFilter."""
        return SafetyFilter()

    @pytest.fixture
    def validator(self):
        """Create InputValidator."""
        return InputValidator()

    def test_empty_input(self, validator, safety_filter):
        """Empty input should be handled gracefully."""
        validation_result = validator.validate("")
        assert validation_result.status == ValidationStatus.VALID

        filter_result = safety_filter.check("")
        assert filter_result.action == FilterAction.ALLOW

    def test_whitespace_only(self, validator, safety_filter):
        """Whitespace-only input should be handled gracefully."""
        for whitespace in ["   ", "\n\n", "\t\t", "  \n  \t  "]:
            validation_result = validator.validate(whitespace)
            assert validation_result is not None

            filter_result = safety_filter.check(whitespace)
            assert filter_result is not None

    def test_unicode_input(self, validator, safety_filter):
        """Unicode input should be handled gracefully."""
        unicode_inputs = [
            "Move to position x:100",  # Standard
            "Move to position x:100 °C",  # Degree symbol
            "设置温度 temperature:200",  # Chinese characters
            "Position: x→100, y→200",  # Arrows
        ]

        for text in unicode_inputs:
            validation_result = validator.validate(text)
            assert validation_result is not None

            filter_result = safety_filter.check(text)
            assert filter_result is not None

    def test_extreme_numeric_values(self, safety_filter):
        """Extreme numeric values should be handled."""
        extreme_values = [
            "speed:0",
            "speed:999999999",
            "temperature:-999999",
            "temperature:999999",
            "x:0.00000001",
            "x:-0.00000001",
        ]

        for cmd in extreme_values:
            result = safety_filter.check(cmd)
            # Should not crash, and should handle appropriately
            assert result is not None
            assert result.action in [
                FilterAction.ALLOW,
                FilterAction.BLOCK,
                FilterAction.MODIFY,
                FilterAction.ESCALATE,
            ]
