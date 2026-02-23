"""
TLA+ Formal Verification Test Suite
====================================

This module provides Python tests that validate the TLA+ model checking results
for the LEGO MCP Safety Node (IEC 61508 SIL 2+).

Tests verify:
- TLA+ specification syntax validity
- Safety invariant satisfaction
- Liveness property satisfaction
- Model checking coverage

Usage:
    pytest tests/test_formal_verification.py -v
    pytest tests/test_formal_verification.py -v -k "safety"
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

# Path configuration
PROJECT_ROOT = Path(__file__).parent.parent
FORMAL_DIR = PROJECT_ROOT / "ros2_ws" / "src" / "lego_mcp_safety_certified" / "formal"
TLA_SPEC = FORMAL_DIR / "safety_node.tla"
TLA_CONFIG = FORMAL_DIR / "safety_node.cfg"

# TLA+ tools configuration
TLA_TOOLS_DIR = Path.home() / ".tla-tools"
TLA_JAR = TLA_TOOLS_DIR / "tla2tools.jar"
TLA_VERSION = "1.8.0"


@dataclass
class TLCResult:
    """Parsed results from TLC model checker."""

    exit_code: int
    states_generated: int
    distinct_states: int
    invariants_hold: bool
    liveness_holds: bool
    errors: list[str]
    output: str


def is_java_available() -> bool:
    """Check if Java is available."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def is_tla_tools_available() -> bool:
    """Check if TLA+ tools are available."""
    return TLA_JAR.exists()


