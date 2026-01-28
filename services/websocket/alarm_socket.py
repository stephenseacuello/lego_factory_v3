"""
LEGO Factory v3 - Alarm WebSocket Namespace
============================================
Namespace handler for real-time alarm notifications.

Events (Server -> Client):
- alarm_new: New alarm activated
- alarm_ack: Alarm acknowledged
- alarm_clear: Alarm cleared
- alarm_shelved: Alarm shelved
- alarm_unshelved: Alarm unshelved
- alarm_summary: Alarm summary update

Events (Client -> Server):
- subscribe_priority: Subscribe to alarms by priority
- unsubscribe_priority: Unsubscribe from priority level
- subscribe_area: Subscribe to alarms in area
- acknowledge_alarm: Acknowledge an alarm
- shelve_alarm: Shelve an alarm
- request_active_alarms: Request all active alarms
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Set, List

from flask import request, session
from flask_socketio import Namespace, emit, join_room, leave_room

from services.websocket.socket_service import connection_manager

logger = logging.getLogger(__name__)


# Priority levels (ISA-18.2 compliant)
PRIORITY_LEVELS = {
    1: 'emergency',
    2: 'high',
    3: 'medium',
    4: 'low',
    5: 'diagnostic',
}


class AlarmNamespace(Namespace):
    """
    WebSocket namespace for real-time alarm notifications.

    Provides ISA-18.2 compliant alarm management with:
    - Priority-based filtering
    - Area-based subscriptions
    - Acknowledgment workflow
    - Shelving support
    """

    def __init__(self, namespace: str = '/alarms'):
        super().__init__(namespace)
        # Track priority subscriptions per client
        self._priority_subscriptions: Dict[str, Set[int]] = {}
        # Track area subscriptions per client
        self._area_subscriptions: Dict[str, Set[str]] = {}
        # Alarm client metadata
        self._alarm_clients: Dict[str, Dict[str, Any]] = {}

    def on_connect(self):
        """Handle alarm client connection."""
        sid = request.sid
        user_id = session.get('user_id')
        user_role = session.get('role', 'viewer')

        # Register with connection manager
        connection_manager.register_client(
            sid=sid,
            namespace='/alarms',
            user_id=user_id,
            metadata={
                'ip': request.remote_addr,
                'client_type': 'alarm',
                'role': user_role,
            }
        )

        # Initialize subscriptions with default (all priorities)
        self._priority_subscriptions[sid] = {1, 2, 3, 4, 5}
        self._area_subscriptions[sid] = set()

        # Store alarm-specific metadata
        self._alarm_clients[sid] = {
            'user_id': user_id,
            'role': user_role,
            'connected_at': datetime.utcnow().isoformat(),
            'can_acknowledge': user_role in ['operator', 'supervisor', 'admin'],
            'can_shelve': user_role in ['supervisor', 'admin'],
        }

        # Send connection acknowledgment
        emit('connection_ack', {
            'status': 'connected',
            'sid': sid,
            'namespace': '/alarms',
            'permissions': {
                'can_acknowledge': self._alarm_clients[sid]['can_acknowledge'],
                'can_shelve': self._alarm_clients[sid]['can_shelve'],
            },
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Auto-join alarm room
        join_room('alarms')
        connection_manager.join_room(sid, 'alarms')

        # Auto-join priority rooms (all by default)
        for priority in range(1, 6):
            join_room(f"priority:{priority}")

        # Send current alarm summary
        self._send_alarm_summary(sid)

        logger.info(f"Alarm client connected: {sid} (role: {user_role})")

    def on_disconnect(self):
        """Handle alarm client disconnection."""
        sid = request.sid

        # Clean up subscriptions
        self._priority_subscriptions.pop(sid, None)
        self._area_subscriptions.pop(sid, None)
        self._alarm_clients.pop(sid, None)

        # Unregister from connection manager
        connection_manager.unregister_client(sid, '/alarms')

        logger.info(f"Alarm client disconnected: {sid}")

    def on_subscribe_priority(self, data: Dict[str, Any]):
        """
        Subscribe to alarms by priority level.

        Args:
            data: {
                'priorities': list of priority levels (1-5),
                'min_priority': int (optional, subscribe to this and higher),
            }
        """
        sid = request.sid

        if sid not in self._priority_subscriptions:
            self._priority_subscriptions[sid] = set()

        priorities = data.get('priorities', [])
        min_priority = data.get('min_priority')

        if min_priority:
            # Subscribe to min_priority and higher (lower numbers = higher priority)
            priorities = list(range(1, min_priority + 1))

        for priority in priorities:
            if 1 <= priority <= 5:
                self._priority_subscriptions[sid].add(priority)
                join_room(f"priority:{priority}")

        emit('subscribe_priority_ack', {
            'priorities': list(self._priority_subscriptions[sid]),
            'subscribed': True,
        })

        logger.debug(f"Client {sid} subscribed to priorities: {priorities}")

    def on_unsubscribe_priority(self, data: Dict[str, Any]):
        """
        Unsubscribe from priority levels.

        Args:
            data: {
                'priorities': list of priority levels to unsubscribe,
            }
        """
        sid = request.sid

        if sid not in self._priority_subscriptions:
            return

        priorities = data.get('priorities', [])

        for priority in priorities:
            self._priority_subscriptions[sid].discard(priority)
            leave_room(f"priority:{priority}")

        emit('unsubscribe_priority_ack', {
            'priorities': list(self._priority_subscriptions[sid]),
        })

    def on_subscribe_area(self, data: Dict[str, Any]):
        """
        Subscribe to alarms in a specific area.

        Args:
            data: {
                'area': str or list of areas,
            }
        """
        sid = request.sid

        if sid not in self._area_subscriptions:
            self._area_subscriptions[sid] = set()

        areas = data.get('area', [])
        if isinstance(areas, str):
            areas = [areas]

        for area in areas:
            self._area_subscriptions[sid].add(area)
            join_room(f"alarm_area:{area}")

        emit('subscribe_area_ack', {
            'areas': list(self._area_subscriptions[sid]),
            'subscribed': True,
        })

        logger.debug(f"Client {sid} subscribed to alarm areas: {areas}")

    def on_acknowledge_alarm(self, data: Dict[str, Any]):
        """
        Acknowledge an alarm.

        Args:
            data: {
                'alarm_id': str,
                'notes': str (optional),
            }
        """
        sid = request.sid
        client = self._alarm_clients.get(sid, {})

        if not client.get('can_acknowledge'):
            emit('error', {
                'code': 'PERMISSION_DENIED',
                'message': 'Not authorized to acknowledge alarms',
            })
            return

        alarm_id = data.get('alarm_id')
        if not alarm_id:
            emit('error', {'message': 'alarm_id required'})
            return

        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                user_id = client.get('user_id', 'unknown')
                notes = data.get('notes')

                result = service.acknowledge(alarm_id, user_id, notes)

                if result:
                    emit('acknowledge_ack', {
                        'alarm_id': alarm_id,
                        'acknowledged': True,
                        'timestamp': datetime.utcnow().isoformat(),
                    })

                    # Broadcast acknowledgment to all clients
                    self.emit_alarm_ack(result, user_id)

                    session.commit()
                else:
                    emit('error', {
                        'code': 'NOT_FOUND',
                        'message': f'Alarm not found: {alarm_id}',
                    })

        except Exception as e:
            logger.error(f"Error acknowledging alarm: {e}")
            emit('error', {
                'code': 'ACK_ERROR',
                'message': str(e),
            })

    def on_acknowledge_all(self, data: Dict[str, Any] = None):
        """
        Acknowledge all active alarms.

        Args:
            data: {
                'priority': int (optional, only ack this priority),
            }
        """
        sid = request.sid
        client = self._alarm_clients.get(sid, {})
        data = data or {}

        if not client.get('can_acknowledge'):
            emit('error', {
                'code': 'PERMISSION_DENIED',
                'message': 'Not authorized to acknowledge alarms',
            })
            return

        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                user_id = client.get('user_id', 'unknown')
                priority = data.get('priority')

                count = service.acknowledge_all(user_id, priority)

                emit('acknowledge_all_ack', {
                    'count': count,
                    'priority': priority,
                    'timestamp': datetime.utcnow().isoformat(),
                })

                session.commit()

                # Broadcast to all clients
                self.emit_alarm_summary_update()

        except Exception as e:
            logger.error(f"Error acknowledging all alarms: {e}")
            emit('error', {
                'code': 'ACK_ERROR',
                'message': str(e),
            })

    def on_shelve_alarm(self, data: Dict[str, Any]):
        """
        Shelve an alarm temporarily.

        Args:
            data: {
                'alarm_id': str,
                'duration_minutes': int,
                'reason': str,
            }
        """
        sid = request.sid
        client = self._alarm_clients.get(sid, {})

        if not client.get('can_shelve'):
            emit('error', {
                'code': 'PERMISSION_DENIED',
                'message': 'Not authorized to shelve alarms',
            })
            return

        alarm_id = data.get('alarm_id')
        duration = data.get('duration_minutes', 30)
        reason = data.get('reason')

        if not alarm_id or not reason:
            emit('error', {'message': 'alarm_id and reason required'})
            return

        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                user_id = client.get('user_id', 'unknown')

                result = service.shelve(alarm_id, user_id, duration, reason)

                if result:
                    emit('shelve_ack', {
                        'alarm_id': alarm_id,
                        'shelved': True,
                        'duration_minutes': duration,
                        'timestamp': datetime.utcnow().isoformat(),
                    })

                    # Broadcast shelving to all clients
                    self.emit_alarm_shelved(result, user_id, duration, reason)

                    session.commit()
                else:
                    emit('error', {
                        'code': 'NOT_FOUND',
                        'message': f'Alarm not found: {alarm_id}',
                    })

        except Exception as e:
            logger.error(f"Error shelving alarm: {e}")
            emit('error', {
                'code': 'SHELVE_ERROR',
                'message': str(e),
            })

    def on_unshelve_alarm(self, data: Dict[str, Any]):
        """
        Remove shelving from an alarm.

        Args:
            data: {
                'alarm_id': str,
            }
        """
        sid = request.sid
        client = self._alarm_clients.get(sid, {})

        if not client.get('can_shelve'):
            emit('error', {
                'code': 'PERMISSION_DENIED',
                'message': 'Not authorized to unshelve alarms',
            })
            return

        alarm_id = data.get('alarm_id')
        if not alarm_id:
            emit('error', {'message': 'alarm_id required'})
            return

        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                user_id = client.get('user_id', 'unknown')

                result = service.unshelve(alarm_id, user_id)

                if result:
                    emit('unshelve_ack', {
                        'alarm_id': alarm_id,
                        'shelved': False,
                        'timestamp': datetime.utcnow().isoformat(),
                    })

                    # Broadcast unshelving to all clients
                    self.emit_alarm_unshelved(result, user_id)

                    session.commit()

        except Exception as e:
            logger.error(f"Error unshelving alarm: {e}")
            emit('error', {
                'code': 'UNSHELVE_ERROR',
                'message': str(e),
            })

    def on_request_active_alarms(self, data: Dict[str, Any] = None):
        """
        Request all active alarms.

        Args:
            data: {
                'priority': int (optional),
                'include_shelved': bool (default: True),
            }
        """
        sid = request.sid
        data = data or {}

        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                priority = data.get('priority')
                include_shelved = data.get('include_shelved', True)

                alarms = service.get_active_alarms(priority, include_shelved)

                emit('active_alarms', {
                    'alarms': alarms,
                    'count': len(alarms),
                    'timestamp': datetime.utcnow().isoformat(),
                })

        except Exception as e:
            logger.error(f"Error getting active alarms: {e}")
            emit('error', {
                'code': 'QUERY_ERROR',
                'message': str(e),
            })

    def on_request_alarm_summary(self):
        """Request alarm summary."""
        sid = request.sid
        self._send_alarm_summary(sid)

    def on_ping(self):
        """Handle ping request."""
        emit('pong', {
            'timestamp': datetime.utcnow().isoformat(),
            'namespace': '/alarms',
        })

    # Helper methods

    def _send_alarm_summary(self, sid: str):
        """Send alarm summary to a specific client."""
        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session

            with get_db_session() as session:
                service = get_alarm_service(session)
                summary = service.get_alarm_summary()

                emit('alarm_summary', {
                    'total_active': summary.total_active,
                    'unacknowledged': summary.unacknowledged,
                    'acknowledged_active': summary.acknowledged_active,
                    'shelved': summary.shelved,
                    'by_priority': summary.by_priority,
                    'timestamp': datetime.utcnow().isoformat(),
                }, room=sid)

        except Exception as e:
            logger.error(f"Error getting alarm summary: {e}")

    # Server-side emission methods

    def emit_alarm_new(self, alarm_data: Dict[str, Any]):
        """
        Emit new alarm notification.

        Args:
            alarm_data: Alarm details including priority
        """
        from flask_socketio import emit as socketio_emit

        priority = alarm_data.get('priority', 3)
        area = alarm_data.get('area')

        notification = {
            'type': 'new',
            'alarm': alarm_data,
            'timestamp': datetime.utcnow().isoformat(),
        }

        # Emit to priority-specific room
        socketio_emit(
            'alarm_new',
            notification,
            room=f"priority:{priority}",
            namespace='/alarms',
        )

        # Emit to area-specific room if applicable
        if area:
            socketio_emit(
                'alarm_new',
                notification,
                room=f"alarm_area:{area}",
                namespace='/alarms',
            )

        # Always emit to general alarms room
        socketio_emit(
            'alarm_new',
            notification,
            room='alarms',
            namespace='/alarms',
        )

        logger.info(f"Emitted new alarm: {alarm_data.get('alarm_id')} (priority: {priority})")

    def emit_alarm_ack(self, alarm_data: Dict[str, Any], user_id: str):
        """
        Emit alarm acknowledgment notification.

        Args:
            alarm_data: Acknowledged alarm data
            user_id: User who acknowledged
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'alarm_ack',
            {
                'alarm': alarm_data,
                'acknowledged_by': user_id,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='alarms',
            namespace='/alarms',
        )

    def emit_alarm_clear(self, alarm_data: Dict[str, Any]):
        """
        Emit alarm cleared notification.

        Args:
            alarm_data: Cleared alarm data
        """
        from flask_socketio import emit as socketio_emit

        priority = alarm_data.get('priority', 3)

        notification = {
            'type': 'clear',
            'alarm': alarm_data,
            'timestamp': datetime.utcnow().isoformat(),
        }

        socketio_emit(
            'alarm_clear',
            notification,
            room=f"priority:{priority}",
            namespace='/alarms',
        )

        socketio_emit(
            'alarm_clear',
            notification,
            room='alarms',
            namespace='/alarms',
        )

        logger.info(f"Emitted alarm clear: {alarm_data.get('alarm_id')}")

    def emit_alarm_shelved(
        self,
        alarm_data: Dict[str, Any],
        user_id: str,
        duration: int,
        reason: str
    ):
        """
        Emit alarm shelved notification.

        Args:
            alarm_data: Shelved alarm data
            user_id: User who shelved
            duration: Shelve duration in minutes
            reason: Shelve reason
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'alarm_shelved',
            {
                'alarm': alarm_data,
                'shelved_by': user_id,
                'duration_minutes': duration,
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='alarms',
            namespace='/alarms',
        )

    def emit_alarm_unshelved(self, alarm_data: Dict[str, Any], user_id: str):
        """
        Emit alarm unshelved notification.

        Args:
            alarm_data: Unshelved alarm data
            user_id: User who unshelved
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'alarm_unshelved',
            {
                'alarm': alarm_data,
                'unshelved_by': user_id,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='alarms',
            namespace='/alarms',
        )

    def emit_alarm_summary_update(self):
        """Emit alarm summary update to all clients."""
        try:
            from services.scada.alarm_management.alarm_service import get_alarm_service
            from config.database import get_db_session
            from flask_socketio import emit as socketio_emit

            with get_db_session() as session:
                service = get_alarm_service(session)
                summary = service.get_alarm_summary()

                socketio_emit(
                    'alarm_summary',
                    {
                        'total_active': summary.total_active,
                        'unacknowledged': summary.unacknowledged,
                        'acknowledged_active': summary.acknowledged_active,
                        'shelved': summary.shelved,
                        'by_priority': summary.by_priority,
                        'timestamp': datetime.utcnow().isoformat(),
                    },
                    room='alarms',
                    namespace='/alarms',
                )

        except Exception as e:
            logger.error(f"Error emitting alarm summary: {e}")


