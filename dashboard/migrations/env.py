"""
Alembic Migration Environment
LegoMCP PhD-Level Manufacturing Platform

Handles database schema migrations with full audit trail
and rollback capabilities for production deployments.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.base import Base
from config import Config

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = Base.metadata


def get_url():
    """Get database URL from environment or config."""
    return os.environ.get(
        "DATABASE_URL",
        Config.SQLALCHEMY_DATABASE_URI
    )


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            version_table="alembic_version",
            version_table_schema=None,
        )

        with context.begin_transaction():
            context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter objects for migration autogenerate.

    Excludes system tables and other non-application objects.
    """
    # Exclude alembic version table
    if type_ == "table" and name == "alembic_version":
        return False

    # Exclude spatial_ref_sys (PostGIS)
    if type_ == "table" and name == "spatial_ref_sys":
        return False

    return True


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
