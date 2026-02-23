"""
Simulation Routes - Discrete Event Simulation API

LegoMCP World-Class Manufacturing System v5.0
Phase 18: Discrete Event Simulation (DES)

Provides:
- Factory simulation
- What-if scenario analysis
- Capacity planning
- Bottleneck identification
"""

from flask import Blueprint

from .scenarios import scenarios_bp

simulation_bp = Blueprint('simulation', __name__, url_prefix='/api/simulation')

simulation_bp.register_blueprint(scenarios_bp)

__all__ = ['simulation_bp', 'scenarios_bp']
