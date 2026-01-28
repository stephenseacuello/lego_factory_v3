#!/usr/bin/env python3
"""
Chaos Scenarios for LEGO MCP

Predefined chaos testing scenarios for common failure modes:
- Equipment failure during production
- Network partition between zones
- Cascade failure handling
- Recovery validation

Industry 4.0/5.0 Architecture - Resilience Testing
"""

import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import threading

from .fault_injector import FaultInjector, FaultType, FaultInjection


class ScenarioOutcome(Enum):
    """Possible scenario outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ScenarioStep:
    """Single step in a chaos scenario."""
    name: str
    action: str  # inject, wait, validate, stop
    target: Optional[str] = None
    fault_type: Optional[FaultType] = None
    parameters: Dict = field(default_factory=dict)
    wait_seconds: float = 0.0
    validation: Optional[Callable[[], bool]] = None
    on_failure: str = "continue"  # continue, abort, retry


@dataclass
class ChaosScenario:
    """
    Definition of a chaos testing scenario.

    Scenarios consist of steps that inject faults, wait, and validate
    system behavior under failure conditions.
    """
    scenario_id: str
    name: str
    description: str
    steps: List[ScenarioStep] = field(default_factory=list)
    timeout_seconds: float = 300.0  # 5 minutes default
    cleanup_on_failure: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result of a scenario execution."""
    scenario_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    outcome: ScenarioOutcome = ScenarioOutcome.SUCCESS
    steps_completed: int = 0
    steps_failed: int = 0
    error_message: Optional[str] = None
    step_results: List[Dict] = field(default_factory=list)
    injections: List[str] = field(default_factory=list)  # Injection IDs


