"""
SCADA API Routes
REST API for machine control, tags, alarms, historian, and recipes.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from flask import Blueprint, request, jsonify, current_app
import asyncio

from services.scada.tag_management.tag_service import (
    TagService, tag_cache, write_tag_value, read_tag_value, read_tag_values
)
from services.scada.alarm_management.alarm_service import (
    AlarmService, alarm_processor, process_tag_value, AlarmPriority
)
from services.scada.historian.historian_service import (
    HistorianReader, HistorianExporter, historian_writer, write_to_historian
)
from services.scada.machine_control.machine_service import (
    machine_manager, MachineManager, ControllerType
)
from config.database import get_session

scada_bp = Blueprint('scada', __name__, url_prefix='/api/scada')


# =============================================================================
# MACHINE CONTROL
# =============================================================================

@scada_bp.route('/machines', methods=['GET'])
def list_machines():
    """List all registered machines"""
    machines = machine_manager.list_machines()
    statuses = machine_manager.get_all_status()
    
    result = []
    for machine_id in machines:
        status = statuses.get(machine_id)
        result.append({
            'machine_id': machine_id,
            'state': status.state.value if status else 'unknown',
            'position': {
                'x': status.position.x if status else 0,
                'y': status.position.y if status else 0,
                'z': status.position.z if status else 0
            },
            'progress': status.progress_pct if status else 0
        })
    
    return jsonify(result)


@scada_bp.route('/machines/ports', methods=['GET'])
def list_serial_ports():
    """List available serial ports"""
    ports = MachineManager.list_serial_ports()
    return jsonify(ports)


@scada_bp.route('/machines', methods=['POST'])
def register_machine():
    """Register a new machine"""
    data = request.json
    
    try:
        controller_type = ControllerType(data['controller_type'])
    except ValueError:
        return jsonify({'error': f"Invalid controller type: {data['controller_type']}"}), 400
    
    machine = machine_manager.register_machine(
        machine_id=data['machine_id'],
        controller_type=controller_type,
        config=data.get('config', {})
    )
    
    return jsonify({
        'machine_id': data['machine_id'],
        'controller_type': controller_type.value,
        'status': 'registered'
    })


@scada_bp.route('/machines/<machine_id>/connect', methods=['POST'])
async def connect_machine(machine_id: str):
    """Connect to a machine"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    success = await machine.connect()
    return jsonify({
        'machine_id': machine_id,
        'connected': success,
        'state': machine.status.state.value
    })


@scada_bp.route('/machines/<machine_id>/disconnect', methods=['POST'])
async def disconnect_machine(machine_id: str):
    """Disconnect from a machine"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    success = await machine.disconnect()
    return jsonify({
        'machine_id': machine_id,
        'disconnected': success
    })


@scada_bp.route('/machines/<machine_id>/status', methods=['GET'])
def get_machine_status(machine_id: str):
    """Get machine status"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    status = machine.status
    return jsonify({
        'machine_id': machine_id,
        'state': status.state.value,
        'position': {
            'x': status.position.x,
            'y': status.position.y,
            'z': status.position.z,
            'a': status.position.a
        },
        'feed_rate': status.feed_rate,
        'spindle_speed': status.spindle_speed,
        'current_line': status.current_line,
        'total_lines': status.total_lines,
        'progress_pct': status.progress_pct,
        'error_message': status.error_message,
        'timestamp': status.timestamp.isoformat()
    })


@scada_bp.route('/machines/<machine_id>/home', methods=['POST'])
async def home_machine(machine_id: str):
    """Home the machine"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    data = request.json or {}
    axes = data.get('axes', 'XYZ')
    
    success = await machine.home(axes)
    return jsonify({
        'machine_id': machine_id,
        'homed': success,
        'axes': axes
    })


@scada_bp.route('/machines/<machine_id>/zero', methods=['POST'])
async def zero_machine(machine_id: str):
    """Zero work coordinates"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    data = request.json or {}
    axes = data.get('axes', 'XYZ')
    
    success = await machine.zero(axes)
    return jsonify({
        'machine_id': machine_id,
        'zeroed': success,
        'axes': axes
    })


