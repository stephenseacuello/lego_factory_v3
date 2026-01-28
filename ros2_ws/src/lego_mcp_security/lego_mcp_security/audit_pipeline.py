#!/usr/bin/env python3
"""
Security Audit Pipeline for LEGO MCP

Collects, processes, and stores security audit events for:
- Compliance reporting (IEC 62443, ISO 27001)
- Incident investigation
- Anomaly detection
- Forensic analysis

Industry 4.0/5.0 Architecture - Security Operations
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
import hashlib
import json
import threading
from collections import deque


class AuditEventType(Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    CONFIGURATION_CHANGE = "configuration_change"
    NODE_LIFECYCLE = "node_lifecycle"
    SECURITY_INCIDENT = "security_incident"
    ZONE_CROSSING = "zone_crossing"
    ESTOP_TRIGGERED = "estop_triggered"
    ESTOP_RESET = "estop_reset"
    CERTIFICATE_EVENT = "certificate_event"
    ANOMALY_DETECTED = "anomaly_detected"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = 0
    INFO = 1
    NOTICE = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    ALERT = 6
    EMERGENCY = 7


@dataclass
class AuditEvent:
    """Single audit event record."""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    source_node: str
    source_zone: str
    target_resource: str
    action: str
    outcome: str  # SUCCESS, FAILURE, PENDING
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    details: Dict = field(default_factory=dict)
    # Tamper evidence
    previous_hash: str = ""
    event_hash: str = ""


class SecurityAuditPipeline:
    """
    Security Audit Pipeline.

    Provides centralized audit logging with:
    - Event collection from all security-relevant sources
    - Chain of custody (hash linking for tamper evidence)
    - Real-time alerting on critical events
    - Export for SIEM integration
    """

    def __init__(
        self,
        max_buffer_size: int = 10000,
        retention_hours: int = 168,  # 7 days
        enable_hash_chain: bool = True,
    ):
        """
        Initialize audit pipeline.

        Args:
            max_buffer_size: Maximum events in memory buffer
            retention_hours: How long to retain events
            enable_hash_chain: Enable tamper-evident hash chain
        """
        self._buffer: deque[AuditEvent] = deque(maxlen=max_buffer_size)
        self._retention_hours = retention_hours
        self._enable_hash_chain = enable_hash_chain
        self._lock = threading.RLock()
        self._last_hash = "GENESIS"
        self._alert_handlers: List[Callable[[AuditEvent], None]] = []
        self._event_count = 0

        # Severity thresholds for alerting
        self._alert_threshold = AuditSeverity.WARNING

    def record_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        source_node: str,
        source_zone: str,
        target_resource: str,
        action: str,
        outcome: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict] = None,
    ) -> AuditEvent:
        """
        Record an audit event.

        Args:
            event_type: Type of event
            severity: Event severity
            source_node: Node generating the event
            source_zone: Security zone of source
            target_resource: Resource being accessed/modified
            action: Action being performed
            outcome: Result of the action
            user_id: Optional user identifier
            session_id: Optional session identifier
            details: Additional event details

        Returns:
            The recorded AuditEvent
        """
        with self._lock:
            self._event_count += 1
            now = datetime.now()

            # Generate event ID
            event_id = hashlib.sha256(
                f"{now.isoformat()}{source_node}{self._event_count}".encode()
            ).hexdigest()[:16]

            # Create event
            event = AuditEvent(
                event_id=event_id,
                timestamp=now,
                event_type=event_type,
                severity=severity,
                source_node=source_node,
                source_zone=source_zone,
                target_resource=target_resource,
                action=action,
                outcome=outcome,
                user_id=user_id,
                session_id=session_id,
                details=details or {},
            )

            # Add hash chain for tamper evidence
            if self._enable_hash_chain:
                event.previous_hash = self._last_hash
                event_data = f"{event.event_id}{event.timestamp.isoformat()}{event.source_node}{event.action}{event.previous_hash}"
                event.event_hash = hashlib.sha256(event_data.encode()).hexdigest()
                self._last_hash = event.event_hash

            # Add to buffer
            self._buffer.append(event)

            # Trigger alerts for high-severity events
            if severity.value >= self._alert_threshold.value:
                self._trigger_alerts(event)

            return event

    def add_alert_handler(self, handler: Callable[[AuditEvent], None]):
        """Add a handler for alert notifications."""
        self._alert_handlers.append(handler)

    def _trigger_alerts(self, event: AuditEvent):
        """Trigger alert handlers for an event."""
        for handler in self._alert_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Alert handler error: {e}")

    def set_alert_threshold(self, severity: AuditSeverity):
        """Set the minimum severity level for alerts."""
        self._alert_threshold = severity

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        min_severity: Optional[AuditSeverity] = None,
        source_node: Optional[str] = None,
        source_zone: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.

        Args:
            event_type: Filter by event type
            min_severity: Minimum severity level
            source_node: Filter by source node
            source_zone: Filter by source zone
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum events to return

        Returns:
            List of matching AuditEvents
        """
        with self._lock:
            results = []
            for event in reversed(self._buffer):
                if len(results) >= limit:
                    break

                # Apply filters
                if event_type and event.event_type != event_type:
                    continue
                if min_severity and event.severity.value < min_severity.value:
                    continue
                if source_node and event.source_node != source_node:
                    continue
                if source_zone and event.source_zone != source_zone:
                    continue
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue

                results.append(event)

            return results

    def verify_chain_integrity(self) -> tuple[bool, Optional[str]]:
        """
        Verify the integrity of the hash chain.

        Returns:
            Tuple of (valid, error_message)
        """
        if not self._enable_hash_chain:
            return True, None

        with self._lock:
            events = list(self._buffer)

        if not events:
            return True, None

        # Verify chain
        for i, event in enumerate(events):
            # Recompute hash
            event_data = f"{event.event_id}{event.timestamp.isoformat()}{event.source_node}{event.action}{event.previous_hash}"
            computed_hash = hashlib.sha256(event_data.encode()).hexdigest()

            if computed_hash != event.event_hash:
                return False, f"Hash mismatch at event {event.event_id}"

            # Verify chain link
            if i > 0 and event.previous_hash != events[i - 1].event_hash:
                return False, f"Chain break between events {events[i-1].event_id} and {event.event_id}"

        return True, None

    def export_for_siem(self, format: str = "json") -> str:
        """
        Export events for SIEM integration.

        Args:
            format: Export format (json, cef)

        Returns:
            Formatted event data
        """
        with self._lock:
            events = list(self._buffer)

        if format == "json":
            return json.dumps([
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "severity": e.severity.name,
                    "source_node": e.source_node,
                    "source_zone": e.source_zone,
                    "target_resource": e.target_resource,
                    "action": e.action,
                    "outcome": e.outcome,
                    "user_id": e.user_id,
                    "details": e.details,
                    "event_hash": e.event_hash,
                }
                for e in events
            ], indent=2)

        elif format == "cef":
            # Common Event Format for SIEM
            cef_lines = []
            for e in events:
                severity_map = {0: 0, 1: 1, 2: 2, 3: 4, 4: 6, 5: 8, 6: 9, 7: 10}
                cef_severity = severity_map.get(e.severity.value, 5)
                cef_line = (
                    f"CEF:0|LEGO_MCP|SecurityAudit|7.0|{e.event_type.value}|"
                    f"{e.action}|{cef_severity}|"
                    f"src={e.source_node} szone={e.source_zone} "
                    f"dst={e.target_resource} outcome={e.outcome} "
                    f"rt={int(e.timestamp.timestamp() * 1000)}"
                )
                cef_lines.append(cef_line)
            return "\n".join(cef_lines)

        return ""

    def get_statistics(self) -> Dict:
        """Get audit pipeline statistics."""
        with self._lock:
            events = list(self._buffer)

        if not events:
            return {"total_events": 0}

        severity_counts = {}
        type_counts = {}
        zone_counts = {}

        for event in events:
            severity_counts[event.severity.name] = severity_counts.get(event.severity.name, 0) + 1
            type_counts[event.event_type.value] = type_counts.get(event.event_type.value, 0) + 1
            zone_counts[event.source_zone] = zone_counts.get(event.source_zone, 0) + 1

        return {
            "total_events": len(events),
            "oldest_event": events[0].timestamp.isoformat() if events else None,
            "newest_event": events[-1].timestamp.isoformat() if events else None,
            "by_severity": severity_counts,
            "by_type": type_counts,
            "by_zone": zone_counts,
            "chain_valid": self.verify_chain_integrity()[0],
        }

    # Convenience methods for common events

    def log_authentication(
        self,
        source_node: str,
        source_zone: str,
        user_id: str,
        success: bool,
        details: Optional[Dict] = None,
    ):
        """Log an authentication event."""
        self.record_event(
            event_type=AuditEventType.AUTHENTICATION,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            source_node=source_node,
            source_zone=source_zone,
            target_resource="auth_service",
            action="authenticate",
            outcome="SUCCESS" if success else "FAILURE",
            user_id=user_id,
            details=details,
        )

    def log_access_attempt(
        self,
        source_node: str,
        source_zone: str,
        target_resource: str,
        granted: bool,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        """Log an access attempt."""
        self.record_event(
            event_type=AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED,
            severity=AuditSeverity.INFO if granted else AuditSeverity.WARNING,
            source_node=source_node,
            source_zone=source_zone,
            target_resource=target_resource,
            action="access",
            outcome="GRANTED" if granted else "DENIED",
            user_id=user_id,
            details=details,
        )

    def log_estop(
        self,
        source_node: str,
        source_zone: str,
        triggered: bool,
        reason: str,
        user_id: Optional[str] = None,
    ):
        """Log an e-stop event."""
        self.record_event(
            event_type=AuditEventType.ESTOP_TRIGGERED if triggered else AuditEventType.ESTOP_RESET,
            severity=AuditSeverity.ALERT if triggered else AuditSeverity.NOTICE,
            source_node=source_node,
            source_zone=source_zone,
            target_resource="safety_system",
            action="estop_trigger" if triggered else "estop_reset",
            outcome="ACTIVATED" if triggered else "DEACTIVATED",
            user_id=user_id,
            details={"reason": reason},
        )

    def log_security_incident(
        self,
        source_node: str,
        source_zone: str,
        incident_type: str,
        description: str,
        severity: AuditSeverity = AuditSeverity.ERROR,
        details: Optional[Dict] = None,
    ):
        """Log a security incident."""
        self.record_event(
            event_type=AuditEventType.SECURITY_INCIDENT,
            severity=severity,
            source_node=source_node,
            source_zone=source_zone,
            target_resource="security_system",
            action=incident_type,
            outcome="DETECTED",
            details={"description": description, **(details or {})},
        )
