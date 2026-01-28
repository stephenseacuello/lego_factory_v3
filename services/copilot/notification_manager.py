"""
Notification Manager for proactive alerts.

Sends notifications through various channels:
- Slack
- Email
- SMS (via Twilio)
- WebSocket (browser)
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification delivery channels."""
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"
    WEBSOCKET = "websocket"
    MQTT = "mqtt"


class NotificationPriority(Enum):
    """Notification priority levels."""
    CRITICAL = "critical"  # Immediate delivery, all channels
    HIGH = "high"         # Fast delivery
    MEDIUM = "medium"     # Standard delivery
    LOW = "low"           # Batched delivery


@dataclass
class Notification:
    """A notification to send."""
    id: str
    title: str
    message: str
    priority: NotificationPriority
    channels: List[NotificationChannel]
    timestamp: datetime = field(default_factory=datetime.now)
    machine_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    sent: bool = False
    sent_at: Optional[datetime] = None
    delivery_status: Dict[str, str] = field(default_factory=dict)


@dataclass
class NotificationConfig:
    """Configuration for notification manager."""
    # Slack
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#cnc-alerts"

    # Email
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)

    # SMS (Twilio)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    sms_recipients: List[str] = field(default_factory=list)

    # Batching
    batch_interval_seconds: int = 60
    max_notifications_per_batch: int = 10

    # Throttling
    throttle_same_notification_minutes: int = 5


