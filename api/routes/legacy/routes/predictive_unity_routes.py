"""
Predictive Maintenance Unity API Routes
========================================
REST API endpoints for Unity Digital Twin predictive maintenance visualization.

Endpoints:
- GET /api/predictive/unity/<machine_id>/state - Get full predictive state
- GET /api/predictive/unity/<machine_id>/health - Get health scores
- GET /api/predictive/unity/<machine_id>/tools - Get tool wear predictions
- GET /api/predictive/unity/<machine_id>/maintenance - Get maintenance schedule
- GET /api/predictive/unity/<machine_id>/anomalies - Get active anomalies
- POST /api/predictive/unity/<machine_id>/anomaly - Add anomaly marker
- DELETE /api/predictive/unity/<machine_id>/anomaly/<anomaly_id> - Clear anomaly
- GET /api/predictive/unity/<machine_id>/trends/<metric> - Get trend data

Author: Flask CNC SCADA System
"""

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Blueprint
predictive_unity_bp = Blueprint(
    'predictive_unity',
    __name__,
    url_prefix='/api/predictive/unity'
)


# =============================================================================
# Service Import (lazy to avoid circular imports)
# =============================================================================

def get_predictive_service():
    """Get the Unity predictive integration service."""
    try:
        from services.predictive.unity_integration import get_unity_predictive
        return get_unity_predictive()
    except ImportError:
        logger.warning("Unity predictive integration not available")
        return None


# =============================================================================
# State Endpoints
# =============================================================================

