"""
Compliance Audit Logger

Implements comprehensive audit logging for DoD/federal
compliance requirements.

Reference: NIST 800-92, NIST 800-171 AU family, DFARS 252.204-7012
"""

import logging
import json
import hashlib
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
from queue import Queue
import os

logger = logging.getLogger(__name__)


class AuditSeverity(Enum):
    """Audit event severity levels (aligned with syslog)."""
    EMERGENCY = 0    # System is unusable
    ALERT = 1        # Action must be taken immediately
    CRITICAL = 2     # Critical conditions
    ERROR = 3        # Error conditions
    WARNING = 4      # Warning conditions
    NOTICE = 5       # Normal but significant
    INFO = 6         # Informational
    DEBUG = 7        # Debug-level


class AuditCategory(Enum):
    """Audit event categories per NIST 800-53 AU-2."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ACCESS = "access"
    MODIFICATION = "modification"
    DELETION = "deletion"
    PRIVILEGED = "privileged"
    SYSTEM = "system"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    CUI = "cui"
    INCIDENT = "incident"
    CONFIGURATION = "configuration"


class AuditOutcome(Enum):
    """Audit event outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass
class AuditEvent:
    """
    Audit Event Record.
    
    Conforms to:
    - NIST 800-92 Log Management
    - NIST 800-171 3.3 (Audit and Accountability)
    - Common Event Format (CEF)
    """
    event_id: str
    timestamp: str
    category: AuditCategory
    severity: AuditSeverity
    outcome: AuditOutcome
    
    # Actor information
    user_id: str = ""
    user_name: str = ""
    user_role: str = ""
    
    # Action information
    action: str = ""
    resource_type: str = ""
    resource_id: str = ""
    
    # Context
    source_ip: str = ""
    source_host: str = ""
    target_system: str = ""
    session_id: str = ""
    
    # Details
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Compliance markers
    cui_involved: bool = False
    cui_categories: List[str] = field(default_factory=list)
    nist_controls: List[str] = field(default_factory=list)
    
    # Integrity
    hash_value: Optional[str] = None
    previous_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "severity": self.severity.value,
            "outcome": self.outcome.value,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_role": self.user_role,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "source_ip": self.source_ip,
            "source_host": self.source_host,
            "target_system": self.target_system,
            "session_id": self.session_id,
            "description": self.description,
            "details": self.details,
            "cui_involved": self.cui_involved,
            "cui_categories": self.cui_categories,
            "nist_controls": self.nist_controls,
            "hash": self.hash_value
        }

    def to_cef(self) -> str:
        """Convert to Common Event Format (CEF)."""
        # CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension
        severity_map = {
            AuditSeverity.EMERGENCY: 10,
            AuditSeverity.ALERT: 9,
            AuditSeverity.CRITICAL: 8,
            AuditSeverity.ERROR: 7,
            AuditSeverity.WARNING: 5,
            AuditSeverity.NOTICE: 4,
            AuditSeverity.INFO: 3,
            AuditSeverity.DEBUG: 1
        }
        
        extensions = [
            f"rt={self.timestamp}",
            f"suser={self.user_id}",
            f"src={self.source_ip}",
            f"outcome={self.outcome.value}",
            f"msg={self.description}"
        ]
        
        return (
            f"CEF:0|LEGO MCP|Manufacturing|1.0|"
            f"{self.category.value}|{self.action}|"
            f"{severity_map.get(self.severity, 5)}|"
            f"{' '.join(extensions)}"
        )

    def compute_hash(self, previous_hash: str = "") -> str:
        """Compute cryptographic hash for integrity chain."""
        content = json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "action": self.action,
            "user_id": self.user_id,
            "outcome": self.outcome.value,
            "previous_hash": previous_hash
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class AuditChain:
    """Tamper-evident audit log chain."""
    chain_id: str
    events: List[AuditEvent] = field(default_factory=list)
    genesis_hash: str = ""
    current_hash: str = ""
    
    def add_event(self, event: AuditEvent) -> None:
        """Add event to chain with hash linking."""
        event.previous_hash = self.current_hash
        event.hash_value = event.compute_hash(self.current_hash)
        self.current_hash = event.hash_value
        self.events.append(event)

    def verify_integrity(self) -> bool:
        """Verify chain integrity."""
        if not self.events:
            return True
            
        prev_hash = self.genesis_hash
        for event in self.events:
            computed = event.compute_hash(prev_hash)
            if computed != event.hash_value:
                return False
            prev_hash = event.hash_value
        return True


