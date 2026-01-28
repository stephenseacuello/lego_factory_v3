"""
Base Equipment Controller - Abstract interface for all equipment types.

ISA-95 Level 2 Equipment Integration Base Class.
Provides common interface for status monitoring, job control, and OEE data collection.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class EquipmentStatus(Enum):
    """Standard equipment status codes per ISA-95."""
    OFFLINE = "offline"           # Not connected/powered off
    IDLE = "idle"                 # Ready, no active job
    RUNNING = "running"           # Actively processing
    PAUSED = "paused"             # Job paused
    ERROR = "error"               # Fault condition
    MAINTENANCE = "maintenance"   # Scheduled maintenance
    SETUP = "setup"               # Changeover/setup
    WARMUP = "warmup"             # Heating/calibrating


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class EquipmentState:
    """Current equipment state snapshot."""
    status: EquipmentStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Job info
    current_job_id: Optional[str] = None
    job_progress_percent: float = 0.0
    job_elapsed_seconds: float = 0.0
    job_remaining_seconds: float = 0.0

    # Equipment-specific data
    temperatures: Dict[str, float] = field(default_factory=dict)
    positions: Dict[str, float] = field(default_factory=dict)
    speeds: Dict[str, float] = field(default_factory=dict)

    # Error info
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Metadata
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Result of a completed job."""
    job_id: str
    status: JobStatus
    start_time: datetime
    end_time: datetime

    # Production data
    parts_produced: int = 0
    parts_defective: int = 0

    # Time breakdown
    run_time_seconds: float = 0.0
    idle_time_seconds: float = 0.0
    downtime_seconds: float = 0.0

    # Material usage
    material_used: float = 0.0  # grams for 3D printing, mm for CNC
    material_unit: str = "grams"

    # Error info
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Raw data
    extra_data: Dict[str, Any] = field(default_factory=dict)


class BaseEquipmentController(ABC):
    """
    Abstract base class for all equipment controllers.

    Implements common interface for:
    - Connection management
    - Status monitoring
    - Job submission and control
    - OEE data collection
    """

    def __init__(
        self,
        work_center_id: str,
        name: str,
        connection_info: Dict[str, Any]
    ):
        self.work_center_id = work_center_id
        self.name = name
        self.connection_info = connection_info
        self._connected = False
        self._last_state: Optional[EquipmentState] = None
        self._state_callbacks: List[callable] = []

    @property
    def is_connected(self) -> bool:
        """Check if equipment is connected."""
        return self._connected

    @property
    def last_state(self) -> Optional[EquipmentState]:
        """Get last known equipment state."""
        return self._last_state

    def register_state_callback(self, callback: callable):
        """Register callback for state changes."""
        self._state_callbacks.append(callback)

    def _notify_state_change(self, state: EquipmentState):
        """Notify all registered callbacks of state change."""
        self._last_state = state
        for callback in self._state_callbacks:
            try:
                callback(self.work_center_id, state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    # Connection Management

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to equipment.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from equipment."""
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """
        Check if equipment is responsive.

        Returns:
            True if equipment responds, False otherwise.
        """
        pass

    # Status Monitoring

    @abstractmethod
    async def get_state(self) -> EquipmentState:
        """
        Get current equipment state.

        Returns:
            EquipmentState with current status and data.
        """
        pass

    @abstractmethod
    async def get_capabilities(self) -> Dict[str, Any]:
        """
        Get equipment capabilities and configuration.

        Returns:
            Dict with build volume, speeds, supported materials, etc.
        """
        pass

    # Job Control

    @abstractmethod
    async def submit_job(
        self,
        job_id: str,
        file_path: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Submit a job to the equipment.

        Args:
            job_id: Unique job identifier (work order operation ID)
            file_path: Path to job file (G-code, etc.)
            parameters: Optional job parameters

        Returns:
            True if job submitted successfully.
        """
        pass

    @abstractmethod
    async def start_job(self) -> bool:
        """
        Start the current/pending job.

        Returns:
            True if job started successfully.
        """
        pass

    @abstractmethod
    async def pause_job(self) -> bool:
        """
        Pause the current job.

        Returns:
            True if job paused successfully.
        """
        pass

    @abstractmethod
    async def resume_job(self) -> bool:
        """
        Resume a paused job.

        Returns:
            True if job resumed successfully.
        """
        pass

    @abstractmethod
    async def cancel_job(self) -> bool:
        """
        Cancel the current job.

        Returns:
            True if job cancelled successfully.
        """
        pass

    @abstractmethod
    async def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """
        Get result of a completed job.

        Args:
            job_id: Job identifier

        Returns:
            JobResult if found, None otherwise.
        """
        pass

    # Equipment Control

    @abstractmethod
    async def home(self) -> bool:
        """
        Home all axes.

        Returns:
            True if homing started/completed successfully.
        """
        pass

    @abstractmethod
    async def emergency_stop(self) -> bool:
        """
        Trigger emergency stop.

        Returns:
            True if E-stop triggered successfully.
        """
        pass

    # OEE Data Collection

    def calculate_oee_metrics(self, job_result: JobResult) -> Dict[str, float]:
        """
        Calculate OEE metrics from job result.

        Returns:
            Dict with availability, performance, quality, and overall OEE.
        """
        total_time = (job_result.end_time - job_result.start_time).total_seconds()

        if total_time <= 0:
            return {
                'availability': 0.0,
                'performance': 0.0,
                'quality': 0.0,
                'oee': 0.0
            }

        # Availability = Run Time / Planned Production Time
        planned_time = total_time - job_result.idle_time_seconds
        if planned_time > 0:
            availability = job_result.run_time_seconds / planned_time
        else:
            availability = 0.0

        # Performance = Ideal Cycle Time * Total Count / Run Time
        # For 3D printing, we use actual vs estimated time
        if job_result.run_time_seconds > 0:
            total_parts = job_result.parts_produced + job_result.parts_defective
            # Assume 1 part per job for now
            performance = min(1.0, total_parts / max(1, total_parts))
        else:
            performance = 0.0

        # Quality = Good Count / Total Count
        total_parts = job_result.parts_produced + job_result.parts_defective
        if total_parts > 0:
            quality = job_result.parts_produced / total_parts
        else:
            quality = 0.0 if job_result.status == JobStatus.FAILED else 1.0

        # OEE = Availability * Performance * Quality
        oee = availability * performance * quality

        return {
            'availability': round(availability * 100, 1),
            'performance': round(performance * 100, 1),
            'quality': round(quality * 100, 1),
            'oee': round(oee * 100, 1)
        }