@predictive_unity_bp.route('/<machine_id>/state', methods=['GET'])
def get_predictive_state(machine_id: str):
    """
    Get complete predictive state for Unity Digital Twin.

    Returns all health scores, tool predictions, maintenance events,
    anomalies, and trends formatted for Unity visualization.
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_unity_state_dict(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    return jsonify({
        'success': True,
        'data': state
    })


@predictive_unity_bp.route('/<machine_id>/health', methods=['GET'])
def get_health_scores(machine_id: str):
    """
    Get health scores for Unity gauge display.

    Returns overall health and per-component scores with
    status, trend, and confidence values.
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_predictive_state(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    # Format health scores for Unity
    health_data = {
        'overall': {
            'score': state.overall_health_score,
            'status': service._score_to_status(state.overall_health_score).value,
            'color': service._score_to_color(state.overall_health_score)
        },
        'components': {}
    }

    for name, hs in state.health_scores.items():
        health_data['components'][name] = {
            'score': hs.score,
            'status': hs.status.value,
            'trend': hs.trend,
            'confidence': hs.confidence
        }

    return jsonify({
        'success': True,
        'machine_id': machine_id,
        'timestamp': state.timestamp,
        'data': health_data
    })


# =============================================================================
# Tool Predictions
# =============================================================================

@predictive_unity_bp.route('/<machine_id>/tools', methods=['GET'])
def get_tool_predictions(machine_id: str):
    """
    Get tool wear predictions for Unity overlay.

    Returns tool wear status, remaining life, recommendations,
    and 3D overlay positioning data.
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_predictive_state(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    from dataclasses import asdict

    tools = []
    for tp in state.tool_predictions:
        tools.append({
            'tool_number': tp.tool_number,
            'tool_name': tp.tool_name,
            'wear_percent': tp.current_wear_percent,
            'life_remaining_hours': tp.predicted_life_remaining_hours,
            'failure_time': tp.predicted_failure_time.isoformat() if tp.predicted_failure_time else None,
            'confidence': tp.confidence,
            'recommendation': tp.recommendation,
            'severity': tp.severity.value,
            'overlay': {
                'position': asdict(tp.overlay_position),
                'color': list(tp.color_rgb),
                'pulse': tp.pulse_animation,
                'show_trend': tp.show_trend_arrow
            }
        })

    return jsonify({
        'success': True,
        'machine_id': machine_id,
        'timestamp': state.timestamp,
        'tools': tools
    })


@predictive_unity_bp.route('/<machine_id>/tools', methods=['POST'])
def update_tool_predictions(machine_id: str):
    """
    Update tool wear predictions from ML service.

    Request body:
    {
        "predictions": [
            {
                "tool_number": 1,
                "tool_name": "Endmill 10mm",
                "wear_percent": 45.5,
                "life_remaining_hours": 12.5,
                "confidence": 0.85
            }
        ]
    }
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    data = request.get_json() or {}
    predictions = data.get('predictions', [])

    if not predictions:
        return jsonify({
            'success': False,
            'error': 'No predictions provided'
        }), 400

    service.update_tool_predictions(machine_id, predictions)

    return jsonify({
        'success': True,
        'message': f'Updated {len(predictions)} tool predictions',
        'machine_id': machine_id
    })


# =============================================================================
# Maintenance Schedule
# =============================================================================

@predictive_unity_bp.route('/<machine_id>/maintenance', methods=['GET'])
def get_maintenance_schedule(machine_id: str):
    """
    Get maintenance schedule for Unity calendar AR overlay.

    Returns upcoming maintenance events with AR display properties.
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_predictive_state(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    events = []
    for me in state.upcoming_maintenance[:10]:
        events.append({
            'event_id': me.event_id,
            'component': me.component.value,
            'type': me.maintenance_type.value,
            'scheduled_start': me.scheduled_start.isoformat(),
            'duration_hours': me.scheduled_duration_hours,
            'description': me.description,
            'priority': me.priority,
            'requires_shutdown': me.requires_shutdown,
            'parts_needed': me.parts_needed,
            'ar': {
                'show': me.show_in_ar,
                'icon': me.ar_icon,
                'color': list(me.ar_color_rgb)
            }
        })

    return jsonify({
        'success': True,
        'machine_id': machine_id,
        'timestamp': state.timestamp,
        'events': events
    })


@predictive_unity_bp.route('/<machine_id>/maintenance', methods=['POST'])
def update_maintenance_schedule(machine_id: str):
    """
    Update maintenance schedule from scheduler service.

    Request body:
    {
        "events": [
            {
                "event_id": "maint-001",
                "component": "spindle",
                "maintenance_type": "preventive",
                "scheduled_start": "2024-01-15T08:00:00",
                "duration_hours": 4.0,
                "description": "Spindle bearing replacement",
                "priority": 2,
                "requires_shutdown": true
            }
        ]
    }
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    data = request.get_json() or {}
    events = data.get('events', [])

    service.update_maintenance_schedule(machine_id, events)

    return jsonify({
        'success': True,
        'message': f'Updated maintenance schedule with {len(events)} events',
        'machine_id': machine_id
    })


# =============================================================================
# Anomaly Markers
# =============================================================================

@predictive_unity_bp.route('/<machine_id>/anomalies', methods=['GET'])
def get_anomalies(machine_id: str):
    """
    Get active anomaly markers for 3D visualization.

    Returns anomalies with 3D position, severity, and visual properties.
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_predictive_state(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    from dataclasses import asdict

    anomalies = []
    for am in state.active_anomalies:
        anomalies.append({
            'anomaly_id': am.anomaly_id,
            'component': am.component.value,
            'type': am.anomaly_type,
            'severity': am.severity.value,
            'detected_at': am.detected_at.isoformat(),
            'description': am.description,
            'marker': {
                'position': asdict(am.position),
                'type': am.marker_type,
                'color': list(am.color_rgb),
                'size': am.size,
                'pulse': am.pulse,
                'show_label': am.show_label
            }
        })

    return jsonify({
        'success': True,
        'machine_id': machine_id,
        'timestamp': state.timestamp,
        'anomalies': anomalies
    })


@predictive_unity_bp.route('/<machine_id>/anomaly', methods=['POST'])
def add_anomaly(machine_id: str):
    """
    Add anomaly marker for 3D visualization.

    Request body:
    {
        "component": "spindle",
        "anomaly_type": "vibration",
        "severity": "warning",
        "description": "Unusual vibration pattern detected",
        "position": {"x": 0, "y": 0, "z": 180}  // Optional
    }
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    data = request.get_json() or {}

    required = ['component', 'anomaly_type', 'description']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({
            'success': False,
            'error': f'Missing required fields: {missing}'
        }), 400

    anomaly_id = service.add_anomaly(
        machine_id=machine_id,
        component=data['component'],
        anomaly_type=data['anomaly_type'],
        severity=data.get('severity', 'warning'),
        description=data['description'],
        position=data.get('position')
    )

    return jsonify({
        'success': True,
        'anomaly_id': anomaly_id,
        'machine_id': machine_id
    }), 201


@predictive_unity_bp.route('/<machine_id>/anomaly/<anomaly_id>', methods=['DELETE'])
def clear_anomaly(machine_id: str, anomaly_id: str):
    """Clear an anomaly marker."""
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    cleared = service.clear_anomaly(machine_id, anomaly_id)

    if cleared:
        return jsonify({
            'success': True,
            'message': f'Anomaly {anomaly_id} cleared'
        })
    else:
        return jsonify({
            'success': False,
            'error': f'Anomaly {anomaly_id} not found'
        }), 404


# =============================================================================
# Trends
# =============================================================================

@predictive_unity_bp.route('/<machine_id>/trends', methods=['GET'])
def get_all_trends(machine_id: str):
    """Get all trend data for Unity charts."""
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_predictive_state(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    trends = {}
    for name, td in state.trends.items():
        trends[name] = {
            'metric': td.metric_name,
            'unit': td.unit,
            'data': {
                'timestamps': td.timestamps[-100:],
                'values': td.values[-100:]
            },
            'predictions': {
                'timestamps': td.prediction_timestamps,
                'values': td.prediction_values
            },
            'thresholds': {
                'warning': td.warning_threshold,
                'critical': td.critical_threshold
            }
        }

    return jsonify({
        'success': True,
        'machine_id': machine_id,
        'timestamp': state.timestamp,
        'trends': trends
    })


@predictive_unity_bp.route('/<machine_id>/trends/<metric>', methods=['GET'])
def get_trend(machine_id: str, metric: str):
    """Get specific trend data for Unity chart."""
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    state = service.get_predictive_state(machine_id)
    if not state:
        return jsonify({
            'success': False,
            'error': f'No predictive state for machine {machine_id}'
        }), 404

    if metric not in state.trends:
        return jsonify({
            'success': False,
            'error': f'Trend {metric} not found'
        }), 404

    td = state.trends[metric]

    return jsonify({
        'success': True,
        'machine_id': machine_id,
        'metric': metric,
        'data': {
            'timestamps': td.timestamps[-100:],
            'values': td.values[-100:]
        },
        'predictions': {
            'timestamps': td.prediction_timestamps,
            'values': td.prediction_values
        },
        'thresholds': {
            'warning': td.warning_threshold,
            'critical': td.critical_threshold
        },
        'unit': td.unit
    })


@predictive_unity_bp.route('/<machine_id>/trends/<metric>', methods=['POST'])
def update_trend(machine_id: str, metric: str):
    """
    Update trend data from ML service.

    Request body:
    {
        "timestamps": [1705000000, 1705000060, ...],
        "values": [25.5, 26.0, ...],
        "predictions": {
            "timestamps": [1705001000, 1705002000],
            "values": [28.0, 29.5]
        },
        "thresholds": {
            "warning": 30.0,
            "critical": 40.0
        }
    }
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    data = request.get_json() or {}

    if 'timestamps' not in data or 'values' not in data:
        return jsonify({
            'success': False,
            'error': 'timestamps and values are required'
        }), 400

    service.update_trend_data(
        machine_id=machine_id,
        metric_name=metric,
        timestamps=data['timestamps'],
        values=data['values'],
        predictions=data.get('predictions'),
        thresholds=data.get('thresholds')
    )

    return jsonify({
        'success': True,
        'message': f'Updated trend {metric}',
        'machine_id': machine_id
    })


# =============================================================================
# Health Update (from ML services)
# =============================================================================

@predictive_unity_bp.route('/<machine_id>/health', methods=['POST'])
def update_health_scores(machine_id: str):
    """
    Update health scores from ML service.

    Request body:
    {
        "scores": {
            "spindle": 85.0,
            "bearing": 92.0,
            "motor": 78.5
        },
        "trends": {
            "spindle": "stable",
            "bearing": "improving",
            "motor": "declining"
        }
    }
    """
    service = get_predictive_service()
    if not service:
        return jsonify({
            'success': False,
            'error': 'Predictive service not available'
        }), 503

    data = request.get_json() or {}
    scores = data.get('scores', {})
    trends = data.get('trends', {})

    if not scores:
        return jsonify({
            'success': False,
            'error': 'No scores provided'
        }), 400

    service.update_health_scores(machine_id, scores, trends)

    return jsonify({
        'success': True,
        'message': f'Updated {len(scores)} health scores',
        'machine_id': machine_id
    })
