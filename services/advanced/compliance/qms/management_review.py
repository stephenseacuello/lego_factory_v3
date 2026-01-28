"""
Management Review Service for ISO 9001/13485 Compliance.

Implements structured management review process with
input collection, analysis, and action tracking.

Research Value:
- AI-assisted trend analysis
- Predictive quality indicators
- Automated report generation

References:
- ISO 9001:2015 Section 9.3 (Management Review)
- ISO 13485:2016 Section 5.6 (Management Review)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto
from datetime import datetime, timedelta
import uuid
import math


class ReviewFrequency(Enum):
    """Frequency of management reviews."""
    MONTHLY = 1
    QUARTERLY = 3
    SEMI_ANNUAL = 6
    ANNUAL = 12


class ReviewStatus(Enum):
    """Management review lifecycle status."""
    SCHEDULED = auto()
    INPUT_COLLECTION = auto()
    IN_REVIEW = auto()
    MINUTES_DRAFT = auto()
    MINUTES_APPROVED = auto()
    ACTIONS_IN_PROGRESS = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class ActionPriority(Enum):
    """Priority levels for action items."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class ReviewInput:
    """Input item for management review."""

    input_id: str
    category: str  # e.g., "Customer Feedback", "Audit Results"
    title: str
    description: str
    data: Dict[str, Any]

    # Source
    submitted_by: str
    submission_date: datetime
    source_document: Optional[str] = None

    # Analysis
    trend: Optional[str] = None  # "Improving", "Stable", "Declining"
    risk_level: str = "Medium"
    action_required: bool = False

    def to_summary(self) -> Dict[str, Any]:
        """Create summary for review presentation."""
        return {
            "category": self.category,
            "title": self.title,
            "trend": self.trend,
            "risk_level": self.risk_level,
            "action_required": self.action_required,
            "key_data": {k: v for k, v in self.data.items()
                        if k in ["current", "target", "change", "score"]},
        }


@dataclass
class ReviewOutput:
    """Output/decision from management review."""

    output_id: str
    category: str  # e.g., "Resource Decision", "Policy Change"
    decision: str
    rationale: str

    # Action items
    actions: List[Dict[str, Any]] = field(default_factory=list)

    # Responsible
    owner: str = ""
    due_date: Optional[datetime] = None

    # Status
    status: str = "Open"

    def add_action(
        self,
        description: str,
        responsible: str,
        due_date: datetime,
        priority: ActionPriority
    ):
        """Add action item."""
        self.actions.append({
            "action_id": str(uuid.uuid4()),
            "description": description,
            "responsible": responsible,
            "due_date": due_date.isoformat(),
            "priority": priority.name,
            "status": "Open",
            "completion_date": None,
        })


@dataclass
class ManagementReviewMeeting:
    """Management review meeting record."""

    review_id: str
    review_number: str  # e.g., "MR-2024-Q1"
    status: ReviewStatus
    frequency: ReviewFrequency

    # Scheduling
    scheduled_date: datetime
    actual_date: Optional[datetime] = None
    duration_hours: float = 2.0

    # Participants
    chairperson: str = ""
    attendees: List[str] = field(default_factory=list)
    absentees: List[str] = field(default_factory=list)

    # Content
    agenda: List[str] = field(default_factory=list)
    inputs: List[ReviewInput] = field(default_factory=list)
    outputs: List[ReviewOutput] = field(default_factory=list)

    # Minutes
    minutes: str = ""
    key_discussions: List[Dict[str, Any]] = field(default_factory=list)

    # Previous review
    previous_review_id: Optional[str] = None
    previous_actions_reviewed: List[Dict[str, Any]] = field(default_factory=list)

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

    def add_input(self, input_item: ReviewInput):
        """Add review input."""
        self.inputs.append(input_item)

    def add_output(
        self,
        category: str,
        decision: str,
        rationale: str,
        owner: str = ""
    ) -> ReviewOutput:
        """Add review output/decision."""
        output = ReviewOutput(
            output_id=str(uuid.uuid4()),
            category=category,
            decision=decision,
            rationale=rationale,
            owner=owner,
        )
        self.outputs.append(output)
        return output

    def get_action_summary(self) -> Dict[str, Any]:
        """Get summary of all action items."""
        all_actions = []
        for output in self.outputs:
            all_actions.extend(output.actions)

        total = len(all_actions)
        open_actions = sum(1 for a in all_actions if a["status"] == "Open")
        overdue = sum(
            1 for a in all_actions
            if a["status"] == "Open" and
            datetime.fromisoformat(a["due_date"]) < datetime.now()
        )

        by_priority = {}
        for action in all_actions:
            priority = action["priority"]
            by_priority[priority] = by_priority.get(priority, 0) + 1

        return {
            "total": total,
            "open": open_actions,
            "closed": total - open_actions,
            "overdue": overdue,
            "by_priority": by_priority,
        }


