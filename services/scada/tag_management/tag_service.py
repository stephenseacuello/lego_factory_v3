"""
LEGO Factory v3 - Tag Management Service
=========================================
Manages tag definitions, hierarchies, templates, and real-time values.
"""

import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict
import logging

from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import Session

from config.database import get_db_session

logger = logging.getLogger(__name__)


def _emit_tag_event(event_type: str, data: Dict[str, Any]):
    """
    Emit tag event to WebSocket clients.
    Gracefully handles case where SocketIO isn't initialized.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace, emit_to_room

        # Emit to /tags namespace for tag subscribers
        emit_to_namespace(event_type, data, namespace='/tags')

        # Also emit to tag-specific room if needed
        tag_id = data.get('tag_id')
        if tag_id:
            emit_to_room(event_type, data, room=f'tag_{tag_id}', namespace='/tags')

        logger.debug(f"Emitted tag event: {event_type} for tag {tag_id}")
    except ImportError:
        logger.debug("WebSocket service not available, skipping tag emit")
    except Exception as e:
        logger.warning(f"Failed to emit tag event: {e}")


@dataclass
class TagValue:
    """Real-time tag value"""
    tag_id: str
    tag_name: str
    value: Any
    quality: int  # OPC quality code
    timestamp: datetime
    eng_units: str = None


@dataclass
class TagInfo:
    """Tag information with current value"""
    tag_id: str
    tag_name: str
    description: str
    data_type: str
    eng_units: str
    eng_low: float
    eng_high: float
    alarm_hh: float
    alarm_hi: float
    alarm_lo: float
    alarm_ll: float
    source_type: str
    source_address: str
    is_active: bool
    current_value: Any = None
    quality: int = 0
    last_update: datetime = None


class TagCache:
    """In-memory cache for real-time tag values"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._values: Dict[str, TagValue] = {}
            cls._instance._lock = asyncio.Lock()
            cls._instance._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        return cls._instance

    async def set(self, tag_id: str, value: Any, quality: int = 192,
                  tag_name: str = None, eng_units: str = None):
        """Update tag value in cache"""
        async with self._lock:
            # Check if value or quality changed
            old_value = self._values.get(tag_id)
            value_changed = old_value is None or old_value.value != value
            quality_changed = old_value is not None and old_value.quality != quality

            tag_value = TagValue(
                tag_id=tag_id,
                tag_name=tag_name or tag_id,
                value=value,
                quality=quality,
                timestamp=datetime.utcnow(),
                eng_units=eng_units
            )
            self._values[tag_id] = tag_value

            # Notify subscribers
            for queue in self._subscribers.get(tag_id, []):
                try:
                    queue.put_nowait(tag_value)
                except asyncio.QueueFull:
                    pass

            # Emit WebSocket events for value and quality changes
            event_data = {
                'tag_id': tag_id,
                'tag_name': tag_name or tag_id,
                'value': value,
                'quality': quality,
                'timestamp': tag_value.timestamp.isoformat(),
                'eng_units': eng_units,
            }

            if value_changed:
                event_data['previous_value'] = old_value.value if old_value else None
                _emit_tag_event('tag_value_changed', event_data)

            if quality_changed:
                event_data['previous_quality'] = old_value.quality if old_value else None
                _emit_tag_event('tag_quality_changed', event_data)

    async def get(self, tag_id: str) -> Optional[TagValue]:
        """Get current tag value"""
        return self._values.get(tag_id)

    async def get_many(self, tag_ids: List[str]) -> Dict[str, TagValue]:
        """Get multiple tag values"""
        return {tid: self._values[tid] for tid in tag_ids if tid in self._values}

    async def subscribe(self, tag_id: str) -> asyncio.Queue:
        """Subscribe to tag value changes"""
        queue = asyncio.Queue(maxsize=100)
        self._subscribers[tag_id].append(queue)
        return queue

    async def unsubscribe(self, tag_id: str, queue: asyncio.Queue):
        """Unsubscribe from tag value changes"""
        if queue in self._subscribers.get(tag_id, []):
            self._subscribers[tag_id].remove(queue)


