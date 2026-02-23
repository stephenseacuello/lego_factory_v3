"""
Tests for Runtime Safety Monitors

Tests verify:
- Monitor initialization and discovery
- Type invariant checking
- Safety property validation
- Fault injection detection
- Integration with model checker
- Performance requirements
"""

import pytest
from typing import Dict, Any
import copy

# Import monitor framework
from dashboard.services.verification.monitors import (
    BaseMonitor,
    MonitorStatus,
    MonitorSeverity,
    MonitorResult,
    MonitorReport,
    invariant,
    safety_property,
)

# Import SafetyNode monitor
from dashboard.services.verification.monitors.safety_node_monitor import (
    SafetyNodeMonitor,
    SAFETY_STATES,
    RELAY_STATES,
    create_safety_node_monitor,
)

# Import generator
from dashboard.services.verification.runtime_monitor_generator import (
    RuntimeMonitorGenerator,
    TLAParser,
    TLAToPythonTranslator,
    TLASpec,
    TLAProperty,
    TLAExpressionType,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def normal_state() -> Dict[str, Any]:
    """Create a normal operating state."""
    return {
        "safety_state": "NORMAL",
        "primary_relay": "CLOSED",
        "secondary_relay": "CLOSED",
        "heartbeat_counter": 0,
        "heartbeat_received": True,
        "hw_estop_pressed": False,
        "primary_fault": False,
        "secondary_fault": False,
        "time": 0,
    }


@pytest.fixture
def estop_state() -> Dict[str, Any]:
    """Create an E-stop active state (correct)."""
    return {
        "safety_state": "ESTOP_ACTIVE",
        "primary_relay": "OPEN",
        "secondary_relay": "OPEN",
        "heartbeat_counter": 5,
        "heartbeat_received": False,
        "hw_estop_pressed": True,
        "primary_fault": False,
        "secondary_fault": False,
        "time": 100,
    }


@pytest.fixture
def safety_monitor() -> SafetyNodeMonitor:
    """Create a SafetyNodeMonitor instance."""
    return SafetyNodeMonitor()


@pytest.fixture
def tla_parser() -> TLAParser:
    """Create a TLA+ parser."""
    return TLAParser()


@pytest.fixture
def monitor_generator() -> RuntimeMonitorGenerator:
    """Create a RuntimeMonitorGenerator."""
    return RuntimeMonitorGenerator()


# ============================================================================
# Test Monitor Framework
# ============================================================================

class TestMonitorFramework:
    """Tests for the monitor framework base classes."""

    def test_monitor_result_creation(self):
        """Test MonitorResult dataclass."""
        result = MonitorResult(
            monitor_name="TestMonitor",
            property_name="TestProperty",
            status=MonitorStatus.SATISFIED,
        )

        assert result.monitor_name == "TestMonitor"
        assert result.status == MonitorStatus.SATISFIED

    def test_monitor_result_to_dict(self):
        """Test MonitorResult serialization."""
        result = MonitorResult(
            monitor_name="Test",
            property_name="Prop",
            status=MonitorStatus.VIOLATED,
            severity=MonitorSeverity.SAFETY_CRITICAL,
            message="Test failure",
        )

        d = result.to_dict()
        assert d["status"] == "violated"
        assert d["severity"] == "SAFETY_CRITICAL"
        assert d["message"] == "Test failure"

    def test_monitor_report_aggregation(self):
        """Test MonitorReport aggregation."""
        report = MonitorReport()
        report.checks_total = 5
        report.checks_passed = 4
        report.checks_failed = 1

        assert not report.all_passed
        assert report.checks_failed == 1

    def test_monitor_report_safety_critical(self):
        """Test safety critical failure detection."""
        report = MonitorReport()
        report.results.append(MonitorResult(
            monitor_name="Test",
            property_name="CriticalProp",
            status=MonitorStatus.VIOLATED,
            severity=MonitorSeverity.SAFETY_CRITICAL,
        ))

        assert report.has_safety_critical_failure

    def test_invariant_decorator(self):
        """Test @invariant decorator."""

        class TestMonitor(BaseMonitor):
            @invariant("TestInvariant", severity=MonitorSeverity.WARNING)
            def check_test(self, state: Dict) -> bool:
                return state.get("value", 0) > 0

        monitor = TestMonitor("Test")
        assert "TestInvariant" in monitor._invariants

    def test_safety_property_decorator(self):
        """Test @safety_property decorator."""

        class TestMonitor(BaseMonitor):
            @safety_property("TestSafety", sil_level=2)
            def check_safety(self, state: Dict) -> bool:
                return True

        monitor = TestMonitor("Test")
        assert "TestSafety" in monitor._safety_properties


# ============================================================================
# Test SafetyNodeMonitor
# ============================================================================

class TestSafetyNodeMonitorInit:
    """Tests for SafetyNodeMonitor initialization."""

    def test_initialization(self, safety_monitor):
        """Test monitor initializes correctly."""
        assert safety_monitor.name == "SafetyNodeMonitor"
        assert len(safety_monitor._invariants) > 0
        assert len(safety_monitor._safety_properties) > 0

    def test_discovered_invariants(self, safety_monitor):
        """Test that invariants are discovered."""
        assert "TypeInvariant" in safety_monitor._invariants
        assert "SafetyInvariant" in safety_monitor._invariants

    def test_discovered_safety_properties(self, safety_monitor):
        """Test that safety properties are discovered."""
        props = safety_monitor._safety_properties
        assert "SafetyP1_EstopImpliesRelaysOpen" in props
        assert "SafetyP2_EstopCommandSucceeds" in props
        assert "SafetyP3_SingleFaultSafe" in props

    def test_factory_function(self):
        """Test create_safety_node_monitor factory."""
        monitor = create_safety_node_monitor()
        assert isinstance(monitor, SafetyNodeMonitor)


class TestTypeInvariant:
    """Tests for TypeInvariant checking."""

    def test_valid_normal_state(self, safety_monitor, normal_state):
        """Test TypeInvariant passes for valid state."""
        result = safety_monitor.check_type_invariant(normal_state)
        assert result is True

    def test_valid_estop_state(self, safety_monitor, estop_state):
        """Test TypeInvariant passes for E-stop state."""
        result = safety_monitor.check_type_invariant(estop_state)
        assert result is True

    def test_invalid_safety_state(self, safety_monitor, normal_state):
        """Test TypeInvariant fails for invalid safety_state."""
        normal_state["safety_state"] = "INVALID_STATE"
        result = safety_monitor.check_type_invariant(normal_state)
        assert result is False

    def test_invalid_relay_state(self, safety_monitor, normal_state):
        """Test TypeInvariant fails for invalid relay state."""
        normal_state["primary_relay"] = "STUCK"
        result = safety_monitor.check_type_invariant(normal_state)
        assert result is False

    def test_invalid_heartbeat_counter(self, safety_monitor, normal_state):
        """Test TypeInvariant fails for out-of-range counter."""
        normal_state["heartbeat_counter"] = -1
        result = safety_monitor.check_type_invariant(normal_state)
        assert result is False

    def test_missing_field_fails(self, safety_monitor):
        """Test TypeInvariant fails for missing fields."""
        incomplete_state = {"safety_state": "NORMAL"}
        result = safety_monitor.check_type_invariant(incomplete_state)
        assert result is False


class TestSafetyP1EstopImpliesRelaysOpen:
    """Tests for SafetyP1: E-stop implies relays open."""

    def test_normal_state_passes(self, safety_monitor, normal_state):
        """P1 trivially passes when not in E-stop."""
        result = safety_monitor.check_safetyp1_estop_implies_relays_open(normal_state)
        assert result is True

    def test_correct_estop_passes(self, safety_monitor, estop_state):
        """P1 passes when E-stop active and both relays open."""
        result = safety_monitor.check_safetyp1_estop_implies_relays_open(estop_state)
        assert result is True

    def test_estop_with_closed_relay_fails(self, safety_monitor, estop_state):
        """P1 fails when E-stop but relay still closed."""
        estop_state["primary_relay"] = "CLOSED"
        result = safety_monitor.check_safetyp1_estop_implies_relays_open(estop_state)
        assert result is False

    def test_estop_with_fault_passes(self, safety_monitor, estop_state):
        """P1 passes with fault (can't guarantee relay state)."""
        estop_state["primary_relay"] = "CLOSED"
        estop_state["primary_fault"] = True
        result = safety_monitor.check_safetyp1_estop_implies_relays_open(estop_state)
        assert result is True


class TestSafetyP2EstopCommandSucceeds:
    """Tests for SafetyP2: E-stop command succeeds."""

    def test_normal_state_passes(self, safety_monitor, normal_state):
        """P2 trivially passes when not in E-stop."""
        result = safety_monitor.check_safetyp2_estop_command_succeeds(normal_state)
        assert result is True

    def test_estop_primary_open_passes(self, safety_monitor, estop_state):
        """P2 passes when primary relay opens on E-stop."""
        result = safety_monitor.check_safetyp2_estop_command_succeeds(estop_state)
        assert result is True

    def test_estop_primary_stuck_fails(self, safety_monitor, estop_state):
        """P2 fails when primary stays closed without fault."""
        estop_state["primary_relay"] = "CLOSED"
        result = safety_monitor.check_safetyp2_estop_command_succeeds(estop_state)
        assert result is False

    def test_estop_primary_faulted_passes(self, safety_monitor, estop_state):
        """P2 passes when primary faulted (can't guarantee state)."""
        estop_state["primary_relay"] = "CLOSED"
        estop_state["primary_fault"] = True
        result = safety_monitor.check_safetyp2_estop_command_succeeds(estop_state)
        assert result is True


class TestSafetyP3SingleFaultSafe:
    """Tests for SafetyP3: Single fault doesn't prevent safety."""

    def test_normal_state_passes(self, safety_monitor, normal_state):
        """P3 trivially passes when not in E-stop."""
        result = safety_monitor.check_safetyp3_single_fault_safe(normal_state)
        assert result is True

    def test_both_relays_open_passes(self, safety_monitor, estop_state):
        """P3 passes when both relays open."""
        result = safety_monitor.check_safetyp3_single_fault_safe(estop_state)
        assert result is True

    def test_primary_open_only_passes(self, safety_monitor, estop_state):
        """P3 passes with only primary open."""
        estop_state["secondary_relay"] = "CLOSED"
        result = safety_monitor.check_safetyp3_single_fault_safe(estop_state)
        assert result is True

    def test_secondary_open_only_passes(self, safety_monitor, estop_state):
        """P3 passes with only secondary open."""
        estop_state["primary_relay"] = "CLOSED"
        result = safety_monitor.check_safetyp3_single_fault_safe(estop_state)
        assert result is True

    def test_both_closed_no_faults_fails(self, safety_monitor, estop_state):
        """P3 fails when both closed without faults."""
        estop_state["primary_relay"] = "CLOSED"
        estop_state["secondary_relay"] = "CLOSED"
        result = safety_monitor.check_safetyp3_single_fault_safe(estop_state)
        assert result is False

    def test_both_closed_both_faults_passes(self, safety_monitor, estop_state):
        """P3 passes when both closed but both faulted (expected)."""
        estop_state["primary_relay"] = "CLOSED"
        estop_state["secondary_relay"] = "CLOSED"
        estop_state["primary_fault"] = True
        estop_state["secondary_fault"] = True
        result = safety_monitor.check_safetyp3_single_fault_safe(estop_state)
        assert result is True


class TestCombinedSafetyInvariant:
    """Tests for combined SafetyInvariant."""

    def test_normal_state_passes(self, safety_monitor, normal_state):
        """SafetyInvariant passes for normal operation."""
        result = safety_monitor.check_safety_invariant(normal_state)
        assert result is True

    def test_correct_estop_passes(self, safety_monitor, estop_state):
        """SafetyInvariant passes for correct E-stop."""
        result = safety_monitor.check_safety_invariant(estop_state)
        assert result is True

    def test_violation_detected(self, safety_monitor, estop_state):
        """SafetyInvariant detects violations."""
        # Create a bad state: E-stop but relays closed
        estop_state["primary_relay"] = "CLOSED"
        estop_state["secondary_relay"] = "CLOSED"
        result = safety_monitor.check_safety_invariant(estop_state)
        assert result is False


class TestMonitorCheckAll:
    """Tests for check_all() method."""

    def test_check_all_normal_state(self, safety_monitor, normal_state):
        """check_all passes for normal state."""
        report = safety_monitor.check_all(normal_state)
        assert report.all_passed
        assert report.checks_failed == 0

    def test_check_all_reports_violation(self, safety_monitor, estop_state):
        """check_all reports violations."""
        # Create violation
        estop_state["primary_relay"] = "CLOSED"
        estop_state["secondary_relay"] = "CLOSED"

        report = safety_monitor.check_all(estop_state)
        assert not report.all_passed
        assert report.checks_failed > 0

    def test_check_all_returns_details(self, safety_monitor, normal_state):
        """check_all returns detailed results."""
        report = safety_monitor.check_all(normal_state)

        assert report.checks_total > 0
        assert len(report.results) == report.checks_total

        # All should be satisfied
        for result in report.results:
            assert result.status == MonitorStatus.SATISFIED

    def test_check_all_safety_critical_flag(self, safety_monitor, estop_state):
        """check_all sets safety_critical flag on violations."""
        # Create safety-critical violation
        estop_state["primary_relay"] = "CLOSED"
        estop_state["secondary_relay"] = "CLOSED"

        report = safety_monitor.check_all(estop_state)
        assert report.has_safety_critical_failure


class TestHelperMethods:
    """Tests for helper methods."""

    def test_both_relays_open(self, safety_monitor):
        """Test both_relays_open helper."""
        state = {"primary_relay": "OPEN", "secondary_relay": "OPEN"}
        assert safety_monitor.both_relays_open(state)

        state["primary_relay"] = "CLOSED"
        assert not safety_monitor.both_relays_open(state)

    def test_relays_disagree(self, safety_monitor):
        """Test relays_disagree helper."""
        state = {"primary_relay": "OPEN", "secondary_relay": "CLOSED"}
        assert safety_monitor.relays_disagree(state)

        state["secondary_relay"] = "OPEN"
        assert not safety_monitor.relays_disagree(state)

    def test_watchdog_timeout(self, safety_monitor):
        """Test watchdog_timeout helper."""
        state = {"heartbeat_counter": 5}
        assert not safety_monitor.watchdog_timeout(state)

        state["heartbeat_counter"] = 10
        assert safety_monitor.watchdog_timeout(state)

    def test_estop_active(self, safety_monitor):
        """Test estop_active helper."""
        assert safety_monitor.estop_active({"safety_state": "ESTOP_ACTIVE"})
        assert safety_monitor.estop_active({"safety_state": "LOCKOUT"})
        assert not safety_monitor.estop_active({"safety_state": "NORMAL"})


# ============================================================================
# Test TLA+ Parser
# ============================================================================

class TestTLAParser:
    """Tests for TLA+ parser."""

    def test_parse_type_sets(self, tla_parser):
        """Test parsing type set definitions."""
        content = '''
        SafetyStates == {"NORMAL", "WARNING", "ESTOP_ACTIVE"}
        RelayStates == {"OPEN", "CLOSED"}
        '''
        spec = tla_parser.parse(content)

        assert "SafetyStates" in spec.type_sets
        assert spec.type_sets["SafetyStates"] == {"NORMAL", "WARNING", "ESTOP_ACTIVE"}
        assert spec.type_sets["RelayStates"] == {"OPEN", "CLOSED"}

    def test_parse_module_name(self, tla_parser):
        """Test module name extraction."""
        content = '''
        ---- MODULE TestModule ----
        EXTENDS Naturals
        '''
        spec = tla_parser.parse(content)
        assert spec.module_name == "TestModule"

    def test_parse_constants(self, tla_parser):
        """Test CONSTANTS parsing."""
        content = '''
        CONSTANTS
            MAX_TIME,
            TIMEOUT
        VARIABLES
            x
        '''
        spec = tla_parser.parse(content)
        assert "MAX_TIME" in spec.constants
        assert "TIMEOUT" in spec.constants


# ============================================================================
# Test RuntimeMonitorGenerator
# ============================================================================

class TestRuntimeMonitorGenerator:
    """Tests for RuntimeMonitorGenerator."""

    def test_generate_code_structure(self, monitor_generator):
        """Test generated code has correct structure."""
        spec = TLASpec(module_name="Test")
        spec.type_sets["States"] = {"A", "B"}
        spec.invariants["TestInv"] = TLAProperty(
            name="TestInv",
            expression="x > 0",
            expr_type=TLAExpressionType.INVARIANT,
        )

        code = monitor_generator.generate_monitor_code(spec)

        assert "class TestMonitor" in code
        assert "BaseMonitor" in code
        assert "@invariant" in code or "@safety_property" in code

    def test_translator_basic_operators(self):
        """Test TLA+ to Python translation."""
        spec = TLASpec(module_name="Test")
        spec.variables["x"] = None
        spec.variables["y"] = None

        translator = TLAToPythonTranslator(spec)

        # Test conjunction
        result = translator.translate_expression("x > 0 /\\ y > 0")
        assert "and" in result

        # Test disjunction
        result = translator.translate_expression("x > 0 \\/ y > 0")
        assert "or" in result

        # Test negation
        result = translator.translate_expression("~x")
        assert "not" in result


# ============================================================================
# Test Fault Injection Scenarios
# ============================================================================

class TestFaultInjectionScenarios:
    """Tests that verify monitor detects various fault conditions."""

    def test_detect_stuck_primary_relay(self, safety_monitor):
        """Detect primary relay stuck closed during E-stop."""
        state = {
            "safety_state": "ESTOP_ACTIVE",
            "primary_relay": "CLOSED",  # FAULT: should be open
            "secondary_relay": "OPEN",
            "heartbeat_counter": 0,
            "heartbeat_received": False,
            "hw_estop_pressed": True,
            "primary_fault": False,  # Not reported as fault
            "secondary_fault": False,
            "time": 50,
        }

        report = safety_monitor.check_all(state)
        assert not report.all_passed
        # Should fail P1 (both should be open) but pass P3 (secondary is open)

    def test_detect_stuck_secondary_relay(self, safety_monitor):
        """Detect secondary relay stuck closed during E-stop."""
        state = {
            "safety_state": "ESTOP_ACTIVE",
            "primary_relay": "OPEN",
            "secondary_relay": "CLOSED",  # FAULT: should be open
            "heartbeat_counter": 0,
            "heartbeat_received": False,
            "hw_estop_pressed": True,
            "primary_fault": False,
            "secondary_fault": False,  # Not reported as fault
            "time": 50,
        }

        report = safety_monitor.check_all(state)
        # P1 fails (both should be open), P2 passes, P3 passes
        assert not report.all_passed

    def test_detect_dual_channel_failure(self, safety_monitor):
        """Detect catastrophic dual-channel failure."""
        state = {
            "safety_state": "ESTOP_ACTIVE",
            "primary_relay": "CLOSED",  # Both stuck!
            "secondary_relay": "CLOSED",
            "heartbeat_counter": 0,
            "heartbeat_received": False,
            "hw_estop_pressed": True,
            "primary_fault": False,  # Not detected by hardware
            "secondary_fault": False,
            "time": 50,
        }

        report = safety_monitor.check_all(state)
        assert not report.all_passed
        assert report.has_safety_critical_failure

    def test_relay_disagreement_detected(self, safety_monitor, normal_state):
        """Detect relay state disagreement."""
        normal_state["primary_relay"] = "OPEN"
        normal_state["secondary_relay"] = "CLOSED"

        assert safety_monitor.relays_disagree(normal_state)


# ============================================================================
# Test Performance Requirements
# ============================================================================

class TestPerformanceRequirements:
    """Tests for monitor performance."""

    def test_check_all_performance(self, safety_monitor, normal_state):
        """check_all completes within timing requirements."""
        import time

        start = time.perf_counter()
        for _ in range(1000):
            safety_monitor.check_all(normal_state)
        elapsed = time.perf_counter() - start

        # Should complete 1000 checks in < 1 second
        assert elapsed < 1.0, f"1000 checks took {elapsed:.3f}s (too slow)"

        # Average should be < 1ms per check
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Average check time {avg_ms:.3f}ms (should be < 1ms)"

    def test_single_check_microseconds(self, safety_monitor, normal_state):
        """Individual checks complete in microseconds."""
        report = safety_monitor.check_all(normal_state)

        for result in report.results:
            # Each check should be < 100 microseconds
            assert result.duration_us < 100, f"{result.property_name} took {result.duration_us:.1f}us"


# ============================================================================
# Test Statistics and Reporting
# ============================================================================

class TestStatisticsAndReporting:
    """Tests for monitor statistics."""

    def test_get_statistics(self, safety_monitor):
        """Test statistics collection."""
        stats = safety_monitor.get_statistics()

        assert stats["name"] == "SafetyNodeMonitor"
        assert stats["invariant_count"] >= 2
        assert stats["safety_property_count"] >= 3

    def test_violation_counting(self, safety_monitor, estop_state):
        """Test violation counting."""
        initial_violations = safety_monitor._violation_count

        # Create a violation
        estop_state["primary_relay"] = "CLOSED"
        estop_state["secondary_relay"] = "CLOSED"
        safety_monitor.check_all(estop_state)

        assert safety_monitor._violation_count > initial_violations

    def test_report_serialization(self, safety_monitor, normal_state):
        """Test report JSON serialization."""
        report = safety_monitor.check_all(normal_state)
        d = report.to_dict()

        assert "checks_total" in d
        assert "all_passed" in d
        assert "results" in d
        assert isinstance(d["results"], list)
