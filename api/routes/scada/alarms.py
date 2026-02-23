"""
LEGO Factory v3 - Alarm API Routes
==================================
REST API for ISA-18.2 alarm management with Pydantic validation.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timedelta
import logging

from services.scada.alarm_management.alarm_service import (
    get_alarm_service,
    alarm_processor,
    start_alarm_processor,
    stop_alarm_processor
)
from config.database import get_db_session

# Import Pydantic schemas and validation utilities
from api.schemas import (
    AlarmDefinitionCreate,
    AlarmDefinitionUpdate,
    AlarmAcknowledge,
    AlarmShelveRequest,
    AlarmUnshelveRequest,
    AlarmGroupCreate,
)
from api.utils.validation import validate_request, validate_path_param

logger = logging.getLogger(__name__)

alarms_bp = Blueprint('alarms', __name__, url_prefix='/alarms')


@alarms_bp.route('/definitions', methods=['GET'])
@jwt_required()
def list_alarm_definitions():
    """Get all alarm definitions with filtering"""
    try:
        area = request.args.get('area')
        priority = request.args.get('priority')
        alarm_class = request.args.get('class')
        enabled = request.args.get('enabled')
        search = request.args.get('search')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        if enabled is not None:
            enabled = enabled.lower() == 'true'

        with get_db_session() as session:
            service = get_alarm_service(session)
            definitions = service.get_alarm_definitions(
                area=area,
                priority=priority,
                alarm_class=alarm_class,
                enabled=enabled,
                search=search,
                limit=limit,
                offset=offset
            )
            return jsonify({'definitions': definitions, 'count': len(definitions)})
    except Exception as e:
        logger.error(f"Error listing alarm definitions: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/definitions/<alarm_id>', methods=['GET'])
@jwt_required()
def get_alarm_definition(alarm_id: str):
    """Get alarm definition by ID"""
    try:
        with get_db_session() as session:
            service = get_alarm_service(session)
            definition = service.get_alarm_definition(alarm_id)
            if not definition:
                return jsonify({'error': 'Alarm definition not found'}), 404
            return jsonify(definition)
    except Exception as e:
        logger.error(f"Error getting alarm definition {alarm_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/definitions', methods=['POST'])
@validate_request(AlarmDefinitionCreate)
def create_alarm_definition(validated_data: AlarmDefinitionCreate):
    """
    Create a new alarm definition.

    Request body (validated by Pydantic):
        {
            "alarm_id": "string (required, unique identifier)",
            "name": "string (required, 1-200 chars)",
            "tag_id": "string (required, associated tag)",
            "alarm_type": "high|low|hihi|lolo|deviation|rate_of_change|digital|equipment",
            "priority": "diagnostic|low|medium|high|critical (default: medium)",
            "alarm_class": "process|equipment|safety|environmental|quality",
            "setpoint": "number (required for level alarms)",
            "deadband": "number (optional, default: 0)",
            "delay_on_ms": "integer (optional, on-delay in ms)",
            "delay_off_ms": "integer (optional, off-delay in ms)",
            "area": "string (optional)",
            "equipment": "string (optional)",
            "message": "string (optional, custom message template)"
        }

    Returns:
        201: Created alarm definition
        400: Validation error with field details
        500: Server error
    """
    try:
        with get_db_session() as session:
            service = get_alarm_service(session)
            definition = service.create_alarm_definition(validated_data.model_dump(exclude_none=True))
            session.commit()
            return jsonify(definition), 201
    except Exception as e:
        logger.error(f"Error creating alarm definition: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/definitions/<alarm_id>', methods=['PUT'])
@jwt_required()
def update_alarm_definition(alarm_id: str):
    """Update alarm definition"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        with get_db_session() as session:
            service = get_alarm_service(session)
            definition = service.update_alarm_definition(alarm_id, data)
            if not definition:
                return jsonify({'error': 'Alarm definition not found'}), 404
            session.commit()
            return jsonify(definition)
    except Exception as e:
        logger.error(f"Error updating alarm definition {alarm_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/definitions/<alarm_id>', methods=['DELETE'])
@jwt_required()
def delete_alarm_definition(alarm_id: str):
    """Delete alarm definition (soft delete)"""
    try:
        with get_db_session() as session:
            service = get_alarm_service(session)
            success = service.delete_alarm_definition(alarm_id)
            if not success:
                return jsonify({'error': 'Alarm definition not found'}), 404
            session.commit()
            return jsonify({'message': 'Alarm definition deleted'})
    except Exception as e:
        logger.error(f"Error deleting alarm definition {alarm_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/active', methods=['GET'])
@jwt_required()
def get_active_alarms():
    """Get currently active alarms"""
    try:
        priority = request.args.get('priority')
        area = request.args.get('area')
        unacknowledged = request.args.get('unacknowledged')

        if unacknowledged is not None:
            unacknowledged = unacknowledged.lower() == 'true'

        with get_db_session() as session:
            service = get_alarm_service(session)
            alarms = service.get_active_alarms(
                priority=priority,
                area=area,
                unacknowledged_only=unacknowledged
            )
            return jsonify({'alarms': alarms, 'count': len(alarms)})
    except Exception as e:
        logger.error(f"Error getting active alarms: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/events/<event_id>/acknowledge', methods=['POST'])
@jwt_required()
def acknowledge_alarm(event_id: str):
    """Acknowledge an alarm event"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'system')
        comment = data.get('comment')

        with get_db_session() as session:
            service = get_alarm_service(session)
            event = service.acknowledge_alarm(event_id, user_id, comment)
            if not event:
                return jsonify({'error': 'Alarm event not found'}), 404
            session.commit()
            return jsonify(event)
    except Exception as e:
        logger.error(f"Error acknowledging alarm {event_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/definitions/<alarm_id>/shelve', methods=['POST'])
@jwt_required()
def shelve_alarm(alarm_id: str):
    """Shelve an alarm definition"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        user_id = data.get('user_id', 'system')
        duration_minutes = data.get('duration_minutes', 60)
        reason = data.get('reason')

        with get_db_session() as session:
            service = get_alarm_service(session)
            success = service.shelve_alarm(alarm_id, user_id, duration_minutes, reason)
            if not success:
                return jsonify({'error': 'Alarm definition not found'}), 404
            session.commit()
            return jsonify({
                'message': 'Alarm shelved',
                'alarm_id': alarm_id,
                'duration_minutes': duration_minutes
            })
    except Exception as e:
        logger.error(f"Error shelving alarm {alarm_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/definitions/<alarm_id>/unshelve', methods=['POST'])
@jwt_required()
def unshelve_alarm(alarm_id: str):
    """Unshelve an alarm definition"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id', 'system')

        with get_db_session() as session:
            service = get_alarm_service(session)
            success = service.unshelve_alarm(alarm_id, user_id)
            if not success:
                return jsonify({'error': 'Alarm definition not found'}), 404
            session.commit()
            return jsonify({'message': 'Alarm unshelved', 'alarm_id': alarm_id})
    except Exception as e:
        logger.error(f"Error unshelving alarm {alarm_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/history', methods=['GET'])
@jwt_required(optional=True)
def get_alarm_history():
    """Get alarm event history"""
    try:
        alarm_ids = request.args.getlist('alarm_id')
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        priority = request.args.get('priority')
        limit = request.args.get('limit', 1000, type=int)

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=24)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        with get_db_session() as session:
            service = get_alarm_service(session)
            events = service.get_alarm_history(
                alarm_id=alarm_ids[0] if alarm_ids else None,
                start_time=start,
                end_time=end,
                limit=limit
            )
            return jsonify({'events': events, 'count': len(events)})
    except Exception as e:
        logger.error(f"Error getting alarm history: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/summary', methods=['GET'])
@jwt_required(optional=True)
def get_alarm_summary():
    """Get alarm summary statistics"""
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=24)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        with get_db_session() as session:
            service = get_alarm_service(session)
            summary = service.get_alarm_summary()
            return jsonify(summary)
    except Exception as e:
        logger.error(f"Error getting alarm summary: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/analytics/by-area', methods=['GET'])
@jwt_required()
def get_alarms_by_area():
    """Get alarm counts by area"""
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(days=7)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        with get_db_session() as session:
            service = get_alarm_service(session)
            result = service.get_alarm_counts_by_area(start, end)
            return jsonify({'data': result})
    except Exception as e:
        logger.error(f"Error getting alarms by area: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/analytics/chattering', methods=['GET'])
@jwt_required()
def get_chattering_alarms():
    """Get chattering alarms (high frequency)"""
    try:
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        threshold = request.args.get('threshold', 10, type=int)

        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow() - timedelta(hours=1)
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        with get_db_session() as session:
            service = get_alarm_service(session)
            result = service.get_chattering_alarms(start, end, threshold)
            return jsonify({'alarms': result})
    except Exception as e:
        logger.error(f"Error getting chattering alarms: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/groups', methods=['GET'])
@jwt_required()
def list_alarm_groups():
    """Get alarm groups"""
    try:
        with get_db_session() as session:
            service = get_alarm_service(session)
            groups = service.get_alarm_groups()
            return jsonify({'groups': groups, 'count': len(groups)})
    except Exception as e:
        logger.error(f"Error listing alarm groups: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/groups', methods=['POST'])
@jwt_required()
def create_alarm_group():
    """Create an alarm group"""
    try:
        data = request.get_json()
        if not data or 'name' not in data:
            return jsonify({'error': 'No name provided'}), 400

        with get_db_session() as session:
            service = get_alarm_service(session)
            group = service.create_alarm_group(
                name=data['name'],
                description=data.get('description'),
                alarm_ids=data.get('alarm_ids', [])
            )
            session.commit()
            return jsonify(group), 201
    except Exception as e:
        logger.error(f"Error creating alarm group: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/processor/start', methods=['POST'])
@jwt_required()
def start_processor():
    """Start the alarm processor"""
    try:
        start_alarm_processor()
        return jsonify({'message': 'Alarm processor started'})
    except Exception as e:
        logger.error(f"Error starting alarm processor: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/processor/stop', methods=['POST'])
@jwt_required()
def stop_processor():
    """Stop the alarm processor"""
    try:
        stop_alarm_processor()
        return jsonify({'message': 'Alarm processor stopped'})
    except Exception as e:
        logger.error(f"Error stopping alarm processor: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/processor/status', methods=['GET'])
@jwt_required()
def processor_status():
    """Get alarm processor status"""
    try:
        stats = alarm_processor.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting processor status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@alarms_bp.route('/types', methods=['GET'])
@jwt_required()
def get_alarm_types():
    """Get available alarm types, priorities, and states"""
    from models.scada.alarms import AlarmPriority, AlarmClass, AlarmType, AlarmState

    return jsonify({
        'priorities': [p.value for p in AlarmPriority],
        'classes': [c.value for c in AlarmClass],
        'types': [t.value for t in AlarmType],
        'states': [s.value for s in AlarmState]
    })
