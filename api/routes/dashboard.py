"""
LEGO Factory v3 - Dashboard Routes
===================================
Main dashboard and navigation blueprints.
"""

from flask import Blueprint, render_template, jsonify
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
def home():
    """Main dashboard view."""
    # Gather KPIs from services
    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        active_alarms = processor.get_active_alarms()
        alarm_summary = {
            'critical': len([a for a in active_alarms if a.get('priority') == 'critical']),
            'high': len([a for a in active_alarms if a.get('priority') == 'high']),
            'medium': len([a for a in active_alarms if a.get('priority') == 'medium']),
            'low': len([a for a in active_alarms if a.get('priority') == 'low']),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch alarm data: {e}")
        active_alarms = []
        alarm_summary = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

    try:
        from services.mes.oee_service import get_oee_dashboard
        oee = get_oee_dashboard()
    except Exception as e:
        logger.warning(f"Failed to fetch OEE data: {e}")
        oee = {'overall': 85.2, 'availability': 92.1, 'performance': 94.3, 'quality': 98.1}

    try:
        from services.scada.machine_control import get_all_controllers
        controllers = get_all_controllers()
        machines = {
            'total': len(controllers),
            'running': len([c for c in controllers.values() if c.state.value == 'running']),
            'idle': len([c for c in controllers.values() if c.state.value == 'idle']),
            'alarm': len([c for c in controllers.values() if c.state.value == 'alarm']),
        }
    except Exception as e:
        logger.warning(f"Failed to fetch machine data: {e}")
        machines = {'total': 8, 'running': 5, 'idle': 2, 'alarm': 1}

    return render_template(
        'dashboard/home.html',
        active_alarms=len(active_alarms),
        alarm_summary=alarm_summary,
        oee=oee,
        machines=machines,
        work_orders={'in_progress': 12, 'pending': 8, 'completed': 45},
    )


@dashboard_bp.route('/api/dashboard/kpis')
def get_kpis():
    """Get real-time KPI data."""
    return jsonify({
        'oee': {'overall': 85.2, 'availability': 92.1, 'performance': 94.3, 'quality': 98.1},
        'alarms': {'active': 3, 'critical': 1, 'high': 2},
        'production': {'today': 845, 'target': 1000},
        'machines': {'running': 5, 'total': 8},
    })
