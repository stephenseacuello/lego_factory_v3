"""
CAPA (Corrective and Preventive Action) Service.

ISO 9001:2015 Section 10.2 and ISO 13485:2016 Section 8.5
compliant corrective and preventive action management.

Research Value:
- AI-assisted root cause analysis
- Predictive CAPA analytics
- Cross-functional effectiveness tracking

References:
- ISO 9001:2015 Section 10.2 (Nonconformity and Corrective Action)
- ISO 13485:2016 Section 8.5 (Improvement)
- FDA 21 CFR 820.100 (CAPA)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto
from datetime import datetime, timedelta
import uuid
import math


class CAPAType(Enum):
    """Type of CAPA action."""
    CORRECTIVE = auto()  # Fix existing problem
    PREVENTIVE = auto()  # Prevent potential problem
    COMBINED = auto()    # Both corrective and preventive


class CAPAStatus(Enum):
    """CAPA lifecycle status."""
    INITIATED = auto()
    INVESTIGATION = auto()
    ROOT_CAUSE_ANALYSIS = auto()
    ACTION_PLANNING = auto()
    IMPLEMENTATION = auto()
    VERIFICATION = auto()
    EFFECTIVENESS_REVIEW = auto()
    CLOSED = auto()
    CANCELLED = auto()


class CAPAPriority(Enum):
    """CAPA priority levels."""
    CRITICAL = 1    # Patient safety, regulatory
    HIGH = 2        # Significant quality impact
    MEDIUM = 3      # Moderate quality impact
    LOW = 4         # Minor improvement


class RootCauseCategory(Enum):
    """Root cause categories for analysis."""
    # Equipment related
    EQUIPMENT_FAILURE = auto()
    EQUIPMENT_CALIBRATION = auto()
    EQUIPMENT_MAINTENANCE = auto()

    # Process related
    PROCESS_CAPABILITY = auto()
    PROCESS_CONTROL = auto()
    PROCESS_DESIGN = auto()

    # Material related
    MATERIAL_DEFECT = auto()
    MATERIAL_HANDLING = auto()
    MATERIAL_SPECIFICATION = auto()

    # Human related
    TRAINING = auto()
    PROCEDURE_COMPLIANCE = auto()
    WORKLOAD = auto()
    COMMUNICATION = auto()

    # Environmental
    ENVIRONMENTAL_CONDITIONS = auto()
    CONTAMINATION = auto()

    # System related
    SOFTWARE_ERROR = auto()
    SYSTEM_DESIGN = auto()
    DOCUMENTATION = auto()

    # Supplier related
    SUPPLIER_QUALITY = auto()
    SUPPLIER_CHANGE = auto()


@dataclass
class RootCauseAnalysis:
    """Root cause analysis findings."""

    analysis_id: str
    method_used: str  # "5 Whys", "Fishbone", "Fault Tree", "FMEA"
    performed_by: str
    performed_date: datetime

    # Findings
    problem_statement: str
    immediate_cause: str
    root_cause: str
    root_cause_category: RootCauseCategory
    contributing_factors: List[str] = field(default_factory=list)

    # Evidence
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    analysis_steps: List[str] = field(default_factory=list)

    # Confidence
    confidence_level: float = 0.8  # 0-1

    def add_why(self, question: str, answer: str):
        """Add a why step (5 Whys method)."""
        step_num = len(self.analysis_steps) + 1
        self.analysis_steps.append(f"Why {step_num}: {question} → {answer}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "method": self.method_used,
            "performed_by": self.performed_by,
            "date": self.performed_date.isoformat(),
            "problem_statement": self.problem_statement,
            "immediate_cause": self.immediate_cause,
            "root_cause": self.root_cause,
            "category": self.root_cause_category.name,
            "contributing_factors": self.contributing_factors,
            "analysis_steps": self.analysis_steps,
            "confidence": self.confidence_level,
        }


@dataclass
class EffectivenessReview:
    """CAPA effectiveness review."""

    review_id: str
    capa_id: str
    reviewer: str
    review_date: datetime

    # Review criteria
    objectives_met: bool
    recurrence_prevented: bool
    similar_issues_addressed: bool

    # Evidence
    verification_method: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    # Metrics
    metrics_before: Dict[str, float] = field(default_factory=dict)
    metrics_after: Dict[str, float] = field(default_factory=dict)

    # Conclusion
    effective: bool = False
    comments: str = ""
    follow_up_required: bool = False
    follow_up_actions: List[str] = field(default_factory=list)

    def calculate_improvement(self) -> Dict[str, float]:
        """Calculate improvement in metrics."""
        improvements = {}

        for key in self.metrics_before:
            if key in self.metrics_after:
                before = self.metrics_before[key]
                after = self.metrics_after[key]

                if before != 0:
                    pct_change = (after - before) / abs(before) * 100
                else:
                    pct_change = 100 if after > 0 else 0

                improvements[key] = round(pct_change, 2)

        return improvements


@dataclass
class CAPA:
    """Corrective and Preventive Action record."""

    capa_id: str
    capa_number: str  # e.g., "CAPA-2024-001"
    capa_type: CAPAType
    status: CAPAStatus
    priority: CAPAPriority

    # Source information
    source_type: str  # "Customer Complaint", "Audit", "NCR", "Trend Analysis"
    source_reference: str
    initiated_by: str
    initiated_date: datetime

    # Problem description
    problem_title: str
    problem_description: str
    affected_products: List[str] = field(default_factory=list)
    affected_processes: List[str] = field(default_factory=list)
    affected_departments: List[str] = field(default_factory=list)

    # Investigation
    investigation_team: List[str] = field(default_factory=list)
    investigation_findings: str = ""
    containment_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Root cause
    root_cause_analysis: Optional[RootCauseAnalysis] = None

    # Actions
    corrective_actions: List[Dict[str, Any]] = field(default_factory=list)
    preventive_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Effectiveness
    effectiveness_review: Optional[EffectivenessReview] = None
    effectiveness_check_date: Optional[datetime] = None

    # Dates
    target_closure_date: Optional[datetime] = None
    actual_closure_date: Optional[datetime] = None

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
            "status": self.status.name,
        })

    def add_containment_action(
        self,
        description: str,
        responsible: str,
        due_date: datetime
    ):
        """Add containment action."""
        self.containment_actions.append({
            "id": str(uuid.uuid4()),
            "description": description,
            "responsible": responsible,
            "due_date": due_date.isoformat(),
            "status": "Open",
            "completion_date": None,
        })

    def add_corrective_action(
        self,
        description: str,
        responsible: str,
        due_date: datetime,
        verification_method: str
    ):
        """Add corrective action."""
        self.corrective_actions.append({
            "id": str(uuid.uuid4()),
            "description": description,
            "responsible": responsible,
            "due_date": due_date.isoformat(),
            "verification_method": verification_method,
            "status": "Planned",
            "completion_date": None,
            "evidence": [],
        })

    def add_preventive_action(
        self,
        description: str,
        responsible: str,
        due_date: datetime,
        verification_method: str
    ):
        """Add preventive action."""
        self.preventive_actions.append({
            "id": str(uuid.uuid4()),
            "description": description,
            "responsible": responsible,
            "due_date": due_date.isoformat(),
            "verification_method": verification_method,
            "status": "Planned",
            "completion_date": None,
            "evidence": [],
        })

    def get_action_summary(self) -> Dict[str, Any]:
        """Get summary of all actions."""
        def summarize_actions(actions):
            total = len(actions)
            completed = sum(1 for a in actions if a.get("status") == "Completed")
            overdue = sum(
                1 for a in actions
                if a.get("status") != "Completed" and
                datetime.fromisoformat(a["due_date"]) < datetime.now()
            )
            return {"total": total, "completed": completed, "overdue": overdue}

        return {
            "containment": summarize_actions(self.containment_actions),
            "corrective": summarize_actions(self.corrective_actions),
            "preventive": summarize_actions(self.preventive_actions),
        }

    def is_overdue(self) -> bool:
        """Check if CAPA is overdue."""
        if self.status == CAPAStatus.CLOSED:
            return False
        if self.target_closure_date:
            return datetime.now() > self.target_closure_date
        return False

    def get_days_open(self) -> int:
        """Get number of days CAPA has been open."""
        end_date = self.actual_closure_date or datetime.now()
        return (end_date - self.initiated_date).days


class CAPAService:
    """
    CAPA Management Service.

    Manages the complete CAPA lifecycle per ISO requirements.
    """

    def __init__(self):
        self.capas: Dict[str, CAPA] = {}
        self.capa_counter = 0

        # Priority-based due dates (days)
        self.due_date_matrix = {
            CAPAPriority.CRITICAL: {
                "containment": 1,
                "investigation": 7,
                "closure": 30,
            },
            CAPAPriority.HIGH: {
                "containment": 3,
                "investigation": 14,
                "closure": 60,
            },
            CAPAPriority.MEDIUM: {
                "containment": 7,
                "investigation": 30,
                "closure": 90,
            },
            CAPAPriority.LOW: {
                "containment": 14,
                "investigation": 45,
                "closure": 120,
            },
        }

    def generate_capa_number(self) -> str:
        """Generate unique CAPA number."""
        self.capa_counter += 1
        year = datetime.now().year
        return f"CAPA-{year}-{self.capa_counter:04d}"

    def initiate_capa(
        self,
        capa_type: CAPAType,
        priority: CAPAPriority,
        source_type: str,
        source_reference: str,
        problem_title: str,
        problem_description: str,
        initiator: str,
        affected_products: List[str] = None,
        affected_processes: List[str] = None
    ) -> CAPA:
        """Initiate a new CAPA."""
        capa_id = str(uuid.uuid4())
        capa_number = self.generate_capa_number()

        # Calculate target dates
        due_dates = self.due_date_matrix[priority]
        target_closure = datetime.now() + timedelta(days=due_dates["closure"])

        capa = CAPA(
            capa_id=capa_id,
            capa_number=capa_number,
            capa_type=capa_type,
            status=CAPAStatus.INITIATED,
            priority=priority,
            source_type=source_type,
            source_reference=source_reference,
            initiated_by=initiator,
            initiated_date=datetime.now(),
            problem_title=problem_title,
            problem_description=problem_description,
            affected_products=affected_products or [],
            affected_processes=affected_processes or [],
            target_closure_date=target_closure,
        )

        capa.add_audit_entry("Initiated", initiator, f"CAPA {capa_number} created")

        self.capas[capa_id] = capa

        return capa

    def assign_investigation_team(
        self,
        capa_id: str,
        team_members: List[str],
        lead: str
    ) -> Dict[str, Any]:
        """Assign investigation team to CAPA."""
        if capa_id not in self.capas:
            return {"success": False, "error": "CAPA not found"}

        capa = self.capas[capa_id]
        capa.investigation_team = [lead] + [m for m in team_members if m != lead]
        capa.status = CAPAStatus.INVESTIGATION

        capa.add_audit_entry(
            "Team assigned",
            lead,
            f"Investigation team: {', '.join(capa.investigation_team)}"
        )

        return {
            "success": True,
            "team_lead": lead,
            "team_size": len(capa.investigation_team),
        }

    def perform_root_cause_analysis(
        self,
        capa_id: str,
        analyst: str,
        method: str,
        problem_statement: str,
        immediate_cause: str,
        root_cause: str,
        category: RootCauseCategory,
        contributing_factors: List[str] = None,
        analysis_steps: List[str] = None
    ) -> RootCauseAnalysis:
        """Perform and record root cause analysis."""
        if capa_id not in self.capas:
            raise ValueError("CAPA not found")

        capa = self.capas[capa_id]

        analysis = RootCauseAnalysis(
            analysis_id=str(uuid.uuid4()),
            method_used=method,
            performed_by=analyst,
            performed_date=datetime.now(),
            problem_statement=problem_statement,
            immediate_cause=immediate_cause,
            root_cause=root_cause,
            root_cause_category=category,
            contributing_factors=contributing_factors or [],
            analysis_steps=analysis_steps or [],
        )

        capa.root_cause_analysis = analysis
        capa.status = CAPAStatus.ROOT_CAUSE_ANALYSIS

        capa.add_audit_entry(
            "Root cause analysis completed",
            analyst,
            f"Method: {method}, Category: {category.name}"
        )

        return analysis

    def generate_five_whys(
        self,
        capa_id: str,
        analyst: str,
        initial_problem: str,
        whys: List[Tuple[str, str]]
    ) -> RootCauseAnalysis:
        """Generate 5 Whys root cause analysis."""
        if capa_id not in self.capas:
            raise ValueError("CAPA not found")

        if len(whys) < 3:
            raise ValueError("At least 3 'whys' required")

        # Extract root cause from final why
        root_cause = whys[-1][1]

        # Categorize root cause (simplified)
        category = self._categorize_root_cause(root_cause)

        analysis = RootCauseAnalysis(
            analysis_id=str(uuid.uuid4()),
            method_used="5 Whys",
            performed_by=analyst,
            performed_date=datetime.now(),
            problem_statement=initial_problem,
            immediate_cause=whys[0][1],
            root_cause=root_cause,
            root_cause_category=category,
        )

        for question, answer in whys:
            analysis.add_why(question, answer)

        self.capas[capa_id].root_cause_analysis = analysis
        self.capas[capa_id].status = CAPAStatus.ROOT_CAUSE_ANALYSIS

        return analysis

    def _categorize_root_cause(self, root_cause: str) -> RootCauseCategory:
        """Auto-categorize root cause based on keywords."""
        keywords = {
            RootCauseCategory.TRAINING: ["training", "skill", "knowledge", "competenc"],
            RootCauseCategory.PROCEDURE_COMPLIANCE: ["procedure", "instruction", "follow"],
            RootCauseCategory.EQUIPMENT_FAILURE: ["equipment", "machine", "tool", "fail"],
            RootCauseCategory.EQUIPMENT_CALIBRATION: ["calibrat", "accuracy", "drift"],
            RootCauseCategory.MATERIAL_DEFECT: ["material", "defect", "quality"],
            RootCauseCategory.PROCESS_CONTROL: ["process", "control", "parameter"],
            RootCauseCategory.SOFTWARE_ERROR: ["software", "system", "bug", "error"],
            RootCauseCategory.COMMUNICATION: ["communicat", "inform", "notify"],
            RootCauseCategory.SUPPLIER_QUALITY: ["supplier", "vendor", "outsource"],
        }

        root_cause_lower = root_cause.lower()

        for category, words in keywords.items():
            for word in words:
                if word in root_cause_lower:
                    return category

        return RootCauseCategory.PROCESS_DESIGN  # Default

    def plan_actions(
        self,
        capa_id: str,
        planner: str,
        corrective_actions: List[Dict[str, Any]],
        preventive_actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Plan corrective and preventive actions."""
        if capa_id not in self.capas:
            return {"success": False, "error": "CAPA not found"}

        capa = self.capas[capa_id]

        # Add corrective actions
        for action in corrective_actions:
            capa.add_corrective_action(
                description=action["description"],
                responsible=action["responsible"],
                due_date=datetime.fromisoformat(action["due_date"]),
                verification_method=action.get("verification_method", "Inspection"),
            )

        # Add preventive actions
        for action in preventive_actions:
            capa.add_preventive_action(
                description=action["description"],
                responsible=action["responsible"],
                due_date=datetime.fromisoformat(action["due_date"]),
                verification_method=action.get("verification_method", "Audit"),
            )

        capa.status = CAPAStatus.ACTION_PLANNING

        capa.add_audit_entry(
            "Actions planned",
            planner,
            f"Corrective: {len(corrective_actions)}, Preventive: {len(preventive_actions)}"
        )

        return {
            "success": True,
            "corrective_count": len(capa.corrective_actions),
            "preventive_count": len(capa.preventive_actions),
        }

    def complete_action(
        self,
        capa_id: str,
        action_id: str,
        action_type: str,
        completed_by: str,
        evidence: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Mark an action as completed."""
        if capa_id not in self.capas:
            return {"success": False, "error": "CAPA not found"}

        capa = self.capas[capa_id]

        # Find action
        actions = (
            capa.corrective_actions if action_type == "corrective"
            else capa.preventive_actions if action_type == "preventive"
            else capa.containment_actions
        )

        for action in actions:
            if action["id"] == action_id:
                action["status"] = "Completed"
                action["completion_date"] = datetime.now().isoformat()
                action["completed_by"] = completed_by
                action["evidence"] = evidence or []

                capa.add_audit_entry(
                    f"{action_type.capitalize()} action completed",
                    completed_by,
                    action["description"][:50]
                )

                # Check if all actions complete
                if self._all_actions_complete(capa):
                    capa.status = CAPAStatus.VERIFICATION

                return {"success": True, "action_status": "Completed"}

        return {"success": False, "error": "Action not found"}

    def _all_actions_complete(self, capa: CAPA) -> bool:
        """Check if all actions are complete."""
        all_actions = (
            capa.containment_actions +
            capa.corrective_actions +
            capa.preventive_actions
        )

        return all(a.get("status") == "Completed" for a in all_actions)

    def perform_effectiveness_review(
        self,
        capa_id: str,
        reviewer: str,
        objectives_met: bool,
        recurrence_prevented: bool,
        verification_method: str,
        metrics_before: Dict[str, float],
        metrics_after: Dict[str, float],
        comments: str = ""
    ) -> EffectivenessReview:
        """Perform CAPA effectiveness review."""
        if capa_id not in self.capas:
            raise ValueError("CAPA not found")

        capa = self.capas[capa_id]

        review = EffectivenessReview(
            review_id=str(uuid.uuid4()),
            capa_id=capa_id,
            reviewer=reviewer,
            review_date=datetime.now(),
            objectives_met=objectives_met,
            recurrence_prevented=recurrence_prevented,
            similar_issues_addressed=True,
            verification_method=verification_method,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            effective=objectives_met and recurrence_prevented,
            comments=comments,
        )

        capa.effectiveness_review = review
        capa.status = CAPAStatus.EFFECTIVENESS_REVIEW

        capa.add_audit_entry(
            "Effectiveness review completed",
            reviewer,
            f"Effective: {review.effective}"
        )

        return review

    def close_capa(
        self,
        capa_id: str,
        closer: str,
        closure_comments: str = ""
    ) -> Dict[str, Any]:
        """Close CAPA after successful effectiveness review."""
        if capa_id not in self.capas:
            return {"success": False, "error": "CAPA not found"}

        capa = self.capas[capa_id]

        if not capa.effectiveness_review:
            return {"success": False, "error": "Effectiveness review required"}

        if not capa.effectiveness_review.effective:
            return {"success": False, "error": "CAPA not effective - requires additional actions"}

        capa.status = CAPAStatus.CLOSED
        capa.actual_closure_date = datetime.now()

        # Add closure approval
        capa.approvals.append({
            "type": "Closure",
            "approver": closer,
            "date": datetime.now().isoformat(),
            "comments": closure_comments,
        })

        capa.add_audit_entry("Closed", closer, closure_comments)

        return {
            "success": True,
            "capa_number": capa.capa_number,
            "days_to_close": capa.get_days_open(),
            "met_target": not capa.is_overdue(),
        }

    def get_capa_metrics(self) -> Dict[str, Any]:
        """Get CAPA program metrics."""
        if not self.capas:
            return {"total": 0}

        all_capas = list(self.capas.values())

        # Status distribution
        status_dist = {}
        for capa in all_capas:
            status = capa.status.name
            status_dist[status] = status_dist.get(status, 0) + 1

        # Priority distribution
        priority_dist = {}
        for capa in all_capas:
            priority = capa.priority.name
            priority_dist[priority] = priority_dist.get(priority, 0) + 1

        # Root cause distribution
        root_cause_dist = {}
        for capa in all_capas:
            if capa.root_cause_analysis:
                cat = capa.root_cause_analysis.root_cause_category.name
                root_cause_dist[cat] = root_cause_dist.get(cat, 0) + 1

        # Performance metrics
        closed_capas = [c for c in all_capas if c.status == CAPAStatus.CLOSED]
        on_time = sum(1 for c in closed_capas if not c.is_overdue())

        avg_days = (
            sum(c.get_days_open() for c in closed_capas) / len(closed_capas)
            if closed_capas else 0
        )

        overdue = sum(1 for c in all_capas if c.is_overdue())

        return {
            "total": len(all_capas),
            "open": len(all_capas) - len(closed_capas),
            "closed": len(closed_capas),
            "overdue": overdue,
            "on_time_rate": round(on_time / len(closed_capas) * 100, 1) if closed_capas else 0,
            "avg_days_to_close": round(avg_days, 1),
            "status_distribution": status_dist,
            "priority_distribution": priority_dist,
            "root_cause_distribution": root_cause_dist,
        }


class ISO13485CAPA(CAPAService):
    """
    ISO 13485:2016 compliant CAPA for medical devices.

    Extends base CAPA with medical device requirements.
    """

    def __init__(self):
        super().__init__()

        # Medical device specific fields
        self.risk_assessment_required = True
        self.regulatory_notification_threshold = CAPAPriority.HIGH

    def initiate_medical_device_capa(
        self,
        capa_type: CAPAType,
        priority: CAPAPriority,
        source_type: str,
        source_reference: str,
        problem_title: str,
        problem_description: str,
        initiator: str,
        device_identifier: str,
        device_name: str,
        lot_numbers: List[str] = None,
        patient_impact: bool = False
    ) -> CAPA:
        """Initiate CAPA for medical device issue."""
        capa = self.initiate_capa(
            capa_type=capa_type,
            priority=priority,
            source_type=source_type,
            source_reference=source_reference,
            problem_title=problem_title,
            problem_description=problem_description,
            initiator=initiator,
            affected_products=[device_identifier],
        )

        # Add medical device specific data
        capa.audit_trail.append({
            "timestamp": datetime.now().isoformat(),
            "action": "Medical device data added",
            "user": initiator,
            "details": {
                "device_identifier": device_identifier,
                "device_name": device_name,
                "lot_numbers": lot_numbers or [],
                "patient_impact": patient_impact,
            },
        })

        # Check if regulatory notification required
        if patient_impact or priority == CAPAPriority.CRITICAL:
            capa.add_audit_entry(
                "Regulatory notification flagged",
                "System",
                "MDR/IVDR reporting may be required"
            )

        return capa

    def perform_risk_assessment(
        self,
        capa_id: str,
        assessor: str,
        severity: int,  # 1-5
        occurrence: int,  # 1-5
        detectability: int,  # 1-5
        mitigation_required: bool = False
    ) -> Dict[str, Any]:
        """Perform ISO 14971 risk assessment for CAPA."""
        if capa_id not in self.capas:
            return {"success": False, "error": "CAPA not found"}

        capa = self.capas[capa_id]

        # Calculate RPN (Risk Priority Number)
        rpn = severity * occurrence * detectability

        # Risk level classification
        if rpn >= 100 or severity >= 4:
            risk_level = "High"
            action_required = True
        elif rpn >= 50:
            risk_level = "Medium"
            action_required = True
        else:
            risk_level = "Low"
            action_required = mitigation_required

        risk_assessment = {
            "assessor": assessor,
            "date": datetime.now().isoformat(),
            "severity": severity,
            "occurrence": occurrence,
            "detectability": detectability,
            "rpn": rpn,
            "risk_level": risk_level,
            "action_required": action_required,
            "meets_iso14971": True,
        }

        capa.audit_trail.append({
            "timestamp": datetime.now().isoformat(),
            "action": "Risk assessment completed",
            "user": assessor,
            "details": risk_assessment,
        })

        return {
            "success": True,
            "risk_assessment": risk_assessment,
        }

    def check_regulatory_reporting(
        self,
        capa_id: str
    ) -> Dict[str, Any]:
        """Check if CAPA requires regulatory reporting."""
        if capa_id not in self.capas:
            return {"success": False, "error": "CAPA not found"}

        capa = self.capas[capa_id]

        # Check MDR/IVDR requirements
        reporting_required = False
        reporting_reasons = []

        if capa.priority == CAPAPriority.CRITICAL:
            reporting_required = True
            reporting_reasons.append("Critical priority issue")

        # Check for patient safety issues
        for entry in capa.audit_trail:
            details = entry.get("details", {})
            if isinstance(details, dict) and details.get("patient_impact"):
                reporting_required = True
                reporting_reasons.append("Patient impact identified")
                break

        return {
            "capa_number": capa.capa_number,
            "reporting_required": reporting_required,
            "reasons": reporting_reasons,
            "regulatory_frameworks": ["MDR 2017/745", "21 CFR 803"] if reporting_required else [],
            "deadline": "Within 15 days" if reporting_required else "N/A",
        }


# Module exports
__all__ = [
    "CAPAType",
    "CAPAStatus",
    "CAPAPriority",
    "RootCauseCategory",
    "CAPA",
    "RootCauseAnalysis",
    "EffectivenessReview",
    "CAPAService",
    "ISO13485CAPA",
]
