"""
HMI Routes - Human Machine Interface API

LegoMCP World-Class Manufacturing System v5.0
Phase 20: HMI & AR Work Instructions

Provides:
- Work instructions delivery
- Operator guidance
- Voice interface support
- AR marker data
- VR Training System
"""

from flask import Blueprint

from .operator import operator_bp
from .vr_training import vr_training_bp

hmi_bp = Blueprint('hmi', __name__, url_prefix='/api/hmi')

hmi_bp.register_blueprint(operator_bp)
hmi_bp.register_blueprint(vr_training_bp)

__all__ = ['hmi_bp', 'operator_bp', 'vr_training_bp']
