"""
MRP Routes - Material Requirements Planning API Endpoints

ISA-95 Level 4 Planning:
- MRP run and results
- Capacity planning
- Scheduling
- Material Master / Inventory Control
"""

from flask import Blueprint

from .planning import planning_bp
from .capacity import capacity_bp
from .materials import materials_bp

# Combined MRP blueprint
mrp_bp = Blueprint('mrp', __name__, url_prefix='/api/mrp')

# Register sub-blueprints
mrp_bp.register_blueprint(planning_bp)
mrp_bp.register_blueprint(capacity_bp)
mrp_bp.register_blueprint(materials_bp)

__all__ = [
    'mrp_bp',
    'planning_bp',
    'capacity_bp',
    'materials_bp',
]
