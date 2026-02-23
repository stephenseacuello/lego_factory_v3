"""
V8 Notification Service
========================

Multi-channel notification delivery for:
- Email notifications
- SMS alerts (via Twilio)
- Webhook integrations
- Slack/Teams notifications
- In-app notifications
- Push notifications

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from .notification_service import (
    NotificationService,
    NotificationChannel,
    NotificationPriority,
    NotificationTemplate,
    Notification,
    NotificationResult,
    get_notification_service,
    send_alert_notification,
    send_action_notification,
    send_system_notification,
)

__all__ = [
    "NotificationService",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationTemplate",
    "Notification",
    "NotificationResult",
    "get_notification_service",
    "send_alert_notification",
    "send_action_notification",
    "send_system_notification",
]

__version__ = "8.0.0"