class NotificationManager:
    """
    Manages sending notifications through various channels.

    Features:
    - Multi-channel delivery
    - Priority-based routing
    - Notification batching
    - Throttling to prevent spam
    """

    def __init__(self, config: Optional[NotificationConfig] = None):
        """Initialize notification manager."""
        self.config = config or NotificationConfig()
        self._pending: List[Notification] = []
        self._sent_history: List[Notification] = []
        self._throttle_cache: Dict[str, datetime] = {}
        self._batch_task: Optional[asyncio.Task] = None

    async def send(self, notification: Notification) -> Dict[str, Any]:
        """
        Send a notification.

        Args:
            notification: The notification to send

        Returns:
            Delivery status for each channel
        """
        result = {
            "notification_id": notification.id,
            "delivered": [],
            "failed": [],
            "throttled": False,
        }

        # Check throttling
        throttle_key = f"{notification.title}:{notification.machine_id}"
        if throttle_key in self._throttle_cache:
            last_sent = self._throttle_cache[throttle_key]
            if datetime.now() - last_sent < timedelta(
                minutes=self.config.throttle_same_notification_minutes
            ):
                result["throttled"] = True
                logger.info(f"Notification throttled: {notification.title}")
                return result

        # Update throttle cache
        self._throttle_cache[throttle_key] = datetime.now()

        # Send to each channel
        for channel in notification.channels:
            try:
                if channel == NotificationChannel.SLACK:
                    success = await self._send_slack(notification)
                elif channel == NotificationChannel.EMAIL:
                    success = await self._send_email(notification)
                elif channel == NotificationChannel.SMS:
                    success = await self._send_sms(notification)
                elif channel == NotificationChannel.WEBSOCKET:
                    success = await self._send_websocket(notification)
                elif channel == NotificationChannel.MQTT:
                    success = await self._send_mqtt(notification)
                else:
                    success = False

                if success:
                    result["delivered"].append(channel.value)
                    notification.delivery_status[channel.value] = "delivered"
                else:
                    result["failed"].append(channel.value)
                    notification.delivery_status[channel.value] = "failed"

            except Exception as e:
                logger.error(f"Failed to send via {channel.value}: {e}")
                result["failed"].append(channel.value)
                notification.delivery_status[channel.value] = f"error: {str(e)}"

        notification.sent = len(result["delivered"]) > 0
        notification.sent_at = datetime.now()
        self._sent_history.append(notification)

        return result

    async def _send_slack(self, notification: Notification) -> bool:
        """Send notification via Slack webhook."""
        if not self.config.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False

        try:
            import aiohttp

            # Build Slack message
            color = {
                NotificationPriority.CRITICAL: "#FF0000",  # Red
                NotificationPriority.HIGH: "#FFA500",      # Orange
                NotificationPriority.MEDIUM: "#FFFF00",    # Yellow
                NotificationPriority.LOW: "#00FF00",       # Green
            }.get(notification.priority, "#808080")

            payload = {
                "channel": self.config.slack_channel,
                "attachments": [
                    {
                        "color": color,
                        "title": notification.title,
                        "text": notification.message,
                        "fields": [
                            {
                                "title": "Machine",
                                "value": notification.machine_id or "N/A",
                                "short": True,
                            },
                            {
                                "title": "Priority",
                                "value": notification.priority.value.upper(),
                                "short": True,
                            },
                        ],
                        "footer": "CNC SCADA Copilot",
                        "ts": notification.timestamp.timestamp(),
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.slack_webhook_url,
                    json=payload,
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent: {notification.title}")
                        return True
                    else:
                        logger.error(f"Slack error: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Slack send error: {e}")
            return False

    async def _send_email(self, notification: Notification) -> bool:
        """Send notification via email."""
        if not all([
            self.config.smtp_host,
            self.config.email_recipients,
        ]):
            logger.warning("Email not configured")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Build email
            msg = MIMEMultipart()
            msg["Subject"] = f"[CNC Alert] {notification.title}"
            msg["From"] = self.config.smtp_user or "cnc-copilot@local"
            msg["To"] = ", ".join(self.config.email_recipients)

            body = f"""
CNC SCADA Alert

Title: {notification.title}
Priority: {notification.priority.value.upper()}
Machine: {notification.machine_id or 'N/A'}
Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{notification.message}

---
Sent by CNC SCADA Copilot
            """

            msg.attach(MIMEText(body, "plain"))

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_user and self.config.smtp_password:
                    server.starttls()
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    msg["From"],
                    self.config.email_recipients,
                    msg.as_string(),
                )

            logger.info(f"Email notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False

    async def _send_sms(self, notification: Notification) -> bool:
        """Send notification via SMS (Twilio)."""
        if not all([
            self.config.twilio_account_sid,
            self.config.twilio_auth_token,
            self.config.twilio_from_number,
            self.config.sms_recipients,
        ]):
            logger.warning("SMS (Twilio) not configured")
            return False

        try:
            from twilio.rest import Client

            client = Client(
                self.config.twilio_account_sid,
                self.config.twilio_auth_token,
            )

            # Truncate message for SMS
            sms_body = f"{notification.title}: {notification.message}"[:160]

            for recipient in self.config.sms_recipients:
                client.messages.create(
                    body=sms_body,
                    from_=self.config.twilio_from_number,
                    to=recipient,
                )

            logger.info(f"SMS notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False

    async def _send_websocket(self, notification: Notification) -> bool:
        """Send notification via WebSocket to connected clients."""
        try:
            # Import SocketIO from Flask app
            # This integrates with the existing socketio_service
            from flask import current_app

            socketio = current_app.extensions.get("socketio")
            if not socketio:
                logger.warning("SocketIO not available")
                return False

            # Emit to connected clients
            socketio.emit(
                "copilot_notification",
                {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority.value,
                    "machine_id": notification.machine_id,
                    "timestamp": notification.timestamp.isoformat(),
                },
                namespace="/copilot",
            )

            logger.info(f"WebSocket notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            return False

    async def _send_mqtt(self, notification: Notification) -> bool:
        """Send notification via MQTT."""
        try:
            # Import MQTT service
            from services.mqtt_service import mqtt_client

            topic = f"cnc/notifications/{notification.priority.value}"
            payload = json.dumps({
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "machine_id": notification.machine_id,
                "timestamp": notification.timestamp.isoformat(),
            })

            mqtt_client.publish(topic, payload)

            logger.info(f"MQTT notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"MQTT send error: {e}")
            return False

    def queue_notification(self, notification: Notification):
        """Queue a notification for batch delivery."""
        self._pending.append(notification)

    async def process_batch(self):
        """Process pending notifications in batch."""
        if not self._pending:
            return

        # Group by priority
        critical = [n for n in self._pending if n.priority == NotificationPriority.CRITICAL]
        other = [n for n in self._pending if n.priority != NotificationPriority.CRITICAL]

        # Send critical immediately
        for notification in critical:
            await self.send(notification)

        # Batch others
        if other:
            # Create summary notification
            summary = Notification(
                id=f"batch-{datetime.now().timestamp()}",
                title=f"CNC Alerts Summary ({len(other)} alerts)",
                message="\n".join([f"- {n.title}" for n in other[:10]]),
                priority=NotificationPriority.MEDIUM,
                channels=[NotificationChannel.SLACK],
            )
            await self.send(summary)

        self._pending.clear()

    def get_history(
        self,
        limit: int = 50,
        priority: Optional[NotificationPriority] = None,
    ) -> List[Dict[str, Any]]:
        """Get notification history."""
        history = self._sent_history[-limit:]

        if priority:
            history = [n for n in history if n.priority == priority]

        return [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "priority": n.priority.value,
                "machine_id": n.machine_id,
                "timestamp": n.timestamp.isoformat(),
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "delivery_status": n.delivery_status,
            }
            for n in history
        ]

    def create_notification(
        self,
        title: str,
        message: str,
        priority: str = "medium",
        channels: Optional[List[str]] = None,
        machine_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Create a notification object."""
        priority_enum = {
            "critical": NotificationPriority.CRITICAL,
            "high": NotificationPriority.HIGH,
            "medium": NotificationPriority.MEDIUM,
            "low": NotificationPriority.LOW,
        }.get(priority.lower(), NotificationPriority.MEDIUM)

        channel_enums = []
        for ch in (channels or ["websocket"]):
            try:
                channel_enums.append(NotificationChannel(ch))
            except ValueError:
                pass

        return Notification(
            id=f"notif-{datetime.now().timestamp()}",
            title=title,
            message=message,
            priority=priority_enum,
            channels=channel_enums,
            machine_id=machine_id,
            data=data or {},
        )
