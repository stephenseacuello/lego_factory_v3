"""
Supply Chain Routes - Supplier & Procurement API

LegoMCP World-Class Manufacturing System v5.0
Phase 22: Supply Chain Integration

Provides:
- Supplier portal
- Automated procurement
- Supplier quality management
- EDI/API integration
- Supply Chain Digital Twin
"""

from flask import Blueprint

from .suppliers import suppliers_bp
from .twin import supply_chain_twin_bp

supply_chain_bp = Blueprint('supply_chain', __name__, url_prefix='/api/supply-chain')

supply_chain_bp.register_blueprint(suppliers_bp)
supply_chain_bp.register_blueprint(supply_chain_twin_bp)

__all__ = ['supply_chain_bp', 'suppliers_bp', 'supply_chain_twin_bp']
