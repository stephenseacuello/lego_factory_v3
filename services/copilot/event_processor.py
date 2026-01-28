"""
Event Processor for CNC machine events.

Analyzes machine events and determines if action is needed.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of machine events."""
    # Status changes
    STATUS_CHANGE = "status_change"
    STATE_CHANGE = "state_change"

    # Position
    POSITION_UPDATE = "position_update"
    LIMIT_REACHED = "limit_reached"

    # Alarms and errors
    ALARM = "alarm"
    ERROR = "error"
    WARNING = "warning"

    # Job progress
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_PAUSED = "job_paused"
    JOB_PROGRESS = "job_progress"

    # Sensor data
    SENSOR_READING = "sensor_reading"
    SENSOR_ANOMALY = "sensor_anomaly"

    # Quality
    QUALITY_ALERT = "quality_alert"
    SPC_VIOLATION = "spc_violation"

    # System
    CONNECTION_LOST = "connection_lost"
    CONNECTION_RESTORED = "connection_restored"


class EventSeverity(Enum):
    """Severity of events."""
    CRITICAL = "critical"   # Requires immediate action
    HIGH = "high"          # Should address soon
    MEDIUM = "medium"      # Monitor situation
    LOW = "low"            # Informational
    INFO = "info"          # Just logging


@dataclass
class MachineEvent:
    """A machine event with context."""
    event_id: str
    event_type: EventType
    severity: EventSeverity
    machine_id: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    requires_action: bool = False
    action_taken: bool = False
    related_events: List[str] = field(default_factory=list)


@dataclass
class EventPattern:
    """Pattern to detect in event streams."""
    name: str
    description: str
    event_types: List[EventType]
    time_window_seconds: int = 60
    min_occurrences: int = 1
    severity: EventSeverity = EventSeverity.MEDIUM
    callback: Optional[str] = None


