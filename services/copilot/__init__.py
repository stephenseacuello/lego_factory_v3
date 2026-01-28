"""
CNC SCADA Real-time Copilot Service.

Provides Claude-powered assistance with live machine context:
- Real-time status monitoring
- Proactive issue detection and notification
- Natural language interaction
- Shift handoff summaries
- MQTT integration for live updates
"""

from .realtime_copilot import (
    RealtimeCopilot,
    CopilotConfig,
    CopilotMode,
    MachineContext,
    ConversationContext,
    get_copilot,
    configure_copilot,
)

from .event_processor import (
    EventProcessor,
    MachineEvent,
    EventType,
    EventPattern,
)

from .notification_manager import (
    NotificationManager,
    NotificationConfig,
    Notification,
    NotificationChannel,
    NotificationPriority,
)

from .mqtt_listener import (
    MQTTListener,
    MQTTConfig,
    create_mqtt_listener_for_copilot,
)

from .shift_awareness import (
    ShiftAwareness,
    ShiftSchedule,
    Shift,
    ShiftType,
    Operator,
    ShiftAssignment,
    ShiftMetrics,
)

__all__ = [
    # Core copilot
    "RealtimeCopilot",
    "CopilotConfig",
    "CopilotMode",
    "MachineContext",
    "ConversationContext",
    "get_copilot",
    "configure_copilot",
    # Event processing
    "EventProcessor",
    "MachineEvent",
    "EventType",
    "EventPattern",
    # Notifications
    "NotificationManager",
    "NotificationConfig",
    "Notification",
    "NotificationChannel",
    "NotificationPriority",
    # MQTT
    "MQTTListener",
    "MQTTConfig",
    "create_mqtt_listener_for_copilot",
    # Shift awareness
    "ShiftAwareness",
    "ShiftSchedule",
    "Shift",
    "ShiftType",
    "Operator",
    "ShiftAssignment",
    "ShiftMetrics",
]
