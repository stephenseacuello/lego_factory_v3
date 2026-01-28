"""
LEGO Factory v3 - Alarm Management Service (ISA-18.2)
=====================================================
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

from config.database import get_db_session

logger = logging.getLogger(__name__)


def _emit_alarm_event(event_type: str, data: Dict[str, Any]):
    """
    Emit alarm event to WebSocket clients.
    Gracefully handles case where SocketIO isn't initialized.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace, emit_to_room

        # Emit to /alarms namespace for all alarm subscribers
        emit_to_namespace(event_type, data, namespace='/alarms')

        # Also notify SCADA users room
        emit_to_room(event_type, data, room='scada', namespace='/')

        logger.debug(f"Emitted alarm event: {event_type}")
    except ImportError:
        logger.debug("WebSocket service not available, skipping alarm emit")
    except Exception as e:
        logger.warning(f"Failed to emit alarm event: {e}")


class AlarmPriority(Enum):
    EMERGENCY = 1
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
    HIGH_HIGH = 'high_high'
    HIGH = 'high'
    LOW = 'low'
    LOW_LOW = 'low_low'
    RATE_OF_CHANGE = 'rate_of_change'
    DEVIATION = 'deviation'
    DIGITAL = 'digital'
    BAD_QUALITY = 'bad_quality'
    ML_ANOMALY = 'ml_anomaly'


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
    limit_value: float
    timestamp: datetime
    consequence: str = None
    corrective_action: str = None


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

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._alarm_defs = {}  # tag_id -> List[alarms]
            cls._instance._active_alarms = {}  # instance_id -> alarm
            cls._instance._pending_activations = {}
            cls._instance._pending_clears = {}
            cls._instance._subscribers = []
            cls._instance._ml_alarms = {}  # instance_id -> AlarmEvent for ML-generated alarms
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    def load_alarm_definitions(self, alarms: List[Any]):
        """Load alarm definitions into memory for fast evaluation"""
        self._alarm_defs.clear()
        for alarm in alarms:
            tag_id = str(alarm.tag_id)
            if tag_id not in self._alarm_defs:
                self._alarm_defs[tag_id] = []
            self._alarm_defs[tag_id].append(alarm)
        logger.info(f"Loaded {len(alarms)} alarm definitions for {len(self._alarm_defs)} tags")

    def load_active_alarms(self, active: List[Any]):
        """Load active alarms into memory"""
        self._active_alarms = {str(a.id): a for a in active}
        logger.info(f"Loaded {len(active)} active alarms")

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

        # Emit to WebSocket clients
        event_data = {
            'instance_id': event.instance_id,
            'alarm_id': event.alarm_id,
            'tag_id': event.tag_id,
            'tag_name': event.tag_name,
            'alarm_type': event.alarm_type,
            'priority': event.priority,
            'status': event.status,
            'message': event.message,
            'value': event.value,
            'limit_value': event.limit_value,
            'timestamp': event.timestamp.isoformat(),
            'consequence': event.consequence,
            'corrective_action': event.corrective_action,
        }

        # Determine event type based on status
        if event.status == AlarmStatus.ACTIVE_UNACKED.value:
            _emit_alarm_event('alarm_triggered', event_data)
        elif event.status == AlarmStatus.CLEARED_UNACKED.value or event.status == AlarmStatus.NORMAL.value:
            _emit_alarm_event('alarm_cleared', event_data)

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
            if not alarm.enabled:
                continue

            # Check alarm condition based on type
            in_alarm = self._check_condition(alarm, value)

            # Handle alarm state transitions
            event = await self._process_alarm_state(
                alarm, tag_id, tag_name, value, timestamp, in_alarm, session
            )

            if event:
                events.append(event)
                await self._notify_subscribers(event)

        return events

    def _check_condition(self, alarm, value: float) -> bool:
        """Check if alarm condition is met"""
        alarm_type = alarm.alarm_type.value if hasattr(alarm.alarm_type, 'value') else alarm.alarm_type
        deadband = float(alarm.deadband or 0) if hasattr(alarm, 'deadband') else 0

        if alarm_type == 'high_high' and alarm.high_high_limit is not None:
            return value >= float(alarm.high_high_limit)
        elif alarm_type == 'high' and alarm.high_limit is not None:
            return value >= float(alarm.high_limit)
        elif alarm_type == 'low' and alarm.low_limit is not None:
            return value <= float(alarm.low_limit)
        elif alarm_type == 'low_low' and alarm.low_low_limit is not None:
            return value <= float(alarm.low_low_limit)
        elif alarm_type == 'digital':
            return value != 0

        return False

    async def _process_alarm_state(
        self,
        alarm,
        tag_id: str,
        tag_name: str,
        value: float,
        timestamp: datetime,
        in_alarm: bool,
        session: Session
    ) -> Optional[AlarmEvent]:
        """Process alarm state transition"""
        alarm_id = str(alarm.id)

        # Find existing active alarm
        existing = None
        for instance_id, active in self._active_alarms.items():
            if str(active.alarm_id) == alarm_id:
                existing = active
                break

        if in_alarm and not existing:
            # New alarm activation - create event
            instance_id = str(uuid.uuid4())

            # Get limit value for the alarm type
            alarm_type = alarm.alarm_type.value if hasattr(alarm.alarm_type, 'value') else alarm.alarm_type
            limit_value = getattr(alarm, f'{alarm_type}_limit', alarm.setpoint) or 0

            message = f"{tag_name} {alarm_type.upper()} alarm: {value} exceeds {limit_value}"

            logger.info(f"Alarm activated: {tag_name} - {alarm_type} (Priority {alarm.priority.value})")

            return AlarmEvent(
                instance_id=instance_id,
                alarm_id=alarm_id,
                tag_id=tag_id,
                tag_name=tag_name,
                alarm_type=alarm_type,
                priority=alarm.priority.value if hasattr(alarm.priority, 'value') else alarm.priority,
                status=AlarmStatus.ACTIVE_UNACKED.value,
                message=message,
                value=value,
                limit_value=float(limit_value) if limit_value else 0,
                timestamp=timestamp,
                consequence=alarm.consequence,
                corrective_action=alarm.corrective_action
            )

        elif not in_alarm and existing:
            # Alarm clearing
            instance_id = str(existing.id)
            alarm_type = alarm.alarm_type.value if hasattr(alarm.alarm_type, 'value') else alarm.alarm_type

            logger.info(f"Alarm cleared: {tag_name} - {alarm_type}")

            return AlarmEvent(
                instance_id=instance_id,
                alarm_id=alarm_id,
                tag_id=tag_id,
                tag_name=tag_name,
                alarm_type=alarm_type,
                priority=alarm.priority.value if hasattr(alarm.priority, 'value') else alarm.priority,
                status=AlarmStatus.CLEARED_UNACKED.value if not existing.is_acknowledged else AlarmStatus.NORMAL.value,
                message=f"{tag_name} alarm cleared",
                value=value,
                limit_value=0,
                timestamp=timestamp
            )

        return None

    def submit_ml_alarm(self, alarm_event: AlarmEvent):
        """
        Submit an ML-generated alarm to the alarm system.

        This method receives alarms from the anomaly detection service and:
        1. Stores in memory for active alarm tracking
        2. Persists to the database for history
        3. Broadcasts to subscribers and WebSocket clients
        4. Handles deduplication based on alarm_id

        Args:
            alarm_event: The AlarmEvent generated by ML anomaly detection
        """
        try:
            # Check if this alarm is already active (by alarm_id)
            existing_instance = None
            for instance_id, existing in self._ml_alarms.items():
                if existing.alarm_id == alarm_event.alarm_id:
                    existing_instance = instance_id
                    break

            if existing_instance:
                # Update existing alarm
                logger.debug(f"Updating existing ML alarm: {alarm_event.alarm_id}")
                self._ml_alarms[existing_instance] = alarm_event
            else:
                # New alarm
                self._ml_alarms[alarm_event.instance_id] = alarm_event
                logger.info(
                    f"ML alarm activated: {alarm_event.tag_name} - "
                    f"{alarm_event.alarm_type} (Priority {alarm_event.priority})"
                )

            # Persist to database
            self._persist_ml_alarm(alarm_event)

            # Notify subscribers and broadcast via WebSocket
            # Use asyncio.create_task if in async context, otherwise run sync
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._notify_subscribers(alarm_event))
            except RuntimeError:
                # No event loop running, emit directly via WebSocket
                event_data = {
                    'instance_id': alarm_event.instance_id,
                    'alarm_id': alarm_event.alarm_id,
                    'tag_id': alarm_event.tag_id,
                    'tag_name': alarm_event.tag_name,
                    'alarm_type': alarm_event.alarm_type,
                    'priority': alarm_event.priority,
                    'status': alarm_event.status,
                    'message': alarm_event.message,
                    'value': alarm_event.value,
                    'limit_value': alarm_event.limit_value,
                    'timestamp': alarm_event.timestamp.isoformat(),
                    'consequence': alarm_event.consequence,
                    'corrective_action': alarm_event.corrective_action,
                    'source': 'ml_anomaly',
                }
                _emit_alarm_event('alarm_triggered', event_data)

        except Exception as e:
            logger.error(f"Failed to submit ML alarm: {e}")
            raise

    def _persist_ml_alarm(self, alarm_event: AlarmEvent):
        """Persist ML alarm event to database."""
        try:
            from models.scada.alarms import AlarmEvent as AlarmEventModel

            with get_db_session() as session:
                db_event = AlarmEventModel(
                    timestamp=alarm_event.timestamp,
                    alarm_id=alarm_event.alarm_id,
                    event_type='ml_anomaly_activate',
                    previous_state='normal',
                    new_state=alarm_event.status,
                    trigger_value=alarm_event.value,
                    limit_value=alarm_event.limit_value,
                    priority=alarm_event.priority,
                    comment=alarm_event.message,
                )
                session.add(db_event)
                session.commit()
                logger.debug(f"Persisted ML alarm event: {alarm_event.alarm_id}")

        except Exception as e:
            logger.warning(f"Failed to persist ML alarm to database: {e}")

    def get_ml_alarms(self) -> List[AlarmEvent]:
        """Get all active ML-generated alarms."""
        return list(self._ml_alarms.values())

    def clear_ml_alarm(self, alarm_id: str) -> bool:
        """
        Clear an ML-generated alarm.

        Args:
            alarm_id: The alarm ID to clear

        Returns:
            True if alarm was found and cleared, False otherwise
        """
        instance_to_remove = None
        for instance_id, alarm in self._ml_alarms.items():
            if alarm.alarm_id == alarm_id:
                instance_to_remove = instance_id
                break

        if instance_to_remove:
            alarm = self._ml_alarms.pop(instance_to_remove)
            logger.info(f"ML alarm cleared: {alarm_id}")

            # Emit cleared event
            event_data = {
                'instance_id': alarm.instance_id,
                'alarm_id': alarm.alarm_id,
                'tag_id': alarm.tag_id,
                'tag_name': alarm.tag_name,
                'alarm_type': alarm.alarm_type,
                'priority': alarm.priority,
                'status': AlarmStatus.NORMAL.value,
                'message': f"{alarm.tag_name} ML anomaly alarm cleared",
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'ml_anomaly',
            }
            _emit_alarm_event('alarm_cleared', event_data)

            return True

        return False


