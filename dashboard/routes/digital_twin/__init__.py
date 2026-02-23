"""
Digital Twin Routes

Real-time equipment state, predictive maintenance, and simulation APIs.

v2.0: Added data_api with live/simulation hybrid support for dashboards.
"""

from flask import Blueprint

from .twin import twin_bp
from .maintenance import maintenance_bp
from .simulation import simulation_bp
from .data_api import data_api_bp

digital_twin_bp = Blueprint('digital_twin', __name__, url_prefix='/api/twin')

# Register sub-blueprints
digital_twin_bp.register_blueprint(twin_bp)
digital_twin_bp.register_blueprint(maintenance_bp)
digital_twin_bp.register_blueprint(simulation_bp)
digital_twin_bp.register_blueprint(data_api_bp)

__all__ = ['digital_twin_bp', 'data_api_bp']
