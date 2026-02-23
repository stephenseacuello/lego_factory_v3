"""
Stream Consumer - Async Event Processing

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture

Provides async consumer groups for parallel event processing
with automatic load balancing and failure handling.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
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


@dataclass
class ConsumerConfig:
    """Configuration for a stream consumer."""
    group_name: str = "default"
    consumer_name: str = field(default_factory=lambda: f"consumer-{uuid4().hex[:8]}")
    batch_size: int = 10
    block_ms: int = 5000
    max_retries: int = 3
    retry_delay_ms: int = 1000
    claim_min_idle_time_ms: int = 60000  # Claim pending messages after 1 minute
    ack_timeout_ms: int = 30000


@dataclass
class ConsumerGroup:
    """Consumer group for load balancing."""
    name: str
    stream_keys: List[str]
    consumers: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class StreamConsumer:
    """
    High-performance stream consumer using Redis Streams.

    Features:
    - Consumer group support for parallel processing
    - Automatic pending message recovery
    - Graceful shutdown with message draining
    - Metrics and monitoring
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        config: Optional[ConsumerConfig] = None
    ):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.config = config or ConsumerConfig()
        self._redis: Optional[Redis] = None
        self._running = False
        self._handlers: Dict[str, Callable] = {}
        self._processed_count = 0
        self._error_count = 0
        self._last_process_time: Optional[datetime] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available")
            return

        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding='utf-8',
                decode_responses=True
            )
            await self._redis.ping()
            logger.info(f"Consumer connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis = None

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def register_handler(
        self,
        category: EventCategory,
        handler: Callable[[ManufacturingEvent], Any]
    ) -> None:
        """Register a handler for an event category."""
        stream_key = f"lego:events:{category.value}"
        self._handlers[stream_key] = handler

    async def _ensure_consumer_group(self, stream_key: str) -> None:
        """Ensure consumer group exists for stream."""
        if not self._redis:
            return

        try:
            await self._redis.xgroup_create(
                stream_key,
                self.config.group_name,
                id='0',
                mkstream=True
            )
            logger.info(f"Created consumer group {self.config.group_name} for {stream_key}")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.warning(f"Failed to create group: {e}")

    async def _claim_pending_messages(self, stream_key: str) -> List[tuple]:
        """Claim pending messages that have been idle too long."""
        if not self._redis:
            return []

        try:
            # Get pending messages
            pending = await self._redis.xpending_range(
                stream_key,
                self.config.group_name,
                min='-',
                max='+',
                count=self.config.batch_size
            )

            claimed = []
            for msg in pending:
                message_id = msg['message_id']
                idle_time = msg['time_since_delivered']

                if idle_time > self.config.claim_min_idle_time_ms:
                    # Claim the message
                    result = await self._redis.xclaim(
                        stream_key,
                        self.config.group_name,
                        self.config.consumer_name,
                        min_idle_time=self.config.claim_min_idle_time_ms,
                        message_ids=[message_id]
                    )
                    if result:
                        claimed.extend(result)
                        logger.info(f"Claimed pending message {message_id}")

            return claimed

        except Exception as e:
            logger.error(f"Failed to claim pending messages: {e}")
            return []

    async def _process_message(
        self,
        stream_key: str,
        message_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Process a single message."""
        try:
            # Parse event
            event_data = json.loads(data.get('data', '{}'))
            event = ManufacturingEvent.from_dict(event_data)

            # Get handler
            handler = self._handlers.get(stream_key)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)

            # Acknowledge
            if self._redis:
                await self._redis.xack(
                    stream_key,
                    self.config.group_name,
                    message_id
                )

            self._processed_count += 1
            self._last_process_time = datetime.utcnow()
            return True

        except Exception as e:
            logger.error(f"Failed to process message {message_id}: {e}")
            self._error_count += 1
            return False

    async def start(self) -> None:
        """Start consuming events from all registered streams."""
        if not self._redis:
            await self.connect()

        if not self._redis or not self._handlers:
            logger.warning("No Redis connection or handlers registered")
            return

        stream_keys = list(self._handlers.keys())

        # Ensure consumer groups exist
        for stream_key in stream_keys:
            await self._ensure_consumer_group(stream_key)

        self._running = True
        logger.info(f"Consumer {self.config.consumer_name} started")

        while self._running:
            try:
                # First, claim any pending messages
                for stream_key in stream_keys:
                    claimed = await self._claim_pending_messages(stream_key)
                    for message_id, data in claimed:
                        await self._process_message(stream_key, message_id, data)

                # Read new messages
                streams = {key: '>' for key in stream_keys}
                messages = await self._redis.xreadgroup(
                    self.config.group_name,
                    self.config.consumer_name,
                    streams=streams,
                    count=self.config.batch_size,
                    block=self.config.block_ms
                )

                for stream_key, stream_messages in messages:
                    for message_id, data in stream_messages:
                        await self._process_message(stream_key, message_id, data)

            except asyncio.CancelledError:
                logger.info("Consumer cancelled")
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1)

        logger.info(f"Consumer {self.config.consumer_name} stopped")

    async def stop(self) -> None:
        """Stop the consumer gracefully."""
        self._running = False

    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics."""
        return {
            'consumer_name': self.config.consumer_name,
            'group_name': self.config.group_name,
            'processed_count': self._processed_count,
            'error_count': self._error_count,
            'last_process_time': self._last_process_time.isoformat() if self._last_process_time else None,
            'running': self._running,
            'handlers': list(self._handlers.keys())
        }


class ConsumerPool:
    """
    Pool of consumers for high-throughput processing.

    Manages multiple consumer instances for parallel processing
    with automatic scaling and monitoring.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        group_name: str = "default",
        pool_size: int = 4
    ):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.group_name = group_name
        self.pool_size = pool_size
        self._consumers: List[StreamConsumer] = []
        self._tasks: List[asyncio.Task] = []

    def add_handler(
        self,
        category: EventCategory,
        handler: Callable[[ManufacturingEvent], Any]
    ) -> None:
        """Add a handler to all consumers in the pool."""
        for consumer in self._consumers:
            consumer.register_handler(category, handler)

    async def start(self) -> None:
        """Start all consumers in the pool."""
        for i in range(self.pool_size):
            config = ConsumerConfig(
                group_name=self.group_name,
                consumer_name=f"consumer-{i}-{uuid4().hex[:4]}"
            )
            consumer = StreamConsumer(self.redis_url, config)
            self._consumers.append(consumer)

            task = asyncio.create_task(consumer.start())
            self._tasks.append(task)

        logger.info(f"Started consumer pool with {self.pool_size} consumers")

    async def stop(self) -> None:
        """Stop all consumers in the pool."""
        for consumer in self._consumers:
            await consumer.stop()

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._consumers.clear()
        self._tasks.clear()
        logger.info("Consumer pool stopped")

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics for all consumers in the pool."""
        return {
            'pool_size': self.pool_size,
            'group_name': self.group_name,
            'consumers': [c.get_stats() for c in self._consumers],
            'total_processed': sum(c._processed_count for c in self._consumers),
            'total_errors': sum(c._error_count for c in self._consumers)
        }
