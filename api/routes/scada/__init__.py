"""
LEGO Factory v3 - SCADA API Routes
==================================
"""

from flask import Blueprint

scada_bp = Blueprint('scada', __name__, url_prefix='/scada')

from api.routes.scada.machines import machines_bp
from api.routes.scada.tags import tags_bp
from api.routes.scada.alarms import alarms_bp
from api.routes.scada.historian import historian_bp
from api.routes.scada.recipes import recipes_bp

# Register sub-blueprints
scada_bp.register_blueprint(machines_bp)
scada_bp.register_blueprint(tags_bp)
scada_bp.register_blueprint(alarms_bp)
scada_bp.register_blueprint(historian_bp)
scada_bp.register_blueprint(recipes_bp)
