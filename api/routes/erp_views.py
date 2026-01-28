"""
LEGO Factory v3 - ERP View Routes
==================================
ERP dashboard views for sales, inventory, MRP.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

erp_bp = Blueprint('erp', __name__, url_prefix='/erp')


@erp_bp.route('/sales-orders')
def sales_orders():
    """Sales orders dashboard."""
    return render_template('erp/sales_orders.html')


@erp_bp.route('/purchase-orders')
def purchase_orders():
    """Purchase orders dashboard."""
    return render_template('erp/purchase_orders.html')


@erp_bp.route('/inventory')
def inventory():
    """Inventory dashboard."""
    return render_template('erp/inventory.html')


@erp_bp.route('/items')
def items():
    """Item master dashboard."""
    return render_template('erp/items.html')


@erp_bp.route('/mrp')
def mrp():
    """MRP planning dashboard."""
    return render_template('erp/mrp.html')


@erp_bp.route('/customers')
def customers():
    """Customer management."""
    return render_template('erp/customers.html')


@erp_bp.route('/vendors')
def vendors():
    """Vendor management."""
    return render_template('erp/vendors.html')


@erp_bp.route('/costing')
def costing():
    """Product costing dashboard."""
    return render_template('erp/costing.html')