# Global alarm processor instance
alarm_processor = AlarmProcessor()


class AlarmService:
    """Alarm management operations"""

    def __init__(self, session: Session):
        self.session = session

    def create_alarm(self, alarm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create an alarm definition"""
        from models.scada.alarms import AlarmDefinition, AlarmPriority, AlarmClass, AlarmType

        alarm = AlarmDefinition(
            alarm_id=alarm_data['alarm_id'],
            name=alarm_data['name'],
            description=alarm_data.get('description'),
            priority=AlarmPriority(alarm_data['priority']),
            alarm_class=AlarmClass(alarm_data.get('alarm_class', 'process')),
            alarm_type=AlarmType(alarm_data['alarm_type']),
            tag_id=alarm_data['tag_id'],
            setpoint=alarm_data.get('setpoint'),
            high_limit=alarm_data.get('high_limit'),
            high_high_limit=alarm_data.get('high_high_limit'),
            low_limit=alarm_data.get('low_limit'),
            low_low_limit=alarm_data.get('low_low_limit'),
            deviation_limit=alarm_data.get('deviation_limit'),
            rate_limit=alarm_data.get('rate_limit'),
            deadband=alarm_data.get('deadband', 0),
            on_delay_seconds=alarm_data.get('on_delay_seconds', 0),
            off_delay_seconds=alarm_data.get('off_delay_seconds', 0),
            consequence=alarm_data.get('consequence'),
            corrective_action=alarm_data.get('corrective_action'),
            enabled=alarm_data.get('enabled', True),
        )
        self.session.add(alarm)
        self.session.flush()
        logger.info(f"Created alarm {alarm.alarm_id}")
        return alarm.to_dict()

    def get_alarm(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Get alarm definition by ID"""
        from models.scada.alarms import AlarmDefinition
        alarm = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.alarm_id == alarm_id
        ).first()
        return alarm.to_dict() if alarm else None

    def get_alarms_for_tag(self, tag_id: str) -> List[Dict[str, Any]]:
        """Get all alarms for a tag"""
        from models.scada.alarms import AlarmDefinition
        alarms = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.tag_id == tag_id
        ).all()
        return [a.to_dict() for a in alarms]

    def get_all_alarms(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Get all alarm definitions"""
        from models.scada.alarms import AlarmDefinition
        query = self.session.query(AlarmDefinition)
        if enabled_only:
            query = query.filter(AlarmDefinition.enabled == True)
        alarms = query.all()
        return [a.to_dict() for a in alarms]

    def get_active_alarms(
        self,
        priority: int = None,
        include_shelved: bool = True
    ) -> List[Dict[str, Any]]:
        """Get active alarms with filtering"""
        from models.scada.alarms import AlarmDefinition

        query = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.is_active == True
        )

        if priority:
            query = query.filter(AlarmDefinition.priority == priority)
        if not include_shelved:
            query = query.filter(
                or_(
                    AlarmDefinition.shelved_until.is_(None),
                    AlarmDefinition.shelved_until < datetime.utcnow()
                )
            )

        alarms = query.order_by(
            AlarmDefinition.priority,
            AlarmDefinition.last_activation.desc()
        ).all()
        return [a.to_dict() for a in alarms]

    def get_standing_alarms(self) -> List[Dict[str, Any]]:
        """Get all unacknowledged alarms"""
        from models.scada.alarms import AlarmDefinition

        alarms = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.is_active == True,
            AlarmDefinition.is_acknowledged == False
        ).order_by(
            AlarmDefinition.priority,
            AlarmDefinition.last_activation.desc()
        ).all()
        return [a.to_dict() for a in alarms]

    def acknowledge(
        self,
        alarm_id: str,
        user_id: str,
        notes: str = None
    ) -> Optional[Dict[str, Any]]:
        """Acknowledge an alarm"""
        from models.scada.alarms import AlarmDefinition

        alarm = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.alarm_id == alarm_id
        ).first()

        if not alarm:
            return None

        alarm.is_acknowledged = True
        alarm.last_ack = datetime.utcnow()
        self.session.flush()

        logger.info(f"Alarm acknowledged: {alarm_id} by {user_id}")

        # Emit WebSocket event for alarm acknowledgment
        alarm_data = alarm.to_dict()
        _emit_alarm_event('alarm_acknowledged', {
            'alarm_id': alarm_id,
            'acknowledged_by': user_id,
            'acknowledged_at': datetime.utcnow().isoformat(),
            'notes': notes,
            'alarm': alarm_data,
        })

        return alarm_data

    def acknowledge_all(self, user_id: str, priority: int = None) -> int:
        """Acknowledge all active alarms"""
        from models.scada.alarms import AlarmDefinition

        query = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.is_active == True,
            AlarmDefinition.is_acknowledged == False
        )

        if priority:
            query = query.filter(AlarmDefinition.priority == priority)

        count = query.update({
            'is_acknowledged': True,
            'last_ack': datetime.utcnow()
        })

        logger.info(f"Acknowledged {count} alarms by {user_id}")

        # Emit WebSocket event for bulk acknowledgment
        _emit_alarm_event('alarms_acknowledged_bulk', {
            'acknowledged_by': user_id,
            'acknowledged_at': datetime.utcnow().isoformat(),
            'count': count,
            'priority_filter': priority,
        })

        return count

    def shelve(
        self,
        alarm_id: str,
        user_id: str,
        duration_minutes: int,
        reason: str
    ) -> Optional[Dict[str, Any]]:
        """Temporarily suppress an alarm"""
        from models.scada.alarms import AlarmDefinition

        alarm = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.alarm_id == alarm_id
        ).first()

        if not alarm:
            return None

        shelved_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        alarm.is_shelved = True
        alarm.shelved_until = shelved_until
        alarm.shelved_by = user_id
        alarm.shelve_reason = reason
        self.session.flush()

        logger.info(f"Alarm shelved: {alarm_id} for {duration_minutes} min by {user_id}")

        # Emit WebSocket event for alarm shelving
        alarm_data = alarm.to_dict()
        _emit_alarm_event('alarm_shelved', {
            'alarm_id': alarm_id,
            'shelved_by': user_id,
            'shelved_at': datetime.utcnow().isoformat(),
            'shelved_until': shelved_until.isoformat(),
            'duration_minutes': duration_minutes,
            'reason': reason,
            'alarm': alarm_data,
        })

        return alarm_data

    def unshelve(self, alarm_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Remove shelving from an alarm"""
        from models.scada.alarms import AlarmDefinition

        alarm = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.alarm_id == alarm_id
        ).first()

        if not alarm:
            return None

        alarm.is_shelved = False
        alarm.shelved_until = None
        alarm.shelved_by = None
        alarm.shelve_reason = None
        self.session.flush()

        # Emit WebSocket event for alarm unshelving
        alarm_data = alarm.to_dict()
        _emit_alarm_event('alarm_unshelved', {
            'alarm_id': alarm_id,
            'unshelved_by': user_id,
            'unshelved_at': datetime.utcnow().isoformat(),
            'alarm': alarm_data,
        })

        return alarm_data

    def get_alarm_summary(self) -> AlarmSummary:
        """Get summary of active alarms"""
        from models.scada.alarms import AlarmDefinition

        alarms = self.session.query(AlarmDefinition).filter(
            AlarmDefinition.is_active == True
        ).all()

        summary = AlarmSummary()
        summary.total_active = len(alarms)

        for alarm in alarms:
            if not alarm.is_acknowledged:
                summary.unacknowledged += 1
            else:
                summary.acknowledged_active += 1

            if alarm.is_shelved and alarm.shelved_until and alarm.shelved_until > datetime.utcnow():
                summary.shelved += 1

            priority_val = alarm.priority.value if hasattr(alarm.priority, 'value') else alarm.priority
            if priority_val not in summary.by_priority:
                summary.by_priority[priority_val] = 0
            summary.by_priority[priority_val] += 1

        return summary

    def get_alarm_history(
        self,
        alarm_id: str = None,
        tag_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Query alarm history"""
        from models.scada.alarms import AlarmEvent

        query = self.session.query(AlarmEvent)

        if alarm_id:
            query = query.filter(AlarmEvent.alarm_id == alarm_id)
        if tag_id:
            query = query.filter(AlarmEvent.tag_id == tag_id)
        if start_time:
            query = query.filter(AlarmEvent.timestamp >= start_time)
        if end_time:
            query = query.filter(AlarmEvent.timestamp <= end_time)

        events = query.order_by(AlarmEvent.timestamp.desc()).limit(limit).all()
        return [{'alarm_id': e.alarm_id, 'timestamp': e.timestamp.isoformat(),
                 'event_type': e.event_type} for e in events]


def get_alarm_service(session: Session = None) -> AlarmService:
    """Get alarm service with session"""
    if session:
        return AlarmService(session)
    with get_db_session() as session:
        return AlarmService(session)


def initialize_alarm_processor(session: Session):
    """Load alarm definitions and active alarms into processor"""
    from models.scada.alarms import AlarmDefinition

    service = AlarmService(session)

    # Load definitions
    alarms = session.query(AlarmDefinition).filter(
        AlarmDefinition.enabled == True
    ).all()
    alarm_processor.load_alarm_definitions(alarms)

    # Load active alarms
    active = session.query(AlarmDefinition).filter(
        AlarmDefinition.is_active == True
    ).all()
    alarm_processor.load_active_alarms(active)


async def process_tag_value(
    tag_id: str,
    tag_name: str,
    value: float,
    timestamp: datetime = None
) -> List[AlarmEvent]:
    """Process a tag value through the alarm system"""
    timestamp = timestamp or datetime.utcnow()

    with get_db_session() as session:
        events = await alarm_processor.evaluate_tag(
            tag_id, tag_name, value, timestamp, session
        )

    return events
