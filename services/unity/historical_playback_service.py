"""
LEGO Factory v3 - Historical Playback Service
==============================================
Historical data playback for Unity Digital Twin visualization.

Features:
- Create and manage playback sessions with configurable time ranges
- Variable playback speed (0.1x to 10x)
- Seek to specific timestamps
- WebSocket emission of state updates to /unity namespace
- Preload data from historian for efficient seeking
- Synchronize machine states, alarms, sensor values
- Event markers for alarms, work order changes, etc.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Callable

import pandas as pd

logger = logging.getLogger(__name__)


class PlaybackState(str, Enum):
    """Playback session states."""
    CREATED = 'created'
    LOADING = 'loading'
    READY = 'ready'
    PLAYING = 'playing'
    PAUSED = 'paused'
    STOPPED = 'stopped'
    ERROR = 'error'


@dataclass
class PlaybackEvent:
    """Event marker during playback."""
    timestamp: datetime
    event_type: str  # 'alarm', 'work_order', 'state_change', 'anomaly'
    entity_id: Optional[str]
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'entity_id': self.entity_id,
            'data': self.data,
        }


@dataclass
class PlaybackSession:
    """Playback session configuration and state."""
    session_id: str
    start_time: datetime
    end_time: datetime
    speed: float = 1.0
    state: PlaybackState = PlaybackState.CREATED
    current_time: datetime = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    # Data caches
    tag_data: Optional[pd.DataFrame] = field(default=None, repr=False)
    events: List[PlaybackEvent] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if self.current_time is None:
            self.current_time = self.start_time

    @property
    def duration_seconds(self) -> float:
        """Total duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def progress(self) -> float:
        """Current playback progress (0.0 to 1.0)."""
        if self.duration_seconds <= 0:
            return 0.0
        elapsed = (self.current_time - self.start_time).total_seconds()
        return max(0.0, min(1.0, elapsed / self.duration_seconds))

    @property
    def elapsed_seconds(self) -> float:
        """Elapsed time in seconds."""
        return (self.current_time - self.start_time).total_seconds()

    @property
    def remaining_seconds(self) -> float:
        """Remaining time in seconds."""
        return (self.end_time - self.current_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'current_time': self.current_time.isoformat(),
            'speed': self.speed,
            'state': self.state.value,
            'progress': self.progress,
            'duration_seconds': self.duration_seconds,
            'elapsed_seconds': self.elapsed_seconds,
            'remaining_seconds': self.remaining_seconds,
            'created_at': self.created_at.isoformat(),
            'error_message': self.error_message,
            'event_count': len(self.events),
            'data_loaded': self.tag_data is not None and not self.tag_data.empty,
        }


