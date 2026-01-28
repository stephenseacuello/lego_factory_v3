"""
LEGO Factory v3 - Data Collector Service
=========================================
Data collection for MESA-11 Data Collection/Acquisition function.
Handles sensor data ingestion and machine event logging.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text

from models.mes.sensor_data import (
    SensorReading, DataCollectionEvent, EventType,
    MachineHeartbeat, TagDefinition
)

logger = logging.getLogger(__name__)


def _emit_data_event(event_type: str, data: Dict[str, Any]):
    """
    Emit data collection event to WebSocket clients.
    """
    try:
        from services.websocket.socket_service import emit_to_namespace
        emit_to_namespace(event_type, data, namespace='/dashboard')
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to emit data event: {e}")


class DataCollectorService:
    """Service for collecting and querying sensor/event data."""

    def __init__(self, session: Session):
        self.session = session

    # =========================================================================
    # Sensor Data Collection
    # =========================================================================

    def record_sensor_reading(
        self,
        machine_id: str,
        tag_name: str,
        value: Union[float, int, str, bool],
        timestamp: Optional[datetime] = None,
        unit: Optional[str] = None,
        quality: int = 192,
        source: Optional[str] = None,
    ) -> SensorReading:
        """
        Record a sensor reading to TimescaleDB.

        Args:
            machine_id: Machine identifier
            tag_name: Tag/sensor name
            value: Sensor value (auto-detects type)
            timestamp: Reading timestamp (defaults to now)
            unit: Unit of measure (e.g., 'mm', 'C', 'rpm')
            quality: OPC quality code (192 = good)
            source: Data source ('plc', 'sensor', 'calculated', 'manual')

        Returns:
            Created SensorReading
        """
        reading = SensorReading(
            timestamp=timestamp or datetime.utcnow(),
            machine_id=machine_id,
            tag_name=tag_name,
            unit=unit,
            quality=quality,
            source=source,
        )

        # Set value in appropriate column based on type
        if isinstance(value, bool):
            reading.value_bool = value
        elif isinstance(value, int):
            reading.value_int = value
        elif isinstance(value, float):
            reading.value_float = value
        else:
            reading.value_str = str(value)

        self.session.add(reading)
        self.session.flush()

        return reading

    def record_sensor_batch(
        self,
        readings: List[Dict[str, Any]],
    ) -> int:
        """
        Record multiple sensor readings efficiently.

        Args:
            readings: List of dicts with keys: machine_id, tag_name, value,
                     and optional: timestamp, unit, quality, source

        Returns:
            Number of readings recorded
        """
        count = 0
        for data in readings:
            try:
                self.record_sensor_reading(
                    machine_id=data['machine_id'],
                    tag_name=data['tag_name'],
                    value=data['value'],
                    timestamp=data.get('timestamp'),
                    unit=data.get('unit'),
                    quality=data.get('quality', 192),
                    source=data.get('source'),
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to record sensor reading: {e}")

        self.session.flush()
        return count

    def get_sensor_history(
        self,
        machine_id: str,
        tag_name: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query sensor history for a tag.

        Args:
            machine_id: Machine identifier
            tag_name: Tag name
            start_time: Query start time
            end_time: Query end time (defaults to now)
            limit: Maximum records to return

        Returns:
            List of sensor readings
        """
        end_time = end_time or datetime.utcnow()

        readings = self.session.query(SensorReading).filter(
            and_(
                SensorReading.machine_id == machine_id,
                SensorReading.tag_name == tag_name,
                SensorReading.timestamp >= start_time,
                SensorReading.timestamp <= end_time,
            )
        ).order_by(SensorReading.timestamp.desc()).limit(limit).all()

        return [r.to_dict() for r in readings]

    def get_sensor_aggregates(
        self,
        machine_id: str,
        tag_name: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        bucket_size: str = '1 hour',
    ) -> List[Dict[str, Any]]:
        """
        Get time-bucketed aggregates for sensor data.
        Uses TimescaleDB time_bucket if available.

        Args:
            machine_id: Machine identifier
            tag_name: Tag name
            start_time: Query start time
            end_time: Query end time
            bucket_size: Time bucket size (e.g., '1 minute', '1 hour', '1 day')

        Returns:
            List of aggregated data points
        """
        end_time = end_time or datetime.utcnow()

        # Try TimescaleDB time_bucket first
        try:
            query = text("""
                SELECT
                    time_bucket(:bucket, timestamp) AS bucket_time,
                    AVG(value_float) AS avg_value,
                    MIN(value_float) AS min_value,
                    MAX(value_float) AS max_value,
                    COUNT(*) AS count
                FROM sensor_readings
                WHERE machine_id = :machine_id
                  AND tag_name = :tag_name
                  AND timestamp >= :start_time
                  AND timestamp <= :end_time
                  AND value_float IS NOT NULL
                GROUP BY bucket_time
                ORDER BY bucket_time
            """)

            result = self.session.execute(query, {
                'bucket': bucket_size,
                'machine_id': machine_id,
                'tag_name': tag_name,
                'start_time': start_time,
                'end_time': end_time,
            })

            return [
                {
                    'timestamp': row.bucket_time.isoformat() if row.bucket_time else None,
                    'avg': row.avg_value,
                    'min': row.min_value,
                    'max': row.max_value,
                    'count': row.count,
                }
                for row in result
            ]
        except Exception as e:
            logger.warning(f"TimescaleDB aggregation failed, falling back: {e}")
            # Fallback to raw query
            return self.get_sensor_history(machine_id, tag_name, start_time, end_time)

    def get_latest_readings(
        self,
        machine_id: str,
        tag_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get latest reading for each tag on a machine.

        Args:
            machine_id: Machine identifier
            tag_names: Optional list of specific tags

        Returns:
            Dict mapping tag_name to latest reading
        """
        # Use window function to get latest per tag
        subquery = self.session.query(
            SensorReading.tag_name,
            SensorReading.value_float,
            SensorReading.value_int,
            SensorReading.value_str,
            SensorReading.value_bool,
            SensorReading.timestamp,
            SensorReading.unit,
            func.row_number().over(
                partition_by=SensorReading.tag_name,
                order_by=SensorReading.timestamp.desc()
            ).label('rn')
        ).filter(
            SensorReading.machine_id == machine_id
        )

        if tag_names:
            subquery = subquery.filter(SensorReading.tag_name.in_(tag_names))

        subquery = subquery.subquery()

        latest = self.session.query(subquery).filter(subquery.c.rn == 1).all()

        result = {}
        for row in latest:
            value = row.value_float
            if value is None:
                value = row.value_int
            if value is None:
                value = row.value_str
            if value is None:
                value = row.value_bool

            result[row.tag_name] = {
                'value': value,
                'timestamp': row.timestamp.isoformat() if row.timestamp else None,
                'unit': row.unit,
            }

        return result

    # =========================================================================
    # Machine Event Logging
    # =========================================================================

    def record_machine_event(
        self,
        machine_id: str,
        event_type: str,
        description: Optional[str] = None,
        event_code: Optional[str] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        job_id: Optional[str] = None,
        work_order_id: Optional[str] = None,
        data: Optional[Dict] = None,
        severity: Optional[str] = None,
        source: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> DataCollectionEvent:
        """
        Record a machine event.

        Args:
            machine_id: Machine identifier
            event_type: Event type (use EventType enum values)
            description: Human-readable description
            event_code: Optional event/error code
            previous_state: Previous machine state
            new_state: New machine state
            job_id: Related job ID
            work_order_id: Related work order ID
            data: Additional event data (JSON)
            severity: 'info', 'warning', 'error', 'critical'
            source: Event source
            operator_id: Operator who triggered event

        Returns:
            Created DataCollectionEvent
        """
        event = DataCollectionEvent(
            timestamp=datetime.utcnow(),
            machine_id=machine_id,
            event_type=event_type,
            event_code=event_code,
            description=description,
            previous_state=previous_state,
            new_state=new_state,
            job_id=job_id,
            work_order_id=work_order_id,
            data=data or {},
            severity=severity or 'info',
            source=source,
            operator_id=operator_id,
        )

        self.session.add(event)
        self.session.flush()

        # Emit to WebSocket for real-time updates
        _emit_data_event('machine_event', {
            'machine_id': machine_id,
            'event_type': event_type,
            'description': description,
            'severity': severity,
            'timestamp': event.timestamp.isoformat(),
        })

        logger.info(f"Machine event: {machine_id} - {event_type}: {description}")

        return event

    def get_machine_events(
        self,
        machine_id: Optional[str] = None,
        event_type: Optional[str] = None,
        job_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Query machine events with filtering.

        Returns:
            Dict with events list and total count
        """
        query = self.session.query(DataCollectionEvent)

        if machine_id:
            query = query.filter(DataCollectionEvent.machine_id == machine_id)
        if event_type:
            query = query.filter(DataCollectionEvent.event_type == event_type)
        if job_id:
            query = query.filter(DataCollectionEvent.job_id == job_id)
        if start_time:
            query = query.filter(DataCollectionEvent.timestamp >= start_time)
        if end_time:
            query = query.filter(DataCollectionEvent.timestamp <= end_time)
        if severity:
            query = query.filter(DataCollectionEvent.severity == severity)

        total = query.count()
        events = query.order_by(DataCollectionEvent.timestamp.desc()).offset(offset).limit(limit).all()

        return {
            'events': [e.to_dict() for e in events],
            'total': total,
            'limit': limit,
            'offset': offset,
        }

    def get_recent_events(
        self,
        machine_id: Optional[str] = None,
        hours: int = 24,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent events for a machine or all machines."""
        start_time = datetime.utcnow() - timedelta(hours=hours)

        query = self.session.query(DataCollectionEvent).filter(
            DataCollectionEvent.timestamp >= start_time
        )

        if machine_id:
            query = query.filter(DataCollectionEvent.machine_id == machine_id)

        events = query.order_by(DataCollectionEvent.timestamp.desc()).limit(limit).all()

        return [e.to_dict() for e in events]

    # =========================================================================
    # Heartbeat Management
    # =========================================================================

    def update_heartbeat(
        self,
        machine_id: str,
        is_connected: bool = True,
        connection_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        port: Optional[int] = None,
        error: Optional[str] = None,
    ) -> MachineHeartbeat:
        """
        Update machine heartbeat.

        Args:
            machine_id: Machine identifier
            is_connected: Connection status
            connection_type: Type of connection
            ip_address: Machine IP
            port: Connection port
            error: Error message if disconnected

        Returns:
            Updated MachineHeartbeat
        """
        heartbeat = self.session.query(MachineHeartbeat).filter(
            MachineHeartbeat.machine_id == machine_id
        ).first()

        if not heartbeat:
            heartbeat = MachineHeartbeat(machine_id=machine_id)
            self.session.add(heartbeat)

        heartbeat.last_heartbeat = datetime.utcnow()
        heartbeat.is_connected = is_connected

        if connection_type:
            heartbeat.connection_type = connection_type
        if ip_address:
            heartbeat.ip_address = ip_address
        if port:
            heartbeat.port = port

        if is_connected:
            heartbeat.consecutive_failures = 0
            heartbeat.last_error = None
        else:
            heartbeat.consecutive_failures = (heartbeat.consecutive_failures or 0) + 1
            heartbeat.last_error = error

        self.session.flush()

        return heartbeat

    def get_stale_machines(self, stale_seconds: int = 30) -> List[str]:
        """
        Get machines that haven't sent a heartbeat recently.

        Args:
            stale_seconds: Threshold in seconds

        Returns:
            List of machine IDs
        """
        threshold = datetime.utcnow() - timedelta(seconds=stale_seconds)

        stale = self.session.query(MachineHeartbeat.machine_id).filter(
            and_(
                MachineHeartbeat.is_connected == True,
                MachineHeartbeat.last_heartbeat < threshold
            )
        ).all()

        return [h[0] for h in stale]

    # =========================================================================
    # Tag Definitions
    # =========================================================================

    def get_tag_definitions(
        self,
        machine_id: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get tag definitions with optional filtering."""
        query = self.session.query(TagDefinition)

        if machine_id:
            query = query.filter(TagDefinition.machine_id == machine_id)
        if category:
            query = query.filter(TagDefinition.category == category)
        if active_only:
            query = query.filter(TagDefinition.is_active == True)

        tags = query.order_by(TagDefinition.tag_name).all()

        return [t.to_dict() for t in tags]

    def create_tag_definition(self, data: Dict[str, Any]) -> TagDefinition:
        """Create a new tag definition."""
        tag = TagDefinition(
            tag_name=data['tag_name'],
            display_name=data.get('display_name'),
            description=data.get('description'),
            machine_id=data.get('machine_id'),
            machine_type=data.get('machine_type'),
            data_type=data.get('data_type', 'float'),
            unit=data.get('unit'),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            alarm_high=data.get('alarm_high'),
            alarm_low=data.get('alarm_low'),
            collection_rate_ms=data.get('collection_rate_ms', 1000),
            category=data.get('category'),
            source_type=data.get('source_type'),
            source_address=data.get('source_address'),
        )

        self.session.add(tag)
        self.session.flush()

        return tag


# Module-level convenience functions
def record_sensor_reading(session: Session, **kwargs) -> SensorReading:
    """Record a sensor reading."""
    service = DataCollectorService(session)
    return service.record_sensor_reading(**kwargs)


def record_machine_event(session: Session, **kwargs) -> DataCollectionEvent:
    """Record a machine event."""
    service = DataCollectorService(session)
    return service.record_machine_event(**kwargs)


def get_sensor_history(session: Session, machine_id: str, tag_name: str, start_time: datetime, **kwargs) -> List[Dict]:
    """Get sensor history."""
    service = DataCollectorService(session)
    return service.get_sensor_history(machine_id, tag_name, start_time, **kwargs)
