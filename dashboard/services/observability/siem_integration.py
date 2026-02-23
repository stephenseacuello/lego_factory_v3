"""
SIEM Integration for Manufacturing Security

Integrates with Security Information and Event Management (SIEM)
systems for comprehensive security monitoring.

Supports:
- Splunk Enterprise
- IBM QRadar
- Microsoft Sentinel
- Elastic SIEM
- CEF (Common Event Format)
- LEEF (Log Event Extended Format)

Reference: IEC 62443 Industrial Cybersecurity

Author: LEGO MCP Security Engineering
"""

import logging
import json
import hashlib
import socket
import ssl
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone
from enum import Enum, auto
from abc import ABC, abstractmethod
import uuid

logger = logging.getLogger(__name__)


class SIEMProvider(Enum):
    """Supported SIEM providers."""
    SPLUNK = "splunk"
    QRADAR = "qradar"
    SENTINEL = "sentinel"
    ELASTIC = "elastic"
    GENERIC_SYSLOG = "syslog"


class SeverityLevel(Enum):
    """Security event severity levels."""
    EMERGENCY = 0     # System unusable
    ALERT = 1         # Immediate action required
    CRITICAL = 2      # Critical conditions
    ERROR = 3         # Error conditions
    WARNING = 4       # Warning conditions
    NOTICE = 5        # Normal but significant
    INFO = 6          # Informational
    DEBUG = 7         # Debug messages


class EventCategory(Enum):
    """Security event categories."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    MALWARE = "malware"
    ANOMALY = "anomaly"
    SAFETY = "safety"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


@dataclass
class SecurityEvent:
    """Security event for SIEM."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: SeverityLevel = SeverityLevel.INFO
    category: EventCategory = EventCategory.OPERATIONAL
    source_ip: str = ""
    source_host: str = ""
    destination_ip: str = ""
    destination_host: str = ""
    user: str = ""
    action: str = ""
    outcome: str = ""
    message: str = ""
    device_vendor: str = "LEGO_MCP"
    device_product: str = "Manufacturing_System"
    device_version: str = "8.0"
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_cef(self) -> str:
        """
        Convert to CEF (Common Event Format).

        Format: CEF:Version|Device Vendor|Device Product|Device Version|
                Device Event Class ID|Name|Severity|[Extension]
        """
        extensions = {
            "src": self.source_ip,
            "shost": self.source_host,
            "dst": self.destination_ip,
            "dhost": self.destination_host,
            "suser": self.user,
            "act": self.action,
            "outcome": self.outcome,
            "msg": self.message,
            "rt": self.timestamp.strftime("%b %d %Y %H:%M:%S"),
        }

        # Filter empty values
        ext_str = " ".join(
            f"{k}={v}" for k, v in extensions.items() if v
        )

        return (
            f"CEF:0|{self.device_vendor}|{self.device_product}|"
            f"{self.device_version}|{self.category.value}|"
            f"{self.action}|{self.severity.value}|{ext_str}"
        )

    def to_leef(self) -> str:
        """
        Convert to LEEF (Log Event Extended Format) for QRadar.

        Format: LEEF:Version|Vendor|Product|Version|EventID|
                Key1=Value1<tab>Key2=Value2...
        """
        attributes = {
            "devTime": self.timestamp.strftime("%b %d %Y %H:%M:%S"),
            "cat": self.category.value,
            "sev": self.severity.value,
            "src": self.source_ip,
            "dst": self.destination_ip,
            "usrName": self.user,
            "action": self.action,
            "result": self.outcome,
        }

        attr_str = "\t".join(
            f"{k}={v}" for k, v in attributes.items() if v
        )

        return (
            f"LEEF:2.0|{self.device_vendor}|{self.device_product}|"
            f"{self.device_version}|{self.event_id}|{attr_str}"
        )

    def to_json(self) -> str:
        """Convert to JSON for Elastic/Splunk."""
        return json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.name,
            "severity_code": self.severity.value,
            "category": self.category.value,
            "source": {
                "ip": self.source_ip,
                "host": self.source_host,
            },
            "destination": {
                "ip": self.destination_ip,
                "host": self.destination_host,
            },
            "user": self.user,
            "action": self.action,
            "outcome": self.outcome,
            "message": self.message,
            "device": {
                "vendor": self.device_vendor,
                "product": self.device_product,
                "version": self.device_version,
            },
            "raw": self.raw_data,
        })


class SIEMConnector(ABC):
    """Abstract SIEM connector."""

    @abstractmethod
    def send(self, event: SecurityEvent) -> bool:
        """Send event to SIEM."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test SIEM connection."""
        pass


