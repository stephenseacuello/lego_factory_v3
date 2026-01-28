"""
Internal Audit Service for ISO 9001/13485 Compliance.

Implements comprehensive audit program management with
scheduling, execution, finding tracking, and reporting.

Research Value:
- AI-assisted audit planning
- Risk-based audit prioritization
- Automated finding classification

References:
- ISO 9001:2015 Section 9.2 (Internal Audit)
- ISO 13485:2016 Section 8.2.4 (Internal Audit)
- ISO 19011:2018 (Guidelines for Auditing)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto
from datetime import datetime, timedelta
import uuid
import random
import math


class AuditType(Enum):
    """Types of internal audits."""
    SYSTEM = auto()          # Full QMS audit
    PROCESS = auto()         # Single process audit
    PRODUCT = auto()         # Product-specific audit
    COMPLIANCE = auto()      # Regulatory compliance audit
    SUPPLIER = auto()        # Supplier audit
    FOLLOW_UP = auto()       # Follow-up on previous findings
    SURVEILLANCE = auto()    # Ongoing monitoring


class AuditStatus(Enum):
    """Audit lifecycle status."""
    PLANNED = auto()
    SCHEDULED = auto()
    IN_PROGRESS = auto()
    REPORT_DRAFT = auto()
    REPORT_REVIEW = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class FindingSeverity(Enum):
    """Severity levels for audit findings."""
    MAJOR_NONCONFORMITY = 1     # System failure, immediate action required
    MINOR_NONCONFORMITY = 2     # Isolated deviation, corrective action required
    OBSERVATION = 3             # Potential improvement, no action required
    OPPORTUNITY_FOR_IMPROVEMENT = 4  # Recommendation for enhancement
    POSITIVE_FINDING = 5        # Best practice identified


@dataclass
class AuditFinding:
    """Individual audit finding."""

    finding_id: str
    audit_id: str
    finding_number: str  # e.g., "F-001"
    severity: FindingSeverity

    # Finding details
    clause_reference: str  # ISO clause
    process_area: str
    finding_statement: str
    objective_evidence: str

    # Risk assessment
    risk_level: str = "Medium"  # Low, Medium, High
    recurrence: bool = False  # Previously identified

    # Corrective action linkage
    capa_required: bool = False
    capa_reference: Optional[str] = None

    # Status tracking
    status: str = "Open"  # Open, In Progress, Closed, Verified
    response_due_date: Optional[datetime] = None
    closure_date: Optional[datetime] = None

    # Auditee response
    auditee_response: Optional[str] = None
    proposed_action: Optional[str] = None

    # Verification
    verified_by: Optional[str] = None
    verification_date: Optional[datetime] = None
    verification_evidence: Optional[str] = None

    def get_priority_score(self) -> int:
        """Calculate priority score for finding."""
        severity_score = 5 - self.severity.value  # Higher for major NC
        risk_multiplier = {"High": 3, "Medium": 2, "Low": 1}.get(self.risk_level, 2)
        recurrence_bonus = 2 if self.recurrence else 0

        return severity_score * risk_multiplier + recurrence_bonus


@dataclass
class AuditChecklist:
    """Audit checklist for specific process/area."""

    checklist_id: str
    checklist_name: str
    applicable_standard: str  # e.g., "ISO 9001:2015"

    # Checklist items
    items: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    version: str = "1.0"
    last_updated: datetime = field(default_factory=datetime.now)
    created_by: str = ""

    def add_item(
        self,
        clause: str,
        requirement: str,
        question: str,
        evidence_expected: str
    ):
        """Add checklist item."""
        self.items.append({
            "item_id": str(uuid.uuid4()),
            "clause": clause,
            "requirement": requirement,
            "question": question,
            "evidence_expected": evidence_expected,
            "response": None,  # Conforming, Non-conforming, N/A
            "evidence_found": None,
            "notes": None,
        })

    def get_completion_rate(self) -> float:
        """Get checklist completion rate."""
        if not self.items:
            return 0.0

        completed = sum(1 for item in self.items if item.get("response"))
        return completed / len(self.items) * 100


@dataclass
class InternalAudit:
    """Internal audit record."""

    audit_id: str
    audit_number: str  # e.g., "IA-2024-001"
    audit_type: AuditType
    status: AuditStatus

    # Scope
    audit_scope: str
    processes_audited: List[str]
    clauses_covered: List[str]
    departments: List[str]

    # Dates
    planned_date: datetime
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Team
    lead_auditor: str = ""
    audit_team: List[str] = field(default_factory=list)
    auditees: List[str] = field(default_factory=list)

    # Execution
    checklists: List[AuditChecklist] = field(default_factory=list)
    findings: List[AuditFinding] = field(default_factory=list)

    # Report
    executive_summary: str = ""
    conclusion: str = ""  # "Conforming", "Minor NCs", "Major NCs"
    audit_score: Optional[float] = None  # 0-100

    # Approvals
    approvals: List[Dict[str, Any]] = field(default_factory=list)

    # Audit trail
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def add_audit_entry(self, action: str, user: str, details: str = ""):
        """Add entry to audit trail."""
        self.audit_trail.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user": user,
            "details": details,
        })

    def add_finding(
        self,
        severity: FindingSeverity,
        clause: str,
        process_area: str,
        statement: str,
        evidence: str
    ) -> AuditFinding:
        """Add audit finding."""
        finding_num = len(self.findings) + 1

        finding = AuditFinding(
            finding_id=str(uuid.uuid4()),
            audit_id=self.audit_id,
            finding_number=f"F-{finding_num:03d}",
            severity=severity,
            clause_reference=clause,
            process_area=process_area,
            finding_statement=statement,
            objective_evidence=evidence,
            capa_required=severity in [
                FindingSeverity.MAJOR_NONCONFORMITY,
                FindingSeverity.MINOR_NONCONFORMITY
            ],
        )

        # Set due date based on severity
        if severity == FindingSeverity.MAJOR_NONCONFORMITY:
            finding.response_due_date = datetime.now() + timedelta(days=30)
        elif severity == FindingSeverity.MINOR_NONCONFORMITY:
            finding.response_due_date = datetime.now() + timedelta(days=60)

        self.findings.append(finding)

        return finding

    def get_findings_summary(self) -> Dict[str, Any]:
        """Get summary of audit findings."""
        summary = {
            "total": len(self.findings),
            "by_severity": {},
            "open": 0,
            "closed": 0,
            "capa_required": 0,
        }

        for finding in self.findings:
            sev = finding.severity.name
            summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1

            if finding.status in ["Open", "In Progress"]:
                summary["open"] += 1
            else:
                summary["closed"] += 1

            if finding.capa_required:
                summary["capa_required"] += 1

        return summary

    def calculate_audit_score(self) -> float:
        """Calculate overall audit conformance score."""
        if not self.checklists:
            return 100.0

        total_items = 0
        conforming = 0

        for checklist in self.checklists:
            for item in checklist.items:
                if item.get("response") not in [None, "N/A"]:
                    total_items += 1
                    if item.get("response") == "Conforming":
                        conforming += 1

        if total_items == 0:
            return 100.0

        # Deduct for findings
        penalty = 0
        for finding in self.findings:
            if finding.severity == FindingSeverity.MAJOR_NONCONFORMITY:
                penalty += 10
            elif finding.severity == FindingSeverity.MINOR_NONCONFORMITY:
                penalty += 5
            elif finding.severity == FindingSeverity.OBSERVATION:
                penalty += 1

        base_score = (conforming / total_items) * 100
        self.audit_score = max(0, base_score - penalty)

        return self.audit_score


class AuditScheduler:
    """
    Audit scheduling and planning service.

    Implements risk-based audit scheduling per ISO 19011.
    """

    def __init__(self):
        # Risk scores for processes (higher = more frequent audits)
        self.process_risks: Dict[str, float] = {}

        # Previous audit results influence frequency
        self.process_history: Dict[str, List[Dict[str, Any]]] = {}

    def calculate_process_risk(
        self,
        process_name: str,
        impact: int,  # 1-5
        complexity: int,  # 1-5
        change_frequency: int,  # 1-5
        previous_findings: int = 0
    ) -> float:
        """Calculate risk score for process."""
        base_risk = (impact + complexity + change_frequency) / 3

        # Adjust for history
        history_factor = 1.0 + (previous_findings * 0.1)

        risk_score = base_risk * history_factor

        self.process_risks[process_name] = min(5.0, risk_score)

        return self.process_risks[process_name]

    def get_recommended_frequency(self, process_name: str) -> int:
        """Get recommended audit frequency in months."""
        risk = self.process_risks.get(process_name, 3.0)

        if risk >= 4.0:
            return 3   # Quarterly
        elif risk >= 3.0:
            return 6   # Semi-annually
        elif risk >= 2.0:
            return 12  # Annually
        else:
            return 24  # Biannually

    def generate_annual_plan(
        self,
        year: int,
        processes: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate annual audit plan."""
        plan = []
        audit_counter = 0

        for process in processes:
            frequency = self.get_recommended_frequency(process)
            audits_per_year = 12 // frequency

            for i in range(audits_per_year):
                audit_counter += 1
                month = (i * frequency) + 1

                plan.append({
                    "audit_number": f"IA-{year}-{audit_counter:03d}",
                    "process": process,
                    "planned_month": month,
                    "planned_date": datetime(year, min(12, month), 15),
                    "risk_level": self._risk_to_level(self.process_risks.get(process, 3.0)),
                    "estimated_duration": self._estimate_duration(process),
                })

        # Sort by date
        plan.sort(key=lambda x: x["planned_date"])

        return plan

    def _risk_to_level(self, risk: float) -> str:
        """Convert risk score to level."""
        if risk >= 4.0:
            return "High"
        elif risk >= 2.5:
            return "Medium"
        else:
            return "Low"

    def _estimate_duration(self, process: str) -> int:
        """Estimate audit duration in hours."""
        risk = self.process_risks.get(process, 3.0)
        return int(4 + risk * 2)  # 4-14 hours based on risk


