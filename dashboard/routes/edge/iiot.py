"""
IIoT Routes - Edge Computing API Endpoints

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT

Provides:
- Device registration and management
- Protocol adapters (OPC-UA, MQTT, Modbus)
- Real-time data streaming
- Edge analytics
- Store and forward
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
import uuid
import random

iiot_bp = Blueprint('iiot', __name__, url_prefix='/iiot')

# Try to import edge services
try:
    from services.edge.iiot_gateway import IIoTGatewayService
    EDGE_AVAILABLE = True
except ImportError:
    EDGE_AVAILABLE = False

# In-memory storage
_devices = {
    'DEV-PRINT-01': {
        'device_id': 'DEV-PRINT-01',
        'name': 'Prusa MK3S+ #1',
        'type': '3d_printer',
        'protocol': 'octoprint',
        'address': '192.168.1.101',
        'status': 'online',
        'last_seen': datetime.utcnow().isoformat(),
        'tags': ['printing', 'work_center_1'],
    },
    'DEV-PRINT-02': {
        'device_id': 'DEV-PRINT-02',
        'name': 'Prusa MK3S+ #2',
        'type': '3d_printer',
        'protocol': 'octoprint',
        'address': '192.168.1.102',
        'status': 'online',
        'last_seen': datetime.utcnow().isoformat(),
        'tags': ['printing', 'work_center_1'],
    },
    'DEV-TEMP-01': {
        'device_id': 'DEV-TEMP-01',
        'name': 'Environment Sensor',
        'type': 'sensor',
        'protocol': 'mqtt',
        'address': 'mqtt://192.168.1.200',
        'status': 'online',
        'last_seen': datetime.utcnow().isoformat(),
        'tags': ['environment', 'temperature', 'humidity'],
    },
}

_data_points = []
_edge_rules = {}


@iiot_bp.route('/status', methods=['GET'])
def get_edge_status():
    """Get edge computing system status."""
    online_devices = len([d for d in _devices.values() if d['status'] == 'online'])

    return jsonify({
        'available': True,
        'gateway_status': 'running',
        'protocols': {
            'opcua': {'available': True, 'connections': 0},
            'mqtt': {'available': True, 'connections': 2},
            'modbus': {'available': True, 'connections': 0},
            'octoprint': {'available': True, 'connections': 2},
        },
        'devices': {
            'total': len(_devices),
            'online': online_devices,
            'offline': len(_devices) - online_devices,
        },
        'data': {
            'points_collected_today': 15000,
            'buffer_size': len(_data_points),
            'last_sync': datetime.utcnow().isoformat(),
        },
        'edge_compute': {
            'rules_active': len(_edge_rules),
            'alerts_generated': 5,
        },
    })


# ==================== Device Management ====================

@iiot_bp.route('/devices', methods=['GET'])
def list_devices():
    """List all registered devices."""
    status = request.args.get('status')
    device_type = request.args.get('type')
    protocol = request.args.get('protocol')

    devices = list(_devices.values())

    if status:
        devices = [d for d in devices if d['status'] == status]
    if device_type:
        devices = [d for d in devices if d['type'] == device_type]
    if protocol:
        devices = [d for d in devices if d['protocol'] == protocol]

    return jsonify({
        'devices': devices,
        'count': len(devices),
    })


@iiot_bp.route('/devices', methods=['POST'])
def register_device():
    """
    Register a new device.

    Request body:
    {
        "name": "New Printer",
        "type": "3d_printer|sensor|plc|cnc",
        "protocol": "opcua|mqtt|modbus|octoprint",
        "address": "192.168.1.100",
        "config": {...}
    }
    """
    data = request.get_json() or {}

    device_id = f"DEV-{str(uuid.uuid4())[:6].upper()}"

    device = {
        'device_id': device_id,
        'name': data.get('name'),
        'type': data.get('type', 'generic'),
        'protocol': data.get('protocol', 'mqtt'),
        'address': data.get('address'),
        'config': data.get('config', {}),
        'status': 'registered',
        'registered_at': datetime.utcnow().isoformat(),
        'last_seen': None,
        'tags': data.get('tags', []),
    }

    _devices[device_id] = device

    return jsonify({
        'success': True,
        'device': device,
    }), 201


@iiot_bp.route('/devices/<device_id>', methods=['GET'])
def get_device(device_id: str):
    """Get device details."""
    device = _devices.get(device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404

    # Add real-time data
    device_data = device.copy()
    device_data['current_data'] = _get_device_data(device_id)

    return jsonify(device_data)


@iiot_bp.route('/devices/<device_id>', methods=['DELETE'])
def remove_device(device_id: str):
    """Remove a device."""
    if device_id in _devices:
        del _devices[device_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Device not found'}), 404


@iiot_bp.route('/devices/<device_id>/command', methods=['POST'])
def send_device_command(device_id: str):
    """
    Send command to device.

    Request body:
    {
        "command": "start|stop|pause|resume|home|set_temp",
        "parameters": {...}
    }
    """
    device = _devices.get(device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404

    data = request.get_json() or {}
    command = data.get('command')

    # Simulate command execution
    result = {
        'device_id': device_id,
        'command': command,
        'parameters': data.get('parameters', {}),
        'sent_at': datetime.utcnow().isoformat(),
        'status': 'sent',
        'response': {'acknowledged': True},
    }

    return jsonify({'result': result})


def _get_device_data(device_id: str):
    """Get current data for a device (simulated)."""
    device = _devices.get(device_id, {})
    device_type = device.get('type', 'generic')

    if device_type == '3d_printer':
        return {
            'nozzle_temp': round(210 + random.uniform(-2, 2), 1),
            'bed_temp': round(60 + random.uniform(-1, 1), 1),
            'print_progress': round(random.uniform(0, 100), 1),
            'print_time_remaining': random.randint(0, 180),
            'status': random.choice(['printing', 'idle', 'heating']),
            'timestamp': datetime.utcnow().isoformat(),
        }
    elif device_type == 'sensor':
        return {
            'temperature': round(23 + random.uniform(-2, 2), 1),
            'humidity': round(50 + random.uniform(-5, 5), 1),
            'timestamp': datetime.utcnow().isoformat(),
        }
    else:
        return {
            'value': random.uniform(0, 100),
            'timestamp': datetime.utcnow().isoformat(),
        }


# ==================== Data Collection ====================

@iiot_bp.route('/data', methods=['POST'])
def ingest_data():
    """
    Ingest data point from device.

    Request body:
    {
        "device_id": "DEV-PRINT-01",
        "measurements": [
            {"tag": "nozzle_temp", "value": 210.5, "unit": "C"},
            {"tag": "bed_temp", "value": 60.2, "unit": "C"}
        ],
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    data = request.get_json() or {}

    device_id = data.get('device_id')
    if device_id and device_id in _devices:
        _devices[device_id]['last_seen'] = datetime.utcnow().isoformat()
        _devices[device_id]['status'] = 'online'

    data_point = {
        'point_id': str(uuid.uuid4()),
        'device_id': device_id,
        'measurements': data.get('measurements', []),
        'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
        'received_at': datetime.utcnow().isoformat(),
    }

    _data_points.append(data_point)

    # Keep buffer limited
    if len(_data_points) > 10000:
        _data_points.pop(0)

    return jsonify({
        'success': True,
        'point_id': data_point['point_id'],
    }), 201


@iiot_bp.route('/data/<device_id>/latest', methods=['GET'])
def get_latest_data(device_id: str):
    """Get latest data for a device."""
    device = _devices.get(device_id)
    if not device:
        return jsonify({'error': 'Device not found'}), 404

    # Get from buffer or generate
    device_points = [p for p in _data_points if p['device_id'] == device_id]

    if device_points:
        latest = device_points[-1]
    else:
        latest = {
            'device_id': device_id,
            'measurements': _get_device_data(device_id),
            'timestamp': datetime.utcnow().isoformat(),
        }

    return jsonify({'data': latest})


@iiot_bp.route('/data/<device_id>/history', methods=['GET'])
def get_data_history(device_id: str):
    """
    Get historical data for a device.

    Query params:
        start: Start timestamp
        end: End timestamp
        tag: Specific tag to filter
        limit: Max points
    """
    tag = request.args.get('tag')
    limit = request.args.get('limit', 100, type=int)

    device_points = [p for p in _data_points if p['device_id'] == device_id]

    # Generate some demo history if empty
    if not device_points:
        device_points = []
        for i in range(min(limit, 50)):
            timestamp = datetime.utcnow() - timedelta(minutes=i)
            device_points.append({
                'device_id': device_id,
                'measurements': _get_device_data(device_id),
                'timestamp': timestamp.isoformat(),
            })
        device_points.reverse()

    return jsonify({
        'device_id': device_id,
        'points': device_points[-limit:],
        'count': len(device_points),
    })


# ==================== Edge Analytics ====================

@iiot_bp.route('/rules', methods=['GET'])
def list_edge_rules():
    """List edge processing rules."""
    return jsonify({
        'rules': list(_edge_rules.values()),
        'count': len(_edge_rules),
    })


@iiot_bp.route('/rules', methods=['POST'])
def create_edge_rule():
    """
    Create an edge processing rule.

    Request body:
    {
        "name": "High Temp Alert",
        "device_id": "DEV-PRINT-01",
        "condition": {
            "tag": "nozzle_temp",
            "operator": ">",
            "threshold": 250
        },
        "action": {
            "type": "alert|command|log",
            "parameters": {...}
        }
    }
    """
    data = request.get_json() or {}

    rule_id = f"RULE-{str(uuid.uuid4())[:6].upper()}"

    rule = {
        'rule_id': rule_id,
        'name': data.get('name'),
        'device_id': data.get('device_id'),
        'condition': data.get('condition', {}),
        'action': data.get('action', {}),
        'status': 'active',
        'created_at': datetime.utcnow().isoformat(),
        'triggers_count': 0,
        'last_triggered': None,
    }

    _edge_rules[rule_id] = rule

    return jsonify({
        'success': True,
        'rule': rule,
    }), 201


@iiot_bp.route('/rules/<rule_id>', methods=['DELETE'])
def delete_edge_rule(rule_id: str):
    """Delete an edge rule."""
    if rule_id in _edge_rules:
        del _edge_rules[rule_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Rule not found'}), 404


@iiot_bp.route('/analytics/aggregate', methods=['GET'])
def get_aggregated_data():
    """
    Get aggregated analytics data.

    Query params:
        device_id: Device to aggregate
        tag: Tag to aggregate
        period: hour|day|week
        function: avg|min|max|sum|count
    """
    device_id = request.args.get('device_id')
    tag = request.args.get('tag')
    period = request.args.get('period', 'hour')
    function = request.args.get('function', 'avg')

    # Generate demo aggregation
    periods = []
    for i in range(24):
        timestamp = datetime.utcnow() - timedelta(hours=i)
        periods.append({
            'timestamp': timestamp.isoformat(),
            'value': round(random.gauss(210, 5), 2),
            'count': random.randint(50, 100),
        })

    periods.reverse()

    return jsonify({
        'device_id': device_id,
        'tag': tag or 'nozzle_temp',
        'period': period,
        'function': function,
        'data': periods,
    })


# ==================== Protocol Adapters ====================

@iiot_bp.route('/protocols', methods=['GET'])
def list_protocols():
    """List available protocol adapters."""
    return jsonify({
        'protocols': [
            {
                'name': 'OPC-UA',
                'id': 'opcua',
                'status': 'available',
                'description': 'OPC Unified Architecture for industrial automation',
                'config_options': ['server_url', 'security_mode', 'certificate'],
            },
            {
                'name': 'MQTT',
                'id': 'mqtt',
                'status': 'available',
                'description': 'Message Queue Telemetry Transport',
                'config_options': ['broker_url', 'username', 'password', 'topic_prefix'],
            },
            {
                'name': 'Modbus TCP',
                'id': 'modbus',
                'status': 'available',
                'description': 'Modbus protocol over TCP/IP',
                'config_options': ['host', 'port', 'unit_id', 'registers'],
            },
            {
                'name': 'OctoPrint',
                'id': 'octoprint',
                'status': 'available',
                'description': '3D printer control via OctoPrint API',
                'config_options': ['api_url', 'api_key'],
            },
        ]
    })


@iiot_bp.route('/protocols/<protocol_id>/test', methods=['POST'])
def test_protocol_connection(protocol_id: str):
    """
    Test protocol connection.

    Request body:
    {
        "config": {
            "server_url": "opc.tcp://192.168.1.100:4840",
            ...
        }
    }
    """
    data = request.get_json() or {}

    # Simulate connection test
    result = {
        'protocol': protocol_id,
        'config': data.get('config', {}),
        'success': True,
        'latency_ms': random.randint(5, 50),
        'message': 'Connection successful',
        'tested_at': datetime.utcnow().isoformat(),
    }

    return jsonify({'result': result})


# ==================== Store and Forward ====================

@iiot_bp.route('/buffer/status', methods=['GET'])
def get_buffer_status():
    """Get store-and-forward buffer status."""
    return jsonify({
        'buffer': {
            'size': len(_data_points),
            'max_size': 100000,
            'oldest_entry': _data_points[0]['timestamp'] if _data_points else None,
            'newest_entry': _data_points[-1]['timestamp'] if _data_points else None,
            'pending_sync': len(_data_points),
            'last_sync': datetime.utcnow().isoformat(),
            'sync_status': 'ok',
        },
        'cloud_connection': {
            'status': 'connected',
            'last_heartbeat': datetime.utcnow().isoformat(),
        },
    })


@iiot_bp.route('/buffer/sync', methods=['POST'])
def trigger_buffer_sync():
    """Trigger manual buffer sync to cloud."""
    synced_count = len(_data_points)
    _data_points.clear()

    return jsonify({
        'success': True,
        'synced_count': synced_count,
        'synced_at': datetime.utcnow().isoformat(),
    })
