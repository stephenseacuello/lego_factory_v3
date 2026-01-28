"""
Tag Management Service
Manages tag definitions, hierarchies, templates, and real-time values
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

from models.scada.models import Tag, TagGroup, TagTemplate
from config.database import get_session

logger = logging.getLogger(__name__)


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
    
    def __init__(self):
        self._values: Dict[str, TagValue] = {}
        self._lock = asyncio.Lock()
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    
    async def set(self, tag_id: str, value: Any, quality: int = 192, 
                  tag_name: str = None, eng_units: str = None):
        """Update tag value in cache"""
        async with self._lock:
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
    
    # =========================================================================
    # TAG CRUD
    # =========================================================================
    
    def create_tag(self, tag_data: Dict[str, Any]) -> Tag:
        """Create a new tag"""
        tag = Tag(
            tag_id=uuid.uuid4(),
            tag_name=tag_data['tag_name'],
            description=tag_data.get('description'),
            group_id=tag_data.get('group_id'),
            data_type=tag_data['data_type'],
            eng_units=tag_data.get('eng_units'),
            eng_low=tag_data.get('eng_low'),
            eng_high=tag_data.get('eng_high'),
            raw_low=tag_data.get('raw_low'),
            raw_high=tag_data.get('raw_high'),
            alarm_hh=tag_data.get('alarm_hh'),
            alarm_hi=tag_data.get('alarm_hi'),
            alarm_lo=tag_data.get('alarm_lo'),
            alarm_ll=tag_data.get('alarm_ll'),
            alarm_deadband=tag_data.get('alarm_deadband'),
            scan_rate_ms=tag_data.get('scan_rate_ms', 1000),
            historian_enabled=tag_data.get('historian_enabled', True),
            compression_enabled=tag_data.get('compression_enabled', True),
            compression_deviation=tag_data.get('compression_deviation'),
            source_type=tag_data.get('source_type'),
            source_address=tag_data.get('source_address'),
            source_config=tag_data.get('source_config'),
            is_active=tag_data.get('is_active', True)
        )
        self.session.add(tag)
        self.session.flush()
        logger.info(f"Created tag: {tag.tag_name}")
        return tag
    
    def get_tag(self, tag_id: str) -> Optional[Tag]:
        """Get tag by ID"""
        return self.session.query(Tag).filter(Tag.tag_id == tag_id).first()
    
    def get_tag_by_name(self, tag_name: str) -> Optional[Tag]:
        """Get tag by name"""
        return self.session.query(Tag).filter(Tag.tag_name == tag_name).first()
    
    def get_tags(
        self, 
        group_id: str = None,
        source_type: str = None,
        is_active: bool = None,
        search: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Tag]:
        """Get tags with filtering"""
        query = self.session.query(Tag)
        
        if group_id:
            query = query.filter(Tag.group_id == group_id)
        if source_type:
            query = query.filter(Tag.source_type == source_type)
        if is_active is not None:
            query = query.filter(Tag.is_active == is_active)
        if search:
            query = query.filter(
                or_(
                    Tag.tag_name.ilike(f'%{search}%'),
                    Tag.description.ilike(f'%{search}%')
                )
            )
        
        return query.order_by(Tag.tag_name).offset(offset).limit(limit).all()
    
    def update_tag(self, tag_id: str, tag_data: Dict[str, Any]) -> Optional[Tag]:
        """Update tag configuration"""
        tag = self.get_tag(tag_id)
        if not tag:
            return None
        
        for key, value in tag_data.items():
            if hasattr(tag, key) and key not in ('tag_id', 'created_at'):
                setattr(tag, key, value)
        
        tag.updated_at = datetime.utcnow()
        self.session.flush()
        logger.info(f"Updated tag: {tag.tag_name}")
        return tag
    
    def delete_tag(self, tag_id: str) -> bool:
        """Delete tag (soft delete - set inactive)"""
        tag = self.get_tag(tag_id)
        if not tag:
            return False
        
        tag.is_active = False
        tag.updated_at = datetime.utcnow()
        logger.info(f"Deactivated tag: {tag.tag_name}")
        return True
    
    # =========================================================================
    # TAG GROUPS
    # =========================================================================
    
    def create_group(self, name: str, description: str = None, 
                     parent_group_id: str = None) -> TagGroup:
        """Create a tag group"""
        # Build path
        path = name
        if parent_group_id:
            parent = self.session.query(TagGroup).filter(
                TagGroup.group_id == parent_group_id
            ).first()
            if parent and parent.path:
                path = f"{parent.path}/{name}"
        
        group = TagGroup(
            group_id=uuid.uuid4(),
            name=name,
            description=description,
            parent_group_id=parent_group_id,
            path=path
        )
        self.session.add(group)
        self.session.flush()
        return group
    
    def get_groups(self, parent_id: str = None) -> List[TagGroup]:
        """Get tag groups"""
        query = self.session.query(TagGroup)
        if parent_id:
            query = query.filter(TagGroup.parent_group_id == parent_id)
        else:
            query = query.filter(TagGroup.parent_group_id.is_(None))
        return query.order_by(TagGroup.name).all()
    
    def get_group_hierarchy(self) -> List[Dict[str, Any]]:
        """Get full group hierarchy as nested structure"""
        groups = self.session.query(TagGroup).all()
        
        # Build lookup
        group_dict = {str(g.group_id): {
            'group_id': str(g.group_id),
            'name': g.name,
            'description': g.description,
            'path': g.path,
            'children': []
        } for g in groups}
        
        # Build tree
        root = []
        for g in groups:
            if g.parent_group_id:
                parent_id = str(g.parent_group_id)
                if parent_id in group_dict:
                    group_dict[parent_id]['children'].append(group_dict[str(g.group_id)])
            else:
                root.append(group_dict[str(g.group_id)])
        
        return root
    
    # =========================================================================
    # TAG TEMPLATES
    # =========================================================================
    
    def create_template(self, template_data: Dict[str, Any]) -> TagTemplate:
        """Create a tag template"""
        template = TagTemplate(
            template_id=uuid.uuid4(),
            **template_data
        )
        self.session.add(template)
        self.session.flush()
        return template
    
    def get_templates(self) -> List[TagTemplate]:
        """Get all tag templates"""
        return self.session.query(TagTemplate).order_by(TagTemplate.template_name).all()
    
    def create_tag_from_template(
        self, 
        template_id: str, 
        tag_name: str,
        setpoint: float = None,
        **overrides
    ) -> Tag:
        """Create a tag from a template"""
        template = self.session.query(TagTemplate).filter(
            TagTemplate.template_id == template_id
        ).first()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Build tag data from template
        tag_data = {
            'tag_name': tag_name,
            'data_type': template.data_type,
            'eng_units': template.eng_units,
            'scan_rate_ms': template.scan_rate_ms,
            'compression_deviation': template.compression_deviation,
            'source_type': template.source_type,
        }
        
        # Calculate alarm limits from setpoint if provided
        if setpoint is not None:
            if template.alarm_hh_offset is not None:
                tag_data['alarm_hh'] = setpoint + float(template.alarm_hh_offset)
            if template.alarm_hi_offset is not None:
                tag_data['alarm_hi'] = setpoint + float(template.alarm_hi_offset)
            if template.alarm_lo_offset is not None:
                tag_data['alarm_lo'] = setpoint + float(template.alarm_lo_offset)
            if template.alarm_ll_offset is not None:
                tag_data['alarm_ll'] = setpoint + float(template.alarm_ll_offset)
        
        # Apply overrides
        tag_data.update(overrides)
        
        return self.create_tag(tag_data)
    
    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================
    
    def bulk_create_tags(self, tags_data: List[Dict[str, Any]]) -> List[Tag]:
        """Create multiple tags"""
        tags = []
        for data in tags_data:
            tag = Tag(tag_id=uuid.uuid4(), **data)
            self.session.add(tag)
            tags.append(tag)
        self.session.flush()
        logger.info(f"Bulk created {len(tags)} tags")
        return tags
    
    def bulk_update_tags(self, updates: List[Dict[str, Any]]) -> int:
        """Update multiple tags
        
        Args:
            updates: List of dicts with 'tag_id' and fields to update
        """
        count = 0
        for update_data in updates:
            tag_id = update_data.pop('tag_id')
            tag = self.get_tag(tag_id)
            if tag:
                for key, value in update_data.items():
                    if hasattr(tag, key):
                        setattr(tag, key, value)
                tag.updated_at = datetime.utcnow()
                count += 1
        self.session.flush()
        return count
    
    # =========================================================================
    # SCALING / ENGINEERING UNITS
    # =========================================================================
    
    def scale_value(self, tag: Tag, raw_value: float) -> float:
        """Convert raw value to engineering units"""
        if tag.raw_low is None or tag.raw_high is None:
            return raw_value
        if tag.eng_low is None or tag.eng_high is None:
            return raw_value
        
        raw_range = float(tag.raw_high - tag.raw_low)
        eng_range = float(tag.eng_high - tag.eng_low)
        
        if raw_range == 0:
            return raw_value
        
        return float(tag.eng_low) + ((raw_value - float(tag.raw_low)) / raw_range) * eng_range
    
    def inverse_scale(self, tag: Tag, eng_value: float) -> float:
        """Convert engineering units to raw value"""
        if tag.raw_low is None or tag.raw_high is None:
            return eng_value
        if tag.eng_low is None or tag.eng_high is None:
            return eng_value
        
        raw_range = float(tag.raw_high - tag.raw_low)
        eng_range = float(tag.eng_high - tag.eng_low)
        
        if eng_range == 0:
            return eng_value
        
        return float(tag.raw_low) + ((eng_value - float(tag.eng_low)) / eng_range) * raw_range
    
    # =========================================================================
    # EXPORT / IMPORT
    # =========================================================================
    
    def export_tags(self, group_id: str = None) -> List[Dict[str, Any]]:
        """Export tags to dictionary format"""
        tags = self.get_tags(group_id=group_id, limit=10000)
        return [{
            'tag_name': t.tag_name,
            'description': t.description,
            'data_type': t.data_type,
            'eng_units': t.eng_units,
            'eng_low': float(t.eng_low) if t.eng_low else None,
            'eng_high': float(t.eng_high) if t.eng_high else None,
            'alarm_hh': float(t.alarm_hh) if t.alarm_hh else None,
            'alarm_hi': float(t.alarm_hi) if t.alarm_hi else None,
            'alarm_lo': float(t.alarm_lo) if t.alarm_lo else None,
            'alarm_ll': float(t.alarm_ll) if t.alarm_ll else None,
            'scan_rate_ms': t.scan_rate_ms,
            'source_type': t.source_type,
            'source_address': t.source_address,
        } for t in tags]
    
    def import_tags(self, tags_data: List[Dict[str, Any]], 
                    update_existing: bool = False) -> Dict[str, int]:
        """Import tags from dictionary format
        
        Returns:
            Dict with 'created', 'updated', 'skipped' counts
        """
        result = {'created': 0, 'updated': 0, 'skipped': 0}
        
        for data in tags_data:
            existing = self.get_tag_by_name(data['tag_name'])
            
            if existing:
                if update_existing:
                    self.update_tag(str(existing.tag_id), data)
                    result['updated'] += 1
                else:
                    result['skipped'] += 1
            else:
                self.create_tag(data)
                result['created'] += 1
        
        self.session.flush()
        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_tag_service() -> TagService:
    """Get tag service with session"""
    with get_session() as session:
        return TagService(session)


async def write_tag_value(tag_id: str, value: Any, quality: int = 192):
    """Write a value to the tag cache"""
    await tag_cache.set(tag_id, value, quality)


async def read_tag_value(tag_id: str) -> Optional[TagValue]:
    """Read current tag value from cache"""
    return await tag_cache.get(tag_id)


async def read_tag_values(tag_ids: List[str]) -> Dict[str, TagValue]:
    """Read multiple tag values from cache"""
    return await tag_cache.get_many(tag_ids)