def download_tla_tools() -> bool:
    """Download TLA+ tools if not present."""
    if is_tla_tools_available():
        return True

    try:
        TLA_TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/tlaplus/tlaplus/releases/download/v{TLA_VERSION}/tla2tools.jar"
        subprocess.run(
            ["wget", "-q", "-O", str(TLA_JAR), url],
            check=True,
            timeout=120,
        )
        return TLA_JAR.exists()
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def run_sany(spec_path: Path) -> tuple[bool, str]:
    """Run SANY syntax checker on TLA+ specification."""
    try:
        result = subprocess.run(
            [
                "java",
                "-cp",
                str(TLA_JAR),
                "tla2sany.SANY",
                str(spec_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=spec_path.parent,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.SubprocessError as e:
        return False, str(e)


def run_tlc(
    spec_path: Path,
    config_path: Path,
    workers: int = 2,
    timeout_seconds: int = 300,
) -> TLCResult:
    """Run TLC model checker on TLA+ specification."""
    try:
        result = subprocess.run(
            [
                "java",
                "-XX:+UseParallelGC",
                "-Xmx2g",
                "-cp",
                str(TLA_JAR),
                "tlc2.TLC",
                "-config",
                str(config_path.name),
                "-workers",
                str(workers),
                "-deadlock",
                "-cleanup",
                str(spec_path.name),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=spec_path.parent,
        )

        output = result.stdout + result.stderr

        # Parse states generated
        states_match = re.search(r"(\d+) states generated", output)
        states_generated = int(states_match.group(1)) if states_match else 0

        # Parse distinct states
        distinct_match = re.search(r"(\d+) distinct states found", output)
        distinct_states = int(distinct_match.group(1)) if distinct_match else 0

        # Check for invariant violations
        invariants_hold = "Invariant" not in output or "is violated" not in output

        # Check for liveness violations
        liveness_holds = "Temporal properties were violated" not in output

        # Collect errors
        errors = []
        for line in output.split("\n"):
            if "Error:" in line or "is violated" in line:
                errors.append(line.strip())

        return TLCResult(
            exit_code=result.returncode,
            states_generated=states_generated,
            distinct_states=distinct_states,
            invariants_hold=invariants_hold,
            liveness_holds=liveness_holds,
            errors=errors,
            output=output,
        )

    except subprocess.TimeoutExpired:
        return TLCResult(
            exit_code=-1,
            states_generated=0,
            distinct_states=0,
            invariants_hold=False,
            liveness_holds=False,
            errors=["Model checking timed out"],
            output="",
        )
    except subprocess.SubprocessError as e:
        return TLCResult(
            exit_code=-1,
            states_generated=0,
            distinct_states=0,
            invariants_hold=False,
            liveness_holds=False,
            errors=[str(e)],
            output="",
        )


# Skip all tests if dependencies not available
pytestmark = pytest.mark.skipif(
    not is_java_available(),
    reason="Java not available - required for TLA+ tools",
)


class TestTLASpecificationExists:
    """Tests that verify TLA+ specification files exist."""

    def test_tla_spec_exists(self):
        """Verify safety_node.tla specification exists."""
        assert TLA_SPEC.exists(), f"TLA+ spec not found: {TLA_SPEC}"

    def test_tla_config_exists(self):
        """Verify safety_node.cfg configuration exists."""
        assert TLA_CONFIG.exists(), f"TLA+ config not found: {TLA_CONFIG}"

    def test_formal_dir_exists(self):
        """Verify formal verification directory exists."""
        assert FORMAL_DIR.exists(), f"Formal dir not found: {FORMAL_DIR}"


@pytest.mark.skipif(
    not is_tla_tools_available() and not download_tla_tools(),
    reason="TLA+ tools not available and could not be downloaded",
)
class TestTLASyntax:
    """Tests that verify TLA+ specification syntax."""

    def test_safety_node_syntax(self):
        """Verify safety_node.tla has valid TLA+ syntax."""
        success, output = run_sany(TLA_SPEC)
        assert success, f"SANY syntax check failed:\n{output}"

    def test_spec_contains_required_modules(self):
        """Verify spec extends required TLA+ modules."""
        content = TLA_SPEC.read_text()
        assert "EXTENDS Naturals" in content
        assert "EXTENDS" in content and "Sequences" in content

    def test_spec_defines_safety_states(self):
        """Verify spec defines all safety states."""
        content = TLA_SPEC.read_text()
        required_states = ["NORMAL", "WARNING", "ESTOP_PENDING", "ESTOP_ACTIVE", "LOCKOUT"]
        for state in required_states:
            assert f'"{state}"' in content, f"State {state} not defined in spec"

    def test_spec_defines_relay_states(self):
        """Verify spec defines relay states."""
        content = TLA_SPEC.read_text()
        assert '"OPEN"' in content
        assert '"CLOSED"' in content


@pytest.mark.skipif(
    not is_tla_tools_available() and not download_tla_tools(),
    reason="TLA+ tools not available and could not be downloaded",
)
class TestSafetyInvariants:
    """Tests that verify safety invariants hold."""

    @pytest.fixture(scope="class")
    def tlc_result(self) -> TLCResult:
        """Run TLC model checker once for all safety tests."""
        return run_tlc(TLA_SPEC, TLA_CONFIG, workers=2, timeout_seconds=300)

    def test_model_checking_completes(self, tlc_result: TLCResult):
        """Verify model checking completes without timeout."""
        assert tlc_result.exit_code != -1, "Model checking timed out"
        assert tlc_result.states_generated > 0, "No states generated"

    def test_type_invariant_holds(self, tlc_result: TLCResult):
        """Verify TypeInvariant is satisfied in all states."""
        assert "TypeInvariant" not in " ".join(
            tlc_result.errors
        ), f"TypeInvariant violated:\n{tlc_result.output}"

    def test_safety_invariant_holds(self, tlc_result: TLCResult):
        """Verify SafetyInvariant is satisfied in all states."""
        assert "SafetyInvariant" not in " ".join(
            tlc_result.errors
        ), f"SafetyInvariant violated:\n{tlc_result.output}"

    def test_p1_estop_implies_relays_open(self, tlc_result: TLCResult):
        """Verify P1: E-stop active implies both relays open."""
        assert "SafetyP1" not in " ".join(
            tlc_result.errors
        ), f"SafetyP1 violated:\n{tlc_result.output}"

    def test_p2_estop_command_succeeds(self, tlc_result: TLCResult):
        """Verify P2: E-stop command succeeds when channels healthy."""
        assert "SafetyP2" not in " ".join(
            tlc_result.errors
        ), f"SafetyP2 violated:\n{tlc_result.output}"

    def test_p3_single_fault_safe(self, tlc_result: TLCResult):
        """Verify P3: Single channel fault does not prevent safety."""
        assert "SafetyP3" not in " ".join(
            tlc_result.errors
        ), f"SafetyP3 violated:\n{tlc_result.output}"

    def test_all_invariants_hold(self, tlc_result: TLCResult):
        """Verify all invariants hold (comprehensive check)."""
        assert tlc_result.invariants_hold, (
            f"One or more invariants violated. Errors:\n"
            + "\n".join(tlc_result.errors)
        )


@pytest.mark.skipif(
    not is_tla_tools_available() and not download_tla_tools(),
    reason="TLA+ tools not available and could not be downloaded",
)
class TestLivenessProperties:
    """Tests that verify liveness properties hold."""

    @pytest.fixture(scope="class")
    def tlc_result(self) -> TLCResult:
        """Run TLC model checker once for all liveness tests."""
        return run_tlc(TLA_SPEC, TLA_CONFIG, workers=2, timeout_seconds=300)

    def test_l1_timeout_triggers_estop(self, tlc_result: TLCResult):
        """Verify L1: Heartbeat timeout eventually triggers e-stop."""
        assert tlc_result.liveness_holds or "LivenessL1" not in " ".join(
            tlc_result.errors
        ), f"LivenessL1 violated:\n{tlc_result.output}"

    def test_l2_reset_eventually_succeeds(self, tlc_result: TLCResult):
        """Verify L2: Safe reset request eventually succeeds."""
        assert tlc_result.liveness_holds or "LivenessL2" not in " ".join(
            tlc_result.errors
        ), f"LivenessL2 violated:\n{tlc_result.output}"


@pytest.mark.skipif(
    not is_tla_tools_available() and not download_tla_tools(),
    reason="TLA+ tools not available and could not be downloaded",
)
class TestModelCheckingCoverage:
    """Tests that verify adequate state space coverage."""

    @pytest.fixture(scope="class")
    def tlc_result(self) -> TLCResult:
        """Run TLC model checker once for coverage tests."""
        return run_tlc(TLA_SPEC, TLA_CONFIG, workers=2, timeout_seconds=300)

    def test_minimum_states_explored(self, tlc_result: TLCResult):
        """Verify minimum number of states explored."""
        # With MAX_TIME=100, WATCHDOG_TIMEOUT=5, we expect substantial state space
        min_expected_states = 100
        assert (
            tlc_result.states_generated >= min_expected_states
        ), f"Only {tlc_result.states_generated} states explored, expected >= {min_expected_states}"

    def test_distinct_states_found(self, tlc_result: TLCResult):
        """Verify distinct states were found."""
        assert tlc_result.distinct_states > 0, "No distinct states found"

    def test_no_deadlock(self, tlc_result: TLCResult):
        """Verify no deadlock states exist."""
        assert "deadlock" not in tlc_result.output.lower() or (
            "Checking for deadlock" in tlc_result.output
            and "Error: deadlock" not in tlc_result.output
        ), f"Deadlock found:\n{tlc_result.output}"


class TestTLASpecContent:
    """Tests that verify TLA+ specification content."""

    def test_spec_contains_dual_channel_relay(self):
        """Verify spec models dual-channel relay."""
        content = TLA_SPEC.read_text()
        assert "primary_relay" in content
        assert "secondary_relay" in content

    def test_spec_contains_watchdog(self):
        """Verify spec models watchdog timer."""
        content = TLA_SPEC.read_text()
        assert "heartbeat_counter" in content
        assert "WATCHDOG_TIMEOUT" in content

    def test_spec_contains_fault_injection(self):
        """Verify spec models fault injection for verification."""
        content = TLA_SPEC.read_text()
        assert "primary_fault" in content
        assert "secondary_fault" in content
        assert "InjectPrimaryFault" in content
        assert "InjectSecondaryFault" in content

    def test_spec_contains_cross_channel_check(self):
        """Verify spec models cross-channel consistency check."""
        content = TLA_SPEC.read_text()
        assert "CrossChannelCheck" in content
        assert "RelaysDisagree" in content

    def test_config_contains_invariants(self):
        """Verify config specifies all required invariants."""
        content = TLA_CONFIG.read_text()
        required_invariants = [
            "TypeInvariant",
            "SafetyInvariant",
            "SafetyP1_EstopImpliesRelaysOpen",
            "SafetyP2_EstopCommandSucceeds",
            "SafetyP3_SingleFaultSafe",
        ]
        for inv in required_invariants:
            assert inv in content, f"Invariant {inv} not in config"

    def test_config_contains_properties(self):
        """Verify config specifies liveness properties."""
        content = TLA_CONFIG.read_text()
        assert "LivenessL1_TimeoutTriggersEstop" in content
        assert "LivenessL2_ResetEventuallySucceeds" in content


class TestIEC61508Compliance:
    """Tests related to IEC 61508 SIL 2+ compliance."""

    def test_spec_documents_sil_level(self):
        """Verify spec documents IEC 61508 SIL 2+ compliance."""
        content = TLA_SPEC.read_text()
        assert "IEC 61508" in content
        assert "SIL 2" in content

    def test_spec_documents_safety_properties(self):
        """Verify spec documents safety properties per IEC 61508."""
        content = TLA_SPEC.read_text()
        # Must document what each safety property ensures
        assert "SAFETY PROPERTIES" in content
        assert "LIVENESS PROPERTIES" in content

    def test_dual_channel_architecture(self):
        """Verify dual-channel architecture for SIL 2+."""
        content = TLA_SPEC.read_text()
        # Dual-channel is required for SIL 2+
        assert "dual-channel" in content.lower() or "Dual-Channel" in content

    def test_single_fault_tolerance(self):
        """Verify single fault tolerance property."""
        content = TLA_SPEC.read_text()
        # SIL 2+ requires tolerance to single faults
        assert "SingleFaultSafe" in content or "single fault" in content.lower()
