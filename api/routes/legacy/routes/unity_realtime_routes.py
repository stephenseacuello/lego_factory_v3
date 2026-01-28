"""
Unity Real-Time Routes
=======================
WebSocket and binary protocol endpoints for Unity Digital Twin.

Provides:
- WebSocket connection management
- Binary protocol streaming (FlatBuffers)
- Real-time position updates at 60Hz
- Low-latency command handling (<20ms target)

Author: Flask CNC SCADA System
"""

import logging
import time
import uuid
from functools import wraps
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, g

logger = logging.getLogger(__name__)

# Blueprint for Unity real-time routes
unity_realtime_bp = Blueprint(
    'unity_realtime',
    __name__,
    url_prefix='/api/unity/realtime'
)


# =============================================================================
# Lazy Service Imports
# =============================================================================

def get_gateway_service():
    """Lazy import of Unity gateway service."""
    from services.unity_gateway_service import get_unity_gateway_service
    return get_unity_gateway_service()


def get_socketio():
    """Lazy import of SocketIO instance."""
    try:
        from app import socketio
        return socketio
    except ImportError:
        return None


# =============================================================================
# Authentication Decorator
# =============================================================================

def require_unity_auth(f):
    """Decorator to require Unity client authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from config import get_config
        config = get_config()

        # Check if JWT is enabled
        if not getattr(config, 'JWT_ENABLED', False):
            # Development mode - use default client
            g.client_id = request.headers.get('X-Unity-Client-ID', str(uuid.uuid4()))
            g.auth_level = 2  # Default to operator level
            g.user_id = 'dev-user'
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization required'}), 401

        token = auth_header[7:]

        try:
            # Validate JWT token
            from services.auth_service import verify_token, get_user_store
            payload = verify_token(token, "access")

            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401

            # Get user from token
            store = get_user_store()
            user = store.get(payload.get("sub"))

            if not user or not user.active:
                return jsonify({'error': 'User not found or disabled'}), 401

            # Map role to auth level
            role_levels = {'viewer': 1, 'operator': 2, 'supervisor': 3,
                          'maintenance': 3, 'management': 4, 'admin': 5}

            g.client_id = request.headers.get('X-Unity-Client-ID', str(uuid.uuid4()))
            g.auth_level = role_levels.get(user.role, 2)
            g.user_id = user.username
            g.current_user = user

            return f(*args, **kwargs)

        except Exception as e:
            logger.warning(f"Unity auth failed: {e}")
            return jsonify({'error': 'Authentication failed'}), 401

    return decorated


# =============================================================================
# REST Endpoints
# =============================================================================

@unity_realtime_bp.route('/connect', methods=['POST'])
def connect():
    """
    Initialize a Unity client connection.

    Request body:
    {
        "client_id": "optional-client-id",
        "binary_protocol": true,
        "subscriptions": ["machine-1", "machine-2"]
    }

    Response:
    {
        "session_id": "uuid",
        "websocket_url": "wss://...",
        "binary_url": "wss://.../binary",
        "server_time_us": 1234567890
    }
    """
    data = request.get_json() or {}

    client_id = data.get('client_id', str(uuid.uuid4()))
    binary_protocol = data.get('binary_protocol', False)
    subscriptions = data.get('subscriptions', [])

    gateway = get_gateway_service()
    session_id = str(uuid.uuid4())

    # Register client
    from services.unity_gateway_service import CommandAuthLevel
    client = gateway.register_client(
        client_id=client_id,
        session_id=session_id,
        binary_protocol=binary_protocol,
        auth_level=CommandAuthLevel.OPERATOR
    )

    # Subscribe to machines
    for machine_id in subscriptions:
        gateway.subscribe_machine(client_id, machine_id)

    # Build response
    host = request.host
    protocol = 'wss' if request.is_secure else 'ws'

    return jsonify({
        'session_id': session_id,
        'client_id': client_id,
        'websocket_url': f'{protocol}://{host}/ws/unity',
        'binary_url': f'{protocol}://{host}/ws/unity/binary',
        'server_time_us': int(time.time() * 1_000_000),
        'config': {
            'position_rate_hz': gateway.position_rate_hz,
            'kinematics_rate_hz': gateway.kinematics_rate_hz,
            'sensor_rate_hz': gateway.sensor_rate_hz,
            'binary_protocol': binary_protocol
        }
    })


@unity_realtime_bp.route('/disconnect', methods=['POST'])
def disconnect():
    """
    Disconnect a Unity client.

    Request body:
    {
        "client_id": "client-id",
        "session_id": "session-id"
    }
    """
    data = request.get_json() or {}
    client_id = data.get('client_id')

    if not client_id:
        return jsonify({'error': 'client_id required'}), 400

    gateway = get_gateway_service()
    gateway.unregister_client(client_id)

    return jsonify({'status': 'disconnected'})


@unity_realtime_bp.route('/subscribe/<machine_id>', methods=['POST'])
@require_unity_auth
def subscribe(machine_id: str):
    """Subscribe to a machine's real-time updates."""
    gateway = get_gateway_service()
    client_id = g.get('client_id')

    success = gateway.subscribe_machine(client_id, machine_id)

    if success:
        return jsonify({
            'status': 'subscribed',
            'machine_id': machine_id
        })
    else:
        return jsonify({'error': 'Subscription failed'}), 400


