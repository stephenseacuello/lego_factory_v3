"""
Alarm Management Service (ISA-18.2)
Complete alarm lifecycle management with prioritization, acknowledgment,
shelving, history, and analytics.
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import Session

from models.scada.models import (
    Tag, AlarmDefinition, AlarmStateLimit, ActiveAlarm, 
    AlarmHistory, AlarmStatistics, OperatingState
)
from config.database import get_session

logger = logging.getLogger(__name__)


class AlarmPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    DIAGNOSTIC = 5


class AlarmStatus(Enum):
    ACTIVE_UNACKED = 'ACTIVE_UNACKED'
    ACKED_ACTIVE = 'ACKED_ACTIVE'
    CLEARED_UNACKED = 'CLEARED_UNACKED'
    NORMAL = 'NORMAL'


class AlarmEventType(Enum):
    ACTIVATED = 'ACTIVATED'
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    CLEARED = 'CLEARED'
    SHELVED = 'SHELVED'
    UNSHELVED = 'UNSHELVED'
    SUPPRESSED = 'SUPPRESSED'
    UNSUPPRESSED = 'UNSUPPRESSED'


class AlarmType(Enum):
    HI_HI = 'HI_HI'
    HI = 'HI'
    LO = 'LO'
    LO_LO = 'LO_LO'
    RATE = 'RATE'
    DEV = 'DEV'
    DISCRETE = 'DISCRETE'
    ML = 'ML'  # Machine learning anomaly


@dataclass
class AlarmEvent:
    """Alarm event for notification"""
    instance_id: str
    alarm_id: str
    tag_id: str
    tag_name: str
    alarm_type: str
    priority: int
    status: str
    message: str
    value: float
    setpoint: float
    timestamp: datetime
    consequence: str = None
    response_instruction: str = None


@dataclass
class AlarmSummary:
    """Summary of alarm counts by status and priority"""
    total_active: int = 0
    unacknowledged: int = 0
    acknowledged_active: int = 0
    shelved: int = 0
    by_priority: Dict[int, int] = field(default_factory=dict)


class AlarmProcessor:
    """Real-time alarm processing engine"""
    
    def __init__(self):
        self._alarm_defs: Dict[str, List[AlarmDefinition]] = {}  # tag_id -> alarms
        self._active_alarms: Dict[str, ActiveAlarm] = {}  # instance_id -> alarm
        self._pending_activations: Dict[str, datetime] = {}  # alarm_id -> activation_time
        self._pending_clears: Dict[str, datetime] = {}  # instance_id -> clear_time
        self._subscribers: List[asyncio.Queue] = []
        self._current_state_id: Optional[str] = None
        self._lock = asyncio.Lock()
    
    def load_alarm_definitions(self, alarms: List[AlarmDefinition]):
        """Load alarm definitions into memory for fast evaluation"""
        self._alarm_defs.clear()
        for alarm in alarms:
            tag_id = str(alarm.tag_id)
            if tag_id not in self._alarm_defs:
                self._alarm_defs[tag_id] = []
            self._alarm_defs[tag_id].append(alarm)
        logger.info(f"Loaded {len(alarms)} alarm definitions for {len(self._alarm_defs)} tags")
    
    def load_active_alarms(self, active: List[ActiveAlarm]):
        """Load active alarms into memory"""
        self._active_alarms = {str(a.instance_id): a for a in active}
        logger.info(f"Loaded {len(active)} active alarms")
    
    def set_operating_state(self, state_id: str):
        """Set current operating state for state-based alarming"""
        self._current_state_id = state_id
        logger.info(f"Operating state set to: {state_id}")
    
    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to alarm events"""
        queue = asyncio.Queue(maxsize=1000)
        self._subscribers.append(queue)
        return queue
    
    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from alarm events"""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
    
    async def _notify_subscribers(self, event: AlarmEvent):
        """Notify all subscribers of alarm event"""
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Alarm subscriber queue full, dropping event")
    
    async def evaluate_tag(
        self, 
        tag_id: str, 
        tag_name: str,
        value: float, 
        timestamp: datetime,
        session: Session
    ) -> List[AlarmEvent]:
        """
        Evaluate tag value against all configured alarms.
        
        Returns list of alarm events generated.
        """
        events = []
        alarms = self._alarm_defs.get(tag_id, [])
        
        for alarm in alarms:
            if not alarm.is_enabled:
                continue
            
            # Get effective setpoint (may be state-specific)
            setpoint = self._get_effective_setpoint(alarm)
            if setpoint is None:
                continue
            
            # Check if suppressed for current state
            if self._is_suppressed(alarm):
                continue
            
            # Evaluate alarm condition
            in_alarm = self._check_condition(alarm, value, float(setpoint))
            
            # Handle alarm state transitions
            event = await self._process_alarm_state(
                alarm, tag_id, tag_name, value, float(setpoint), 
                timestamp, in_alarm, session
            )
            
            if event:
                events.append(event)
                await self._notify_subscribers(event)
        
        return events
    
    def _get_effective_setpoint(self, alarm: AlarmDefinition) -> Optional[float]:
        """Get effective setpoint considering current operating state"""
        if self._current_state_id and alarm.state_limits:
            for limit in alarm.state_limits:
                if str(limit.state_id) == self._current_state_id:
                    return float(limit.setpoint) if limit.setpoint else None
        
        return float(alarm.setpoint) if alarm.setpoint else None
    
    def _is_suppressed(self, alarm: AlarmDefinition) -> bool:
        """Check if alarm is suppressed for current state"""
        if self._current_state_id and alarm.state_limits:
            for limit in alarm.state_limits:
                if str(limit.state_id) == self._current_state_id:
                    return limit.is_suppressed
        return False
    
    def _check_condition(self, alarm: AlarmDefinition, value: float, setpoint: float) -> bool:
        """Check if alarm condition is met"""
        deadband = float(alarm.deadband or 0)
        
        if alarm.alarm_type == AlarmType.HI_HI.value:
            return value >= setpoint
        elif alarm.alarm_type == AlarmType.HI.value:
            return value >= setpoint
        elif alarm.alarm_type == AlarmType.LO.value:
            return value <= setpoint
        elif alarm.alarm_type == AlarmType.LO_LO.value:
            return value <= setpoint
        elif alarm.alarm_type == AlarmType.DISCRETE.value:
            return value != 0
        elif alarm.alarm_type == AlarmType.ML.value:
            # ML alarms are triggered externally
            return False
        
        return False
    
    async def _process_alarm_state(
        self,
        alarm: AlarmDefinition,
        tag_id: str,
        tag_name: str,
        value: float,
        setpoint: float,
        timestamp: datetime,
        in_alarm: bool,
        session: Session
    ) -> Optional[AlarmEvent]:
        """Process alarm state transition"""
        alarm_id = str(alarm.alarm_id)
        
        # Find existing active alarm
        existing = None
        for instance_id, active in self._active_alarms.items():
            if str(active.alarm_id) == alarm_id:
                existing = active
                break
        
        if in_alarm and not existing:
            # New alarm activation
            # Check on-delay
            if alarm.on_delay_ms and alarm.on_delay_ms > 0:
                if alarm_id not in self._pending_activations:
                    self._pending_activations[alarm_id] = timestamp
                    return None
                elif (timestamp - self._pending_activations[alarm_id]).total_seconds() * 1000 < alarm.on_delay_ms:
                    return None
                else:
                    del self._pending_activations[alarm_id]
            
            # Create active alarm
            instance_id = str(uuid.uuid4())
            active_alarm = ActiveAlarm(
                instance_id=instance_id,
                alarm_id=alarm.alarm_id,
                tag_id=tag_id,
                status=AlarmStatus.ACTIVE_UNACKED.value,
                priority=alarm.priority,
                alarm_value=value,
                alarm_time=timestamp
            )
            session.add(active_alarm)
            self._active_alarms[instance_id] = active_alarm
            
            # Log to history
            history = AlarmHistory(
                instance_id=instance_id,
                alarm_id=alarm.alarm_id,
                tag_id=tag_id,
                event_type=AlarmEventType.ACTIVATED.value,
                event_time=timestamp,
                priority=alarm.priority,
                alarm_value=value
            )
            session.add(history)
            
            # Get units from tag
            tag = session.query(Tag).filter(Tag.tag_id == tag_id).first()
            units = tag.eng_units if tag and tag.eng_units else ''

            # Format message
            message = alarm.message_template.format(
                tag_name=tag_name,
                value=value,
                setpoint=setpoint,
                units=units
            ) if alarm.message_template else f"{tag_name} {alarm.alarm_type} alarm"
            
            logger.info(f"Alarm activated: {tag_name} - {alarm.alarm_type} (Priority {alarm.priority})")
            
            return AlarmEvent(
                instance_id=instance_id,
                alarm_id=alarm_id,
                tag_id=tag_id,
                tag_name=tag_name,
                alarm_type=alarm.alarm_type,
                priority=alarm.priority,
                status=AlarmStatus.ACTIVE_UNACKED.value,
                message=message,
                value=value,
                setpoint=setpoint,
                timestamp=timestamp,
                consequence=alarm.consequence,
                response_instruction=alarm.response_instruction
            )
        
        elif not in_alarm and existing:
            # Alarm clearing
            instance_id = str(existing.instance_id)
            
            # Check off-delay
            if alarm.off_delay_ms and alarm.off_delay_ms > 0:
                if instance_id not in self._pending_clears:
                    self._pending_clears[instance_id] = timestamp
                    return None
                elif (timestamp - self._pending_clears[instance_id]).total_seconds() * 1000 < alarm.off_delay_ms:
                    return None
                else:
                    del self._pending_clears[instance_id]
            
            # Update status based on acknowledgment
            if existing.ack_time:
                # Already acknowledged - can remove
                session.delete(existing)
                del self._active_alarms[instance_id]
                new_status = AlarmStatus.NORMAL.value
            else:
                # Not acknowledged - mark as cleared but keep
                existing.status = AlarmStatus.CLEARED_UNACKED.value
                existing.clear_time = timestamp
                new_status = AlarmStatus.CLEARED_UNACKED.value
            
            # Log to history
            history = AlarmHistory(
                instance_id=instance_id,
                alarm_id=alarm.alarm_id,
                tag_id=tag_id,
                event_type=AlarmEventType.CLEARED.value,
                event_time=timestamp,
                priority=alarm.priority,
                alarm_value=value
            )
            session.add(history)
            
            logger.info(f"Alarm cleared: {tag_name} - {alarm.alarm_type}")
            
            return AlarmEvent(
                instance_id=instance_id,
                alarm_id=alarm_id,
                tag_id=tag_id,
                tag_name=tag_name,
                alarm_type=alarm.alarm_type,
                priority=alarm.priority,
                status=new_status,
                message=f"{tag_name} alarm cleared",
                value=value,
                setpoint=setpoint,
                timestamp=timestamp
            )
        
        elif in_alarm and existing:
            # Clear any pending clear
            instance_id = str(existing.instance_id)
            if instance_id in self._pending_clears:
                del self._pending_clears[instance_id]
            
            # Update value
            existing.alarm_value = value
        
        return None


# Global alarm processor instance
alarm_processor = AlarmProcessor()


class AlarmService:
    """Alarm management operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    # =========================================================================
    # ALARM DEFINITIONS
    # =========================================================================
    
    def create_alarm(self, alarm_data: Dict[str, Any]) -> AlarmDefinition:
        """Create an alarm definition"""
        alarm = AlarmDefinition(
            alarm_id=uuid.uuid4(),
            tag_id=alarm_data['tag_id'],
            alarm_type=alarm_data['alarm_type'],
            priority=alarm_data['priority'],
            setpoint=alarm_data.get('setpoint'),
            deadband=alarm_data.get('deadband', 0),
            on_delay_ms=alarm_data.get('on_delay_ms', 0),
            off_delay_ms=alarm_data.get('off_delay_ms', 0),
            message_template=alarm_data.get('message_template', '{tag_name} {alarm_type} alarm'),
            consequence=alarm_data.get('consequence'),
            response_instruction=alarm_data.get('response_instruction'),
            is_enabled=alarm_data.get('is_enabled', True),
            created_by=alarm_data.get('created_by')
        )
        self.session.add(alarm)
        self.session.flush()
        logger.info(f"Created alarm {alarm.alarm_type} for tag {alarm.tag_id}")
        return alarm
    
    def get_alarm(self, alarm_id: str) -> Optional[AlarmDefinition]:
        """Get alarm definition by ID"""
        return self.session.query(AlarmDefinition).filter(
            AlarmDefinition.alarm_id == alarm_id
        ).first()
    
    def get_alarms_for_tag(self, tag_id: str) -> List[AlarmDefinition]:
        """Get all alarms for a tag"""
        return self.session.query(AlarmDefinition).filter(
            AlarmDefinition.tag_id == tag_id
        ).all()
    
    def get_all_alarms(self, enabled_only: bool = False) -> List[AlarmDefinition]:
        """Get all alarm definitions"""
        query = self.session.query(AlarmDefinition)
        if enabled_only:
            query = query.filter(AlarmDefinition.is_enabled == True)
        return query.all()
    
    def update_alarm(self, alarm_id: str, updates: Dict[str, Any]) -> Optional[AlarmDefinition]:
        """Update alarm definition"""
        alarm = self.get_alarm(alarm_id)
        if not alarm:
            return None
        
        for key, value in updates.items():
            if hasattr(alarm, key) and key not in ('alarm_id', 'created_at'):
                setattr(alarm, key, value)
        
        alarm.updated_at = datetime.utcnow()
        self.session.flush()
        return alarm
    
    def enable_alarm(self, alarm_id: str) -> bool:
        """Enable an alarm"""
        alarm = self.get_alarm(alarm_id)
        if alarm:
            alarm.is_enabled = True
            alarm.updated_at = datetime.utcnow()
            return True
        return False
    
    def disable_alarm(self, alarm_id: str) -> bool:
        """Disable an alarm"""
        alarm = self.get_alarm(alarm_id)
        if alarm:
            alarm.is_enabled = False
            alarm.updated_at = datetime.utcnow()
            return True
        return False
    
    # =========================================================================
    # ACTIVE ALARMS
    # =========================================================================
    
    def get_active_alarms(
        self, 
        priority: int = None,
        status: str = None,
        include_shelved: bool = True
    ) -> List[ActiveAlarm]:
        """Get active alarms with filtering"""
        query = self.session.query(ActiveAlarm)
        
        if priority:
            query = query.filter(ActiveAlarm.priority == priority)
        if status:
            query = query.filter(ActiveAlarm.status == status)
        if not include_shelved:
            query = query.filter(
                or_(
                    ActiveAlarm.shelved_until.is_(None),
                    ActiveAlarm.shelved_until < datetime.utcnow()
                )
            )
        
        return query.order_by(
            ActiveAlarm.priority,
            ActiveAlarm.alarm_time.desc()
        ).all()
    
    def get_standing_alarms(self) -> List[ActiveAlarm]:
        """Get all unacknowledged alarms"""
        return self.session.query(ActiveAlarm).filter(
            ActiveAlarm.status == AlarmStatus.ACTIVE_UNACKED.value
        ).order_by(
            ActiveAlarm.priority,
            ActiveAlarm.alarm_time.desc()
        ).all()
    
    def acknowledge(
        self, 
        instance_id: str, 
        user_id: str, 
        notes: str = None
    ) -> Optional[ActiveAlarm]:
        """Acknowledge an alarm"""
        alarm = self.session.query(ActiveAlarm).filter(
            ActiveAlarm.instance_id == instance_id
        ).first()
        
        if not alarm:
            return None
        
        now = datetime.utcnow()
        
        if alarm.status == AlarmStatus.ACTIVE_UNACKED.value:
            alarm.status = AlarmStatus.ACKED_ACTIVE.value
            alarm.ack_time = now
            alarm.ack_by = user_id
            alarm.ack_notes = notes
        elif alarm.status == AlarmStatus.CLEARED_UNACKED.value:
            # Acknowledge and remove
            self.session.delete(alarm)
            alarm_processor._active_alarms.pop(instance_id, None)
        
        # Log to history
        history = AlarmHistory(
            instance_id=instance_id,
            alarm_id=alarm.alarm_id,
            tag_id=alarm.tag_id,
            event_type=AlarmEventType.ACKNOWLEDGED.value,
            event_time=now,
            priority=alarm.priority,
            user_id=user_id,
            notes=notes
        )
        self.session.add(history)
        
        logger.info(f"Alarm acknowledged: {instance_id} by {user_id}")
        return alarm
    
    def acknowledge_all(self, user_id: str, priority: int = None) -> int:
        """Acknowledge all active alarms"""
        query = self.session.query(ActiveAlarm).filter(
            ActiveAlarm.status == AlarmStatus.ACTIVE_UNACKED.value
        )
        
        if priority:
            query = query.filter(ActiveAlarm.priority == priority)
        
        alarms = query.all()
        count = 0
        now = datetime.utcnow()
        
        for alarm in alarms:
            alarm.status = AlarmStatus.ACKED_ACTIVE.value
            alarm.ack_time = now
            alarm.ack_by = user_id
            
            history = AlarmHistory(
                instance_id=alarm.instance_id,
                alarm_id=alarm.alarm_id,
                tag_id=alarm.tag_id,
                event_type=AlarmEventType.ACKNOWLEDGED.value,
                event_time=now,
                priority=alarm.priority,
                user_id=user_id
            )
            self.session.add(history)
            count += 1
        
        logger.info(f"Acknowledged {count} alarms by {user_id}")
        return count
    
    def shelve(
        self, 
        instance_id: str, 
        user_id: str, 
        duration_minutes: int,
        reason: str
    ) -> Optional[ActiveAlarm]:
        """Temporarily suppress an alarm"""
        alarm = self.session.query(ActiveAlarm).filter(
            ActiveAlarm.instance_id == instance_id
        ).first()
        
        if not alarm:
            return None
        
        now = datetime.utcnow()
        alarm.shelved_until = now + timedelta(minutes=duration_minutes)
        alarm.shelved_by = user_id
        alarm.shelve_reason = reason
        
        # Log to history
        history = AlarmHistory(
            instance_id=instance_id,
            alarm_id=alarm.alarm_id,
            tag_id=alarm.tag_id,
            event_type=AlarmEventType.SHELVED.value,
            event_time=now,
            priority=alarm.priority,
            user_id=user_id,
            notes=f"Shelved for {duration_minutes} min: {reason}"
        )
        self.session.add(history)
        
        logger.info(f"Alarm shelved: {instance_id} for {duration_minutes} min by {user_id}")
        return alarm
    
    def unshelve(self, instance_id: str, user_id: str) -> Optional[ActiveAlarm]:
        """Remove shelving from an alarm"""
        alarm = self.session.query(ActiveAlarm).filter(
            ActiveAlarm.instance_id == instance_id
        ).first()
        
        if not alarm:
            return None
        
        alarm.shelved_until = None
        alarm.shelved_by = None
        alarm.shelve_reason = None
        
        # Log to history
        history = AlarmHistory(
            instance_id=instance_id,
            alarm_id=alarm.alarm_id,
            tag_id=alarm.tag_id,
            event_type=AlarmEventType.UNSHELVED.value,
            event_time=datetime.utcnow(),
            priority=alarm.priority,
            user_id=user_id
        )
        self.session.add(history)
        
        return alarm
    
    def get_alarm_summary(self) -> AlarmSummary:
        """Get summary of active alarms"""
        active = self.session.query(ActiveAlarm).all()
        
        summary = AlarmSummary()
        summary.total_active = len(active)
        
        for alarm in active:
            # By status
            if alarm.status == AlarmStatus.ACTIVE_UNACKED.value:
                summary.unacknowledged += 1
            elif alarm.status == AlarmStatus.ACKED_ACTIVE.value:
                summary.acknowledged_active += 1
            
            # Shelved
            if alarm.shelved_until and alarm.shelved_until > datetime.utcnow():
                summary.shelved += 1
            
            # By priority
            if alarm.priority not in summary.by_priority:
                summary.by_priority[alarm.priority] = 0
            summary.by_priority[alarm.priority] += 1
        
        return summary
    
    # =========================================================================
    # ALARM HISTORY
    # =========================================================================
    
    def get_alarm_history(
        self,
        alarm_id: str = None,
        tag_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        event_types: List[str] = None,
        limit: int = 1000
    ) -> List[AlarmHistory]:
        """Query alarm history"""
        query = self.session.query(AlarmHistory)
        
        if alarm_id:
            query = query.filter(AlarmHistory.alarm_id == alarm_id)
        if tag_id:
            query = query.filter(AlarmHistory.tag_id == tag_id)
        if start_time:
            query = query.filter(AlarmHistory.event_time >= start_time)
        if end_time:
            query = query.filter(AlarmHistory.event_time <= end_time)
        if event_types:
            query = query.filter(AlarmHistory.event_type.in_(event_types))
        
        return query.order_by(AlarmHistory.event_time.desc()).limit(limit).all()
    
    # =========================================================================
    # ANALYTICS
    # =========================================================================
    
    def get_top_alarms(self, days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most frequent alarms"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        result = self.session.query(
            AlarmHistory.alarm_id,
            func.count(AlarmHistory.id).label('count')
        ).filter(
            AlarmHistory.event_time >= start_time,
            AlarmHistory.event_type == AlarmEventType.ACTIVATED.value
        ).group_by(
            AlarmHistory.alarm_id
        ).order_by(
            func.count(AlarmHistory.id).desc()
        ).limit(limit).all()
        
        return [{'alarm_id': str(r.alarm_id), 'count': r.count} for r in result]
    
    def get_chattering_alarms(self, days: int = 7, threshold: int = 10) -> List[Dict[str, Any]]:
        """Get alarms that activate too frequently (potential chattering)"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # Alarms with more than threshold activations per day
        result = self.session.query(
            AlarmHistory.alarm_id,
            func.count(AlarmHistory.id).label('count')
        ).filter(
            AlarmHistory.event_time >= start_time,
            AlarmHistory.event_type == AlarmEventType.ACTIVATED.value
        ).group_by(
            AlarmHistory.alarm_id
        ).having(
            func.count(AlarmHistory.id) > threshold * days
        ).order_by(
            func.count(AlarmHistory.id).desc()
        ).all()
        
        return [{'alarm_id': str(r.alarm_id), 'count': r.count, 'per_day': r.count / days} 
                for r in result]
    
    def get_response_time_stats(self, days: int = 30) -> Dict[str, float]:
        """Get average acknowledgment response time by priority"""
        start_time = datetime.utcnow() - timedelta(days=days)
        
        # This would need a more complex query joining activation and ack events
        # Simplified version
        return {
            'avg_response_seconds': 0,
            'by_priority': {}
        }


# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_alarm_processor(session: Session):
    """Load alarm definitions and active alarms into processor"""
    service = AlarmService(session)
    
    # Load definitions
    alarms = service.get_all_alarms(enabled_only=True)
    alarm_processor.load_alarm_definitions(alarms)
    
    # Load active alarms
    active = service.get_active_alarms()
    alarm_processor.load_active_alarms(active)


async def process_tag_value(
    tag_id: str, 
    tag_name: str,
    value: float, 
    timestamp: datetime = None
) -> List[AlarmEvent]:
    """Process a tag value through the alarm system"""
    timestamp = timestamp or datetime.utcnow()
    
    with get_session() as session:
        events = await alarm_processor.evaluate_tag(
            tag_id, tag_name, value, timestamp, session
        )
    
    return events
