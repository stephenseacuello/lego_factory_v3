"""
Compliance Routes - Regulatory Compliance API

LegoMCP World-Class Manufacturing System v5.0
Phase 24: Regulatory Compliance

Provides:
- Audit trail management
- Electronic signatures (21 CFR Part 11)
- Access control
- Compliance reporting
"""

from flask import Blueprint

from .audit import audit_bp

compliance_bp = Blueprint('compliance', __name__, url_prefix='/api/compliance')

compliance_bp.register_blueprint(audit_bp)

__all__ = ['compliance_bp', 'audit_bp']