@unity_realtime_bp.route('/unsubscribe/<machine_id>', methods=['POST'])
@require_unity_auth
def unsubscribe(machine_id: str):
    """Unsubscribe from a machine's updates."""
    gateway = get_gateway_service()
    client_id = g.get('client_id')

    success = gateway.unsubscribe_machine(client_id, machine_id)

    if success:
        return jsonify({
            'status': 'unsubscribed',
            'machine_id': machine_id
        })
    else:
        return jsonify({'error': 'Unsubscription failed'}), 400


@unity_realtime_bp.route('/state/<machine_id>', methods=['GET'])
def get_state(machine_id: str):
    """
    Get current machine state (polling fallback).

    Query params:
    - predict: Include velocity prediction (default: true)
    - format: 'json' or 'binary' (default: json)
    """
    gateway = get_gateway_service()
    predict = request.args.get('predict', 'true').lower() == 'true'
    fmt = request.args.get('format', 'json')

    cache = gateway.get_machine_state(
        machine_id,
        predict_forward_ms=16 if predict else 0
    )

    if not cache:
        return jsonify({'error': 'Machine not found'}), 404

    if fmt == 'binary':
        binary_data = gateway.create_position_message(machine_id, include_prediction=predict)
        if binary_data:
            return binary_data, 200, {'Content-Type': 'application/octet-stream'}
        return jsonify({'error': 'Binary encoding failed'}), 500

    return jsonify({
        'machine_id': machine_id,
        'position': {
            'x': cache.position.x,
            'y': cache.position.y,
            'z': cache.position.z
        },
        'velocity': {
            'vx': cache.velocity.vx,
            'vy': cache.velocity.vy,
            'vz': cache.velocity.vz
        },
        'timestamp_us': cache.position.timestamp_us,
        'quality_score': cache.quality_score,
        'last_update': cache.last_update
    })


