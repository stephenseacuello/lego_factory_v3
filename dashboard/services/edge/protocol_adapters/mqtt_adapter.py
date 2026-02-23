"""
MQTT Protocol Adapter - Lightweight IoT Messaging

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT

Provides MQTT client capabilities:
- Broker connection management
- Topic subscription
- Message publishing
- QoS support
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import uuid
import json


class MQTTQoS(Enum):
    """MQTT Quality of Service levels."""
    AT_MOST_ONCE = 0   # Fire and forget
    AT_LEAST_ONCE = 1  # Acknowledged delivery
    EXACTLY_ONCE = 2   # Assured delivery


@dataclass
class MQTTMessage:
    """An MQTT message."""
    message_id: str
    topic: str
    payload: Any
    qos: MQTTQoS
    retained: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MQTTSubscription:
    """An MQTT topic subscription."""
    subscription_id: str
    topic_filter: str
    qos: MQTTQoS
    callback: Optional[Callable] = None
    message_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MQTTBrokerConnection:
    """MQTT broker connection."""
    connection_id: str
    broker_host: str
    broker_port: int
    client_id: str
    connected: bool = False
    use_tls: bool = False
    connected_at: Optional[datetime] = None
    messages_sent: int = 0
    messages_received: int = 0


class MQTTAdapter:
    """
    MQTT protocol adapter for IoT messaging.

    Provides MQTT client functionality for lightweight
    publish/subscribe messaging with IoT devices.
    """

    def __init__(self):
        self.connections: Dict[str, MQTTBrokerConnection] = {}
        self.subscriptions: Dict[str, MQTTSubscription] = {}
        self.message_buffer: List[MQTTMessage] = []
        self._retained_messages: Dict[str, MQTTMessage] = {}

    def connect(
        self,
        broker_host: str,
        broker_port: int = 1883,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        clean_session: bool = True
    ) -> MQTTBrokerConnection:
        """
        Connect to MQTT broker.

        Args:
            broker_host: Broker hostname or IP
            broker_port: Broker port (default 1883, 8883 for TLS)
            client_id: Client identifier
            username: Optional username
            password: Optional password
            use_tls: Use TLS encryption
            clean_session: Start with clean session

        Returns:
            Connection object
        """
        connection = MQTTBrokerConnection(
            connection_id=str(uuid.uuid4()),
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id or f"legomcp-{uuid.uuid4().hex[:8]}",
            connected=True,
            use_tls=use_tls,
            connected_at=datetime.utcnow(),
        )

        self.connections[connection.connection_id] = connection
        return connection

    def disconnect(self, connection_id: str) -> bool:
        """Disconnect from MQTT broker."""
        if connection_id in self.connections:
            self.connections[connection_id].connected = False
            return True
        return False

    def publish(
        self,
        connection_id: str,
        topic: str,
        payload: Any,
        qos: MQTTQoS = MQTTQoS.AT_LEAST_ONCE,
        retain: bool = False
    ) -> Optional[MQTTMessage]:
        """
        Publish message to topic.

        Args:
            connection_id: Connection ID
            topic: Topic to publish to
            payload: Message payload (will be JSON encoded if dict/list)
            qos: Quality of Service level
            retain: Retain message on broker

        Returns:
            Published message object
        """
        if connection_id not in self.connections:
            return None

        conn = self.connections[connection_id]
        if not conn.connected:
            return None

        # Serialize payload
        if isinstance(payload, (dict, list)):
            payload_str = json.dumps(payload)
        else:
            payload_str = str(payload)

        message = MQTTMessage(
            message_id=str(uuid.uuid4()),
            topic=topic,
            payload=payload_str,
            qos=qos,
            retained=retain,
        )

        self.message_buffer.append(message)
        conn.messages_sent += 1

        # Store retained message
        if retain:
            self._retained_messages[topic] = message

        # Deliver to matching subscriptions
        self._deliver_message(message)

        # Limit buffer size
        if len(self.message_buffer) > 1000:
            self.message_buffer = self.message_buffer[-1000:]

        return message

    def subscribe(
        self,
        connection_id: str,
        topic_filter: str,
        qos: MQTTQoS = MQTTQoS.AT_LEAST_ONCE,
        callback: Optional[Callable] = None
    ) -> Optional[MQTTSubscription]:
        """
        Subscribe to topic filter.

        Args:
            connection_id: Connection ID
            topic_filter: Topic filter (supports + and # wildcards)
            qos: Maximum QoS level
            callback: Callback for received messages

        Returns:
            Subscription object
        """
        if connection_id not in self.connections:
            return None

        subscription = MQTTSubscription(
            subscription_id=str(uuid.uuid4()),
            topic_filter=topic_filter,
            qos=qos,
            callback=callback,
        )

        self.subscriptions[subscription.subscription_id] = subscription

        # Deliver retained messages
        for topic, msg in self._retained_messages.items():
            if self._topic_matches(topic, topic_filter):
                subscription.message_count += 1
                if callback:
                    callback(msg)

        return subscription

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from topic."""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            return True
        return False

    def _deliver_message(self, message: MQTTMessage):
        """Deliver message to matching subscriptions."""
        for sub in self.subscriptions.values():
            if self._topic_matches(message.topic, sub.topic_filter):
                sub.message_count += 1
                if sub.callback:
                    sub.callback(message)

    def _topic_matches(self, topic: str, filter_pattern: str) -> bool:
        """Check if topic matches filter pattern."""
        topic_parts = topic.split('/')
        filter_parts = filter_pattern.split('/')

        i = 0
        for i, fp in enumerate(filter_parts):
            if fp == '#':
                return True
            if i >= len(topic_parts):
                return False
            if fp != '+' and fp != topic_parts[i]:
                return False

        return i + 1 == len(topic_parts)

    def get_connection_status(self, connection_id: str) -> Optional[Dict]:
        """Get connection status."""
        if connection_id not in self.connections:
            return None

        conn = self.connections[connection_id]
        return {
            'connection_id': conn.connection_id,
            'broker_host': conn.broker_host,
            'broker_port': conn.broker_port,
            'client_id': conn.client_id,
            'connected': conn.connected,
            'use_tls': conn.use_tls,
            'messages_sent': conn.messages_sent,
            'messages_received': conn.messages_received,
            'connected_at': conn.connected_at.isoformat() if conn.connected_at else None,
        }

    def get_subscription_stats(self) -> Dict:
        """Get subscription statistics."""
        return {
            'total_subscriptions': len(self.subscriptions),
            'total_messages_received': sum(
                s.message_count for s in self.subscriptions.values()
            ),
            'topics': [s.topic_filter for s in self.subscriptions.values()],
        }


# Singleton instance
_mqtt_adapter: Optional[MQTTAdapter] = None


def get_mqtt_adapter() -> MQTTAdapter:
    """Get or create the MQTT adapter instance."""
    global _mqtt_adapter
    if _mqtt_adapter is None:
        _mqtt_adapter = MQTTAdapter()
    return _mqtt_adapter
