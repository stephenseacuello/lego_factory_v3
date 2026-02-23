"""
ERP Routes - Enterprise Resource Planning API Endpoints

LegoMCP World-Class Manufacturing System v6.0

ISA-95 Level 4 Business Planning:
- BOM management
- Costing and variance analysis
- Procurement and purchase orders
- Demand forecasting
- Customer Orders & ATP/CTP (Phase 8)
- Quality Costing & ABC (Phase 16)
- Vendor/Supplier Management (Phase 17)
- Accounts Receivable & Payable (Phase 17)
- General Ledger Integration (Phase 17)

Standards:
- GAAP/IFRS Financial Compliance
- SOX Internal Controls
- ISO 9001 Supplier Quality
"""

from flask import Blueprint

from .bom import bom_bp
from .costing import costing_bp
from .procurement import procurement_bp
from .demand import demand_bp
from .orders import orders_bp
from .quality_costing import quality_costing_bp
from .vendors import vendors_bp
from .financials import financials_bp

# Combined ERP blueprint
erp_bp = Blueprint('erp', __name__, url_prefix='/api/erp')

# Register sub-blueprints
erp_bp.register_blueprint(bom_bp)
erp_bp.register_blueprint(costing_bp)
erp_bp.register_blueprint(procurement_bp)
erp_bp.register_blueprint(demand_bp)
erp_bp.register_blueprint(orders_bp)
erp_bp.register_blueprint(quality_costing_bp)
erp_bp.register_blueprint(vendors_bp)
erp_bp.register_blueprint(financials_bp)

__all__ = [
    'erp_bp',
    'bom_bp',
    'costing_bp',
    'procurement_bp',
    'demand_bp',
    'orders_bp',
    'quality_costing_bp',
    'vendors_bp',
    'financials_bp',
]
