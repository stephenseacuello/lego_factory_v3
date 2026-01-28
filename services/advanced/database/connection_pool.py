"""
Connection Pool - Database Connection Management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides connection pooling and database abstraction.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, AsyncContextManager
from datetime import datetime, timedelta
from enum import Enum
from contextlib import asynccontextmanager
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MYSQL = "mysql"
    TIMESCALEDB = "timescaledb"
    INFLUXDB = "influxdb"


class ConnectionState(Enum):
    """Connection state."""
    AVAILABLE = "available"
    IN_USE = "in_use"
    STALE = "stale"
    CLOSED = "closed"


@dataclass
class PoolConfig:
    """Connection pool configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "lego_mcp"
    username: str = "lego_mcp"
    password: str = ""
    database_type: DatabaseType = DatabaseType.POSTGRESQL
    min_connections: int = 5
    max_connections: int = 20
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_lifetime: int = 3600
    ssl_mode: str = "prefer"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "database_type": self.database_type.value,
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout,
            "idle_timeout": self.idle_timeout,
            "max_lifetime": self.max_lifetime,
            "ssl_mode": self.ssl_mode,
        }


@dataclass
class DatabaseConnection:
    """A database connection."""
    connection_id: str
    pool_id: str
    state: ConnectionState
    created_at: datetime
    last_used_at: datetime
    use_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "connection_id": self.connection_id,
            "pool_id": self.pool_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat(),
            "use_count": self.use_count,
            "last_error": self.last_error,
        }

    @property
    def age_seconds(self) -> float:
        """Get connection age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        """Get idle time in seconds."""
        return (datetime.now() - self.last_used_at).total_seconds()


class ConnectionPool:
    """
    Database connection pool manager.

    Features:
    - Connection pooling with min/max limits
    - Automatic connection recycling
    - Health checking
    - Metrics collection
    - Async context manager support
    """

    def __init__(self, config: PoolConfig):
        self.config = config
        self.pool_id = f"pool-{uuid.uuid4().hex[:8]}"
        self.connections: Dict[str, DatabaseConnection] = {}
        self._lock = asyncio.Lock()
        self._available = asyncio.Queue()
        self._initialized = False
        self._stats = {
            "total_connections_created": 0,
            "total_connections_recycled": 0,
            "total_queries_executed": 0,
            "total_errors": 0,
            "peak_connections": 0,
        }

    async def initialize(self):
        """Initialize the connection pool."""
        if self._initialized:
            return

        logger.info(f"Initializing connection pool {self.pool_id}")

        # Create minimum connections
        for _ in range(self.config.min_connections):
            conn = await self._create_connection()
            await self._available.put(conn.connection_id)

        self._initialized = True
        logger.info(f"Pool initialized with {len(self.connections)} connections")

    async def _create_connection(self) -> DatabaseConnection:
        """Create a new database connection."""
        conn_id = f"conn-{uuid.uuid4().hex[:8]}"

        connection = DatabaseConnection(
            connection_id=conn_id,
            pool_id=self.pool_id,
            state=ConnectionState.AVAILABLE,
            created_at=datetime.now(),
            last_used_at=datetime.now(),
        )

        self.connections[conn_id] = connection
        self._stats["total_connections_created"] += 1
        self._stats["peak_connections"] = max(
            self._stats["peak_connections"],
            len(self.connections)
        )

        logger.debug(f"Created connection: {conn_id}")
        return connection

    async def acquire(self, timeout: Optional[float] = None) -> DatabaseConnection:
        """Acquire a connection from the pool."""
        if not self._initialized:
            await self.initialize()

        timeout = timeout or self.config.connection_timeout

        async with self._lock:
            # Try to get from available queue
            try:
                conn_id = await asyncio.wait_for(
                    self._available.get(),
                    timeout=timeout
                )
                connection = self.connections.get(conn_id)

                if connection:
                    # Check if connection is still valid
                    if await self._is_healthy(connection):
                        connection.state = ConnectionState.IN_USE
                        connection.last_used_at = datetime.now()
                        connection.use_count += 1
                        return connection
                    else:
                        # Recycle stale connection
                        await self._recycle_connection(connection)

            except asyncio.TimeoutError:
                pass

            # Create new connection if under max
            if len(self.connections) < self.config.max_connections:
                connection = await self._create_connection()
                connection.state = ConnectionState.IN_USE
                connection.use_count = 1
                return connection

            raise RuntimeError("Connection pool exhausted")

    async def release(self, connection: DatabaseConnection):
        """Release a connection back to the pool."""
        async with self._lock:
            if connection.connection_id not in self.connections:
                return

            # Check if connection should be recycled
            if (connection.age_seconds > self.config.max_lifetime or
                connection.last_error):
                await self._recycle_connection(connection)
                return

            connection.state = ConnectionState.AVAILABLE
            connection.last_used_at = datetime.now()
            await self._available.put(connection.connection_id)

    async def _is_healthy(self, connection: DatabaseConnection) -> bool:
        """Check if connection is healthy."""
        # Check age
        if connection.age_seconds > self.config.max_lifetime:
            return False

        # Check idle time
        if connection.idle_seconds > self.config.idle_timeout:
            return False

        # Check state
        if connection.state == ConnectionState.STALE:
            return False

        return True

    async def _recycle_connection(self, connection: DatabaseConnection):
        """Recycle an old/stale connection."""
        if connection.connection_id in self.connections:
            del self.connections[connection.connection_id]
            self._stats["total_connections_recycled"] += 1
            logger.debug(f"Recycled connection: {connection.connection_id}")

        # Create replacement if under minimum
        if len(self.connections) < self.config.min_connections:
            new_conn = await self._create_connection()
            await self._available.put(new_conn.connection_id)

    @asynccontextmanager
    async def connection(self):
        """Async context manager for acquiring a connection."""
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)

    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a query using a pooled connection."""
        async with self.connection() as conn:
            try:
                # Simulate query execution
                self._stats["total_queries_executed"] += 1

                return {
                    "success": True,
                    "connection_id": conn.connection_id,
                    "query": query,
                    "params": params,
                    "rows_affected": 0,
                    "execution_time_ms": 5,
                }

            except Exception as e:
                conn.last_error = str(e)
                self._stats["total_errors"] += 1
                raise

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        available = sum(
            1 for c in self.connections.values()
            if c.state == ConnectionState.AVAILABLE
        )
        in_use = sum(
            1 for c in self.connections.values()
            if c.state == ConnectionState.IN_USE
        )

        return {
            "pool_id": self.pool_id,
            "database_type": self.config.database_type.value,
            "current_connections": len(self.connections),
            "available_connections": available,
            "in_use_connections": in_use,
            "min_connections": self.config.min_connections,
            "max_connections": self.config.max_connections,
            **self._stats,
        }

    async def close(self):
        """Close all connections and shut down the pool."""
        logger.info(f"Closing connection pool {self.pool_id}")

        async with self._lock:
            for conn in list(self.connections.values()):
                conn.state = ConnectionState.CLOSED
            self.connections.clear()
            self._initialized = False

        logger.info("Connection pool closed")


class MultiDatabasePool:
    """
    Manages multiple database connection pools.

    Useful for applications that connect to multiple databases
    (e.g., PostgreSQL for main data, TimescaleDB for time-series).
    """

    def __init__(self):
        self.pools: Dict[str, ConnectionPool] = {}

    async def add_pool(
        self,
        name: str,
        config: PoolConfig,
    ) -> ConnectionPool:
        """Add a new connection pool."""
        pool = ConnectionPool(config)
        await pool.initialize()
        self.pools[name] = pool
        logger.info(f"Added pool: {name}")
        return pool

    def get_pool(self, name: str) -> Optional[ConnectionPool]:
        """Get a pool by name."""
        return self.pools.get(name)

    async def execute(
        self,
        pool_name: str,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a query on a specific pool."""
        pool = self.pools.get(pool_name)
        if not pool:
            raise ValueError(f"Pool not found: {pool_name}")
        return await pool.execute(query, params)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get stats for all pools."""
        return {name: pool.get_stats() for name, pool in self.pools.items()}

    async def close_all(self):
        """Close all pools."""
        for pool in self.pools.values():
            await pool.close()
        self.pools.clear()