class ComplianceAuditLogger:
    """
    Compliance-Grade Audit Logger.

    Implements NIST 800-171 AU family requirements:
    - AU.L2-3.3.1: Create audit logs
    - AU.L2-3.3.2: Unique user identification
    - AU.L2-3.3.4: Alert on audit failure
    - AU.L2-3.3.5: Correlate audit records

    Usage:
        >>> audit = ComplianceAuditLogger()
        >>> audit.log_authentication("user123", success=True)
        >>> audit.log_cui_access("user123", "doc456", granted=True)
    """

    def __init__(
        self,
        system_name: str = "LEGO MCP Manufacturing",
        log_path: Optional[str] = None,
        chain_enabled: bool = True
    ):
        self.system_name = system_name
        self.log_path = log_path or "/var/log/lego_mcp/audit.log"
        self.chain_enabled = chain_enabled
        
        # Event chain for tamper detection
        self.chain = AuditChain(
            chain_id=hashlib.sha256(
                f"{system_name}{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16],
            genesis_hash=hashlib.sha256(b"GENESIS").hexdigest()
        )
        self.chain.current_hash = self.chain.genesis_hash
        
        # Event queue for async processing
        self._event_queue: Queue = Queue()
        self._event_counter = 0
        self._lock = threading.Lock()
        
        # Alert handlers
        self._alert_handlers: List[Callable[[AuditEvent], None]] = []
        
        logger.info(f"ComplianceAuditLogger initialized for {system_name}")

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        with self._lock:
            self._event_counter += 1
            return f"EVT-{datetime.utcnow().strftime('%Y%m%d')}-{self._event_counter:08d}"

    def log_event(
        self,
        category: AuditCategory,
        action: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        user_id: str = "",
        resource_type: str = "",
        resource_id: str = "",
        description: str = "",
        details: Optional[Dict[str, Any]] = None,
        cui_involved: bool = False,
        cui_categories: Optional[List[str]] = None,
        nist_controls: Optional[List[str]] = None,
        source_ip: str = "",
        session_id: str = ""
    ) -> AuditEvent:
        """Log an audit event."""
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            category=category,
            severity=severity,
            outcome=outcome,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            source_ip=source_ip,
            session_id=session_id,
            target_system=self.system_name,
            description=description,
            details=details or {},
            cui_involved=cui_involved,
            cui_categories=cui_categories or [],
            nist_controls=nist_controls or []
        )

        # Add to tamper-evident chain
        if self.chain_enabled:
            self.chain.add_event(event)

        # Write to log
        self._write_event(event)

        # Check for alerts
        if severity.value <= AuditSeverity.WARNING.value:
            self._trigger_alerts(event)

        logger.debug(f"Audit event logged: {event.event_id}")
        return event

    def log_authentication(
        self,
        user_id: str,
        success: bool,
        method: str = "password",
        mfa_used: bool = False,
        source_ip: str = "",
        failure_reason: str = ""
    ) -> AuditEvent:
        """Log authentication attempt (NIST 3.5.1, 3.5.2)."""
        return self.log_event(
            category=AuditCategory.AUTHENTICATION,
            action=f"login_{method}",
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            user_id=user_id,
            source_ip=source_ip,
            description=f"Authentication {'successful' if success else 'failed'}: {user_id}",
            details={
                "method": method,
                "mfa_used": mfa_used,
                "failure_reason": failure_reason if not success else None
            },
            nist_controls=["3.5.1", "3.5.2", "3.5.3"] if mfa_used else ["3.5.1", "3.5.2"]
        )

    def log_authorization(
        self,
        user_id: str,
        resource: str,
        action: str,
        granted: bool,
        reason: str = ""
    ) -> AuditEvent:
        """Log authorization decision (NIST 3.1.1, 3.1.2)."""
        return self.log_event(
            category=AuditCategory.AUTHORIZATION,
            action=f"authorize_{action}",
            severity=AuditSeverity.INFO if granted else AuditSeverity.WARNING,
            outcome=AuditOutcome.SUCCESS if granted else AuditOutcome.FAILURE,
            user_id=user_id,
            resource_type="permission",
            resource_id=resource,
            description=f"Authorization {'granted' if granted else 'denied'}: {action} on {resource}",
            details={"reason": reason},
            nist_controls=["3.1.1", "3.1.2"]
        )

    def log_cui_access(
        self,
        user_id: str,
        document_id: str,
        action: str,
        granted: bool,
        cui_categories: List[str],
        reason: str = ""
    ) -> AuditEvent:
        """Log CUI access attempt (NIST 3.1.3, 3.3.1)."""
        return self.log_event(
            category=AuditCategory.CUI,
            action=f"cui_{action}",
            severity=AuditSeverity.NOTICE if granted else AuditSeverity.WARNING,
            outcome=AuditOutcome.SUCCESS if granted else AuditOutcome.FAILURE,
            user_id=user_id,
            resource_type="cui_document",
            resource_id=document_id,
            description=f"CUI access {'granted' if granted else 'denied'}: {document_id}",
            details={"reason": reason},
            cui_involved=True,
            cui_categories=cui_categories,
            nist_controls=["3.1.3", "3.3.1", "3.3.2"]
        )

    def log_privileged_action(
        self,
        user_id: str,
        action: str,
        target: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Log privileged operation (NIST 3.1.7)."""
        return self.log_event(
            category=AuditCategory.PRIVILEGED,
            action=f"privileged_{action}",
            severity=AuditSeverity.NOTICE,
            outcome=AuditOutcome.SUCCESS if success else AuditOutcome.FAILURE,
            user_id=user_id,
            resource_type="system",
            resource_id=target,
            description=f"Privileged action: {action} on {target}",
            details=details or {},
            nist_controls=["3.1.7", "3.3.1", "3.3.2"]
        )

    def log_configuration_change(
        self,
        user_id: str,
        config_type: str,
        change: str,
        old_value: Any = None,
        new_value: Any = None
    ) -> AuditEvent:
        """Log configuration change (NIST 3.4.1, 3.4.2)."""
        return self.log_event(
            category=AuditCategory.CONFIGURATION,
            action="config_change",
            severity=AuditSeverity.NOTICE,
            outcome=AuditOutcome.SUCCESS,
            user_id=user_id,
            resource_type="configuration",
            resource_id=config_type,
            description=f"Configuration changed: {change}",
            details={
                "change": change,
                "old_value": str(old_value) if old_value else None,
                "new_value": str(new_value) if new_value else None
            },
            nist_controls=["3.4.1", "3.4.2"]
        )

    def log_security_incident(
        self,
        incident_type: str,
        description: str,
        severity: AuditSeverity = AuditSeverity.ALERT,
        affected_systems: Optional[List[str]] = None,
        indicators: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """Log security incident (NIST 3.6.1, 3.6.2)."""
        return self.log_event(
            category=AuditCategory.INCIDENT,
            action=f"incident_{incident_type}",
            severity=severity,
            outcome=AuditOutcome.UNKNOWN,
            description=description,
            details={
                "incident_type": incident_type,
                "affected_systems": affected_systems or [],
                "indicators": indicators or {}
            },
            nist_controls=["3.6.1", "3.6.2"]
        )

    def log_data_modification(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        operation: str,
        cui_involved: bool = False
    ) -> AuditEvent:
        """Log data modification (NIST 3.3.1)."""
        return self.log_event(
            category=AuditCategory.MODIFICATION,
            action=f"modify_{operation}",
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            description=f"Data modified: {operation} on {resource_type}/{resource_id}",
            cui_involved=cui_involved,
            nist_controls=["3.3.1", "3.3.2"]
        )

    def _write_event(self, event: AuditEvent) -> None:
        """Write event to audit log file."""
        try:
            # Ensure directory exists
            log_dir = os.path.dirname(self.log_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            with open(self.log_path, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            # Audit failure - this is critical (NIST 3.3.4)
            logger.error(f"AUDIT FAILURE: Unable to write audit log: {e}")
            self._handle_audit_failure(event, str(e))

    def _handle_audit_failure(self, event: AuditEvent, error: str) -> None:
        """Handle audit logging failure (NIST 3.3.4)."""
        # This is a critical security event
        for handler in self._alert_handlers:
            try:
                failure_event = AuditEvent(
                    event_id=self._generate_event_id(),
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    category=AuditCategory.SYSTEM,
                    severity=AuditSeverity.ALERT,
                    outcome=AuditOutcome.FAILURE,
                    action="audit_failure",
                    description=f"Audit logging failure: {error}",
                    details={"original_event": event.event_id}
                )
                handler(failure_event)
            except Exception:
                pass

    def _trigger_alerts(self, event: AuditEvent) -> None:
        """Trigger alert handlers for significant events."""
        for handler in self._alert_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def register_alert_handler(
        self,
        handler: Callable[[AuditEvent], None]
    ) -> None:
        """Register an alert handler for security events."""
        self._alert_handlers.append(handler)

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify audit log chain integrity."""
        if not self.chain_enabled:
            return {"enabled": False}

        is_valid = self.chain.verify_integrity()
        
        return {
            "enabled": True,
            "chain_id": self.chain.chain_id,
            "event_count": len(self.chain.events),
            "genesis_hash": self.chain.genesis_hash,
            "current_hash": self.chain.current_hash,
            "integrity_valid": is_valid,
            "verified_at": datetime.utcnow().isoformat() + "Z"
        }

    def generate_compliance_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        nist_controls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate compliance audit report."""
        events = self.chain.events

        if start_date:
            events = [e for e in events if e.timestamp >= start_date]
        if end_date:
            events = [e for e in events if e.timestamp <= end_date]
        if nist_controls:
            events = [
                e for e in events
                if any(c in e.nist_controls for c in nist_controls)
            ]

        # Categorize events
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_outcome: Dict[str, int] = {}
        cui_events = 0

        for event in events:
            by_category[event.category.value] = by_category.get(event.category.value, 0) + 1
            by_severity[event.severity.name] = by_severity.get(event.severity.name, 0) + 1
            by_outcome[event.outcome.value] = by_outcome.get(event.outcome.value, 0) + 1
            if event.cui_involved:
                cui_events += 1

        return {
            "report_type": "Compliance Audit Report",
            "generated": datetime.utcnow().isoformat() + "Z",
            "period": {
                "start": start_date or "beginning",
                "end": end_date or "present"
            },
            "system": self.system_name,
            "chain_integrity": self.verify_chain_integrity(),
            "summary": {
                "total_events": len(events),
                "by_category": by_category,
                "by_severity": by_severity,
                "by_outcome": by_outcome,
                "cui_events": cui_events
            },
            "nist_coverage": self._calculate_nist_coverage(events),
            "high_severity_events": [
                e.to_dict() for e in events
                if e.severity.value <= AuditSeverity.WARNING.value
            ][:100]  # Limit to 100
        }

    def _calculate_nist_coverage(
        self,
        events: List[AuditEvent]
    ) -> Dict[str, int]:
        """Calculate NIST control coverage from audit events."""
        coverage: Dict[str, int] = {}
        for event in events:
            for control in event.nist_controls:
                coverage[control] = coverage.get(control, 0) + 1
        return coverage

    # ====================================================
    # V8 Command Center Integration
    # ====================================================

    def log_command_center_action(
        self,
        user_id: str,
        action_id: str,
        action_type: str,
        target: str,
        parameters: Dict[str, Any],
        approved: bool,
        approver: Optional[str] = None
    ) -> AuditEvent:
        """Log command center action for compliance tracking."""
        return self.log_event(
            category=AuditCategory.PRIVILEGED,
            action=f"command_center_{action_type}",
            severity=AuditSeverity.NOTICE,
            outcome=AuditOutcome.SUCCESS if approved else AuditOutcome.FAILURE,
            user_id=user_id,
            resource_type="command_center_action",
            resource_id=action_id,
            description=f"Command Center action: {action_type} on {target}",
            details={
                "action_type": action_type,
                "target": target,
                "parameters": parameters,
                "approved": approved,
                "approver": approver
            },
            nist_controls=["3.1.7", "3.3.1", "3.3.2"]
        )

    def log_decision_workflow(
        self,
        user_id: str,
        decision_id: str,
        decision_type: str,
        outcome: str,
        risk_level: str,
        rationale: str = ""
    ) -> AuditEvent:
        """Log AI decision workflow for algorithm-to-action pipeline."""
        severity_map = {
            "low": AuditSeverity.INFO,
            "medium": AuditSeverity.NOTICE,
            "high": AuditSeverity.WARNING,
            "critical": AuditSeverity.ALERT
        }
        return self.log_event(
            category=AuditCategory.COMPLIANCE,
            action=f"decision_{outcome}",
            severity=severity_map.get(risk_level, AuditSeverity.NOTICE),
            outcome=AuditOutcome.SUCCESS if outcome == "approved" else AuditOutcome.FAILURE,
            user_id=user_id,
            resource_type="ai_decision",
            resource_id=decision_id,
            description=f"Decision {outcome}: {decision_type} (risk: {risk_level})",
            details={
                "decision_type": decision_type,
                "outcome": outcome,
                "risk_level": risk_level,
                "rationale": rationale
            },
            nist_controls=["3.3.1", "3.3.2", "3.3.5"]
        )

    def log_cosimulation_run(
        self,
        user_id: str,
        simulation_id: str,
        mode: str,
        config: Dict[str, Any],
        started: bool = True
    ) -> AuditEvent:
        """Log co-simulation run for traceability."""
        return self.log_event(
            category=AuditCategory.SYSTEM,
            action=f"cosim_{'started' if started else 'completed'}",
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            user_id=user_id,
            resource_type="cosimulation",
            resource_id=simulation_id,
            description=f"Co-simulation {mode} {'started' if started else 'completed'}",
            details={
                "mode": mode,
                "config": config,
                "status": "running" if started else "completed"
            },
            nist_controls=["3.3.1"]
        )

    def log_alert_action(
        self,
        user_id: str,
        alert_id: str,
        action: str,
        severity: str,
        source: str
    ) -> AuditEvent:
        """Log alert acknowledgment or resolution."""
        return self.log_event(
            category=AuditCategory.SECURITY if source == "security" else AuditCategory.SYSTEM,
            action=f"alert_{action}",
            severity=AuditSeverity.WARNING if severity in ["critical", "high"] else AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            user_id=user_id,
            resource_type="alert",
            resource_id=alert_id,
            description=f"Alert {action}: {alert_id} ({severity})",
            details={
                "alert_action": action,
                "alert_severity": severity,
                "alert_source": source
            },
            nist_controls=["3.6.1", "3.6.2"]
        )

    def log_equipment_control(
        self,
        user_id: str,
        equipment_id: str,
        action: str,
        parameters: Dict[str, Any],
        source: str = "manual"
    ) -> AuditEvent:
        """Log equipment control action from command center."""
        return self.log_event(
            category=AuditCategory.PRIVILEGED,
            action=f"equipment_{action}",
            severity=AuditSeverity.NOTICE,
            outcome=AuditOutcome.SUCCESS,
            user_id=user_id,
            resource_type="equipment",
            resource_id=equipment_id,
            description=f"Equipment control: {action} on {equipment_id}",
            details={
                "action": action,
                "parameters": parameters,
                "source": source
            },
            nist_controls=["3.1.7", "3.3.1", "3.4.5"]
        )

    def get_recent_events(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Get recent audit events for dashboard display."""
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        events = [e for e in self.chain.events if e.timestamp >= cutoff]
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]

    def get_events_by_user(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[AuditEvent]:
        """Get audit events for a specific user."""
        events = [e for e in self.chain.events if e.user_id == user_id]
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]

    def get_compliance_dashboard_data(self) -> Dict[str, Any]:
        """Get audit data formatted for compliance dashboard."""
        from datetime import timedelta
        now = datetime.utcnow()
        day_ago = (now - timedelta(days=1)).isoformat() + "Z"
        week_ago = (now - timedelta(days=7)).isoformat() + "Z"

        recent_24h = [e for e in self.chain.events if e.timestamp >= day_ago]
        recent_7d = [e for e in self.chain.events if e.timestamp >= week_ago]

        # Count security events
        security_events = [
            e for e in recent_24h
            if e.category == AuditCategory.SECURITY
            or e.severity.value <= AuditSeverity.WARNING.value
        ]

        return {
            "total_events_24h": len(recent_24h),
            "total_events_7d": len(recent_7d),
            "security_events_24h": len(security_events),
            "chain_integrity": self.verify_chain_integrity(),
            "cui_events_24h": len([e for e in recent_24h if e.cui_involved]),
            "by_category": {
                cat.value: len([e for e in recent_24h if e.category == cat])
                for cat in AuditCategory
            },
            "by_severity": {
                sev.name: len([e for e in recent_24h if e.severity == sev])
                for sev in AuditSeverity
            },
            "recent_high_severity": [
                e.to_dict() for e in recent_24h
                if e.severity.value <= AuditSeverity.WARNING.value
            ][:10]
        }


