"""
Approval Workflow Handler.

Handles NC program approval workflows with audit logging.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """NC program approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """An NC program approval request."""
    program_id: str
    program_name: str
    version: str
    requested_by: str
    requested_at: datetime
    fusion_project: Optional[str] = None
    operation: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    comments: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalResult:
    """Result of an approval action."""
    success: bool
    action: str
    program_name: str
    message: str
    audit_entry: Dict[str, Any] = None


class ApprovalWorkflowHandler:
    """
    Handler for NC program approval workflows.

    Provides:
    - List pending approvals
    - Approve/reject programs
    - Audit logging
    - Provenance tracking
    """

    def __init__(self, flask_url: str = "http://localhost:5000"):
        """Initialize with Flask backend URL."""
        self.flask_url = flask_url.rstrip("/")

    async def list_pending(self) -> List[ApprovalRequest]:
        """Get list of pending approval requests."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.flask_url}/api/fusion360/pending-approvals",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    data = await response.json()

                    requests = []
                    for item in data.get("pending", []):
                        requests.append(ApprovalRequest(
                            program_id=item.get("id", ""),
                            program_name=item.get("name", ""),
                            version=item.get("version", "1.0"),
                            requested_by=item.get("requested_by", "Unknown"),
                            requested_at=datetime.fromisoformat(item.get("requested_at", datetime.utcnow().isoformat())),
                            fusion_project=item.get("fusion_project"),
                            operation=item.get("operation"),
                            status=ApprovalStatus.PENDING,
                            metadata=item.get("metadata", {}),
                        ))

                    return requests

        except Exception as e:
            logger.exception("Error fetching pending approvals")
            return []

    async def approve(
        self,
        program_name: str,
        approver: str,
        comments: Optional[str] = None,
        safety_verified: bool = True,
    ) -> ApprovalResult:
        """
        Approve an NC program for production.

        Args:
            program_name: Name of the program to approve
            approver: Name/ID of the approver
            comments: Optional approval comments
            safety_verified: Whether safety checks passed

        Returns:
            ApprovalResult with audit entry
        """
        if not safety_verified:
            return ApprovalResult(
                success=False,
                action="approve",
                program_name=program_name,
                message="Cannot approve: Safety verification failed",
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.flask_url}/api/fusion360/approve",
                    json={
                        "program_name": program_name,
                        "approved_by": approver,
                        "comments": comments,
                        "safety_verified": safety_verified,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        audit_entry = {
                            "action": "APPROVE",
                            "program": program_name,
                            "approver": approver,
                            "timestamp": datetime.utcnow().isoformat(),
                            "comments": comments,
                            "safety_verified": safety_verified,
                        }

                        logger.info(f"NC Program approved: {program_name} by {approver}")

                        return ApprovalResult(
                            success=True,
                            action="approve",
                            program_name=program_name,
                            message=f"Program '{program_name}' approved for production",
                            audit_entry=audit_entry,
                        )
                    else:
                        return ApprovalResult(
                            success=False,
                            action="approve",
                            program_name=program_name,
                            message=f"Approval failed: {data.get('error', 'Unknown error')}",
                        )

        except Exception as e:
            logger.exception(f"Error approving program: {program_name}")
            return ApprovalResult(
                success=False,
                action="approve",
                program_name=program_name,
                message=f"Error: {str(e)}",
            )

    async def reject(
        self,
        program_name: str,
        reviewer: str,
        reason: str,
    ) -> ApprovalResult:
        """
        Reject an NC program.

        Args:
            program_name: Name of the program to reject
            reviewer: Name/ID of the reviewer
            reason: Reason for rejection

        Returns:
            ApprovalResult with audit entry
        """
        if not reason:
            return ApprovalResult(
                success=False,
                action="reject",
                program_name=program_name,
                message="Rejection reason is required",
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.flask_url}/api/fusion360/reject",
                    json={
                        "program_name": program_name,
                        "rejected_by": reviewer,
                        "reason": reason,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        audit_entry = {
                            "action": "REJECT",
                            "program": program_name,
                            "reviewer": reviewer,
                            "timestamp": datetime.utcnow().isoformat(),
                            "reason": reason,
                        }

                        logger.info(f"NC Program rejected: {program_name} by {reviewer}")

                        return ApprovalResult(
                            success=True,
                            action="reject",
                            program_name=program_name,
                            message=f"Program '{program_name}' rejected: {reason}",
                            audit_entry=audit_entry,
                        )
                    else:
                        return ApprovalResult(
                            success=False,
                            action="reject",
                            program_name=program_name,
                            message=f"Rejection failed: {data.get('error', 'Unknown error')}",
                        )

        except Exception as e:
            logger.exception(f"Error rejecting program: {program_name}")
            return ApprovalResult(
                success=False,
                action="reject",
                program_name=program_name,
                message=f"Error: {str(e)}",
            )

    async def get_provenance(self, program_name: str) -> Dict[str, Any]:
        """
        Get provenance information for an NC program.

        Returns the complete chain of custody from CAD to machine.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.flask_url}/api/fusion360/provenance/{program_name}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"Failed to get provenance (HTTP {response.status})"}

        except Exception as e:
            logger.exception(f"Error getting provenance for: {program_name}")
            return {"error": str(e)}

    async def verify_safety(self, program_name: str) -> Dict[str, Any]:
        """
        Perform safety verification on an NC program.

        Checks:
        - Toolpath analysis for collisions
        - Feed/speed validation
        - Soft limit verification
        - Tool availability
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get program content
                async with session.get(
                    f"{self.flask_url}/api/gcode/program/{program_name}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        return {"safe": False, "reason": "Cannot load program"}

                    program_data = await response.json()

                # Analyze toolpath
                async with session.post(
                    f"{self.flask_url}/api/gcode/analyze",
                    json={"program_name": program_name},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        return {"safe": False, "reason": "Analysis failed"}

                    analysis = await response.json()

            # Evaluate safety
            issues = []

            if analysis.get("collision_risk", False):
                issues.append("Potential collision detected")

            if analysis.get("rapid_through_material", False):
                issues.append("Rapid move through material")

            if analysis.get("exceeds_limits", False):
                issues.append("Exceeds machine limits")

            if analysis.get("missing_tools", []):
                issues.append(f"Missing tools: {', '.join(analysis['missing_tools'])}")

            return {
                "safe": len(issues) == 0,
                "issues": issues,
                "analysis": analysis,
                "verified_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.exception(f"Error verifying safety for: {program_name}")
            return {"safe": False, "reason": str(e)}

    def format_pending_list(self, requests: List[ApprovalRequest]) -> str:
        """Format pending approvals for display."""
        if not requests:
            return "No pending approvals."

        lines = ["## Pending NC Program Approvals", ""]

        for req in requests:
            age = datetime.utcnow() - req.requested_at
            age_str = f"{age.days}d" if age.days > 0 else f"{age.seconds // 3600}h"

            lines.append(f"### {req.program_name}")
            lines.append(f"- **Version:** {req.version}")
            lines.append(f"- **Requested by:** {req.requested_by}")
            lines.append(f"- **Age:** {age_str}")
            if req.fusion_project:
                lines.append(f"- **Fusion Project:** {req.fusion_project}")
            if req.operation:
                lines.append(f"- **Operation:** {req.operation}")
            lines.append("")

        lines.append(f"*Total: {len(requests)} pending*")

        return "\n".join(lines)

    def format_approval_result(self, result: ApprovalResult) -> str:
        """Format approval result for display."""
        if result.success:
            emoji = "✅" if result.action == "approve" else "❌"
            return f"{emoji} {result.message}"
        else:
            return f"⚠️ {result.message}"