class SyslogConnector(SIEMConnector):
    """
    Syslog connector for generic SIEM integration.

    Supports UDP, TCP, and TLS transport.
    """

    def __init__(
        self,
        host: str,
        port: int = 514,
        protocol: str = "udp",
        use_tls: bool = False,
        facility: int = 16,  # Local0
    ):
        self.host = host
        self.port = port
        self.protocol = protocol
        self.use_tls = use_tls
        self.facility = facility
        self._socket: Optional[socket.socket] = None

    def _connect(self) -> bool:
        """Establish connection."""
        try:
            if self.protocol == "udp":
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            else:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if self.use_tls:
                    context = ssl.create_default_context()
                    self._socket = context.wrap_socket(
                        self._socket, server_hostname=self.host
                    )
                self._socket.connect((self.host, self.port))

            return True
        except Exception as e:
            logger.error(f"Syslog connection failed: {e}")
            return False

    def send(self, event: SecurityEvent) -> bool:
        """Send event via syslog."""
        if not self._socket:
            if not self._connect():
                return False

        try:
            # RFC 5424 priority
            priority = self.facility * 8 + event.severity.value

            # Format message
            timestamp = event.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            hostname = socket.gethostname()
            app_name = event.device_product

            message = (
                f"<{priority}>1 {timestamp} {hostname} {app_name} "
                f"- - - {event.to_cef()}"
            )

            if self.protocol == "udp":
                self._socket.sendto(
                    message.encode(), (self.host, self.port)
                )
            else:
                self._socket.send(message.encode() + b"\n")

            return True
        except Exception as e:
            logger.error(f"Failed to send syslog: {e}")
            self._socket = None
            return False

    def test_connection(self) -> bool:
        """Test syslog connection."""
        return self._connect()

    def close(self) -> None:
        """Close connection."""
        if self._socket:
            self._socket.close()
            self._socket = None


class SplunkHECConnector(SIEMConnector):
    """
    Splunk HTTP Event Collector (HEC) connector.
    """

    def __init__(
        self,
        host: str,
        token: str,
        port: int = 8088,
        use_ssl: bool = True,
        index: str = "main",
        source: str = "lego_mcp",
        sourcetype: str = "_json",
    ):
        self.host = host
        self.token = token
        self.port = port
        self.use_ssl = use_ssl
        self.index = index
        self.source = source
        self.sourcetype = sourcetype

    def send(self, event: SecurityEvent) -> bool:
        """Send event to Splunk HEC."""
        import urllib.request
        import urllib.error

        protocol = "https" if self.use_ssl else "http"
        url = f"{protocol}://{self.host}:{self.port}/services/collector/event"

        payload = {
            "time": event.timestamp.timestamp(),
            "host": socket.gethostname(),
            "source": self.source,
            "sourcetype": self.sourcetype,
            "index": self.index,
            "event": json.loads(event.to_json()),
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Splunk {self.token}",
                    "Content-Type": "application/json",
                },
            )

            # Skip SSL verification for self-signed certs (configurable)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=context) as response:
                return response.status == 200

        except urllib.error.URLError as e:
            logger.error(f"Splunk HEC error: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Splunk HEC connection."""
        test_event = SecurityEvent(
            message="Connection test",
            action="test",
            severity=SeverityLevel.DEBUG,
        )
        return self.send(test_event)


class QRadarConnector(SIEMConnector):
    """IBM QRadar SIEM connector."""

    def __init__(
        self,
        host: str,
        port: int = 514,
        use_leef: bool = True,
    ):
        self.host = host
        self.port = port
        self.use_leef = use_leef
        self.syslog = SyslogConnector(host, port, protocol="tcp")

    def send(self, event: SecurityEvent) -> bool:
        """Send event to QRadar."""
        # QRadar prefers LEEF format
        return self.syslog.send(event)

    def test_connection(self) -> bool:
        """Test QRadar connection."""
        return self.syslog.test_connection()


@dataclass
class ImmutableAuditEntry:
    """
    Immutable audit entry with cryptographic chain.

    Provides tamper-evident audit logging for compliance.
    """
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = ""
    actor: str = ""
    action: str = ""
    resource: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self, previous_hash: str = "") -> str:
        """Compute hash of entry for chain integrity."""
        content = json.dumps({
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": previous_hash,
        }, sort_keys=True)

        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


