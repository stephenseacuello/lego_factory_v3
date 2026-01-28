"""
Production Feedback Collector - Collect outcomes from production.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning System

Collect outcomes from production:
- Quality inspection results -> Quality prediction model
- Actual print times -> Duration prediction model
- Equipment failures -> Maintenance prediction model
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProductionEvent:
    """Production event with outcome data."""
    event_id: str
    event_type: str  # print_complete, inspection_result, equipment_failure
    timestamp: datetime
    job_id: str
    equipment_id: str
    features: Dict[str, Any]  # Input features used for prediction
    outcome: Dict[str, Any]  # Actual outcome
    prediction: Optional[Dict[str, Any]] = None  # What was predicted
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackStream:
    """Stream for specific feedback type."""
    name: str
    model_id: str
    buffer: List[ProductionEvent] = field(default_factory=list)
    buffer_size: int = 100
    last_flush: datetime = field(default_factory=datetime.utcnow)


class ProductionFeedbackCollector:
    """
    Collect production outcomes and feed back to models.

    Features:
    - Multi-stream collection (quality, timing, equipment)
    - Buffered batch processing
    - Async event handling
    - Drift detection integration
    """

    def __init__(self):
        self._streams: Dict[str, FeedbackStream] = {
            'quality': FeedbackStream(name='quality', model_id='quality_predictor'),
            'timing': FeedbackStream(name='timing', model_id='duration_predictor'),
            'equipment': FeedbackStream(name='equipment', model_id='maintenance_predictor')
        }
        self._drift_detector = None
        self._model_updater = None
        self._event_handlers: List[Callable[[ProductionEvent], None]] = []
        self._stats = {
            'events_collected': 0,
            'updates_triggered': 0,
            'drift_alerts': 0
        }

    def set_drift_detector(self, detector: Any) -> None:
        """Set drift detector for monitoring."""
        self._drift_detector = detector

    def set_model_updater(self, updater: Any) -> None:
        """Set model updater for retraining."""
        self._model_updater = updater

    def add_event_handler(self, handler: Callable[[ProductionEvent], None]) -> None:
        """Add handler for incoming events."""
        self._event_handlers.append(handler)

    async def collect(self, event: ProductionEvent) -> None:
        """
        Collect a production event.

        Args:
            event: Production event with features and outcome
        """
        # Determine which stream
        stream = self._get_stream_for_event(event)
        if not stream:
            logger.warning(f"No stream for event type: {event.event_type}")
            return

        # Add to buffer
        stream.buffer.append(event)
        self._stats['events_collected'] += 1

        # Notify handlers
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        # Check if buffer should be flushed
        if len(stream.buffer) >= stream.buffer_size:
            await self._flush_stream(stream)

        # Check for drift
        if self._drift_detector and event.prediction:
            await self._check_drift(event)

        logger.debug(f"Collected event {event.event_id} for stream {stream.name}")

    def _get_stream_for_event(self, event: ProductionEvent) -> Optional[FeedbackStream]:
        """Get appropriate stream for event type."""
        mapping = {
            'inspection_result': 'quality',
            'quality_check': 'quality',
            'print_complete': 'timing',
            'job_complete': 'timing',
            'equipment_failure': 'equipment',
            'maintenance_event': 'equipment'
        }
        stream_name = mapping.get(event.event_type)
        return self._streams.get(stream_name) if stream_name else None

    async def _flush_stream(self, stream: FeedbackStream) -> None:
        """Flush stream buffer to model updater."""
        if not stream.buffer:
            return

        if self._model_updater:
            try:
                events = stream.buffer.copy()
                await self._model_updater.process_batch(stream.model_id, events)
                self._stats['updates_triggered'] += 1
                logger.info(f"Flushed {len(events)} events for {stream.name}")
            except Exception as e:
                logger.error(f"Error flushing stream {stream.name}: {e}")

        stream.buffer.clear()
        stream.last_flush = datetime.utcnow()

    async def _check_drift(self, event: ProductionEvent) -> None:
        """Check for model drift based on prediction vs outcome."""
        if not self._drift_detector:
            return

        # Calculate prediction error
        if 'value' in event.prediction and 'value' in event.outcome:
            predicted = event.prediction['value']
            actual = event.outcome['value']
            error = abs(predicted - actual)

            drift_result = await self._drift_detector.check(
                model_id=self._get_model_id(event),
                error=error,
                features=event.features
            )

            if drift_result.get('drift_detected'):
                self._stats['drift_alerts'] += 1
                logger.warning(f"Drift detected for model {drift_result.get('model_id')}")

    def _get_model_id(self, event: ProductionEvent) -> str:
        """Get model ID from event."""
        stream = self._get_stream_for_event(event)
        return stream.model_id if stream else "unknown"

    async def flush_all(self) -> None:
        """Flush all stream buffers."""
        for stream in self._streams.values():
            await self._flush_stream(stream)

    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            **self._stats,
            'streams': {
                name: {
                    'buffer_size': len(stream.buffer),
                    'last_flush': stream.last_flush.isoformat()
                }
                for name, stream in self._streams.items()
            }
        }

    def get_recent_events(self,
                         stream_name: Optional[str] = None,
                         limit: int = 50) -> List[ProductionEvent]:
        """Get recent events from buffer."""
        if stream_name and stream_name in self._streams:
            return self._streams[stream_name].buffer[-limit:]

        # All streams
        all_events = []
        for stream in self._streams.values():
            all_events.extend(stream.buffer)

        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        return all_events[:limit]