class ManagementReviewService:
    """
    Management Review Service.

    Manages the complete management review lifecycle.
    """

    def __init__(self):
        self.reviews: Dict[str, ManagementReviewMeeting] = {}
        self.review_counter = 0

        # ISO 9001 required inputs
        self.required_inputs = [
            "Status of previous review actions",
            "Customer feedback",
            "Process performance and product conformity",
            "Nonconformities and corrective actions",
            "Monitoring and measurement results",
            "Audit results",
            "External provider performance",
            "Resource adequacy",
            "Risk and opportunity actions effectiveness",
            "Improvement opportunities",
        ]

        # ISO 9001 required outputs
        self.required_outputs = [
            "Improvement opportunities",
            "QMS changes needed",
            "Resource needs",
        ]

    def generate_review_number(self, frequency: ReviewFrequency) -> str:
        """Generate review number."""
        self.review_counter += 1
        year = datetime.now().year
        month = datetime.now().month

        if frequency == ReviewFrequency.QUARTERLY:
            period = f"Q{(month - 1) // 3 + 1}"
        elif frequency == ReviewFrequency.SEMI_ANNUAL:
            period = "H1" if month <= 6 else "H2"
        elif frequency == ReviewFrequency.ANNUAL:
            period = "ANNUAL"
        else:
            period = f"M{month:02d}"

        return f"MR-{year}-{period}"

    def schedule_review(
        self,
        scheduled_date: datetime,
        frequency: ReviewFrequency,
        chairperson: str,
        attendees: List[str]
    ) -> ManagementReviewMeeting:
        """Schedule a management review meeting."""
        review_id = str(uuid.uuid4())
        review_number = self.generate_review_number(frequency)

        # Create standard agenda
        agenda = [
            "Opening and roll call",
            "Review of previous meeting actions",
            "Customer feedback and satisfaction",
            "Process performance metrics",
            "Audit results and findings",
            "Nonconformities and CAPA status",
            "Risk and opportunity review",
            "Resource requirements",
            "Improvement opportunities",
            "Decisions and action items",
            "Next review scheduling",
            "Closing",
        ]

        review = ManagementReviewMeeting(
            review_id=review_id,
            review_number=review_number,
            status=ReviewStatus.SCHEDULED,
            frequency=frequency,
            scheduled_date=scheduled_date,
            chairperson=chairperson,
            attendees=attendees,
            agenda=agenda,
        )

        # Find previous review
        previous = self._get_previous_review()
        if previous:
            review.previous_review_id = previous.review_id

        review.add_audit_entry(
            "Scheduled",
            chairperson,
            f"Review {review_number} scheduled for {scheduled_date.date()}"
        )

        self.reviews[review_id] = review

        return review

    def _get_previous_review(self) -> Optional[ManagementReviewMeeting]:
        """Get the most recent completed review."""
        completed = [
            r for r in self.reviews.values()
            if r.status == ReviewStatus.COMPLETED
        ]

        if not completed:
            return None

        return max(completed, key=lambda r: r.actual_date or r.scheduled_date)

    def start_input_collection(
        self,
        review_id: str,
        coordinator: str
    ) -> Dict[str, Any]:
        """Start input collection phase."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]
        review.status = ReviewStatus.INPUT_COLLECTION

        review.add_audit_entry("Input collection started", coordinator)

        return {
            "success": True,
            "required_inputs": self.required_inputs,
            "deadline": (review.scheduled_date - timedelta(days=7)).isoformat(),
        }

    def submit_input(
        self,
        review_id: str,
        category: str,
        title: str,
        description: str,
        data: Dict[str, Any],
        submitter: str,
        source_document: Optional[str] = None
    ) -> ReviewInput:
        """Submit input for management review."""
        if review_id not in self.reviews:
            raise ValueError("Review not found")

        review = self.reviews[review_id]

        # Analyze trend if historical data available
        trend = self._analyze_trend(data)

        # Assess risk level
        risk_level = self._assess_input_risk(category, data)

        input_item = ReviewInput(
            input_id=str(uuid.uuid4()),
            category=category,
            title=title,
            description=description,
            data=data,
            submitted_by=submitter,
            submission_date=datetime.now(),
            source_document=source_document,
            trend=trend,
            risk_level=risk_level,
            action_required=risk_level in ["High", "Critical"],
        )

        review.add_input(input_item)

        review.add_audit_entry(
            "Input submitted",
            submitter,
            f"{category}: {title}"
        )

        return input_item

    def _analyze_trend(self, data: Dict[str, Any]) -> Optional[str]:
        """Analyze trend from data."""
        if "current" in data and "previous" in data:
            current = data["current"]
            previous = data["previous"]

            if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                if previous != 0:
                    change = (current - previous) / abs(previous) * 100
                    if change > 5:
                        return "Improving"
                    elif change < -5:
                        return "Declining"
                    else:
                        return "Stable"

        return None

    def _assess_input_risk(self, category: str, data: Dict[str, Any]) -> str:
        """Assess risk level of input."""
        # High risk categories
        high_risk_categories = [
            "Customer Complaints",
            "Product Recalls",
            "Major Nonconformities",
            "Regulatory Issues",
        ]

        if category in high_risk_categories:
            return "High"

        # Check for concerning data
        if "score" in data and data["score"] < 70:
            return "High"
        if "defect_rate" in data and data["defect_rate"] > 5:
            return "High"
        if "customer_satisfaction" in data and data["customer_satisfaction"] < 3.5:
            return "High"

        return "Medium"

    def conduct_review(
        self,
        review_id: str,
        actual_date: datetime,
        duration_hours: float,
        attendees: List[str],
        absentees: List[str]
    ) -> Dict[str, Any]:
        """Record that review meeting was conducted."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        review.actual_date = actual_date
        review.duration_hours = duration_hours
        review.attendees = attendees
        review.absentees = absentees
        review.status = ReviewStatus.IN_REVIEW

        # Review previous actions if applicable
        if review.previous_review_id:
            previous = self.reviews.get(review.previous_review_id)
            if previous:
                review.previous_actions_reviewed = self._get_previous_actions(previous)

        review.add_audit_entry(
            "Meeting conducted",
            review.chairperson,
            f"Duration: {duration_hours}h, Attendees: {len(attendees)}"
        )

        return {
            "success": True,
            "inputs_reviewed": len(review.inputs),
            "previous_actions": len(review.previous_actions_reviewed),
        }

    def _get_previous_actions(
        self,
        previous_review: ManagementReviewMeeting
    ) -> List[Dict[str, Any]]:
        """Get actions from previous review for follow-up."""
        actions = []

        for output in previous_review.outputs:
            for action in output.actions:
                actions.append({
                    "action_id": action["action_id"],
                    "description": action["description"],
                    "responsible": action["responsible"],
                    "due_date": action["due_date"],
                    "status": action["status"],
                    "from_review": previous_review.review_number,
                })

        return actions

    def record_discussion(
        self,
        review_id: str,
        topic: str,
        key_points: List[str],
        conclusions: str,
        recorder: str
    ) -> Dict[str, Any]:
        """Record discussion point during review."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        discussion = {
            "topic": topic,
            "key_points": key_points,
            "conclusions": conclusions,
            "recorded_by": recorder,
            "recorded_at": datetime.now().isoformat(),
        }

        review.key_discussions.append(discussion)

        return {"success": True, "discussion_count": len(review.key_discussions)}

    def record_decision(
        self,
        review_id: str,
        category: str,
        decision: str,
        rationale: str,
        owner: str,
        actions: List[Dict[str, Any]] = None
    ) -> ReviewOutput:
        """Record decision/output from review."""
        if review_id not in self.reviews:
            raise ValueError("Review not found")

        review = self.reviews[review_id]

        output = review.add_output(category, decision, rationale, owner)

        # Add action items
        if actions:
            for action in actions:
                output.add_action(
                    description=action["description"],
                    responsible=action["responsible"],
                    due_date=datetime.fromisoformat(action["due_date"]),
                    priority=ActionPriority[action.get("priority", "MEDIUM")],
                )

        review.add_audit_entry(
            "Decision recorded",
            review.chairperson,
            f"{category}: {decision[:50]}..."
        )

        return output

    def generate_minutes(
        self,
        review_id: str,
        preparer: str
    ) -> Dict[str, Any]:
        """Generate meeting minutes."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        # Generate minutes text
        minutes_parts = []

        # Header
        minutes_parts.append(f"MANAGEMENT REVIEW MINUTES")
        minutes_parts.append(f"Review Number: {review.review_number}")
        minutes_parts.append(f"Date: {review.actual_date.strftime('%Y-%m-%d') if review.actual_date else 'TBD'}")
        minutes_parts.append(f"Chairperson: {review.chairperson}")
        minutes_parts.append(f"")

        # Attendance
        minutes_parts.append("ATTENDANCE:")
        minutes_parts.append(f"Present: {', '.join(review.attendees)}")
        if review.absentees:
            minutes_parts.append(f"Absent: {', '.join(review.absentees)}")
        minutes_parts.append("")

        # Previous actions
        if review.previous_actions_reviewed:
            minutes_parts.append("REVIEW OF PREVIOUS ACTIONS:")
            for action in review.previous_actions_reviewed:
                status = action["status"]
                minutes_parts.append(f"  - {action['description']}: {status}")
            minutes_parts.append("")

        # Inputs reviewed
        minutes_parts.append("INPUTS REVIEWED:")
        for input_item in review.inputs:
            minutes_parts.append(f"  - {input_item.category}: {input_item.title}")
            if input_item.trend:
                minutes_parts.append(f"    Trend: {input_item.trend}")
            if input_item.action_required:
                minutes_parts.append(f"    *** Action Required ***")
        minutes_parts.append("")

        # Discussions
        if review.key_discussions:
            minutes_parts.append("KEY DISCUSSIONS:")
            for disc in review.key_discussions:
                minutes_parts.append(f"  Topic: {disc['topic']}")
                minutes_parts.append(f"  Conclusion: {disc['conclusions']}")
            minutes_parts.append("")

        # Decisions
        minutes_parts.append("DECISIONS AND OUTPUTS:")
        for output in review.outputs:
            minutes_parts.append(f"  Category: {output.category}")
            minutes_parts.append(f"  Decision: {output.decision}")
            if output.actions:
                minutes_parts.append("  Actions:")
                for action in output.actions:
                    minutes_parts.append(
                        f"    - {action['description']} "
                        f"(Owner: {action['responsible']}, "
                        f"Due: {action['due_date'][:10]})"
                    )
        minutes_parts.append("")

        # Closing
        minutes_parts.append("NEXT REVIEW:")
        next_date = self._calculate_next_review_date(review)
        minutes_parts.append(f"  Scheduled: {next_date.strftime('%Y-%m-%d')}")

        review.minutes = "\n".join(minutes_parts)
        review.status = ReviewStatus.MINUTES_DRAFT

        review.add_audit_entry("Minutes generated", preparer)

        return {
            "success": True,
            "minutes": review.minutes,
            "word_count": len(review.minutes.split()),
        }

    def _calculate_next_review_date(
        self,
        review: ManagementReviewMeeting
    ) -> datetime:
        """Calculate next review date based on frequency."""
        base_date = review.actual_date or review.scheduled_date
        months = review.frequency.value

        # Simple month addition
        new_month = base_date.month + months
        new_year = base_date.year + (new_month - 1) // 12
        new_month = ((new_month - 1) % 12) + 1

        return datetime(new_year, new_month, base_date.day)

    def approve_minutes(
        self,
        review_id: str,
        approver: str,
        comments: str = ""
    ) -> Dict[str, Any]:
        """Approve meeting minutes."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        review.approvals.append({
            "type": "Minutes",
            "approver": approver,
            "date": datetime.now().isoformat(),
            "comments": comments,
        })

        review.status = ReviewStatus.MINUTES_APPROVED

        review.add_audit_entry("Minutes approved", approver, comments)

        return {"success": True, "status": "Minutes Approved"}

    def complete_action(
        self,
        review_id: str,
        action_id: str,
        completed_by: str,
        evidence: str = ""
    ) -> Dict[str, Any]:
        """Complete an action item."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        for output in review.outputs:
            for action in output.actions:
                if action["action_id"] == action_id:
                    action["status"] = "Completed"
                    action["completion_date"] = datetime.now().isoformat()
                    action["completed_by"] = completed_by
                    action["evidence"] = evidence

                    review.add_audit_entry(
                        "Action completed",
                        completed_by,
                        action["description"][:50]
                    )

                    # Check if all actions complete
                    action_summary = review.get_action_summary()
                    if action_summary["open"] == 0:
                        review.status = ReviewStatus.COMPLETED

                    return {
                        "success": True,
                        "actions_remaining": action_summary["open"],
                    }

        return {"success": False, "error": "Action not found"}

    def get_review_metrics(self) -> Dict[str, Any]:
        """Get management review program metrics."""
        if not self.reviews:
            return {"total_reviews": 0}

        all_reviews = list(self.reviews.values())
        completed = [r for r in all_reviews if r.status == ReviewStatus.COMPLETED]

        # Attendance metrics
        avg_attendance = sum(len(r.attendees) for r in completed) / len(completed) if completed else 0

        # Action completion
        total_actions = 0
        completed_actions = 0
        overdue_actions = 0

        for review in all_reviews:
            summary = review.get_action_summary()
            total_actions += summary["total"]
            completed_actions += summary["closed"]
            overdue_actions += summary["overdue"]

        # Input coverage
        input_categories = set()
        for review in completed:
            for input_item in review.inputs:
                input_categories.add(input_item.category)

        return {
            "total_reviews": len(all_reviews),
            "completed_reviews": len(completed),
            "scheduled_reviews": sum(1 for r in all_reviews if r.status == ReviewStatus.SCHEDULED),
            "average_attendance": round(avg_attendance, 1),
            "total_actions": total_actions,
            "completed_actions": completed_actions,
            "overdue_actions": overdue_actions,
            "action_completion_rate": round(
                completed_actions / total_actions * 100, 1
            ) if total_actions else 0,
            "input_categories_covered": len(input_categories),
            "required_inputs": len(self.required_inputs),
        }