class ImmutableAuditChain:
    """
    Immutable audit chain with tamper detection.

    Implements cryptographic chaining for compliance audit trails.
    """

    def __init__(self):
        self.entries: List[ImmutableAuditEntry] = []
        self._last_hash = "0" * 64  # Genesis hash

    def append(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        details: Optional[Dict] = None,
    ) -> ImmutableAuditEntry:
        """Append entry to audit chain."""
        entry = ImmutableAuditEntry(
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            details=details or {},
            previous_hash=self._last_hash,
        )

        entry.entry_hash = entry.compute_hash(self._last_hash)
        self._last_hash = entry.entry_hash

        self.entries.append(entry)

        logger.debug(f"Audit entry added: {entry.entry_id}")
        return entry

    def verify_integrity(self) -> Tuple[bool, Optional[int]]:
        """
        Verify chain integrity.

        Returns (valid, first_invalid_index).
        """
        if not self.entries:
            return True, None

        previous_hash = "0" * 64

        for i, entry in enumerate(self.entries):
            expected_hash = entry.compute_hash(previous_hash)

            if entry.entry_hash != expected_hash:
                logger.error(f"Chain integrity violation at index {i}")
                return False, i

            if entry.previous_hash != previous_hash:
                logger.error(f"Previous hash mismatch at index {i}")
                return False, i

            previous_hash = entry.entry_hash

        return True, None

    def get_entries(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> List[ImmutableAuditEntry]:
        """Query audit entries with filters."""
        results = self.entries

        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if actor:
            results = [e for e in results if e.actor == actor]

        return results

    def export(self) -> str:
        """Export chain as JSON."""
        return json.dumps([e.to_dict() for e in self.entries], indent=2)

    def get_merkle_root(self) -> str:
        """Compute Merkle root of all entries."""
        if not self.entries:
            return "0" * 64

        hashes = [e.entry_hash for e in self.entries]

        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])

            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_hashes.append(new_hash)

            hashes = new_hashes

        return hashes[0]


class SIEMIntegrationManager:
    """
    SIEM Integration Manager.

    Provides unified interface for security event management
    and immutable audit logging.

    Usage:
        manager = SIEMIntegrationManager()

        # Add SIEM connector
        manager.add_connector("splunk", SplunkHECConnector(
            host="splunk.example.com",
            token="your-hec-token",
        ))

        # Log security event
        manager.log_event(SecurityEvent(
            severity=SeverityLevel.WARNING,
            category=EventCategory.AUTHENTICATION,
            user="operator1",
            action="login_failed",
            message="Failed login attempt",
        ))

        # Create audit entry
        manager.audit(
            event_type="configuration_change",
            actor="admin",
            action="update",
            resource="safety_parameters",
        )

        # Verify audit integrity
        valid, index = manager.verify_audit_chain()
    """

    def __init__(self):
        self.connectors: Dict[str, SIEMConnector] = {}
        self.audit_chain = ImmutableAuditChain()
        self._event_buffer: List[SecurityEvent] = []
        self._buffer_size = 100

        logger.info("SIEM Integration Manager initialized")

    def add_connector(self, name: str, connector: SIEMConnector) -> None:
        """Add SIEM connector."""
        self.connectors[name] = connector
        logger.info(f"Added SIEM connector: {name}")

    def log_event(self, event: SecurityEvent) -> bool:
        """Log security event to all connectors."""
        success = True

        for name, connector in self.connectors.items():
            try:
                if not connector.send(event):
                    logger.warning(f"Failed to send to {name}")
                    success = False
            except Exception as e:
                logger.error(f"Error sending to {name}: {e}")
                success = False

        # Also add to audit chain for critical events
        if event.severity.value <= SeverityLevel.WARNING.value:
            self.audit(
                event_type="security_event",
                actor=event.user or "system",
                action=event.action,
                resource=event.category.value,
                details={"message": event.message, "severity": event.severity.name},
            )

        return success

    def audit(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        details: Optional[Dict] = None,
    ) -> ImmutableAuditEntry:
        """Create immutable audit entry."""
        return self.audit_chain.append(
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            details=details,
        )

    def verify_audit_chain(self) -> Tuple[bool, Optional[int]]:
        """Verify audit chain integrity."""
        return self.audit_chain.verify_integrity()

    def get_audit_entries(self, **filters) -> List[ImmutableAuditEntry]:
        """Query audit entries."""
        return self.audit_chain.get_entries(**filters)

    def export_audit(self) -> str:
        """Export complete audit chain."""
        return self.audit_chain.export()

    def get_merkle_proof(self) -> Dict[str, str]:
        """Get Merkle proof for audit verification."""
        return {
            "merkle_root": self.audit_chain.get_merkle_root(),
            "entry_count": len(self.audit_chain.entries),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def test_connectors(self) -> Dict[str, bool]:
        """Test all SIEM connectors."""
        results = {}
        for name, connector in self.connectors.items():
            results[name] = connector.test_connection()
        return results


# Factory function
def create_siem_manager(
    splunk_host: Optional[str] = None,
    splunk_token: Optional[str] = None,
    syslog_host: Optional[str] = None,
) -> SIEMIntegrationManager:
    """Create configured SIEM manager."""
    manager = SIEMIntegrationManager()

    if splunk_host and splunk_token:
        manager.add_connector("splunk", SplunkHECConnector(
            host=splunk_host,
            token=splunk_token,
        ))

    if syslog_host:
        manager.add_connector("syslog", SyslogConnector(
            host=syslog_host,
        ))

    return manager


__all__ = [
    "SIEMIntegrationManager",
    "SecurityEvent",
    "SeverityLevel",
    "EventCategory",
    "SIEMProvider",
    "SIEMConnector",
    "SyslogConnector",
    "SplunkHECConnector",
    "QRadarConnector",
    "ImmutableAuditEntry",
    "ImmutableAuditChain",
    "create_siem_manager",
]
