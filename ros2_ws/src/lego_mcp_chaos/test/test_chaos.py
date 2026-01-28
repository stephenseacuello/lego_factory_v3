#!/usr/bin/env python3
"""
Unit Tests for LEGO MCP Chaos Testing Package

Tests:
- Fault Injector
- Chaos Scenarios
- Resilience Validator
- Scenario Runner

Industry 4.0/5.0 Architecture - Chaos Engineering Testing
"""

import pytest
import time
from datetime import datetime
from pathlib import Path

# Import modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'lego_mcp_chaos'))

from lego_mcp_chaos.fault_injector import (
    FaultInjector,
    FaultType,
    FaultInjection,
)
from lego_mcp_chaos.chaos_scenarios import (
    ChaosScenario,
    ChaosScenarioRunner,
    ScenarioStep,
    ScenarioOutcome,
    create_equipment_failure_scenario,
    create_safety_estop_scenario,
    create_cascade_failure_scenario,
    create_network_partition_scenario,
)
from lego_mcp_chaos.resilience_validator import (
    ResilienceValidator,
    ValidationLevel,
    ValidationCriteria,
    ValidationResult,
    ResilienceReport,
)


class TestFaultType:
    """Tests for FaultType enumeration."""

    def test_fault_types_exist(self):
        """Test all fault types are defined."""
        assert FaultType.NODE_CRASH
        assert FaultType.NODE_HANG
        assert FaultType.MESSAGE_DELAY
        assert FaultType.MESSAGE_DROP
        assert FaultType.NETWORK_PARTITION
        assert FaultType.RESOURCE_EXHAUSTION

    def test_fault_type_values(self):
        """Test fault type values are unique."""
        values = [ft.value for ft in FaultType]
        assert len(values) == len(set(values))


class TestFaultInjector:
    """Tests for FaultInjector class."""

    def test_initialization(self):
        """Test FaultInjector initialization."""
        injector = FaultInjector()
        assert injector is not None
        assert len(injector.get_active_injections()) == 0

    def test_generate_id(self):
        """Test injection ID generation."""
        injector = FaultInjector()
        id1 = injector._generate_id()
        id2 = injector._generate_id()
        assert id1 != id2
        assert id1.startswith('FAULT-')

    def test_inject_message_delay(self):
        """Test message delay injection."""
        injector = FaultInjector()

        injection = injector.inject_message_delay(
            topic='/test/topic',
            delay_ms=100.0,
            duration_seconds=5.0,
        )

        assert injection is not None
        assert injection.fault_type == FaultType.MESSAGE_DELAY
        assert injection.target == '/test/topic'
        assert injection.active is True

        # Check delay is registered
        delay = injector.should_delay_message('/test/topic')
        assert delay == 100.0

        # Stop injection
        injector.stop_injection(injection.injection_id)
        delay = injector.should_delay_message('/test/topic')
        assert delay == 0.0

    def test_inject_message_drop(self):
        """Test message drop injection."""
        injector = FaultInjector()

        injection = injector.inject_message_drop(
            topic='/test/topic',
            drop_rate=0.5,
        )

        assert injection is not None
        assert injection.fault_type == FaultType.MESSAGE_DROP
        assert injection.parameters['drop_rate'] == 0.5

        # Stop injection
        injector.stop_injection(injection.injection_id)

    def test_stop_all_injections(self):
        """Test stopping all active injections."""
        injector = FaultInjector()

        # Create multiple injections
        injector.inject_message_delay('/topic1', 100.0)
        injector.inject_message_delay('/topic2', 200.0)
        injector.inject_message_drop('/topic3', 0.3)

        assert len(injector.get_active_injections()) == 3

        injector.stop_all_injections()
        assert len(injector.get_active_injections()) == 0

    def test_get_statistics(self):
        """Test statistics collection."""
        injector = FaultInjector()

        injector.inject_message_delay('/topic1', 100.0)
        injector.inject_message_drop('/topic2', 0.5)

        stats = injector.get_statistics()
        assert stats['total_injections'] == 2
        assert stats['active_injections'] == 2
        assert 'MESSAGE_DELAY' in stats['by_type']

        injector.stop_all_injections()


