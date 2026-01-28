"""
LEGO Factory v3 - WebSocket Service
====================================
Core WebSocket service using Flask-SocketIO for real-time communication.

Namespaces:
- /unity: Unity Digital Twin communication
- /dashboard: Web dashboard updates
- /alarms: Real-time alarm notifications
- /tags: Tag value subscriptions

Rooms:
- scada: SCADA operators
- mes: MES users
- erp: ERP users
- maintenance: Maintenance technicians
- quality: Quality engineers
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from functools import wraps
from threading import Lock

from flask import Flask, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms, disconnect

logger = logging.getLogger(__name__)

# Global SocketIO instance
_socketio: Optional[SocketIO] = None
_socket_lock = Lock()

# Connected clients tracking
_connected_clients: Dict[str, Dict[str, Any]] = {}
_room_memberships: Dict[str, Set[str]] = {}


class ConnectionManager:
    """Manages WebSocket connections and rooms."""

    def __init__(self):
        self._clients: Dict[str, Dict[str, Any]] = {}
        self._rooms: Dict[str, Set[str]] = {
            'scada': set(),
            'mes': set(),
            'erp': set(),
            'maintenance': set(),
            'quality': set(),
            'unity': set(),
            'dashboard': set(),
        }
        self._lock = Lock()
        self._namespace_clients: Dict[str, Set[str]] = {
            '/unity': set(),
            '/dashboard': set(),
            '/alarms': set(),
            '/tags': set(),
        }

    def register_client(
        self,
        sid: str,
        namespace: str,
        user_id: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Register a new client connection."""
        with self._lock:
            client_info = {
                'sid': sid,
                'namespace': namespace,
                'user_id': user_id,
                'connected_at': datetime.utcnow().isoformat(),
                'rooms': set(),
                'metadata': metadata or {},
            }
            self._clients[sid] = client_info

            if namespace in self._namespace_clients:
                self._namespace_clients[namespace].add(sid)

            logger.info(f"Client registered: {sid} on {namespace} (user: {user_id})")
            return client_info

    def unregister_client(self, sid: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Unregister a client connection."""
        with self._lock:
            client_info = self._clients.pop(sid, None)

            if client_info:
                # Remove from all rooms
                for room in client_info.get('rooms', set()):
                    if room in self._rooms:
                        self._rooms[room].discard(sid)

                # Remove from namespace tracking
                if namespace in self._namespace_clients:
                    self._namespace_clients[namespace].discard(sid)

                logger.info(f"Client unregistered: {sid} from {namespace}")

            return client_info

    def join_room(self, sid: str, room: str) -> bool:
        """Add client to a room."""
        with self._lock:
            if sid not in self._clients:
                return False

            if room not in self._rooms:
                self._rooms[room] = set()

            self._rooms[room].add(sid)
            self._clients[sid]['rooms'].add(room)

            logger.debug(f"Client {sid} joined room: {room}")
            return True

    def leave_room(self, sid: str, room: str) -> bool:
        """Remove client from a room."""
        with self._lock:
            if sid not in self._clients:
                return False

            if room in self._rooms:
                self._rooms[room].discard(sid)

            if sid in self._clients:
                self._clients[sid]['rooms'].discard(room)

            logger.debug(f"Client {sid} left room: {room}")
            return True

    def get_client(self, sid: str) -> Optional[Dict[str, Any]]:
        """Get client information."""
        return self._clients.get(sid)

    def get_room_clients(self, room: str) -> Set[str]:
        """Get all clients in a room."""
        return self._rooms.get(room, set()).copy()

    def get_namespace_clients(self, namespace: str) -> Set[str]:
        """Get all clients connected to a namespace."""
        return self._namespace_clients.get(namespace, set()).copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        with self._lock:
            return {
                'total_clients': len(self._clients),
                'clients_by_namespace': {
                    ns: len(clients) for ns, clients in self._namespace_clients.items()
                },
                'clients_by_room': {
                    room: len(clients) for room, clients in self._rooms.items()
                },
            }


# Global connection manager
connection_manager = ConnectionManager()


def init_socketio(
    app: Flask,
    async_mode: str = 'eventlet',
    cors_allowed_origins: str = "*",
    ping_timeout: int = 60,
    ping_interval: int = 25,
    max_http_buffer_size: int = 1000000,
    **kwargs
) -> SocketIO:
    """
    Initialize SocketIO with the Flask application.

    Args:
        app: Flask application instance
        async_mode: Async mode (eventlet, gevent, or threading)
        cors_allowed_origins: CORS allowed origins
        ping_timeout: Ping timeout in seconds
        ping_interval: Ping interval in seconds
        max_http_buffer_size: Maximum HTTP buffer size
        **kwargs: Additional SocketIO configuration

    Returns:
        Configured SocketIO instance
    """
    global _socketio

    with _socket_lock:
        if _socketio is not None:
            logger.warning("SocketIO already initialized, returning existing instance")
            return _socketio

        _socketio = SocketIO(
            app,
            async_mode=async_mode,
            cors_allowed_origins=cors_allowed_origins,
            ping_timeout=ping_timeout,
            ping_interval=ping_interval,
            max_http_buffer_size=max_http_buffer_size,
            logger=True,
            engineio_logger=False,
            **kwargs
        )

        # Register default namespace handlers
        _register_default_handlers(_socketio)

        logger.info(f"SocketIO initialized with async_mode={async_mode}")
        return _socketio


def get_socketio() -> Optional[SocketIO]:
    """Get the global SocketIO instance."""
    return _socketio


def _register_default_handlers(socketio: SocketIO):
    """Register default event handlers on the main namespace."""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection to default namespace."""
        sid = request.sid
        user_id = session.get('user_id')

        connection_manager.register_client(
            sid=sid,
            namespace='/',
            user_id=user_id,
            metadata={'ip': request.remote_addr}
        )

        emit('connection_ack', {
            'status': 'connected',
            'sid': sid,
            'timestamp': datetime.utcnow().isoformat(),
        })

        logger.info(f"Client connected: {sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection from default namespace."""
        sid = request.sid
        connection_manager.unregister_client(sid, '/')
        logger.info(f"Client disconnected: {sid}")

    @socketio.on('join')
    def handle_join(data):
        """Handle room join request."""
        sid = request.sid
        room = data.get('room')

        if not room:
            emit('error', {'message': 'Room name required'})
            return

        join_room(room)
        connection_manager.join_room(sid, room)

        emit('room_joined', {
            'room': room,
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Notify others in room
        emit('user_joined', {
            'sid': sid,
            'room': room,
            'timestamp': datetime.utcnow().isoformat(),
        }, room=room, include_self=False)

    @socketio.on('leave')
    def handle_leave(data):
        """Handle room leave request."""
        sid = request.sid
        room = data.get('room')

        if not room:
            emit('error', {'message': 'Room name required'})
            return

        leave_room(room)
        connection_manager.leave_room(sid, room)

        emit('room_left', {
            'room': room,
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Notify others in room
        emit('user_left', {
            'sid': sid,
            'room': room,
            'timestamp': datetime.utcnow().isoformat(),
        }, room=room)

    @socketio.on('ping')
    def handle_ping():
        """Handle ping request."""
        emit('pong', {'timestamp': datetime.utcnow().isoformat()})

    @socketio.on('get_stats')
    def handle_get_stats():
        """Handle stats request."""
        stats = connection_manager.get_stats()
        emit('stats', stats)

    @socketio.on_error_default
    def default_error_handler(e):
        """Handle errors."""
        logger.error(f"SocketIO error: {e}")
        emit('error', {'message': str(e)})


def register_namespaces(socketio: SocketIO):
    """
    Register all WebSocket namespaces.

    This should be called after init_socketio to register
    the specialized namespace handlers.
    """
    from services.websocket.unity_socket import UnityNamespace
    from services.websocket.dashboard_socket import DashboardNamespace
    from services.websocket.alarm_socket import AlarmNamespace
    from services.websocket.tag_socket import TagNamespace

    # Register namespace handlers
    socketio.on_namespace(UnityNamespace('/unity'))
    socketio.on_namespace(DashboardNamespace('/dashboard'))
    socketio.on_namespace(AlarmNamespace('/alarms'))
    socketio.on_namespace(TagNamespace('/tags'))

    logger.info("Registered namespaces: /unity, /dashboard, /alarms, /tags")


def emit_to_room(
    event: str,
    data: Dict[str, Any],
    room: str,
    namespace: str = '/',
    skip_sid: Optional[str] = None
):
    """
    Emit an event to all clients in a room.

    Args:
        event: Event name
        data: Event data
        room: Room name
        namespace: Namespace (default: /)
        skip_sid: SID to skip (optional)
    """
    if _socketio is None:
        logger.warning("SocketIO not initialized, cannot emit")
        return

    try:
        _socketio.emit(
            event,
            data,
            room=room,
            namespace=namespace,
            skip_sid=skip_sid
        )
        logger.debug(f"Emitted {event} to room {room} on {namespace}")
    except Exception as e:
        logger.error(f"Error emitting to room: {e}")


def emit_to_namespace(
    event: str,
    data: Dict[str, Any],
    namespace: str = '/',
    skip_sid: Optional[str] = None
):
    """
    Emit an event to all clients on a namespace.

    Args:
        event: Event name
        data: Event data
        namespace: Namespace
        skip_sid: SID to skip (optional)
    """
    if _socketio is None:
        logger.warning("SocketIO not initialized, cannot emit")
        return

    try:
        _socketio.emit(
            event,
            data,
            namespace=namespace,
            skip_sid=skip_sid
        )
        logger.debug(f"Emitted {event} to namespace {namespace}")
    except Exception as e:
        logger.error(f"Error emitting to namespace: {e}")


def broadcast_event(
    event: str,
    data: Dict[str, Any],
    namespaces: List[str] = None
):
    """
    Broadcast an event to multiple namespaces.

    Args:
        event: Event name
        data: Event data
        namespaces: List of namespaces (default: all)
    """
    if _socketio is None:
        logger.warning("SocketIO not initialized, cannot broadcast")
        return

    namespaces = namespaces or ['/', '/unity', '/dashboard', '/alarms', '/tags']

    for namespace in namespaces:
        try:
            _socketio.emit(event, data, namespace=namespace)
        except Exception as e:
            logger.error(f"Error broadcasting to {namespace}: {e}")

    logger.debug(f"Broadcast {event} to namespaces: {namespaces}")


def emit_to_client(
    event: str,
    data: Dict[str, Any],
    sid: str,
    namespace: str = '/'
):
    """
    Emit an event to a specific client.

    Args:
        event: Event name
        data: Event data
        sid: Client session ID
        namespace: Namespace
    """
    if _socketio is None:
        logger.warning("SocketIO not initialized, cannot emit")
        return

    try:
        _socketio.emit(event, data, room=sid, namespace=namespace)
        logger.debug(f"Emitted {event} to client {sid}")
    except Exception as e:
        logger.error(f"Error emitting to client: {e}")


def disconnect_client(sid: str, namespace: str = '/'):
    """
    Disconnect a specific client.

    Args:
        sid: Client session ID
        namespace: Namespace
    """
    if _socketio is None:
        logger.warning("SocketIO not initialized")
        return

    try:
        _socketio.server.disconnect(sid, namespace=namespace)
        logger.info(f"Disconnected client: {sid} from {namespace}")
    except Exception as e:
        logger.error(f"Error disconnecting client: {e}")


def require_auth(f):
    """
    Decorator to require authentication for SocketIO events.

    Usage:
        @socketio.on('my_event')
        @require_auth
        def handle_my_event(data):
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check session for user authentication
        user_id = session.get('user_id')

        if not user_id:
            emit('error', {
                'code': 'AUTH_REQUIRED',
                'message': 'Authentication required'
            })
            return

        return f(*args, **kwargs)

    return decorated


def require_room(room_name: str):
    """
    Decorator to require room membership for SocketIO events.

    Usage:
        @socketio.on('scada_event')
        @require_room('scada')
        def handle_scada_event(data):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            sid = request.sid
            client = connection_manager.get_client(sid)

            if not client or room_name not in client.get('rooms', set()):
                emit('error', {
                    'code': 'ROOM_REQUIRED',
                    'message': f'Must be member of room: {room_name}'
                })
                return

            return f(*args, **kwargs)

        return decorated
    return decorator


# Convenience functions for common operations
def notify_scada_users(event: str, data: Dict[str, Any]):
    """Notify all SCADA operators."""
    emit_to_room(event, data, 'scada')


def notify_mes_users(event: str, data: Dict[str, Any]):
    """Notify all MES users."""
    emit_to_room(event, data, 'mes')


def notify_maintenance(event: str, data: Dict[str, Any]):
    """Notify maintenance technicians."""
    emit_to_room(event, data, 'maintenance')


def notify_quality(event: str, data: Dict[str, Any]):
    """Notify quality engineers."""
    emit_to_room(event, data, 'quality')
