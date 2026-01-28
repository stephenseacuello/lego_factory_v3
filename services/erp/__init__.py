"""
LEGO Factory v3 - ERP (Enterprise Resource Planning) Services
==============================================================

ISA-95 Level 4 services for business planning and logistics.
These services manage the business-level aspects of manufacturing
operations including inventory, sales, purchasing, and planning.

Core Capabilities
-----------------
**Item Master Management** (ItemService):
    - Product and material master data
    - Bills of Material (BOM) management
    - Item categories, units of measure
    - Product lifecycle states
    - Engineering change management

**Inventory Management** (InventoryService):
    - Stock levels by location and lot
    - Inventory transactions (receipts, issues, transfers)
    - Stock valuation methods (FIFO, average cost)
    - Cycle counting and adjustments
    - Safety stock and reorder point management

**Sales Management** (SalesService):
    - Customer order management
    - Order-to-delivery tracking
    - Available-to-Promise (ATP) calculation
    - Pricing and discount management
    - Customer credit management

**Purchasing Management** (PurchasingService):
    - Purchase order creation and tracking
    - Vendor management and evaluation
    - Request for Quote (RFQ) processing
    - Goods receipt and invoice verification
    - Supplier performance metrics

**Materials Requirements Planning** (MRPService):
    - Demand explosion from sales orders
    - Time-phased requirements calculation
    - Planned order generation
    - Lead time and lot size considerations
    - What-if analysis and simulation

ISA-95 Integration
------------------
ERP services implement ISA-95 Level 4 activities:

    Business Planning:
        - Master data management (items, BOMs, routings)
        - Demand management and forecasting
        - Inventory planning and control

    Order Processing:
        - Customer order entry and management
        - Production order creation
        - Purchase order generation

    Integration Points:
        - Work orders flow down to MES (Level 3)
        - Actual production data flows up from MES
        - B2MML message exchange for ISA-95 compliance

Example:
    from services.erp import (
        get_item_service, get_inventory_service,
        get_mrp_service, MRPPlan
    )

    # Get current inventory
    inv_svc = get_inventory_service()
    stock = await inv_svc.get_stock_level(item_id="BRICK-2x4-RED")

    # Run MRP
    mrp_svc = get_mrp_service()
    plan = await mrp_svc.run_mrp(
        items=["BRICK-2x4-RED", "BRICK-2x4-BLUE"],
        horizon_days=30
    )
    for req in plan.requirements:
        print(f"{req.item_id}: Need {req.quantity} by {req.due_date}")
"""

from services.erp.item_service import ItemService, get_item_service
from services.erp.inventory_service import InventoryService, get_inventory_service
from services.erp.sales_service import SalesService, get_sales_service
from services.erp.purchasing_service import PurchasingService, get_purchasing_service
from services.erp.mrp_service import MRPService, MRPPlan, MRPRequirement, get_mrp_service

__all__ = [
    # Item Service
    'ItemService',
    'get_item_service',
    # Inventory Service
    'InventoryService',
    'get_inventory_service',
    # Sales Service
    'SalesService',
    'get_sales_service',
    # Purchasing Service
    'PurchasingService',
    'get_purchasing_service',
    # MRP Service
    'MRPService',
    'MRPPlan',
    'MRPRequirement',
    'get_mrp_service',
]
