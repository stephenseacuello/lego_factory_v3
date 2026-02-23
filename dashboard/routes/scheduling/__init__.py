"""
Scheduling Routes - Advanced Production Scheduling API

LegoMCP World-Class Manufacturing System v5.0
Phase 12: Advanced Scheduling Algorithms

ISA-95 Level 3/4 Scheduling Operations:
- CP-SAT optimal scheduling
- NSGA-II multi-objective optimization
- RL-based real-time dispatching
- Pareto front analysis
"""

from flask import Blueprint

from .optimizer import optimizer_bp

# Combined scheduling blueprint
scheduling_bp = Blueprint('scheduling', __name__, url_prefix='/api/scheduling')

# Register sub-blueprints
scheduling_bp.register_blueprint(optimizer_bp)

__all__ = [
    'scheduling_bp',
    'optimizer_bp',
]