@unity_realtime_bp.route('/command/<machine_id>', methods=['POST'])
@require_unity_auth
def send_command(machine_id: str):
    """
    Send a command to a machine.

    Request body:
    {
        "type": "jog|gcode|spindle|coolant|home|estop",
        "params": {...}
    }

    Jog params: {"axis": "X", "distance": 10.0, "feed_rate": 1000}
    G-code params: {"line": "G1 X10 Y20 F1000"}
    Spindle params: {"rpm": 10000, "direction": "CW"}
    """
    data = request.get_json() or {}
    command_type = data.get('type')
    params = data.get('params', {})

    if not command_type:
        return jsonify({'error': 'Command type required'}), 400

    gateway = get_gateway_service()
    client_id = g.get('client_id')

    # Check rate limit
    if not gateway.check_rate_limit(client_id, f'command:{command_type}', 10):
        return jsonify({'error': 'Rate limit exceeded'}), 429

    # Forward to ROS2 bridge
    try:
        from services.ros2_bridge_service import get_ros2_bridge

        bridge = get_ros2_bridge()

        if command_type == 'jog':
            # Jog command - needs low latency
            result = bridge.jog_machine(
                machine_id,
                params.get('axis', 'X'),
                params.get('distance', 1.0),
                params.get('feed_rate', 1000)
            )
        elif command_type == 'gcode':
            result = bridge.send_gcode(machine_id, params.get('line', ''))
        elif command_type == 'home':
            result = bridge.home_machine(machine_id)
        elif command_type == 'estop':
            result = bridge.emergency_stop(machine_id)
        else:
            return jsonify({'error': f'Unknown command type: {command_type}'}), 400

        return jsonify({
            'status': 'sent',
            'command_type': command_type,
            'machine_id': machine_id,
            'result': result
        })

    except Exception as e:
        logger.exception(f"Command execution failed: {e}")
        return jsonify({'error': str(e)}), 500


@unity_realtime_bp.route('/batch-state', methods=['POST'])
def get_batch_state():
    """
    Get state for multiple machines in one request.

    Request body:
    {
        "machine_ids": ["machine-1", "machine-2"],
        "include_kinematics": false,
        "include_sensors": false
    }
    """
    data = request.get_json() or {}
    machine_ids = data.get('machine_ids', [])

    if not machine_ids:
        return jsonify({'error': 'machine_ids required'}), 400

    gateway = get_gateway_service()
    states = {}

    for machine_id in machine_ids:
        cache = gateway.get_machine_state(machine_id, predict_forward_ms=16)
        if cache:
            states[machine_id] = {
                'position': {
                    'x': cache.position.x,
                    'y': cache.position.y,
                    'z': cache.position.z
                },
                'velocity': {
                    'vx': cache.velocity.vx,
                    'vy': cache.velocity.vy,
                    'vz': cache.velocity.vz
                },
                'quality_score': cache.quality_score
            }

    return jsonify({
        'timestamp_us': int(time.time() * 1_000_000),
        'states': states
    })


@unity_realtime_bp.route('/health', methods=['GET'])
def health():
    """Gateway health check."""
    gateway = get_gateway_service()
    status = gateway.get_status()

    return jsonify({
        'status': 'healthy',
        'gateway': status
    })


# =============================================================================
# SocketIO Events (if available)
# =============================================================================