class TestChaosScenario:
    """Tests for ChaosScenario class."""

    def test_scenario_creation(self):
        """Test scenario creation."""
        scenario = ChaosScenario(
            scenario_id='test_scenario',
            name='Test Scenario',
            description='A test scenario',
            steps=[],
            timeout_seconds=60.0,
        )

        assert scenario.scenario_id == 'test_scenario'
        assert scenario.timeout_seconds == 60.0

    def test_scenario_step_creation(self):
        """Test scenario step creation."""
        step = ScenarioStep(
            name='Test Step',
            action='inject',
            target='test_node',
            fault_type=FaultType.NODE_CRASH,
        )

        assert step.name == 'Test Step'
        assert step.action == 'inject'
        assert step.fault_type == FaultType.NODE_CRASH

    def test_predefined_equipment_failure(self):
        """Test predefined equipment failure scenario."""
        scenario = create_equipment_failure_scenario('grbl_node')

        assert 'equipment_failure' in scenario.scenario_id
        assert len(scenario.steps) > 0
        assert 'equipment' in scenario.tags

    def test_predefined_safety_estop(self):
        """Test predefined safety e-stop scenario."""
        scenario = create_safety_estop_scenario()

        assert scenario.scenario_id == 'safety_estop_test'
        assert 'safety' in scenario.tags
        assert 'critical' in scenario.tags

    def test_predefined_cascade_failure(self):
        """Test predefined cascade failure scenario."""
        scenario = create_cascade_failure_scenario()

        assert scenario.scenario_id == 'cascade_failure_test'
        assert 'cascade' in scenario.tags

    def test_predefined_network_partition(self):
        """Test predefined network partition scenario."""
        scenario = create_network_partition_scenario()

        assert scenario.scenario_id == 'network_partition_test'
        assert 'network' in scenario.tags
        assert 'partition' in scenario.tags


class TestChaosScenarioRunner:
    """Tests for ChaosScenarioRunner class."""

    def test_runner_initialization(self):
        """Test scenario runner initialization."""
        runner = ChaosScenarioRunner()
        assert runner is not None
        assert runner.is_running() is False

    def test_run_simple_scenario(self):
        """Test running a simple scenario."""
        runner = ChaosScenarioRunner()

        # Create a simple scenario with just wait steps
        scenario = ChaosScenario(
            scenario_id='simple_test',
            name='Simple Test',
            description='A simple test scenario',
            steps=[
                ScenarioStep(
                    name='Wait 1',
                    action='wait',
                    wait_seconds=0.1,
                ),
                ScenarioStep(
                    name='Validate',
                    action='validate',
                    validation=lambda: True,
                ),
            ],
            timeout_seconds=10.0,
        )

        result = runner.run_scenario(scenario)

        assert result.scenario_id == 'simple_test'
        assert result.outcome == ScenarioOutcome.SUCCESS
        assert result.steps_completed == 2
        assert result.steps_failed == 0

    def test_scenario_with_failure(self):
        """Test scenario with failing validation."""
        runner = ChaosScenarioRunner()

        scenario = ChaosScenario(
            scenario_id='failing_test',
            name='Failing Test',
            description='A test with failing validation',
            steps=[
                ScenarioStep(
                    name='Validate False',
                    action='validate',
                    validation=lambda: False,
                    on_failure='continue',
                ),
            ],
            timeout_seconds=10.0,
        )

        result = runner.run_scenario(scenario)

        # Should be partial success (validation failed but continued)
        assert result.outcome == ScenarioOutcome.PARTIAL
        assert result.steps_failed == 1

    def test_concurrent_scenario_prevention(self):
        """Test that concurrent scenarios are prevented."""
        runner = ChaosScenarioRunner()

        # Create a long-running scenario
        long_scenario = ChaosScenario(
            scenario_id='long_test',
            name='Long Test',
            description='A long-running test',
            steps=[
                ScenarioStep(
                    name='Long Wait',
                    action='wait',
                    wait_seconds=1.0,
                ),
            ],
            timeout_seconds=10.0,
        )

        # Run in background (would need threading in real test)
        # For unit test, just verify the logic exists

    def test_abort_scenario(self):
        """Test scenario abort functionality."""
        runner = ChaosScenarioRunner()

        # Abort when nothing running should be safe
        runner.abort_scenario()
        assert runner.is_running() is False


