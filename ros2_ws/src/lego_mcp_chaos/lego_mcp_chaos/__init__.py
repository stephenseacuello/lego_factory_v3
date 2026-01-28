"""
LEGO MCP Chaos Testing Framework

Chaos engineering for ROS2 systems:
- Fault injection (node crashes, network partitions, delays)
- Predefined chaos scenarios
- Resilience validation
- Recovery time objective (RTO) testing

Industry 4.0/5.0 Architecture - SRE Practices
"""

from .fault_injector import FaultInjector, FaultType, FaultInjection
from .chaos_scenarios import (
    ChaosScenario,
    ChaosScenarioRunner,
    ScenarioStep,
    ScenarioOutcome,
    ScenarioResult,
    create_equipment_failure_scenario,
    create_safety_estop_scenario,
    create_cascade_failure_scenario,
    create_network_partition_scenario,
)
from .resilience_validator import (
    ResilienceValidator,
    ValidationLevel,
    ValidationCriteria,
    ValidationResult,
    ResilienceReport,
)

__all__ = [
    # Fault injection
    'FaultInjector',
    'FaultType',
    'FaultInjection',
    # Chaos scenarios
    'ChaosScenario',
    'ChaosScenarioRunner',
    'ScenarioStep',
    'ScenarioOutcome',
    'ScenarioResult',
    'create_equipment_failure_scenario',
    'create_safety_estop_scenario',
    'create_cascade_failure_scenario',
    'create_network_partition_scenario',
    # Resilience validation
    'ResilienceValidator',
    'ValidationLevel',
    'ValidationCriteria',
    'ValidationResult',
    'ResilienceReport',
]
