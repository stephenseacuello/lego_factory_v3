"""
LEGO Factory v3 - Routes
========================
Blueprint registration for all view routes.
"""

from flask import Flask

from api.routes.dashboard import dashboard_bp
from api.routes.scada_views import scada_bp
from api.routes.mes_views import mes_bp
from api.routes.lego_views import lego_bp
from api.routes.erp_views import erp_bp
from api.routes.qms_views import qms_bp
from api.routes.cmms_views import cmms_bp
from api.routes.unity_views import unity_bp
from api.routes.ml_views import ml_bp
from api.routes.health import health_bp


def register_blueprints(app: Flask):
    """Register all blueprints with the Flask app."""
    # Main dashboard
    app.register_blueprint(dashboard_bp)

    # Health monitoring (circuit breakers, dependencies)
    app.register_blueprint(health_bp)

    # SCADA / Level 2
    app.register_blueprint(scada_bp)

    # MES / Level 3
    app.register_blueprint(mes_bp)

    # LEGO Design
    app.register_blueprint(lego_bp)

    # ERP / Level 4
    app.register_blueprint(erp_bp)

    # QMS
    app.register_blueprint(qms_bp)

    # CMMS
    app.register_blueprint(cmms_bp)

    # Unity Digital Twin
    app.register_blueprint(unity_bp)

    # ML / Analytics
    app.register_blueprint(ml_bp)

    # Auth (stub)
    from api.routes.auth import auth_bp
    app.register_blueprint(auth_bp)


__all__ = [
    'register_blueprints',
    'dashboard_bp',
    'health_bp',
    'scada_bp',
    'mes_bp',
    'lego_bp',
    'erp_bp',
    'qms_bp',
    'cmms_bp',
    'unity_bp',
    'ml_bp',
]