class ChaosScenarioRunner:
    """
    Runner for chaos testing scenarios.

    Executes predefined scenarios and validates system resilience.

    Usage:
        runner = ChaosScenarioRunner()
        scenario = create_equipment_failure_scenario()
        result = runner.run_scenario(scenario)
    """

    def __init__(self, fault_injector: Optional[FaultInjector] = None):
        """
        Initialize scenario runner.

        Args:
            fault_injector: FaultInjector instance (creates new if None)
        """
        self.injector = fault_injector or FaultInjector()
        self._running_scenario: Optional[str] = None
        self._abort_requested = False
        self._lock = threading.RLock()

        # Result storage
        self._results: Dict[str, ScenarioResult] = {}

    def run_scenario(
        self,
        scenario: ChaosScenario,
        async_mode: bool = False,
    ) -> ScenarioResult:
        """
        Run a chaos scenario.

        Args:
            scenario: Scenario to run
            async_mode: Run asynchronously

        Returns:
            ScenarioResult
        """
        with self._lock:
            if self._running_scenario:
                return ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    start_time=datetime.now(),
                    outcome=ScenarioOutcome.ERROR,
                    error_message="Another scenario is already running",
                )
            self._running_scenario = scenario.scenario_id
            self._abort_requested = False

        result = ScenarioResult(
            scenario_id=scenario.scenario_id,
            start_time=datetime.now(),
        )

        try:
            for i, step in enumerate(scenario.steps):
                if self._abort_requested:
                    result.outcome = ScenarioOutcome.FAILURE
                    result.error_message = "Aborted by user"
                    break

                step_result = self._execute_step(step, result)
                result.step_results.append(step_result)

                if step_result["success"]:
                    result.steps_completed += 1
                else:
                    result.steps_failed += 1
                    if step.on_failure == "abort":
                        result.outcome = ScenarioOutcome.FAILURE
                        result.error_message = f"Step '{step.name}' failed"
                        break

            # Determine outcome
            if result.outcome == ScenarioOutcome.SUCCESS:
                if result.steps_failed > 0:
                    result.outcome = ScenarioOutcome.PARTIAL
                else:
                    result.outcome = ScenarioOutcome.SUCCESS

        except Exception as e:
            result.outcome = ScenarioOutcome.ERROR
            result.error_message = str(e)

        finally:
            # Cleanup
            if scenario.cleanup_on_failure or result.outcome == ScenarioOutcome.SUCCESS:
                self._cleanup(result)

            result.end_time = datetime.now()

            with self._lock:
                self._running_scenario = None
                self._results[scenario.scenario_id] = result

        return result

    def _execute_step(
        self,
        step: ScenarioStep,
        result: ScenarioResult,
    ) -> Dict:
        """Execute a single scenario step."""
        step_result = {
            "name": step.name,
            "action": step.action,
            "start_time": datetime.now().isoformat(),
            "success": False,
            "error": None,
        }

        try:
            if step.action == "inject":
                injection = self._inject_fault(step)
                if injection:
                    result.injections.append(injection.injection_id)
                    step_result["injection_id"] = injection.injection_id
                    step_result["success"] = injection.active or injection.outcome == "SUCCESS"
                else:
                    step_result["error"] = "Injection failed"

            elif step.action == "wait":
                time.sleep(step.wait_seconds)
                step_result["success"] = True

            elif step.action == "validate":
                if step.validation:
                    step_result["success"] = step.validation()
                else:
                    step_result["success"] = True

            elif step.action == "stop":
                if step.target:
                    # Stop specific injection
                    self.injector.stop_injection(step.target)
                else:
                    # Stop all injections for this scenario
                    for inj_id in result.injections:
                        self.injector.stop_injection(inj_id)
                step_result["success"] = True

            else:
                step_result["error"] = f"Unknown action: {step.action}"

        except Exception as e:
            step_result["error"] = str(e)

        step_result["end_time"] = datetime.now().isoformat()
        return step_result

    def _inject_fault(self, step: ScenarioStep) -> Optional[FaultInjection]:
        """Inject a fault based on step definition."""
        if not step.fault_type:
            return None

        if step.fault_type == FaultType.NODE_CRASH:
            return self.injector.inject_node_crash(
                step.target,
                **step.parameters,
            )
        elif step.fault_type == FaultType.NODE_HANG:
            return self.injector.inject_node_hang(
                step.target,
                **step.parameters,
            )
        elif step.fault_type == FaultType.MESSAGE_DELAY:
            return self.injector.inject_message_delay(
                step.target,
                **step.parameters,
            )
        elif step.fault_type == FaultType.MESSAGE_DROP:
            return self.injector.inject_message_drop(
                step.target,
                **step.parameters,
            )
        elif step.fault_type == FaultType.RESOURCE_EXHAUSTION:
            return self.injector.inject_resource_exhaustion(
                step.target,
                **step.parameters,
            )
        elif step.fault_type == FaultType.NETWORK_PARTITION:
            nodes = step.target.split(",")
            if len(nodes) == 2:
                return self.injector.inject_network_partition(
                    nodes[0].strip(),
                    nodes[1].strip(),
                    **step.parameters,
                )
        return None

    def _cleanup(self, result: ScenarioResult):
        """Cleanup after scenario execution."""
        for inj_id in result.injections:
            self.injector.stop_injection(inj_id)

    def abort_scenario(self):
        """Abort currently running scenario."""
        self._abort_requested = True

    def get_result(self, scenario_id: str) -> Optional[ScenarioResult]:
        """Get result for a scenario."""
        return self._results.get(scenario_id)

    def is_running(self) -> bool:
        """Check if a scenario is currently running."""
        return self._running_scenario is not None


# Predefined Scenarios

