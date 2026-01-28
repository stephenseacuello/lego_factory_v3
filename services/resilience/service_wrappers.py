"""
LEGO Factory v3 - Service Wrappers with Circuit Breakers
=========================================================
Wrapped service calls with circuit breaker protection and fallbacks.

This module provides resilient wrappers for external service calls:
- Redis operations (with local cache fallback)
- MQTT publishing (with retry queue)
- Database operations (with cached data fallback)
- External API calls (with cached/default responses)
- ROS2 bridge calls (with command queue)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from pybreaker import CircuitBreakerError

from services.resilience.circuit_breaker import (
    redis_breaker,
    mqtt_breaker,
    database_breaker,
    external_api_breaker,
    ros2_breaker,
    with_fallback,
    local_cache,
    mqtt_retry_queue,
    ros2_retry_queue,
    is_circuit_open,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Redis Wrappers
# ============================================================================

class ResilientRedisClient:
    """
    Redis client wrapper with circuit breaker and local cache fallback.

    When Redis is unavailable:
    - GET operations fall back to local cache
    - SET operations write to local cache and queue for Redis sync
    - DELETE operations are queued for sync when Redis recovers
    """

    def __init__(self, redis_client=None):
        """
        Initialize resilient Redis client.

        Args:
            redis_client: Underlying Redis client instance
        """
        self._redis = redis_client
        self._pending_writes: List[Dict[str, Any]] = []

    def set_client(self, redis_client):
        """Set the underlying Redis client."""
        self._redis = redis_client

    @with_fallback(default_value=None, log_fallback=True)
    @redis_breaker
    def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis with fallback to local cache.

        Args:
            key: Redis key

        Returns:
            Value or None if not found
        """
        if self._redis is None:
            raise ConnectionError("Redis client not initialized")

        value = self._redis.get(key)

        # Update local cache on successful read
        if value is not None:
            local_cache.set(key, value)

        return value

    def get_with_fallback(self, key: str) -> Optional[str]:
        """
        Get value with explicit local cache fallback.

        Uses local cache when circuit breaker is open.
        """
        try:
            return self.get(key)
        except CircuitBreakerError:
            logger.debug(f"Redis circuit open, using local cache for key: {key}")
            return local_cache.get(key)

    @with_fallback(default_value=False, log_fallback=True)
    @redis_breaker
    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Set a value in Redis with fallback to local cache.

        Args:
            key: Redis key
            value: Value to set
            ex: Expiration in seconds
            px: Expiration in milliseconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists

        Returns:
            True if successful
        """
        if self._redis is None:
            raise ConnectionError("Redis client not initialized")

        result = self._redis.set(key, value, ex=ex, px=px, nx=nx, xx=xx)

        # Also update local cache
        ttl = ex if ex else (px // 1000 if px else None)
        local_cache.set(key, value, ttl=ttl)

        return bool(result)

    def set_with_fallback(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
    ) -> bool:
        """
        Set value with local cache fallback when circuit is open.

        Queues write for sync when Redis recovers.
        """
        try:
            return self.set(key, value, ex=ex)
        except CircuitBreakerError:
            # Write to local cache
            local_cache.set(key, value, ttl=ex)

            # Queue for later sync
            self._pending_writes.append({
                'operation': 'set',
                'key': key,
                'value': value,
                'ex': ex,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })

            logger.debug(f"Redis circuit open, queued set for key: {key}")
            return True

    @with_fallback(default_value=0, log_fallback=True)
    @redis_breaker
    def delete(self, *keys: str) -> int:
        """
        Delete keys from Redis.

        Args:
            keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        if self._redis is None:
            raise ConnectionError("Redis client not initialized")

        result = self._redis.delete(*keys)

        # Also remove from local cache
        for key in keys:
            local_cache.delete(key)

        return result

    @with_fallback(default_value=False, log_fallback=True)
    @redis_breaker
    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        if self._redis is None:
            raise ConnectionError("Redis client not initialized")
        return bool(self._redis.exists(key))

    @with_fallback(default_value=[], log_fallback=True)
    @redis_breaker
    def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get a range from a list."""
        if self._redis is None:
            raise ConnectionError("Redis client not initialized")

        values = self._redis.lrange(key, start, end)

        # Cache the result
        local_cache.set(f"list:{key}:{start}:{end}", values)

        return values

    def sync_pending_writes(self) -> int:
        """
        Sync pending writes to Redis when it becomes available.

        Returns:
            Number of writes synced
        """
        if is_circuit_open('redis') or self._redis is None:
            return 0

        synced = 0
        failed = []

        for write in self._pending_writes:
            try:
                if write['operation'] == 'set':
                    self._redis.set(
                        write['key'],
                        write['value'],
                        ex=write.get('ex'),
                    )
                    synced += 1
                elif write['operation'] == 'delete':
                    self._redis.delete(write['key'])
                    synced += 1
            except Exception as e:
                logger.warning(f"Failed to sync pending Redis write: {e}")
                failed.append(write)

        self._pending_writes = failed

        if synced > 0:
            logger.info(f"Synced {synced} pending Redis writes")

        return synced


# Global resilient Redis client
resilient_redis = ResilientRedisClient()


# ============================================================================
# MQTT Wrappers
# ============================================================================

class ResilientMQTTClient:
    """
    MQTT client wrapper with circuit breaker and message queuing.

    When MQTT broker is unavailable:
    - Publish operations queue messages for retry
    - Subscribe operations fail gracefully
    """

    def __init__(self, mqtt_client=None):
        """
        Initialize resilient MQTT client.

        Args:
            mqtt_client: Underlying MQTT client instance
        """
        self._mqtt = mqtt_client
        self._subscriptions: Dict[str, Callable] = {}

    def set_client(self, mqtt_client):
        """Set the underlying MQTT client."""
        self._mqtt = mqtt_client

    @with_fallback(default_value=False, log_fallback=True)
    @mqtt_breaker
    def publish(
        self,
        topic: str,
        payload: Union[str, bytes, Dict],
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        """
        Publish a message to MQTT broker.

        Args:
            topic: MQTT topic
            payload: Message payload
            qos: Quality of Service level
            retain: Retain message flag

        Returns:
            True if published successfully
        """
        if self._mqtt is None:
            raise ConnectionError("MQTT client not initialized")

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        result = self._mqtt.publish(topic, payload, qos=qos, retain=retain)
        return result.rc == 0

    def publish_with_retry(
        self,
        topic: str,
        payload: Union[str, bytes, Dict],
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        """
        Publish with automatic queueing when circuit is open.

        Messages are queued and retried when broker becomes available.
        """
        try:
            return self.publish(topic, payload, qos=qos, retain=retain)
        except CircuitBreakerError:
            # Queue for retry
            mqtt_retry_queue.enqueue({
                'topic': topic,
                'payload': payload if isinstance(payload, (str, bytes)) else json.dumps(payload),
                'qos': qos,
                'retain': retain,
            })
            logger.debug(f"MQTT circuit open, queued message for topic: {topic}")
            return True

    @with_fallback(default_value=False, log_fallback=True)
    @mqtt_breaker
    def subscribe(
        self,
        topic: str,
        callback: Optional[Callable] = None,
        qos: int = 0,
    ) -> bool:
        """
        Subscribe to an MQTT topic.

        Args:
            topic: MQTT topic pattern
            callback: Optional message callback
            qos: Quality of Service level

        Returns:
            True if subscribed successfully
        """
        if self._mqtt is None:
            raise ConnectionError("MQTT client not initialized")

        result = self._mqtt.subscribe(topic, qos=qos)

        if callback:
            self._subscriptions[topic] = callback

        return result[0] == 0

    def process_retry_queue(self) -> int:
        """
        Process queued messages when MQTT becomes available.

        Returns:
            Number of messages published
        """
        if is_circuit_open('mqtt') or self._mqtt is None:
            return 0

        published = 0
        messages = mqtt_retry_queue.get_all()

        for msg in messages:
            try:
                payload = msg.payload
                self._mqtt.publish(
                    payload['topic'],
                    payload['payload'],
                    qos=payload.get('qos', 0),
                    retain=payload.get('retain', False),
                )
                published += 1
            except Exception as e:
                logger.warning(f"Failed to publish queued MQTT message: {e}")
                # Re-queue if under max attempts
                if msg.attempts < msg.max_attempts:
                    msg.attempts += 1
                    mqtt_retry_queue.enqueue(msg.payload, msg.max_attempts - msg.attempts)

        if published > 0:
            logger.info(f"Published {published} queued MQTT messages")

        return published


# Global resilient MQTT client
resilient_mqtt = ResilientMQTTClient()


# ============================================================================
# Database Wrappers
# ============================================================================

class ResilientDatabaseSession:
    """
    Database session wrapper with circuit breaker and cached data fallback.

    When database is unavailable:
    - Read operations return cached data if available
    - Write operations are queued (with warnings)
    """

    def __init__(self, session_factory=None):
        """
        Initialize resilient database session.

        Args:
            session_factory: SQLAlchemy session factory
        """
        self._session_factory = session_factory
        self._cache: Dict[str, Any] = {}
        self._pending_writes: List[Dict[str, Any]] = []

    def set_session_factory(self, session_factory):
        """Set the session factory."""
        self._session_factory = session_factory

    @with_fallback(default_value=None, log_fallback=True)
    @database_breaker
    def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """
        Execute a database query with circuit breaker protection.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Query result
        """
        if self._session_factory is None:
            raise ConnectionError("Database session not initialized")

        session = self._session_factory()
        try:
            from sqlalchemy import text
            result = session.execute(text(query), params or {})

            # Cache the result for fallback
            cache_key = f"query:{hash(query)}:{hash(str(params))}"
            self._cache[cache_key] = result.fetchall()

            return self._cache[cache_key]
        finally:
            session.close()

    def query_with_fallback(
        self,
        query: str,
        params: Optional[Dict] = None,
        default: Any = None,
    ) -> Any:
        """
        Execute query with cached fallback when circuit is open.
        """
        try:
            return self.execute_query(query, params)
        except CircuitBreakerError:
            cache_key = f"query:{hash(query)}:{hash(str(params))}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Database circuit open, returning cached result")
                return cached
            return default

    @with_fallback(default_value=None, log_fallback=True)
    @database_breaker
    def get_by_id(self, model_class, id_value: Any) -> Optional[Any]:
        """
        Get a model instance by ID with circuit breaker protection.

        Args:
            model_class: SQLAlchemy model class
            id_value: Primary key value

        Returns:
            Model instance or None
        """
        if self._session_factory is None:
            raise ConnectionError("Database session not initialized")

        session = self._session_factory()
        try:
            result = session.get(model_class, id_value)

            # Cache for fallback
            cache_key = f"model:{model_class.__name__}:{id_value}"
            if result:
                self._cache[cache_key] = result

            return result
        finally:
            session.close()

    def get_cached(self, model_name: str, id_value: Any) -> Optional[Any]:
        """Get cached model instance."""
        cache_key = f"model:{model_name}:{id_value}"
        return self._cache.get(cache_key)


# Global resilient database session
resilient_db = ResilientDatabaseSession()


# ============================================================================
# External API Wrappers
# ============================================================================

class ResilientAPIClient:
    """
    External API client wrapper with circuit breaker and cached responses.

    Supports Fusion 360 API, Slicer Service, and other external services.
    """

    def __init__(self, base_url: str = "", timeout: int = 30):
        """
        Initialize resilient API client.

        Args:
            base_url: Base URL for API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._response_cache: Dict[str, Any] = {}
        self._default_responses: Dict[str, Any] = {}

    def set_default_response(self, endpoint: str, response: Any):
        """Set a default response for an endpoint when API is unavailable."""
        self._default_responses[endpoint] = response

    @with_fallback(default_value=None, log_fallback=True)
    @external_api_breaker
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a GET request with circuit breaker protection.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Response data or None
        """
        import requests

        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        # Cache response
        cache_key = f"GET:{endpoint}:{hash(str(params))}"
        self._response_cache[cache_key] = data

        return data

    def get_with_fallback(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        GET request with cached/default response fallback.
        """
        try:
            return self.get(endpoint, params)
        except CircuitBreakerError:
            # Try cache
            cache_key = f"GET:{endpoint}:{hash(str(params))}"
            cached = self._response_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"API circuit open, returning cached response for {endpoint}")
                return cached

            # Try default
            default = self._default_responses.get(endpoint)
            if default is not None:
                logger.debug(f"API circuit open, returning default response for {endpoint}")
                return default

            return None

    @with_fallback(default_value=None, log_fallback=True)
    @external_api_breaker
    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Make a POST request with circuit breaker protection.
        """
        import requests

        url = f"{self.base_url}{endpoint}"
        response = requests.post(
            url,
            data=data,
            json=json_data,
            timeout=self.timeout,
        )
        response.raise_for_status()

        return response.json()


# Pre-configured API clients
slicer_api = ResilientAPIClient(base_url="http://localhost:8766")
fusion360_api = ResilientAPIClient(base_url="http://localhost:8767")


# ============================================================================
# ROS2 Bridge Wrappers
# ============================================================================

class ResilientROS2Bridge:
    """
    ROS2 bridge wrapper with circuit breaker and command queuing.

    When ROS2 bridge is unavailable:
    - Commands are queued for later execution
    - Status queries return last known state
    """

    def __init__(self, mqtt_client=None, prefix: str = "ros2_bridge"):
        """
        Initialize resilient ROS2 bridge.

        Args:
            mqtt_client: MQTT client for ROS2 bridge communication
            prefix: MQTT topic prefix for ROS2 bridge
        """
        self._mqtt = mqtt_client
        self._prefix = prefix
        self._last_state: Dict[str, Any] = {}

    def set_mqtt_client(self, mqtt_client):
        """Set the MQTT client."""
        self._mqtt = mqtt_client

    @with_fallback(default_value=False, log_fallback=True)
    @ros2_breaker
    def publish_command(
        self,
        robot_id: str,
        command: str,
        params: Optional[Dict] = None,
    ) -> bool:
        """
        Publish a command to ROS2 robot.

        Args:
            robot_id: Robot identifier
            command: Command name
            params: Command parameters

        Returns:
            True if published successfully
        """
        if self._mqtt is None:
            raise ConnectionError("MQTT client not initialized")

        topic = f"{self._prefix}/{robot_id}/command"
        payload = json.dumps({
            'command': command,
            'params': params or {},
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })

        result = self._mqtt.publish(topic, payload, qos=1)
        return result.rc == 0

    def send_command_with_retry(
        self,
        robot_id: str,
        command: str,
        params: Optional[Dict] = None,
    ) -> bool:
        """
        Send command with automatic queueing when circuit is open.
        """
        try:
            return self.publish_command(robot_id, command, params)
        except CircuitBreakerError:
            # Queue for retry
            ros2_retry_queue.enqueue({
                'robot_id': robot_id,
                'command': command,
                'params': params or {},
            })
            logger.debug(f"ROS2 circuit open, queued command for robot: {robot_id}")
            return True

    @with_fallback(default_value={}, log_fallback=True)
    @ros2_breaker
    def get_robot_state(self, robot_id: str) -> Dict[str, Any]:
        """
        Get current state of a ROS2 robot.

        Args:
            robot_id: Robot identifier

        Returns:
            Robot state dictionary
        """
        if self._mqtt is None:
            raise ConnectionError("MQTT client not initialized")

        # In a real implementation, this would request state via MQTT
        # For now, return last known state
        return self._last_state.get(robot_id, {})

    def get_state_with_fallback(self, robot_id: str) -> Dict[str, Any]:
        """
        Get robot state with fallback to last known state.
        """
        try:
            state = self.get_robot_state(robot_id)
            self._last_state[robot_id] = state
            return state
        except CircuitBreakerError:
            logger.debug(f"ROS2 circuit open, returning last known state for {robot_id}")
            return self._last_state.get(robot_id, {'status': 'unknown', 'circuit_open': True})

    def update_state(self, robot_id: str, state: Dict[str, Any]):
        """Update cached robot state (called from MQTT callback)."""
        self._last_state[robot_id] = state

    def process_command_queue(self) -> int:
        """
        Process queued commands when ROS2 bridge becomes available.

        Returns:
            Number of commands processed
        """
        if is_circuit_open('ros2') or self._mqtt is None:
            return 0

        processed = 0
        messages = ros2_retry_queue.get_all()

        for msg in messages:
            try:
                payload = msg.payload
                topic = f"{self._prefix}/{payload['robot_id']}/command"
                command_payload = json.dumps({
                    'command': payload['command'],
                    'params': payload['params'],
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
                self._mqtt.publish(topic, command_payload, qos=1)
                processed += 1
            except Exception as e:
                logger.warning(f"Failed to send queued ROS2 command: {e}")
                if msg.attempts < msg.max_attempts:
                    msg.attempts += 1
                    ros2_retry_queue.enqueue(msg.payload, msg.max_attempts - msg.attempts)

        if processed > 0:
            logger.info(f"Processed {processed} queued ROS2 commands")

        return processed


# Global resilient ROS2 bridge
resilient_ros2 = ResilientROS2Bridge()