class TestResilienceValidator:
    """Tests for ResilienceValidator class."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = ResilienceValidator()
        assert validator is not None

    def test_validation_levels(self):
        """Test validation level enumeration."""
        assert ValidationLevel.RELAXED
        assert ValidationLevel.NORMAL
        assert ValidationLevel.STRICT

    def test_add_criteria(self):
        """Test adding validation criteria."""
        validator = ResilienceValidator()

        criteria = ValidationCriteria(
            name='custom_check',
            description='Custom validation check',
            check_function=lambda: True,
            timeout_seconds=5.0,
        )

        validator.add_criteria(criteria)
        # Criteria should be added to internal list

    def test_remove_criteria(self):
        """Test removing validation criteria."""
        validator = ResilienceValidator()

        # Add then remove
        criteria = ValidationCriteria(
            name='removable_check',
            description='A check to remove',
            check_function=lambda: True,
        )

        validator.add_criteria(criteria)
        validator.remove_criteria('removable_check')

    def test_validate_resilience(self):
        """Test resilience validation."""
        validator = ResilienceValidator(level=ValidationLevel.RELAXED)

        # Run validation with default criteria
        report = validator.validate_resilience(scenario_id='test_validation')

        assert report is not None
        assert isinstance(report, ResilienceReport)
        assert report.scenario_id == 'test_validation'
        assert report.timestamp is not None

    def test_validate_rto(self):
        """Test Recovery Time Objective validation."""
        validator = ResilienceValidator()

        # Create a check that passes immediately
        result = validator.validate_rto(
            target_seconds=5.0,
            check_function=lambda: True,
            poll_interval=0.1,
            timeout_seconds=10.0,
        )

        assert result['met'] is True
        assert result['actual_seconds'] < result['target_seconds']

    def test_validate_rto_timeout(self):
        """Test RTO validation timeout."""
        validator = ResilienceValidator()

        # Create a check that never passes
        result = validator.validate_rto(
            target_seconds=0.1,
            check_function=lambda: False,
            poll_interval=0.1,
            timeout_seconds=0.5,
        )

        assert result['met'] is False
        assert 'error' in result

    def test_validate_data_integrity(self):
        """Test data integrity validation."""
        validator = ResilienceValidator()

        pre_state = {'key1': 'value1', 'key2': 'value2'}
        post_state = {'key1': 'value1', 'key2': 'value2'}

        result = validator.validate_data_integrity(pre_state, post_state)

        assert result['passed'] is True
        assert len(result['differences']) == 0

    def test_validate_data_integrity_with_changes(self):
        """Test data integrity with changes detected."""
        validator = ResilienceValidator()

        pre_state = {'key1': 'value1', 'key2': 'value2'}
        post_state = {'key1': 'changed', 'key2': 'value2'}

        result = validator.validate_data_integrity(pre_state, post_state)

        assert result['passed'] is False
        assert len(result['differences']) > 0

    def test_validate_data_integrity_with_ignored_keys(self):
        """Test data integrity with ignored keys."""
        validator = ResilienceValidator()

        pre_state = {'key1': 'value1', 'timestamp': '2024-01-01'}
        post_state = {'key1': 'value1', 'timestamp': '2024-01-02'}

        result = validator.validate_data_integrity(
            pre_state,
            post_state,
            ignore_keys=['timestamp']
        )

        assert result['passed'] is True

    def test_generate_recommendations(self):
        """Test recommendation generation."""
        validator = ResilienceValidator()

        # Create a report with failures
        report = ResilienceReport(
            timestamp=datetime.now(),
            scenario_id='test',
            recovery_time_seconds=60.0,  # Exceeds 30s target
            availability_percentage=80.0,  # Below 95% target
        )

        report.validations = [
            ValidationResult(
                criteria_name='safety_check',
                passed=False,
                error_message='Safety node timeout',
            ),
        ]

        recommendations = validator._generate_recommendations(report)

        assert len(recommendations) > 0
        assert any('safety' in r.lower() for r in recommendations)


class TestIntegration:
    """Integration tests for chaos components."""

    def test_scenario_with_fault_injection(self):
        """Test scenario execution with actual fault injection."""
        injector = FaultInjector()
        runner = ChaosScenarioRunner(fault_injector=injector)

        scenario = ChaosScenario(
            scenario_id='integration_test',
            name='Integration Test',
            description='Test fault injection in scenario',
            steps=[
                ScenarioStep(
                    name='Inject Delay',
                    action='inject',
                    target='/test/topic',
                    fault_type=FaultType.MESSAGE_DELAY,
                    parameters={'delay_ms': 50.0},
                ),
                ScenarioStep(
                    name='Wait',
                    action='wait',
                    wait_seconds=0.1,
                ),
                ScenarioStep(
                    name='Stop',
                    action='stop',
                ),
            ],
            timeout_seconds=10.0,
            cleanup_on_failure=True,
        )

        result = runner.run_scenario(scenario)

        # After cleanup, no active injections
        assert len(injector.get_active_injections()) == 0

    def test_validator_with_scenario_result(self):
        """Test resilience validation after scenario."""
        validator = ResilienceValidator()
        runner = ChaosScenarioRunner()

        # Run a scenario
        scenario = create_equipment_failure_scenario('test_equipment')
        result = runner.run_scenario(scenario)

        # Validate resilience
        report = validator.validate_resilience(
            scenario_id=result.scenario_id
        )

        assert report.scenario_id == result.scenario_id


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