class ISO9001ManagementReview(ManagementReviewService):
    """
    ISO 9001:2015 compliant management review.

    Ensures all clause 9.3 requirements are met.
    """

    def __init__(self):
        super().__init__()

        # ISO 9001:2015 Section 9.3.2 required inputs
        self.iso9001_required_inputs = {
            "9.3.2.a": "Status of actions from previous management reviews",
            "9.3.2.b": "Changes in external and internal issues",
            "9.3.2.c.1": "Customer satisfaction and interested party feedback",
            "9.3.2.c.2": "Quality objectives achievement",
            "9.3.2.c.3": "Process performance and product conformity",
            "9.3.2.c.4": "Nonconformities and corrective actions",
            "9.3.2.c.5": "Monitoring and measurement results",
            "9.3.2.c.6": "Audit results",
            "9.3.2.c.7": "External provider performance",
            "9.3.2.d": "Resource adequacy",
            "9.3.2.e": "Risk and opportunity actions effectiveness",
            "9.3.2.f": "Improvement opportunities",
        }

        # ISO 9001:2015 Section 9.3.3 required outputs
        self.iso9001_required_outputs = {
            "9.3.3.a": "Improvement opportunities",
            "9.3.3.b": "QMS changes needed",
            "9.3.3.c": "Resource needs",
        }

    def check_input_coverage(self, review_id: str) -> Dict[str, Any]:
        """Check if all ISO 9001 required inputs are covered."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        covered = set()
        missing = []

        # Map input categories to ISO clauses
        category_mapping = {
            "Previous Actions": "9.3.2.a",
            "External Issues": "9.3.2.b",
            "Internal Issues": "9.3.2.b",
            "Customer Satisfaction": "9.3.2.c.1",
            "Customer Feedback": "9.3.2.c.1",
            "Quality Objectives": "9.3.2.c.2",
            "Process Performance": "9.3.2.c.3",
            "Product Conformity": "9.3.2.c.3",
            "Nonconformities": "9.3.2.c.4",
            "Corrective Actions": "9.3.2.c.4",
            "CAPA": "9.3.2.c.4",
            "Monitoring Results": "9.3.2.c.5",
            "Measurement Results": "9.3.2.c.5",
            "Audit Results": "9.3.2.c.6",
            "Internal Audit": "9.3.2.c.6",
            "Supplier Performance": "9.3.2.c.7",
            "External Providers": "9.3.2.c.7",
            "Resources": "9.3.2.d",
            "Risk Management": "9.3.2.e",
            "Opportunities": "9.3.2.e",
            "Improvement": "9.3.2.f",
        }

        # Check coverage
        for input_item in review.inputs:
            for cat, clause in category_mapping.items():
                if cat.lower() in input_item.category.lower():
                    covered.add(clause)

        # Find missing
        for clause, description in self.iso9001_required_inputs.items():
            if clause not in covered:
                missing.append({
                    "clause": clause,
                    "requirement": description,
                })

        coverage_pct = len(covered) / len(self.iso9001_required_inputs) * 100

        return {
            "coverage_percentage": round(coverage_pct, 1),
            "covered_clauses": list(covered),
            "missing_inputs": missing,
            "compliant": len(missing) == 0,
        }

    def check_output_coverage(self, review_id: str) -> Dict[str, Any]:
        """Check if all ISO 9001 required outputs are addressed."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        covered = set()

        # Map output categories to ISO clauses
        category_mapping = {
            "Improvement": "9.3.3.a",
            "QMS Change": "9.3.3.b",
            "System Change": "9.3.3.b",
            "Resource": "9.3.3.c",
        }

        for output in review.outputs:
            for cat, clause in category_mapping.items():
                if cat.lower() in output.category.lower():
                    covered.add(clause)

        missing = []
        for clause, description in self.iso9001_required_outputs.items():
            if clause not in covered:
                missing.append({
                    "clause": clause,
                    "requirement": description,
                })

        return {
            "covered_clauses": list(covered),
            "missing_outputs": missing,
            "compliant": len(missing) == 0,
        }

    def generate_compliance_report(self, review_id: str) -> Dict[str, Any]:
        """Generate ISO 9001 compliance report for review."""
        if review_id not in self.reviews:
            return {"success": False, "error": "Review not found"}

        review = self.reviews[review_id]

        input_check = self.check_input_coverage(review_id)
        output_check = self.check_output_coverage(review_id)

        # Check documented information requirements
        doc_compliant = bool(review.minutes and review.approvals)

        # Overall compliance
        overall_compliant = (
            input_check["compliant"] and
            output_check["compliant"] and
            doc_compliant
        )

        return {
            "review_number": review.review_number,
            "review_date": review.actual_date.isoformat() if review.actual_date else None,
            "input_compliance": input_check,
            "output_compliance": output_check,
            "documented_information": {
                "minutes_recorded": bool(review.minutes),
                "minutes_approved": bool(review.approvals),
                "compliant": doc_compliant,
            },
            "overall_compliance": overall_compliant,
            "gaps": {
                "inputs": input_check["missing_inputs"],
                "outputs": output_check["missing_outputs"],
            },
            "recommendations": self._generate_compliance_recommendations(
                input_check, output_check, doc_compliant
            ),
        }

    def _generate_compliance_recommendations(
        self,
        input_check: Dict[str, Any],
        output_check: Dict[str, Any],
        doc_compliant: bool
    ) -> List[str]:
        """Generate recommendations for compliance gaps."""
        recommendations = []

        if input_check["missing_inputs"]:
            clauses = [m["clause"] for m in input_check["missing_inputs"]]
            recommendations.append(
                f"Collect and review data for missing input clauses: {', '.join(clauses)}"
            )

        if output_check["missing_outputs"]:
            clauses = [m["clause"] for m in output_check["missing_outputs"]]
            recommendations.append(
                f"Ensure decisions are recorded for output clauses: {', '.join(clauses)}"
            )

        if not doc_compliant:
            recommendations.append(
                "Complete and approve meeting minutes as documented information"
            )

        if not recommendations:
            recommendations.append("Review meets ISO 9001:2015 Section 9.3 requirements")

        return recommendations


# Module exports
__all__ = [
    "ReviewFrequency",
    "ReviewStatus",
    "ActionPriority",
    "ReviewInput",
    "ReviewOutput",
    "ManagementReviewMeeting",
    "ManagementReviewService",
    "ISO9001ManagementReview",
]
