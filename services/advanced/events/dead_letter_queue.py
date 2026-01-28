"""
Dead Letter Queue - Failed Event Handling

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture

Handles events that fail processing with:
- Automatic retry with exponential backoff
- Dead letter queue for permanent failures
- Alerting and monitoring
- Manual replay capability
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    aioredis = None
    Redis = None

from .event_types import ManufacturingEvent, EventCategory

logger = logging.getLogger(__name__)


class FailureReason(str, Enum):
    """Reasons for event processing failure."""
    HANDLER_ERROR = "handler_error"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    UNKNOWN = "unknown"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 60000
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay_ms(self, attempt: int) -> int:
        """Calculate delay for a given retry attempt."""
        delay = min(
            self.initial_delay_ms * (self.exponential_base ** attempt),
            self.max_delay_ms
        )
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
        return int(delay)


@dataclass
class FailedEvent:
    """An event that failed processing."""
    event: ManufacturingEvent
    failure_reason: FailureReason
    error_message: str
    failed_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    dlq_id: str = field(default_factory=lambda: str(uuid4()))
    stack_trace: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'dlq_id': self.dlq_id,
            'event': self.event.to_dict(),
            'failure_reason': self.failure_reason.value,
            'error_message': self.error_message,
            'failed_at': self.failed_at.isoformat(),
            'retry_count': self.retry_count,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None,
            'stack_trace': self.stack_trace
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FailedEvent':
        """Create from dictionary."""
        event = ManufacturingEvent.from_dict(data['event'])
        return cls(
            dlq_id=data.get('dlq_id', str(uuid4())),
            event=event,
            failure_reason=FailureReason(data['failure_reason']),
            error_message=data['error_message'],
            failed_at=datetime.fromisoformat(data['failed_at']),
            retry_count=data.get('retry_count', 0),
            next_retry_at=datetime.fromisoformat(data['next_retry_at']) if data.get('next_retry_at') else None,
            stack_trace=data.get('stack_trace')
        )


class DeadLetterQueue:
    """
    Dead letter queue for failed events.

    Provides:
    - Storage for failed events
    - Automatic retry with backoff
    - Manual replay capability
    - Alerting for permanent failures
    """

    DLQ_STREAM = "lego:events:dlq"
    RETRY_STREAM = "lego:events:retry"
    PERMANENT_FAILURES_SET = "lego:events:permanent_failures"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None
    ):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.retry_policy = retry_policy or RetryPolicy()
        self._redis: Optional[Redis] = None
        self._running = False
        self._alert_handlers: List[Callable[[FailedEvent], Any]] = []

    async def connect(self) -> None:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available for DLQ")
            return

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding='utf-8',
                decode_responses=True
            )
            await self._redis.ping()
            logger.info("DLQ connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect DLQ to Redis: {e}")
            self._redis = None

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def add_alert_handler(self, handler: Callable[[FailedEvent], Any]) -> None:
        """Add a handler to be called when an event permanently fails."""
        self._alert_handlers.append(handler)

    async def add_failed_event(
        self,
        event: ManufacturingEvent,
        reason: FailureReason,
        error_message: str,
        stack_trace: Optional[str] = None
    ) -> FailedEvent:
        """
        Add a failed event to the queue.

        If retries are available, schedules for retry.
        Otherwise, moves to permanent failures.
        """
        failed_event = FailedEvent(
            event=event,
            failure_reason=reason,
            error_message=error_message,
            stack_trace=stack_trace
        )

        if failed_event.retry_count < self.retry_policy.max_retries:
            # Schedule for retry
            delay_ms = self.retry_policy.get_delay_ms(failed_event.retry_count)
            failed_event.next_retry_at = datetime.utcnow() + timedelta(milliseconds=delay_ms)

            if self._redis:
                await self._redis.xadd(
                    self.RETRY_STREAM,
                    {'data': json.dumps(failed_event.to_dict())},
                    maxlen=10000
                )
            logger.warning(
                f"Event {event.event_id} scheduled for retry in {delay_ms}ms "
                f"(attempt {failed_event.retry_count + 1})"
            )
        else:
            # Permanent failure
            failed_event.failure_reason = FailureReason.MAX_RETRIES_EXCEEDED

            if self._redis:
                await self._redis.xadd(
                    self.DLQ_STREAM,
                    {'data': json.dumps(failed_event.to_dict())},
                    maxlen=10000
                )
                await self._redis.sadd(
                    self.PERMANENT_FAILURES_SET,
                    failed_event.dlq_id
                )

            logger.error(
                f"Event {event.event_id} permanently failed after "
                f"{self.retry_policy.max_retries} retries: {error_message}"
            )

            # Alert handlers
            await self._trigger_alerts(failed_event)

        return failed_event

    async def increment_retry(self, failed_event: FailedEvent) -> FailedEvent:
        """Increment retry count and reschedule if possible."""
        failed_event.retry_count += 1

        if failed_event.retry_count < self.retry_policy.max_retries:
            delay_ms = self.retry_policy.get_delay_ms(failed_event.retry_count)
            failed_event.next_retry_at = datetime.utcnow() + timedelta(milliseconds=delay_ms)

            if self._redis:
                await self._redis.xadd(
                    self.RETRY_STREAM,
                    {'data': json.dumps(failed_event.to_dict())},
                    maxlen=10000
                )
        else:
            # Move to permanent failures
            failed_event.failure_reason = FailureReason.MAX_RETRIES_EXCEEDED

            if self._redis:
                await self._redis.xadd(
                    self.DLQ_STREAM,
                    {'data': json.dumps(failed_event.to_dict())},
                    maxlen=10000
                )

            await self._trigger_alerts(failed_event)

        return failed_event

    async def _trigger_alerts(self, failed_event: FailedEvent) -> None:
        """Trigger alert handlers for permanent failure."""
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(failed_event)
                else:
                    handler(failed_event)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    async def get_retry_events(self, count: int = 10) -> List[FailedEvent]:
        """Get events that are due for retry."""
        if not self._redis:
            return []

        try:
            now = datetime.utcnow()
            messages = await self._redis.xrange(
                self.RETRY_STREAM,
                count=count
            )

            events = []
            for message_id, data in messages:
                try:
                    failed_event = FailedEvent.from_dict(json.loads(data['data']))
                    if failed_event.next_retry_at and failed_event.next_retry_at <= now:
                        events.append(failed_event)
                        # Remove from retry stream
                        await self._redis.xdel(self.RETRY_STREAM, message_id)
                except Exception as e:
                    logger.error(f"Failed to parse retry event: {e}")

            return events

        except Exception as e:
            logger.error(f"Failed to get retry events: {e}")
            return []

    async def get_dlq_events(
        self,
        count: int = 100,
        start_id: str = '-',
        end_id: str = '+'
    ) -> List[FailedEvent]:
        """Get events from the dead letter queue."""
        if not self._redis:
            return []

        try:
            messages = await self._redis.xrange(
                self.DLQ_STREAM,
                min=start_id,
                max=end_id,
                count=count
            )

            events = []
            for message_id, data in messages:
                try:
                    events.append(FailedEvent.from_dict(json.loads(data['data'])))
                except Exception as e:
                    logger.error(f"Failed to parse DLQ event: {e}")

            return events

        except Exception as e:
            logger.error(f"Failed to get DLQ events: {e}")
            return []

    async def replay_event(
        self,
        dlq_id: str,
        event_bus: Any  # EventBus
    ) -> bool:
        """
        Replay a failed event by republishing it.

        Returns True if successfully replayed.
        """
        if not self._redis:
            return False

        try:
            # Find the event in DLQ
            messages = await self._redis.xrange(self.DLQ_STREAM)
            for message_id, data in messages:
                failed_event = FailedEvent.from_dict(json.loads(data['data']))
                if failed_event.dlq_id == dlq_id:
                    # Republish the event
                    await event_bus.publish(failed_event.event)

                    # Remove from DLQ
                    await self._redis.xdel(self.DLQ_STREAM, message_id)
                    await self._redis.srem(self.PERMANENT_FAILURES_SET, dlq_id)

                    logger.info(f"Replayed event {dlq_id}")
                    return True

            logger.warning(f"Event {dlq_id} not found in DLQ")
            return False

        except Exception as e:
            logger.error(f"Failed to replay event: {e}")
            return False

    async def purge_dlq(self) -> int:
        """Purge all events from the dead letter queue."""
        if not self._redis:
            return 0

        try:
            count = await self._redis.xlen(self.DLQ_STREAM)
            await self._redis.delete(self.DLQ_STREAM)
            await self._redis.delete(self.PERMANENT_FAILURES_SET)
            logger.info(f"Purged {count} events from DLQ")
            return count
        except Exception as e:
            logger.error(f"Failed to purge DLQ: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics."""
        if not self._redis:
            return {'status': 'disconnected'}

        try:
            return {
                'status': 'connected',
                'dlq_count': await self._redis.xlen(self.DLQ_STREAM),
                'retry_count': await self._redis.xlen(self.RETRY_STREAM),
                'permanent_failure_count': await self._redis.scard(self.PERMANENT_FAILURES_SET),
                'retry_policy': {
                    'max_retries': self.retry_policy.max_retries,
                    'initial_delay_ms': self.retry_policy.initial_delay_ms,
                    'max_delay_ms': self.retry_policy.max_delay_ms
                }
            }
        except Exception as e:
            logger.error(f"Failed to get DLQ stats: {e}")
            return {'status': 'error', 'error': str(e)}


