"""
Mock MES/ERP Adapter for Testing.

Provides simulated work orders and data for testing without external system.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .base_adapter import (
    BaseMesAdapter,
    WorkOrder,
    WorkOrderStatus,
    Operation,
    OperationStatus,
    ProductionReport,
    InspectionResult,
    MaterialStock,
)

logger = logging.getLogger(__name__)


class MockMesAdapter(BaseMesAdapter):
    """
    Mock adapter for testing MES integration.

    Generates realistic work orders and maintains state for testing.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})

        # In-memory storage
        self.work_orders: Dict[str, WorkOrder] = {}
        self.production_reports: List[ProductionReport] = []
        self.inspection_results: List[InspectionResult] = []
        self.material_stock: Dict[str, List[MaterialStock]] = {}

        # Generate sample data
        self._generate_sample_data()

    def _generate_sample_data(self):
        """Generate sample work orders and materials."""
        # Sample parts
        parts = [
            ("PART-001", "Aluminum Bracket", ["milling", "drilling"]),
            ("PART-002", "Steel Mounting Plate", ["milling", "tapping"]),
            ("PART-003", "Copper Heat Sink", ["milling", "engraving"]),
            ("PART-004", "Acrylic Panel", ["routing", "engraving"]),
            ("PART-005", "Wood Sign", ["routing", "engraving"]),
        ]

        # Generate work orders
        for i, (part_num, part_desc, caps) in enumerate(parts, 1):
            wo_id = f"WO-{datetime.now().strftime('%Y%m%d')}-{i:04d}"

            operations = [
                Operation(
                    operation_id=f"{wo_id}-OP10",
                    operation_number=10,
                    operation_name="Setup & Fixture",
                    work_center="SETUP",
                    setup_time_minutes=15.0,
                    run_time_minutes=5.0,
                    status=OperationStatus.PENDING,
                ),
                Operation(
                    operation_id=f"{wo_id}-OP20",
                    operation_number=20,
                    operation_name="Machining",
                    work_center="CNC",
                    setup_time_minutes=5.0,
                    run_time_minutes=30.0,
                    required_capabilities=caps,
                    status=OperationStatus.PENDING,
                    program_id=f"PRG-{part_num}",
                ),
                Operation(
                    operation_id=f"{wo_id}-OP30",
                    operation_number=30,
                    operation_name="Inspection",
                    work_center="QC",
                    setup_time_minutes=0.0,
                    run_time_minutes=10.0,
                    status=OperationStatus.PENDING,
                ),
            ]

            wo = WorkOrder(
                work_order_id=wo_id,
                part_number=part_num,
                part_description=part_desc,
                quantity=10,
                due_date=datetime.now() + timedelta(days=i + 2),
                priority=2 if i < 3 else 1,
                status=WorkOrderStatus.RELEASED,
                customer_id=f"CUST-{100 + i}",
                customer_name=f"Customer {i}",
                routing_id=f"RTG-{part_num}",
                operations=operations,
                material_lots=[f"LOT-{part_num}-001"],
                created_at=datetime.now() - timedelta(hours=i),
                updated_at=datetime.now(),
            )
            self.work_orders[wo_id] = wo

        # Generate material stock
        materials = [
            ("MAT-AL6061", "Aluminum 6061-T6", 100.0),
            ("MAT-ST304", "Stainless Steel 304", 50.0),
            ("MAT-CU101", "Copper 101", 25.0),
            ("MAT-ACRYLIC", "Clear Acrylic Sheet", 200.0),
            ("MAT-PLYWOOD", "Baltic Birch Plywood", 150.0),
        ]

        for mat_id, mat_name, qty in materials:
            self.material_stock[mat_id] = [
                MaterialStock(
                    material_id=mat_id,
                    material_name=mat_name,
                    lot_number=f"LOT-{mat_id}-001",
                    quantity_available=qty,
                    quantity_reserved=0.0,
                    unit="ea",
                    location="RACK-A1",
                    supplier_id="SUP-001",
                )
            ]

        logger.info(f"Generated {len(self.work_orders)} sample work orders")

    def connect(self) -> bool:
        """Mock connection always succeeds."""
        self._connected = True
        logger.info("Mock MES adapter connected")
        return True

    def disconnect(self) -> None:
        """Mock disconnect."""
        self._connected = False
        logger.info("Mock MES adapter disconnected")

    def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            'status': 'ok',
            'adapter': 'mock',
            'work_orders': len(self.work_orders),
            'timestamp': datetime.utcnow().isoformat(),
        }

    def get_pending_work_orders(
        self,
        machine_id: Optional[str] = None,
        limit: int = 100
    ) -> List[WorkOrder]:
        """Get pending work orders."""
        pending = [
            wo for wo in self.work_orders.values()
            if wo.status in (WorkOrderStatus.PENDING, WorkOrderStatus.RELEASED)
        ]

        # Sort by priority (desc) and due date (asc)
        pending.sort(key=lambda w: (-w.priority, w.due_date or datetime.max))

        return pending[:limit]

    def get_work_order(self, work_order_id: str) -> Optional[WorkOrder]:
        """Get specific work order."""
        return self.work_orders.get(work_order_id)

    def update_work_order_status(
        self,
        work_order_id: str,
        status: WorkOrderStatus,
        notes: str = ""
    ) -> bool:
        """Update work order status."""
        if work_order_id in self.work_orders:
            self.work_orders[work_order_id].status = status
            self.work_orders[work_order_id].updated_at = datetime.now()
            self.work_orders[work_order_id].notes = notes
            logger.info(f"Updated WO {work_order_id} to {status.value}")
            return True
        return False

    def update_operation_status(
        self,
        work_order_id: str,
        operation_id: str,
        status: OperationStatus,
        machine_id: str = "",
        notes: str = ""
    ) -> bool:
        """Update operation status."""
        wo = self.work_orders.get(work_order_id)
        if not wo:
            return False

        for op in wo.operations:
            if op.operation_id == operation_id:
                op.status = status
                op.machine_id = machine_id
                logger.info(f"Updated operation {operation_id} to {status.value}")
                return True

        return False

    def submit_production_report(self, report: ProductionReport) -> bool:
        """Submit production report."""
        self.production_reports.append(report)
        logger.info(f"Received production report for WO {report.work_order_id}")

        # Auto-update operation status
        self.update_operation_status(
            report.work_order_id,
            report.operation_id,
            OperationStatus.COMPLETED if report.quantity_completed > 0 else OperationStatus.RUNNING,
            report.machine_id
        )

        return True

    def submit_inspection_result(self, result: InspectionResult) -> bool:
        """Submit inspection result."""
        self.inspection_results.append(result)
        logger.info(f"Received inspection result {result.inspection_id}: {'PASS' if result.passed else 'FAIL'}")
        return True

    def get_material_stock(
        self,
        material_id: str,
        location: Optional[str] = None
    ) -> List[MaterialStock]:
        """Get material stock."""
        stock = self.material_stock.get(material_id, [])
        if location:
            stock = [s for s in stock if s.location == location]
        return stock

    def consume_material(
        self,
        material_id: str,
        lot_number: str,
        quantity: float,
        work_order_id: str
    ) -> bool:
        """Consume material."""
        for stock in self.material_stock.get(material_id, []):
            if stock.lot_number == lot_number:
                if stock.quantity_available >= quantity:
                    stock.quantity_available -= quantity
                    logger.info(f"Consumed {quantity} of {material_id} for WO {work_order_id}")
                    return True
                else:
                    logger.warning(f"Insufficient stock for {material_id}")
                    return False
        return False

    # Additional methods for testing
    def add_work_order(self, work_order: WorkOrder) -> None:
        """Add work order (for testing)."""
        self.work_orders[work_order.work_order_id] = work_order

    def get_production_reports(self) -> List[ProductionReport]:
        """Get all submitted production reports."""
        return self.production_reports

    def get_inspection_results(self) -> List[InspectionResult]:
        """Get all submitted inspection results."""
        return self.inspection_results

    def reset(self) -> None:
        """Reset to initial state."""
        self.work_orders.clear()
        self.production_reports.clear()
        self.inspection_results.clear()
        self.material_stock.clear()
        self._generate_sample_data()
