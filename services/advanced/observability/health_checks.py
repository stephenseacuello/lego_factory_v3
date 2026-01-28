"""
LEGO Factory v3 - Specialized Health Checks
============================================
Health check implementations for infrastructure services.

Provides health checks for:
- PostgreSQL database connectivity
- Redis cache connectivity
- MQTT broker connectivity
- TimescaleDB historian

Reference: Kubernetes health probe patterns, ISA-95 availability requirements
"""

import asyncio
import logging
import os
from typing import Any, Callable, Dict, Optional

from services.advanced.observability.health import (
    HealthCheck,
    CheckResult,
    HealthStatus,
    CheckType,
    TCPHealthCheck,
)

logger = logging.getLogger(__name__)


class PostgreSQLHealthCheck(HealthCheck):
    """
    PostgreSQL database connectivity health check.

    Executes a simple query to verify database connectivity
    and query execution capability.

    Usage:
        >>> check = PostgreSQLHealthCheck("db", connection_string)
        >>> result = await check.check()
    """

    def __init__(
        self,
        name: str,
        connection_string: Optional[str] = None,
        query: str = "SELECT 1",
        **kwargs
    ):
        """
        Initialize PostgreSQL health check.

        Args:
            name: Check name
            connection_string: Database URL (defaults to DATABASE_URL env var)
            query: Health check query (default: SELECT 1)
        """
        super().__init__(name, **kwargs)
        self.connection_string = connection_string or os.getenv('DATABASE_URL')
        self.query = query

    async def check(self) -> CheckResult:
        """Check PostgreSQL connectivity."""
        if not self.connection_string:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="DATABASE_URL not configured"
            )

        try:
            # Try to import and use the database module
            from config.database import get_engine

            loop = asyncio.get_event_loop()

            def _check_db():
                engine = get_engine()
                if engine is None:
                    return False, "Database engine not initialized"
                with engine.connect() as conn:
                    result = conn.execute(self.query)
                    result.close()
                    return True, "Database connection successful"

            success, message = await loop.run_in_executor(None, _check_db)

            if success:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=message,
                    details={"query": self.query}
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=message
                )

        except ImportError:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Database module not available"
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {str(e)}"
            )


class RedisHealthCheck(HealthCheck):
    """
    Redis cache connectivity health check.

    Performs a PING command to verify Redis is responsive.

    Usage:
        >>> check = RedisHealthCheck("redis")
        >>> result = await check.check()
    """

    def __init__(
        self,
        name: str,
        redis_url: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        **kwargs
    ):
        """
        Initialize Redis health check.

        Args:
            name: Check name
            redis_url: Redis URL (defaults to REDIS_URL env var)
            host: Redis host (fallback if URL not provided)
            port: Redis port
            password: Redis password
            db: Redis database number
        """
        super().__init__(name, **kwargs)
        self.redis_url = redis_url or os.getenv('REDIS_URL')
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port
        self.password = password or os.getenv('REDIS_PASSWORD')
        self.db = db

    async def check(self) -> CheckResult:
        """Check Redis connectivity."""
        try:
            import redis

            loop = asyncio.get_event_loop()

            def _check_redis():
                if self.redis_url:
                    client = redis.from_url(self.redis_url, socket_timeout=self.timeout)
                else:
                    client = redis.Redis(
                        host=self.host,
                        port=self.port,
                        password=self.password,
                        db=self.db,
                        socket_timeout=self.timeout
                    )

                try:
                    response = client.ping()
                    info = client.info('server')
                    return response, {
                        'redis_version': info.get('redis_version', 'unknown'),
                        'connected_clients': client.info('clients').get('connected_clients', 0),
                        'used_memory_human': client.info('memory').get('used_memory_human', 'unknown')
                    }
                finally:
                    client.close()

            response, details = await loop.run_in_executor(None, _check_redis)

            if response:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Redis PING successful",
                    details=details
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Redis PING failed"
                )

        except ImportError:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="redis-py library not installed"
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check failed: {str(e)}",
                details={"host": self.host, "port": self.port}
            )


