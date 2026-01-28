"""
LEGO Factory v3 - Unity State Service
======================================
Digital Twin state synchronization (ISO 23247 compliant).
"""

import logging
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import time

logger = logging.getLogger(__name__)


def _emit_unity_event(event_type: str, data: Dict[str, Any]):
    """
    Emit Unity event to WebSocket clients.
    Gracefully handles case where SocketIO isn't initialized.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace, emit_to_room

        # Emit to /unity namespace for Unity clients
        emit_to_namespace(event_type, data, namespace='/unity')

        # Also emit to unity room on /unity namespace
        emit_to_room(event_type, data, room='unity', namespace='/unity')

        logger.debug(f"Emitted unity event: {event_type}")
    except ImportError:
        logger.debug("WebSocket service not available, skipping unity emit")
    except Exception as e:
        logger.warning(f"Failed to emit unity event: {e}")


class EntityType(str, Enum):
    """Digital Twin entity types."""
    MACHINE = 'machine'
    ROBOT = 'robot'
    CONVEYOR = 'conveyor'
    SENSOR = 'sensor'
    WORKPIECE = 'workpiece'
    BRICK = 'brick'
    WORKER = 'worker'
    ALARM = 'alarm'
    ZONE = 'zone'


@dataclass
class Transform:
    """3D Transform for positioning."""
    position: Dict[str, float] = field(default_factory=lambda: {'x': 0, 'y': 0, 'z': 0})
    rotation: Dict[str, float] = field(default_factory=lambda: {'x': 0, 'y': 0, 'z': 0, 'w': 1})
    scale: Dict[str, float] = field(default_factory=lambda: {'x': 1, 'y': 1, 'z': 1})


@dataclass
class DigitalTwinEntity:
    """Entity in the Digital Twin."""
    entity_id: str
    entity_type: EntityType
    name: str
    transform: Transform = field(default_factory=Transform)
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    visible: bool = True
    last_update: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_id': self.entity_id,
            'entity_type': self.entity_type.value,
            'name': self.name,
            'transform': asdict(self.transform),
            'state': self.state,
            'metadata': self.metadata,
            'parent_id': self.parent_id,
            'visible': self.visible,
            'last_update': self.last_update.isoformat(),
        }


@dataclass
class SceneState:
    """Complete scene state for Unity."""
    scene_id: str
    name: str
    entities: Dict[str, DigitalTwinEntity] = field(default_factory=dict)
    global_state: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scene_id': self.scene_id,
            'name': self.name,
            'entities': {k: v.to_dict() for k, v in self.entities.items()},
            'global_state': self.global_state,
            'timestamp': self.timestamp.isoformat(),
        }


class UnityStateService:
    """
    Service for Unity Digital Twin state synchronization.

    Features:
    - Real-time state updates via WebSocket
    - Entity tracking and management
    - Historical playback support
    - Alarm visualization
    - ML anomaly overlay
    """

    def __init__(self, socketio=None):
        self.socketio = socketio

        # Scene management
        self.scenes: Dict[str, SceneState] = {}
        self.active_scene: Optional[str] = None

        # Entity tracking
        self.entities: Dict[str, DigitalTwinEntity] = {}

        # State callbacks
        self._state_callbacks: List[Callable] = []

        # Update rate control
        self.update_interval = 0.1  # 10 Hz default
        self._running = False
        self._update_thread: Optional[threading.Thread] = None

        # Connected Unity clients
        self._unity_clients: set = set()

        # Initialize default scene
        self._init_default_scene()

    def _init_default_scene(self):
        """Initialize the default factory scene."""
        scene = SceneState(
            scene_id='factory_floor',
            name='LEGO Factory Floor',
        )

        # Add default machines
        machines = [
            ('printer_1', 'Prusa MK4', {'x': 0, 'y': 0, 'z': 0}),
            ('printer_2', 'Prusa MK4', {'x': 1.5, 'y': 0, 'z': 0}),
            ('printer_3', 'Bambu X1C', {'x': 3, 'y': 0, 'z': 0}),
        ]

        for machine_id, name, pos in machines:
            entity = DigitalTwinEntity(
                entity_id=machine_id,
                entity_type=EntityType.MACHINE,
                name=name,
                transform=Transform(position=pos),
                state={'status': 'idle', 'temperature': 0, 'progress': 0},
            )
            scene.entities[machine_id] = entity
            self.entities[machine_id] = entity

        # Add robots
        robots = [
            ('niryo_ned2', 'Niryo Ned2', {'x': -1, 'y': 0, 'z': 1}),
            ('xarm_lite6', 'xArm Lite 6', {'x': 4, 'y': 0, 'z': 1}),
        ]

        for robot_id, name, pos in robots:
            entity = DigitalTwinEntity(
                entity_id=robot_id,
                entity_type=EntityType.ROBOT,
                name=name,
                transform=Transform(position=pos),
                state={'status': 'idle', 'joint_positions': [0, 0, 0, 0, 0, 0]},
            )
            scene.entities[robot_id] = entity
            self.entities[robot_id] = entity

        self.scenes['factory_floor'] = scene
        self.active_scene = 'factory_floor'

    def start(self):
        """Start the state service."""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        logger.info("Unity state service started")

    def stop(self):
        """Stop the state service."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5.0)
        logger.info("Unity state service stopped")

    def _update_loop(self):
        """Background update loop."""
        while self._running:
            try:
                self._sync_state_from_sources()
                self._broadcast_state()
            except Exception as e:
                logger.error(f"Unity state update error: {e}")

            time.sleep(self.update_interval)

    def _sync_state_from_sources(self):
        """Sync entity states from external sources."""
        # Sync machine states from SCADA
        try:
            from services.scada.machine_control import get_all_controllers
            controllers = get_all_controllers()

            for machine_id, controller in controllers.items():
                if machine_id in self.entities:
                    self.entities[machine_id].state.update({
                        'status': controller.state.value,
                        'connected': controller.is_connected,
                    })
                    self.entities[machine_id].last_update = datetime.utcnow()
        except Exception as e:
            logger.debug(f"Machine sync error: {e}")

        # Sync robot states from ROS2 bridge
        try:
            from services.robotics.ros2_bridge import get_ros2_bridge
            bridge = get_ros2_bridge()

            for robot_state in bridge.get_all_robot_states():
                robot_id = robot_state['robot_id']
                if robot_id in self.entities:
                    self.entities[robot_id].state.update({
                        'status': robot_state['state'],
                        'joint_positions': robot_state.get('joint_positions', []),
                        'gripper_closed': robot_state.get('gripper_closed', False),
                    })
                    self.entities[robot_id].last_update = datetime.utcnow()
        except Exception as e:
            logger.debug(f"Robot sync error: {e}")

        # Sync alarms
        try:
            from services.scada.alarm_management import get_alarm_processor
            processor = get_alarm_processor()

            active_alarms = processor.get_active_alarms()
            self.scenes[self.active_scene].global_state['active_alarms'] = len(active_alarms)
            self.scenes[self.active_scene].global_state['alarm_summary'] = {
                'critical': len([a for a in active_alarms if a.get('priority') == 'critical']),
                'high': len([a for a in active_alarms if a.get('priority') == 'high']),
                'medium': len([a for a in active_alarms if a.get('priority') == 'medium']),
                'low': len([a for a in active_alarms if a.get('priority') == 'low']),
            }
        except Exception as e:
            logger.debug(f"Alarm sync error: {e}")

    def _broadcast_state(self):
        """Broadcast state to connected Unity clients."""
        scene = self.scenes.get(self.active_scene)
        if not scene:
            return

        # Prepare delta update (changed entities only)
        delta = {
            'scene_id': scene.scene_id,
            'timestamp': datetime.utcnow().isoformat(),
            'entities': {},
            'global_state': scene.global_state,
        }

        for entity_id, entity in scene.entities.items():
            # Only include recently updated entities
            if (datetime.utcnow() - entity.last_update).total_seconds() < 1.0:
                delta['entities'][entity_id] = entity.to_dict()

        if delta['entities'] or delta['global_state']:
            # Use the WebSocket service for emission
            try:
                from services.websocket.unity_socket import emit_entity_update
                from services.websocket.socket_service import emit_to_room

                # Emit individual entity updates for subscribed clients
                for entity_id, entity_data in delta['entities'].items():
                    emit_entity_update(entity_id, entity_data)

                # Also emit the full delta to the unity room
                emit_to_room('state_delta', delta, 'unity', '/unity')

            except ImportError:
                # Fallback to direct SocketIO emission if websocket service not available
                if self.socketio:
                    self.socketio.emit('unity_state_update', delta, namespace='/unity')

    def update_entity(
        self,
        entity_id: str,
        state: Dict[str, Any] = None,
        transform: Dict[str, Any] = None
    ) -> bool:
        """Update an entity's state or transform."""
        if entity_id not in self.entities:
            return False

        entity = self.entities[entity_id]

        if state:
            entity.state.update(state)

        if transform:
            if 'position' in transform:
                entity.transform.position.update(transform['position'])
            if 'rotation' in transform:
                entity.transform.rotation.update(transform['rotation'])
            if 'scale' in transform:
                entity.transform.scale.update(transform['scale'])

        entity.last_update = datetime.utcnow()

        # Notify callbacks
        for callback in self._state_callbacks:
            try:
                callback(entity_id, entity.to_dict())
            except Exception as e:
                logger.error(f"State callback error: {e}")

        # Emit entity update via WebSocket
        entity_data = entity.to_dict()
        _emit_unity_event('entity_updated', {
            'entity_id': entity_id,
            'entity_type': entity.entity_type.value,
            'name': entity.name,
            'state': state,
            'transform': transform,
            'timestamp': datetime.utcnow().isoformat(),
            'entity': entity_data,
        })

        # Also try the specific emit_entity_update if available
        try:
            from services.websocket.unity_socket import emit_entity_update
            emit_entity_update(entity_id, {
                'state': state,
                'transform': transform,
            })
        except ImportError:
            pass  # WebSocket service not available

        return True

    def create_entity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new entity in the scene."""
        entity = DigitalTwinEntity(
            entity_id=data['entity_id'],
            entity_type=EntityType(data.get('entity_type', 'workpiece')),
            name=data.get('name', data['entity_id']),
            transform=Transform(
                position=data.get('position', {'x': 0, 'y': 0, 'z': 0}),
                rotation=data.get('rotation', {'x': 0, 'y': 0, 'z': 0, 'w': 1}),
                scale=data.get('scale', {'x': 1, 'y': 1, 'z': 1}),
            ),
            state=data.get('state', {}),
            metadata=data.get('metadata', {}),
            parent_id=data.get('parent_id'),
            visible=data.get('visible', True),
        )

        self.entities[entity.entity_id] = entity

        if self.active_scene and self.active_scene in self.scenes:
            self.scenes[self.active_scene].entities[entity.entity_id] = entity

        # Emit WebSocket event for entity creation
        entity_data = entity.to_dict()
        _emit_unity_event('entity_created', {
            'entity_id': entity.entity_id,
            'entity_type': entity.entity_type.value,
            'name': entity.name,
            'scene_id': self.active_scene,
            'timestamp': datetime.utcnow().isoformat(),
            'entity': entity_data,
        })

        return entity_data

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity from the scene."""
        if entity_id not in self.entities:
            return False

        # Get entity info before deletion for the event
        entity = self.entities[entity_id]
        entity_type = entity.entity_type.value
        entity_name = entity.name

        del self.entities[entity_id]

        if self.active_scene and self.active_scene in self.scenes:
            self.scenes[self.active_scene].entities.pop(entity_id, None)

        # Emit WebSocket event for entity deletion
        _emit_unity_event('entity_deleted', {
            'entity_id': entity_id,
            'entity_type': entity_type,
            'name': entity_name,
            'scene_id': self.active_scene,
            'timestamp': datetime.utcnow().isoformat(),
        })

        return True

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity state."""
        if entity_id in self.entities:
            return self.entities[entity_id].to_dict()
        return None

    def get_scene_state(self, scene_id: str = None) -> Dict[str, Any]:
        """Get complete scene state."""
        scene_id = scene_id or self.active_scene
        if scene_id in self.scenes:
            return self.scenes[scene_id].to_dict()
        logger.debug(f"Scene not found: {scene_id}")
        return {}

    def change_scene(self, scene_id: str) -> bool:
        """Change the active scene and emit WebSocket event."""
        if scene_id not in self.scenes:
            return False

        old_scene_id = self.active_scene
        self.active_scene = scene_id
        scene = self.scenes[scene_id]

        # Emit WebSocket event for scene change
        _emit_unity_event('scene_changed', {
            'old_scene_id': old_scene_id,
            'new_scene_id': scene_id,
            'scene_name': scene.name,
            'entity_count': len(scene.entities),
            'timestamp': datetime.utcnow().isoformat(),
            'scene': scene.to_dict(),
        })

        logger.info(f"Scene changed from {old_scene_id} to {scene_id}")
        return True

    def create_scene(self, scene_id: str, name: str) -> Dict[str, Any]:
        """Create a new scene and emit WebSocket event."""
        scene = SceneState(
            scene_id=scene_id,
            name=name,
        )
        self.scenes[scene_id] = scene

        # Emit WebSocket event for scene creation
        scene_data = scene.to_dict()
        _emit_unity_event('scene_created', {
            'scene_id': scene_id,
            'scene_name': name,
            'timestamp': datetime.utcnow().isoformat(),
            'scene': scene_data,
        })

        logger.info(f"Scene created: {scene_id}")
        return scene_data

    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get all entities of a specific type."""
        return [
            e.to_dict() for e in self.entities.values()
            if e.entity_type.value == entity_type
        ]

    def register_unity_client(self, client_id: str):
        """Register a connected Unity client."""
        self._unity_clients.add(client_id)
        logger.info(f"Unity client connected: {client_id}")

    def unregister_unity_client(self, client_id: str):
        """Unregister a Unity client."""
        self._unity_clients.discard(client_id)
        logger.info(f"Unity client disconnected: {client_id}")

    def register_state_callback(self, callback: Callable):
        """Register callback for state changes."""
        self._state_callbacks.append(callback)


# Global instance
_unity_service: Optional[UnityStateService] = None


def get_unity_service() -> UnityStateService:
    """Get Unity state service instance."""
    global _unity_service
    if _unity_service is None:
        _unity_service = UnityStateService()
    return _unity_service


def init_unity_service(socketio):
    """Initialize Unity service with SocketIO."""
    global _unity_service
    _unity_service = UnityStateService(socketio)
    return _unity_service
