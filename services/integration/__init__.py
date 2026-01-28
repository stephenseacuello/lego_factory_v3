"""
Integration Layer for Flask CNC SCADA
======================================
Orchestrates all services for complete workflow execution.

Components:
- WorkflowCoordinator: Central orchestration connecting MES, GCode, Scheduler, etc.
- JobContext: Execution context manager for running jobs
- ServiceBus: Inter-service messaging and event routing
- EventDispatcher: Event publishing and subscription system
"""

from services.integration.workflow_coordinator import (
    WorkflowCoordinator,
    get_workflow_coordinator,
)
from services.integration.job_context import (
    JobContext,
    ExecutionState,
)
from services.integration.service_bus import (
    ServiceBus,
    Message,
    get_service_bus,
)
from services.integration.event_dispatcher import (
    EventDispatcher,
    Event,
    EventType,
    get_event_dispatcher,
)

__all__ = [
    # Coordinator
    "WorkflowCoordinator",
    "get_workflow_coordinator",
    # Job Context
    "JobContext",
    "ExecutionState",
    # Service Bus
    "ServiceBus",
    "Message",
    "get_service_bus",
    # Events
    "EventDispatcher",
    "Event",
    "EventType",
    "get_event_dispatcher",
]
