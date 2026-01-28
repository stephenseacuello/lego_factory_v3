"""
V8 Notification Service Implementation
=======================================

Multi-channel notification delivery system with:
- Template-based message formatting
- Priority-based routing
- Delivery tracking and retry logic
- Channel-specific adapters

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import hashlib
import json
import logging
import os
import smtplib
import threading
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Available notification channels"""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    IN_APP = "in_app"
    PUSH = "push"


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(Enum):
    """Notification delivery status"""
    PENDING = "pending"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class NotificationTemplate:
    """Template for notification messages"""
    template_id: str
    name: str
    subject_template: str
    body_template: str
    channels: List[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(self, context: Dict[str, Any]) -> tuple:
        """Render template with context variables."""
        subject = self.subject_template
        body = self.body_template

        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        return subject, body


@dataclass
class Notification:
    """Single notification record"""
    notification_id: str
    template_id: Optional[str]
    channel: NotificationChannel
    priority: NotificationPriority
    recipient: str
    subject: str
    body: str
    status: NotificationStatus
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "template_id": self.template_id,
            "channel": self.channel.value,
            "priority": self.priority.value,
            "recipient": self.recipient,
            "subject": self.subject,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "retry_count": self.retry_count,
            "error_message": self.error_message
        }


@dataclass
class NotificationResult:
    """Result of notification delivery"""
    success: bool
    notification_id: str
    channel: NotificationChannel
    message: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }


# ============================================
# Channel Adapters
# ============================================

class ChannelAdapter(ABC):
    """Base class for notification channel adapters"""

    @abstractmethod
    def send(self, notification: Notification) -> NotificationResult:
        """Send notification through this channel."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if channel is properly configured."""
        pass


class EmailAdapter(ChannelAdapter):
    """Email notification adapter using SMTP"""

    def __init__(self):
        self.smtp_host = os.environ.get("SMTP_HOST", "localhost")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.from_address = os.environ.get("SMTP_FROM", "noreply@lego-mcp.local")
        self.use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user)

    def send(self, notification: Notification) -> NotificationResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notification.subject
            msg["From"] = self.from_address
            msg["To"] = notification.recipient

            # Create HTML and plain text versions
            text_part = MIMEText(notification.body, "plain")
            html_part = MIMEText(
                f"<html><body><p>{notification.body}</p></body></html>",
                "html"
            )

            msg.attach(text_part)
            msg.attach(html_part)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return NotificationResult(
                success=True,
                notification_id=notification.notification_id,
                channel=NotificationChannel.EMAIL,
                message="Email sent successfully",
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.EMAIL,
                message=str(e),
                timestamp=datetime.now()
            )


class WebhookAdapter(ChannelAdapter):
    """Webhook notification adapter"""

    def __init__(self):
        self.timeout = int(os.environ.get("WEBHOOK_TIMEOUT", "30"))

    def is_configured(self) -> bool:
        return True  # Webhooks are configured per-notification

    def send(self, notification: Notification) -> NotificationResult:
        webhook_url = notification.metadata.get("webhook_url")
        if not webhook_url:
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.WEBHOOK,
                message="No webhook URL provided",
                timestamp=datetime.now()
            )

        try:
            payload = {
                "notification_id": notification.notification_id,
                "subject": notification.subject,
                "body": notification.body,
                "priority": notification.priority.value,
                "timestamp": notification.created_at.isoformat(),
                "metadata": notification.metadata
            }

            headers = {"Content-Type": "application/json"}
            auth_header = notification.metadata.get("webhook_auth")
            if auth_header:
                headers["Authorization"] = auth_header

            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            return NotificationResult(
                success=True,
                notification_id=notification.notification_id,
                channel=NotificationChannel.WEBHOOK,
                message=f"Webhook delivered: {response.status_code}",
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.WEBHOOK,
                message=str(e),
                timestamp=datetime.now()
            )


