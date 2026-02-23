"""
Human-in-the-Loop Manager for AI Manufacturing Systems

Manages escalation and human oversight for AI decisions:
- Multi-level escalation paths
- Timeout and fallback handling
- Audit trail and accountability
- Operator notification

Critical for safety-critical manufacturing AI per IEC 61508.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable
from enum import Enum
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Escalation levels for human oversight."""
    NONE = 0              # No escalation needed
    NOTIFICATION = 1      # Notify operator, continue automatically
    CONFIRMATION = 2      # Require operator confirmation
    REVIEW = 3            # Require operator review and possible edit
    APPROVAL = 4          # Require supervisor approval
    EMERGENCY = 5         # Immediate supervisor intervention


class EscalationStatus(Enum):
    """Status of an escalation request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class OperatorRole(Enum):
    """Operator roles for escalation."""
    OPERATOR = "operator"
    SENIOR_OPERATOR = "senior_operator"
    SUPERVISOR = "supervisor"
    SAFETY_OFFICER = "safety_officer"
    SYSTEM_ADMIN = "system_admin"


@dataclass
class EscalationRequest:
    """
    An escalation request requiring human attention.

    Attributes:
        request_id: Unique request identifier
        level: Escalation level
        operation: Operation requiring escalation
        context: Additional context
        ai_recommendation: AI's recommendation
        confidence: AI confidence
        required_role: Minimum role required
        timeout_seconds: Time before timeout
        created_at: Creation timestamp
    """
    request_id: str
    level: EscalationLevel
    operation: str
    context: Dict[str, Any]
    ai_recommendation: Any
    confidence: float
    required_role: OperatorRole = OperatorRole.OPERATOR
    timeout_seconds: float = 300.0  # 5 minutes default
    created_at: float = field(default_factory=time.time)
    status: EscalationStatus = EscalationStatus.PENDING
    resolved_by: Optional[str] = None
    resolved_at: Optional[float] = None
    resolution_notes: str = ""
    final_action: Optional[Any] = None


@dataclass
class EscalationResponse:
    """
    Response to an escalation request.

    Attributes:
        request_id: Original request ID
        status: Resolution status
        approved_action: Approved action (may differ from AI recommendation)
        operator_id: ID of responding operator
        notes: Operator notes
        response_time_seconds: Time to respond
    """
    request_id: str
    status: EscalationStatus
    approved_action: Optional[Any]
    operator_id: str
    notes: str = ""
    response_time_seconds: float = 0.0


@dataclass
class HILConfig:
    """
    Human-in-the-loop configuration.

    Attributes:
        default_timeout: Default timeout for escalations
        escalation_chain: Role escalation chain
        notification_handlers: Notification callbacks
        enable_audit: Enable audit logging
        max_pending_requests: Maximum pending escalations
    """
    default_timeout_seconds: float = 300.0
    escalation_chain: List[OperatorRole] = field(default_factory=lambda: [
        OperatorRole.OPERATOR,
        OperatorRole.SENIOR_OPERATOR,
        OperatorRole.SUPERVISOR,
        OperatorRole.SAFETY_OFFICER
    ])
    enable_audit: bool = True
    max_pending_requests: int = 100
    auto_escalate_on_timeout: bool = True
    timeout_escalation_delay_seconds: float = 60.0


class HumanInLoopManager:
    """
    Manages human-in-the-loop interactions for AI systems.

    Features:
    - Asynchronous escalation handling
    - Multi-level escalation paths
    - Timeout and fallback policies
    - Audit trail for compliance
    - Notification system integration

    Usage:
        >>> hil = HumanInLoopManager(config)
        >>> response = await hil.escalate(
        ...     level=EscalationLevel.CONFIRMATION,
        ...     operation="set_temperature",
        ...     ai_recommendation={"temp": 220},
        ...     confidence=0.75
        ... )
        >>> if response.status == EscalationStatus.APPROVED:
        ...     execute(response.approved_action)
    """

    def __init__(
        self,
        config: Optional[HILConfig] = None,
        notification_handler: Optional[Callable] = None,
        audit_handler: Optional[Callable] = None
    ):
        """
        Initialize Human-in-Loop manager.

        Args:
            config: HIL configuration
            notification_handler: Callback for notifications
            audit_handler: Callback for audit events
        """
        self.config = config or HILConfig()
        self.notification_handler = notification_handler
        self.audit_handler = audit_handler

        # Active requests
        self._pending_requests: Dict[str, EscalationRequest] = {}
        self._request_history: List[EscalationRequest] = []

        # Response handlers (for async responses)
        self._response_futures: Dict[str, asyncio.Future] = {}

        logger.info("HumanInLoopManager initialized")

    async def escalate(
        self,
        level: EscalationLevel,
        operation: str,
        ai_recommendation: Any,
        confidence: float,
        context: Optional[Dict] = None,
        timeout_seconds: Optional[float] = None,
        required_role: Optional[OperatorRole] = None
    ) -> EscalationResponse:
        """
        Escalate a decision to human oversight.

        Args:
            level: Escalation level
            operation: Operation description
            ai_recommendation: AI's recommended action
            confidence: AI confidence
            context: Additional context
            timeout_seconds: Custom timeout
            required_role: Minimum role required

        Returns:
            EscalationResponse with human decision
        """
        # Check capacity
        if len(self._pending_requests) >= self.config.max_pending_requests:
            logger.warning("Max pending escalations reached")
            return EscalationResponse(
                request_id="",
                status=EscalationStatus.REJECTED,
                approved_action=None,
                operator_id="system",
                notes="System at capacity"
            )

        # Create request
        request = EscalationRequest(
            request_id=str(uuid.uuid4()),
            level=level,
            operation=operation,
            context=context or {},
            ai_recommendation=ai_recommendation,
            confidence=confidence,
            required_role=required_role or self._get_required_role(level),
            timeout_seconds=timeout_seconds or self.config.default_timeout_seconds
        )

        # Handle based on level
        if level == EscalationLevel.NONE:
            return EscalationResponse(
                request_id=request.request_id,
                status=EscalationStatus.APPROVED,
                approved_action=ai_recommendation,
                operator_id="auto",
                notes="No escalation required"
            )

        if level == EscalationLevel.NOTIFICATION:
            # Notify but proceed automatically
            await self._send_notification(request)
            return EscalationResponse(
                request_id=request.request_id,
                status=EscalationStatus.APPROVED,
                approved_action=ai_recommendation,
                operator_id="auto",
                notes="Notification sent, proceeding automatically"
            )

        # Store request and wait for response
        self._pending_requests[request.request_id] = request

        # Create future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._response_futures[request.request_id] = future

        # Send notification
        await self._send_notification(request)

        # Audit log
        self._audit("escalation_created", request)

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(
                future,
                timeout=request.timeout_seconds
            )
            return response

        except asyncio.TimeoutError:
            # Handle timeout
            return await self._handle_timeout(request)

        finally:
            # Cleanup
            self._pending_requests.pop(request.request_id, None)
            self._response_futures.pop(request.request_id, None)
            self._request_history.append(request)

    def respond(
        self,
        request_id: str,
        status: EscalationStatus,
        operator_id: str,
        approved_action: Optional[Any] = None,
        notes: str = ""
    ) -> bool:
        """
        Respond to an escalation request.

        Args:
            request_id: Request ID
            status: Resolution status
            operator_id: Responding operator ID
            approved_action: Approved action
            notes: Operator notes

        Returns:
            True if response was accepted
        """
        if request_id not in self._pending_requests:
            logger.warning(f"Unknown request ID: {request_id}")
            return False

        request = self._pending_requests[request_id]
        future = self._response_futures.get(request_id)

        if future is None or future.done():
            logger.warning(f"Request {request_id} already resolved")
            return False

        # Update request
        request.status = status
        request.resolved_by = operator_id
        request.resolved_at = time.time()
        request.resolution_notes = notes
        request.final_action = approved_action if approved_action else request.ai_recommendation

        # Create response
        response = EscalationResponse(
            request_id=request_id,
            status=status,
            approved_action=request.final_action,
            operator_id=operator_id,
            notes=notes,
            response_time_seconds=time.time() - request.created_at
        )

        # Resolve future
        future.set_result(response)

        # Audit log
        self._audit("escalation_resolved", request, response)

        return True

    async def _send_notification(self, request: EscalationRequest) -> None:
        """Send notification for escalation request."""
        if self.notification_handler:
            try:
                notification = {
                    "request_id": request.request_id,
                    "level": request.level.name,
                    "operation": request.operation,
                    "ai_recommendation": request.ai_recommendation,
                    "confidence": request.confidence,
                    "required_role": request.required_role.value,
                    "timeout_at": datetime.fromtimestamp(
                        request.created_at + request.timeout_seconds
                    ).isoformat(),
                    "context": request.context
                }

                if asyncio.iscoroutinefunction(self.notification_handler):
                    await self.notification_handler(notification)
                else:
                    self.notification_handler(notification)

            except Exception as e:
                logger.error(f"Notification error: {e}")

    async def _handle_timeout(self, request: EscalationRequest) -> EscalationResponse:
        """Handle escalation timeout."""
        request.status = EscalationStatus.TIMEOUT
        request.resolved_at = time.time()

        # Auto-escalate if configured
        if self.config.auto_escalate_on_timeout:
            next_role = self._get_next_escalation_role(request.required_role)
            if next_role:
                logger.info(f"Auto-escalating {request.request_id} to {next_role.value}")

                # Create new escalation at higher level
                new_level = EscalationLevel(min(request.level.value + 1, EscalationLevel.EMERGENCY.value))
                return await self.escalate(
                    level=new_level,
                    operation=request.operation,
                    ai_recommendation=request.ai_recommendation,
                    confidence=request.confidence,
                    context={**request.context, "escalated_from": request.request_id},
                    required_role=next_role
                )

        # Fallback to rejection on timeout
        self._audit("escalation_timeout", request)

        return EscalationResponse(
            request_id=request.request_id,
            status=EscalationStatus.TIMEOUT,
            approved_action=None,
            operator_id="timeout",
            notes="Request timed out without response",
            response_time_seconds=request.timeout_seconds
        )

    def _get_required_role(self, level: EscalationLevel) -> OperatorRole:
        """Get required role for escalation level."""
        role_mapping = {
            EscalationLevel.NONE: OperatorRole.OPERATOR,
            EscalationLevel.NOTIFICATION: OperatorRole.OPERATOR,
            EscalationLevel.CONFIRMATION: OperatorRole.OPERATOR,
            EscalationLevel.REVIEW: OperatorRole.SENIOR_OPERATOR,
            EscalationLevel.APPROVAL: OperatorRole.SUPERVISOR,
            EscalationLevel.EMERGENCY: OperatorRole.SAFETY_OFFICER
        }
        return role_mapping.get(level, OperatorRole.OPERATOR)

    def _get_next_escalation_role(self, current_role: OperatorRole) -> Optional[OperatorRole]:
        """Get next role in escalation chain."""
        try:
            current_idx = self.config.escalation_chain.index(current_role)
            if current_idx + 1 < len(self.config.escalation_chain):
                return self.config.escalation_chain[current_idx + 1]
        except ValueError:
            pass
        return None

    def _audit(self, event_type: str, request: EscalationRequest, response: Optional[EscalationResponse] = None) -> None:
        """Log audit event."""
        if not self.config.enable_audit:
            return

        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "request_id": request.request_id,
            "level": request.level.name,
            "operation": request.operation,
            "ai_confidence": request.confidence,
            "required_role": request.required_role.value,
            "status": request.status.value
        }

        if response:
            audit_entry.update({
                "resolved_by": response.operator_id,
                "response_time_seconds": response.response_time_seconds,
                "notes": response.notes
            })

        logger.info(f"HIL Audit: {audit_entry}")

        if self.audit_handler:
            try:
                self.audit_handler(audit_entry)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")

    def get_pending_requests(
        self,
        role: Optional[OperatorRole] = None
    ) -> List[EscalationRequest]:
        """Get pending escalation requests, optionally filtered by role."""
        requests = list(self._pending_requests.values())

        if role:
            role_idx = self.config.escalation_chain.index(role) if role in self.config.escalation_chain else 0
            requests = [
                r for r in requests
                if r.required_role in self.config.escalation_chain[:role_idx + 1]
            ]

        return sorted(requests, key=lambda r: (r.level.value, r.created_at), reverse=True)

    def get_request_stats(self) -> Dict[str, Any]:
        """Get escalation statistics."""
        total = len(self._request_history)
        if total == 0:
            return {"total_requests": 0}

        status_counts = {}
        level_counts = {}
        total_response_time = 0.0
        response_count = 0

        for request in self._request_history:
            status_counts[request.status.value] = status_counts.get(request.status.value, 0) + 1
            level_counts[request.level.name] = level_counts.get(request.level.name, 0) + 1

            if request.resolved_at and request.created_at:
                total_response_time += request.resolved_at - request.created_at
                response_count += 1

        return {
            "total_requests": total,
            "pending_requests": len(self._pending_requests),
            "status_distribution": status_counts,
            "level_distribution": level_counts,
            "average_response_time_seconds": total_response_time / max(1, response_count),
            "approval_rate": status_counts.get("approved", 0) / max(1, total)
        }

    def cancel_request(self, request_id: str, reason: str = "") -> bool:
        """Cancel a pending escalation request."""
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        request.status = EscalationStatus.CANCELLED
        request.resolution_notes = reason

        future = self._response_futures.get(request_id)
        if future and not future.done():
            future.set_result(EscalationResponse(
                request_id=request_id,
                status=EscalationStatus.CANCELLED,
                approved_action=None,
                operator_id="system",
                notes=reason
            ))

        self._audit("escalation_cancelled", request)
        return True
