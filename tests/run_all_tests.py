#!/usr/bin/env python3
"""
Comprehensive Test Runner for LEGO MCP Manufacturing System

Runs all tests without requiring pytest installation.
Provides detailed output and summary statistics.

Usage:
    python tests/run_all_tests.py
"""

import sys
import os
import time
import traceback
from typing import List, Tuple, Callable, Any
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    duration_ms: float
    error: str = ""


@dataclass
class TestSuiteResult:
    """Result of a test suite."""
    name: str
    results: List[TestResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.suites: List[TestSuiteResult] = []

    def run_test(self, name: str, test_fn: Callable) -> TestResult:
        """Run a single test function."""
        start = time.perf_counter()
        try:
            test_fn()
            duration = (time.perf_counter() - start) * 1000
            return TestResult(name=name, passed=True, duration_ms=duration)
        except AssertionError as e:
            duration = (time.perf_counter() - start) * 1000
            return TestResult(name=name, passed=False, duration_ms=duration, error=str(e))
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return TestResult(name=name, passed=False, duration_ms=duration, error=f"{type(e).__name__}: {e}")

    def run_suite(self, name: str, tests: List[Tuple[str, Callable]]) -> TestSuiteResult:
        """Run a test suite."""
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)

        suite = TestSuiteResult(name=name)

        for test_name, test_fn in tests:
            result = self.run_test(test_name, test_fn)
            suite.results.append(result)

            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"  {status}: {test_name} ({result.duration_ms:.1f}ms)")
            if not result.passed:
                print(f"         Error: {result.error[:100]}")

        self.suites.append(suite)
        return suite

    def print_summary(self):
        """Print overall summary."""
        total_passed = sum(s.passed for s in self.suites)
        total_failed = sum(s.failed for s in self.suites)
        total_tests = sum(s.total for s in self.suites)

        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        for suite in self.suites:
            status = "✓" if suite.failed == 0 else "✗"
            print(f"  {status} {suite.name}: {suite.passed}/{suite.total} passed")

        print("-"*60)
        print(f"  TOTAL: {total_passed}/{total_tests} passed, {total_failed} failed")
        print("="*60)

        return total_failed == 0


def test_runtime_monitors():
    """Tests for runtime safety monitors."""
    from dashboard.services.verification.monitors import (
        BaseMonitor, MonitorStatus, MonitorSeverity, MonitorResult, MonitorReport
    )
    from dashboard.services.verification.monitors.safety_node_monitor import (
        SafetyNodeMonitor, SAFETY_STATES, RELAY_STATES
    )

    tests = []

    # Test fixtures
    normal_state = {
        'safety_state': 'NORMAL',
        'primary_relay': 'CLOSED',
        'secondary_relay': 'CLOSED',
        'heartbeat_counter': 0,
        'heartbeat_received': True,
        'hw_estop_pressed': False,
        'primary_fault': False,
        'secondary_fault': False,
        'time': 0,
    }

    estop_state = {
        'safety_state': 'ESTOP_ACTIVE',
        'primary_relay': 'OPEN',
        'secondary_relay': 'OPEN',
        'heartbeat_counter': 5,
        'heartbeat_received': False,
        'hw_estop_pressed': True,
        'primary_fault': False,
        'secondary_fault': False,
        'time': 100,
    }

    def test_monitor_init():
        monitor = SafetyNodeMonitor()
        assert monitor.name == "SafetyNodeMonitor"
        assert len(monitor._invariants) >= 2
        assert len(monitor._safety_properties) >= 3
    tests.append(("Monitor initialization", test_monitor_init))

    def test_normal_state_passes():
        monitor = SafetyNodeMonitor()
        report = monitor.check_all(normal_state)
        assert report.all_passed, f"Normal state should pass all checks"
    tests.append(("Normal state passes all checks", test_normal_state_passes))

    def test_type_invariant():
        monitor = SafetyNodeMonitor()
        assert monitor.check_type_invariant(normal_state)
        invalid = normal_state.copy()
        invalid['safety_state'] = 'INVALID'
        assert not monitor.check_type_invariant(invalid)
    tests.append(("Type invariant validation", test_type_invariant))

    def test_estop_state_passes():
        monitor = SafetyNodeMonitor()
        report = monitor.check_all(estop_state)
        assert report.all_passed
    tests.append(("Valid E-stop state passes", test_estop_state_passes))

    def test_violation_detection():
        monitor = SafetyNodeMonitor()
        bad_state = estop_state.copy()
        bad_state['primary_relay'] = 'CLOSED'
        bad_state['secondary_relay'] = 'CLOSED'
        report = monitor.check_all(bad_state)
        assert not report.all_passed
        assert report.has_safety_critical_failure
    tests.append(("Violation detection", test_violation_detection))

    def test_p3_single_fault_safe():
        monitor = SafetyNodeMonitor()
        # Secondary closed but primary open - should pass P3
        state = estop_state.copy()
        state['secondary_relay'] = 'CLOSED'
        assert monitor.check_safetyp3_single_fault_safe(state)
    tests.append(("P3 single fault safe", test_p3_single_fault_safe))

    return tests