class ISO9001AuditProgram:
    """
    ISO 9001:2015 Internal Audit Program.

    Manages complete audit lifecycle per ISO requirements.
    """

    def __init__(self):
        self.audits: Dict[str, InternalAudit] = {}
        self.scheduler = AuditScheduler()
        self.audit_counter = 0

        # ISO 9001 audit checklist template
        self.iso9001_checklist = self._create_iso9001_checklist()

    def _create_iso9001_checklist(self) -> AuditChecklist:
        """Create ISO 9001:2015 audit checklist."""
        checklist = AuditChecklist(
            checklist_id=str(uuid.uuid4()),
            checklist_name="ISO 9001:2015 Full Audit",
            applicable_standard="ISO 9001:2015",
        )

        # Section 4 - Context
        checklist.add_item(
            "4.1", "Understanding the organization",
            "How does the organization determine external and internal issues?",
            "Strategic planning documents, SWOT analysis"
        )
        checklist.add_item(
            "4.2", "Interested parties",
            "How are interested parties and their requirements determined?",
            "Stakeholder register, requirement analysis"
        )
        checklist.add_item(
            "4.3", "QMS Scope",
            "Is the QMS scope documented and available?",
            "Quality Manual, scope statement"
        )
        checklist.add_item(
            "4.4", "QMS Processes",
            "Are processes needed for the QMS determined?",
            "Process maps, turtle diagrams"
        )

        # Section 5 - Leadership
        checklist.add_item(
            "5.1", "Leadership commitment",
            "How does top management demonstrate leadership?",
            "Management review minutes, resource allocation"
        )
        checklist.add_item(
            "5.2", "Quality Policy",
            "Is the quality policy appropriate and communicated?",
            "Quality policy document, communication records"
        )
        checklist.add_item(
            "5.3", "Roles and responsibilities",
            "Are QMS roles and responsibilities assigned?",
            "Organization chart, job descriptions"
        )

        # Section 6 - Planning
        checklist.add_item(
            "6.1", "Risk management",
            "How are risks and opportunities addressed?",
            "Risk register, risk assessment records"
        )
        checklist.add_item(
            "6.2", "Quality objectives",
            "Are quality objectives established and measured?",
            "Quality objectives, KPI dashboards"
        )
        checklist.add_item(
            "6.3", "Change management",
            "How are changes to the QMS planned?",
            "Change request forms, MOC procedures"
        )

        # Section 7 - Support
        checklist.add_item(
            "7.1", "Resources",
            "Are resources for QMS determined and provided?",
            "Budget records, resource plans"
        )
        checklist.add_item(
            "7.2", "Competence",
            "How is competence ensured?",
            "Training records, competency matrices"
        )
        checklist.add_item(
            "7.5", "Documented information",
            "Is documented information controlled?",
            "Document control procedures, version logs"
        )

        # Section 8 - Operation
        checklist.add_item(
            "8.1", "Operational planning",
            "Are operational processes planned?",
            "Work orders, production plans"
        )
        checklist.add_item(
            "8.4", "External providers",
            "Are external providers controlled?",
            "Supplier evaluations, approved supplier list"
        )
        checklist.add_item(
            "8.5", "Production control",
            "Are production processes controlled?",
            "Work instructions, process parameters"
        )
        checklist.add_item(
            "8.6", "Release of products",
            "How are products released?",
            "Inspection records, release criteria"
        )
        checklist.add_item(
            "8.7", "Nonconforming outputs",
            "How are nonconformities handled?",
            "NCR records, disposition records"
        )

        # Section 9 - Performance
        checklist.add_item(
            "9.1", "Monitoring and measurement",
            "How is QMS performance monitored?",
            "KPI reports, customer satisfaction data"
        )
        checklist.add_item(
            "9.2", "Internal audit",
            "Is the internal audit program effective?",
            "Audit schedule, audit reports"
        )
        checklist.add_item(
            "9.3", "Management review",
            "Are management reviews conducted?",
            "Management review minutes, action items"
        )

        # Section 10 - Improvement
        checklist.add_item(
            "10.2", "Nonconformity and corrective action",
            "Is the CAPA process effective?",
            "CAPA records, effectiveness reviews"
        )
        checklist.add_item(
            "10.3", "Continual improvement",
            "Is the organization continually improving?",
            "Improvement projects, trend analysis"
        )

        return checklist

    def generate_audit_number(self) -> str:
        """Generate unique audit number."""
        self.audit_counter += 1
        year = datetime.now().year
        return f"IA-{year}-{self.audit_counter:03d}"

    def plan_audit(
        self,
        audit_type: AuditType,
        scope: str,
        processes: List[str],
        clauses: List[str],
        departments: List[str],
        planned_date: datetime,
        lead_auditor: str
    ) -> InternalAudit:
        """Plan a new internal audit."""
        audit_id = str(uuid.uuid4())
        audit_number = self.generate_audit_number()

        audit = InternalAudit(
            audit_id=audit_id,
            audit_number=audit_number,
            audit_type=audit_type,
            status=AuditStatus.PLANNED,
            audit_scope=scope,
            processes_audited=processes,
            clauses_covered=clauses,
            departments=departments,
            planned_date=planned_date,
            lead_auditor=lead_auditor,
        )

        # Clone ISO 9001 checklist for this audit
        checklist = AuditChecklist(
            checklist_id=str(uuid.uuid4()),
            checklist_name=f"Checklist for {audit_number}",
            applicable_standard="ISO 9001:2015",
            items=[item.copy() for item in self.iso9001_checklist.items
                   if any(clause in item["clause"] for clause in clauses)]
        )
        audit.checklists.append(checklist)

        audit.add_audit_entry("Planned", lead_auditor, f"Audit {audit_number} planned")

        self.audits[audit_id] = audit

        return audit

    def schedule_audit(
        self,
        audit_id: str,
        start_date: datetime,
        end_date: datetime,
        audit_team: List[str],
        auditees: List[str]
    ) -> Dict[str, Any]:
        """Schedule audit with dates and team."""
        if audit_id not in self.audits:
            return {"success": False, "error": "Audit not found"}

        audit = self.audits[audit_id]

        audit.scheduled_start = start_date
        audit.scheduled_end = end_date
        audit.audit_team = audit_team
        audit.auditees = auditees
        audit.status = AuditStatus.SCHEDULED

        audit.add_audit_entry(
            "Scheduled",
            audit.lead_auditor,
            f"Scheduled for {start_date.date()} to {end_date.date()}"
        )

        return {
            "success": True,
            "audit_number": audit.audit_number,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

    def start_audit(
        self,
        audit_id: str,
        lead_auditor: str
    ) -> Dict[str, Any]:
        """Start audit execution."""
        if audit_id not in self.audits:
            return {"success": False, "error": "Audit not found"}

        audit = self.audits[audit_id]

        if audit.status not in [AuditStatus.SCHEDULED, AuditStatus.PLANNED]:
            return {"success": False, "error": f"Cannot start audit in {audit.status.name} status"}

        audit.actual_start = datetime.now()
        audit.status = AuditStatus.IN_PROGRESS

        audit.add_audit_entry("Started", lead_auditor, "Audit execution began")

        return {
            "success": True,
            "audit_number": audit.audit_number,
            "checklist_items": sum(len(c.items) for c in audit.checklists),
        }

    def record_checklist_response(
        self,
        audit_id: str,
        item_id: str,
        response: str,
        evidence_found: str,
        notes: str,
        auditor: str
    ) -> Dict[str, Any]:
        """Record response to checklist item."""
        if audit_id not in self.audits:
            return {"success": False, "error": "Audit not found"}

        audit = self.audits[audit_id]

        for checklist in audit.checklists:
            for item in checklist.items:
                if item["item_id"] == item_id:
                    item["response"] = response
                    item["evidence_found"] = evidence_found
                    item["notes"] = notes
                    item["auditor"] = auditor
                    item["recorded_at"] = datetime.now().isoformat()

                    return {
                        "success": True,
                        "completion_rate": checklist.get_completion_rate(),
                    }

        return {"success": False, "error": "Item not found"}

    def record_finding(
        self,
        audit_id: str,
        severity: FindingSeverity,
        clause: str,
        process_area: str,
        statement: str,
        evidence: str,
        auditor: str
    ) -> AuditFinding:
        """Record audit finding."""
        if audit_id not in self.audits:
            raise ValueError("Audit not found")

        audit = self.audits[audit_id]

        # Check for recurrence
        recurrence = self._check_recurrence(process_area, clause)

        finding = audit.add_finding(severity, clause, process_area, statement, evidence)
        finding.recurrence = recurrence

        # Determine risk level
        finding.risk_level = self._assess_finding_risk(severity, recurrence)

        audit.add_audit_entry(
            "Finding recorded",
            auditor,
            f"{severity.name}: {statement[:50]}..."
        )

        return finding

    def _check_recurrence(self, process: str, clause: str) -> bool:
        """Check if similar finding was recorded before."""
        for audit in self.audits.values():
            if audit.status == AuditStatus.COMPLETED:
                for finding in audit.findings:
                    if (finding.process_area == process and
                        finding.clause_reference == clause):
                        return True
        return False

    def _assess_finding_risk(
        self,
        severity: FindingSeverity,
        recurrence: bool
    ) -> str:
        """Assess risk level of finding."""
        if severity == FindingSeverity.MAJOR_NONCONFORMITY:
            return "High"
        elif severity == FindingSeverity.MINOR_NONCONFORMITY:
            return "High" if recurrence else "Medium"
        else:
            return "Medium" if recurrence else "Low"

    def complete_audit(
        self,
        audit_id: str,
        summary: str,
        lead_auditor: str
    ) -> Dict[str, Any]:
        """Complete audit and generate report."""
        if audit_id not in self.audits:
            return {"success": False, "error": "Audit not found"}

        audit = self.audits[audit_id]

        audit.actual_end = datetime.now()
        audit.executive_summary = summary

        # Calculate score
        score = audit.calculate_audit_score()

        # Determine conclusion
        findings_summary = audit.get_findings_summary()
        major_ncs = findings_summary["by_severity"].get("MAJOR_NONCONFORMITY", 0)
        minor_ncs = findings_summary["by_severity"].get("MINOR_NONCONFORMITY", 0)

        if major_ncs > 0:
            audit.conclusion = "Major Nonconformities - Immediate Action Required"
        elif minor_ncs > 0:
            audit.conclusion = "Minor Nonconformities - Corrective Action Required"
        else:
            audit.conclusion = "Conforming - Continue Current Practices"

        audit.status = AuditStatus.REPORT_DRAFT

        audit.add_audit_entry("Completed", lead_auditor, f"Score: {score:.1f}%")

        return {
            "success": True,
            "audit_number": audit.audit_number,
            "score": round(score, 1),
            "conclusion": audit.conclusion,
            "findings": findings_summary,
            "duration_days": (audit.actual_end - audit.actual_start).days if audit.actual_start else 0,
        }

    def approve_report(
        self,
        audit_id: str,
        approver: str,
        comments: str = ""
    ) -> Dict[str, Any]:
        """Approve audit report."""
        if audit_id not in self.audits:
            return {"success": False, "error": "Audit not found"}

        audit = self.audits[audit_id]

        audit.approvals.append({
            "approver": approver,
            "date": datetime.now().isoformat(),
            "comments": comments,
        })

        audit.status = AuditStatus.COMPLETED

        audit.add_audit_entry("Report approved", approver, comments)

        return {
            "success": True,
            "audit_number": audit.audit_number,
            "status": "Completed",
        }

    def get_program_metrics(self) -> Dict[str, Any]:
        """Get audit program metrics."""
        if not self.audits:
            return {"total_audits": 0}

        all_audits = list(self.audits.values())
        completed = [a for a in all_audits if a.status == AuditStatus.COMPLETED]

        # Finding statistics
        total_findings = sum(len(a.findings) for a in completed)
        major_ncs = sum(
            sum(1 for f in a.findings if f.severity == FindingSeverity.MAJOR_NONCONFORMITY)
            for a in completed
        )
        minor_ncs = sum(
            sum(1 for f in a.findings if f.severity == FindingSeverity.MINOR_NONCONFORMITY)
            for a in completed
        )

        # Open findings
        open_findings = sum(
            sum(1 for f in a.findings if f.status in ["Open", "In Progress"])
            for a in all_audits
        )

        # Average score
        scores = [a.audit_score for a in completed if a.audit_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0

        return {
            "total_audits": len(all_audits),
            "completed_audits": len(completed),
            "planned_audits": sum(1 for a in all_audits if a.status == AuditStatus.PLANNED),
            "in_progress": sum(1 for a in all_audits if a.status == AuditStatus.IN_PROGRESS),
            "total_findings": total_findings,
            "major_nonconformities": major_ncs,
            "minor_nonconformities": minor_ncs,
            "open_findings": open_findings,
            "average_score": round(avg_score, 1),
            "year": datetime.now().year,
        }

    def generate_annual_report(self, year: int) -> Dict[str, Any]:
        """Generate annual audit program report."""
        year_audits = [
            a for a in self.audits.values()
            if a.planned_date.year == year and a.status == AuditStatus.COMPLETED
        ]

        # Trend analysis
        scores_by_quarter = {1: [], 2: [], 3: [], 4: []}
        for audit in year_audits:
            if audit.audit_score is not None and audit.actual_end:
                quarter = (audit.actual_end.month - 1) // 3 + 1
                scores_by_quarter[quarter].append(audit.audit_score)

        quarterly_avg = {
            f"Q{q}": round(sum(s) / len(s), 1) if s else None
            for q, s in scores_by_quarter.items()
        }

        # Most common finding areas
        finding_areas = {}
        for audit in year_audits:
            for finding in audit.findings:
                area = finding.process_area
                finding_areas[area] = finding_areas.get(area, 0) + 1

        top_areas = sorted(finding_areas.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "year": year,
            "audits_completed": len(year_audits),
            "total_findings": sum(len(a.findings) for a in year_audits),
            "quarterly_scores": quarterly_avg,
            "top_finding_areas": dict(top_areas),
            "program_effectiveness": self._calculate_program_effectiveness(year_audits),
            "recommendations": self._generate_recommendations(year_audits),
        }

    def _calculate_program_effectiveness(self, audits: List[InternalAudit]) -> str:
        """Calculate overall program effectiveness."""
        if not audits:
            return "Insufficient data"

        avg_score = sum(a.audit_score or 0 for a in audits) / len(audits)

        if avg_score >= 90:
            return "Highly Effective"
        elif avg_score >= 75:
            return "Effective"
        elif avg_score >= 60:
            return "Partially Effective"
        else:
            return "Requires Improvement"

    def _generate_recommendations(self, audits: List[InternalAudit]) -> List[str]:
        """Generate recommendations based on audit results."""
        recommendations = []

        # Analyze findings
        all_findings = [f for a in audits for f in a.findings]
        recurring = [f for f in all_findings if f.recurrence]

        if recurring:
            recommendations.append(
                f"Address {len(recurring)} recurring findings through enhanced CAPA process"
            )

        # Check for process areas with multiple findings
        areas = {}
        for f in all_findings:
            areas[f.process_area] = areas.get(f.process_area, 0) + 1

        problem_areas = [area for area, count in areas.items() if count >= 3]
        if problem_areas:
            recommendations.append(
                f"Focus improvement efforts on: {', '.join(problem_areas)}"
            )

        # Check audit coverage
        if len(audits) < 4:
            recommendations.append("Increase audit frequency to ensure adequate coverage")

        if not recommendations:
            recommendations.append("Maintain current audit program effectiveness")

        return recommendations


# Module exports
__all__ = [
    "AuditType",
    "AuditStatus",
    "FindingSeverity",
    "AuditFinding",
    "AuditChecklist",
    "InternalAudit",
    "AuditScheduler",
    "ISO9001AuditProgram",
]
