"""
LEGO Factory v3 - CRM View Routes
==================================
CRM dashboard views for customer relationship management.
"""

from flask import Blueprint, render_template
import logging

logger = logging.getLogger(__name__)

crm_bp = Blueprint('crm_web', __name__, url_prefix='/crm')


@crm_bp.route('/dashboard')
def dashboard():
    """CRM overview dashboard."""
    return render_template('crm/dashboard.html')


@crm_bp.route('/customers')
def customers():
    """Customer management."""
    return render_template('crm/customers.html')


@crm_bp.route('/contacts')
def contacts():
    """Contact management."""
    return render_template('crm/contacts.html')


@crm_bp.route('/activities')
def activities():
    """Activity log."""
    return render_template('crm/activities.html')