class SlackAdapter(ChannelAdapter):
    """Slack notification adapter"""

    def __init__(self):
        self.webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        self.default_channel = os.environ.get("SLACK_DEFAULT_CHANNEL", "#alerts")

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def send(self, notification: Notification) -> NotificationResult:
        if not self.webhook_url:
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.SLACK,
                message="Slack webhook not configured",
                timestamp=datetime.now()
            )

        try:
            # Build Slack message with blocks
            color_map = {
                NotificationPriority.CRITICAL: "#dc3545",
                NotificationPriority.HIGH: "#fd7e14",
                NotificationPriority.NORMAL: "#0d6efd",
                NotificationPriority.LOW: "#6c757d"
            }

            payload = {
                "channel": notification.metadata.get("slack_channel", self.default_channel),
                "attachments": [{
                    "color": color_map.get(notification.priority, "#0d6efd"),
                    "title": notification.subject,
                    "text": notification.body,
                    "footer": "LEGO MCP Command Center",
                    "ts": int(notification.created_at.timestamp())
                }]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            return NotificationResult(
                success=True,
                notification_id=notification.notification_id,
                channel=NotificationChannel.SLACK,
                message="Slack message sent",
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.SLACK,
                message=str(e),
                timestamp=datetime.now()
            )


class TeamsAdapter(ChannelAdapter):
    """Microsoft Teams notification adapter"""

    def __init__(self):
        self.webhook_url = os.environ.get("TEAMS_WEBHOOK_URL", "")

    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def send(self, notification: Notification) -> NotificationResult:
        if not self.webhook_url:
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.TEAMS,
                message="Teams webhook not configured",
                timestamp=datetime.now()
            )

        try:
            # Build Teams Adaptive Card
            color_map = {
                NotificationPriority.CRITICAL: "attention",
                NotificationPriority.HIGH: "warning",
                NotificationPriority.NORMAL: "accent",
                NotificationPriority.LOW: "default"
            }

            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "0076D7",
                "summary": notification.subject,
                "sections": [{
                    "activityTitle": notification.subject,
                    "activitySubtitle": f"Priority: {notification.priority.value}",
                    "text": notification.body,
                    "markdown": True
                }]
            }

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            return NotificationResult(
                success=True,
                notification_id=notification.notification_id,
                channel=NotificationChannel.TEAMS,
                message="Teams message sent",
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Teams send failed: {e}")
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=NotificationChannel.TEAMS,
                message=str(e),
                timestamp=datetime.now()
            )


class InAppAdapter(ChannelAdapter):
    """In-app notification adapter (stores for UI retrieval)"""

    def __init__(self):
        self._notifications: deque = deque(maxlen=1000)
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        return True

    def send(self, notification: Notification) -> NotificationResult:
        with self._lock:
            self._notifications.append(notification)

        return NotificationResult(
            success=True,
            notification_id=notification.notification_id,
            channel=NotificationChannel.IN_APP,
            message="In-app notification stored",
            timestamp=datetime.now()
        )

    def get_notifications(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Notification]:
        """Get recent in-app notifications."""
        with self._lock:
            notifications = list(self._notifications)

        if user_id:
            notifications = [
                n for n in notifications
                if n.recipient == user_id or n.recipient == "all"
            ]

        return notifications[-limit:]


# ============================================
# Notification Service
# ============================================