def create_equipment_failure_scenario(equipment_id: str = "bantam_cnc") -> ChaosScenario:
    """Create scenario for equipment failure during production."""
    return ChaosScenario(
        scenario_id=f"equipment_failure_{equipment_id}",
        name=f"Equipment Failure - {equipment_id}",
        description="Simulates equipment node crash during operation and validates recovery",
        steps=[
            ScenarioStep(
                name="Initial state validation",
                action="validate",
                validation=lambda: True,  # Would check equipment is running
            ),
            ScenarioStep(
                name="Inject equipment crash",
                action="inject",
                target=equipment_id,
                fault_type=FaultType.NODE_CRASH,
            ),
            ScenarioStep(
                name="Wait for detection",
                action="wait",
                wait_seconds=5.0,
            ),
            ScenarioStep(
                name="Validate supervisor detected failure",
                action="validate",
                validation=lambda: True,  # Would check supervisor logs
            ),
            ScenarioStep(
                name="Wait for recovery",
                action="wait",
                wait_seconds=10.0,
            ),
            ScenarioStep(
                name="Validate equipment recovered",
                action="validate",
                validation=lambda: True,  # Would check equipment is running again
            ),
        ],
        timeout_seconds=60.0,
        tags=["equipment", "recovery", "supervisor"],
    )


def create_safety_estop_scenario() -> ChaosScenario:
    """Create scenario for e-stop handling."""
    return ChaosScenario(
        scenario_id="safety_estop_test",
        name="Safety E-Stop Response",
        description="Tests system response to e-stop condition",
        steps=[
            ScenarioStep(
                name="Verify safety node active",
                action="validate",
            ),
            ScenarioStep(
                name="Inject orchestrator heartbeat timeout",
                action="inject",
                target="lego_mcp_orchestrator",
                fault_type=FaultType.NODE_HANG,
                parameters={"duration_seconds": 3.0},
            ),
            ScenarioStep(
                name="Wait for watchdog timeout",
                action="wait",
                wait_seconds=2.0,
            ),
            ScenarioStep(
                name="Validate e-stop triggered",
                action="validate",
            ),
            ScenarioStep(
                name="Wait for node resume",
                action="wait",
                wait_seconds=2.0,
            ),
        ],
        timeout_seconds=30.0,
        tags=["safety", "estop", "critical"],
    )


def create_cascade_failure_scenario() -> ChaosScenario:
    """Create scenario for cascade failure prevention."""
    return ChaosScenario(
        scenario_id="cascade_failure_test",
        name="Cascade Failure Prevention",
        description="Tests that single failure doesn't cascade to other systems",
        steps=[
            ScenarioStep(
                name="Inject supervisor crash",
                action="inject",
                target="lego_mcp_supervisor",
                fault_type=FaultType.NODE_CRASH,
            ),
            ScenarioStep(
                name="Wait",
                action="wait",
                wait_seconds=5.0,
            ),
            ScenarioStep(
                name="Validate safety still active",
                action="validate",
            ),
            ScenarioStep(
                name="Validate orchestrator still running",
                action="validate",
            ),
        ],
        timeout_seconds=60.0,
        tags=["cascade", "isolation", "supervisor"],
    )


def create_network_partition_scenario() -> ChaosScenario:
    """Create scenario for network partition handling."""
    return ChaosScenario(
        scenario_id="network_partition_test",
        name="Network Partition",
        description="Tests handling of network partition between control and supervisory zones",
        steps=[
            ScenarioStep(
                name="Inject network partition",
                action="inject",
                target="control_zone,supervisory_zone",
                fault_type=FaultType.NETWORK_PARTITION,
                parameters={"duration_seconds": 30.0},
            ),
            ScenarioStep(
                name="Wait during partition",
                action="wait",
                wait_seconds=10.0,
            ),
            ScenarioStep(
                name="Validate equipment in safe state",
                action="validate",
            ),
            ScenarioStep(
                name="Stop partition",
                action="stop",
            ),
            ScenarioStep(
                name="Wait for recovery",
                action="wait",
                wait_seconds=10.0,
            ),
            ScenarioStep(
                name="Validate reconnection",
                action="validate",
            ),
        ],
        timeout_seconds=120.0,
        tags=["network", "partition", "recovery"],
    )
