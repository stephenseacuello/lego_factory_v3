"""
LEGO MCP V8 Orchestration Services
===================================

Algorithm-to-Action orchestration layer providing:
- Decision engine for AI recommendations
- Approval workflow management
- Execution coordination
- Event correlation
- Unified workflow management

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from .decision_engine import DecisionEngine, Decision, DecisionOutcome
from .execution_coordinator import ExecutionCoordinator, ExecutionPlan
from .event_correlator import EventCorrelator, CorrelatedEvent
from .workflow_manager import (
    WorkflowManager,
    WorkflowState,
    WorkflowType,
    StepType,
    ApprovalLevel,
    WorkflowStep,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowEvent,
    get_workflow_manager,
)

__all__ = [
    # Decision Engine
    'DecisionEngine',
    'Decision',
    'DecisionOutcome',
    # Execution Coordinator
    'ExecutionCoordinator',
    'ExecutionPlan',
    # Event Correlator
    'EventCorrelator',
    'CorrelatedEvent',
    # Workflow Manager
    'WorkflowManager',
    'WorkflowState',
    'WorkflowType',
    'StepType',
    'ApprovalLevel',
    'WorkflowStep',
    'WorkflowDefinition',
    'WorkflowInstance',
    'WorkflowEvent',
    'get_workflow_manager',
]

__version__ = '8.0.0'
