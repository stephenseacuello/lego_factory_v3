"""
Message Bus - Event-driven inter-agent communication.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework

Provides:
- Asynchronous message passing between agents
- Topic-based pub/sub messaging
- Priority queuing for critical messages
- Message persistence and replay
- Dead letter queue for failed messages
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import logging
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages in the agent communication system."""
    # Coordination messages
    REQUEST = "request"
    RESPONSE = "response"
    PROPOSAL = "proposal"
    ACCEPT = "accept"
    REJECT = "reject"

    # Event notifications
    EVENT = "event"
    ALERT = "alert"
    STATUS = "status"

    # Task management
    TASK_ASSIGN = "task_assign"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"

    # Consensus
    VOTE_REQUEST = "vote_request"
    VOTE = "vote"
    COMMIT = "commit"
    ABORT = "abort"

    # Heartbeat
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"


class Priority(Enum):
    """Message priority levels."""
    CRITICAL = 0  # Safety, emergency stops
    HIGH = 1      # Quality alerts, urgent decisions
    NORMAL = 2    # Standard operations
    LOW = 3       # Background tasks, logging
    BATCH = 4     # Bulk operations, analytics


@dataclass
class Message:
    """
    Message structure for inter-agent communication.

    Attributes:
        id: Unique message identifier
        type: Message type (request, response, event, etc.)
        sender: Agent ID of sender
        recipient: Agent ID of recipient (None for broadcast)
        topic: Message topic for pub/sub routing
        payload: Message content
        priority: Message priority
        correlation_id: ID linking related messages (request/response)
        timestamp: Message creation time
        ttl_seconds: Time to live in seconds
        requires_ack: Whether acknowledgment is required
    """
    type: MessageType
    sender: str
    payload: Dict[str, Any]
    topic: str = "default"
    recipient: Optional[str] = None
    priority: Priority = Priority.NORMAL
    correlation_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300
    requires_ack: bool = False
    acked: bool = False
    retry_count: int = 0
    max_retries: int = 3

    def __lt__(self, other: 'Message') -> bool:
        """Compare by priority for heap queue."""
        return (self.priority.value, self.timestamp) < (other.priority.value, other.timestamp)

    def is_expired(self) -> bool:
        """Check if message has expired."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl_seconds

    def create_response(self, payload: Dict[str, Any],
                       msg_type: MessageType = MessageType.RESPONSE) -> 'Message':
        """Create a response message linked to this message."""
        return Message(
            type=msg_type,
            sender=self.recipient or "system",
            recipient=self.sender,
            topic=self.topic,
            payload=payload,
            priority=self.priority,
            correlation_id=self.id
        )


@dataclass
class Subscription:
    """Subscription to message topics."""
    subscriber_id: str
    topics: Set[str]
    handler: Callable[[Message], Any]
    filter_fn: Optional[Callable[[Message], bool]] = None
    priority_filter: Optional[Set[Priority]] = None


class MessageBus:
    """
    Central message bus for agent communication.

    Features:
    - Topic-based pub/sub
    - Priority queuing
    - Async message processing
    - Acknowledgment tracking
    - Dead letter queue
    - Message replay
    """

    def __init__(self, max_queue_size: int = 10000):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._agent_subscriptions: Dict[str, Subscription] = {}
        self._message_queue: List[Message] = []  # Priority heap
        self._pending_acks: Dict[str, Message] = {}
        self._dead_letters: List[Message] = []
        self._message_history: List[Message] = []
        self._max_queue_size = max_queue_size
        self._max_history_size = 1000
        self._running = False
        self._process_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._stats = {
            'messages_published': 0,
            'messages_delivered': 0,
            'messages_expired': 0,
            'messages_failed': 0,
            'acks_received': 0
        }

    async def start(self) -> None:
        """Start the message bus processing loop."""
        if self._running:
            return
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("Message bus started")

    async def stop(self) -> None:
        """Stop the message bus."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("Message bus stopped")

    def subscribe(self,
                  subscriber_id: str,
                  topics: Set[str],
                  handler: Callable[[Message], Any],
                  filter_fn: Optional[Callable[[Message], bool]] = None,
                  priority_filter: Optional[Set[Priority]] = None) -> None:
        """
        Subscribe to message topics.

        Args:
            subscriber_id: Unique identifier for the subscriber
            topics: Set of topics to subscribe to
            handler: Callback function for messages
            filter_fn: Optional filter function for messages
            priority_filter: Optional set of priorities to receive
        """
        subscription = Subscription(
            subscriber_id=subscriber_id,
            topics=topics,
            handler=handler,
            filter_fn=filter_fn,
            priority_filter=priority_filter
        )

        for topic in topics:
            self._subscriptions[topic].append(subscription)

        self._agent_subscriptions[subscriber_id] = subscription
        logger.debug(f"Agent {subscriber_id} subscribed to topics: {topics}")

    def unsubscribe(self, subscriber_id: str) -> None:
        """Unsubscribe an agent from all topics."""
        if subscriber_id in self._agent_subscriptions:
            subscription = self._agent_subscriptions[subscriber_id]
            for topic in subscription.topics:
                self._subscriptions[topic] = [
                    s for s in self._subscriptions[topic]
                    if s.subscriber_id != subscriber_id
                ]
            del self._agent_subscriptions[subscriber_id]
            logger.debug(f"Agent {subscriber_id} unsubscribed")

    async def publish(self, message: Message) -> str:
        """
        Publish a message to the bus.

        Args:
            message: Message to publish

        Returns:
            Message ID
        """
        async with self._lock:
            if len(self._message_queue) >= self._max_queue_size:
                # Remove lowest priority message
                self._message_queue.sort()
                removed = self._message_queue.pop()
                logger.warning(f"Queue full, removed message {removed.id}")

            heapq.heappush(self._message_queue, message)
            self._stats['messages_published'] += 1

            if message.requires_ack:
                self._pending_acks[message.id] = message

        logger.debug(f"Published message {message.id} to topic {message.topic}")
        return message.id

    async def send(self,
                   sender: str,
                   recipient: str,
                   msg_type: MessageType,
                   payload: Dict[str, Any],
                   priority: Priority = Priority.NORMAL,
                   requires_ack: bool = False) -> str:
        """
        Send a direct message to a specific agent.

        Convenience method for point-to-point messaging.
        """
        message = Message(
            type=msg_type,
            sender=sender,
            recipient=recipient,
            topic=f"agent.{recipient}",
            payload=payload,
            priority=priority,
            requires_ack=requires_ack
        )
        return await self.publish(message)

    async def broadcast(self,
                       sender: str,
                       topic: str,
                       msg_type: MessageType,
                       payload: Dict[str, Any],
                       priority: Priority = Priority.NORMAL) -> str:
        """
        Broadcast a message to all subscribers of a topic.
        """
        message = Message(
            type=msg_type,
            sender=sender,
            topic=topic,
            payload=payload,
            priority=priority
        )
        return await self.publish(message)

    async def acknowledge(self, message_id: str) -> None:
        """Acknowledge receipt of a message."""
        if message_id in self._pending_acks:
            msg = self._pending_acks.pop(message_id)
            msg.acked = True
            self._stats['acks_received'] += 1
            logger.debug(f"Message {message_id} acknowledged")

    async def request_response(self,
                               message: Message,
                               timeout: float = 30.0) -> Optional[Message]:
        """
        Send a request and wait for response.

        Args:
            message: Request message
            timeout: Timeout in seconds

        Returns:
            Response message or None if timeout
        """
        response_future: asyncio.Future = asyncio.Future()
        correlation_id = message.id

        # Set up response handler
        async def response_handler(msg: Message) -> None:
            if msg.correlation_id == correlation_id:
                if not response_future.done():
                    response_future.set_result(msg)

        # Subscribe to responses temporarily
        temp_sub_id = f"temp_{correlation_id}"
        self.subscribe(
            temp_sub_id,
            {f"response.{message.sender}"},
            response_handler
        )

        try:
            await self.publish(message)
            return await asyncio.wait_for(response_future, timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Request {correlation_id} timed out")
            return None
        finally:
            self.unsubscribe(temp_sub_id)

    async def _process_loop(self) -> None:
        """Main message processing loop."""
        while self._running:
            try:
                await self._process_messages()
                await self._check_pending_acks()
                await asyncio.sleep(0.01)  # 10ms tick
            except Exception as e:
                logger.error(f"Error in message processing: {e}")

    async def _process_messages(self) -> None:
        """Process pending messages."""
        async with self._lock:
            if not self._message_queue:
                return

            # Get highest priority message
            message = heapq.heappop(self._message_queue)

        # Check expiration
        if message.is_expired():
            self._stats['messages_expired'] += 1
            logger.debug(f"Message {message.id} expired")
            return

        # Find subscribers
        subscribers = self._get_subscribers(message)

        if not subscribers:
            if message.recipient:
                # Direct message with no recipient - dead letter
                self._dead_letters.append(message)
                self._stats['messages_failed'] += 1
            return

        # Deliver to subscribers
        for subscription in subscribers:
            try:
                # Apply filters
                if subscription.filter_fn and not subscription.filter_fn(message):
                    continue
                if subscription.priority_filter and message.priority not in subscription.priority_filter:
                    continue

                # Call handler
                if asyncio.iscoroutinefunction(subscription.handler):
                    await subscription.handler(message)
                else:
                    subscription.handler(message)

                self._stats['messages_delivered'] += 1

            except Exception as e:
                logger.error(f"Error delivering to {subscription.subscriber_id}: {e}")
                self._stats['messages_failed'] += 1

        # Store in history
        self._message_history.append(message)
        if len(self._message_history) > self._max_history_size:
            self._message_history.pop(0)

    def _get_subscribers(self, message: Message) -> List[Subscription]:
        """Get subscribers for a message."""
        subscribers = []

        # Direct recipient
        if message.recipient and message.recipient in self._agent_subscriptions:
            subscribers.append(self._agent_subscriptions[message.recipient])

        # Topic subscribers
        subscribers.extend(self._subscriptions.get(message.topic, []))

        # Wildcard subscribers
        topic_parts = message.topic.split('.')
        for i in range(len(topic_parts)):
            wildcard = '.'.join(topic_parts[:i]) + '.*'
            subscribers.extend(self._subscriptions.get(wildcard, []))

        return subscribers

    async def _check_pending_acks(self) -> None:
        """Check for messages awaiting acknowledgment."""
        now = datetime.utcnow()
        to_retry = []

        for msg_id, message in list(self._pending_acks.items()):
            age = (now - message.timestamp).total_seconds()

            if age > 30:  # 30 second ack timeout
                if message.retry_count < message.max_retries:
                    message.retry_count += 1
                    to_retry.append(message)
                    del self._pending_acks[msg_id]
                else:
                    # Max retries reached - dead letter
                    self._dead_letters.append(message)
                    del self._pending_acks[msg_id]
                    self._stats['messages_failed'] += 1
                    logger.warning(f"Message {msg_id} failed after {message.max_retries} retries")

        for message in to_retry:
            await self.publish(message)

    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        return {
            **self._stats,
            'queue_size': len(self._message_queue),
            'pending_acks': len(self._pending_acks),
            'dead_letters': len(self._dead_letters),
            'subscribers': len(self._agent_subscriptions),
            'topics': list(self._subscriptions.keys())
        }

    def get_dead_letters(self, limit: int = 100) -> List[Message]:
        """Get failed messages from dead letter queue."""
        return self._dead_letters[-limit:]

    def replay_messages(self,
                       topic: Optional[str] = None,
                       since: Optional[datetime] = None,
                       limit: int = 100) -> List[Message]:
        """Replay messages from history."""
        messages = self._message_history

        if topic:
            messages = [m for m in messages if m.topic == topic]

        if since:
            messages = [m for m in messages if m.timestamp >= since]

        return messages[-limit:]
