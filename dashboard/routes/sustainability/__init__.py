"""
Sustainability Routes - Carbon & Energy Tracking API

LegoMCP World-Class Manufacturing System v5.0
Phase 19: Sustainability & Carbon Tracking

ISO 14001 environmental management:
- CO2 tracking per unit
- Energy consumption optimization
- Scope 1/2/3 emissions
- Circular economy metrics
"""

from flask import Blueprint

from .carbon import carbon_bp

sustainability_bp = Blueprint('sustainability', __name__, url_prefix='/api/sustainability')

sustainability_bp.register_blueprint(carbon_bp)

__all__ = ['sustainability_bp', 'carbon_bp']
