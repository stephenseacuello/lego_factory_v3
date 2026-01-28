"""
MQTT Listener for Real-time Copilot.

Subscribes to MQTT topics and feeds events to the copilot:
- Machine status updates
- Position updates
- Alarm triggers
- Sensor data
- Job progress
"""

import logging
import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

from .event_processor import EventType

logger = logging.getLogger(__name__)


@dataclass
class MQTTConfig:
    """MQTT connection configuration."""
    broker_host: str = "localhost"
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "cnc-copilot"
    keepalive: int = 60
    reconnect_delay: float = 5.0

    # Topic subscriptions
    topics: List[str] = field(default_factory=lambda: [
        "cnc/+/status",
        "cnc/+/position",
        "cnc/+/alarm",
        "cnc/+/error",
        "sensor/+/data",
        "job/+/progress",
        "job/+/completed",
        "quality/+/spc",
    ])


class MQTTListener:
    """
    Listens to MQTT topics and processes messages for the copilot.

    Supports:
    - Automatic reconnection
    - Topic-based message routing
    - Machine context updates
    - Event generation
    """

    def __init__(
        self,
        config: Optional[MQTTConfig] = None,
        on_event: Optional[Callable] = None,
        on_context_update: Optional[Callable] = None,
    ):
        """
        Initialize MQTT listener.

        Args:
            config: MQTT configuration
            on_event: Callback for events (MachineEvent)
            on_context_update: Callback for context updates
        """
        self.config = config or MQTTConfig()
        self._on_event = on_event
        self._on_context_update = on_context_update

        self._client = None
        self._running = False
        self._connected = False
        self._reconnect_task = None

        # Topic handlers
        self._topic_handlers: Dict[str, Callable] = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up topic-specific message handlers."""
        self._topic_handlers = {
            "cnc/+/status": self._handle_status,
            "cnc/+/position": self._handle_position,
            "cnc/+/alarm": self._handle_alarm,
            "cnc/+/error": self._handle_error,
            "sensor/+/data": self._handle_sensor_data,
            "job/+/progress": self._handle_job_progress,
            "job/+/completed": self._handle_job_completed,
            "quality/+/spc": self._handle_spc_data,
        }

    async def start(self):
        """Start the MQTT listener."""
        if self._running:
            return

        self._running = True
        logger.info("Starting MQTT listener")

        try:
            await self._connect()
        except Exception as e:
            logger.error(f"Initial MQTT connection failed: {e}")
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def stop(self):
        """Stop the MQTT listener."""
        self._running = False

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        await self._disconnect()
        logger.info("MQTT listener stopped")

    async def _connect(self):
        """Connect to the MQTT broker."""
        try:
            import paho.mqtt.client as mqtt

            # Create client
            self._client = mqtt.Client(
                client_id=self.config.client_id,
                protocol=mqtt.MQTTv311,
            )

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Set credentials if provided
            if self.config.username:
                self._client.username_pw_set(
                    self.config.username,
                    self.config.password,
                )

            # Connect
            self._client.connect(
                self.config.broker_host,
                self.config.broker_port,
                self.config.keepalive,
            )

            # Start network loop
            self._client.loop_start()

            logger.info(
                f"Connected to MQTT broker at "
                f"{self.config.broker_host}:{self.config.broker_port}"
            )

        except ImportError:
            logger.warning("paho-mqtt not installed, MQTT listener disabled")
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            raise

    async def _disconnect(self):
        """Disconnect from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    async def _reconnect_loop(self):
        """Background task to handle reconnection."""
        while self._running:
            try:
                if not self._connected:
                    logger.info("Attempting MQTT reconnection...")
                    await self._connect()
                await asyncio.sleep(self.config.reconnect_delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                await asyncio.sleep(self.config.reconnect_delay)

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            self._connected = True
            logger.info("MQTT connected successfully")

            # Subscribe to topics
            for topic in self.config.topics:
                client.subscribe(topic, qos=1)
                logger.debug(f"Subscribed to: {topic}")
        else:
            logger.error(f"MQTT connection failed with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT unexpected disconnect: {rc}")
            if self._running and not self._reconnect_task:
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    def _on_message(self, client, userdata, msg):
        """Callback when a message is received."""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")

            # Try to parse as JSON
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"raw": payload}

            # Route to appropriate handler
            self._route_message(topic, data)

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def _route_message(self, topic: str, data: Dict[str, Any]):
        """Route a message to the appropriate handler."""
        # Extract machine/sensor ID from topic
        parts = topic.split("/")
        if len(parts) >= 3:
            entity_id = parts[1]  # e.g., "tinyg", "mill1"

            # Find matching handler
            for pattern, handler in self._topic_handlers.items():
                if self._topic_matches(topic, pattern):
                    handler(entity_id, data)
                    return

        logger.debug(f"No handler for topic: {topic}")

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if a topic matches a pattern with wildcards."""
        topic_parts = topic.split("/")
        pattern_parts = pattern.split("/")

        if len(topic_parts) != len(pattern_parts):
            return False

        for t, p in zip(topic_parts, pattern_parts):
            if p == "+":
                continue
            if p == "#":
                return True
            if t != p:
                return False

        return True

    def _handle_status(self, machine_id: str, data: Dict[str, Any]):
        """Handle machine status updates."""
        status = data.get("status") or data.get("state", "unknown")

        if self._on_context_update:
            self._on_context_update(
                machine_id=machine_id,
                status=status,
            )

        logger.debug(f"Status update: {machine_id} = {status}")

    def _handle_position(self, machine_id: str, data: Dict[str, Any]):
        """Handle position updates."""
        position = {
            "x": data.get("x", data.get("posx", 0)),
            "y": data.get("y", data.get("posy", 0)),
            "z": data.get("z", data.get("posz", 0)),
        }

        # Add additional axes if present
        for axis in ["a", "b", "c"]:
            if axis in data:
                position[axis] = data[axis]

        if self._on_context_update:
            self._on_context_update(
                machine_id=machine_id,
                position=position,
            )

    def _handle_alarm(self, machine_id: str, data: Dict[str, Any]):
        """Handle alarm triggers."""
        alarm_code = data.get("code") or data.get("alarm", "unknown")
        message = data.get("message", f"Alarm {alarm_code}")

        # Update context
        if self._on_context_update:
            self._on_context_update(
                machine_id=machine_id,
                alarms=[alarm_code],
            )

        # Generate event
        if self._on_event:
            from .event_processor import MachineEvent

            event = MachineEvent(
                id=f"alarm-{machine_id}-{datetime.now().timestamp()}",
                event_type=EventType.ALARM,
                machine_id=machine_id,
                severity="high",
                data=data,
                message=message,
            )
            self._on_event(event)

        logger.warning(f"Alarm on {machine_id}: {alarm_code}")

    def _handle_error(self, machine_id: str, data: Dict[str, Any]):
        """Handle error messages."""
        error_code = data.get("code") or data.get("error", "unknown")
        message = data.get("message", f"Error {error_code}")

        if self._on_event:
            from .event_processor import MachineEvent

            event = MachineEvent(
                id=f"error-{machine_id}-{datetime.now().timestamp()}",
                event_type=EventType.ERROR,
                machine_id=machine_id,
                severity="medium",
                data=data,
                message=message,
            )
            self._on_event(event)

        logger.error(f"Error on {machine_id}: {error_code}")

    def _handle_sensor_data(self, sensor_id: str, data: Dict[str, Any]):
        """Handle sensor data updates."""
        # Extract machine ID from sensor ID if possible
        machine_id = data.get("machine_id", sensor_id.split("_")[0])

        if self._on_context_update:
            self._on_context_update(
                machine_id=machine_id,
                sensor_data={sensor_id: data},
            )

        # Check for anomalies
        if data.get("anomaly") or data.get("out_of_range"):
            if self._on_event:
                from .event_processor import MachineEvent

                event = MachineEvent(
                    id=f"sensor-{sensor_id}-{datetime.now().timestamp()}",
                    event_type=EventType.SENSOR_ANOMALY,
                    machine_id=machine_id,
                    severity="medium",
                    data=data,
                    message=f"Sensor anomaly detected: {sensor_id}",
                )
                self._on_event(event)

    def _handle_job_progress(self, job_id: str, data: Dict[str, Any]):
        """Handle job progress updates."""
        machine_id = data.get("machine_id", "unknown")
        progress = data.get("progress", 0)

        if self._on_context_update:
            self._on_context_update(
                machine_id=machine_id,
                job=job_id,
                progress=progress,
            )

    def _handle_job_completed(self, job_id: str, data: Dict[str, Any]):
        """Handle job completion."""
        machine_id = data.get("machine_id", "unknown")

        if self._on_context_update:
            self._on_context_update(
                machine_id=machine_id,
                job=None,
                progress=100,
            )

        if self._on_event:
            from .event_processor import MachineEvent

            event = MachineEvent(
                id=f"job-{job_id}-{datetime.now().timestamp()}",
                event_type=EventType.JOB_COMPLETED,
                machine_id=machine_id,
                severity="low",
                data={"job_id": job_id, **data},
                message=f"Job completed: {job_id}",
            )
            self._on_event(event)

        logger.info(f"Job completed: {job_id} on {machine_id}")

    def _handle_spc_data(self, machine_id: str, data: Dict[str, Any]):
        """Handle SPC control chart data."""
        # Check for control limit violations
        if data.get("violation") or data.get("out_of_control"):
            if self._on_event:
                from .event_processor import MachineEvent

                event = MachineEvent(
                    id=f"spc-{machine_id}-{datetime.now().timestamp()}",
                    event_type=EventType.SPC_VIOLATION,
                    machine_id=machine_id,
                    severity="high",
                    data=data,
                    message=(
                        f"SPC violation: {data.get('parameter', 'unknown')} "
                        f"out of control limits"
                    ),
                )
                self._on_event(event)

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        qos: int = 1,
        retain: bool = False,
    ):
        """
        Publish a message to an MQTT topic.

        Args:
            topic: MQTT topic
            payload: Message payload (will be JSON-encoded)
            qos: Quality of service (0, 1, or 2)
            retain: Whether to retain the message
        """
        if not self._client or not self._connected:
            logger.warning("Cannot publish: not connected to MQTT")
            return

        try:
            message = json.dumps(payload)
            self._client.publish(topic, message, qos=qos, retain=retain)
            logger.debug(f"Published to {topic}")
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to MQTT broker."""
        return self._connected


def create_mqtt_listener_for_copilot(copilot) -> MQTTListener:
    """
    Create an MQTT listener configured for the copilot.

    Args:
        copilot: RealtimeCopilot instance

    Returns:
        Configured MQTTListener
    """
    def on_event(event):
        copilot.event_processor.process_event(event)

    def on_context_update(**kwargs):
        copilot.update_machine_context(**kwargs)

    return MQTTListener(
        on_event=on_event,
        on_context_update=on_context_update,
    )
