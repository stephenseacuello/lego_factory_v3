"""
CMMC 2.0 Level 3 Compliance Assessment

Implements Cybersecurity Maturity Model Certification (CMMC)
requirements for defense contractors handling CUI.

Reference: CMMC 2.0 Model, DFARS 252.204-7021
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)


class CMMCLevel(Enum):
    """CMMC 2.0 Maturity Levels."""
    LEVEL_1 = 1  # Foundational - 17 practices (FCI)
    LEVEL_2 = 2  # Advanced - 110 practices (CUI)
    LEVEL_3 = 3  # Expert - 110+ practices (highest CUI sensitivity)


class CMMCDomain(Enum):
    """CMMC 2.0 Domains (aligned with NIST 800-171)."""
    AC = "Access Control"
    AT = "Awareness and Training"
    AU = "Audit and Accountability"
    CA = "Security Assessment"
    CM = "Configuration Management"
    IA = "Identification and Authentication"
    IR = "Incident Response"
    MA = "Maintenance"
    MP = "Media Protection"
    PE = "Physical Protection"
    PS = "Personnel Security"
    RA = "Risk Assessment"
    SC = "System and Communications Protection"
    SI = "System and Information Integrity"


class PracticeStatus(Enum):
    """Practice implementation status."""
    MET = "met"
    NOT_MET = "not_met"
    PARTIALLY_MET = "partially_met"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class CMMCPractice:
    """CMMC Practice definition."""
    practice_id: str
    domain: CMMCDomain
    level: CMMCLevel
    title: str
    description: str
    nist_mapping: List[str] = field(default_factory=list)
    status: PracticeStatus = PracticeStatus.NOT_MET
    implementation: str = ""
    evidence: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    assessment_date: Optional[str] = None


@dataclass
class DomainAssessment:
    """Assessment result for a CMMC domain."""
    domain: CMMCDomain
    practices_total: int = 0
    practices_met: int = 0
    practices_partial: int = 0
    practices_not_met: int = 0
    maturity_score: float = 0.0
    findings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain.value,
            "practices_total": self.practices_total,
            "practices_met": self.practices_met,
            "practices_partial": self.practices_partial,
            "practices_not_met": self.practices_not_met,
            "maturity_score": round(self.maturity_score, 2),
            "findings": self.findings
        }


@dataclass
class CMMCAssessmentResult:
    """Overall CMMC assessment result."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    target_level: CMMCLevel = CMMCLevel.LEVEL_3
    achieved_level: Optional[CMMCLevel] = None
    overall_score: float = 0.0
    domain_assessments: Dict[str, DomainAssessment] = field(default_factory=dict)
    sprs_score: int = 0  # Supplier Performance Risk System score
    poam_required: bool = False
    certification_ready: bool = False
    findings_summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "target_level": self.target_level.value,
            "achieved_level": self.achieved_level.value if self.achieved_level else None,
            "overall_score": round(self.overall_score, 2),
            "sprs_score": self.sprs_score,
            "poam_required": self.poam_required,
            "certification_ready": self.certification_ready,
            "domain_assessments": {
                k: v.to_dict() for k, v in self.domain_assessments.items()
            },
            "findings_summary": self.findings_summary
        }


