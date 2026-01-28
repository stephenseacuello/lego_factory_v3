"""
Dashboard Routes - Unified Operator Dashboard.

Provides REST endpoints and templates for the operator dashboard.
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
def index():
    """Main operator dashboard page."""
    return render_template('dashboard/index.html')


@dashboard_bp.route('/sensors')
def sensors():
    """Sensor monitoring dashboard page."""
    return render_template('sensors.html')


@dashboard_bp.route('/api/overview')
def get_overview():
    """
    Get dashboard overview data.

    Returns summary of:
    - Fleet status
    - Active jobs
    - OEE metrics
    - Recent alarms
    """
    try:
        # Import services
        from core.controllers.tinyg_controller import TinyGController
        from services.mes_service import MESService

        # Get machine data
        machines = []
        try:
            # Mock machine data for demo
            machines = [
                {
                    'machine_id': 'tinyg_001',
                    'name': 'TinyG Mill #1',
                    'type': 'cnc_mill',
                    'state': 'idle',
                    'state_text': 'Ready',
                    'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                    'feed_rate': 0.0,
                    'spindle_speed': 0.0,
                    'connected': True,
                },
                {
                    'machine_id': 'grbl_001',
                    'name': 'GRBL Router #1',
                    'type': 'cnc_router',
                    'state': 'idle',
                    'state_text': 'Ready',
                    'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                    'feed_rate': 0.0,
                    'spindle_speed': 0.0,
                    'connected': True,
                },
            ]
        except Exception as e:
            logger.warning(f"Error getting machine data: {e}")

        # Get OEE data
        oee_data = {
            'fleet_oee': 0.85,
            'availability': 0.92,
            'performance': 0.95,
            'quality': 0.97,
            'machines': {
                'tinyg_001': {'oee': 0.87, 'availability': 0.94, 'performance': 0.95, 'quality': 0.98},
                'grbl_001': {'oee': 0.83, 'availability': 0.90, 'performance': 0.95, 'quality': 0.97},
            }
        }

        # Get active jobs
        active_jobs = [
            {
                'job_id': 'JOB-001',
                'work_order_id': 'WO-2024-0001',
                'part_number': 'PART-001',
                'machine_id': 'tinyg_001',
                'status': 'running',
                'progress': 45.0,
                'started_at': (datetime.now() - timedelta(minutes=30)).isoformat(),
            }
        ]

        # Get recent alarms
        recent_alarms = [
            {
                'alarm_id': 'ALM-001',
                'machine_id': 'grbl_001',
                'severity': 'warning',
                'message': 'Feed rate override below 50%',
                'timestamp': (datetime.now() - timedelta(minutes=15)).isoformat(),
                'acknowledged': False,
            }
        ]

        # Summary stats
        summary = {
            'total_machines': len(machines),
            'machines_running': sum(1 for m in machines if m['state'] == 'running'),
            'machines_idle': sum(1 for m in machines if m['state'] == 'idle'),
            'machines_alarm': sum(1 for m in machines if m['state'] == 'alarm'),
            'machines_offline': sum(1 for m in machines if not m['connected']),
            'active_jobs': len(active_jobs),
            'pending_alarms': len([a for a in recent_alarms if not a['acknowledged']]),
        }

        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'machines': machines,
            'oee': oee_data,
            'active_jobs': active_jobs,
            'recent_alarms': recent_alarms,
        })

    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/machine/<machine_id>')
def get_machine_details(machine_id: str):
    """Get detailed status for a specific machine."""
    try:
        # Mock detailed machine data
        machine = {
            'machine_id': machine_id,
            'name': f'{machine_id.upper()} Mill',
            'type': 'cnc_mill',
            'firmware': '0.97',
            'state': 'idle',
            'state_text': 'Ready',
            'position': {
                'machine': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0},
                'work': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0},
            },
            'feed_rate': 0.0,
            'spindle_speed': 0.0,
            'overrides': {
                'feed': 100.0,
                'rapid': 100.0,
                'spindle': 100.0,
            },
            'buffers': {
                'planner': 28,
                'rx': 0,
            },
            'oee': {
                'oee': 0.87,
                'availability': 0.94,
                'performance': 0.95,
                'quality': 0.98,
            },
            'job_queue': [],
            'current_program': None,
            'uptime_hours': 124.5,
            'parts_today': 42,
        }

        return jsonify({'success': True, 'machine': machine})

    except Exception as e:
        logger.error(f"Error getting machine details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/machine/<machine_id>/jog', methods=['POST'])
def jog_machine(machine_id: str):
    """Send jog command to machine."""
    try:
        data = request.json
        axis = data.get('axis', 'X')
        distance = data.get('distance', 1.0)
        feed_rate = data.get('feed_rate', 1000.0)

        # In production, this would call the actual controller
        logger.info(f"Jog command: {machine_id} {axis} {distance}mm at F{feed_rate}")

        return jsonify({
            'success': True,
            'message': f'Jogged {axis} by {distance}mm',
        })

    except Exception as e:
        logger.error(f"Error jogging machine: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/machine/<machine_id>/home', methods=['POST'])
def home_machine(machine_id: str):
    """Home machine axes."""
    try:
        data = request.json
        axes = data.get('axes', 'XYZ')

        logger.info(f"Home command: {machine_id} axes={axes}")

        return jsonify({
            'success': True,
            'message': f'Homing {axes}',
        })

    except Exception as e:
        logger.error(f"Error homing machine: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/machine/<machine_id>/feedhold', methods=['POST'])
def feed_hold(machine_id: str):
    """Pause machine operation."""
    try:
        logger.info(f"Feed hold: {machine_id}")
        return jsonify({'success': True, 'message': 'Feed hold activated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/machine/<machine_id>/resume', methods=['POST'])
def resume_machine(machine_id: str):
    """Resume machine operation."""
    try:
        logger.info(f"Resume: {machine_id}")
        return jsonify({'success': True, 'message': 'Resumed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/alarms')
def get_alarms():
    """Get alarm history."""
    try:
        limit = request.args.get('limit', 50, type=int)
        severity = request.args.get('severity')
        machine_id = request.args.get('machine_id')

        # Mock alarm data
        alarms = [
            {
                'alarm_id': f'ALM-{i:03d}',
                'machine_id': 'tinyg_001' if i % 2 == 0 else 'grbl_001',
                'severity': 'warning' if i % 3 == 0 else 'info',
                'code': f'E{100 + i}',
                'message': f'Sample alarm message {i}',
                'timestamp': (datetime.now() - timedelta(minutes=i * 5)).isoformat(),
                'acknowledged': i > 3,
                'acknowledged_by': 'operator1' if i > 3 else None,
            }
            for i in range(1, min(limit + 1, 20))
        ]

        # Filter
        if severity:
            alarms = [a for a in alarms if a['severity'] == severity]
        if machine_id:
            alarms = [a for a in alarms if a['machine_id'] == machine_id]

        return jsonify({'success': True, 'alarms': alarms})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/alarms/<alarm_id>/acknowledge', methods=['POST'])
def acknowledge_alarm(alarm_id: str):
    """Acknowledge an alarm."""
    try:
        data = request.json
        operator_id = data.get('operator_id', 'unknown')

        logger.info(f"Alarm {alarm_id} acknowledged by {operator_id}")

        return jsonify({
            'success': True,
            'message': f'Alarm {alarm_id} acknowledged',
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/work-orders')
def get_work_orders():
    """Get work orders from MES."""
    try:
        from services.mes_adapter_service import mes_adapter_service

        work_orders = mes_adapter_service.get_pending_work_orders(limit=50)

        return jsonify({
            'success': True,
            'work_orders': [mes_adapter_service.to_dict(wo) for wo in work_orders],
        })

    except Exception as e:
        logger.error(f"Error getting work orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/work-orders/<wo_id>/dispatch', methods=['POST'])
def dispatch_work_order(wo_id: str):
    """Dispatch work order to machine."""
    try:
        data = request.json
        machine_id = data.get('machine_id')
        operation_id = data.get('operation_id')

        logger.info(f"Dispatching WO {wo_id} operation {operation_id} to {machine_id}")

        return jsonify({
            'success': True,
            'message': f'Work order {wo_id} dispatched to {machine_id}',
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/oee')
def get_oee_metrics():
    """Get OEE metrics."""
    try:
        machine_id = request.args.get('machine_id')
        period = request.args.get('period', 'shift')  # shift, day, week

        # Mock OEE data
        if machine_id:
            oee_data = {
                'machine_id': machine_id,
                'period': period,
                'oee': 0.87,
                'availability': 0.94,
                'performance': 0.95,
                'quality': 0.98,
                'planned_time': 480.0,  # minutes
                'run_time': 451.2,
                'ideal_cycle_time': 60.0,
                'actual_cycle_time': 63.2,
                'total_count': 42,
                'good_count': 41,
                'reject_count': 1,
            }
        else:
            oee_data = {
                'fleet_oee': 0.85,
                'period': period,
                'machines': {
                    'tinyg_001': {'oee': 0.87, 'availability': 0.94, 'performance': 0.95, 'quality': 0.98},
                    'grbl_001': {'oee': 0.83, 'availability': 0.90, 'performance': 0.95, 'quality': 0.97},
                }
            }

        return jsonify({'success': True, 'oee': oee_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/traceability/<part_serial>')
def get_part_traceability(part_serial: str):
    """Get part traceability/genealogy."""
    try:
        from services.traceability_service import get_traceability_service

        service = get_traceability_service()
        record = service.get_as_built_record(part_serial)

        if record:
            return jsonify({'success': True, 'traceability': record})
        else:
            return jsonify({'success': False, 'error': 'Part not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Factory Cell Dashboard Routes
# =============================================================================

@dashboard_bp.route('/factory')
def factory_cell():
    """Factory cell digital twin dashboard page."""
    return render_template('factory_cell.html')


@dashboard_bp.route('/api/factory/overview')
def get_factory_overview():
    """
    Get factory cell overview data.

    Returns summary of:
    - Cell status
    - Robot states (Ned2, xArm)
    - Bantam CNC status
    - Inspection station status
    - Production metrics
    """
    try:
        from config import get_config
        config = get_config()

        # Get factory cell services if available
        orchestrator = None
        ned2_state = None
        xarm_state = None
        bantam_state = None
        inspection_state = None

        try:
            from services.factory_cell_orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            cell_state = orchestrator.get_cell_state() if orchestrator else None
        except ImportError:
            cell_state = None

        try:
            from services.robots.ned2_controller import get_ned2_controller
            ned2 = get_ned2_controller()
            ned2_state = ned2.get_state() if ned2 else None
        except ImportError:
            ned2_state = None

        try:
            from services.robots.xarm_controller import get_xarm_controller
            xarm = get_xarm_controller()
            xarm_state = xarm.get_state() if xarm else None
        except ImportError:
            xarm_state = None

        try:
            from services.bantam_sensor_service import get_sensor_service
            bantam = get_sensor_service()
            bantam_state = bantam.get_statistics() if bantam else None
        except ImportError:
            bantam_state = None

        try:
            from services.inspection_service import get_inspection_service
            inspection = get_inspection_service()
            inspection_state = inspection.get_statistics() if inspection else None
        except ImportError:
            inspection_state = None

        # Build response with available data or defaults
        overview = {
            'cell_id': config.FACTORY_CELL_ID if hasattr(config, 'FACTORY_CELL_ID') else 'factory-cell-001',
            'cell_name': config.FACTORY_CELL_NAME if hasattr(config, 'FACTORY_CELL_NAME') else 'Default Factory Cell',
            'timestamp': datetime.now().isoformat(),
            'cell_state': cell_state or {
                'workflow_stage': 'IDLE',
                'is_running': False,
                'current_job': None,
                'parts_completed': 0,
                'parts_passed': 0,
                'parts_failed': 0,
            },
            'robots': {
                'ned2': ned2_state or {
                    'robot_id': config.NED2_ID if hasattr(config, 'NED2_ID') else 'ned2-001',
                    'is_connected': False,
                    'mode': 'simulation',
                    'joint_angles': [0, 0, 0, 0, 0, 0],
                },
                'xarm': xarm_state or {
                    'robot_id': config.XARM_ID if hasattr(config, 'XARM_ID') else 'xarm-001',
                    'is_connected': False,
                    'mode': 'simulation',
                    'joint_angles': [0, 0, 0, 0, 0, 0],
                },
            },
            'bantam': bantam_state or {
                'machine_id': config.BANTAM_ID if hasattr(config, 'BANTAM_ID') else 'bantam-001',
                'is_running': False,
                'sample_count': 0,
                'alerts_generated': 0,
            },
            'inspection': inspection_state or {
                'station_id': 'inspection-001',
                'is_ready': True,
                'total_inspected': 0,
                'total_passed': 0,
                'total_failed': 0,
                'pass_rate': 0.0,
            },
        }

        return jsonify({'success': True, 'overview': overview})

    except Exception as e:
        logger.error(f"Error getting factory overview: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/factory/workflow')
def get_factory_workflow():
    """Get current workflow state and stage details."""
    try:
        from services.factory_cell_orchestrator import WorkflowStage

        stages = [
            {'id': 'IDLE', 'name': 'Idle', 'description': 'Waiting for job'},
            {'id': 'LOAD_RAW_STOCK', 'name': 'Load Stock', 'description': 'Ned2 picking raw stock'},
            {'id': 'FIXTURE_PART', 'name': 'Fixture', 'description': 'Ned2 loading into CNC'},
            {'id': 'MACHINE_PART', 'name': 'Machine', 'description': 'Bantam CNC machining'},
            {'id': 'UNLOAD_PART', 'name': 'Unload', 'description': 'xArm removing part'},
            {'id': 'INSPECT_PART', 'name': 'Inspect', 'description': 'Quality inspection'},
            {'id': 'STORE_FINISHED', 'name': 'Store', 'description': 'xArm storing part'},
            {'id': 'COMPLETE', 'name': 'Complete', 'description': 'Cycle complete'},
        ]

        try:
            from services.factory_cell_orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            current_stage = orchestrator.workflow_stage.value if orchestrator else 'IDLE'
        except ImportError:
            current_stage = 'IDLE'

        return jsonify({
            'success': True,
            'stages': stages,
            'current_stage': current_stage,
        })

    except Exception as e:
        logger.error(f"Error getting workflow: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/factory/jobs')
def get_factory_jobs():
    """Get factory cell job queue and history."""
    try:
        try:
            from services.factory_cell_orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if orchestrator:
                queue = [job.to_dict() for job in orchestrator.job_queue]
                history = [job.to_dict() for job in orchestrator.completed_jobs[-20:]]
            else:
                queue = []
                history = []
        except ImportError:
            queue = []
            history = []

        return jsonify({
            'success': True,
            'job_queue': queue,
            'completed_jobs': history,
        })

    except Exception as e:
        logger.error(f"Error getting factory jobs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/factory/jobs', methods=['POST'])
def add_factory_job():
    """Add a new job to the factory cell queue."""
    try:
        data = request.json
        job_id = data.get('job_id')
        part_count = data.get('part_count', 1)
        gcode_file = data.get('gcode_file')
        priority = data.get('priority', 1)

        if not job_id:
            return jsonify({'success': False, 'error': 'job_id required'}), 400

        try:
            from services.factory_cell_orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if orchestrator:
                result = orchestrator.add_job(
                    job_id=job_id,
                    part_count=part_count,
                    gcode_file=gcode_file,
                    priority=priority
                )
                return jsonify({'success': True, 'job_id': result})
            else:
                return jsonify({'success': False, 'error': 'Orchestrator not available'}), 503
        except ImportError:
            return jsonify({'success': False, 'error': 'Factory cell service not available'}), 503

    except Exception as e:
        logger.error(f"Error adding factory job: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/api/factory/production-stats')
def get_production_stats():
    """Get factory cell production statistics."""
    try:
        try:
            from services.factory_cell_orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if orchestrator:
                stats = orchestrator.get_production_stats()
            else:
                stats = None
        except ImportError:
            stats = None

        if not stats:
            stats = {
                'total_parts': 0,
                'passed_parts': 0,
                'failed_parts': 0,
                'pass_rate': 0.0,
                'average_cycle_time': 0.0,
                'uptime_hours': 0.0,
                'oee': 0.0,
            }

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        logger.error(f"Error getting production stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