class EventProcessor:
    """
    Processes machine events and detects patterns.

    Features:
    - Event classification
    - Pattern detection
    - Anomaly identification
    - Event correlation
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """Initialize event processor."""
        self.flask_url = flask_url
        self._event_history: Dict[str, List[MachineEvent]] = {}
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        self._patterns: List[EventPattern] = []
        self._last_states: Dict[str, str] = {}

        # Load default patterns
        self._load_default_patterns()

    def _load_default_patterns(self):
        """Load default event patterns to detect."""
        self._patterns = [
            EventPattern(
                name="repeated_alarms",
                description="Same alarm occurring multiple times",
                event_types=[EventType.ALARM],
                time_window_seconds=300,  # 5 minutes
                min_occurrences=3,
                severity=EventSeverity.HIGH,
            ),
            EventPattern(
                name="frequent_stops",
                description="Machine stopping frequently",
                event_types=[EventType.JOB_PAUSED, EventType.STATE_CHANGE],
                time_window_seconds=600,  # 10 minutes
                min_occurrences=5,
                severity=EventSeverity.MEDIUM,
            ),
            EventPattern(
                name="connection_instability",
                description="Connection dropping repeatedly",
                event_types=[EventType.CONNECTION_LOST],
                time_window_seconds=300,
                min_occurrences=3,
                severity=EventSeverity.HIGH,
            ),
            EventPattern(
                name="quality_drift",
                description="Multiple SPC violations",
                event_types=[EventType.SPC_VIOLATION, EventType.QUALITY_ALERT],
                time_window_seconds=1800,  # 30 minutes
                min_occurrences=3,
                severity=EventSeverity.HIGH,
            ),
        ]

    async def process_event(self, event: MachineEvent) -> Dict[str, Any]:
        """
        Process an incoming machine event.

        Args:
            event: The machine event to process

        Returns:
            Processing result with any detected issues
        """
        result = {
            "event_id": event.event_id,
            "processed": True,
            "patterns_detected": [],
            "actions_triggered": [],
            "notifications": [],
        }

        # Store event in history
        if event.machine_id not in self._event_history:
            self._event_history[event.machine_id] = []
        self._event_history[event.machine_id].append(event)

        # Trim old events (keep last hour)
        cutoff = datetime.now() - timedelta(hours=1)
        self._event_history[event.machine_id] = [
            e for e in self._event_history[event.machine_id]
            if e.timestamp > cutoff
        ]

        # Check for pattern matches
        patterns = await self._check_patterns(event)
        result["patterns_detected"] = patterns

        # Call registered handlers
        if event.event_type in self._event_handlers:
            for handler in self._event_handlers[event.event_type]:
                try:
                    handler_result = await handler(event)
                    if handler_result:
                        result["actions_triggered"].append(handler_result)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")

        # Determine if notification needed
        notifications = self._determine_notifications(event, patterns)
        result["notifications"] = notifications

        logger.info(
            f"Processed event {event.event_id}: {event.event_type.value} "
            f"from {event.machine_id}"
        )

        return result

    async def _check_patterns(self, event: MachineEvent) -> List[Dict[str, Any]]:
        """Check for pattern matches in event history."""
        detected = []
        history = self._event_history.get(event.machine_id, [])

        for pattern in self._patterns:
            if event.event_type not in pattern.event_types:
                continue

            # Check time window
            cutoff = datetime.now() - timedelta(seconds=pattern.time_window_seconds)
            matching_events = [
                e for e in history
                if e.event_type in pattern.event_types and e.timestamp > cutoff
            ]

            if len(matching_events) >= pattern.min_occurrences:
                detected.append({
                    "pattern": pattern.name,
                    "description": pattern.description,
                    "severity": pattern.severity.value,
                    "occurrences": len(matching_events),
                    "time_window": pattern.time_window_seconds,
                })

        return detected

    def _determine_notifications(
        self,
        event: MachineEvent,
        patterns: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Determine what notifications to send."""
        notifications = []

        # Critical events always notify
        if event.severity == EventSeverity.CRITICAL:
            notifications.append({
                "priority": "critical",
                "title": f"Critical: {event.event_type.value}",
                "message": event.message,
                "machine_id": event.machine_id,
                "channels": ["slack", "email", "sms"],
            })

        # High severity events
        elif event.severity == EventSeverity.HIGH:
            notifications.append({
                "priority": "high",
                "title": f"Alert: {event.event_type.value}",
                "message": event.message,
                "machine_id": event.machine_id,
                "channels": ["slack", "email"],
            })

        # Pattern detections
        for pattern in patterns:
            if pattern["severity"] in ["critical", "high"]:
                notifications.append({
                    "priority": pattern["severity"],
                    "title": f"Pattern Detected: {pattern['pattern']}",
                    "message": pattern["description"],
                    "machine_id": event.machine_id,
                    "channels": ["slack"],
                })

        return notifications

    def register_handler(
        self,
        event_type: EventType,
        handler: Callable[[MachineEvent], Awaitable[Optional[Dict]]],
    ):
        """Register a handler for an event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def create_event_from_mqtt(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> Optional[MachineEvent]:
        """
        Create a MachineEvent from MQTT message.

        Args:
            topic: MQTT topic
            payload: Message payload

        Returns:
            MachineEvent or None if not relevant
        """
        # Parse topic to extract machine ID and event type
        # Expected format: cnc/{machine_id}/{event_type}
        parts = topic.split("/")
        if len(parts) < 3:
            return None

        machine_id = parts[1]
        event_str = parts[2]

        # Map topic to event type
        event_map = {
            "status": EventType.STATUS_CHANGE,
            "state": EventType.STATE_CHANGE,
            "position": EventType.POSITION_UPDATE,
            "alarm": EventType.ALARM,
            "error": EventType.ERROR,
            "job": EventType.JOB_PROGRESS,
            "sensor": EventType.SENSOR_READING,
            "quality": EventType.QUALITY_ALERT,
        }

        event_type = event_map.get(event_str, EventType.STATUS_CHANGE)

        # Determine severity
        severity = EventSeverity.INFO
        if event_type == EventType.ALARM:
            severity = EventSeverity.HIGH
        elif event_type == EventType.ERROR:
            severity = EventSeverity.CRITICAL
        elif event_type in [EventType.QUALITY_ALERT, EventType.SPC_VIOLATION]:
            severity = EventSeverity.HIGH

        # Check for state changes
        new_state = payload.get("state", payload.get("status", ""))
        if machine_id in self._last_states:
            if new_state != self._last_states[machine_id]:
                event_type = EventType.STATE_CHANGE
                if new_state == "alarm":
                    severity = EventSeverity.HIGH
        self._last_states[machine_id] = new_state

        return MachineEvent(
            event_id=f"{machine_id}-{datetime.now().timestamp()}",
            event_type=event_type,
            severity=severity,
            machine_id=machine_id,
            timestamp=datetime.now(),
            data=payload,
            message=payload.get("message", str(payload)),
            requires_action=severity in [EventSeverity.CRITICAL, EventSeverity.HIGH],
        )

    def get_event_history(
        self,
        machine_id: str,
        event_type: Optional[EventType] = None,
        since: Optional[datetime] = None,
    ) -> List[MachineEvent]:
        """Get event history for a machine."""
        events = self._event_history.get(machine_id, [])

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if since:
            events = [e for e in events if e.timestamp > since]

        return events

    def get_statistics(self, machine_id: Optional[str] = None) -> Dict[str, Any]:
        """Get event statistics."""
        if machine_id:
            events = self._event_history.get(machine_id, [])
        else:
            events = []
            for machine_events in self._event_history.values():
                events.extend(machine_events)

        if not events:
            return {"total_events": 0}

        # Count by type
        by_type = {}
        by_severity = {}

        for event in events:
            type_key = event.event_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            sev_key = event.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1

        return {
            "total_events": len(events),
            "by_type": by_type,
            "by_severity": by_severity,
            "machines": list(self._event_history.keys()),
            "time_range": {
                "oldest": min(e.timestamp for e in events).isoformat() if events else None,
                "newest": max(e.timestamp for e in events).isoformat() if events else None,
            },
        }
