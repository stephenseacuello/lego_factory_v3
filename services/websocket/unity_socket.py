"""
LEGO Factory v3 - Unity WebSocket Namespace
============================================
Namespace handler for Unity Digital Twin communication.

Events (Server -> Client):
- entity_update: Entity state/transform changes
- scene_change: Active scene changed
- state_sync: Full state synchronization
- alarm_overlay: Alarm visualization updates
- anomaly_overlay: ML anomaly highlights

Events (Client -> Server):
- subscribe_entity: Subscribe to entity updates
- unsubscribe_entity: Unsubscribe from entity updates
- request_sync: Request full state sync
- update_entity: Update entity from Unity
- camera_position: Camera position for analytics
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Set, List

from flask import request, session
from flask_socketio import Namespace, emit, join_room, leave_room

from services.websocket.socket_service import connection_manager

logger = logging.getLogger(__name__)


class UnityNamespace(Namespace):
    """
    WebSocket namespace for Unity Digital Twin communication.

    Supports real-time bidirectional communication between the
    Flask backend and Unity visualization clients.
    """

    def __init__(self, namespace: str = '/unity'):
        super().__init__(namespace)
        # Track subscribed entities per client
        self._entity_subscriptions: Dict[str, Set[str]] = {}
        # Track Unity client metadata
        self._unity_clients: Dict[str, Dict[str, Any]] = {}

    def on_connect(self):
        """Handle Unity client connection."""
        sid = request.sid
        user_id = session.get('user_id')

        # Register with connection manager
        connection_manager.register_client(
            sid=sid,
            namespace='/unity',
            user_id=user_id,
            metadata={
                'ip': request.remote_addr,
                'client_type': 'unity',
            }
        )

        # Initialize subscriptions
        self._entity_subscriptions[sid] = set()

        # Store Unity-specific metadata
        self._unity_clients[sid] = {
            'connected_at': datetime.utcnow().isoformat(),
            'scene': None,
            'camera_position': None,
        }

        # Send connection acknowledgment
        emit('connection_ack', {
            'status': 'connected',
            'sid': sid,
            'namespace': '/unity',
            'timestamp': datetime.utcnow().isoformat(),
        })

        # Auto-join unity room
        join_room('unity')
        connection_manager.join_room(sid, 'unity')

        logger.info(f"Unity client connected: {sid}")

    def on_disconnect(self):
        """Handle Unity client disconnection."""
        sid = request.sid

        # Clean up subscriptions
        self._entity_subscriptions.pop(sid, None)
        self._unity_clients.pop(sid, None)

        # Unregister from connection manager
        connection_manager.unregister_client(sid, '/unity')

        logger.info(f"Unity client disconnected: {sid}")

    def on_subscribe_entity(self, data: Dict[str, Any]):
        """
        Subscribe to entity updates.

        Args:
            data: {
                'entity_id': str or list,
                'include_children': bool (optional)
            }
        """
        sid = request.sid

        if sid not in self._entity_subscriptions:
            self._entity_subscriptions[sid] = set()

        entity_ids = data.get('entity_id', [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        include_children = data.get('include_children', False)

        for entity_id in entity_ids:
            self._entity_subscriptions[sid].add(entity_id)

            # Join entity-specific room for targeted updates
            room_name = f"entity:{entity_id}"
            join_room(room_name)

            if include_children:
                # Subscribe to child entity room
                join_room(f"entity:{entity_id}:children")

        emit('subscribe_ack', {
            'entity_ids': entity_ids,
            'subscribed': True,
            'total_subscriptions': len(self._entity_subscriptions[sid]),
        })

        logger.debug(f"Client {sid} subscribed to entities: {entity_ids}")

    def on_unsubscribe_entity(self, data: Dict[str, Any]):
        """
        Unsubscribe from entity updates.

        Args:
            data: {
                'entity_id': str or list,
            }
        """
        sid = request.sid

        if sid not in self._entity_subscriptions:
            return

        entity_ids = data.get('entity_id', [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        for entity_id in entity_ids:
            self._entity_subscriptions[sid].discard(entity_id)

            # Leave entity-specific room
            room_name = f"entity:{entity_id}"
            leave_room(room_name)
            leave_room(f"entity:{entity_id}:children")

        emit('unsubscribe_ack', {
            'entity_ids': entity_ids,
            'subscribed': False,
            'total_subscriptions': len(self._entity_subscriptions[sid]),
        })

        logger.debug(f"Client {sid} unsubscribed from entities: {entity_ids}")

    def on_request_sync(self, data: Dict[str, Any] = None):
        """
        Request full state synchronization.

        Args:
            data: {
                'scene_id': str (optional),
                'entity_types': list (optional),
            }
        """
        sid = request.sid
        data = data or {}

        try:
            from services.unity.unity_state_service import get_unity_service

            service = get_unity_service()
            scene_id = data.get('scene_id')
            entity_types = data.get('entity_types')

            # Get scene state
            scene_state = service.get_scene_state(scene_id)

            # Filter by entity types if specified
            if entity_types and 'entities' in scene_state:
                scene_state['entities'] = {
                    k: v for k, v in scene_state['entities'].items()
                    if v.get('entity_type') in entity_types
                }

            emit('state_sync', {
                'scene': scene_state,
                'timestamp': datetime.utcnow().isoformat(),
                'full_sync': True,
            })

            # Update client metadata
            if sid in self._unity_clients:
                self._unity_clients[sid]['scene'] = scene_id

            logger.debug(f"State sync sent to client {sid}")

        except Exception as e:
            logger.error(f"Error during state sync: {e}")
            emit('error', {
                'code': 'SYNC_ERROR',
                'message': str(e),
            })

    def on_update_entity(self, data: Dict[str, Any]):
        """
        Handle entity update from Unity client.

        This allows Unity to push updates back to the server,
        such as user interactions or VR-based modifications.

        Args:
            data: {
                'entity_id': str,
                'state': dict (optional),
                'transform': dict (optional),
            }
        """
        sid = request.sid

        entity_id = data.get('entity_id')
        if not entity_id:
            emit('error', {'message': 'entity_id required'})
            return

        try:
            from services.unity.unity_state_service import get_unity_service

            service = get_unity_service()
            success = service.update_entity(
                entity_id=entity_id,
                state=data.get('state'),
                transform=data.get('transform'),
            )

            if success:
                emit('update_ack', {
                    'entity_id': entity_id,
                    'success': True,
                    'timestamp': datetime.utcnow().isoformat(),
                })

                # Broadcast to other Unity clients
                self.emit_entity_update(entity_id, data, skip_sid=sid)
            else:
                emit('error', {
                    'code': 'UPDATE_FAILED',
                    'message': f'Entity not found: {entity_id}',
                })

        except Exception as e:
            logger.error(f"Error updating entity: {e}")
            emit('error', {
                'code': 'UPDATE_ERROR',
                'message': str(e),
            })

    def on_camera_position(self, data: Dict[str, Any]):
        """
        Handle camera position update from Unity.

        Used for analytics and focusing updates on visible entities.

        Args:
            data: {
                'position': {'x': float, 'y': float, 'z': float},
                'rotation': {'x': float, 'y': float, 'z': float, 'w': float},
                'fov': float,
            }
        """
        sid = request.sid

        if sid in self._unity_clients:
            self._unity_clients[sid]['camera_position'] = {
                'position': data.get('position'),
                'rotation': data.get('rotation'),
                'fov': data.get('fov'),
                'updated_at': datetime.utcnow().isoformat(),
            }

    def on_ping(self):
        """Handle ping request."""
        emit('pong', {
            'timestamp': datetime.utcnow().isoformat(),
            'namespace': '/unity',
        })

    # Server-side emission methods

    def emit_entity_update(
        self,
        entity_id: str,
        data: Dict[str, Any],
        skip_sid: Optional[str] = None
    ):
        """
        Emit entity update to subscribed clients.

        Args:
            entity_id: Entity ID
            data: Update data (state, transform, etc.)
            skip_sid: SID to skip (optional)
        """
        from flask_socketio import emit as socketio_emit

        update_data = {
            'entity_id': entity_id,
            'timestamp': datetime.utcnow().isoformat(),
            **data,
        }

        # Emit to entity-specific room
        socketio_emit(
            'entity_update',
            update_data,
            room=f"entity:{entity_id}",
            namespace='/unity',
            skip_sid=skip_sid,
        )

        # Also emit to general unity room for non-subscribed monitoring
        socketio_emit(
            'entity_update',
            update_data,
            room='unity',
            namespace='/unity',
            skip_sid=skip_sid,
        )

    def emit_scene_change(
        self,
        scene_id: str,
        scene_data: Dict[str, Any] = None
    ):
        """
        Emit scene change notification.

        Args:
            scene_id: New active scene ID
            scene_data: Scene data (optional)
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'scene_change',
            {
                'scene_id': scene_id,
                'scene_data': scene_data,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='unity',
            namespace='/unity',
        )

    def emit_state_sync(
        self,
        scene_state: Dict[str, Any],
        target_sid: Optional[str] = None
    ):
        """
        Emit full state sync.

        Args:
            scene_state: Complete scene state
            target_sid: Target specific client (optional)
        """
        from flask_socketio import emit as socketio_emit

        sync_data = {
            'scene': scene_state,
            'timestamp': datetime.utcnow().isoformat(),
            'full_sync': True,
        }

        if target_sid:
            socketio_emit(
                'state_sync',
                sync_data,
                room=target_sid,
                namespace='/unity',
            )
        else:
            socketio_emit(
                'state_sync',
                sync_data,
                room='unity',
                namespace='/unity',
            )

    def emit_alarm_overlay(
        self,
        entity_id: str,
        alarm_data: Dict[str, Any]
    ):
        """
        Emit alarm visualization overlay.

        Args:
            entity_id: Affected entity ID
            alarm_data: Alarm information for visualization
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'alarm_overlay',
            {
                'entity_id': entity_id,
                'alarm': alarm_data,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='unity',
            namespace='/unity',
        )

    def emit_anomaly_overlay(
        self,
        entity_id: str,
        anomaly_data: Dict[str, Any]
    ):
        """
        Emit ML anomaly visualization overlay.

        Args:
            entity_id: Affected entity ID
            anomaly_data: Anomaly information for visualization
        """
        from flask_socketio import emit as socketio_emit

        socketio_emit(
            'anomaly_overlay',
            {
                'entity_id': entity_id,
                'anomaly': anomaly_data,
                'timestamp': datetime.utcnow().isoformat(),
            },
            room='unity',
            namespace='/unity',
        )

    def get_connected_clients(self) -> List[Dict[str, Any]]:
        """Get list of connected Unity clients."""
        return [
            {
                'sid': sid,
                **metadata,
                'subscriptions': list(self._entity_subscriptions.get(sid, set())),
            }
            for sid, metadata in self._unity_clients.items()
        ]


# Global namespace instance for external access
_unity_namespace: Optional[UnityNamespace] = None


def get_unity_namespace() -> Optional[UnityNamespace]:
    """Get Unity namespace instance."""
    return _unity_namespace


def set_unity_namespace(namespace: UnityNamespace):
    """Set Unity namespace instance."""
    global _unity_namespace
    _unity_namespace = namespace


# Convenience functions for emitting events

def emit_entity_update(
    entity_id: str,
    data: Dict[str, Any],
    skip_sid: Optional[str] = None
):
    """Emit entity update to Unity clients."""
    if _unity_namespace:
        _unity_namespace.emit_entity_update(entity_id, data, skip_sid)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'entity_update',
            {'entity_id': entity_id, 'timestamp': datetime.utcnow().isoformat(), **data},
            'unity',
            '/unity',
            skip_sid
        )


def emit_scene_change(scene_id: str, scene_data: Dict[str, Any] = None):
    """Emit scene change to Unity clients."""
    if _unity_namespace:
        _unity_namespace.emit_scene_change(scene_id, scene_data)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'scene_change',
            {'scene_id': scene_id, 'scene_data': scene_data, 'timestamp': datetime.utcnow().isoformat()},
            'unity',
            '/unity'
        )


def emit_alarm_overlay(entity_id: str, alarm_data: Dict[str, Any]):
    """Emit alarm overlay to Unity clients."""
    if _unity_namespace:
        _unity_namespace.emit_alarm_overlay(entity_id, alarm_data)
    else:
        from services.websocket.socket_service import emit_to_room
        emit_to_room(
            'alarm_overlay',
            {'entity_id': entity_id, 'alarm': alarm_data, 'timestamp': datetime.utcnow().isoformat()},
            'unity',
            '/unity'
        )
