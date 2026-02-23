"""
NIST SP 800-171 Compliance Checker

Implements security requirements for protecting
Controlled Unclassified Information (CUI).

Reference: NIST SP 800-171 Rev 2, DFARS 252.204-7012
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)


class ControlFamily(Enum):
    """NIST 800-171 Control Families."""
    ACCESS_CONTROL = "3.1"
    AWARENESS_TRAINING = "3.2"
    AUDIT = "3.3"
    CONFIGURATION = "3.4"
    IDENTIFICATION = "3.5"
    INCIDENT_RESPONSE = "3.6"
    MAINTENANCE = "3.7"
    MEDIA_PROTECTION = "3.8"
    PERSONNEL = "3.9"
    PHYSICAL = "3.10"
    RISK = "3.11"
    SECURITY_ASSESSMENT = "3.12"
    SYSTEM_COMM = "3.13"
    SYSTEM_INFO = "3.14"


class ControlStatus(Enum):
    """Control implementation status."""
    IMPLEMENTED = "implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    PLANNED = "planned"
    NOT_APPLICABLE = "not_applicable"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class SecurityControl:
    """NIST 800-171 Security Control."""
    control_id: str
    family: ControlFamily
    title: str
    description: str
    status: ControlStatus = ControlStatus.NOT_IMPLEMENTED
    implementation_notes: str = ""
    evidence: List[str] = field(default_factory=list)
    assessment_date: Optional[str] = None
    assessor: Optional[str] = None
    poam_id: Optional[str] = None  # Plan of Action & Milestones


@dataclass
class ComplianceAssessment:
    """Assessment result for a control family or full assessment."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    controls_assessed: int = 0
    controls_implemented: int = 0
    controls_partial: int = 0
    controls_planned: int = 0
    controls_not_implemented: int = 0
    compliance_score: float = 0.0
    findings: List[Dict[str, Any]] = field(default_factory=list)
    poam_items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "controls_assessed": self.controls_assessed,
            "controls_implemented": self.controls_implemented,
            "controls_partial": self.controls_partial,
            "controls_planned": self.controls_planned,
            "controls_not_implemented": self.controls_not_implemented,
            "compliance_score": round(self.compliance_score, 2),
            "findings": self.findings,
            "poam_items": self.poam_items
        }


