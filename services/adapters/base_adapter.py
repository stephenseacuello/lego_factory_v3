"""
Base MES/ERP Adapter Interface.

Abstract interface for integrating with external MES (Manufacturing Execution System)
and ERP (Enterprise Resource Planning) systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AdapterError(Exception):
    """Base exception for adapter errors."""
    pass


class ConnectionError(AdapterError):
    """Failed to connect to external system."""
    pass


class SyncError(AdapterError):
    """Failed to sync data with external system."""
    pass


class WorkOrderStatus(Enum):
    """Work order status values."""
    PENDING = "pending"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class OperationStatus(Enum):
    """Operation status values."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkOrder:
    """Work order from MES/ERP system."""
    work_order_id: str
    part_number: str
    part_description: str = ""
    quantity: int = 1
    due_date: Optional[datetime] = None
    priority: int = 1  # 1=low, 2=normal, 3=high, 4=urgent
    status: WorkOrderStatus = WorkOrderStatus.PENDING
    customer_id: str = ""
    customer_name: str = ""
    routing_id: str = ""
    operations: List["Operation"] = field(default_factory=list)
    material_lots: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Operation:
    """Single operation within a work order."""
    operation_id: str
    operation_number: int
    operation_name: str
    work_center: str = ""
    machine_id: str = ""
    setup_time_minutes: float = 0.0
    run_time_minutes: float = 0.0
    required_capabilities: List[str] = field(default_factory=list)
    status: OperationStatus = OperationStatus.PENDING
    program_id: str = ""
    instructions: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductionReport:
    """Production report to send to MES/ERP."""
    work_order_id: str
    operation_id: str
    machine_id: str
    operator_id: str = ""
    quantity_completed: int = 0
    quantity_scrapped: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    cycle_time_seconds: float = 0.0
    setup_time_seconds: float = 0.0
    downtime_seconds: float = 0.0
    downtime_reason: str = ""
    notes: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InspectionResult:
    """Quality inspection result."""
    inspection_id: str
    work_order_id: str
    operation_id: str
    part_serial: str = ""
    machine_id: str = ""
    inspector_id: str = ""
    inspection_type: str = "inline"  # inline, final, receiving
    passed: bool = True
    measurements: List["Measurement"] = field(default_factory=list)
    defects: List["Defect"] = field(default_factory=list)
    inspection_time: Optional[datetime] = None
    notes: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Measurement:
    """Single measurement in an inspection."""
    feature_name: str
    nominal_value: float
    measured_value: float
    upper_tolerance: float
    lower_tolerance: float
    unit: str = "mm"
    passed: bool = True


@dataclass
class Defect:
    """Defect found during inspection."""
    defect_code: str
    defect_description: str
    severity: str = "minor"  # minor, major, critical
    quantity: int = 1
    location: str = ""


@dataclass
class MaterialStock:
    """Material inventory information."""
    material_id: str
    material_name: str
    lot_number: str = ""
    quantity_available: float = 0.0
    quantity_reserved: float = 0.0
    unit: str = "ea"
    location: str = ""
    expiration_date: Optional[datetime] = None
    supplier_id: str = ""
    certificate_of_conformance: str = ""


class BaseMesAdapter(ABC):
    """
    Abstract base class for MES/ERP adapters.

    Implementations should handle connection management, authentication,
    and data transformation for specific MES/ERP systems.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.

        Args:
            config: Adapter-specific configuration dictionary
        """
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if adapter is connected to external system."""
        return self._connected

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to external system.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from external system."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check health of external system connection.

        Returns:
            Dictionary with health status information
        """
        pass

    # Work Order Methods
    @abstractmethod
    def get_pending_work_orders(
        self,
        machine_id: Optional[str] = None,
        limit: int = 100
    ) -> List[WorkOrder]:
        """
        Fetch pending work orders from MES.

        Args:
            machine_id: Filter by machine capability (optional)
            limit: Maximum number of work orders to return

        Returns:
            List of pending work orders
        """
        pass

    @abstractmethod
    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        """
        Fetch a specific work order by ID.

        Args:
            work_order_id: Work order identifier

        Returns:
            WorkOrder if found, None otherwise
        """
        pass

    @abstractmethod
    def update_work_order_status(
        self,
        work_order_id: str,
        status: WorkOrderStatus,
        notes: str = ""
    ) -> bool:
        """
        Update work order status in MES.

        Args:
            work_order_id: Work order identifier
            status: New status
            notes: Optional status notes

        Returns:
            True if update successful
        """
        pass

    @abstractmethod
    def update_operation_status(
        self,
        work_order_id: str,
        operation_id: str,
        status: OperationStatus,
        machine_id: str = "",
        notes: str = ""
    ) -> bool:
        """
        Update operation status in MES.

        Args:
            work_order_id: Work order identifier
            operation_id: Operation identifier
            status: New status
            machine_id: Machine performing operation
            notes: Optional status notes

        Returns:
            True if update successful
        """
        pass

    # Production Reporting
    @abstractmethod
    def submit_production_report(self, report: ProductionReport) -> bool:
        """
        Submit production report to MES.

        Args:
            report: Production report data

        Returns:
            True if submission successful
        """
        pass

    # Quality Data
    @abstractmethod
    def submit_inspection_result(self, result: InspectionResult) -> bool:
        """
        Submit quality inspection result to MES.

        Args:
            result: Inspection result data

        Returns:
            True if submission successful
        """
        pass

    # Material Management
    @abstractmethod
    def get_material_stock(
        self,
        material_id: str,
        location: Optional[str] = None
    ) -> List[MaterialStock]:
        """
        Get material inventory information.

        Args:
            material_id: Material identifier
            location: Filter by storage location

        Returns:
            List of material stock records
        """
        pass

    @abstractmethod
    def consume_material(
        self,
        material_id: str,
        lot_number: str,
        quantity: float,
        work_order_id: str
    ) -> bool:
        """
        Record material consumption against work order.

        Args:
            material_id: Material identifier
            lot_number: Lot being consumed
            quantity: Quantity consumed
            work_order_id: Work order consuming material

        Returns:
            True if consumption recorded
        """
        pass

    # Utility Methods
    def to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                if isinstance(value, Enum):
                    result[field_name] = value.value
                elif isinstance(value, datetime):
                    result[field_name] = value.isoformat()
                elif isinstance(value, list):
                    result[field_name] = [self.to_dict(v) for v in value]
                elif hasattr(value, '__dataclass_fields__'):
                    result[field_name] = self.to_dict(value)
                else:
                    result[field_name] = value
            return result
        return obj