class NotificationService:
    """
    Centralized notification service.

    Manages multi-channel notification delivery with:
    - Template-based messaging
    - Priority routing
    - Delivery tracking
    - Retry logic
    """

    _instance: Optional["NotificationService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "NotificationService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._templates: Dict[str, NotificationTemplate] = {}
        self._adapters: Dict[NotificationChannel, ChannelAdapter] = {}
        self._history: deque = deque(maxlen=10000)
        self._subscribers: Dict[str, Set[NotificationChannel]] = {}
        self._data_lock = threading.RLock()

        self._setup_adapters()
        self._setup_default_templates()
        self._initialized = True

        logger.info("NotificationService initialized")

    def _setup_adapters(self) -> None:
        """Initialize channel adapters."""
        self._adapters[NotificationChannel.EMAIL] = EmailAdapter()
        self._adapters[NotificationChannel.WEBHOOK] = WebhookAdapter()
        self._adapters[NotificationChannel.SLACK] = SlackAdapter()
        self._adapters[NotificationChannel.TEAMS] = TeamsAdapter()
        self._adapters[NotificationChannel.IN_APP] = InAppAdapter()

    def _setup_default_templates(self) -> None:
        """Setup default notification templates."""
        # Alert template
        self.register_template(NotificationTemplate(
            template_id="alert_critical",
            name="Critical Alert",
            subject_template="[CRITICAL] {{alert_title}}",
            body_template="Critical alert on {{source}}:\n\n{{message}}\n\nTime: {{timestamp}}",
            channels=[
                NotificationChannel.EMAIL,
                NotificationChannel.SLACK,
                NotificationChannel.IN_APP
            ],
            priority=NotificationPriority.CRITICAL
        ))

        self.register_template(NotificationTemplate(
            template_id="alert_high",
            name="High Priority Alert",
            subject_template="[HIGH] {{alert_title}}",
            body_template="High priority alert on {{source}}:\n\n{{message}}\n\nTime: {{timestamp}}",
            channels=[
                NotificationChannel.EMAIL,
                NotificationChannel.SLACK,
                NotificationChannel.IN_APP
            ],
            priority=NotificationPriority.HIGH
        ))

        self.register_template(NotificationTemplate(
            template_id="alert_normal",
            name="Alert",
            subject_template="[ALERT] {{alert_title}}",
            body_template="Alert on {{source}}:\n\n{{message}}",
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.NORMAL
        ))

        # Action templates
        self.register_template(NotificationTemplate(
            template_id="action_pending",
            name="Action Pending Approval",
            subject_template="Action Pending: {{action_title}}",
            body_template="An action requires your approval:\n\n{{action_title}}\n\nType: {{action_type}}\nTarget: {{target}}\nRisk: {{risk_level}}\n\nPlease review in the Command Center.",
            channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
            priority=NotificationPriority.HIGH
        ))

        self.register_template(NotificationTemplate(
            template_id="action_approved",
            name="Action Approved",
            subject_template="Action Approved: {{action_title}}",
            body_template="Action '{{action_title}}' has been approved by {{approver}}.\n\nExecution will begin shortly.",
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.NORMAL
        ))

        self.register_template(NotificationTemplate(
            template_id="action_rejected",
            name="Action Rejected",
            subject_template="Action Rejected: {{action_title}}",
            body_template="Action '{{action_title}}' has been rejected.\n\nReason: {{reason}}",
            channels=[NotificationChannel.IN_APP],
            priority=NotificationPriority.NORMAL
        ))

        # System templates
        self.register_template(NotificationTemplate(
            template_id="system_maintenance",
            name="System Maintenance",
            subject_template="Scheduled Maintenance: {{system_name}}",
            body_template="Scheduled maintenance for {{system_name}}.\n\nStart: {{start_time}}\nEnd: {{end_time}}\n\nServices may be temporarily unavailable.",
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            priority=NotificationPriority.NORMAL
        ))

        self.register_template(NotificationTemplate(
            template_id="daily_report",
            name="Daily Report",
            subject_template="Daily Manufacturing Report - {{date}}",
            body_template="Daily report summary:\n\n{{summary}}\n\nView full report in the Command Center.",
            channels=[NotificationChannel.EMAIL],
            priority=NotificationPriority.LOW
        ))

    def register_template(self, template: NotificationTemplate) -> None:
        """Register a notification template."""
        with self._data_lock:
            self._templates[template.template_id] = template
            logger.debug(f"Registered template: {template.template_id}")

    def get_template(self, template_id: str) -> Optional[NotificationTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def subscribe(
        self,
        user_id: str,
        channels: List[NotificationChannel]
    ) -> None:
        """Subscribe a user to notification channels."""
        with self._data_lock:
            self._subscribers[user_id] = set(channels)

    def unsubscribe(self, user_id: str) -> None:
        """Unsubscribe a user from all channels."""
        with self._data_lock:
            self._subscribers.pop(user_id, None)

    def send(
        self,
        recipient: str,
        channel: NotificationChannel,
        subject: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        template_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NotificationResult:
        """Send a single notification."""
        notification = Notification(
            notification_id=f"NOT-{uuid.uuid4().hex[:12].upper()}",
            template_id=template_id,
            channel=channel,
            priority=priority,
            recipient=recipient,
            subject=subject,
            body=body,
            status=NotificationStatus.PENDING,
            created_at=datetime.now(),
            metadata=metadata or {}
        )

        return self._deliver(notification)

    def send_from_template(
        self,
        template_id: str,
        recipients: List[str],
        context: Dict[str, Any],
        channels: Optional[List[NotificationChannel]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[NotificationResult]:
        """Send notifications using a template."""
        template = self._templates.get(template_id)
        if not template:
            logger.error(f"Template not found: {template_id}")
            return []

        subject, body = template.render(context)
        use_channels = channels or template.channels
        results = []

        for recipient in recipients:
            for channel in use_channels:
                result = self.send(
                    recipient=recipient,
                    channel=channel,
                    subject=subject,
                    body=body,
                    priority=template.priority,
                    template_id=template_id,
                    metadata=metadata
                )
                results.append(result)

        return results

    def _deliver(self, notification: Notification) -> NotificationResult:
        """Deliver a notification through its channel."""
        adapter = self._adapters.get(notification.channel)
        if not adapter:
            return NotificationResult(
                success=False,
                notification_id=notification.notification_id,
                channel=notification.channel,
                message=f"No adapter for channel: {notification.channel}",
                timestamp=datetime.now()
            )

        if not adapter.is_configured():
            # Fall back to in-app for unconfigured channels
            if notification.channel != NotificationChannel.IN_APP:
                logger.warning(
                    f"Channel {notification.channel} not configured, "
                    f"falling back to in-app"
                )
                notification.channel = NotificationChannel.IN_APP
                adapter = self._adapters[NotificationChannel.IN_APP]

        notification.status = NotificationStatus.SENDING
        notification.sent_at = datetime.now()

        result = adapter.send(notification)

        if result.success:
            notification.status = NotificationStatus.DELIVERED
            notification.delivered_at = datetime.now()
        else:
            notification.status = NotificationStatus.FAILED
            notification.error_message = result.message

            # Retry logic for failed notifications
            if notification.retry_count < notification.max_retries:
                notification.retry_count += 1
                notification.status = NotificationStatus.RETRYING
                # Would queue for retry here

        # Store in history
        with self._data_lock:
            self._history.append(notification)

        return result

    def get_history(
        self,
        channel: Optional[NotificationChannel] = None,
        status: Optional[NotificationStatus] = None,
        limit: int = 100
    ) -> List[Notification]:
        """Get notification history."""
        with self._data_lock:
            notifications = list(self._history)

        if channel:
            notifications = [n for n in notifications if n.channel == channel]
        if status:
            notifications = [n for n in notifications if n.status == status]

        return notifications[-limit:]

    def get_in_app_notifications(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Notification]:
        """Get in-app notifications for display."""
        adapter = self._adapters.get(NotificationChannel.IN_APP)
        if isinstance(adapter, InAppAdapter):
            return adapter.get_notifications(user_id, limit)
        return []

    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all notification channels."""
        return {
            channel.value: {
                "configured": adapter.is_configured(),
                "type": type(adapter).__name__
            }
            for channel, adapter in self._adapters.items()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        with self._data_lock:
            history = list(self._history)

        by_status = {}
        by_channel = {}
        by_priority = {}

        for n in history:
            by_status[n.status.value] = by_status.get(n.status.value, 0) + 1
            by_channel[n.channel.value] = by_channel.get(n.channel.value, 0) + 1
            by_priority[n.priority.value] = by_priority.get(n.priority.value, 0) + 1

        return {
            "total": len(history),
            "by_status": by_status,
            "by_channel": by_channel,
            "by_priority": by_priority
        }


# Singleton accessor
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get singleton NotificationService instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# Convenience functions
def send_alert_notification(
    alert_id: str,
    title: str,
    message: str,
    severity: str,
    source: str,
    recipients: Optional[List[str]] = None
) -> List[NotificationResult]:
    """Send alert notification using appropriate template."""
    service = get_notification_service()

    template_map = {
        "critical": "alert_critical",
        "high": "alert_high",
        "medium": "alert_normal",
        "low": "alert_normal"
    }
    template_id = template_map.get(severity.lower(), "alert_normal")

    context = {
        "alert_id": alert_id,
        "alert_title": title,
        "message": message,
        "source": source,
        "timestamp": datetime.now().isoformat()
    }

    return service.send_from_template(
        template_id=template_id,
        recipients=recipients or ["all"],
        context=context,
        metadata={"alert_id": alert_id, "severity": severity}
    )


def send_action_notification(
    action_id: str,
    title: str,
    action_type: str,
    target: str,
    status: str,
    recipients: List[str],
    **kwargs
) -> List[NotificationResult]:
    """Send action-related notification."""
    service = get_notification_service()

    template_map = {
        "pending": "action_pending",
        "approved": "action_approved",
        "rejected": "action_rejected"
    }
    template_id = template_map.get(status.lower(), "action_pending")

    context = {
        "action_id": action_id,
        "action_title": title,
        "action_type": action_type,
        "target": target,
        **kwargs
    }

    return service.send_from_template(
        template_id=template_id,
        recipients=recipients,
        context=context,
        metadata={"action_id": action_id}
    )


def send_system_notification(
    subject: str,
    body: str,
    priority: str = "normal",
    channels: Optional[List[str]] = None
) -> List[NotificationResult]:
    """Send system-wide notification."""
    service = get_notification_service()

    priority_map = {
        "low": NotificationPriority.LOW,
        "normal": NotificationPriority.NORMAL,
        "high": NotificationPriority.HIGH,
        "critical": NotificationPriority.CRITICAL
    }
    notif_priority = priority_map.get(priority.lower(), NotificationPriority.NORMAL)

    use_channels = [
        NotificationChannel(c) for c in (channels or ["in_app"])
    ]

    results = []
    for channel in use_channels:
        result = service.send(
            recipient="all",
            channel=channel,
            subject=subject,
            body=body,
            priority=notif_priority
        )
        results.append(result)

    return results