class NISTComplianceChecker:
    """
    NIST SP 800-171 Compliance Checker.

    Assesses and tracks compliance with NIST 800-171
    security requirements for CUI protection.

    Usage:
        >>> checker = NISTComplianceChecker()
        >>> checker.load_controls()
        >>> assessment = checker.assess_all()
        >>> print(f"Compliance: {assessment.compliance_score}%")
    """

    # NIST 800-171 Rev 2 Controls (subset - key controls)
    CONTROLS = {
        # Access Control
        "3.1.1": ("Limit system access to authorized users", ControlFamily.ACCESS_CONTROL),
        "3.1.2": ("Limit system access to the types of transactions and functions", ControlFamily.ACCESS_CONTROL),
        "3.1.3": ("Control the flow of CUI in accordance with approved authorizations", ControlFamily.ACCESS_CONTROL),
        "3.1.5": ("Employ the principle of least privilege", ControlFamily.ACCESS_CONTROL),
        "3.1.7": ("Prevent non-privileged users from executing privileged functions", ControlFamily.ACCESS_CONTROL),
        "3.1.12": ("Monitor and control remote access sessions", ControlFamily.ACCESS_CONTROL),
        "3.1.13": ("Employ cryptographic mechanisms to protect remote access", ControlFamily.ACCESS_CONTROL),
        "3.1.20": ("Verify and control connections to external systems", ControlFamily.ACCESS_CONTROL),

        # Audit and Accountability
        "3.3.1": ("Create and retain audit logs", ControlFamily.AUDIT),
        "3.3.2": ("Ensure actions can be traced to individual users", ControlFamily.AUDIT),
        "3.3.4": ("Alert on audit logging process failures", ControlFamily.AUDIT),
        "3.3.5": ("Correlate audit record review", ControlFamily.AUDIT),

        # Configuration Management
        "3.4.1": ("Establish and maintain baseline configurations", ControlFamily.CONFIGURATION),
        "3.4.2": ("Establish and enforce security configuration settings", ControlFamily.CONFIGURATION),
        "3.4.6": ("Employ principle of least functionality", ControlFamily.CONFIGURATION),

        # Identification and Authentication
        "3.5.1": ("Identify system users, processes, or devices", ControlFamily.IDENTIFICATION),
        "3.5.2": ("Authenticate users, processes, or devices", ControlFamily.IDENTIFICATION),
        "3.5.3": ("Use multifactor authentication for network access", ControlFamily.IDENTIFICATION),
        "3.5.7": ("Enforce minimum password complexity", ControlFamily.IDENTIFICATION),

        # Incident Response
        "3.6.1": ("Establish incident-handling capability", ControlFamily.INCIDENT_RESPONSE),
        "3.6.2": ("Track, document, and report incidents", ControlFamily.INCIDENT_RESPONSE),

        # Media Protection
        "3.8.1": ("Protect system media containing CUI", ControlFamily.MEDIA_PROTECTION),
        "3.8.3": ("Sanitize or destroy system media containing CUI", ControlFamily.MEDIA_PROTECTION),
        "3.8.9": ("Protect the confidentiality of backup CUI", ControlFamily.MEDIA_PROTECTION),

        # Physical Protection
        "3.10.1": ("Limit physical access to organizational systems", ControlFamily.PHYSICAL),
        "3.10.2": ("Protect and monitor the physical facility", ControlFamily.PHYSICAL),

        # Risk Assessment
        "3.11.1": ("Periodically assess the risk to operations", ControlFamily.RISK),
        "3.11.2": ("Scan for vulnerabilities periodically", ControlFamily.RISK),

        # Security Assessment
        "3.12.1": ("Periodically assess security controls", ControlFamily.SECURITY_ASSESSMENT),
        "3.12.3": ("Monitor security controls on an ongoing basis", ControlFamily.SECURITY_ASSESSMENT),

        # System and Communications Protection
        "3.13.1": ("Monitor, control, and protect communications at boundaries", ControlFamily.SYSTEM_COMM),
        "3.13.8": ("Implement cryptographic mechanisms for CUI in transit", ControlFamily.SYSTEM_COMM),
        "3.13.11": ("Employ FIPS-validated cryptography", ControlFamily.SYSTEM_COMM),

        # System and Information Integrity
        "3.14.1": ("Identify, report, and correct system flaws", ControlFamily.SYSTEM_INFO),
        "3.14.2": ("Provide protection from malicious code", ControlFamily.SYSTEM_INFO),
        "3.14.6": ("Monitor organizational systems", ControlFamily.SYSTEM_INFO),
        "3.14.7": ("Identify unauthorized use of systems", ControlFamily.SYSTEM_INFO),
    }

    def __init__(self):
        self.controls: Dict[str, SecurityControl] = {}
        self.evidence_store: Dict[str, List[Dict[str, Any]]] = {}
        self._init_controls()
        logger.info("NISTComplianceChecker initialized with %d controls", len(self.controls))

    def _init_controls(self) -> None:
        """Initialize security controls from catalog."""
        for control_id, (title, family) in self.CONTROLS.items():
            self.controls[control_id] = SecurityControl(
                control_id=control_id,
                family=family,
                title=title,
                description=f"NIST 800-171 {control_id}: {title}"
            )

    def update_control_status(
        self,
        control_id: str,
        status: ControlStatus,
        implementation_notes: str = "",
        evidence: Optional[List[str]] = None,
        assessor: Optional[str] = None
    ) -> bool:
        """Update status of a security control."""
        if control_id not in self.controls:
            logger.warning(f"Unknown control: {control_id}")
            return False

        control = self.controls[control_id]
        control.status = status
        control.implementation_notes = implementation_notes
        control.evidence = evidence or []
        control.assessment_date = datetime.utcnow().isoformat() + "Z"
        control.assessor = assessor

        logger.info(f"Control {control_id} updated to {status.value}")
        return True

    def add_evidence(
        self,
        control_id: str,
        evidence_type: str,
        description: str,
        artifact_path: Optional[str] = None
    ) -> str:
        """Add evidence for a control."""
        if control_id not in self.evidence_store:
            self.evidence_store[control_id] = []

        evidence_id = hashlib.sha256(
            f"{control_id}{datetime.utcnow().isoformat()}{description}".encode()
        ).hexdigest()[:16]

        evidence = {
            "id": evidence_id,
            "control_id": control_id,
            "type": evidence_type,
            "description": description,
            "artifact_path": artifact_path,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        self.evidence_store[control_id].append(evidence)

        if control_id in self.controls:
            self.controls[control_id].evidence.append(evidence_id)

        return evidence_id

    def assess_control(self, control_id: str) -> Optional[Dict[str, Any]]:
        """Assess a single control."""
        if control_id not in self.controls:
            return None

        control = self.controls[control_id]
        evidence = self.evidence_store.get(control_id, [])

        finding = None
        if control.status in (ControlStatus.NOT_IMPLEMENTED, ControlStatus.PARTIALLY_IMPLEMENTED):
            finding = {
                "control_id": control_id,
                "title": control.title,
                "status": control.status.value,
                "description": f"Control {control_id} requires attention",
                "remediation": f"Implement {control.title}"
            }

        return {
            "control_id": control_id,
            "status": control.status.value,
            "evidence_count": len(evidence),
            "finding": finding
        }

    def assess_family(self, family: ControlFamily) -> ComplianceAssessment:
        """Assess all controls in a control family."""
        assessment = ComplianceAssessment()

        for control_id, control in self.controls.items():
            if control.family != family:
                continue

            assessment.controls_assessed += 1

            if control.status == ControlStatus.IMPLEMENTED:
                assessment.controls_implemented += 1
            elif control.status == ControlStatus.PARTIALLY_IMPLEMENTED:
                assessment.controls_partial += 1
            elif control.status == ControlStatus.PLANNED:
                assessment.controls_planned += 1
            elif control.status == ControlStatus.NOT_IMPLEMENTED:
                assessment.controls_not_implemented += 1
                assessment.findings.append({
                    "control_id": control_id,
                    "title": control.title,
                    "severity": "HIGH",
                    "finding": f"Control not implemented: {control.title}"
                })

        if assessment.controls_assessed > 0:
            implemented = assessment.controls_implemented + (assessment.controls_partial * 0.5)
            assessment.compliance_score = (implemented / assessment.controls_assessed) * 100

        return assessment

    def assess_all(self) -> ComplianceAssessment:
        """Assess all NIST 800-171 controls."""
        assessment = ComplianceAssessment()

        for control_id, control in self.controls.items():
            assessment.controls_assessed += 1

            if control.status == ControlStatus.IMPLEMENTED:
                assessment.controls_implemented += 1
            elif control.status == ControlStatus.PARTIALLY_IMPLEMENTED:
                assessment.controls_partial += 1
            elif control.status == ControlStatus.PLANNED:
                assessment.controls_planned += 1
                assessment.poam_items.append({
                    "control_id": control_id,
                    "title": control.title,
                    "target_date": None,
                    "milestones": []
                })
            elif control.status == ControlStatus.NOT_IMPLEMENTED:
                assessment.controls_not_implemented += 1
                assessment.findings.append({
                    "control_id": control_id,
                    "title": control.title,
                    "severity": "HIGH",
                    "finding": f"Control not implemented: {control.title}",
                    "remediation": f"Implement {control.title}"
                })
                assessment.poam_items.append({
                    "control_id": control_id,
                    "title": control.title,
                    "target_date": None,
                    "milestones": []
                })

        if assessment.controls_assessed > 0:
            implemented = assessment.controls_implemented + (assessment.controls_partial * 0.5)
            assessment.compliance_score = (implemented / assessment.controls_assessed) * 100

        logger.info(
            f"NIST 800-171 Assessment: {assessment.compliance_score:.1f}% compliant "
            f"({assessment.controls_implemented}/{assessment.controls_assessed} implemented)"
        )

        return assessment

    def generate_ssp(self) -> Dict[str, Any]:
        """
        Generate System Security Plan (SSP) document structure.

        Reference: NIST SP 800-18
        """
        return {
            "document_type": "System Security Plan",
            "standard": "NIST SP 800-171 Rev 2",
            "generated": datetime.utcnow().isoformat() + "Z",
            "system_name": "LEGO MCP Manufacturing System",
            "system_description": "Cyber-physical manufacturing system for LEGO brick production",
            "security_controls": [
                {
                    "control_id": c.control_id,
                    "family": c.family.value,
                    "title": c.title,
                    "status": c.status.value,
                    "implementation": c.implementation_notes,
                    "evidence": c.evidence,
                    "assessment_date": c.assessment_date
                }
                for c in self.controls.values()
            ],
            "risk_assessment": {
                "impact_level": "MODERATE",
                "cui_categories": ["CTI", "PRVCY"],
                "data_classification": "CUI//SP-CTI"
            }
        }

    def generate_poam(self) -> Dict[str, Any]:
        """
        Generate Plan of Action and Milestones (POA&M).

        Reference: OMB Circular A-130
        """
        poam_items = []

        for control_id, control in self.controls.items():
            if control.status in (ControlStatus.NOT_IMPLEMENTED, ControlStatus.PARTIALLY_IMPLEMENTED, ControlStatus.PLANNED):
                poam_items.append({
                    "id": control.poam_id or f"POAM-{control_id.replace('.', '-')}",
                    "control_id": control_id,
                    "weakness": f"Control {control_id}: {control.title}",
                    "status": control.status.value,
                    "scheduled_completion": None,
                    "milestones": [],
                    "resources_required": "TBD",
                    "risk_level": "HIGH" if control.status == ControlStatus.NOT_IMPLEMENTED else "MEDIUM"
                })

        return {
            "document_type": "Plan of Action and Milestones",
            "standard": "NIST SP 800-171",
            "generated": datetime.utcnow().isoformat() + "Z",
            "total_items": len(poam_items),
            "high_risk_items": sum(1 for i in poam_items if i["risk_level"] == "HIGH"),
            "items": poam_items
        }