@scada_bp.route('/machines/<machine_id>/jog', methods=['POST'])
async def jog_machine(machine_id: str):
    """Jog an axis"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    data = request.json
    axis = data.get('axis', 'X')
    distance = data.get('distance', 1.0)
    feed_rate = data.get('feed_rate', 100.0)
    
    success = await machine.jog(axis, distance, feed_rate)
    return jsonify({
        'machine_id': machine_id,
        'jogged': success,
        'axis': axis,
        'distance': distance
    })


@scada_bp.route('/machines/<machine_id>/gcode', methods=['POST'])
async def run_gcode(machine_id: str):
    """Run G-code program"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    data = request.json
    gcode = data.get('gcode', '')
    
    if not gcode:
        return jsonify({'error': 'No G-code provided'}), 400
    
    success = await machine.run_gcode(gcode)
    return jsonify({
        'machine_id': machine_id,
        'completed': success
    })


@scada_bp.route('/machines/<machine_id>/pause', methods=['POST'])
async def pause_machine(machine_id: str):
    """Pause execution"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    success = await machine.pause()
    return jsonify({'machine_id': machine_id, 'paused': success})


@scada_bp.route('/machines/<machine_id>/resume', methods=['POST'])
async def resume_machine(machine_id: str):
    """Resume execution"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    success = await machine.resume()
    return jsonify({'machine_id': machine_id, 'resumed': success})


@scada_bp.route('/machines/<machine_id>/stop', methods=['POST'])
async def stop_machine(machine_id: str):
    """Stop execution"""
    machine = machine_manager.get_machine(machine_id)
    if not machine:
        return jsonify({'error': 'Machine not found'}), 404
    
    success = await machine.stop()
    return jsonify({'machine_id': machine_id, 'stopped': success})


# =============================================================================
# TAG MANAGEMENT
# =============================================================================

@scada_bp.route('/tags', methods=['GET'])
def get_tags():
    """Get tags with filtering"""
    group_id = request.args.get('group_id')
    source_type = request.args.get('source_type')
    is_active = request.args.get('is_active', type=lambda x: x.lower() == 'true')
    search = request.args.get('search')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    with get_session() as session:
        service = TagService(session)
        tags = service.get_tags(
            group_id=group_id,
            source_type=source_type,
            is_active=is_active,
            search=search,
            limit=limit,
            offset=offset
        )
        
        return jsonify([{
            'tag_id': str(t.tag_id),
            'tag_name': t.tag_name,
            'description': t.description,
            'data_type': t.data_type,
            'eng_units': t.eng_units,
            'source_type': t.source_type,
            'source_address': t.source_address,
            'is_active': t.is_active
        } for t in tags])


@scada_bp.route('/tags', methods=['POST'])
def create_tag():
    """Create a new tag"""
    data = request.json
    
    with get_session() as session:
        service = TagService(session)
        tag = service.create_tag(data)
        
        return jsonify({
            'tag_id': str(tag.tag_id),
            'tag_name': tag.tag_name,
            'created': True
        }), 201


@scada_bp.route('/tags/<tag_id>', methods=['GET'])
def get_tag(tag_id: str):
    """Get tag by ID"""
    with get_session() as session:
        service = TagService(session)
        tag = service.get_tag(tag_id)
        
        if not tag:
            return jsonify({'error': 'Tag not found'}), 404
        
        return jsonify({
            'tag_id': str(tag.tag_id),
            'tag_name': tag.tag_name,
            'description': tag.description,
            'data_type': tag.data_type,
            'eng_units': tag.eng_units,
            'eng_low': float(tag.eng_low) if tag.eng_low else None,
            'eng_high': float(tag.eng_high) if tag.eng_high else None,
            'alarm_hh': float(tag.alarm_hh) if tag.alarm_hh else None,
            'alarm_hi': float(tag.alarm_hi) if tag.alarm_hi else None,
            'alarm_lo': float(tag.alarm_lo) if tag.alarm_lo else None,
            'alarm_ll': float(tag.alarm_ll) if tag.alarm_ll else None,
            'scan_rate_ms': tag.scan_rate_ms,
            'source_type': tag.source_type,
            'source_address': tag.source_address,
            'is_active': tag.is_active
        })


