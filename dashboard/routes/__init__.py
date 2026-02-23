"""
Dashboard Routes

All Flask route blueprints.
LEGO MCP v6.0 World-Class Manufacturing Research Platform
"""

from .main import main_bp
from .catalog import catalog_bp
from .builder import builder_bp
from .files import files_bp
from .history import history_bp
from .status import status_bp
from .tools import tools_bp
from .settings import settings_bp
from .api import api_bp
from .manufacturing import manufacturing_bp
from .quality import quality_bp
from .erp import erp_bp
from .mrp import mrp_bp
from .digital_twin import digital_twin_bp
from .events import events_bp
from .ai import ai_bp
from .scheduling import scheduling_bp
from .supply_chain import supply_chain_bp
from .compliance import compliance_bp
from .sustainability import sustainability_bp
from .simulation import simulation_bp
from .hmi import hmi_bp
from .edge import edge_bp
from .unity import unity_bp
from .robotics import robotics_bp
from .supervision import supervision_bp

# v6.0 AI Extensions
from .ai import (
    causal_bp,
    orchestration_bp,
    closed_loop_bp,
    generative_bp,
    research_bp,
    actions_bp,
)

__all__ = [
    # Core routes
    "main_bp",
    "catalog_bp",
    "builder_bp",
    "files_bp",
    "history_bp",
    "status_bp",
    "tools_bp",
    "settings_bp",
    "api_bp",
    "manufacturing_bp",
    "quality_bp",
    "erp_bp",
    "mrp_bp",
    "digital_twin_bp",
    "events_bp",
    "ai_bp",
    "scheduling_bp",
    "supply_chain_bp",
    "compliance_bp",
    "sustainability_bp",
    "simulation_bp",
    "hmi_bp",
    "edge_bp",
    "unity_bp",
    "robotics_bp",
    "supervision_bp",
    # v6.0 AI Extensions
    "causal_bp",
    "orchestration_bp",
    "closed_loop_bp",
    "generative_bp",
    "research_bp",
    "actions_bp",
]
