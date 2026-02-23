"""
Digital Twin Simulation API - Production simulation and what-if analysis.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime

from models import get_db_session
from services.digital_twin import DigitalTwinManager

simulation_bp = Blueprint('simulation', __name__, url_prefix='/simulation')


@simulation_bp.route('/<work_center_id>/production', methods=['POST'])
def simulate_production(work_center_id: str):
    """
    Simulate production run.

    Body:
    {
        "part_id": "uuid",
        "quantity": 100,
        "parameters": {
            "speed_percent": 100,
            "quality_target": 0.98
        }
    }

    Returns predicted completion time, quality, and resource usage.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    part_id = data.get('part_id')
    quantity = data.get('quantity')

    if not part_id or not quantity:
        return jsonify({'error': 'part_id and quantity required'}), 400

    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        try:
            simulation = manager.simulate_production(
                work_center_id=work_center_id,
                part_id=part_id,
                quantity=quantity,
                parameters=data.get('parameters', {})
            )

            return jsonify({
                'work_center_id': work_center_id,
                'part_id': part_id,
                'quantity': quantity,
                'simulation': simulation,
                'simulated_at': datetime.utcnow().isoformat()
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@simulation_bp.route('/what-if', methods=['POST'])
def what_if_analysis():
    """
    Run what-if analysis across multiple work centers.

    Body:
    {
        "scenario": "speed_increase|quality_focus|maintenance_delay",
        "work_center_ids": ["uuid1", "uuid2"],
        "parameters": {
            "speed_change_percent": 10,
            "maintenance_delay_hours": 24
        }
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    scenario = data.get('scenario', 'baseline')
    work_center_ids = data.get('work_center_ids', [])
    parameters = data.get('parameters', {})

    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        results = []
        for wc_id in work_center_ids:
            try:
                # Get current state
                current = manager.get_current_state(wc_id)

                # Apply scenario modifications
                if scenario == 'speed_increase':
                    change = parameters.get('speed_change_percent', 10)
                    new_speed = (current.speed or 100) * (1 + change / 100)
                    predicted_oee_change = change * 0.8  # Performance increase
                    quality_impact = -change * 0.1  # Slight quality decrease

                    results.append({
                        'work_center_id': wc_id,
                        'scenario': scenario,
                        'current_speed': current.speed,
                        'new_speed': new_speed,
                        'predicted_oee_change': f"+{predicted_oee_change:.1f}%",
                        'quality_impact': f"{quality_impact:.1f}%",
                        'recommendation': 'Proceed with monitoring' if quality_impact > -5 else 'Quality risk - not recommended'
                    })

                elif scenario == 'quality_focus':
                    target = parameters.get('quality_target', 0.99)
                    speed_reduction = (target - 0.95) * 100  # Slower for higher quality

                    results.append({
                        'work_center_id': wc_id,
                        'scenario': scenario,
                        'quality_target': f"{target * 100:.1f}%",
                        'speed_reduction': f"-{speed_reduction:.1f}%",
                        'throughput_impact': f"-{speed_reduction * 0.8:.1f}%",
                        'recommendation': 'Suitable for high-value parts'
                    })

                elif scenario == 'maintenance_delay':
                    delay_hours = parameters.get('maintenance_delay_hours', 24)
                    failure_risk_increase = delay_hours * 0.5  # Risk per hour delayed

                    results.append({
                        'work_center_id': wc_id,
                        'scenario': scenario,
                        'delay_hours': delay_hours,
                        'failure_risk_increase': f"+{failure_risk_increase:.1f}%",
                        'potential_downtime_cost': delay_hours * 50,  # $50/hour estimate
                        'recommendation': 'Not recommended' if failure_risk_increase > 20 else 'Acceptable short-term'
                    })

                else:
                    # Baseline - just report current state
                    results.append({
                        'work_center_id': wc_id,
                        'scenario': 'baseline',
                        'current_status': current.status.value if hasattr(current.status, 'value') else str(current.status),
                        'current_speed': current.speed,
                        'current_job_progress': current.job_progress
                    })

            except ValueError as e:
                results.append({
                    'work_center_id': wc_id,
                    'error': str(e)
                })

        return jsonify({
            'scenario': scenario,
            'parameters': parameters,
            'results': results,
            'analyzed_at': datetime.utcnow().isoformat()
        })


@simulation_bp.route('/capacity-impact', methods=['POST'])
def simulate_capacity_impact():
    """
    Simulate impact of adding/removing capacity.

    Body:
    {
        "action": "add|remove|upgrade",
        "work_center_type": "3d_printer|cnc_mill|laser",
        "quantity": 1,
        "capacity_per_hour": 10
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    action = data.get('action', 'add')
    wc_type = data.get('work_center_type', '3d_printer')
    quantity = data.get('quantity', 1)
    capacity_per_hour = data.get('capacity_per_hour', 10)

    # Simple capacity impact calculation
    if action == 'add':
        capacity_change = quantity * capacity_per_hour
        throughput_impact = capacity_change * 8  # 8-hour shift
        investment = quantity * 50000  # Estimated cost per machine
        roi_months = investment / (throughput_impact * 22 * 5)  # Assuming $5/part margin

        result = {
            'action': action,
            'work_center_type': wc_type,
            'quantity_added': quantity,
            'capacity_increase_per_hour': capacity_change,
            'daily_throughput_increase': throughput_impact,
            'estimated_investment': investment,
            'estimated_roi_months': round(roi_months, 1),
            'recommendation': 'Proceed' if roi_months < 24 else 'Review investment case'
        }

    elif action == 'remove':
        capacity_change = -quantity * capacity_per_hour

        result = {
            'action': action,
            'work_center_type': wc_type,
            'quantity_removed': quantity,
            'capacity_decrease_per_hour': abs(capacity_change),
            'bottleneck_risk': 'HIGH' if quantity > 1 else 'MEDIUM',
            'recommendation': 'Ensure sufficient backup capacity'
        }

    elif action == 'upgrade':
        old_capacity = capacity_per_hour
        new_capacity = capacity_per_hour * 1.5  # 50% upgrade
        upgrade_cost = quantity * 10000

        result = {
            'action': action,
            'work_center_type': wc_type,
            'quantity_upgraded': quantity,
            'old_capacity_per_hour': old_capacity,
            'new_capacity_per_hour': new_capacity,
            'capacity_increase_percent': 50,
            'estimated_cost': upgrade_cost,
            'recommendation': 'Cost-effective alternative to new equipment'
        }

    else:
        return jsonify({'error': f'Unknown action: {action}'}), 400

    result['simulated_at'] = datetime.utcnow().isoformat()
    return jsonify(result)


@simulation_bp.route('/failure-prediction/<work_center_id>', methods=['GET'])
def predict_failure(work_center_id: str):
    """
    Predict potential failure based on current state trends.

    Returns failure probability and recommended actions.
    """
    with get_db_session() as session:
        manager = DigitalTwinManager(session)

        try:
            # Get recent state history
            history = manager.get_state_history(
                work_center_id=work_center_id,
                state_type='temperature',
                hours=48
            )

            # Simple trend analysis
            if not history:
                return jsonify({
                    'work_center_id': work_center_id,
                    'failure_probability': 'UNKNOWN',
                    'data_available': False,
                    'recommendation': 'Insufficient data for prediction'
                })

            # Analyze temperature trends (simplified)
            temps = []
            for record in history:
                if isinstance(record.get('state_data'), dict):
                    temps.extend([v for v in record['state_data'].values()
                                  if isinstance(v, (int, float))])

            if temps:
                avg_temp = sum(temps) / len(temps)
                max_temp = max(temps)
                trend = (temps[-1] - temps[0]) / len(temps) if len(temps) > 1 else 0

                # Failure probability based on temperature
                if max_temp > 250:
                    failure_prob = 'HIGH'
                    days_to_failure = 1
                elif max_temp > 220 or trend > 0.5:
                    failure_prob = 'MEDIUM'
                    days_to_failure = 7
                else:
                    failure_prob = 'LOW'
                    days_to_failure = 30

                return jsonify({
                    'work_center_id': work_center_id,
                    'failure_probability': failure_prob,
                    'estimated_days_to_failure': days_to_failure,
                    'metrics': {
                        'average_temperature': round(avg_temp, 1),
                        'max_temperature': round(max_temp, 1),
                        'temperature_trend': round(trend, 3)
                    },
                    'recommendation': 'Schedule immediate maintenance' if failure_prob == 'HIGH'
                                     else 'Monitor closely' if failure_prob == 'MEDIUM'
                                     else 'Normal operation',
                    'predicted_at': datetime.utcnow().isoformat()
                })

            return jsonify({
                'work_center_id': work_center_id,
                'failure_probability': 'UNKNOWN',
                'data_available': True,
                'data_quality': 'No temperature data in records',
                'recommendation': 'Check sensor connectivity'
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 404