@scada_bp.route('/tags/<tag_id>', methods=['PUT'])
def update_tag(tag_id: str):
    """Update tag configuration"""
    data = request.json
    
    with get_session() as session:
        service = TagService(session)
        tag = service.update_tag(tag_id, data)
        
        if not tag:
            return jsonify({'error': 'Tag not found'}), 404
        
        return jsonify({
            'tag_id': str(tag.tag_id),
            'tag_name': tag.tag_name,
            'updated': True
        })


@scada_bp.route('/tags/<tag_id>/value', methods=['GET'])
async def get_tag_value(tag_id: str):
    """Get current tag value"""
    value = await read_tag_value(tag_id)
    
    if not value:
        return jsonify({'error': 'No value available'}), 404
    
    return jsonify({
        'tag_id': value.tag_id,
        'tag_name': value.tag_name,
        'value': value.value,
        'quality': value.quality,
        'timestamp': value.timestamp.isoformat(),
        'eng_units': value.eng_units
    })


@scada_bp.route('/tags/values', methods=['GET'])
async def get_tag_values():
    """Get multiple tag values"""
    tag_ids = request.args.getlist('tag_id')
    
    if not tag_ids:
        return jsonify({'error': 'No tag IDs provided'}), 400
    
    values = await read_tag_values(tag_ids)
    
    return jsonify({
        tid: {
            'value': v.value,
            'quality': v.quality,
            'timestamp': v.timestamp.isoformat()
        } for tid, v in values.items()
    })


@scada_bp.route('/tags/groups', methods=['GET'])
def get_tag_groups():
    """Get tag group hierarchy"""
    with get_session() as session:
        service = TagService(session)
        hierarchy = service.get_group_hierarchy()
        return jsonify(hierarchy)


@scada_bp.route('/tags/groups', methods=['POST'])
def create_tag_group():
    """Create a tag group"""
    data = request.json
    
    with get_session() as session:
        service = TagService(session)
        group = service.create_group(
            name=data['name'],
            description=data.get('description'),
            parent_group_id=data.get('parent_group_id')
        )
        
        return jsonify({
            'group_id': str(group.group_id),
            'name': group.name,
            'path': group.path
        }), 201


# =============================================================================
# ALARM MANAGEMENT
# =============================================================================

@scada_bp.route('/alarms/active', methods=['GET'])
def get_active_alarms():
    """Get active alarms"""
    priority = request.args.get('priority', type=int)
    status = request.args.get('status')
    include_shelved = request.args.get('include_shelved', 'true').lower() == 'true'
    
    with get_session() as session:
        service = AlarmService(session)
        alarms = service.get_active_alarms(
            priority=priority,
            status=status,
            include_shelved=include_shelved
        )
        
        return jsonify([{
            'instance_id': str(a.instance_id),
            'alarm_id': str(a.alarm_id),
            'tag_id': str(a.tag_id),
            'status': a.status,
            'priority': a.priority,
            'value': float(a.alarm_value) if a.alarm_value else None,
            'alarm_time': a.alarm_time.isoformat(),
            'ack_time': a.ack_time.isoformat() if a.ack_time else None,
            'shelved_until': a.shelved_until.isoformat() if a.shelved_until else None
        } for a in alarms])


@scada_bp.route('/alarms/standing', methods=['GET'])
def get_standing_alarms():
    """Get unacknowledged alarms"""
    with get_session() as session:
        service = AlarmService(session)
        alarms = service.get_standing_alarms()
        
        return jsonify([{
            'instance_id': str(a.instance_id),
            'alarm_id': str(a.alarm_id),
            'tag_id': str(a.tag_id),
            'priority': a.priority,
            'value': float(a.alarm_value) if a.alarm_value else None,
            'alarm_time': a.alarm_time.isoformat()
        } for a in alarms])


@scada_bp.route('/alarms/summary', methods=['GET'])
def get_alarm_summary():
    """Get alarm summary counts"""
    with get_session() as session:
        service = AlarmService(session)
        summary = service.get_alarm_summary()
        
        return jsonify({
            'total_active': summary.total_active,
            'unacknowledged': summary.unacknowledged,
            'acknowledged_active': summary.acknowledged_active,
            'shelved': summary.shelved,
            'by_priority': summary.by_priority
        })