class MQTTHealthCheck(HealthCheck):
    """
    MQTT broker connectivity health check.

    Attempts to connect to the MQTT broker to verify availability.

    Usage:
        >>> check = MQTTHealthCheck("mqtt", host="localhost", port=1883)
        >>> result = await check.check()
    """

    def __init__(
        self,
        name: str,
        host: Optional[str] = None,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        **kwargs
    ):
        """
        Initialize MQTT health check.

        Args:
            name: Check name
            host: MQTT broker host
            port: MQTT broker port (default: 1883)
            username: MQTT username
            password: MQTT password
            use_tls: Enable TLS
        """
        super().__init__(name, **kwargs)
        self.host = host or os.getenv('MQTT_HOST', os.getenv('ROS2_MQTT_HOST', 'localhost'))
        self.port = port or int(os.getenv('MQTT_PORT', os.getenv('ROS2_MQTT_PORT', '1883')))
        self.username = username or os.getenv('MQTT_USERNAME')
        self.password = password or os.getenv('MQTT_PASSWORD')
        self.use_tls = use_tls

    async def check(self) -> CheckResult:
        """Check MQTT broker connectivity."""
        try:
            import paho.mqtt.client as mqtt
            import threading
            import time

            connected = threading.Event()
            connect_result = {'rc': -1}

            def on_connect(client, userdata, flags, rc):
                connect_result['rc'] = rc
                connected.set()

            loop = asyncio.get_event_loop()

            def _check_mqtt():
                client = mqtt.Client(client_id=f"health_check_{int(time.time())}")

                if self.username:
                    client.username_pw_set(self.username, self.password)

                if self.use_tls:
                    client.tls_set()

                client.on_connect = on_connect

                try:
                    client.connect(self.host, self.port, keepalive=5)
                    client.loop_start()

                    # Wait for connection
                    if connected.wait(timeout=self.timeout):
                        rc = connect_result['rc']
                        if rc == 0:
                            return True, "MQTT connection successful"
                        else:
                            return False, f"MQTT connection failed with code {rc}"
                    else:
                        return False, "MQTT connection timeout"
                finally:
                    client.loop_stop()
                    client.disconnect()

            success, message = await loop.run_in_executor(None, _check_mqtt)

            if success:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=message,
                    details={"host": self.host, "port": self.port}
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=message,
                    details={"host": self.host, "port": self.port}
                )

        except ImportError:
            # Fall back to TCP check if paho-mqtt not installed
            tcp_check = TCPHealthCheck(
                name=self.name,
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            result = await tcp_check.check()
            if result.status == HealthStatus.HEALTHY:
                result.message = "MQTT broker TCP port reachable (paho-mqtt not installed for full check)"
            return result

        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"MQTT check failed: {str(e)}",
                details={"host": self.host, "port": self.port}
            )


class TimescaleDBHealthCheck(HealthCheck):
    """
    TimescaleDB historian health check.

    Verifies TimescaleDB extension is loaded and operational.

    Usage:
        >>> check = TimescaleDBHealthCheck("timescale")
        >>> result = await check.check()
    """

    def __init__(
        self,
        name: str,
        connection_string: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize TimescaleDB health check.

        Args:
            name: Check name
            connection_string: Database URL
        """
        super().__init__(name, **kwargs)
        self.connection_string = connection_string or os.getenv('DATABASE_URL')

    async def check(self) -> CheckResult:
        """Check TimescaleDB availability."""
        if not self.connection_string:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="DATABASE_URL not configured"
            )

        try:
            from config.database import get_engine
            from sqlalchemy import text

            loop = asyncio.get_event_loop()

            def _check_timescale():
                engine = get_engine()
                if engine is None:
                    return False, "Database engine not initialized", {}

                with engine.connect() as conn:
                    # Check if TimescaleDB extension is installed
                    result = conn.execute(text(
                        "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
                    ))
                    row = result.fetchone()

                    if row:
                        version = row[0]
                        # Check hypertable count
                        ht_result = conn.execute(text(
                            "SELECT count(*) FROM timescaledb_information.hypertables"
                        ))
                        ht_count = ht_result.scalar()

                        return True, f"TimescaleDB {version} operational", {
                            'version': version,
                            'hypertable_count': ht_count
                        }
                    else:
                        return False, "TimescaleDB extension not installed", {}

            success, message, details = await loop.run_in_executor(None, _check_timescale)

            if success:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=message,
                    details=details
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=message,
                    details=details
                )

        except ImportError:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Database module not available"
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"TimescaleDB check failed: {str(e)}"
            )


def create_infrastructure_checks(
    check_database: bool = True,
    check_redis: bool = True,
    check_mqtt: bool = True,
    check_timescale: bool = True
) -> Dict[str, HealthCheck]:
    """
    Create standard infrastructure health checks.

    Args:
        check_database: Include PostgreSQL check
        check_redis: Include Redis check
        check_mqtt: Include MQTT check
        check_timescale: Include TimescaleDB check

    Returns:
        Dictionary of health checks by name

    Usage:
        >>> checks = create_infrastructure_checks()
        >>> for name, check in checks.items():
        ...     result = await check.run()
        ...     print(f"{name}: {result.status}")
    """
    checks = {}

    if check_database:
        checks['postgresql'] = PostgreSQLHealthCheck(
            name='postgresql',
            check_type=CheckType.READINESS,
            timeout=5.0,
            critical=True
        )

    if check_redis:
        checks['redis'] = RedisHealthCheck(
            name='redis',
            check_type=CheckType.READINESS,
            timeout=3.0,
            critical=False  # Redis can be optional
        )

    if check_mqtt:
        checks['mqtt'] = MQTTHealthCheck(
            name='mqtt',
            check_type=CheckType.READINESS,
            timeout=5.0,
            critical=False  # MQTT can be optional
        )

    if check_timescale:
        checks['timescaledb'] = TimescaleDBHealthCheck(
            name='timescaledb',
            check_type=CheckType.READINESS,
            timeout=5.0,
            critical=False  # TimescaleDB is optional
        )

    return checks