class RetryProcessor:
    """
    Background processor for retrying failed events.

    Runs continuously, checking for events due for retry
    and reprocessing them.
    """

    def __init__(
        self,
        dlq: DeadLetterQueue,
        event_bus: Any,  # EventBus
        handler: Callable[[ManufacturingEvent], Any]
    ):
        self.dlq = dlq
        self.event_bus = event_bus
        self.handler = handler
        self._running = False

    async def start(self) -> None:
        """Start the retry processor."""
        self._running = True
        logger.info("Retry processor started")

        while self._running:
            try:
                # Get events due for retry
                events = await self.dlq.get_retry_events(count=10)

                for failed_event in events:
                    try:
                        # Try to process again
                        if asyncio.iscoroutinefunction(self.handler):
                            await self.handler(failed_event.event)
                        else:
                            self.handler(failed_event.event)

                        logger.info(f"Successfully retried event {failed_event.event.event_id}")

                    except Exception as e:
                        # Retry failed, increment count
                        logger.warning(f"Retry failed for {failed_event.event.event_id}: {e}")
                        await self.dlq.increment_retry(failed_event)

                # Wait before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry processor error: {e}")
                await asyncio.sleep(5)

        logger.info("Retry processor stopped")

    def stop(self) -> None:
        """Stop the retry processor."""
        self._running = False