# Global namespace instance
_alarm_namespace: Optional[AlarmNamespace] = None


def get_alarm_namespace() -> Optional[AlarmNamespace]:
    """Get alarm namespace instance."""
    return _alarm_namespace


def set_alarm_namespace(namespace: AlarmNamespace):
    """Set alarm namespace instance."""
    global _alarm_namespace
    _alarm_namespace = namespace


# Convenience functions for emitting events

def emit_alarm_new(alarm_data: Dict[str, Any]):
    """Emit new alarm notification."""
    if _alarm_namespace:
        _alarm_namespace.emit_alarm_new(alarm_data)
    else:
        from services.websocket.socket_service import emit_to_room

        priority = alarm_data.get('priority', 3)
        emit_to_room(
            'alarm_new',
            {'type': 'new', 'alarm': alarm_data, 'timestamp': datetime.utcnow().isoformat()},
            f"priority:{priority}",
            '/alarms'
        )


def emit_alarm_ack(alarm_data: Dict[str, Any], user_id: str):
    """Emit alarm acknowledgment notification."""
    if _alarm_namespace:
        _alarm_namespace.emit_alarm_ack(alarm_data, user_id)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'alarm_ack',
            {'alarm': alarm_data, 'acknowledged_by': user_id, 'timestamp': datetime.utcnow().isoformat()},
            'alarms',
            '/alarms'
        )


def emit_alarm_clear(alarm_data: Dict[str, Any]):
    """Emit alarm cleared notification."""
    if _alarm_namespace:
        _alarm_namespace.emit_alarm_clear(alarm_data)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'alarm_clear',
            {'type': 'clear', 'alarm': alarm_data, 'timestamp': datetime.utcnow().isoformat()},
            'alarms',
            '/alarms'
        )


def emit_alarm_summary():
    """Emit alarm summary update."""
    if _alarm_namespace:
        _alarm_namespace.emit_alarm_summary_update()
