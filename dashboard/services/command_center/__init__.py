"""
LEGO MCP V8 Command Center Services
====================================

Unified Command & Control infrastructure providing:
- System health aggregation
- Real-time KPI monitoring
- Alert management
- Action console
- Service orchestration
- Message bus integration
- ROS2 equipment integration

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from .system_health import SystemHealthService, HealthStatus, ServiceHealth
from .kpi_aggregator import KPIAggregator, KPICategory, KPIMetric
from .alert_manager import AlertManager, Alert, AlertSeverity, AlertStatus
from .action_console import ActionConsole, Action, ActionStatus, ActionCategory
from .service_registry import (
    ServiceRegistry,
    ServiceDescriptor,
    ServiceStatus,
    ServiceCategory,
    get_registry,
)
from .orchestrator import (
    ManufacturingOrchestrator,
    WorkflowContext,
    WorkflowStep,
    WorkflowStatus,
    get_orchestrator,
    create_production_workflow,
)
from .integration_bus import (
    MessageBus,
    EventType,
    EventPriority,
    SystemEvent,
    get_message_bus,
    emit_job_created,
    emit_quality_result,
    emit_safety_alert,
)
from .ros2_integration import (
    ROS2CommandCenter,
    EquipmentState,
    EquipmentType,
    LifecycleState,
    CommandResult,
    get_ros2_command_center,
)

__all__ = [
    # System Health
    'SystemHealthService',
    'HealthStatus',
    'ServiceHealth',

    # KPI Aggregation
    'KPIAggregator',
    'KPICategory',
    'KPIMetric',

    # Alert Management
    'AlertManager',
    'Alert',
    'AlertSeverity',
    'AlertStatus',

    # Action Console
    'ActionConsole',
    'Action',
    'ActionStatus',
    'ActionCategory',

    # Service Registry
    'ServiceRegistry',
    'ServiceDescriptor',
    'ServiceStatus',
    'ServiceCategory',
    'get_registry',

    # Orchestration
    'ManufacturingOrchestrator',
    'WorkflowContext',
    'WorkflowStep',
    'WorkflowStatus',
    'get_orchestrator',
    'create_production_workflow',

    # Message Bus
    'MessageBus',
    'EventType',
    'EventPriority',
    'SystemEvent',
    'get_message_bus',
    'emit_job_created',
    'emit_quality_result',
    'emit_safety_alert',

    # ROS2 Integration
    'ROS2CommandCenter',
    'EquipmentState',
    'EquipmentType',
    'LifecycleState',
    'CommandResult',
    'get_ros2_command_center',
]

__version__ = '8.0.0'
