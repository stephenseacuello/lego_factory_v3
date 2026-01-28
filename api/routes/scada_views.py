"""
LEGO Factory v3 - SCADA View Routes
====================================
SCADA dashboard views for machines, alarms, historian.
"""

from flask import Blueprint, render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

scada_bp = Blueprint('scada', __name__, url_prefix='/scada')


@scada_bp.route('/machines')
def machines():
    """Machine overview dashboard."""
    import json
    from pathlib import Path

    machines_list = []

    # Load machines from config
    try:
        config_path = Path(__file__).parent.parent.parent / 'config' / 'machines.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                for m in config.get('machines', []):
                    machines_list.append({
                        'id': m['machine_id'],
                        'name': m['name'],
                        'description': m.get('description', ''),
                        'machine_type': m.get('machine_type', 'unknown'),
                        'controller_type': m.get('controller_type', 'unknown'),
                        'status': 'disconnected',  # Will be updated when connected
                        'connected': False,
                        'area': m.get('area', ''),
                        'cell': m.get('cell', ''),
                        'port': m.get('connection_config', {}).get('port', ''),
                        'work_envelope': {
                            'x': m.get('work_envelope_x', 0),
                            'y': m.get('work_envelope_y', 0),
                            'z': m.get('work_envelope_z', 0),
                        },
                        'enabled': m.get('enabled', True),
                    })
    except Exception as e:
        logger.error(f"Error loading machines config: {e}")

    # Try to get live status from machine manager
    try:
        from services.scada.machine_control.machine_service import get_machine_manager
        manager = get_machine_manager()
        for machine in machines_list:
            controller = manager.get_machine(machine['id'])
            if controller:
                machine['status'] = controller.status.state.value
                machine['connected'] = controller.status.state.value != 'disconnected'
    except Exception as e:
        logger.warning(f'Exception in scada_views.py: {e}')
        pass  # Machine manager not available, use defaults

    return render_template('scada/machines.html', machines=machines_list)


@scada_bp.route('/alarms')
def alarms():
    """Alarm management dashboard."""
    try:
        from services.scada.alarm_management import get_alarm_processor
        processor = get_alarm_processor()
        alarms_list = processor.get_active_alarms()
        alarm_counts = {
            'critical': len([a for a in alarms_list if a.get('priority') == 'critical']),
            'high': len([a for a in alarms_list if a.get('priority') == 'high']),
            'medium': len([a for a in alarms_list if a.get('priority') == 'medium']),
            'low': len([a for a in alarms_list if a.get('priority') == 'low']),
        }
    except Exception as e:
        logger.warning(f'Exception in scada_views.py: {e}')
        alarms_list = []
        alarm_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}

    return render_template(
        'scada/alarms.html',
        alarms=alarms_list,
        alarm_counts=alarm_counts,
        total_active=len(alarms_list)
    )


@scada_bp.route('/historian')
def historian():
    """Historian data viewer."""
    return render_template('scada/historian.html')


@scada_bp.route('/recipes')
def recipes():
    """Recipe management dashboard."""
    return render_template('scada/recipes.html')


@scada_bp.route('/tags')
def tags():
    """Tag browser dashboard."""
    return render_template('scada/tags.html')
