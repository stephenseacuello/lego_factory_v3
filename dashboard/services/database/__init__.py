"""
Database Service Layer - Database Abstraction and Management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Provides database connection pooling, migrations, and query abstraction.
"""

from .connection_pool import ConnectionPool, DatabaseConnection, PoolConfig
from .query_builder import QueryBuilder, Query, QueryType
from .migration_manager import MigrationManager, Migration, MigrationStatus
from .repository import Repository, BaseEntity

__all__ = [
    # Connection Pool
    'ConnectionPool',
    'DatabaseConnection',
    'PoolConfig',
    # Query Builder
    'QueryBuilder',
    'Query',
    'QueryType',
    # Migrations
    'MigrationManager',
    'Migration',
    'MigrationStatus',
    # Repository
    'Repository',
    'BaseEntity',
]
