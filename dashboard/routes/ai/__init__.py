"""
AI Routes - Manufacturing Intelligence API

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 17: AI Manufacturing Copilot + v6.0 Extensions
"""

from flask import Blueprint, render_template

ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


# Dashboard Page Routes
@ai_bp.route('/page', methods=['GET'])
@ai_bp.route('/copilot/page', methods=['GET'])
def copilot_page():
    """Render AI copilot dashboard page."""
    return render_template('pages/ai/copilot_dashboard.html')


@ai_bp.route('/cam/page', methods=['GET'])
@ai_bp.route('/cam-copilot/page', methods=['GET'])
def cam_copilot_page():
    """Render CAM Copilot dashboard page."""
    return render_template('pages/ai/cam_dashboard.html')


# Import v5.0 modules
from . import copilot  # noqa: E402, F401

# Import v6.0 modules - Multi-Agent Orchestration, Causal AI, etc.
from .causal import causal_bp  # noqa: E402
from .orchestration import orchestration_bp  # noqa: E402
from .closed_loop import closed_loop_bp  # noqa: E402
from .generative import generative_bp  # noqa: E402
from .research import research_bp  # noqa: E402
from .actions import actions_bp  # noqa: E402
from .cam_copilot import cam_copilot_bp  # noqa: E402

# Register CAM copilot as sub-blueprint
ai_bp.register_blueprint(cam_copilot_bp)

# Export blueprints for registration
__all__ = [
    'ai_bp',
    'causal_bp',
    'orchestration_bp',
    'closed_loop_bp',
    'generative_bp',
    'research_bp',
    'actions_bp',
    'cam_copilot_bp',
]
