"""
ISA-95 Operations Management

Implements ISA-95 Operations Schedule and Performance tracking.

Reference: IEC 62264-3 (Activity Models)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class RequestState(Enum):
    """Operations Request States."""
    FORECAST = "Forecast"
    RELEASED = "Released"
    WAITING = "Waiting"
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"
    ABORTED = "Aborted"
    HELD = "Held"
    SUSPENDED = "Suspended"
    CLOSED = "Closed"


class ResponseState(Enum):
    """Operations Response States."""
    WAITING = "Waiting"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    ABORTED = "Aborted"


class OperationsType(Enum):
    """ISA-95 Operations Types."""
    PRODUCTION = "Production"
    MAINTENANCE = "Maintenance"
    QUALITY = "Quality"
    INVENTORY = "Inventory"


@dataclass
class SegmentRequirement:
    """Operations Segment Requirement."""
    id: str
    process_segment_id: str
    description: Optional[str] = None

    # Timing
    earliest_start: Optional[datetime] = None
    latest_end: Optional[datetime] = None
    duration: Optional[timedelta] = None

    # Requirements
    material_requirements: List[Dict] = field(default_factory=list)
    equipment_requirements: List[Dict] = field(default_factory=list)
    personnel_requirements: List[Dict] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationsRequest:
    """ISA-95 Operations Request."""
    id: str
    operations_type: OperationsType = OperationsType.PRODUCTION
    description: Optional[str] = None
    priority: int = 3  # 1 (highest) to 5 (lowest)

    # Timing
    requested_start: Optional[datetime] = None
    requested_end: Optional[datetime] = None

    # State
    state: RequestState = RequestState.WAITING

    # Segments
    segment_requirements: List[SegmentRequirement] = field(default_factory=list)

    # Tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_segment(
        self,
        process_segment_id: str,
        **kwargs
    ) -> SegmentRequirement:
        """Add a segment requirement."""
        segment = SegmentRequirement(
            id=f"{self.id}_seg_{len(self.segment_requirements) + 1:03d}",
            process_segment_id=process_segment_id,
            **kwargs
        )
        self.segment_requirements.append(segment)
        return segment


@dataclass
class SegmentResponse:
    """Operations Segment Response."""
    id: str
    process_segment_id: str

    # Timing
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Actuals
    material_actuals: List[Dict] = field(default_factory=list)
    equipment_actuals: List[Dict] = field(default_factory=list)
    personnel_actuals: List[Dict] = field(default_factory=list)

    # Production data
    segment_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationsResponse:
    """ISA-95 Operations Response."""
    id: str
    operations_request_id: str
    state: ResponseState = ResponseState.WAITING

    # Timing
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None

    # Segments
    segment_responses: List[SegmentResponse] = field(default_factory=list)


@dataclass
class PerformanceRecord:
    """Performance record for analytics."""
    request_id: str
    response_id: str
    segment_id: str

    # Metrics
    good_count: int = 0
    reject_count: int = 0
    scrap_count: int = 0

    # Timing
    planned_duration: Optional[timedelta] = None
    actual_duration: Optional[timedelta] = None

    # Resources
    equipment_used: List[str] = field(default_factory=list)
    material_consumed: Dict[str, float] = field(default_factory=dict)

    # Calculated
    @property
    def yield_rate(self) -> float:
        total = self.good_count + self.reject_count + self.scrap_count
        return self.good_count / total if total > 0 else 0.0

    @property
    def efficiency(self) -> float:
        if self.planned_duration and self.actual_duration:
            return self.planned_duration.total_seconds() / max(
                self.actual_duration.total_seconds(), 1
            )
        return 1.0


class OperationsSchedule:
    """
    ISA-95 Operations Schedule Manager.

    Manages operations requests and scheduling for manufacturing.

    Features:
    - Request lifecycle management
    - Priority-based scheduling
    - Resource conflict detection
    - Schedule optimization hooks

    Usage:
        >>> schedule = OperationsSchedule()
        >>> request = schedule.create_request(...)
        >>> schedule.schedule_request(request.id)
        >>> schedule.start_request(request.id)
    """

    def __init__(
        self,
        schedule_id: Optional[str] = None,
        operations_type: OperationsType = OperationsType.PRODUCTION
    ):
        """
        Initialize Operations Schedule.

        Args:
            schedule_id: Unique schedule identifier
            operations_type: Type of operations
        """
        self.id = schedule_id or f"SCHED_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self.operations_type = operations_type

        # Requests
        self._requests: Dict[str, OperationsRequest] = {}
        self._request_queue: List[str] = []  # Priority queue

        # Responses
        self._responses: Dict[str, OperationsResponse] = {}

        # Callbacks
        self._state_callbacks: List[Callable] = []

        logger.info(f"OperationsSchedule initialized: {self.id}")

    def create_request(
        self,
        request_id: Optional[str] = None,
        description: Optional[str] = None,
        priority: int = 3,
        requested_start: Optional[datetime] = None,
        requested_end: Optional[datetime] = None
    ) -> OperationsRequest:
        """
        Create a new operations request.

        Args:
            request_id: Unique request ID
            description: Request description
            priority: Priority (1-5)
            requested_start: Requested start time
            requested_end: Requested end time

        Returns:
            Created OperationsRequest
        """
        request_id = request_id or f"REQ_{uuid.uuid4().hex[:8].upper()}"

        request = OperationsRequest(
            id=request_id,
            operations_type=self.operations_type,
            description=description,
            priority=max(1, min(5, priority)),
            requested_start=requested_start,
            requested_end=requested_end,
            state=RequestState.WAITING
        )

        self._requests[request_id] = request
        self._insert_into_queue(request_id)

        logger.info(f"Created request: {request_id}")
        return request

    def get_request(self, request_id: str) -> Optional[OperationsRequest]:
        """Get a request by ID."""
        return self._requests.get(request_id)

    def update_request_state(
        self,
        request_id: str,
        new_state: RequestState
    ) -> bool:
        """
        Update request state.

        Args:
            request_id: Request ID
            new_state: New state

        Returns:
            True if updated
        """
        request = self._requests.get(request_id)
        if not request:
            return False

        old_state = request.state
        request.state = new_state
        request.updated_at = datetime.utcnow()

        # Trigger callbacks
        for callback in self._state_callbacks:
            try:
                callback(request_id, old_state, new_state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

        logger.info(f"Request {request_id}: {old_state.value} -> {new_state.value}")
        return True

    def schedule_request(self, request_id: str) -> bool:
        """
        Move request to Ready state.

        Args:
            request_id: Request ID

        Returns:
            True if scheduled
        """
        request = self._requests.get(request_id)
        if not request or request.state != RequestState.WAITING:
            return False

        return self.update_request_state(request_id, RequestState.READY)

    def start_request(self, request_id: str) -> Optional[OperationsResponse]:
        """
        Start executing a request.

        Args:
            request_id: Request ID

        Returns:
            OperationsResponse if started
        """
        request = self._requests.get(request_id)
        if not request or request.state != RequestState.READY:
            return None

        # Create response
        response = OperationsResponse(
            id=f"{request_id}_RESP",
            operations_request_id=request_id,
            state=ResponseState.RUNNING,
            actual_start=datetime.utcnow()
        )

        # Create segment responses
        for seg_req in request.segment_requirements:
            seg_resp = SegmentResponse(
                id=f"{seg_req.id}_RESP",
                process_segment_id=seg_req.process_segment_id,
                actual_start=datetime.utcnow()
            )
            response.segment_responses.append(seg_resp)

        self._responses[response.id] = response
        self.update_request_state(request_id, RequestState.RUNNING)

        logger.info(f"Started request {request_id}")
        return response

    def complete_request(
        self,
        request_id: str,
        segment_data: Optional[Dict[str, Dict]] = None
    ) -> bool:
        """
        Complete a request.

        Args:
            request_id: Request ID
            segment_data: Data for each segment

        Returns:
            True if completed
        """
        request = self._requests.get(request_id)
        if not request or request.state != RequestState.RUNNING:
            return False

        # Update response
        response = self._responses.get(f"{request_id}_RESP")
        if response:
            response.state = ResponseState.COMPLETED
            response.actual_end = datetime.utcnow()

            # Update segment responses
            if segment_data:
                for seg_resp in response.segment_responses:
                    seg_id = seg_resp.process_segment_id
                    if seg_id in segment_data:
                        seg_resp.segment_data.update(segment_data[seg_id])
                    seg_resp.actual_end = datetime.utcnow()

        self.update_request_state(request_id, RequestState.COMPLETED)
        self._request_queue.remove(request_id) if request_id in self._request_queue else None

        logger.info(f"Completed request {request_id}")
        return True

    def abort_request(self, request_id: str, reason: Optional[str] = None) -> bool:
        """
        Abort a request.

        Args:
            request_id: Request ID
            reason: Abort reason

        Returns:
            True if aborted
        """
        request = self._requests.get(request_id)
        if not request:
            return False

        response = self._responses.get(f"{request_id}_RESP")
        if response:
            response.state = ResponseState.ABORTED
            response.actual_end = datetime.utcnow()

        self.update_request_state(request_id, RequestState.ABORTED)
        self._request_queue.remove(request_id) if request_id in self._request_queue else None

        logger.warning(f"Aborted request {request_id}: {reason}")
        return True

    def get_next_request(self) -> Optional[OperationsRequest]:
        """Get the next ready request from queue."""
        for request_id in self._request_queue:
            request = self._requests.get(request_id)
            if request and request.state == RequestState.READY:
                return request
        return None

    def get_requests_by_state(self, state: RequestState) -> List[OperationsRequest]:
        """Get all requests in a specific state."""
        return [r for r in self._requests.values() if r.state == state]

    def on_state_change(self, callback: Callable) -> None:
        """Register state change callback."""
        self._state_callbacks.append(callback)

    def _insert_into_queue(self, request_id: str) -> None:
        """Insert request into priority queue."""
        request = self._requests.get(request_id)
        if not request:
            return

        # Find insertion point (lower priority number = higher priority)
        insert_idx = len(self._request_queue)
        for i, existing_id in enumerate(self._request_queue):
            existing = self._requests.get(existing_id)
            if existing and request.priority < existing.priority:
                insert_idx = i
                break

        self._request_queue.insert(insert_idx, request_id)

    def get_schedule_info(self) -> Dict[str, Any]:
        """Get schedule information."""
        state_counts = {}
        for request in self._requests.values():
            state_counts[request.state.value] = state_counts.get(request.state.value, 0) + 1

        return {
            "id": self.id,
            "operations_type": self.operations_type.value,
            "total_requests": len(self._requests),
            "queue_length": len(self._request_queue),
            "state_counts": state_counts
        }


class ProductionPerformance:
    """
    ISA-95 Production Performance Tracker.

    Tracks and analyzes production performance metrics.

    Features:
    - OEE calculation
    - Quality metrics
    - Equipment utilization
    - Production trends

    Usage:
        >>> tracker = ProductionPerformance()
        >>> tracker.record_production(...)
        >>> oee = tracker.calculate_oee(...)
    """

    def __init__(self):
        """Initialize performance tracker."""
        self._records: List[PerformanceRecord] = []
        self._equipment_uptime: Dict[str, timedelta] = {}
        self._equipment_downtime: Dict[str, timedelta] = {}

        logger.info("ProductionPerformance initialized")

    def record_production(
        self,
        request_id: str,
        response_id: str,
        segment_id: str,
        good_count: int,
        reject_count: int = 0,
        scrap_count: int = 0,
        planned_duration: Optional[timedelta] = None,
        actual_duration: Optional[timedelta] = None,
        equipment_used: Optional[List[str]] = None,
        material_consumed: Optional[Dict[str, float]] = None
    ) -> PerformanceRecord:
        """
        Record production data.

        Args:
            request_id: Operations request ID
            response_id: Operations response ID
            segment_id: Segment ID
            good_count: Good parts produced
            reject_count: Rejected parts
            scrap_count: Scrapped parts
            planned_duration: Planned production time
            actual_duration: Actual production time
            equipment_used: Equipment IDs used
            material_consumed: Material consumption dict

        Returns:
            PerformanceRecord
        """
        record = PerformanceRecord(
            request_id=request_id,
            response_id=response_id,
            segment_id=segment_id,
            good_count=good_count,
            reject_count=reject_count,
            scrap_count=scrap_count,
            planned_duration=planned_duration,
            actual_duration=actual_duration,
            equipment_used=equipment_used or [],
            material_consumed=material_consumed or {}
        )

        self._records.append(record)

        logger.debug(f"Recorded production: {good_count} good, {reject_count} reject")
        return record

    def record_equipment_time(
        self,
        equipment_id: str,
        uptime: timedelta,
        downtime: Optional[timedelta] = None
    ) -> None:
        """Record equipment up/down time."""
        current_uptime = self._equipment_uptime.get(equipment_id, timedelta())
        self._equipment_uptime[equipment_id] = current_uptime + uptime

        if downtime:
            current_downtime = self._equipment_downtime.get(equipment_id, timedelta())
            self._equipment_downtime[equipment_id] = current_downtime + downtime

    def calculate_oee(
        self,
        equipment_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Calculate OEE (Overall Equipment Effectiveness).

        OEE = Availability × Performance × Quality

        Args:
            equipment_id: Filter by equipment
            start_time: Start of period
            end_time: End of period

        Returns:
            Dict with availability, performance, quality, oee
        """
        # Filter records
        records = self._records
        if equipment_id:
            records = [r for r in records if equipment_id in r.equipment_used]

        if not records:
            return {"availability": 0, "performance": 0, "quality": 0, "oee": 0}

        # Availability
        uptime = self._equipment_uptime.get(equipment_id, timedelta(hours=1))
        downtime = self._equipment_downtime.get(equipment_id, timedelta())
        total_time = uptime + downtime
        availability = uptime.total_seconds() / max(total_time.total_seconds(), 1)

        # Performance (actual vs planned)
        total_planned = sum(
            (r.planned_duration or timedelta()).total_seconds() for r in records
        )
        total_actual = sum(
            (r.actual_duration or timedelta()).total_seconds() for r in records
        )
        performance = total_planned / max(total_actual, 1) if total_planned else 1.0

        # Quality
        total_good = sum(r.good_count for r in records)
        total_produced = sum(r.good_count + r.reject_count + r.scrap_count for r in records)
        quality = total_good / max(total_produced, 1)

        # OEE
        oee = availability * performance * quality

        return {
            "availability": round(availability, 4),
            "performance": round(min(performance, 1.0), 4),
            "quality": round(quality, 4),
            "oee": round(oee, 4)
        }

    def get_yield_summary(
        self,
        segment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get yield summary."""
        records = self._records
        if segment_id:
            records = [r for r in records if r.segment_id == segment_id]

        if not records:
            return {"total_produced": 0, "good": 0, "reject": 0, "scrap": 0, "yield": 0}

        total_good = sum(r.good_count for r in records)
        total_reject = sum(r.reject_count for r in records)
        total_scrap = sum(r.scrap_count for r in records)
        total = total_good + total_reject + total_scrap

        return {
            "total_produced": total,
            "good": total_good,
            "reject": total_reject,
            "scrap": total_scrap,
            "yield": round(total_good / max(total, 1), 4)
        }

    def get_material_consumption(
        self,
        material_id: Optional[str] = None
    ) -> Dict[str, float]:
        """Get material consumption summary."""
        consumption: Dict[str, float] = {}

        for record in self._records:
            for mat_id, amount in record.material_consumed.items():
                if material_id and mat_id != material_id:
                    continue
                consumption[mat_id] = consumption.get(mat_id, 0) + amount

        return consumption

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary."""
        if not self._records:
            return {"record_count": 0}

        yield_summary = self.get_yield_summary()
        oee = self.calculate_oee()

        return {
            "record_count": len(self._records),
            "yield_summary": yield_summary,
            "oee": oee,
            "equipment_count": len(self._equipment_uptime)
        }