# Global tag cache instance
tag_cache = TagCache()


class TagService:
    """Tag management operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_tag(self, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tag"""
        from models.scada.tags import Tag, TagDataType, TagCategory

        tag = Tag(
            tag_id=tag_data['tag_id'],
            name=tag_data['name'],
            description=tag_data.get('description'),
            data_type=TagDataType(tag_data.get('data_type', 'float32')),
            category=TagCategory(tag_data.get('category', 'analog_input')),
            area=tag_data.get('area'),
            equipment=tag_data.get('equipment'),
            eng_units=tag_data.get('eng_units'),
            eng_low=tag_data.get('eng_low'),
            eng_high=tag_data.get('eng_high'),
            raw_low=tag_data.get('raw_low'),
            raw_high=tag_data.get('raw_high'),
            deadband=tag_data.get('deadband', 0.0),
            historize=tag_data.get('historize', True),
            scan_rate_ms=tag_data.get('scan_rate_ms', 1000),
            compression_enabled=tag_data.get('compression_enabled', True),
            compression_deviation=tag_data.get('compression_deviation', 0.01),
            source_type=tag_data.get('source_type', 'internal'),
            source_address=tag_data.get('source_address'),
            source_config=tag_data.get('source_config'),
        )
        self.session.add(tag)
        self.session.flush()
        logger.info(f"Created tag: {tag.tag_id}")
        return tag.to_dict()

    def get_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Get tag by ID"""
        from models.scada.tags import Tag
        tag = self.session.query(Tag).filter(Tag.tag_id == tag_id).first()
        return tag.to_dict() if tag else None

    def get_tags(
        self,
        area: str = None,
        equipment: str = None,
        category: str = None,
        search: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get tags with filtering"""
        from models.scada.tags import Tag

        query = self.session.query(Tag).filter(Tag.is_deleted == False)

        if area:
            query = query.filter(Tag.area == area)
        if equipment:
            query = query.filter(Tag.equipment == equipment)
        if category:
            query = query.filter(Tag.category == category)
        if search:
            query = query.filter(
                or_(
                    Tag.tag_id.ilike(f'%{search}%'),
                    Tag.name.ilike(f'%{search}%'),
                    Tag.description.ilike(f'%{search}%')
                )
            )

        tags = query.order_by(Tag.tag_id).offset(offset).limit(limit).all()
        return [t.to_dict() for t in tags]

    def update_tag(self, tag_id: str, tag_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update tag configuration"""
        from models.scada.tags import Tag

        tag = self.session.query(Tag).filter(Tag.tag_id == tag_id).first()
        if not tag:
            return None

        for key, value in tag_data.items():
            if hasattr(tag, key) and key not in ('id', 'tag_id', 'created_at'):
                setattr(tag, key, value)

        tag.updated_at = datetime.utcnow()
        self.session.flush()
        logger.info(f"Updated tag: {tag.tag_id}")
        return tag.to_dict()

    def delete_tag(self, tag_id: str) -> bool:
        """Delete tag (soft delete)"""
        from models.scada.tags import Tag

        tag = self.session.query(Tag).filter(Tag.tag_id == tag_id).first()
        if not tag:
            return False

        tag.soft_delete()
        logger.info(f"Deleted tag: {tag.tag_id}")
        return True

    def get_tag_groups(self, parent_id: str = None) -> List[Dict[str, Any]]:
        """Get tag groups"""
        from models.scada.tags import TagGroup

        query = self.session.query(TagGroup).filter(TagGroup.is_deleted == False)
        if parent_id:
            query = query.filter(TagGroup.parent_id == parent_id)
        else:
            query = query.filter(TagGroup.parent_id.is_(None))

        groups = query.order_by(TagGroup.name).all()
        return [g.to_dict() for g in groups]

    def create_tag_group(self, name: str, description: str = None,
                         parent_id: str = None, tag_ids: List[str] = None) -> Dict[str, Any]:
        """Create a tag group"""
        from models.scada.tags import TagGroup

        group = TagGroup(
            name=name,
            description=description,
            parent_id=parent_id,
            tag_ids=tag_ids or []
        )
        self.session.add(group)
        self.session.flush()
        return group.to_dict()

    def scale_value(self, tag_id: str, raw_value: float) -> float:
        """Convert raw value to engineering units"""
        from models.scada.tags import Tag

        tag = self.session.query(Tag).filter(Tag.tag_id == tag_id).first()
        if not tag:
            return raw_value
        return tag.scale_to_eng(raw_value)

    def inverse_scale(self, tag_id: str, eng_value: float) -> float:
        """Convert engineering units to raw value"""
        from models.scada.tags import Tag

        tag = self.session.query(Tag).filter(Tag.tag_id == tag_id).first()
        if not tag:
            return eng_value
        return tag.scale_to_raw(eng_value)

    def bulk_create_tags(self, tags_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create multiple tags"""
        results = []
        for data in tags_data:
            result = self.create_tag(data)
            results.append(result)
        return results

    def export_tags(self, area: str = None) -> List[Dict[str, Any]]:
        """Export tags to dictionary format"""
        return self.get_tags(area=area, limit=10000)

    def import_tags(self, tags_data: List[Dict[str, Any]],
                    update_existing: bool = False) -> Dict[str, int]:
        """Import tags from dictionary format"""
        result = {'created': 0, 'updated': 0, 'skipped': 0}

        for data in tags_data:
            existing = self.get_tag(data['tag_id'])

            if existing:
                if update_existing:
                    self.update_tag(data['tag_id'], data)
                    result['updated'] += 1
                else:
                    result['skipped'] += 1
            else:
                self.create_tag(data)
                result['created'] += 1

        self.session.flush()
        return result


def get_tag_service(session: Session = None) -> TagService:
    """Get tag service with session"""
    if session:
        return TagService(session)
    with get_db_session() as session:
        return TagService(session)


async def write_tag_value(tag_id: str, value: Any, quality: int = 192,
                          tag_name: str = None, eng_units: str = None):
    """Write a value to the tag cache and persist process variables to DB."""
    await tag_cache.set(tag_id, value, quality, tag_name, eng_units)

    # Persist process variable readings to sensor_readings table
    _persist_tag_reading(tag_id, value, quality, tag_name, eng_units)


def _persist_tag_reading(tag_id: str, value: Any, quality: int,
                         tag_name: str = None, eng_units: str = None):
    """Persist a tag reading to the sensor_readings table for historian."""
    import logging
    _logger = logging.getLogger(__name__)
    try:
        from datetime import datetime
        from config.database import get_db_session
        from models.mes.sensor_data import SensorReading

        # Extract machine_id from tag_id (format: "machine_id.tag_name")
        parts = tag_id.split('.', 1) if '.' in tag_id else [tag_id, tag_name or tag_id]
        machine_id = parts[0]
        name = tag_name or parts[1] if len(parts) > 1 else tag_id

        reading = SensorReading(
            timestamp=datetime.utcnow(),
            machine_id=machine_id,
            tag_name=name,
            unit=eng_units,
            quality=quality,
            source='plc',
        )

        # Set the appropriate value column based on type
        if isinstance(value, bool):
            reading.value_bool = value
        elif isinstance(value, float):
            reading.value_float = value
        elif isinstance(value, int):
            reading.value_int = value
        elif value is not None:
            reading.value_str = str(value)

        with get_db_session() as session:
            session.add(reading)
            session.commit()
    except Exception as e:
        _logger.debug(f"Could not persist tag reading to DB: {e}")


async def read_tag_value(tag_id: str) -> Optional[TagValue]:
    """Read current tag value from cache"""
    return await tag_cache.get(tag_id)


async def read_tag_values(tag_ids: List[str]) -> Dict[str, TagValue]:
    """Read multiple tag values from cache"""
    return await tag_cache.get_many(tag_ids)
