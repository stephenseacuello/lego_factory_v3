"""
Quality Routes - Quality Management API Endpoints

LegoMCP World-Class Manufacturing System v5.0

ISA-95 Quality Operations:
- Inspection management
- Measurement recording
- LEGO compatibility testing
- SPC/Control charts
- FMEA (Phase 10)
- QFD (Phase 11)
- Computer Vision Quality (Phase 13)
- Digital Thread & Traceability (Phase 15)
- Zero-Defect (Phase 21)
"""

from flask import Blueprint

from .inspections import inspections_bp
from .measurements import measurements_bp
from .lego_compatibility import lego_bp
from .spc import spc_bp
from .fmea import fmea_bp
from .qfd import qfd_bp
from .zero_defect import zero_defect_bp
from .vision import vision_bp
from .traceability import traceability_bp
from .heatmap import heatmap_bp

# Combined quality blueprint
quality_bp = Blueprint('quality', __name__, url_prefix='/api/quality')

# Register sub-blueprints
quality_bp.register_blueprint(inspections_bp)
quality_bp.register_blueprint(measurements_bp)
quality_bp.register_blueprint(lego_bp)
quality_bp.register_blueprint(spc_bp)
quality_bp.register_blueprint(fmea_bp)
quality_bp.register_blueprint(qfd_bp)
quality_bp.register_blueprint(zero_defect_bp)
quality_bp.register_blueprint(vision_bp)
quality_bp.register_blueprint(traceability_bp)
quality_bp.register_blueprint(heatmap_bp)

__all__ = [
    'quality_bp',
    'inspections_bp',
    'measurements_bp',
    'lego_bp',
    'spc_bp',
    'fmea_bp',
    'qfd_bp',
    'zero_defect_bp',
    'vision_bp',
    'traceability_bp',
    'heatmap_bp',
]