@scada_bp.route('/alarms/<instance_id>/acknowledge', methods=['POST'])
def acknowledge_alarm(instance_id: str):
    """Acknowledge an alarm"""
    data = request.json or {}
    user_id = data.get('user_id', 'system')
    notes = data.get('notes')
    
    with get_session() as session:
        service = AlarmService(session)
        alarm = service.acknowledge(instance_id, user_id, notes)
        
        if not alarm:
            return jsonify({'error': 'Alarm not found'}), 404
        
        return jsonify({
            'instance_id': instance_id,
            'acknowledged': True
        })


@scada_bp.route('/alarms/acknowledge-all', methods=['POST'])
def acknowledge_all_alarms():
    """Acknowledge all active alarms"""
    data = request.json or {}
    user_id = data.get('user_id', 'system')
    priority = data.get('priority', type=int)
    
    with get_session() as session:
        service = AlarmService(session)
        count = service.acknowledge_all(user_id, priority)
        
        return jsonify({
            'acknowledged_count': count
        })


@scada_bp.route('/alarms/<instance_id>/shelve', methods=['POST'])
def shelve_alarm(instance_id: str):
    """Shelve (temporarily suppress) an alarm"""
    data = request.json
    user_id = data.get('user_id', 'system')
    duration_minutes = data.get('duration_minutes', 30)
    reason = data.get('reason', 'No reason provided')
    
    with get_session() as session:
        service = AlarmService(session)
        alarm = service.shelve(instance_id, user_id, duration_minutes, reason)
        
        if not alarm:
            return jsonify({'error': 'Alarm not found'}), 404
        
        return jsonify({
            'instance_id': instance_id,
            'shelved': True,
            'shelved_until': alarm.shelved_until.isoformat()
        })


@scada_bp.route('/alarms/history', methods=['GET'])
def get_alarm_history():
    """Get alarm history"""
    alarm_id = request.args.get('alarm_id')
    tag_id = request.args.get('tag_id')
    start_time = request.args.get('start')
    end_time = request.args.get('end')
    event_types = request.args.getlist('event_type')
    limit = request.args.get('limit', 100, type=int)
    
    # Parse dates
    start = datetime.fromisoformat(start_time) if start_time else datetime.utcnow() - timedelta(days=1)
    end = datetime.fromisoformat(end_time) if end_time else datetime.utcnow()
    
    with get_session() as session:
        service = AlarmService(session)
        history = service.get_alarm_history(
            alarm_id=alarm_id,
            tag_id=tag_id,
            start_time=start,
            end_time=end,
            event_types=event_types or None,
            limit=limit
        )
        
        return jsonify([{
            'id': h.id,
            'instance_id': str(h.instance_id),
            'alarm_id': str(h.alarm_id),
            'event_type': h.event_type,
            'event_time': h.event_time.isoformat(),
            'priority': h.priority,
            'value': float(h.alarm_value) if h.alarm_value else None
        } for h in history])


@scada_bp.route('/alarms/definitions', methods=['GET'])
def get_alarm_definitions():
    """Get alarm definitions"""
    enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
    
    with get_session() as session:
        service = AlarmService(session)
        alarms = service.get_all_alarms(enabled_only=enabled_only)
        
        return jsonify([{
            'alarm_id': str(a.alarm_id),
            'tag_id': str(a.tag_id),
            'alarm_type': a.alarm_type,
            'priority': a.priority,
            'setpoint': float(a.setpoint) if a.setpoint else None,
            'message_template': a.message_template,
            'is_enabled': a.is_enabled
        } for a in alarms])


@scada_bp.route('/alarms/definitions', methods=['POST'])
def create_alarm_definition():
    """Create an alarm definition"""
    data = request.json
    
    with get_session() as session:
        service = AlarmService(session)
        alarm = service.create_alarm(data)
        
        return jsonify({
            'alarm_id': str(alarm.alarm_id),
            'created': True
        }), 201


# =============================================================================
# HISTORIAN
# =============================================================================