class HistoricalPlaybackService:
    """
    Service for historical data playback in Unity Digital Twin.

    Manages playback sessions, loads historical data from the historian,
    and emits state updates via WebSocket for Unity visualization.
    """

    # Speed limits
    MIN_SPEED = 0.1
    MAX_SPEED = 10.0

    # Update intervals
    DEFAULT_UPDATE_INTERVAL = 0.1  # 100ms real-time between updates

    def __init__(self):
        self._sessions: Dict[str, PlaybackSession] = {}
        self._playback_threads: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

        # Callbacks for external integration
        self._state_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        logger.info("Historical Playback Service initialized")

    def create_playback_session(
        self,
        start_time: datetime,
        end_time: datetime,
        speed: float = 1.0,
        preload: bool = True
    ) -> PlaybackSession:
        """
        Create a new playback session.

        Args:
            start_time: Start time for playback
            end_time: End time for playback
            speed: Initial playback speed (0.1x to 10x)
            preload: Whether to preload data from historian

        Returns:
            Created PlaybackSession

        Raises:
            ValueError: If time range is invalid or speed is out of range
        """
        # Validate inputs
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")

        speed = max(self.MIN_SPEED, min(self.MAX_SPEED, speed))

        session_id = str(uuid.uuid4())

        session = PlaybackSession(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            speed=speed,
            state=PlaybackState.CREATED,
        )

        with self._lock:
            self._sessions[session_id] = session
            self._stop_flags[session_id] = threading.Event()

        logger.info(
            f"Created playback session {session_id}",
            extra={
                'event': 'playback_session_created',
                'session_id': session_id,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': session.duration_seconds,
            }
        )

        # Preload data in background
        if preload:
            self._preload_session_data(session)

        return session

    def _preload_session_data(self, session: PlaybackSession):
        """Preload historical data for the session."""
        session.state = PlaybackState.LOADING

        try:
            # Load tag values from historian
            self._load_tag_data(session)

            # Load events (alarms, work order changes, etc.)
            self._load_events(session)

            session.state = PlaybackState.READY

            logger.info(
                f"Preloaded data for session {session.session_id}",
                extra={
                    'event': 'playback_data_loaded',
                    'session_id': session.session_id,
                    'tag_rows': len(session.tag_data) if session.tag_data is not None else 0,
                    'event_count': len(session.events),
                }
            )

        except Exception as e:
            session.state = PlaybackState.ERROR
            session.error_message = str(e)
            logger.error(f"Error preloading session data: {e}")

    def _load_tag_data(self, session: PlaybackSession):
        """Load tag values from historian for the session time range."""
        try:
            from services.scada.historian.historian_service import HistorianReader

            reader = HistorianReader()

            # Get all available tags (in production, this would query a tag registry)
            tag_ids = self._get_playback_tag_ids()

            if tag_ids:
                session.tag_data = reader.get_raw(
                    tag_ids=tag_ids,
                    start=session.start_time,
                    end=session.end_time,
                    limit=500000  # Reasonable limit for playback
                )
            else:
                session.tag_data = pd.DataFrame()

        except ImportError:
            logger.warning("Historian service not available, using empty data")
            session.tag_data = pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading tag data: {e}")
            session.tag_data = pd.DataFrame()

    def _load_events(self, session: PlaybackSession):
        """Load events (alarms, work orders, etc.) for the session time range."""
        session.events = []

        # Load alarms
        try:
            self._load_alarm_events(session)
        except Exception as e:
            logger.warning(f"Could not load alarm events: {e}")

        # Load work order changes
        try:
            self._load_work_order_events(session)
        except Exception as e:
            logger.warning(f"Could not load work order events: {e}")

        # Sort events by timestamp
        session.events.sort(key=lambda e: e.timestamp)

    def _load_alarm_events(self, session: PlaybackSession):
        """Load alarm events from the database."""
        try:
            from config.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            timestamp,
                            alarm_id,
                            tag_id,
                            priority,
                            message,
                            acknowledged
                        FROM alarm_history
                        WHERE timestamp >= :start AND timestamp <= :end
                        ORDER BY timestamp
                    """),
                    {
                        'start': session.start_time,
                        'end': session.end_time,
                    }
                )

                for row in result:
                    session.events.append(PlaybackEvent(
                        timestamp=row.timestamp,
                        event_type='alarm',
                        entity_id=row.tag_id,
                        data={
                            'alarm_id': row.alarm_id,
                            'priority': row.priority,
                            'message': row.message,
                            'acknowledged': row.acknowledged,
                        }
                    ))
        except Exception as e:
            logger.debug(f"Could not load alarms: {e}")

    def _load_work_order_events(self, session: PlaybackSession):
        """Load work order state change events."""
        try:
            from config.database import get_engine
            from sqlalchemy import text

            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            updated_at as timestamp,
                            order_id,
                            status,
                            machine_id
                        FROM work_order_history
                        WHERE updated_at >= :start AND updated_at <= :end
                        ORDER BY updated_at
                    """),
                    {
                        'start': session.start_time,
                        'end': session.end_time,
                    }
                )

                for row in result:
                    session.events.append(PlaybackEvent(
                        timestamp=row.timestamp,
                        event_type='work_order',
                        entity_id=row.machine_id,
                        data={
                            'order_id': row.order_id,
                            'status': row.status,
                        }
                    ))
        except Exception as e:
            logger.debug(f"Could not load work orders: {e}")

    def _get_playback_tag_ids(self) -> List[str]:
        """Get list of tag IDs to include in playback."""
        # In production, this would query a tag registry
        # For now, return common machine tags
        return [
            # Printer tags
            'printer_1.temperature',
            'printer_1.bed_temperature',
            'printer_1.progress',
            'printer_1.status',
            'printer_2.temperature',
            'printer_2.bed_temperature',
            'printer_2.progress',
            'printer_2.status',
            'printer_3.temperature',
            'printer_3.bed_temperature',
            'printer_3.progress',
            'printer_3.status',
            # Robot tags
            'niryo_ned2.joint_1',
            'niryo_ned2.joint_2',
            'niryo_ned2.joint_3',
            'niryo_ned2.joint_4',
            'niryo_ned2.joint_5',
            'niryo_ned2.joint_6',
            'niryo_ned2.status',
            'xarm_lite6.joint_1',
            'xarm_lite6.joint_2',
            'xarm_lite6.joint_3',
            'xarm_lite6.joint_4',
            'xarm_lite6.joint_5',
            'xarm_lite6.joint_6',
            'xarm_lite6.status',
        ]

    def start_playback(self, session_id: str) -> bool:
        """
        Start playback for a session.

        Args:
            session_id: Session ID to start

        Returns:
            True if started successfully

        Raises:
            ValueError: If session not found or not in valid state
        """
        session = self._get_session(session_id)

        if session.state not in (PlaybackState.READY, PlaybackState.PAUSED):
            if session.state == PlaybackState.LOADING:
                raise ValueError("Session is still loading data")
            elif session.state == PlaybackState.PLAYING:
                return True  # Already playing
            else:
                raise ValueError(f"Cannot start playback in state: {session.state.value}")

        session.state = PlaybackState.PLAYING

        # Clear stop flag
        self._stop_flags[session_id].clear()

        # Start playback thread
        thread = threading.Thread(
            target=self._playback_loop,
            args=(session_id,),
            daemon=True,
            name=f"playback-{session_id[:8]}"
        )
        self._playback_threads[session_id] = thread
        thread.start()

        # Emit playback started event
        self._emit_playback_event('playback_started', session)

        logger.info(f"Started playback for session {session_id}")
        return True

    def pause_playback(self, session_id: str) -> bool:
        """
        Pause playback for a session.

        Args:
            session_id: Session ID to pause

        Returns:
            True if paused successfully
        """
        session = self._get_session(session_id)

        if session.state != PlaybackState.PLAYING:
            return False

        session.state = PlaybackState.PAUSED
        self._stop_flags[session_id].set()

        # Wait for thread to stop
        if session_id in self._playback_threads:
            thread = self._playback_threads[session_id]
            thread.join(timeout=1.0)

        # Emit playback paused event
        self._emit_playback_event('playback_paused', session)

        logger.info(f"Paused playback for session {session_id}")
        return True

    def resume_playback(self, session_id: str) -> bool:
        """
        Resume paused playback.

        Args:
            session_id: Session ID to resume

        Returns:
            True if resumed successfully
        """
        return self.start_playback(session_id)

    def stop_playback(self, session_id: str) -> bool:
        """
        Stop playback and reset to start.

        Args:
            session_id: Session ID to stop

        Returns:
            True if stopped successfully
        """
        session = self._get_session(session_id)

        # Stop the playback thread
        self._stop_flags[session_id].set()

        if session_id in self._playback_threads:
            thread = self._playback_threads[session_id]
            thread.join(timeout=2.0)
            del self._playback_threads[session_id]

        session.state = PlaybackState.STOPPED
        session.current_time = session.start_time

        # Emit playback stopped event
        self._emit_playback_event('playback_stopped', session)

        logger.info(f"Stopped playback for session {session_id}")
        return True

    def seek_to_time(self, session_id: str, target_time: datetime) -> bool:
        """
        Seek to a specific time in the playback.

        Args:
            session_id: Session ID
            target_time: Target timestamp to seek to

        Returns:
            True if seek successful

        Raises:
            ValueError: If target time is outside session range
        """
        session = self._get_session(session_id)

        # Validate target time
        if target_time < session.start_time:
            target_time = session.start_time
        elif target_time > session.end_time:
            target_time = session.end_time

        was_playing = session.state == PlaybackState.PLAYING

        # Pause if playing
        if was_playing:
            self.pause_playback(session_id)

        # Update current time
        session.current_time = target_time

        # Emit state at new position
        state_at_time = self.get_state_at_time(target_time, session)
        self._emit_state_update(session, state_at_time)

        # Emit seek event
        self._emit_playback_event('playback_seek', session, {
            'target_time': target_time.isoformat(),
        })

        # Resume if was playing
        if was_playing:
            self.start_playback(session_id)

        logger.info(f"Seeked session {session_id} to {target_time.isoformat()}")
        return True

    def set_playback_speed(self, session_id: str, speed: float) -> float:
        """
        Set playback speed.

        Args:
            session_id: Session ID
            speed: Playback speed (0.1x to 10x)

        Returns:
            Actual speed set (clamped to valid range)
        """
        session = self._get_session(session_id)

        # Clamp speed to valid range
        speed = max(self.MIN_SPEED, min(self.MAX_SPEED, speed))
        session.speed = speed

        # Emit speed change event
        self._emit_playback_event('playback_speed_changed', session, {
            'speed': speed,
        })

        logger.info(f"Set playback speed for session {session_id} to {speed}x")
        return speed

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current session status.

        Args:
            session_id: Session ID

        Returns:
            Session status dictionary
        """
        session = self._get_session(session_id)
        return session.to_dict()

    def get_state_at_time(
        self,
        timestamp: datetime,
        session: PlaybackSession = None
    ) -> Dict[str, Any]:
        """
        Get the complete factory state at a specific timestamp.

        Args:
            timestamp: Target timestamp
            session: Optional session for cached data access

        Returns:
            State dictionary with entities, sensors, alarms
        """
        state = {
            'timestamp': timestamp.isoformat(),
            'entities': {},
            'sensor_values': {},
            'active_alarms': [],
            'events': [],
        }

        # Get tag values at timestamp
        if session and session.tag_data is not None and not session.tag_data.empty:
            state['sensor_values'] = self._interpolate_tag_values(
                session.tag_data,
                timestamp
            )

        # Build entity states from sensor values
        state['entities'] = self._build_entity_states(state['sensor_values'], timestamp)

        # Get events at or before this timestamp
        if session:
            state['events'] = [
                e.to_dict() for e in session.events
                if e.timestamp <= timestamp
            ][-10:]  # Last 10 events

            # Get active alarms
            state['active_alarms'] = [
                e.to_dict() for e in session.events
                if e.event_type == 'alarm' and e.timestamp <= timestamp
            ]

        return state

    def _interpolate_tag_values(
        self,
        tag_data: pd.DataFrame,
        timestamp: datetime
    ) -> Dict[str, float]:
        """Interpolate tag values at the given timestamp."""
        values = {}

        if tag_data.empty:
            return values

        # Group by tag_id and find closest values
        for tag_id in tag_data['tag_id'].unique():
            tag_df = tag_data[tag_data['tag_id'] == tag_id]

            if tag_df.empty:
                continue

            # Find values before and after timestamp
            before = tag_df[tag_df['time'] <= timestamp]
            after = tag_df[tag_df['time'] > timestamp]

            if not before.empty:
                # Use the most recent value before or at timestamp
                values[tag_id] = before.iloc[-1]['value']
            elif not after.empty:
                # Use first value after if no value before
                values[tag_id] = after.iloc[0]['value']

        return values

    def _build_entity_states(
        self,
        sensor_values: Dict[str, float],
        timestamp: datetime
    ) -> Dict[str, Dict[str, Any]]:
        """Build entity states from sensor values."""
        entities = {}

        # Build printer states
        for printer_num in [1, 2, 3]:
            printer_id = f'printer_{printer_num}'
            prefix = f'{printer_id}.'

            entity_state = {
                'entity_id': printer_id,
                'entity_type': 'machine',
                'timestamp': timestamp.isoformat(),
                'state': {
                    'temperature': sensor_values.get(f'{prefix}temperature', 0),
                    'bed_temperature': sensor_values.get(f'{prefix}bed_temperature', 0),
                    'progress': sensor_values.get(f'{prefix}progress', 0),
                    'status': 'running' if sensor_values.get(f'{prefix}progress', 0) > 0 else 'idle',
                },
            }
            entities[printer_id] = entity_state

        # Build robot states
        for robot_id in ['niryo_ned2', 'xarm_lite6']:
            prefix = f'{robot_id}.'

            joint_positions = []
            for i in range(1, 7):
                joint_val = sensor_values.get(f'{prefix}joint_{i}', 0)
                joint_positions.append(joint_val)

            entity_state = {
                'entity_id': robot_id,
                'entity_type': 'robot',
                'timestamp': timestamp.isoformat(),
                'state': {
                    'joint_positions': joint_positions,
                    'status': 'running' if any(j != 0 for j in joint_positions) else 'idle',
                },
            }
            entities[robot_id] = entity_state

        return entities

    def _playback_loop(self, session_id: str):
        """Main playback loop running in background thread."""
        session = self._sessions.get(session_id)
        if not session:
            return

        stop_flag = self._stop_flags.get(session_id)
        if not stop_flag:
            return

        last_update = time.time()

        logger.debug(f"Playback loop started for session {session_id}")

        try:
            while not stop_flag.is_set():
                # Check if we've reached the end
                if session.current_time >= session.end_time:
                    session.state = PlaybackState.STOPPED
                    self._emit_playback_event('playback_completed', session)
                    logger.info(f"Playback completed for session {session_id}")
                    break

                # Calculate time advancement
                now = time.time()
                real_elapsed = now - last_update
                last_update = now

                # Advance playback time based on speed
                playback_elapsed = real_elapsed * session.speed
                session.current_time = min(
                    session.current_time + timedelta(seconds=playback_elapsed),
                    session.end_time
                )

                # Get and emit state at current time
                state = self.get_state_at_time(session.current_time, session)
                self._emit_state_update(session, state)

                # Emit position update
                self._emit_playback_position(session)

                # Check for events at current time
                self._emit_events_at_time(session)

                # Sleep for update interval
                time.sleep(self.DEFAULT_UPDATE_INTERVAL)

        except Exception as e:
            logger.error(f"Error in playback loop: {e}")
            session.state = PlaybackState.ERROR
            session.error_message = str(e)
            self._emit_playback_event('playback_error', session, {
                'error': str(e),
            })

    def _emit_state_update(self, session: PlaybackSession, state: Dict[str, Any]):
        """Emit state update via WebSocket."""
        try:
            from services.websocket.socket_service import emit_to_room

            emit_to_room(
                'playback_state_update',
                {
                    'session_id': session.session_id,
                    'state': state,
                    'timestamp': datetime.utcnow().isoformat(),
                },
                room='unity',
                namespace='/unity'
            )
        except ImportError:
            logger.debug("WebSocket service not available")
        except Exception as e:
            logger.warning(f"Error emitting state update: {e}")

    def _emit_playback_position(self, session: PlaybackSession):
        """Emit playback position update via WebSocket."""
        try:
            from services.websocket.socket_service import emit_to_room

            emit_to_room(
                'playback_position',
                {
                    'session_id': session.session_id,
                    'current_time': session.current_time.isoformat(),
                    'progress': session.progress,
                    'elapsed_seconds': session.elapsed_seconds,
                    'remaining_seconds': session.remaining_seconds,
                    'speed': session.speed,
                    'state': session.state.value,
                },
                room='unity',
                namespace='/unity'
            )
        except ImportError:
            logger.debug("WebSocket service not available")
        except Exception as e:
            logger.warning(f"Error emitting position update: {e}")

    def _emit_events_at_time(self, session: PlaybackSession):
        """Emit any events that occurred at the current playback time."""
        # Find events within a small window of current time
        window_start = session.current_time - timedelta(milliseconds=100)
        window_end = session.current_time

        for event in session.events:
            if window_start <= event.timestamp <= window_end:
                self._emit_playback_event('playback_event', session, {
                    'event': event.to_dict(),
                })

    def _emit_playback_event(
        self,
        event_type: str,
        session: PlaybackSession,
        extra_data: Dict[str, Any] = None
    ):
        """Emit a playback control event via WebSocket."""
        try:
            from services.websocket.socket_service import emit_to_room

            data = {
                'session_id': session.session_id,
                'session_state': session.state.value,
                'current_time': session.current_time.isoformat(),
                'progress': session.progress,
                'timestamp': datetime.utcnow().isoformat(),
            }

            if extra_data:
                data.update(extra_data)

            emit_to_room(
                event_type,
                data,
                room='unity',
                namespace='/unity'
            )
        except ImportError:
            logger.debug("WebSocket service not available")
        except Exception as e:
            logger.warning(f"Error emitting playback event: {e}")

    def _get_session(self, session_id: str) -> PlaybackSession:
        """Get session by ID, raising ValueError if not found."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a playback session and clean up resources.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            # Stop playback if running
            if session_id in self._sessions:
                session = self._sessions[session_id]
                if session.state == PlaybackState.PLAYING:
                    self.stop_playback(session_id)

            # Clean up resources
            with self._lock:
                self._sessions.pop(session_id, None)
                self._stop_flags.pop(session_id, None)
                self._playback_threads.pop(session_id, None)

            logger.info(f"Deleted playback session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all playback sessions."""
        return [session.to_dict() for session in self._sessions.values()]

    def register_state_callback(
        self,
        callback: Callable[[str, Dict[str, Any]], None]
    ):
        """
        Register a callback for state updates.

        Args:
            callback: Function(session_id, state) to call on updates
        """
        self._state_callbacks.append(callback)

    def cleanup(self):
        """Clean up all sessions and resources."""
        logger.info("Cleaning up playback service")

        # Stop all active sessions
        for session_id in list(self._sessions.keys()):
            try:
                self.stop_playback(session_id)
                self.delete_session(session_id)
            except Exception as e:
                logger.warning(f"Error cleaning up session {session_id}: {e}")


# Global service instance
_playback_service: Optional[HistoricalPlaybackService] = None


def get_playback_service() -> HistoricalPlaybackService:
    """Get or create the global playback service instance."""
    global _playback_service
    if _playback_service is None:
        _playback_service = HistoricalPlaybackService()
    return _playback_service


def init_playback_service() -> HistoricalPlaybackService:
    """Initialize the playback service."""
    global _playback_service
    _playback_service = HistoricalPlaybackService()
    return _playback_service
