"""
Manufacturing Routes - MES/MOM API Endpoints

LegoMCP World-Class Manufacturing System v5.0

ISA-95 Level 3 Manufacturing Operations Management:
- Shop Floor Display
- Work Order Management
- Work Center Control
- OEE Dashboard
- Equipment Integration
- Alternative Routings (Phase 9)
"""

from flask import Blueprint

from .shop_floor import shop_floor_bp
from .work_orders import work_orders_bp
from .work_centers import work_centers_bp
from .oee import oee_bp
from .routings import routings_bp
from .cnc_milling import cnc_bp

# Combined manufacturing blueprint
manufacturing_bp = Blueprint('manufacturing', __name__, url_prefix='/api/mes')

# Register sub-blueprints
manufacturing_bp.register_blueprint(shop_floor_bp)
manufacturing_bp.register_blueprint(work_orders_bp)
manufacturing_bp.register_blueprint(work_centers_bp)
manufacturing_bp.register_blueprint(oee_bp)
manufacturing_bp.register_blueprint(routings_bp)
manufacturing_bp.register_blueprint(cnc_bp)

__all__ = [
    'manufacturing_bp',
    'shop_floor_bp',
    'work_orders_bp',
    'work_centers_bp',
    'oee_bp',
    'routings_bp',
    'cnc_bp',
]
