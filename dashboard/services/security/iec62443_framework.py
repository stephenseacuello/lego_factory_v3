"""
IEC 62443 Industrial Cybersecurity Framework.

Implements comprehensive cybersecurity for industrial automation and
control systems (IACS) compliant with:
- IEC 62443 (Industrial Automation and Control Systems Security)
- NIST Cybersecurity Framework
- ISO 27001 (Information Security Management)
- NERC CIP (Critical Infrastructure Protection)
- Zero Trust Architecture principles

Features:
- Zone and conduit security model
- Security Level (SL) target management
- Risk assessment and threat modeling
- Access control and authentication
- Network segmentation verification
- Intrusion detection and monitoring
- Incident response automation
- Security audit and compliance reporting
- Vulnerability management
- Patch management tracking
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import secrets
import re

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """IEC 62443 Security Levels (SL)."""
    SL0 = 0  # No specific requirements
    SL1 = 1  # Protection against casual/unintentional violation
    SL2 = 2  # Protection against intentional violation, low resources
    SL3 = 3  # Protection against sophisticated attack, moderate resources
    SL4 = 4  # Protection against state-sponsored attack, extensive resources


class ZoneType(Enum):
    """Types of security zones."""
    ENTERPRISE = "enterprise"  # Level 4-5 (IT network)
    DMZ = "dmz"  # Demilitarized zone between IT/OT
    MANUFACTURING = "manufacturing"  # Level 3 (MES, SCADA)
    CONTROL = "control"  # Level 2 (HMI, Engineering)
    FIELD = "field"  # Level 1 (PLC, Controllers)
    PROCESS = "process"  # Level 0 (Sensors, Actuators)
    SAFETY = "safety"  # Safety Instrumented Systems


class AssetType(Enum):
    """Types of industrial assets."""
    PLC = "programmable_logic_controller"
    HMI = "human_machine_interface"
    SCADA = "scada_server"
    DCS = "distributed_control_system"
    RTU = "remote_terminal_unit"
    IED = "intelligent_electronic_device"
    HISTORIAN = "data_historian"
    MES = "manufacturing_execution_system"
    ENGINEERING_WS = "engineering_workstation"
    FIREWALL = "industrial_firewall"
    SWITCH = "network_switch"
    GATEWAY = "protocol_gateway"
    SENSOR = "sensor_device"
    ACTUATOR = "actuator_device"
    SAFETY_SIS = "safety_instrumented_system"


class ThreatType(Enum):
    """Types of cybersecurity threats."""
    MALWARE = "malware"
    RANSOMWARE = "ransomware"
    PHISHING = "phishing"
    INSIDER = "insider_threat"
    SUPPLY_CHAIN = "supply_chain_compromise"
    ZERO_DAY = "zero_day_exploit"
    DOS = "denial_of_service"
    MAN_IN_MIDDLE = "man_in_the_middle"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXFILTRATION = "data_exfiltration"
    PHYSICAL = "physical_access"
    PROTOCOL_ABUSE = "protocol_abuse"


class VulnerabilitySeverity(Enum):
    """CVSS-based vulnerability severity."""
    CRITICAL = "critical"  # CVSS 9.0-10.0
    HIGH = "high"  # CVSS 7.0-8.9
    MEDIUM = "medium"  # CVSS 4.0-6.9
    LOW = "low"  # CVSS 0.1-3.9
    INFORMATIONAL = "informational"


class IncidentSeverity(Enum):
    """Security incident severity levels."""
    CRITICAL = "critical"  # Immediate threat to safety or operations
    HIGH = "high"  # Significant impact, requires immediate response
    MEDIUM = "medium"  # Moderate impact, timely response needed
    LOW = "low"  # Minor impact, standard response
    INFORMATIONAL = "informational"  # No direct impact, awareness only


@dataclass
class SecurityZone:
    """IEC 62443 Security Zone definition."""
    zone_id: str
    zone_name: str
    zone_type: ZoneType
    target_sl: SecurityLevel
    achieved_sl: SecurityLevel
    description: str
    assets: List[str] = field(default_factory=list)  # Asset IDs
    parent_zone: Optional[str] = None
    network_segment: str = ""
    ip_range: str = ""
    vlan_id: Optional[int] = None
    security_policies: List[str] = field(default_factory=list)
    compliance_status: str = "unknown"
    last_assessment: Optional[datetime] = None


@dataclass
class Conduit:
    """IEC 62443 Conduit (communication channel between zones)."""
    conduit_id: str
    conduit_name: str
    source_zone: str
    destination_zone: str
    protocols: List[str] = field(default_factory=list)
    ports: List[int] = field(default_factory=list)
    encryption_required: bool = True
    authentication_required: bool = True
    firewall_rules: List[Dict] = field(default_factory=list)
    data_diode: bool = False  # Unidirectional gateway
    target_sl: SecurityLevel = SecurityLevel.SL2
    achieved_sl: SecurityLevel = SecurityLevel.SL1
    is_active: bool = True


@dataclass
class Asset:
    """Industrial asset for security management."""
    asset_id: str
    asset_name: str
    asset_type: AssetType
    zone_id: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""
    os_version: str = ""
    criticality: str = "medium"  # low, medium, high, critical
    is_safety_related: bool = False
    last_patched: Optional[datetime] = None
    vulnerabilities: List[str] = field(default_factory=list)
    access_accounts: List[Dict] = field(default_factory=list)
    installed_software: List[Dict] = field(default_factory=list)
    network_connections: List[str] = field(default_factory=list)
    backup_status: str = "unknown"


@dataclass
class Vulnerability:
    """Security vulnerability record."""
    vuln_id: str
    cve_id: Optional[str] = None
    title: str = ""
    description: str = ""
    severity: VulnerabilitySeverity = VulnerabilitySeverity.MEDIUM
    cvss_score: float = 0.0
    affected_assets: List[str] = field(default_factory=list)
    affected_software: str = ""
    discovered_at: datetime = field(default_factory=datetime.now)
    status: str = "open"  # open, in_progress, mitigated, accepted, closed
    remediation_plan: str = ""
    remediation_deadline: Optional[datetime] = None
    exploited_in_wild: bool = False


@dataclass
class SecurityPolicy:
    """Security policy definition."""
    policy_id: str
    policy_name: str
    policy_type: str  # access_control, password, network, patching, backup
    description: str
    requirements: List[Dict] = field(default_factory=list)
    applicable_zones: List[str] = field(default_factory=list)
    applicable_asset_types: List[AssetType] = field(default_factory=list)
    is_mandatory: bool = True
    effective_date: datetime = field(default_factory=datetime.now)
    review_date: Optional[datetime] = None
    version: str = "1.0"


@dataclass
class AccessRequest:
    """Access request record."""
    request_id: str
    requestor_id: str
    requestor_name: str
    asset_id: str
    access_type: str  # read, write, execute, admin
    justification: str
    requested_at: datetime
    duration_hours: int = 8
    status: str = "pending"  # pending, approved, denied, expired, revoked
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    mfa_verified: bool = False


@dataclass
class SecurityIncident:
    """Security incident record."""
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    threat_type: ThreatType
    affected_zones: List[str]
    affected_assets: List[str]
    detected_at: datetime
    reported_by: str
    status: str = "new"  # new, investigating, contained, eradicated, recovered, closed
    containment_actions: List[Dict] = field(default_factory=list)
    root_cause: Optional[str] = None
    lessons_learned: Optional[str] = None
    closed_at: Optional[datetime] = None


@dataclass
class AuditLog:
    """Security audit log entry."""
    log_id: str
    timestamp: datetime
    event_type: str
    source_ip: Optional[str] = None
    source_user: Optional[str] = None
    target_asset: Optional[str] = None
    action: str = ""
    result: str = ""  # success, failure, blocked
    details: Dict = field(default_factory=dict)
    risk_score: int = 0  # 0-100


class IEC62443SecurityService:
    """
    IEC 62443 compliant industrial cybersecurity service.

    Provides comprehensive security management for industrial
    automation and control systems.
    """

    def __init__(self):
        self.zones: Dict[str, SecurityZone] = {}
        self.conduits: Dict[str, Conduit] = {}
        self.assets: Dict[str, Asset] = {}
        self.vulnerabilities: Dict[str, Vulnerability] = {}
        self.policies: Dict[str, SecurityPolicy] = {}
        self.access_requests: Dict[str, AccessRequest] = {}
        self.incidents: Dict[str, SecurityIncident] = {}
        self.audit_logs: List[AuditLog] = []
        self._threat_intelligence: List[Dict] = []
        self._anomaly_baselines: Dict[str, Dict] = {}

    def _generate_id(self, prefix: str = "SEC") -> str:
        """Generate unique identifier."""
        timestamp = datetime.now().strftime("%Y%m%d")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{timestamp}-{unique}"

    def _log_audit(self, event_type: str, action: str, result: str,
                   source_user: str = None, target_asset: str = None,
                   details: Dict = None, risk_score: int = 0):
        """Record security audit log entry."""
        log = AuditLog(
            log_id=self._generate_id("LOG"),
            timestamp=datetime.now(),
            event_type=event_type,
            source_user=source_user,
            target_asset=target_asset,
            action=action,
            result=result,
            details=details or {},
            risk_score=risk_score
        )
        self.audit_logs.append(log)
        logger.info(f"Security audit: {event_type} - {action} - {result}")

    # =========================================================================
    # Zone and Conduit Management
    # =========================================================================

    async def create_zone(
        self,
        zone_name: str,
        zone_type: ZoneType,
        target_sl: SecurityLevel,
        description: str,
        network_segment: str,
        ip_range: str = "",
        vlan_id: int = None,
        parent_zone: str = None
    ) -> SecurityZone:
        """
        Create a security zone per IEC 62443.

        Zones group assets with similar security requirements
        and are the foundation of defense-in-depth architecture.
        """
        zone_id = self._generate_id("ZONE")

        zone = SecurityZone(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            target_sl=target_sl,
            achieved_sl=SecurityLevel.SL0,
            description=description,
            network_segment=network_segment,
            ip_range=ip_range,
            vlan_id=vlan_id,
            parent_zone=parent_zone
        )

        self.zones[zone_id] = zone
        self._log_audit("ZONE_CREATED", f"Created zone {zone_name}",
                        "success", details={"zone_type": zone_type.value})

        return zone

    async def create_conduit(
        self,
        conduit_name: str,
        source_zone: str,
        destination_zone: str,
        protocols: List[str],
        ports: List[int],
        target_sl: SecurityLevel = SecurityLevel.SL2,
        encryption_required: bool = True,
        data_diode: bool = False
    ) -> Conduit:
        """
        Create a conduit between security zones.

        Conduits define allowed communication paths and their
        security requirements.
        """
        if source_zone not in self.zones:
            raise ValueError(f"Source zone not found: {source_zone}")
        if destination_zone not in self.zones:
            raise ValueError(f"Destination zone not found: {destination_zone}")

        conduit_id = self._generate_id("COND")

        conduit = Conduit(
            conduit_id=conduit_id,
            conduit_name=conduit_name,
            source_zone=source_zone,
            destination_zone=destination_zone,
            protocols=protocols,
            ports=ports,
            encryption_required=encryption_required,
            target_sl=target_sl,
            data_diode=data_diode
        )

        self.conduits[conduit_id] = conduit
        self._log_audit("CONDUIT_CREATED",
                        f"Created conduit {conduit_name} from {source_zone} to {destination_zone}",
                        "success")

        return conduit

    async def add_firewall_rule(
        self,
        conduit_id: str,
        rule_name: str,
        source_ip: str,
        destination_ip: str,
        port: int,
        protocol: str,
        action: str = "allow"
    ) -> Conduit:
        """Add a firewall rule to a conduit."""
        if conduit_id not in self.conduits:
            raise ValueError(f"Conduit not found: {conduit_id}")

        conduit = self.conduits[conduit_id]

        rule = {
            "rule_id": self._generate_id("FW"),
            "rule_name": rule_name,
            "source_ip": source_ip,
            "destination_ip": destination_ip,
            "port": port,
            "protocol": protocol,
            "action": action,
            "created_at": datetime.now().isoformat()
        }

        conduit.firewall_rules.append(rule)
        self._log_audit("FIREWALL_RULE_ADDED", f"Added rule to {conduit_id}",
                        "success", details=rule)

        return conduit

    # =========================================================================
    # Asset Management
    # =========================================================================

    async def register_asset(
        self,
        asset_name: str,
        asset_type: AssetType,
        zone_id: str,
        ip_address: str = None,
        manufacturer: str = "",
        model: str = "",
        firmware_version: str = "",
        criticality: str = "medium",
        is_safety_related: bool = False
    ) -> Asset:
        """
        Register an industrial asset for security management.

        All assets should be inventoried for proper security management.
        """
        if zone_id not in self.zones:
            raise ValueError(f"Zone not found: {zone_id}")

        asset_id = self._generate_id("ASSET")

        asset = Asset(
            asset_id=asset_id,
            asset_name=asset_name,
            asset_type=asset_type,
            zone_id=zone_id,
            ip_address=ip_address,
            manufacturer=manufacturer,
            model=model,
            firmware_version=firmware_version,
            criticality=criticality,
            is_safety_related=is_safety_related
        )

        self.assets[asset_id] = asset
        self.zones[zone_id].assets.append(asset_id)

        self._log_audit("ASSET_REGISTERED", f"Registered asset {asset_name}",
                        "success", target_asset=asset_id,
                        details={"type": asset_type.value, "zone": zone_id})

        return asset

    async def update_asset_firmware(
        self,
        asset_id: str,
        new_version: str,
        updated_by: str
    ) -> Asset:
        """Record firmware update for an asset."""
        if asset_id not in self.assets:
            raise ValueError(f"Asset not found: {asset_id}")

        asset = self.assets[asset_id]
        old_version = asset.firmware_version
        asset.firmware_version = new_version
        asset.last_patched = datetime.now()

        self._log_audit("FIRMWARE_UPDATED",
                        f"Updated firmware from {old_version} to {new_version}",
                        "success", source_user=updated_by, target_asset=asset_id)

        return asset

    # =========================================================================
    # Vulnerability Management
    # =========================================================================

    async def report_vulnerability(
        self,
        title: str,
        description: str,
        severity: VulnerabilitySeverity,
        cvss_score: float,
        affected_assets: List[str],
        cve_id: str = None,
        exploited_in_wild: bool = False
    ) -> Vulnerability:
        """
        Report a new vulnerability.

        Tracks vulnerabilities affecting industrial assets
        for remediation prioritization.
        """
        vuln_id = self._generate_id("VULN")

        vuln = Vulnerability(
            vuln_id=vuln_id,
            cve_id=cve_id,
            title=title,
            description=description,
            severity=severity,
            cvss_score=cvss_score,
            affected_assets=affected_assets,
            exploited_in_wild=exploited_in_wild
        )

        self.vulnerabilities[vuln_id] = vuln

        # Link to affected assets
        for asset_id in affected_assets:
            if asset_id in self.assets:
                self.assets[asset_id].vulnerabilities.append(vuln_id)

        risk_score = int(cvss_score * 10)
        if exploited_in_wild:
            risk_score = min(100, risk_score + 20)

        self._log_audit("VULNERABILITY_REPORTED",
                        f"Reported vulnerability: {title}",
                        "success", details={"cve": cve_id, "cvss": cvss_score},
                        risk_score=risk_score)

        return vuln

    async def update_vulnerability_status(
        self,
        vuln_id: str,
        new_status: str,
        remediation_plan: str = None,
        updated_by: str = None
    ) -> Vulnerability:
        """Update vulnerability remediation status."""
        if vuln_id not in self.vulnerabilities:
            raise ValueError(f"Vulnerability not found: {vuln_id}")

        vuln = self.vulnerabilities[vuln_id]
        old_status = vuln.status
        vuln.status = new_status

        if remediation_plan:
            vuln.remediation_plan = remediation_plan

        self._log_audit("VULNERABILITY_UPDATED",
                        f"Updated vulnerability {vuln_id} from {old_status} to {new_status}",
                        "success", source_user=updated_by)

        return vuln

    async def get_vulnerability_summary(self) -> Dict:
        """Get vulnerability management summary."""
        by_severity = {s.value: 0 for s in VulnerabilitySeverity}
        by_status = {"open": 0, "in_progress": 0, "mitigated": 0, "closed": 0}

        for vuln in self.vulnerabilities.values():
            by_severity[vuln.severity.value] += 1
            by_status[vuln.status] = by_status.get(vuln.status, 0) + 1

        # Calculate risk exposure
        risk_score = sum(
            v.cvss_score * (2 if v.exploited_in_wild else 1)
            for v in self.vulnerabilities.values()
            if v.status in ["open", "in_progress"]
        )

        return {
            "total_vulnerabilities": len(self.vulnerabilities),
            "by_severity": by_severity,
            "by_status": by_status,
            "risk_exposure_score": round(risk_score, 2),
            "critical_open": sum(
                1 for v in self.vulnerabilities.values()
                if v.severity == VulnerabilitySeverity.CRITICAL and v.status == "open"
            ),
            "exploited_in_wild_count": sum(
                1 for v in self.vulnerabilities.values() if v.exploited_in_wild
            )
        }

    # =========================================================================
    # Access Control
    # =========================================================================

    async def request_access(
        self,
        requestor_id: str,
        requestor_name: str,
        asset_id: str,
        access_type: str,
        justification: str,
        duration_hours: int = 8
    ) -> AccessRequest:
        """
        Request access to an industrial asset.

        Implements just-in-time access control per zero-trust principles.
        """
        if asset_id not in self.assets:
            raise ValueError(f"Asset not found: {asset_id}")

        request_id = self._generate_id("ACC")

        request = AccessRequest(
            request_id=request_id,
            requestor_id=requestor_id,
            requestor_name=requestor_name,
            asset_id=asset_id,
            access_type=access_type,
            justification=justification,
            requested_at=datetime.now(),
            duration_hours=duration_hours
        )

        self.access_requests[request_id] = request

        asset = self.assets[asset_id]
        risk_score = 30
        if asset.is_safety_related:
            risk_score = 60
        if access_type == "admin":
            risk_score += 20

        self._log_audit("ACCESS_REQUESTED",
                        f"Access requested to {asset.asset_name}",
                        "pending", source_user=requestor_id,
                        target_asset=asset_id,
                        details={"access_type": access_type},
                        risk_score=risk_score)

        return request

    async def approve_access(
        self,
        request_id: str,
        approved_by: str,
        require_mfa: bool = True
    ) -> AccessRequest:
        """Approve an access request."""
        if request_id not in self.access_requests:
            raise ValueError(f"Access request not found: {request_id}")

        request = self.access_requests[request_id]

        if request.status != "pending":
            raise ValueError(f"Request not pending: {request.status}")

        request.status = "approved"
        request.approved_by = approved_by
        request.approved_at = datetime.now()
        request.expires_at = datetime.now() + timedelta(hours=request.duration_hours)
        request.mfa_verified = not require_mfa  # Will be verified on first access

        self._log_audit("ACCESS_APPROVED",
                        f"Access approved for request {request_id}",
                        "success", source_user=approved_by,
                        target_asset=request.asset_id)

        return request

    async def deny_access(
        self,
        request_id: str,
        denied_by: str,
        reason: str
    ) -> AccessRequest:
        """Deny an access request."""
        if request_id not in self.access_requests:
            raise ValueError(f"Access request not found: {request_id}")

        request = self.access_requests[request_id]
        request.status = "denied"

        self._log_audit("ACCESS_DENIED",
                        f"Access denied for request {request_id}: {reason}",
                        "blocked", source_user=denied_by,
                        target_asset=request.asset_id, risk_score=40)

        return request

    async def verify_mfa(
        self,
        request_id: str,
        mfa_code: str
    ) -> Tuple[bool, str]:
        """Verify MFA for access request."""
        if request_id not in self.access_requests:
            raise ValueError(f"Access request not found: {request_id}")

        request = self.access_requests[request_id]

        # Simplified MFA verification - in production use TOTP
        valid = len(mfa_code) == 6 and mfa_code.isdigit()

        if valid:
            request.mfa_verified = True
            self._log_audit("MFA_VERIFIED",
                            f"MFA verified for request {request_id}",
                            "success", target_asset=request.asset_id)
            return True, "MFA verified successfully"
        else:
            self._log_audit("MFA_FAILED",
                            f"MFA failed for request {request_id}",
                            "failure", target_asset=request.asset_id,
                            risk_score=50)
            return False, "Invalid MFA code"

    async def revoke_access(
        self,
        request_id: str,
        revoked_by: str,
        reason: str
    ) -> AccessRequest:
        """Revoke previously granted access."""
        if request_id not in self.access_requests:
            raise ValueError(f"Access request not found: {request_id}")

        request = self.access_requests[request_id]
        request.status = "revoked"

        self._log_audit("ACCESS_REVOKED",
                        f"Access revoked: {reason}",
                        "success", source_user=revoked_by,
                        target_asset=request.asset_id)

        return request

    # =========================================================================
    # Incident Management
    # =========================================================================

    async def report_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        threat_type: ThreatType,
        affected_zones: List[str],
        affected_assets: List[str],
        reported_by: str
    ) -> SecurityIncident:
        """
        Report a security incident.

        Triggers incident response workflow based on severity.
        """
        incident_id = self._generate_id("INC")

        incident = SecurityIncident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            threat_type=threat_type,
            affected_zones=affected_zones,
            affected_assets=affected_assets,
            detected_at=datetime.now(),
            reported_by=reported_by
        )

        self.incidents[incident_id] = incident

        risk_score = {
            IncidentSeverity.CRITICAL: 100,
            IncidentSeverity.HIGH: 80,
            IncidentSeverity.MEDIUM: 50,
            IncidentSeverity.LOW: 25,
            IncidentSeverity.INFORMATIONAL: 10
        }.get(severity, 50)

        self._log_audit("INCIDENT_REPORTED",
                        f"Security incident: {title}",
                        "success", source_user=reported_by,
                        details={"threat": threat_type.value,
                                 "severity": severity.value},
                        risk_score=risk_score)

        # Auto-initiate containment for critical incidents
        if severity == IncidentSeverity.CRITICAL:
            await self._auto_contain_critical_incident(incident)

        return incident

    async def _auto_contain_critical_incident(self, incident: SecurityIncident):
        """Automatic containment actions for critical incidents."""
        containment_actions = []

        # Isolate affected zones
        for zone_id in incident.affected_zones:
            if zone_id in self.zones:
                # Disable conduits to affected zone
                for conduit in self.conduits.values():
                    if conduit.destination_zone == zone_id:
                        conduit.is_active = False
                        containment_actions.append({
                            "action": "disable_conduit",
                            "conduit_id": conduit.conduit_id,
                            "timestamp": datetime.now().isoformat()
                        })

        # Revoke active access to affected assets
        for asset_id in incident.affected_assets:
            for request in self.access_requests.values():
                if request.asset_id == asset_id and request.status == "approved":
                    request.status = "revoked"
                    containment_actions.append({
                        "action": "revoke_access",
                        "request_id": request.request_id,
                        "timestamp": datetime.now().isoformat()
                    })

        incident.containment_actions = containment_actions
        incident.status = "contained"

        self._log_audit("AUTO_CONTAINMENT",
                        f"Auto-contained incident {incident.incident_id}",
                        "success",
                        details={"actions": len(containment_actions)},
                        risk_score=90)

    async def update_incident_status(
        self,
        incident_id: str,
        new_status: str,
        updated_by: str,
        notes: str = ""
    ) -> SecurityIncident:
        """Update incident status."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident not found: {incident_id}")

        incident = self.incidents[incident_id]
        old_status = incident.status
        incident.status = new_status

        if new_status == "closed":
            incident.closed_at = datetime.now()

        self._log_audit("INCIDENT_UPDATED",
                        f"Incident {incident_id} status: {old_status} -> {new_status}",
                        "success", source_user=updated_by,
                        details={"notes": notes})

        return incident

    async def set_root_cause(
        self,
        incident_id: str,
        root_cause: str,
        lessons_learned: str,
        updated_by: str
    ) -> SecurityIncident:
        """Set root cause analysis for incident."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident not found: {incident_id}")

        incident = self.incidents[incident_id]
        incident.root_cause = root_cause
        incident.lessons_learned = lessons_learned

        self._log_audit("ROOT_CAUSE_SET",
                        f"Root cause set for incident {incident_id}",
                        "success", source_user=updated_by)

        return incident

    # =========================================================================
    # Security Assessment
    # =========================================================================

    async def assess_zone_security(self, zone_id: str) -> Dict:
        """
        Assess security level achievement for a zone.

        Compares current controls against target security level.
        """
        if zone_id not in self.zones:
            raise ValueError(f"Zone not found: {zone_id}")

        zone = self.zones[zone_id]

        # Assessment criteria per IEC 62443
        findings = []
        score = 100

        # Check asset inventory completeness
        undocumented_assets = 0
        for asset_id in zone.assets:
            asset = self.assets.get(asset_id)
            if asset:
                if not asset.firmware_version:
                    findings.append({
                        "category": "Asset Management",
                        "finding": f"Asset {asset.asset_name} missing firmware version",
                        "severity": "medium"
                    })
                    score -= 5
                if asset.vulnerabilities:
                    findings.append({
                        "category": "Vulnerability Management",
                        "finding": f"Asset {asset.asset_name} has {len(asset.vulnerabilities)} vulnerabilities",
                        "severity": "high"
                    })
                    score -= 10 * len(asset.vulnerabilities)

        # Check conduit security
        zone_conduits = [
            c for c in self.conduits.values()
            if c.source_zone == zone_id or c.destination_zone == zone_id
        ]

        for conduit in zone_conduits:
            if zone.target_sl.value >= 2 and not conduit.encryption_required:
                findings.append({
                    "category": "Network Security",
                    "finding": f"Conduit {conduit.conduit_name} lacks encryption requirement",
                    "severity": "high"
                })
                score -= 15

            if not conduit.firewall_rules:
                findings.append({
                    "category": "Network Security",
                    "finding": f"Conduit {conduit.conduit_name} has no firewall rules",
                    "severity": "medium"
                })
                score -= 10

        # Determine achieved SL based on score
        if score >= 90:
            achieved_sl = SecurityLevel.SL4
        elif score >= 75:
            achieved_sl = SecurityLevel.SL3
        elif score >= 50:
            achieved_sl = SecurityLevel.SL2
        elif score >= 25:
            achieved_sl = SecurityLevel.SL1
        else:
            achieved_sl = SecurityLevel.SL0

        zone.achieved_sl = achieved_sl
        zone.last_assessment = datetime.now()
        zone.compliance_status = "compliant" if achieved_sl.value >= zone.target_sl.value else "non-compliant"

        return {
            "zone_id": zone_id,
            "zone_name": zone.zone_name,
            "target_sl": zone.target_sl.value,
            "achieved_sl": achieved_sl.value,
            "score": max(0, score),
            "findings": findings,
            "compliance_status": zone.compliance_status,
            "assessment_date": datetime.now().isoformat()
        }

    async def run_full_assessment(self) -> Dict:
        """Run security assessment across all zones."""
        results = []
        for zone_id in self.zones:
            result = await self.assess_zone_security(zone_id)
            results.append(result)

        overall_score = sum(r["score"] for r in results) / len(results) if results else 0

        return {
            "assessment_date": datetime.now().isoformat(),
            "zones_assessed": len(results),
            "overall_score": round(overall_score, 2),
            "zone_results": results,
            "critical_findings": sum(
                len([f for f in r["findings"] if f["severity"] == "high"])
                for r in results
            ),
            "compliance_summary": {
                "compliant": sum(1 for r in results if r["compliance_status"] == "compliant"),
                "non_compliant": sum(1 for r in results if r["compliance_status"] == "non-compliant")
            }
        }

    # =========================================================================
    # Anomaly Detection
    # =========================================================================

    async def establish_baseline(
        self,
        asset_id: str,
        metrics: Dict[str, float]
    ) -> Dict:
        """Establish behavioral baseline for anomaly detection."""
        if asset_id not in self.assets:
            raise ValueError(f"Asset not found: {asset_id}")

        self._anomaly_baselines[asset_id] = {
            "metrics": metrics,
            "established_at": datetime.now().isoformat(),
            "sample_count": 1
        }

        return self._anomaly_baselines[asset_id]

    async def check_anomaly(
        self,
        asset_id: str,
        current_metrics: Dict[str, float],
        threshold: float = 2.0
    ) -> Dict:
        """Check for anomalous behavior against baseline."""
        if asset_id not in self._anomaly_baselines:
            return {"asset_id": asset_id, "anomaly_detected": False,
                    "reason": "No baseline established"}

        baseline = self._anomaly_baselines[asset_id]["metrics"]
        anomalies = []

        for metric, value in current_metrics.items():
            if metric in baseline:
                baseline_value = baseline[metric]
                if baseline_value > 0:
                    deviation = abs(value - baseline_value) / baseline_value
                    if deviation > threshold:
                        anomalies.append({
                            "metric": metric,
                            "baseline": baseline_value,
                            "current": value,
                            "deviation": round(deviation * 100, 2)
                        })

        if anomalies:
            self._log_audit("ANOMALY_DETECTED",
                            f"Anomalous behavior on {asset_id}",
                            "alert", target_asset=asset_id,
                            details={"anomalies": anomalies},
                            risk_score=60)

        return {
            "asset_id": asset_id,
            "anomaly_detected": len(anomalies) > 0,
            "anomalies": anomalies,
            "checked_at": datetime.now().isoformat()
        }

    # =========================================================================
    # Reporting
    # =========================================================================

    async def generate_compliance_report(self) -> Dict:
        """Generate IEC 62443 compliance report."""
        assessment = await self.run_full_assessment()
        vuln_summary = await self.get_vulnerability_summary()

        # Count active incidents
        active_incidents = sum(
            1 for i in self.incidents.values()
            if i.status not in ["closed", "recovered"]
        )

        return {
            "report_date": datetime.now().isoformat(),
            "framework": "IEC 62443",
            "overall_compliance": assessment["compliance_summary"],
            "security_score": assessment["overall_score"],
            "zones": {
                "total": len(self.zones),
                "by_type": {
                    zt.value: sum(1 for z in self.zones.values() if z.zone_type == zt)
                    for zt in ZoneType
                }
            },
            "assets": {
                "total": len(self.assets),
                "by_criticality": {
                    c: sum(1 for a in self.assets.values() if a.criticality == c)
                    for c in ["low", "medium", "high", "critical"]
                },
                "safety_related": sum(1 for a in self.assets.values() if a.is_safety_related)
            },
            "vulnerabilities": vuln_summary,
            "incidents": {
                "total": len(self.incidents),
                "active": active_incidents,
                "by_severity": {
                    s.value: sum(1 for i in self.incidents.values() if i.severity == s)
                    for s in IncidentSeverity
                }
            },
            "access_control": {
                "active_requests": sum(
                    1 for r in self.access_requests.values()
                    if r.status == "approved" and
                    r.expires_at and r.expires_at > datetime.now()
                ),
                "denied_last_30_days": sum(
                    1 for r in self.access_requests.values()
                    if r.status == "denied" and
                    r.requested_at > datetime.now() - timedelta(days=30)
                )
            },
            "audit_log_entries": len(self.audit_logs),
            "recommendations": self._generate_recommendations(assessment, vuln_summary)
        }

    def _generate_recommendations(self, assessment: Dict, vuln_summary: Dict) -> List[str]:
        """Generate security recommendations based on assessment."""
        recommendations = []

        if assessment["overall_score"] < 70:
            recommendations.append("Immediate security review required - overall score below 70%")

        if vuln_summary["critical_open"] > 0:
            recommendations.append(
                f"Address {vuln_summary['critical_open']} critical vulnerabilities immediately"
            )

        if vuln_summary["exploited_in_wild_count"] > 0:
            recommendations.append(
                "Prioritize patching vulnerabilities with known exploits in the wild"
            )

        non_compliant = assessment["compliance_summary"]["non_compliant"]
        if non_compliant > 0:
            recommendations.append(
                f"Remediate {non_compliant} zones not meeting target security level"
            )

        return recommendations

    def get_audit_logs(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        event_type: str = None,
        min_risk_score: int = 0
    ) -> List[Dict]:
        """Retrieve audit logs with optional filtering."""
        logs = self.audit_logs

        if start_date:
            logs = [l for l in logs if l.timestamp >= start_date]
        if end_date:
            logs = [l for l in logs if l.timestamp <= end_date]
        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        if min_risk_score > 0:
            logs = [l for l in logs if l.risk_score >= min_risk_score]

        return [
            {
                "log_id": l.log_id,
                "timestamp": l.timestamp.isoformat(),
                "event_type": l.event_type,
                "action": l.action,
                "result": l.result,
                "source_user": l.source_user,
                "target_asset": l.target_asset,
                "risk_score": l.risk_score
            }
            for l in logs
        ]


# Factory function
def create_security_service() -> IEC62443SecurityService:
    """Create and return an IEC62443SecurityService instance."""
    return IEC62443SecurityService()
