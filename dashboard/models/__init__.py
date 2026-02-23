"""
LEGO MCP Manufacturing Database Models

ISA-95 compliant SQLAlchemy models for the Industry 4.0 Digital Manufacturing Platform.

Modules:
- base: Database connection and base model class
- manufacturing: Work orders, operations, work centers
- inventory: Parts, BOM, locations, transactions
- quality: Inspections, metrics, NCRs
- analytics: OEE events, cost ledger, digital twin state
"""

from .base import db, Base, init_db, get_db_session
from .manufacturing import (
    WorkCenter,
    WorkOrder,
    WorkOrderOperation,
    Routing,
    MaintenanceRecord,
)
from .inventory import (
    Part,
    BOM,
    InventoryLocation,
    InventoryTransaction,
    InventoryBalance,
)
from .quality import (
    QualityInspection,
    QualityMetric,
)
from .analytics import (
    OEEEvent,
    CostLedger,
    DigitalTwinState,
)
from .users import User, AuditLog, Customer
from .customer_order import (
    CustomerOrder,
    OrderLine,
    OrderStatus,
    OrderPriority,
    DeliveryPromise,
    CustomerOrderRepository,
)
from .routing_extended import (
    AlternativeRouting,
    RoutingOperation,
    RoutingStatus,
    RoutingRepository,
)
from .bom_extended import (
    EnhancedBOM,
    EnhancedBOMComponent,
    BOMComponentTag,
    FunctionalRole,
    QualityCriticality,
    EnhancedBOMRepository,
)

__all__ = [
    # Base
    'db',
    'Base',
    'init_db',
    'get_db_session',

    # Manufacturing
    'WorkCenter',
    'WorkOrder',
    'WorkOrderOperation',
    'Routing',
    'MaintenanceRecord',

    # Inventory
    'Part',
    'BOM',
    'InventoryLocation',
    'InventoryTransaction',
    'InventoryBalance',

    # Quality
    'QualityInspection',
    'QualityMetric',

    # Analytics
    'OEEEvent',
    'CostLedger',
    'DigitalTwinState',

    # Users
    'User',
    'AuditLog',
    'Customer',

    # Customer Orders (Phase 8)
    'CustomerOrder',
    'OrderLine',
    'OrderStatus',
    'OrderPriority',
    'DeliveryPromise',
    'CustomerOrderRepository',

    # Alternative Routings (Phase 9)
    'AlternativeRouting',
    'RoutingOperation',
    'RoutingStatus',
    'RoutingRepository',

    # Enhanced BOM (Phase 9)
    'EnhancedBOM',
    'EnhancedBOMComponent',
    'BOMComponentTag',
    'FunctionalRole',
    'QualityCriticality',
    'EnhancedBOMRepository',
]