# Singleton instance
_audit_logger_instance: Optional[ComplianceAuditLogger] = None
_audit_lock = threading.Lock()


def get_audit_logger(
    system_name: str = "LEGO MCP Manufacturing"
) -> ComplianceAuditLogger:
    """Get singleton audit logger instance."""
    global _audit_logger_instance
    with _audit_lock:
        if _audit_logger_instance is None:
            _audit_logger_instance = ComplianceAuditLogger(system_name=system_name)
        return _audit_logger_instance


# Convenience functions for V8 command center
def audit_action(
    user_id: str,
    action_id: str,
    action_type: str,
    target: str,
    parameters: Dict[str, Any],
    approved: bool,
    approver: Optional[str] = None
) -> AuditEvent:
    """Convenience function to audit command center actions."""
    return get_audit_logger().log_command_center_action(
        user_id=user_id,
        action_id=action_id,
        action_type=action_type,
        target=target,
        parameters=parameters,
        approved=approved,
        approver=approver
    )


def audit_decision(
    user_id: str,
    decision_id: str,
    decision_type: str,
    outcome: str,
    risk_level: str,
    rationale: str = ""
) -> AuditEvent:
    """Convenience function to audit decision workflows."""
    return get_audit_logger().log_decision_workflow(
        user_id=user_id,
        decision_id=decision_id,
        decision_type=decision_type,
        outcome=outcome,
        risk_level=risk_level,
        rationale=rationale
    )


def audit_alert(
    user_id: str,
    alert_id: str,
    action: str,
    severity: str,
    source: str
) -> AuditEvent:
    """Convenience function to audit alert actions."""
    return get_audit_logger().log_alert_action(
        user_id=user_id,
        alert_id=alert_id,
        action=action,
        severity=severity,
        source=source
    )
