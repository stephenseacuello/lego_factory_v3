"""
LEGO Factory v3 - Tag WebSocket Namespace
==========================================
Namespace handler for real-time tag value subscriptions.

Events (Server -> Client):
- tag_value: Single tag value update
- tag_values: Multiple tag values update (batch)
- tag_quality_change: Tag quality changed
- tag_config_change: Tag configuration changed

Events (Client -> Server):
- subscribe: Subscribe to tag(s)
- unsubscribe: Unsubscribe from tag(s)
- write_value: Write value to tag
- request_value: Request current value
- request_history: Request historical values
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set, List

from flask import request, session
from flask_socketio import Namespace, emit, join_room, leave_room

from services.websocket.socket_service import connection_manager

logger = logging.getLogger(__name__)


class TagNamespace(Namespace):
    """
    WebSocket namespace for real-time tag value updates.

    Provides efficient tag value subscriptions with:
    - Individual tag subscriptions
    - Group subscriptions
    - Quality-aware updates
    - Rate limiting
    """

    def __init__(self, namespace: str = '/tags'):
        super().__init__(namespace)
        # Track tag subscriptions per client
        self._tag_subscriptions: Dict[str, Set[str]] = {}
        # Track update rates per client (for throttling)
        self._update_rates: Dict[str, Dict[str, datetime]] = {}
        # Default minimum update interval (ms)
        self._min_update_interval = 100
        # Tag client metadata
        self._tag_clients: Dict[str, Dict[str, Any]] = {}

    def on_connect(self):
        """Handle tag client connection."""
        sid = request.sid
        user_id = session.get('user_id')
        user_role = session.get('role', 'viewer')

        # Register with connection manager
        connection_manager.register_client(
            sid=sid,
            namespace='/tags',
            user_id=user_id,
            metadata={
                'ip': request.remote_addr,
                'client_type': 'tag',
                'role': user_role,
            }
        )

        # Initialize subscriptions
        self._tag_subscriptions[sid] = set()
        self._update_rates[sid] = {}

        # Store tag-specific metadata
        self._tag_clients[sid] = {
            'user_id': user_id,
            'role': user_role,
            'connected_at': datetime.utcnow().isoformat(),
            'can_write': user_role in ['operator', 'engineer', 'admin'],
            'update_interval': self._min_update_interval,
        }

        # Send connection acknowledgment
        emit('connection_ack', {
            'status': 'connected',
            'sid': sid,
            'namespace': '/tags',
            'permissions': {
                'can_write': self._tag_clients[sid]['can_write'],
            },
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Auto-join tags room
        join_room('tags')
        connection_manager.join_room(sid, 'tags')

        logger.info(f"Tag client connected: {sid}")

    def on_disconnect(self):
        """Handle tag client disconnection."""
        sid = request.sid

        # Clean up subscriptions
        self._tag_subscriptions.pop(sid, None)
        self._update_rates.pop(sid, None)
        self._tag_clients.pop(sid, None)

        # Unregister from connection manager
        connection_manager.unregister_client(sid, '/tags')

        logger.info(f"Tag client disconnected: {sid}")

    def on_subscribe(self, data: Dict[str, Any]):
        """
        Subscribe to tag value updates.

        Args:
            data: {
                'tag_id': str or list,
                'update_interval': int (optional, ms),
                'include_quality': bool (optional),
            }
        """
        sid = request.sid

        if sid not in self._tag_subscriptions:
            self._tag_subscriptions[sid] = set()

        tag_ids = data.get('tag_id', [])
        if isinstance(tag_ids, str):
            tag_ids = [tag_ids]

        update_interval = data.get('update_interval', self._min_update_interval)
        include_quality = data.get('include_quality', True)

        # Store client preferences
        if sid in self._tag_clients:
            self._tag_clients[sid]['update_interval'] = max(update_interval, self._min_update_interval)
            self._tag_clients[sid]['include_quality'] = include_quality

        for tag_id in tag_ids:
            self._tag_subscriptions[sid].add(tag_id)
            join_room(f"tag:{tag_id}")

        emit('subscribe_ack', {
            'tag_ids': tag_ids,
            'subscribed': True,
            'update_interval': self._tag_clients.get(sid, {}).get('update_interval', self._min_update_interval),
            'total_subscriptions': len(self._tag_subscriptions[sid]),
        })

        # Send current values
        self._send_current_values(sid, tag_ids)

        logger.debug(f"Client {sid} subscribed to tags: {tag_ids}")

    def on_unsubscribe(self, data: Dict[str, Any]):
        """
        Unsubscribe from tag value updates.

        Args:
            data: {
                'tag_id': str or list,
                'all': bool (optional, unsubscribe from all)
            }
        """
        sid = request.sid

        if sid not in self._tag_subscriptions:
            return

        if data.get('all'):
            for tag_id in self._tag_subscriptions[sid]:
                leave_room(f"tag:{tag_id}")
            self._tag_subscriptions[sid] = set()
        else:
            tag_ids = data.get('tag_id', [])
            if isinstance(tag_ids, str):
                tag_ids = [tag_ids]

            for tag_id in tag_ids:
                self._tag_subscriptions[sid].discard(tag_id)
                leave_room(f"tag:{tag_id}")

        emit('unsubscribe_ack', {
            'subscribed': False,
            'total_subscriptions': len(self._tag_subscriptions[sid]),
        })

    def on_write_value(self, data: Dict[str, Any]):
        """
        Write value to a tag.

        Args:
            data: {
                'tag_id': str,
                'value': Any,
            }
        """
        sid = request.sid
        client = self._tag_clients.get(sid, {})

        if not client.get('can_write'):
            emit('error', {
                'code': 'PERMISSION_DENIED',
                'message': 'Not authorized to write tag values',
            })
            return

        tag_id = data.get('tag_id')
        value = data.get('value')

        if not tag_id:
            emit('error', {'message': 'tag_id required'})
            return

        try:
            from services.scada.tag_management.tag_service import write_tag_value
            import asyncio

            # Write value to tag cache
            loop = asyncio.new_event_loop()
            loop.run_until_complete(write_tag_value(tag_id, value))
            loop.close()

            emit('write_ack', {
                'tag_id': tag_id,
                'value': value,
                'success': True,
                'timestamp': datetime.utcnow().isoformat(),
            })

            # Broadcast to other subscribers
            self.emit_tag_value(tag_id, value, skip_sid=sid)

            logger.info(f"Tag {tag_id} written by {client.get('user_id', 'unknown')}: {value}")

        except Exception as e:
            logger.error(f"Error writing tag value: {e}")
            emit('error', {
                'code': 'WRITE_ERROR',
                'message': str(e),
            })

    def on_request_value(self, data: Dict[str, Any]):
        """
        Request current tag value.

        Args:
            data: {
                'tag_id': str or list,
            }
        """
        sid = request.sid

        tag_ids = data.get('tag_id', [])
        if isinstance(tag_ids, str):
            tag_ids = [tag_ids]

        self._send_current_values(sid, tag_ids)

    def on_request_history(self, data: Dict[str, Any]):
        """
        Request historical tag values.

        Args:
            data: {
                'tag_id': str,
                'start_time': str (ISO format),
                'end_time': str (ISO format, optional),
                'limit': int (optional),
            }
        """
        sid = request.sid

        tag_id = data.get('tag_id')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        limit = data.get('limit', 1000)

        if not tag_id or not start_time:
            emit('error', {'message': 'tag_id and start_time required'})
            return

        try:
            from services.scada.historian.historian_service import get_historian_service
            from config.database import get_db_session

            # Parse times
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00')) if end_time else datetime.utcnow()

            with get_db_session() as session:
                service = get_historian_service(session)
                history = service.query_raw(tag_id, start_dt, end_dt, limit)

                emit('tag_history', {
                    'tag_id': tag_id,
                    'values': history,
                    'start_time': start_dt.isoformat(),
                    'end_time': end_dt.isoformat(),
                    'count': len(history),
                })

        except Exception as e:
            logger.error(f"Error getting tag history: {e}")
            emit('error', {
                'code': 'HISTORY_ERROR',
                'message': str(e),
            })

    def on_set_update_interval(self, data: Dict[str, Any]):
        """
        Set update interval for this client.

        Args:
            data: {
                'interval': int (ms),
            }
        """
        sid = request.sid
        interval = data.get('interval', self._min_update_interval)

        # Enforce minimum interval
        interval = max(interval, self._min_update_interval)

        if sid in self._tag_clients:
            self._tag_clients[sid]['update_interval'] = interval

        emit('update_interval_set', {
            'interval': interval,
        })

    def on_ping(self):
        """Handle ping request."""
        emit('pong', {
            'timestamp': datetime.utcnow().isoformat(),
            'namespace': '/tags',
        })

    # Helper methods

    def _send_current_values(self, sid: str, tag_ids: List[str]):
        """Send current values for specified tags."""
        try:
            from services.scada.tag_management.tag_service import tag_cache
            import asyncio

            loop = asyncio.new_event_loop()
            values = loop.run_until_complete(tag_cache.get_many(tag_ids))
            loop.close()

            if values:
                tag_values = {
                    tag_id: {
                        'value': tv.value,
                        'quality': tv.quality,
                        'timestamp': tv.timestamp.isoformat() if tv.timestamp else None,
                        'eng_units': tv.eng_units,
                    }
                    for tag_id, tv in values.items()
                }

                emit('tag_values', {
                    'values': tag_values,
                    'timestamp': datetime.utcnow().isoformat(),
                }, room=sid)

        except Exception as e:
            logger.error(f"Error sending current tag values: {e}")

    # Server-side emission methods

    def emit_tag_value(
        self,
        tag_id: str,
        value: Any,
        quality: int = 192,
        timestamp: datetime = None,
        skip_sid: Optional[str] = None
    ):
        """
        Emit single tag value update.

        Args:
            tag_id: Tag identifier
            value: Current value
            quality: OPC quality code
            timestamp: Value timestamp
            skip_sid: Client to skip (optional)
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'tag_value',
            {
                'tag_id': tag_id,
                'value': value,
                'quality': quality,
                'timestamp': (timestamp or datetime.utcnow()).isoformat(),
            },
            room=f"tag:{tag_id}",
            namespace='/tags',
            skip_sid=skip_sid,
        )

    def emit_tag_values(
        self,
        values: Dict[str, Dict[str, Any]],
        skip_sid: Optional[str] = None
    ):
        """
        Emit batch tag value updates.

        Args:
            values: Dict of tag_id -> {value, quality, timestamp}
            skip_sid: Client to skip (optional)
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'tag_values',
            {
                'values': values,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='tags',
            namespace='/tags',
            skip_sid=skip_sid,
        )

    def emit_tag_quality_change(self, tag_id: str, quality: int, previous_quality: int):
        """
        Emit tag quality change notification.

        Args:
            tag_id: Tag identifier
            quality: New quality code
            previous_quality: Previous quality code
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'tag_quality_change',
            {
                'tag_id': tag_id,
                'quality': quality,
                'previous_quality': previous_quality,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room=f"tag:{tag_id}",
            namespace='/tags',
        )


# Global namespace instance
_tag_namespace: Optional[TagNamespace] = None


def get_tag_namespace() -> Optional[TagNamespace]:
    """Get tag namespace instance."""
    return _tag_namespace


def set_tag_namespace(namespace: TagNamespace):
    """Set tag namespace instance."""
    global _tag_namespace
    _tag_namespace = namespace


# Convenience functions for emitting events

def emit_tag_value(
    tag_id: str,
    value: Any,
    quality: int = 192,
    timestamp: datetime = None
):
    """Emit tag value update to subscribed clients."""
    if _tag_namespace:
        _tag_namespace.emit_tag_value(tag_id, value, quality, timestamp)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'tag_value',
            {
                'tag_id': tag_id,
                'value': value,
                'quality': quality,
                'timestamp': (timestamp or datetime.utcnow()).isoformat(),
            },
            f"tag:{tag_id}",
            '/tags'
        )


def emit_tag_values_batch(values: Dict[str, Dict[str, Any]]):
    """Emit batch tag value updates."""
    if _tag_namespace:
        _tag_namespace.emit_tag_values(values)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'tag_values',
            {'values': values, 'timestamp': datetime.utcnow().isoformat()},
            'tags',
            '/tags'
        )
