"""
Edge Routes - IIoT Gateway API

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT

Provides:
- Device management
- Protocol adapters (OPC-UA, MQTT, Modbus)
- Edge analytics
- Data buffering
"""

from flask import Blueprint

from .iiot import iiot_bp

edge_bp = Blueprint('edge', __name__, url_prefix='/api/edge')

edge_bp.register_blueprint(iiot_bp)

__all__ = ['edge_bp', 'iiot_bp']