@scada_bp.route('/historian/raw', methods=['GET'])
def get_historian_raw():
    """Get raw historical data"""
    tag_ids = request.args.getlist('tag_id')
    start = request.args.get('start')
    end = request.args.get('end')
    limit = request.args.get('limit', 10000, type=int)
    
    if not tag_ids:
        return jsonify({'error': 'No tag IDs provided'}), 400
    
    start_time = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(hours=1)
    end_time = datetime.fromisoformat(end) if end else datetime.utcnow()
    
    reader = HistorianReader()
    df = reader.get_raw(tag_ids, start_time, end_time, limit)
    
    # Convert to JSON-friendly format
    return jsonify({
        'columns': list(df.columns),
        'data': df.to_dict('records')
    })


@scada_bp.route('/historian/aggregated', methods=['GET'])
def get_historian_aggregated():
    """Get aggregated historical data"""
    tag_ids = request.args.getlist('tag_id')
    start = request.args.get('start')
    end = request.args.get('end')
    bucket = request.args.get('bucket', '1 minute')
    agg = request.args.get('agg', 'avg')
    
    if not tag_ids:
        return jsonify({'error': 'No tag IDs provided'}), 400
    
    start_time = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(hours=1)
    end_time = datetime.fromisoformat(end) if end else datetime.utcnow()
    
    reader = HistorianReader()
    df = reader.get_aggregated(tag_ids, start_time, end_time, bucket, agg)
    
    return jsonify({
        'columns': list(df.columns),
        'data': df.to_dict('records')
    })


@scada_bp.route('/historian/trend', methods=['GET'])
def get_historian_trend():
    """Get trend data (auto-downsampled)"""
    tag_ids = request.args.getlist('tag_id')
    start = request.args.get('start')
    end = request.args.get('end')
    max_points = request.args.get('max_points', 1000, type=int)
    
    if not tag_ids:
        return jsonify({'error': 'No tag IDs provided'}), 400
    
    start_time = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(hours=1)
    end_time = datetime.fromisoformat(end) if end else datetime.utcnow()
    
    reader = HistorianReader()
    df = reader.get_trend(tag_ids, start_time, end_time, max_points)
    
    return jsonify({
        'columns': list(df.columns),
        'data': df.to_dict('records')
    })


@scada_bp.route('/historian/statistics', methods=['GET'])
def get_historian_statistics():
    """Get statistics for tags"""
    tag_ids = request.args.getlist('tag_id')
    start = request.args.get('start')
    end = request.args.get('end')
    
    if not tag_ids:
        return jsonify({'error': 'No tag IDs provided'}), 400
    
    start_time = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(hours=1)
    end_time = datetime.fromisoformat(end) if end else datetime.utcnow()
    
    reader = HistorianReader()
    df = reader.get_statistics(tag_ids, start_time, end_time)
    
    return jsonify(df.to_dict('records'))


@scada_bp.route('/historian/export', methods=['POST'])
def export_historian_data():
    """Export historical data"""
    data = request.json
    tag_ids = data.get('tag_ids', [])
    start = data.get('start')
    end = data.get('end')
    format = data.get('format', 'csv')
    aggregation = data.get('aggregation')
    bucket = data.get('bucket', '1 minute')
    
    if not tag_ids:
        return jsonify({'error': 'No tag IDs provided'}), 400
    
    start_time = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(hours=1)
    end_time = datetime.fromisoformat(end) if end else datetime.utcnow()
    
    exporter = HistorianExporter()
    
    # Generate filename
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'/tmp/historian_export_{timestamp}.{format}'
    
    if format == 'csv':
        path = exporter.export_csv(tag_ids, start_time, end_time, filename, aggregation, bucket)
    elif format == 'parquet':
        path = exporter.export_parquet(tag_ids, start_time, end_time, filename)
    elif format == 'npz':
        path = exporter.export_npz(tag_ids, start_time, end_time, filename)
    else:
        return jsonify({'error': f'Unsupported format: {format}'}), 400
    
    return jsonify({
        'path': path,
        'format': format
    })


@scada_bp.route('/historian/stats', methods=['GET'])
def get_historian_stats():
    """Get historian system statistics"""
    return jsonify(historian_writer.get_stats())


# =============================================================================
# HEALTH CHECK
# =============================================================================

@scada_bp.route('/health', methods=['GET'])
def health_check():
    """SCADA health check"""
    return jsonify({
        'status': 'healthy',
        'machines_registered': len(machine_manager.list_machines()),
        'historian': historian_writer.get_stats(),
        'timestamp': datetime.utcnow().isoformat()
    })
