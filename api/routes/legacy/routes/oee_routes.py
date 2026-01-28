"""
OEE (Overall Equipment Effectiveness) API Routes.

Provides REST API endpoints for real-time OEE calculations,
availability/performance/quality metrics, and analytics.
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

oee_bp = Blueprint('oee', __name__, url_prefix='/api/oee')

# Lazy service initialization
_oee_service = None


def get_oee_service():
    """Get or create the OEE service instance."""
    global _oee_service
    if _oee_service is None:
        from services.oee_service import OEEService
        _oee_service = OEEService()
    return _oee_service


# =============================================================================
# Real-Time OEE
# =============================================================================

@oee_bp.route('/machines/<machine_id>/current', methods=['GET'])
def get_current_oee(machine_id: str):
    """
    Get current (shift) OEE for a machine.

    Returns real-time OEE with availability, performance, and quality breakdown.
    """
    try:
        service = get_oee_service()

        oee = service.calculate_oee(machine_id)

        if oee:
            return jsonify({
                'success': True,
                'oee': oee
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No OEE data available for machine'
            }), 404

    except Exception as e:
        logger.error(f"Error getting current OEE: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@oee_bp.route('/machines/<machine_id>/historical', methods=['GET'])
def get_historical_oee(machine_id: str):
    """
    Get historical OEE for a machine.

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
        granularity: hour, shift, day, week (default day)
    """
    try:
        service = get_oee_service()

        from datetime import datetime, timedelta

        start_date = None
        end_date = None
        granularity = request.args.get('granularity', 'day')

        if request.args.get('start_date'):
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        # Default to last 30 days
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        historical = service.get_historical_oee(
            machine_id=machine_id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity
        )

        return jsonify({
            'success': True,
            'historical': historical,
            'machine_id': machine_id,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'granularity': granularity
            }
        })

    except Exception as e:
        logger.error(f"Error getting historical OEE: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Production Data Recording
# =============================================================================

@oee_bp.route('/machines/<machine_id>/production', methods=['POST'])
def record_production():
    """
    Record production data for OEE calculations.

    Request Body:
        part_number: Part being produced (required)
        quantity_good: Good parts produced (required)
        quantity_reject: Rejected parts (default 0)
        cycle_time_seconds: Actual cycle time (optional)
        ideal_cycle_time_seconds: Ideal/standard cycle time (optional)
        operator_id: Operator (optional)
        work_order_id: Associated work order (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('part_number') or 'quantity_good' not in data:
            return jsonify({
                'success': False,
                'error': 'part_number and quantity_good required'
            }), 400

        service = get_oee_service()

        record = service.record_production(
            machine_id=machine_id,
            part_number=data['part_number'],
            quantity_good=data['quantity_good'],
            quantity_reject=data.get('quantity_reject', 0),
            cycle_time_seconds=data.get('cycle_time_seconds'),
            ideal_cycle_time_seconds=data.get('ideal_cycle_time_seconds'),
            operator_id=data.get('operator_id'),
            work_order_id=data.get('work_order_id')
        )

        return jsonify({
            'success': True,
            'record': record
        }), 201

    except Exception as e:
        logger.error(f"Error recording production: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@oee_bp.route('/machines/<machine_id>/state', methods=['POST'])
def record_machine_state():
    """
    Record machine state change for availability tracking.

    Request Body:
        state: Machine state - running, idle, down, setup, changeover (required)
        reason: Reason for state change (optional)
        planned: Is this a planned state change (default false)
    """
    try:
        data = request.get_json()

        if not data or not data.get('state'):
            return jsonify({
                'success': False,
                'error': 'state required'
            }), 400

        service = get_oee_service()

        record = service.record_state_change(
            machine_id=machine_id,
            state=data['state'],
            reason=data.get('reason'),
            planned=data.get('planned', False)
        )

        return jsonify({
            'success': True,
            'state_record': record
        })

    except Exception as e:
        logger.error(f"Error recording state: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Ideal Cycle Times
# =============================================================================

@oee_bp.route('/cycle-times', methods=['GET'])
def list_cycle_times():
    """List all configured ideal cycle times."""
    try:
        service = get_oee_service()

        return jsonify({
            'success': True,
            'cycle_times': service.ideal_cycle_times
        })

    except Exception as e:
        logger.error(f"Error listing cycle times: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@oee_bp.route('/cycle-times', methods=['POST'])
def set_cycle_time():
    """
    Set ideal cycle time for a part/machine combination.

    Request Body:
        part_number: Part number (required)
        machine_id: Machine ID (required)
        cycle_time_seconds: Ideal cycle time in seconds (required)
    """
    try:
        data = request.get_json()

        if not data or not data.get('part_number') or not data.get('machine_id') or not data.get('cycle_time_seconds'):
            return jsonify({
                'success': False,
                'error': 'part_number, machine_id, and cycle_time_seconds required'
            }), 400

        service = get_oee_service()

        key = f"{data['part_number']}_{data['machine_id']}"
        service.ideal_cycle_times[key] = data['cycle_time_seconds']

        return jsonify({
            'success': True,
            'cycle_time': {
                'part_number': data['part_number'],
                'machine_id': data['machine_id'],
                'cycle_time_seconds': data['cycle_time_seconds']
            }
        })

    except Exception as e:
        logger.error(f"Error setting cycle time: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Dashboard Data
# =============================================================================

@oee_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    """
    Get dashboard data for all machines.

    Returns current OEE for all tracked machines.
    """
    try:
        service = get_oee_service()

        machines = list(service.machine_states.keys())

        dashboard = []
        for machine_id in machines:
            oee = service.calculate_oee(machine_id)
            if oee:
                dashboard.append({
                    'machine_id': machine_id,
                    'oee': oee
                })

        # Sort by OEE descending
        dashboard.sort(key=lambda x: x['oee'].get('oee', 0), reverse=True)

        return jsonify({
            'success': True,
            'dashboard': dashboard,
            'machine_count': len(dashboard)
        })

    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@oee_bp.route('/summary', methods=['GET'])
def get_oee_summary():
    """
    Get aggregate OEE summary.

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
    """
    try:
        service = get_oee_service()

        from datetime import datetime, timedelta

        start_date = None
        end_date = None

        if request.args.get('start_date'):
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        summary = service.get_oee_summary(
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({
            'success': True,
            'summary': summary
        })

    except Exception as e:
        logger.error(f"Error getting OEE summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Six Big Losses
# =============================================================================

@oee_bp.route('/machines/<machine_id>/losses', methods=['GET'])
def get_six_big_losses(machine_id: str):
    """
    Get Six Big Losses breakdown for a machine.

    The Six Big Losses are:
    1. Equipment Failure (Availability)
    2. Setup/Adjustments (Availability)
    3. Idling/Minor Stops (Performance)
    4. Reduced Speed (Performance)
    5. Process Defects (Quality)
    6. Reduced Yield (Quality)

    Query Parameters:
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
    """
    try:
        service = get_oee_service()

        from datetime import datetime, timedelta

        start_date = None
        end_date = None

        if request.args.get('start_date'):
            start_date = datetime.fromisoformat(
                request.args.get('start_date').replace('Z', '+00:00')
            )

        if request.args.get('end_date'):
            end_date = datetime.fromisoformat(
                request.args.get('end_date').replace('Z', '+00:00')
            )

        losses = service.get_six_big_losses(
            machine_id=machine_id,
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({
            'success': True,
            'losses': losses
        })

    except Exception as e:
        logger.error(f"Error getting six big losses: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Targets and Thresholds
# =============================================================================

@oee_bp.route('/targets', methods=['GET'])
def get_oee_targets():
    """Get OEE targets and thresholds."""
    try:
        service = get_oee_service()

        return jsonify({
            'success': True,
            'targets': service.targets
        })

    except Exception as e:
        logger.error(f"Error getting targets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@oee_bp.route('/targets', methods=['POST'])
def set_oee_targets():
    """
    Set OEE targets and thresholds.

    Request Body:
        oee_target: Target OEE percentage (default 85)
        availability_target: Target availability (default 90)
        performance_target: Target performance (default 95)
        quality_target: Target quality (default 99.9)
        warning_threshold: Warning threshold percentage (default 75)
        critical_threshold: Critical threshold percentage (default 60)
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body required'
            }), 400

        service = get_oee_service()

        if 'oee_target' in data:
            service.targets['oee_target'] = data['oee_target']
        if 'availability_target' in data:
            service.targets['availability_target'] = data['availability_target']
        if 'performance_target' in data:
            service.targets['performance_target'] = data['performance_target']
        if 'quality_target' in data:
            service.targets['quality_target'] = data['quality_target']
        if 'warning_threshold' in data:
            service.targets['warning_threshold'] = data['warning_threshold']
        if 'critical_threshold' in data:
            service.targets['critical_threshold'] = data['critical_threshold']

        return jsonify({
            'success': True,
            'targets': service.targets
        })

    except Exception as e:
        logger.error(f"Error setting targets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Benchmarking
# =============================================================================

@oee_bp.route('/benchmark', methods=['GET'])
def get_benchmark():
    """
    Get OEE benchmark comparison.

    Compares machines against each other and world-class standards.
    """
    try:
        service = get_oee_service()

        machines = list(service.machine_states.keys())

        # World-class OEE standards
        world_class = {
            'oee': 85.0,
            'availability': 90.0,
            'performance': 95.0,
            'quality': 99.9
        }

        benchmark = []
        for machine_id in machines:
            oee = service.calculate_oee(machine_id)
            if oee:
                benchmark.append({
                    'machine_id': machine_id,
                    'oee': oee.get('oee', 0),
                    'availability': oee.get('availability', 0),
                    'performance': oee.get('performance', 0),
                    'quality': oee.get('quality', 0),
                    'vs_world_class': {
                        'oee_gap': round(world_class['oee'] - oee.get('oee', 0), 2),
                        'availability_gap': round(world_class['availability'] - oee.get('availability', 0), 2),
                        'performance_gap': round(world_class['performance'] - oee.get('performance', 0), 2),
                        'quality_gap': round(world_class['quality'] - oee.get('quality', 0), 2)
                    }
                })

        # Sort by OEE descending
        benchmark.sort(key=lambda x: x['oee'], reverse=True)

        # Calculate averages
        if benchmark:
            avg_oee = sum(b['oee'] for b in benchmark) / len(benchmark)
            avg_availability = sum(b['availability'] for b in benchmark) / len(benchmark)
            avg_performance = sum(b['performance'] for b in benchmark) / len(benchmark)
            avg_quality = sum(b['quality'] for b in benchmark) / len(benchmark)
        else:
            avg_oee = avg_availability = avg_performance = avg_quality = 0

        return jsonify({
            'success': True,
            'benchmark': benchmark,
            'averages': {
                'oee': round(avg_oee, 2),
                'availability': round(avg_availability, 2),
                'performance': round(avg_performance, 2),
                'quality': round(avg_quality, 2)
            },
            'world_class': world_class
        })

    except Exception as e:
        logger.error(f"Error getting benchmark: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Reports
# =============================================================================

@oee_bp.route('/reports/shift', methods=['GET'])
def get_shift_report():
    """
    Get shift OEE report.

    Query Parameters:
        shift: Shift identifier (e.g., day, night, 1, 2, 3)
        date: Date for report (ISO format, default today)
    """
    try:
        service = get_oee_service()

        from datetime import datetime

        shift = request.args.get('shift', 'day')
        report_date = datetime.now().date()

        if request.args.get('date'):
            report_date = datetime.fromisoformat(
                request.args.get('date').replace('Z', '+00:00')
            ).date()

        report = service.get_shift_report(shift=shift, date=report_date)

        return jsonify({
            'success': True,
            'report': report
        })

    except Exception as e:
        logger.error(f"Error getting shift report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@oee_bp.route('/reports/daily', methods=['GET'])
def get_daily_report():
    """
    Get daily OEE report.

    Query Parameters:
        date: Date for report (ISO format, default today)
    """
    try:
        service = get_oee_service()

        from datetime import datetime

        report_date = datetime.now().date()

        if request.args.get('date'):
            report_date = datetime.fromisoformat(
                request.args.get('date').replace('Z', '+00:00')
            ).date()

        report = service.get_daily_report(date=report_date)

        return jsonify({
            'success': True,
            'report': report
        })

    except Exception as e:
        logger.error(f"Error getting daily report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