def register_socketio_events(socketio):
    """Register SocketIO event handlers for Unity real-time communication."""

    @socketio.on('connect', namespace='/unity')
    def handle_connect():
        """Handle Unity client WebSocket connection."""
        client_id = request.args.get('client_id', str(uuid.uuid4()))
        session_id = request.args.get('session_id', str(uuid.uuid4()))

        logger.info(f"Unity WebSocket connected: {client_id}")

        gateway = get_gateway_service()
        from services.unity_gateway_service import CommandAuthLevel

        gateway.register_client(
            client_id=client_id,
            session_id=session_id,
            binary_protocol=False,
            auth_level=CommandAuthLevel.OPERATOR
        )

        # Join room for this client
        from flask_socketio import join_room
        join_room(f'unity:{client_id}')

        socketio.emit('connected', {
            'client_id': client_id,
            'session_id': session_id,
            'server_time_us': int(time.time() * 1_000_000)
        }, namespace='/unity')

    @socketio.on('disconnect', namespace='/unity')
    def handle_disconnect():
        """Handle Unity client WebSocket disconnection."""
        client_id = request.args.get('client_id')
        if client_id:
            gateway = get_gateway_service()
            gateway.unregister_client(client_id)
            logger.info(f"Unity WebSocket disconnected: {client_id}")

    @socketio.on('subscribe', namespace='/unity')
    def handle_subscribe(data):
        """Handle machine subscription request."""
        client_id = data.get('client_id')
        machine_id = data.get('machine_id')

        if client_id and machine_id:
            gateway = get_gateway_service()
            success = gateway.subscribe_machine(client_id, machine_id)

            from flask_socketio import join_room
            join_room(f'machine:{machine_id}')

            socketio.emit('subscribed', {
                'machine_id': machine_id,
                'success': success
            }, namespace='/unity')

    @socketio.on('unsubscribe', namespace='/unity')
    def handle_unsubscribe(data):
        """Handle machine unsubscription request."""
        client_id = data.get('client_id')
        machine_id = data.get('machine_id')

        if client_id and machine_id:
            gateway = get_gateway_service()
            success = gateway.unsubscribe_machine(client_id, machine_id)

            from flask_socketio import leave_room
            leave_room(f'machine:{machine_id}')

            socketio.emit('unsubscribed', {
                'machine_id': machine_id,
                'success': success
            }, namespace='/unity')

    @socketio.on('command', namespace='/unity')
    def handle_command(data):
        """Handle command from Unity client."""
        machine_id = data.get('machine_id')
        command_type = data.get('type')
        params = data.get('params', {})

        if not machine_id or not command_type:
            socketio.emit('error', {
                'message': 'machine_id and type required'
            }, namespace='/unity')
            return

        try:
            from services.ros2_bridge_service import get_ros2_bridge
            bridge = get_ros2_bridge()

            if command_type == 'jog':
                result = bridge.jog_machine(
                    machine_id,
                    params.get('axis', 'X'),
                    params.get('distance', 1.0),
                    params.get('feed_rate', 1000)
                )
            elif command_type == 'estop':
                result = bridge.emergency_stop(machine_id)
            else:
                result = {'error': f'Unknown command: {command_type}'}

            socketio.emit('command_result', {
                'machine_id': machine_id,
                'command_type': command_type,
                'result': result
            }, namespace='/unity')

        except Exception as e:
            logger.exception(f"Command failed: {e}")
            socketio.emit('error', {
                'message': str(e)
            }, namespace='/unity')

    @socketio.on('ping', namespace='/unity')
    def handle_ping():
        """Handle ping for latency measurement."""
        socketio.emit('pong', {
            'server_time_us': int(time.time() * 1_000_000)
        }, namespace='/unity')


# =============================================================================
# Background State Broadcaster
# =============================================================================

def start_state_broadcaster(socketio, interval_ms: int = 16):
    """
    Start background task to broadcast state updates to Unity clients.

    Runs at ~60Hz (16ms interval) for smooth animation.
    """
    import eventlet

    def broadcast_loop():
        gateway = get_gateway_service()

        while True:
            try:
                # Get all cached machine states
                with gateway.states_lock:
                    machines = list(gateway.machine_states.keys())

                # Broadcast to each machine's subscribers
                for machine_id in machines:
                    cache = gateway.get_machine_state(machine_id, predict_forward_ms=16)
                    if cache and cache.quality_score > 0.3:
                        state_data = {
                            'machine_id': machine_id,
                            'x': cache.position.x,
                            'y': cache.position.y,
                            'z': cache.position.z,
                            'vx': cache.velocity.vx,
                            'vy': cache.velocity.vy,
                            'vz': cache.velocity.vz,
                            'quality': cache.quality_score,
                            't': cache.position.timestamp_us
                        }
                        socketio.emit(
                            'position',
                            state_data,
                            room=f'machine:{machine_id}',
                            namespace='/unity'
                        )

            except Exception as e:
                logger.debug(f"Broadcast error: {e}")

            eventlet.sleep(interval_ms / 1000)

    eventlet.spawn(broadcast_loop)
    logger.info(f"State broadcaster started at {1000/interval_ms:.1f}Hz")
