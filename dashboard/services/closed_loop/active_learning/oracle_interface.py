"""
Oracle Interface - Human-in-the-loop labeling interface.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import asyncio
import uuid
import logging

logger = logging.getLogger(__name__)


class LabelStatus(Enum):
    """Status of label request."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    EXPIRED = "expired"


@dataclass
class LabelRequest:
    """Request for human labeling."""
    request_id: str
    sample_id: str
    sample_data: Dict[str, Any]
    model_prediction: Optional[Any] = None
    model_confidence: Optional[float] = None
    priority: int = 0
    status: LabelStatus = LabelStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LabelResponse:
    """Response from human labeler."""
    request_id: str
    label: Any
    labeler_id: str
    confidence: float = 1.0
    completed_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class OracleInterface:
    """
    Interface for human-in-the-loop labeling.

    Features:
    - Label request queue management
    - Multi-labeler support
    - Quality control (agreement checking)
    - Async/sync label collection
    """

    def __init__(self,
                timeout_seconds: float = 3600.0,
                require_agreement: bool = False,
                min_labelers: int = 1):
        """
        Initialize oracle interface.

        Args:
            timeout_seconds: Request expiry time
            require_agreement: Require multiple labelers to agree
            min_labelers: Minimum labelers per sample if agreement required
        """
        self.timeout_seconds = timeout_seconds
        self.require_agreement = require_agreement
        self.min_labelers = min_labelers

        self._pending_requests: Dict[str, LabelRequest] = {}
        self._completed: Dict[str, List[LabelResponse]] = {}
        self._listeners: List[Callable] = []

    def create_request(self,
                      sample_id: str,
                      sample_data: Dict[str, Any],
                      model_prediction: Optional[Any] = None,
                      model_confidence: Optional[float] = None,
                      priority: int = 0,
                      context: Optional[Dict] = None) -> LabelRequest:
        """
        Create label request.

        Args:
            sample_id: Unique sample identifier
            sample_data: Sample data for labeler
            model_prediction: Current model prediction
            model_confidence: Model confidence
            priority: Higher = more urgent
            context: Additional context

        Returns:
            Created request
        """
        request = LabelRequest(
            request_id=str(uuid.uuid4())[:8],
            sample_id=sample_id,
            sample_data=sample_data,
            model_prediction=model_prediction,
            model_confidence=model_confidence,
            priority=priority,
            context=context or {}
        )

        self._pending_requests[request.request_id] = request
        logger.info(f"Created label request: {request.request_id}")

        return request

    def create_batch_requests(self,
                             samples: List[Dict[str, Any]],
                             model: Optional[Any] = None) -> List[LabelRequest]:
        """Create batch of label requests."""
        requests = []

        for sample in samples:
            sample_id = sample.get('id', str(uuid.uuid4())[:8])
            sample_data = sample.get('data', sample)

            prediction = None
            confidence = None

            if model and 'features' in sample:
                try:
                    import numpy as np
                    features = np.array(sample['features']).reshape(1, -1)
                    prediction = model.predict(features)[0]

                    if hasattr(model, 'predict_proba'):
                        probs = model.predict_proba(features)[0]
                        confidence = float(max(probs))
                except Exception as e:
                    logger.warning(f"Could not get model prediction: {e}")

            request = self.create_request(
                sample_id=sample_id,
                sample_data=sample_data,
                model_prediction=prediction,
                model_confidence=confidence,
                priority=sample.get('priority', 0)
            )
            requests.append(request)

        return requests

    def get_pending_requests(self,
                            limit: int = 50,
                            labeler_id: Optional[str] = None) -> List[LabelRequest]:
        """Get pending label requests."""
        # Filter expired
        self._expire_old_requests()

        requests = [
            r for r in self._pending_requests.values()
            if r.status == LabelStatus.PENDING or
               (r.status == LabelStatus.ASSIGNED and r.assigned_to == labeler_id)
        ]

        # Sort by priority (high first) then age (old first)
        requests.sort(key=lambda r: (-r.priority, r.created_at))

        return requests[:limit]

    def assign_request(self, request_id: str, labeler_id: str) -> bool:
        """Assign request to labeler."""
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        if request.status != LabelStatus.PENDING:
            return False

        request.status = LabelStatus.ASSIGNED
        request.assigned_to = labeler_id
        return True

    def submit_label(self,
                    request_id: str,
                    label: Any,
                    labeler_id: str,
                    confidence: float = 1.0,
                    notes: str = "") -> LabelResponse:
        """
        Submit label for request.

        Args:
            request_id: Request ID
            label: Assigned label
            labeler_id: ID of labeler
            confidence: Labeler confidence
            notes: Optional notes

        Returns:
            Label response
        """
        if request_id not in self._pending_requests:
            raise ValueError(f"Request not found: {request_id}")

        response = LabelResponse(
            request_id=request_id,
            label=label,
            labeler_id=labeler_id,
            confidence=confidence,
            notes=notes
        )

        if request_id not in self._completed:
            self._completed[request_id] = []
        self._completed[request_id].append(response)

        # Check if request is complete
        request = self._pending_requests[request_id]

        if self.require_agreement:
            if len(self._completed[request_id]) >= self.min_labelers:
                # Check agreement
                labels = [r.label for r in self._completed[request_id]]
                if len(set(str(l) for l in labels)) == 1:
                    request.status = LabelStatus.COMPLETED
                    del self._pending_requests[request_id]
        else:
            request.status = LabelStatus.COMPLETED
            del self._pending_requests[request_id]

        # Notify listeners
        self._notify_listeners(response)

        logger.info(f"Label submitted for {request_id}: {label}")
        return response

    def skip_request(self, request_id: str, reason: str = "") -> bool:
        """Skip a label request."""
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        request.status = LabelStatus.SKIPPED
        request.context['skip_reason'] = reason
        del self._pending_requests[request_id]

        return True

    def get_label(self, request_id: str) -> Optional[Any]:
        """Get final label for request."""
        if request_id not in self._completed:
            return None

        responses = self._completed[request_id]

        if not responses:
            return None

        if len(responses) == 1:
            return responses[0].label

        # Multiple labelers - use majority vote or weighted average
        labels = [r.label for r in responses]
        confidences = [r.confidence for r in responses]

        # For categorical labels
        try:
            from collections import Counter
            label_counts = Counter(str(l) for l in labels)
            most_common = label_counts.most_common(1)[0][0]

            # Return original label (not string)
            for label in labels:
                if str(label) == most_common:
                    return label
        except Exception:
            pass

        # For numeric labels - weighted average
        try:
            import numpy as np
            labels_numeric = np.array(labels, dtype=float)
            weights = np.array(confidences)
            return float(np.average(labels_numeric, weights=weights))
        except Exception:
            pass

        return responses[0].label

    def get_all_labels(self) -> Dict[str, Any]:
        """Get all completed labels."""
        return {
            request_id: self.get_label(request_id)
            for request_id in self._completed
        }

    def add_listener(self, listener: Callable[[LabelResponse], None]) -> None:
        """Add listener for label completions."""
        self._listeners.append(listener)

    def _notify_listeners(self, response: LabelResponse) -> None:
        """Notify listeners of new label."""
        for listener in self._listeners:
            try:
                listener(response)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def _expire_old_requests(self) -> None:
        """Mark old requests as expired."""
        now = datetime.utcnow()
        to_expire = []

        for request_id, request in self._pending_requests.items():
            age = (now - request.created_at).total_seconds()
            if age > self.timeout_seconds:
                to_expire.append(request_id)

        for request_id in to_expire:
            self._pending_requests[request_id].status = LabelStatus.EXPIRED
            del self._pending_requests[request_id]
            logger.info(f"Request expired: {request_id}")

    async def wait_for_label(self,
                            request_id: str,
                            timeout: float = 300.0) -> Optional[Any]:
        """Async wait for label completion."""
        start = datetime.utcnow()

        while (datetime.utcnow() - start).total_seconds() < timeout:
            if request_id in self._completed:
                return self.get_label(request_id)

            if request_id not in self._pending_requests:
                return None

            await asyncio.sleep(1.0)

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get labeling statistics."""
        total_completed = len(self._completed)
        total_pending = len(self._pending_requests)

        labeler_counts = {}
        for responses in self._completed.values():
            for r in responses:
                labeler_counts[r.labeler_id] = labeler_counts.get(r.labeler_id, 0) + 1

        return {
            'total_completed': total_completed,
            'total_pending': total_pending,
            'labels_per_labeler': labeler_counts,
            'avg_labels_per_request': (
                sum(len(r) for r in self._completed.values()) / total_completed
                if total_completed > 0 else 0
            )
        }
