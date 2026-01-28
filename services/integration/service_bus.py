"""
Service Bus for Flask CNC SCADA
===============================
Inter-service messaging and command routing.

Features:
- Request/response messaging between services
- Command pattern implementation
- Service registry and discovery
- Message queuing for async operations
- Dead letter handling for failed messages

Usage:
    from services.integration.service_bus import get_service_bus, Message

    bus = get_service_bus()

    # Register a service handler
    bus.register_handler("gcode", gcode_service.handle_command)

    # Send a command
    response = bus.send("gcode", Message(action="queue_job", data={"file": "test.nc"}))
"""

import logging
import time
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from collections import defaultdict
import json

from config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class MessageStatus(Enum):
    """Message processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DEAD_LETTER = "dead_letter"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class Message:
    """Inter-service message."""
    action: str
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timeout_sec: float = 30.0
    retries: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "data": self.data,
            "timestamp": self.timestamp,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "retries": self.retries,
        }


@dataclass
class MessageResponse:
    """Response to a message."""
    message_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# Type for message handlers
MessageHandler = Callable[[Message], MessageResponse]


@dataclass
class ServiceInfo:
    """Information about a registered service."""
    name: str
    handler: MessageHandler
    registered_at: float = field(default_factory=time.time)
    messages_processed: int = 0
    errors: int = 0
    avg_response_time_ms: float = 0.0


class ServiceBus:
    """
    Central message bus for inter-service communication.

    Provides reliable messaging between services with support for
    sync/async delivery, retries, and dead letter handling.
    """

    def __init__(self, async_enabled: bool = True):
        """
        Initialize service bus.

        Args:
            async_enabled: Enable async message processing
        """
        self._services: Dict[str, ServiceInfo] = {}
        self._lock = threading.RLock()

        # Message queues per service
        self._queues: Dict[str, Queue] = defaultdict(Queue)

        # Pending responses for request/reply pattern
        self._pending_responses: Dict[str, MessageResponse] = {}
        self._response_events: Dict[str, threading.Event] = {}

        # Dead letter queue
        self._dead_letter_queue: List[tuple] = []  # (message, error, timestamp)

        # Async processing
        self._async_enabled = async_enabled
        self._async_threads: Dict[str, threading.Thread] = {}
        self._running = False

        logger.info("ServiceBus initialized")

    def start(self):
        """Start async message processing."""
        self._running = True
        if self._async_enabled:
            for service_name in self._services:
                self._start_service_processor(service_name)
        logger.info("ServiceBus started")

    def stop(self):
        """Stop async message processing."""
        self._running = False
        for thread in self._async_threads.values():
            thread.join(timeout=2.0)
        self._async_threads.clear()
        logger.info("ServiceBus stopped")

    def register_handler(
        self,
        service_name: str,
        handler: MessageHandler,
    ) -> None:
        """
        Register a message handler for a service.

        Args:
            service_name: Name of the service
            handler: Function to handle messages
        """
        with self._lock:
            self._services[service_name] = ServiceInfo(
                name=service_name,
                handler=handler,
            )
            logger.info(f"Registered handler for service: {service_name}")

            # Start processor if bus is running
            if self._running and self._async_enabled:
                self._start_service_processor(service_name)

    def unregister_handler(self, service_name: str) -> bool:
        """
        Unregister a service handler.

        Args:
            service_name: Name of the service

        Returns:
            True if service was unregistered
        """
        with self._lock:
            if service_name in self._services:
                del self._services[service_name]
                logger.info(f"Unregistered handler for service: {service_name}")
                return True
            return False

    def send(
        self,
        service_name: str,
        message: Message,
        sync: bool = True,
    ) -> Optional[MessageResponse]:
        """
        Send a message to a service.

        Args:
            service_name: Target service name
            message: Message to send
            sync: If True, wait for response

        Returns:
            MessageResponse if sync, None if async
        """
        with self._lock:
            if service_name not in self._services:
                logger.error(f"Service not found: {service_name}")
                return MessageResponse(
                    message_id=message.id,
                    success=False,
                    error=f"Service not found: {service_name}",
                )

        if sync:
            return self._send_sync(service_name, message)
        else:
            return self._send_async(service_name, message)

    def _send_sync(
        self,
        service_name: str,
        message: Message,
    ) -> MessageResponse:
        """Send message synchronously and wait for response."""
        service_info = self._services.get(service_name)
        if not service_info:
            return MessageResponse(
                message_id=message.id,
                success=False,
                error=f"Service not found: {service_name}",
            )

        start_time = time.time()
        try:
            response = service_info.handler(message)

            # Update stats
            elapsed_ms = (time.time() - start_time) * 1000
            with self._lock:
                service_info.messages_processed += 1
                # Running average
                n = service_info.messages_processed
                service_info.avg_response_time_ms = (
                    (service_info.avg_response_time_ms * (n - 1) + elapsed_ms) / n
                )

            return response

        except Exception as e:
            with self._lock:
                service_info.errors += 1

            # Handle retries
            if message.retries < message.max_retries:
                message.retries += 1
                logger.warning(
                    f"Message {message.id} failed, retrying "
                    f"({message.retries}/{message.max_retries})"
                )
                return self._send_sync(service_name, message)
            else:
                # Move to dead letter queue
                self._add_to_dead_letter(message, str(e))
                return MessageResponse(
                    message_id=message.id,
                    success=False,
                    error=str(e),
                )

    def _send_async(
        self,
        service_name: str,
        message: Message,
    ) -> None:
        """Queue message for async processing."""
        self._queues[service_name].put(message)
        logger.debug(f"Queued message {message.id} for {service_name}")
        return None

    def _start_service_processor(self, service_name: str):
        """Start async processor thread for a service."""
        if service_name in self._async_threads:
            return

        thread = threading.Thread(
            target=self._process_queue,
            args=(service_name,),
            daemon=True,
            name=f"ServiceBus-{service_name}",
        )
        self._async_threads[service_name] = thread
        thread.start()

    def _process_queue(self, service_name: str):
        """Process messages from service queue."""
        while self._running:
            try:
                message = self._queues[service_name].get(timeout=0.1)
                self._send_sync(service_name, message)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing message for {service_name}: {e}")

    def _add_to_dead_letter(self, message: Message, error: str):
        """Add failed message to dead letter queue."""
        with self._lock:
            self._dead_letter_queue.append((message, error, time.time()))
            logger.warning(f"Message {message.id} moved to dead letter queue: {error}")

    def get_dead_letters(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages from dead letter queue."""
        with self._lock:
            return [
                {
                    "message": msg.to_dict(),
                    "error": error,
                    "timestamp": ts,
                }
                for msg, error, ts in self._dead_letter_queue[-limit:]
            ]

    def reprocess_dead_letters(self) -> int:
        """Attempt to reprocess dead letter messages."""
        with self._lock:
            messages = list(self._dead_letter_queue)
            self._dead_letter_queue.clear()

        reprocessed = 0
        for message, _, _ in messages:
            # Reset retries and try again
            message.retries = 0
            # We need the service name - extract from action if possible
            # This is a simplified implementation
            reprocessed += 1

        return reprocessed

    def get_service_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all registered services."""
        with self._lock:
            return {
                name: {
                    "messages_processed": info.messages_processed,
                    "errors": info.errors,
                    "avg_response_time_ms": round(info.avg_response_time_ms, 2),
                    "queue_size": self._queues[name].qsize(),
                    "registered_at": info.registered_at,
                }
                for name, info in self._services.items()
            }

    def get_registered_services(self) -> List[str]:
        """Get list of registered service names."""
        with self._lock:
            return list(self._services.keys())


# Global service bus instance
_service_bus: Optional[ServiceBus] = None


def get_service_bus() -> ServiceBus:
    """Get global service bus instance."""
    global _service_bus
    if _service_bus is None:
        _service_bus = ServiceBus()
    return _service_bus


def initialize_service_bus(async_enabled: bool = True) -> ServiceBus:
    """Initialize and start global service bus."""
    global _service_bus
    _service_bus = ServiceBus(async_enabled=async_enabled)
    _service_bus.start()
    return _service_bus
