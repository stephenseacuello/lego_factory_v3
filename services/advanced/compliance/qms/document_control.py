"""
Document Control System for ISO 9001/13485 Compliance.

Implements comprehensive document lifecycle management with
version control, approval workflows, and audit trails.

Research Value:
- Blockchain-ready document hashing
- AI-assisted document classification
- Automated obsolescence detection

References:
- ISO 9001:2015 Section 7.5 (Documented Information)
- ISO 13485:2016 Section 4.2.4 (Control of Documents)
- 21 CFR Part 11 (Electronic Records)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum, auto
from datetime import datetime, timedelta
import hashlib
import uuid
import re


class DocumentType(Enum):
    """Types of controlled documents."""
    # Level 1 - Policy
    QUALITY_MANUAL = auto()
    QUALITY_POLICY = auto()

    # Level 2 - Procedures
    PROCEDURE = auto()
    STANDARD_OPERATING_PROCEDURE = auto()
    WORK_INSTRUCTION = auto()

    # Level 3 - Forms & Records
    FORM = auto()
    TEMPLATE = auto()
    CHECKLIST = auto()

    # Level 4 - Supporting
    SPECIFICATION = auto()
    DRAWING = auto()
    EXTERNAL_DOCUMENT = auto()

    # Medical Device Specific
    DESIGN_HISTORY_FILE = auto()
    DEVICE_MASTER_RECORD = auto()
    RISK_MANAGEMENT_FILE = auto()


class DocumentStatus(Enum):
    """Document lifecycle status."""
    DRAFT = auto()
    IN_REVIEW = auto()
    PENDING_APPROVAL = auto()
    APPROVED = auto()
    EFFECTIVE = auto()
    SUPERSEDED = auto()
    OBSOLETE = auto()
    ARCHIVED = auto()


class ApprovalLevel(Enum):
    """Approval hierarchy levels."""
    AUTHOR = auto()
    REVIEWER = auto()
    QUALITY_ASSURANCE = auto()
    DEPARTMENT_HEAD = auto()
    MANAGEMENT_REPRESENTATIVE = auto()
    EXECUTIVE = auto()


@dataclass
class DocumentVersion:
    """Version information for a document."""

    version_number: str  # e.g., "1.0", "2.1"
    major_version: int
    minor_version: int
    created_date: datetime
    created_by: str
    change_description: str
    content_hash: str  # SHA-256 of content

    # Approval chain
    approvals: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    file_path: Optional[str] = None
    file_size: int = 0

    def is_major_change(self) -> bool:
        """Check if this is a major version change."""
        return self.minor_version == 0

    def get_approval_status(self) -> str:
        """Get current approval status."""
        if not self.approvals:
            return "Not submitted"

        pending = [a for a in self.approvals if a.get("status") == "pending"]
        rejected = [a for a in self.approvals if a.get("status") == "rejected"]

        if rejected:
            return "Rejected"
        elif pending:
            return f"Pending ({len(pending)} approvals remaining)"
        else:
            return "Fully approved"


@dataclass
class Document:
    """Controlled document with full lifecycle management."""

    document_id: str
    document_number: str  # e.g., "QMS-SOP-001"
    title: str
    document_type: DocumentType
    status: DocumentStatus

    # Ownership
    owner_department: str
    author: str
    document_controller: str

    # Versioning
    current_version: DocumentVersion
    version_history: List[DocumentVersion] = field(default_factory=list)

    # Classification
    classification: str = "Internal"  # Internal, Confidential, Restricted
    retention_period_years: int = 7

    # Dates
    created_date: datetime = field(default_factory=datetime.now)
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None

    # Relationships
    parent_document: Optional[str] = None
    child_documents: List[str] = field(default_factory=list)
    referenced_documents: List[str] = field(default_factory=list)

    # Training
    training_required: bool = False
    trained_personnel: List[str] = field(default_factory=list)

    # Audit trail
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def add_audit_entry(self, action: str, user: str, details: str = ""):
        """Add entry to audit trail."""
        self.audit_trail.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user": user,
            "details": details,
            "document_version": self.current_version.version_number,
        })

    def is_effective(self) -> bool:
        """Check if document is currently effective."""
        now = datetime.now()
        if self.status != DocumentStatus.EFFECTIVE:
            return False
        if self.effective_date and now < self.effective_date:
            return False
        if self.expiry_date and now > self.expiry_date:
            return False
        return True

    def needs_review(self) -> bool:
        """Check if document needs periodic review."""
        if not self.review_date:
            return False
        return datetime.now() >= self.review_date

    def get_next_version(self, major: bool = False) -> str:
        """Get next version number."""
        if major:
            return f"{self.current_version.major_version + 1}.0"
        else:
            return f"{self.current_version.major_version}.{self.current_version.minor_version + 1}"


@dataclass
class ChangeRequest:
    """Document change request."""

    request_id: str
    document_id: str
    requested_by: str
    request_date: datetime

    # Change details
    change_type: str  # "Major", "Minor", "Editorial"
    change_description: str
    justification: str

    # Impact assessment
    affected_documents: List[str] = field(default_factory=list)
    affected_processes: List[str] = field(default_factory=list)
    training_impact: bool = False

    # Approval
    status: str = "Pending"  # Pending, Approved, Rejected, Implemented
    approved_by: Optional[str] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # Implementation
    implementation_date: Optional[datetime] = None
    verified_by: Optional[str] = None


class DocumentController:
    """
    Document Control System.

    Manages document lifecycle per ISO 9001/13485 requirements.
    """

    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.change_requests: Dict[str, ChangeRequest] = {}
        self.document_number_counter: Dict[str, int] = {}

        # Approval matrix
        self.approval_matrix: Dict[DocumentType, List[ApprovalLevel]] = {
            DocumentType.QUALITY_MANUAL: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.QUALITY_ASSURANCE,
                ApprovalLevel.EXECUTIVE,
            ],
            DocumentType.QUALITY_POLICY: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.QUALITY_ASSURANCE,
                ApprovalLevel.EXECUTIVE,
            ],
            DocumentType.PROCEDURE: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.REVIEWER,
                ApprovalLevel.QUALITY_ASSURANCE,
            ],
            DocumentType.STANDARD_OPERATING_PROCEDURE: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.REVIEWER,
                ApprovalLevel.DEPARTMENT_HEAD,
            ],
            DocumentType.WORK_INSTRUCTION: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.REVIEWER,
            ],
            DocumentType.FORM: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.QUALITY_ASSURANCE,
            ],
            DocumentType.DESIGN_HISTORY_FILE: [
                ApprovalLevel.AUTHOR,
                ApprovalLevel.REVIEWER,
                ApprovalLevel.QUALITY_ASSURANCE,
                ApprovalLevel.MANAGEMENT_REPRESENTATIVE,
            ],
        }

        # Review periods (years)
        self.review_periods: Dict[DocumentType, int] = {
            DocumentType.QUALITY_MANUAL: 3,
            DocumentType.QUALITY_POLICY: 3,
            DocumentType.PROCEDURE: 2,
            DocumentType.STANDARD_OPERATING_PROCEDURE: 2,
            DocumentType.WORK_INSTRUCTION: 1,
            DocumentType.FORM: 2,
            DocumentType.DESIGN_HISTORY_FILE: 5,
        }

    def generate_document_number(
        self,
        doc_type: DocumentType,
        department: str
    ) -> str:
        """Generate unique document number."""
        prefix_map = {
            DocumentType.QUALITY_MANUAL: "QM",
            DocumentType.QUALITY_POLICY: "QP",
            DocumentType.PROCEDURE: "PROC",
            DocumentType.STANDARD_OPERATING_PROCEDURE: "SOP",
            DocumentType.WORK_INSTRUCTION: "WI",
            DocumentType.FORM: "FRM",
            DocumentType.TEMPLATE: "TMP",
            DocumentType.CHECKLIST: "CKL",
            DocumentType.SPECIFICATION: "SPEC",
            DocumentType.DRAWING: "DWG",
            DocumentType.DESIGN_HISTORY_FILE: "DHF",
            DocumentType.DEVICE_MASTER_RECORD: "DMR",
            DocumentType.RISK_MANAGEMENT_FILE: "RMF",
        }

        prefix = prefix_map.get(doc_type, "DOC")
        dept_code = department[:3].upper()

        key = f"{prefix}-{dept_code}"
        if key not in self.document_number_counter:
            self.document_number_counter[key] = 0

        self.document_number_counter[key] += 1
        counter = self.document_number_counter[key]

        return f"{key}-{counter:04d}"

    def create_document(
        self,
        title: str,
        doc_type: DocumentType,
        department: str,
        author: str,
        content: str = "",
        parent_document: Optional[str] = None
    ) -> Document:
        """Create a new controlled document."""
        doc_id = str(uuid.uuid4())
        doc_number = self.generate_document_number(doc_type, department)

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Initial version
        version = DocumentVersion(
            version_number="0.1",
            major_version=0,
            minor_version=1,
            created_date=datetime.now(),
            created_by=author,
            change_description="Initial draft",
            content_hash=content_hash,
        )

        # Calculate review date
        review_period = self.review_periods.get(doc_type, 2)
        review_date = datetime.now() + timedelta(days=review_period * 365)

        document = Document(
            document_id=doc_id,
            document_number=doc_number,
            title=title,
            document_type=doc_type,
            status=DocumentStatus.DRAFT,
            owner_department=department,
            author=author,
            document_controller="System",
            current_version=version,
            review_date=review_date,
            parent_document=parent_document,
        )

        document.add_audit_entry("Created", author, f"Document created: {title}")

        self.documents[doc_id] = document

        return document

    def submit_for_review(
        self,
        document_id: str,
        submitter: str
    ) -> Dict[str, Any]:
        """Submit document for review and approval."""
        if document_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        doc = self.documents[document_id]

        if doc.status not in [DocumentStatus.DRAFT, DocumentStatus.IN_REVIEW]:
            return {"success": False, "error": f"Cannot submit document in {doc.status.name} status"}

        # Get required approvals
        required_approvals = self.approval_matrix.get(
            doc.document_type,
            [ApprovalLevel.AUTHOR, ApprovalLevel.REVIEWER]
        )

        # Initialize approval chain
        doc.current_version.approvals = [
            {
                "level": level.name,
                "status": "pending",
                "approver": None,
                "date": None,
                "comments": None,
            }
            for level in required_approvals
        ]

        doc.status = DocumentStatus.IN_REVIEW
        doc.add_audit_entry("Submitted for review", submitter)

        return {
            "success": True,
            "document_id": document_id,
            "required_approvals": [a["level"] for a in doc.current_version.approvals],
        }

    def approve_document(
        self,
        document_id: str,
        approver: str,
        approval_level: ApprovalLevel,
        approved: bool,
        comments: str = ""
    ) -> Dict[str, Any]:
        """Approve or reject document at specified level."""
        if document_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        doc = self.documents[document_id]

        # Find matching approval level
        for approval in doc.current_version.approvals:
            if approval["level"] == approval_level.name and approval["status"] == "pending":
                approval["status"] = "approved" if approved else "rejected"
                approval["approver"] = approver
                approval["date"] = datetime.now().isoformat()
                approval["comments"] = comments

                action = "Approved" if approved else "Rejected"
                doc.add_audit_entry(
                    f"{action} at {approval_level.name}",
                    approver,
                    comments
                )

                # Check if all approved
                if approved:
                    all_approved = all(
                        a["status"] == "approved"
                        for a in doc.current_version.approvals
                    )
                    if all_approved:
                        doc.status = DocumentStatus.APPROVED
                        doc.add_audit_entry("Fully approved", "System")
                else:
                    doc.status = DocumentStatus.DRAFT  # Return to draft

                return {
                    "success": True,
                    "status": doc.status.name,
                    "all_approved": doc.status == DocumentStatus.APPROVED,
                }

        return {"success": False, "error": "No pending approval at this level"}

    def make_effective(
        self,
        document_id: str,
        effective_date: Optional[datetime] = None,
        controller: str = "System"
    ) -> Dict[str, Any]:
        """Make approved document effective."""
        if document_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        doc = self.documents[document_id]

        if doc.status != DocumentStatus.APPROVED:
            return {"success": False, "error": "Document must be approved first"}

        # Set effective date
        doc.effective_date = effective_date or datetime.now()
        doc.status = DocumentStatus.EFFECTIVE

        # Update version to 1.0 if still draft version
        if doc.current_version.major_version == 0:
            doc.version_history.append(doc.current_version)
            doc.current_version = DocumentVersion(
                version_number="1.0",
                major_version=1,
                minor_version=0,
                created_date=datetime.now(),
                created_by=controller,
                change_description="Initial release",
                content_hash=doc.current_version.content_hash,
                approvals=doc.current_version.approvals.copy(),
            )

        doc.add_audit_entry(
            "Made effective",
            controller,
            f"Effective date: {doc.effective_date.isoformat()}"
        )

        return {
            "success": True,
            "effective_date": doc.effective_date.isoformat(),
            "version": doc.current_version.version_number,
        }

    def create_change_request(
        self,
        document_id: str,
        requester: str,
        change_type: str,
        description: str,
        justification: str
    ) -> ChangeRequest:
        """Create a document change request."""
        request_id = str(uuid.uuid4())

        request = ChangeRequest(
            request_id=request_id,
            document_id=document_id,
            requested_by=requester,
            request_date=datetime.now(),
            change_type=change_type,
            change_description=description,
            justification=justification,
        )

        self.change_requests[request_id] = request

        if document_id in self.documents:
            self.documents[document_id].add_audit_entry(
                "Change request created",
                requester,
                description
            )

        return request

    def revise_document(
        self,
        document_id: str,
        revisor: str,
        new_content: str,
        change_description: str,
        major_change: bool = False
    ) -> Dict[str, Any]:
        """Create new revision of document."""
        if document_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        doc = self.documents[document_id]

        # Archive current version
        doc.version_history.append(doc.current_version)

        # Calculate new version
        if major_change:
            new_major = doc.current_version.major_version + 1
            new_minor = 0
        else:
            new_major = doc.current_version.major_version
            new_minor = doc.current_version.minor_version + 1

        # Create new version
        content_hash = hashlib.sha256(new_content.encode()).hexdigest()

        doc.current_version = DocumentVersion(
            version_number=f"{new_major}.{new_minor}",
            major_version=new_major,
            minor_version=new_minor,
            created_date=datetime.now(),
            created_by=revisor,
            change_description=change_description,
            content_hash=content_hash,
        )

        # Reset status for new review
        doc.status = DocumentStatus.DRAFT

        doc.add_audit_entry(
            "Revised",
            revisor,
            f"New version: {doc.current_version.version_number}"
        )

        return {
            "success": True,
            "new_version": doc.current_version.version_number,
            "previous_version": doc.version_history[-1].version_number,
        }

    def obsolete_document(
        self,
        document_id: str,
        reason: str,
        controller: str
    ) -> Dict[str, Any]:
        """Mark document as obsolete."""
        if document_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        doc = self.documents[document_id]

        # Superseded if replaced, obsolete if retired
        doc.status = DocumentStatus.OBSOLETE
        doc.expiry_date = datetime.now()

        doc.add_audit_entry("Obsoleted", controller, reason)

        return {
            "success": True,
            "document_number": doc.document_number,
            "obsolete_date": doc.expiry_date.isoformat(),
        }

    def get_documents_needing_review(self) -> List[Document]:
        """Get all documents that need periodic review."""
        return [
            doc for doc in self.documents.values()
            if doc.needs_review() and doc.status == DocumentStatus.EFFECTIVE
        ]

    def search_documents(
        self,
        query: str,
        doc_type: Optional[DocumentType] = None,
        status: Optional[DocumentStatus] = None,
        department: Optional[str] = None
    ) -> List[Document]:
        """Search documents by various criteria."""
        results = []

        query_lower = query.lower()

        for doc in self.documents.values():
            # Apply filters
            if doc_type and doc.document_type != doc_type:
                continue
            if status and doc.status != status:
                continue
            if department and doc.owner_department != department:
                continue

            # Search in title and document number
            if (query_lower in doc.title.lower() or
                query_lower in doc.document_number.lower()):
                results.append(doc)

        return results

    def generate_document_index(self) -> Dict[str, Any]:
        """Generate master document index."""
        index = {
            "generated_date": datetime.now().isoformat(),
            "total_documents": len(self.documents),
            "by_type": {},
            "by_status": {},
            "by_department": {},
            "documents": [],
        }

        for doc in self.documents.values():
            # Count by type
            type_name = doc.document_type.name
            index["by_type"][type_name] = index["by_type"].get(type_name, 0) + 1

            # Count by status
            status_name = doc.status.name
            index["by_status"][status_name] = index["by_status"].get(status_name, 0) + 1

            # Count by department
            dept = doc.owner_department
            index["by_department"][dept] = index["by_department"].get(dept, 0) + 1

            # Add document summary
            index["documents"].append({
                "document_number": doc.document_number,
                "title": doc.title,
                "type": type_name,
                "status": status_name,
                "version": doc.current_version.version_number,
                "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
                "review_date": doc.review_date.isoformat() if doc.review_date else None,
            })

        return index


class ISO9001DocumentControl(DocumentController):
    """
    ISO 9001:2015 compliant document control.

    Extends base controller with ISO-specific requirements.
    """

    def __init__(self):
        super().__init__()

        # ISO 9001 required documents
        self.required_documents = {
            "4.3": "Scope of QMS",
            "5.2": "Quality Policy",
            "6.2": "Quality Objectives",
            "7.1.5": "Monitoring and Measuring Resources",
            "7.2": "Competence Records",
            "7.5": "Documented Information",
            "8.1": "Operational Planning",
            "8.2.3": "Design and Development",
            "8.4": "External Provider Controls",
            "8.5.2": "Identification and Traceability",
            "8.5.6": "Control of Changes",
            "8.6": "Release of Products",
            "8.7": "Nonconforming Outputs",
            "9.1": "Monitoring and Measurement",
            "9.2": "Internal Audit",
            "9.3": "Management Review",
            "10.2": "Nonconformity and Corrective Action",
        }

    def check_compliance(self) -> Dict[str, Any]:
        """Check document control compliance with ISO 9001."""
        issues = []
        compliant_items = []

        # Check for required documents
        for clause, description in self.required_documents.items():
            # Search for document addressing this clause
            found = False
            for doc in self.documents.values():
                if (clause in doc.title.lower() or
                    clause in doc.document_number or
                    description.lower() in doc.title.lower()):
                    if doc.status == DocumentStatus.EFFECTIVE:
                        found = True
                        compliant_items.append(f"{clause}: {description}")
                        break

            if not found:
                issues.append({
                    "clause": clause,
                    "requirement": description,
                    "issue": "Required document not found or not effective",
                })

        # Check for review compliance
        overdue_reviews = self.get_documents_needing_review()
        if overdue_reviews:
            issues.append({
                "clause": "7.5.3",
                "requirement": "Document review",
                "issue": f"{len(overdue_reviews)} documents overdue for review",
                "documents": [d.document_number for d in overdue_reviews],
            })

        # Check for proper version control
        for doc in self.documents.values():
            if doc.status == DocumentStatus.EFFECTIVE:
                if not doc.current_version.approvals:
                    issues.append({
                        "clause": "7.5.2",
                        "requirement": "Approval before release",
                        "issue": f"Document {doc.document_number} effective without approval",
                    })

        compliance_score = len(compliant_items) / len(self.required_documents) * 100

        return {
            "compliance_score": round(compliance_score, 1),
            "total_requirements": len(self.required_documents),
            "compliant_items": len(compliant_items),
            "issues": issues,
            "compliant_clauses": compliant_items,
            "status": "Compliant" if compliance_score >= 80 else "Non-compliant",
        }

    def generate_controlled_copy(
        self,
        document_id: str,
        recipient: str,
        copy_number: int
    ) -> Dict[str, Any]:
        """Generate controlled copy of document."""
        if document_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        doc = self.documents[document_id]

        if doc.status != DocumentStatus.EFFECTIVE:
            return {"success": False, "error": "Only effective documents can be distributed"}

        # Record distribution
        distribution_record = {
            "copy_number": copy_number,
            "recipient": recipient,
            "issue_date": datetime.now().isoformat(),
            "document_number": doc.document_number,
            "version": doc.current_version.version_number,
            "control_status": "CONTROLLED COPY",
        }

        doc.add_audit_entry(
            "Controlled copy issued",
            "System",
            f"Copy #{copy_number} to {recipient}"
        )

        return {
            "success": True,
            "distribution_record": distribution_record,
            "watermark": f"CONTROLLED COPY #{copy_number} - {recipient}",
        }


# Module exports
__all__ = [
    "DocumentType",
    "DocumentStatus",
    "ApprovalLevel",
    "Document",
    "DocumentVersion",
    "ChangeRequest",
    "DocumentController",
    "ISO9001DocumentControl",
]
