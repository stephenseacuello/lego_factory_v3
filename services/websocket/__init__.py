"""
LEGO Factory v3 - WebSocket Services
=====================================
Real-time WebSocket communication using Flask-SocketIO.
"""

from services.websocket.socket_service import (
    init_socketio,
    get_socketio,
    register_namespaces,
    emit_to_room,
    emit_to_namespace,
    broadcast_event,
)

def emit_event(event: str, data: dict = None, namespace: str = None, room: str = None):
    """Emit a WebSocket event. Convenience wrapper used by services."""
    try:
        if room:
            emit_to_room(room, event, data or {}, namespace=namespace)
        elif namespace:
            emit_to_namespace(namespace, event, data or {})
        else:
            broadcast_event(event, data or {})
    except Exception:
        pass  # WebSocket not available — non-critical


__all__ = [
    'init_socketio',
    'get_socketio',
    'register_namespaces',
    'emit_to_room',
    'emit_to_namespace',
    'broadcast_event',
    'emit_event',
]