class CMMCAssessment:
    """
    CMMC 2.0 Level 3 Assessment Framework.

    Implements the Cybersecurity Maturity Model Certification
    requirements for defense contractors.

    Usage:
        >>> assessment = CMMCAssessment(target_level=CMMCLevel.LEVEL_3)
        >>> assessment.load_practices()
        >>> result = assessment.perform_assessment()
        >>> print(f"SPRS Score: {result.sprs_score}")
    """

    # CMMC Level 3 Practices (subset - key practices per domain)
    PRACTICES = {
        # Access Control
        "AC.L2-3.1.1": ("Limit system access", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.1"]),
        "AC.L2-3.1.2": ("Limit transaction types", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.2"]),
        "AC.L2-3.1.3": ("Control CUI flow", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.3"]),
        "AC.L2-3.1.5": ("Least privilege", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.5"]),
        "AC.L2-3.1.7": ("Privileged functions", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.7"]),
        "AC.L2-3.1.12": ("Remote access monitoring", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.12"]),
        "AC.L2-3.1.13": ("Remote access encryption", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.13"]),
        "AC.L2-3.1.20": ("External connections", CMMCDomain.AC, CMMCLevel.LEVEL_2, ["3.1.20"]),

        # Audit and Accountability
        "AU.L2-3.3.1": ("System auditing", CMMCDomain.AU, CMMCLevel.LEVEL_2, ["3.3.1"]),
        "AU.L2-3.3.2": ("User accountability", CMMCDomain.AU, CMMCLevel.LEVEL_2, ["3.3.2"]),
        "AU.L2-3.3.4": ("Audit failure alerting", CMMCDomain.AU, CMMCLevel.LEVEL_2, ["3.3.4"]),
        "AU.L2-3.3.5": ("Audit correlation", CMMCDomain.AU, CMMCLevel.LEVEL_2, ["3.3.5"]),

        # Configuration Management
        "CM.L2-3.4.1": ("Baseline configuration", CMMCDomain.CM, CMMCLevel.LEVEL_2, ["3.4.1"]),
        "CM.L2-3.4.2": ("Security settings", CMMCDomain.CM, CMMCLevel.LEVEL_2, ["3.4.2"]),
        "CM.L2-3.4.6": ("Least functionality", CMMCDomain.CM, CMMCLevel.LEVEL_2, ["3.4.6"]),

        # Identification and Authentication
        "IA.L2-3.5.1": ("Identify users", CMMCDomain.IA, CMMCLevel.LEVEL_2, ["3.5.1"]),
        "IA.L2-3.5.2": ("Authenticate users", CMMCDomain.IA, CMMCLevel.LEVEL_2, ["3.5.2"]),
        "IA.L2-3.5.3": ("Multifactor authentication", CMMCDomain.IA, CMMCLevel.LEVEL_2, ["3.5.3"]),
        "IA.L2-3.5.7": ("Password complexity", CMMCDomain.IA, CMMCLevel.LEVEL_2, ["3.5.7"]),

        # Incident Response
        "IR.L2-3.6.1": ("Incident handling", CMMCDomain.IR, CMMCLevel.LEVEL_2, ["3.6.1"]),
        "IR.L2-3.6.2": ("Incident reporting", CMMCDomain.IR, CMMCLevel.LEVEL_2, ["3.6.2"]),

        # Media Protection
        "MP.L2-3.8.1": ("Media protection", CMMCDomain.MP, CMMCLevel.LEVEL_2, ["3.8.1"]),
        "MP.L2-3.8.3": ("Media sanitization", CMMCDomain.MP, CMMCLevel.LEVEL_2, ["3.8.3"]),
        "MP.L2-3.8.9": ("Backup protection", CMMCDomain.MP, CMMCLevel.LEVEL_2, ["3.8.9"]),

        # Physical Protection
        "PE.L2-3.10.1": ("Physical access", CMMCDomain.PE, CMMCLevel.LEVEL_2, ["3.10.1"]),
        "PE.L2-3.10.2": ("Facility monitoring", CMMCDomain.PE, CMMCLevel.LEVEL_2, ["3.10.2"]),

        # Risk Assessment
        "RA.L2-3.11.1": ("Risk assessment", CMMCDomain.RA, CMMCLevel.LEVEL_2, ["3.11.1"]),
        "RA.L2-3.11.2": ("Vulnerability scanning", CMMCDomain.RA, CMMCLevel.LEVEL_2, ["3.11.2"]),

        # Security Assessment
        "CA.L2-3.12.1": ("Security assessment", CMMCDomain.CA, CMMCLevel.LEVEL_2, ["3.12.1"]),
        "CA.L2-3.12.3": ("Security monitoring", CMMCDomain.CA, CMMCLevel.LEVEL_2, ["3.12.3"]),

        # System and Communications Protection
        "SC.L2-3.13.1": ("Boundary protection", CMMCDomain.SC, CMMCLevel.LEVEL_2, ["3.13.1"]),
        "SC.L2-3.13.8": ("CUI transmission encryption", CMMCDomain.SC, CMMCLevel.LEVEL_2, ["3.13.8"]),
        "SC.L2-3.13.11": ("FIPS cryptography", CMMCDomain.SC, CMMCLevel.LEVEL_2, ["3.13.11"]),

        # System and Information Integrity
        "SI.L2-3.14.1": ("Flaw remediation", CMMCDomain.SI, CMMCLevel.LEVEL_2, ["3.14.1"]),
        "SI.L2-3.14.2": ("Malicious code protection", CMMCDomain.SI, CMMCLevel.LEVEL_2, ["3.14.2"]),
        "SI.L2-3.14.6": ("System monitoring", CMMCDomain.SI, CMMCLevel.LEVEL_2, ["3.14.6"]),
        "SI.L2-3.14.7": ("Unauthorized use detection", CMMCDomain.SI, CMMCLevel.LEVEL_2, ["3.14.7"]),
    }

    # SPRS scoring weights (negative points for unmet practices)
    SPRS_WEIGHTS = {
        "3.1.1": 5, "3.1.2": 5, "3.1.3": 5, "3.1.5": 5, "3.1.7": 5,
        "3.1.12": 5, "3.1.13": 5, "3.1.20": 5,
        "3.3.1": 5, "3.3.2": 5, "3.3.4": 3, "3.3.5": 3,
        "3.4.1": 5, "3.4.2": 5, "3.4.6": 3,
        "3.5.1": 5, "3.5.2": 5, "3.5.3": 5, "3.5.7": 3,
        "3.6.1": 5, "3.6.2": 3,
        "3.8.1": 3, "3.8.3": 3, "3.8.9": 3,
        "3.10.1": 3, "3.10.2": 3,
        "3.11.1": 5, "3.11.2": 5,
        "3.12.1": 5, "3.12.3": 3,
        "3.13.1": 5, "3.13.8": 5, "3.13.11": 5,
        "3.14.1": 5, "3.14.2": 5, "3.14.6": 3, "3.14.7": 3,
    }

    def __init__(self, target_level: CMMCLevel = CMMCLevel.LEVEL_3):
        self.target_level = target_level
        self.practices: Dict[str, CMMCPractice] = {}
        self._init_practices()
        logger.info(f"CMMCAssessment initialized for Level {target_level.value}")

    def _init_practices(self) -> None:
        """Initialize practices from catalog."""
        for practice_id, (title, domain, level, nist_mapping) in self.PRACTICES.items():
            if level.value <= self.target_level.value:
                self.practices[practice_id] = CMMCPractice(
                    practice_id=practice_id,
                    domain=domain,
                    level=level,
                    title=title,
                    description=f"CMMC {practice_id}: {title}",
                    nist_mapping=nist_mapping
                )

    def update_practice_status(
        self,
        practice_id: str,
        status: PracticeStatus,
        implementation: str = "",
        evidence: Optional[List[str]] = None,
        gaps: Optional[List[str]] = None
    ) -> bool:
        """Update status of a practice."""
        if practice_id not in self.practices:
            logger.warning(f"Unknown practice: {practice_id}")
            return False

        practice = self.practices[practice_id]
        practice.status = status
        practice.implementation = implementation
        practice.evidence = evidence or []
        practice.gaps = gaps or []
        practice.assessment_date = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Practice {practice_id} updated to {status.value}")
        return True

    def assess_domain(self, domain: CMMCDomain) -> DomainAssessment:
        """Assess all practices in a domain."""
        assessment = DomainAssessment(domain=domain)

        for practice_id, practice in self.practices.items():
            if practice.domain != domain:
                continue

            assessment.practices_total += 1

            if practice.status == PracticeStatus.MET:
                assessment.practices_met += 1
            elif practice.status == PracticeStatus.PARTIALLY_MET:
                assessment.practices_partial += 1
            elif practice.status == PracticeStatus.NOT_MET:
                assessment.practices_not_met += 1
                assessment.findings.append({
                    "practice_id": practice_id,
                    "title": practice.title,
                    "severity": "HIGH",
                    "gaps": practice.gaps
                })

        if assessment.practices_total > 0:
            met = assessment.practices_met + (assessment.practices_partial * 0.5)
            assessment.maturity_score = (met / assessment.practices_total) * 100

        return assessment

    def calculate_sprs_score(self) -> int:
        """
        Calculate Supplier Performance Risk System (SPRS) score.

        SPRS Score Range: -203 to 110
        - 110 = All practices implemented
        - Negative = Missing critical practices
        """
        score = 110  # Start with maximum

        for practice_id, practice in self.practices.items():
            if practice.status in (PracticeStatus.NOT_MET, PracticeStatus.PARTIALLY_MET):
                # Get NIST control mapping for weight
                for nist_id in practice.nist_mapping:
                    weight = self.SPRS_WEIGHTS.get(nist_id, 3)
                    if practice.status == PracticeStatus.NOT_MET:
                        score -= weight
                    elif practice.status == PracticeStatus.PARTIALLY_MET:
                        score -= (weight // 2)

        return max(-203, score)

    def perform_assessment(self) -> CMMCAssessmentResult:
        """Perform full CMMC assessment."""
        result = CMMCAssessmentResult(target_level=self.target_level)

        # Assess each domain
        for domain in CMMCDomain:
            domain_result = self.assess_domain(domain)
            result.domain_assessments[domain.name] = domain_result

        # Calculate overall metrics
        total_practices = sum(d.practices_total for d in result.domain_assessments.values())
        total_met = sum(d.practices_met for d in result.domain_assessments.values())
        total_partial = sum(d.practices_partial for d in result.domain_assessments.values())
        total_not_met = sum(d.practices_not_met for d in result.domain_assessments.values())

        if total_practices > 0:
            met = total_met + (total_partial * 0.5)
            result.overall_score = (met / total_practices) * 100

        # Calculate SPRS score
        result.sprs_score = self.calculate_sprs_score()

        # Determine achieved level
        if result.overall_score >= 100:
            result.achieved_level = self.target_level
            result.certification_ready = True
        elif result.overall_score >= 80:
            result.achieved_level = CMMCLevel.LEVEL_2
            result.poam_required = True
        elif result.overall_score >= 50:
            result.achieved_level = CMMCLevel.LEVEL_1
            result.poam_required = True

        # Findings summary
        result.findings_summary = {
            "total_practices": total_practices,
            "met": total_met,
            "partially_met": total_partial,
            "not_met": total_not_met,
            "critical_gaps": sum(
                len(d.findings) for d in result.domain_assessments.values()
            )
        }

        logger.info(
            f"CMMC Assessment: {result.overall_score:.1f}% "
            f"(SPRS: {result.sprs_score}, Level: {result.achieved_level})"
        )

        return result

    def generate_gap_analysis(self) -> Dict[str, Any]:
        """Generate detailed gap analysis report."""
        gaps_by_domain: Dict[str, List[Dict]] = {}
        remediation_priority: List[Dict] = []

        for practice_id, practice in self.practices.items():
            if practice.status not in (PracticeStatus.NOT_MET, PracticeStatus.PARTIALLY_MET):
                continue

            domain_name = practice.domain.name
            if domain_name not in gaps_by_domain:
                gaps_by_domain[domain_name] = []

            gap_entry = {
                "practice_id": practice_id,
                "title": practice.title,
                "status": practice.status.value,
                "nist_mapping": practice.nist_mapping,
                "gaps": practice.gaps,
                "sprs_impact": sum(
                    self.SPRS_WEIGHTS.get(n, 3) for n in practice.nist_mapping
                )
            }

            gaps_by_domain[domain_name].append(gap_entry)

            # Add to priority list if high impact
            if gap_entry["sprs_impact"] >= 5:
                remediation_priority.append(gap_entry)

        # Sort by SPRS impact
        remediation_priority.sort(key=lambda x: x["sprs_impact"], reverse=True)

        return {
            "generated": datetime.utcnow().isoformat() + "Z",
            "target_level": self.target_level.value,
            "gaps_by_domain": gaps_by_domain,
            "total_gaps": sum(len(gaps) for gaps in gaps_by_domain.values()),
            "remediation_priority": remediation_priority[:20],  # Top 20
            "estimated_sprs_improvement": sum(
                g["sprs_impact"] for g in remediation_priority[:10]
            )
        }

    def generate_ssp_mapping(self) -> Dict[str, Any]:
        """Generate System Security Plan mapping for CMMC."""
        return {
            "document_type": "CMMC System Security Plan",
            "framework": "CMMC 2.0",
            "target_level": self.target_level.value,
            "generated": datetime.utcnow().isoformat() + "Z",
            "system_name": "LEGO MCP Manufacturing System",
            "cui_handling": True,
            "practices": [
                {
                    "practice_id": p.practice_id,
                    "domain": p.domain.value,
                    "level": p.level.value,
                    "title": p.title,
                    "status": p.status.value,
                    "implementation": p.implementation,
                    "nist_mapping": p.nist_mapping,
                    "evidence": p.evidence
                }
                for p in self.practices.values()
            ],
            "dfars_compliance": {
                "clause": "252.204-7012",
                "adequate_security": result.overall_score >= 80
                    if (result := self.perform_assessment()) else False,
                "cyber_incident_reporting": True,
                "cloud_computing_requirements": True
            }
        }