def test_hsm_sealer():
    """Tests for HSM-signed audit sealer."""
    from dashboard.services.traceability.hsm_sealer import (
        HSMSealer, AuditSeal, SealType, SealStatus
    )

    tests = []

    def test_sealer_init():
        sealer = HSMSealer(key_manager=None)
        assert sealer is not None
    tests.append(("HSMSealer initialization", test_sealer_init))

    def test_create_seal():
        sealer = HSMSealer(key_manager=None)
        seal = sealer.create_seal("test_hash", 100, SealType.DAILY)
        assert seal.chain_hash == "test_hash"
        assert seal.event_count == 100
        assert seal.seal_type == SealType.DAILY
        assert seal.signature is not None
    tests.append(("Create seal", test_create_seal))

    def test_verify_seal():
        sealer = HSMSealer(key_manager=None)
        seal = sealer.create_seal("hash123", 50)
        result = sealer.verify_seal(seal)
        assert result.is_valid
        assert result.status == SealStatus.VALID
    tests.append(("Verify seal", test_verify_seal))

    def test_tamper_detection():
        sealer = HSMSealer(key_manager=None)
        seal = sealer.create_seal("original", 100)
        seal.chain_hash = "tampered"
        result = sealer.verify_seal(seal)
        assert not result.is_valid
        assert result.status == SealStatus.TAMPERED
    tests.append(("Tamper detection", test_tamper_detection))

    def test_seal_chaining():
        sealer = HSMSealer(key_manager=None)
        seal1 = sealer.create_seal("h1", 100)
        seal2 = sealer.create_seal("h2", 200)
        assert seal2.previous_seal_id == seal1.seal_id
    tests.append(("Seal chaining", test_seal_chaining))

    return tests


def test_traced_audit():
    """Tests for traced audit events."""
    from dashboard.services.traceability.traced_audit import (
        TracedDigitalThread, TRACE_ID_KEY, SPAN_ID_KEY, TRACEPARENT_KEY
    )

    tests = []

    def test_constants_defined():
        assert TRACE_ID_KEY == "trace_id"
        assert SPAN_ID_KEY == "span_id"
        assert TRACEPARENT_KEY == "traceparent"
    tests.append(("Trace constants defined", test_constants_defined))

    def test_class_available():
        assert TracedDigitalThread is not None
    tests.append(("TracedDigitalThread available", test_class_available))

    return tests


def test_ai_guardrails():
    """Tests for AI guardrails test generators."""
    from dashboard.services.ai.guardrails.test_generators import (
        ManufacturingCommandGenerator,
        InjectionAttemptGenerator,
        PiiGenerator,
        ConfidenceScoreGenerator,
    )

    tests = []

    def test_command_generator():
        gen = ManufacturingCommandGenerator()
        safe = gen.generate_safe_command()
        blocked = gen.generate_blocked_command()
        assert safe.text is not None
        assert blocked.text is not None
    tests.append(("ManufacturingCommandGenerator", test_command_generator))

    def test_injection_generator():
        gen = InjectionAttemptGenerator()
        injection = gen.generate_injection()
        assert injection.text is not None and len(injection.text) > 0
    tests.append(("InjectionAttemptGenerator", test_injection_generator))

    def test_pii_generator():
        gen = PiiGenerator()
        email = gen.generate_email()
        phone = gen.generate_phone()
        assert "@" in email
        assert len(phone) > 0
    tests.append(("PiiGenerator", test_pii_generator))

    def test_confidence_generator():
        gen = ConfidenceScoreGenerator()
        high = gen.generate_high_confidence()
        low = gen.generate_low_confidence()
        assert high >= 0.9
        assert low <= 0.5
    tests.append(("ConfidenceScoreGenerator", test_confidence_generator))

    return tests


def test_tla_parser():
    """Tests for TLA+ parser."""
    from dashboard.services.verification.runtime_monitor_generator import (
        TLAParser, TLASpec, RuntimeMonitorGenerator
    )

    tests = []

    def test_parser_type_sets():
        parser = TLAParser()
        content = 'SafetyStates == {"NORMAL", "ERROR"}'
        spec = parser.parse(content)
        assert "SafetyStates" in spec.type_sets
        assert "NORMAL" in spec.type_sets["SafetyStates"]
    tests.append(("TLA+ parser type sets", test_parser_type_sets))

    def test_generator_code():
        generator = RuntimeMonitorGenerator()
        spec = TLASpec(module_name="TestModule")
        spec.type_sets["States"] = {"A", "B"}
        code = generator.generate_monitor_code(spec)
        assert "class TestModuleMonitor" in code
    tests.append(("RuntimeMonitorGenerator", test_generator_code))

    return tests


def test_formal_verification():
    """Tests for formal verification infrastructure."""
    import os

    tests = []

    def test_ci_workflow_exists():
        assert os.path.exists(".github/workflows/formal-verification.yml")
    tests.append(("CI workflow exists", test_ci_workflow_exists))

    def test_run_script_exists():
        assert os.path.exists("ros2_ws/src/lego_mcp_safety_certified/formal/run_tlc.sh")
    tests.append(("TLC run script exists", test_run_script_exists))

    def test_tla_spec_exists():
        assert os.path.exists("ros2_ws/src/lego_mcp_safety_certified/formal/safety_node.tla")
    tests.append(("TLA+ spec exists", test_tla_spec_exists))

    return tests


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("LEGO MCP Manufacturing System - Comprehensive Test Suite")
    print("="*60)

    runner = TestRunner()

    # Run all test suites
    runner.run_suite("Runtime Safety Monitors", test_runtime_monitors())
    runner.run_suite("HSM-Signed Audit Sealer", test_hsm_sealer())
    runner.run_suite("Traced Audit Events", test_traced_audit())
    runner.run_suite("AI Guardrails Generators", test_ai_guardrails())
    runner.run_suite("TLA+ Parser & Generator", test_tla_parser())
    runner.run_suite("Formal Verification Infrastructure", test_formal_verification())

    # Print summary
    all_passed = runner.print_summary()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
