"""
LEGO Factory v3 - Database Configuration
=========================================
PostgreSQL + TimescaleDB setup with connection pooling.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool

from config.settings import get_config

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_session_factory = None
_scoped_session = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        config = get_config()
        _engine = create_engine(
            config.database.url,
            poolclass=QueuePool,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=config.debug,
        )

        # Enable connection event logging
        @event.listens_for(_engine, "connect")
        def connect(dbapi_connection, connection_record):
            logger.debug("Database connection established")

        @event.listens_for(_engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Database connection checked out from pool")

    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def get_scoped_session():
    """Get or create a scoped session for thread-safe access."""
    global _scoped_session
    if _scoped_session is None:
        _scoped_session = scoped_session(get_session_factory())
    return _scoped_session


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def init_timescaledb():
    """Initialize TimescaleDB extension and create hypertables."""
    engine = get_engine()

    with engine.connect() as conn:
        # Enable TimescaleDB extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
        conn.commit()
        logger.info("TimescaleDB extension enabled")


def create_hypertable(table_name: str, time_column: str = 'time',
                      chunk_time_interval: str = '1 day'):
    """Convert a table to a TimescaleDB hypertable."""
    engine = get_engine()

    with engine.connect() as conn:
        # Check if already a hypertable
        result = conn.execute(text(f"""
            SELECT * FROM timescaledb_information.hypertables
            WHERE hypertable_name = :table_name
        """), {'table_name': table_name})

        if result.fetchone() is None:
            conn.execute(text(f"""
                SELECT create_hypertable(
                    :table_name,
                    :time_column,
                    chunk_time_interval => INTERVAL :interval,
                    if_not_exists => TRUE
                );
            """), {
                'table_name': table_name,
                'time_column': time_column,
                'interval': chunk_time_interval
            })
            conn.commit()
            logger.info(f"Created hypertable: {table_name}")
        else:
            logger.info(f"Hypertable already exists: {table_name}")


def setup_continuous_aggregates():
    """Create continuous aggregates for historian data."""
    engine = get_engine()

    with engine.connect() as conn:
        # 1-minute aggregate
        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS tag_values_1min
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 minute', time) AS bucket,
                tag_id,
                AVG(value_numeric) AS avg_value,
                MIN(value_numeric) AS min_value,
                MAX(value_numeric) AS max_value,
                COUNT(*) AS sample_count
            FROM tag_values
            GROUP BY bucket, tag_id
            WITH NO DATA;
        """))

        # 1-hour aggregate
        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS tag_values_1hour
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', time) AS bucket,
                tag_id,
                AVG(value_numeric) AS avg_value,
                MIN(value_numeric) AS min_value,
                MAX(value_numeric) AS max_value,
                COUNT(*) AS sample_count
            FROM tag_values
            GROUP BY bucket, tag_id
            WITH NO DATA;
        """))

        # 1-day aggregate
        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS tag_values_1day
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 day', time) AS bucket,
                tag_id,
                AVG(value_numeric) AS avg_value,
                MIN(value_numeric) AS min_value,
                MAX(value_numeric) AS max_value,
                COUNT(*) AS sample_count
            FROM tag_values
            GROUP BY bucket, tag_id
            WITH NO DATA;
        """))

        conn.commit()
        logger.info("Continuous aggregates created")


def setup_retention_policies():
    """Set up data retention policies."""
    config = get_config()
    engine = get_engine()

    with engine.connect() as conn:
        # Raw data retention
        conn.execute(text(f"""
            SELECT add_retention_policy('tag_values',
                INTERVAL '{config.historian.retention_raw_days} days',
                if_not_exists => TRUE
            );
        """))

        # 1-minute aggregate retention
        conn.execute(text(f"""
            SELECT add_retention_policy('tag_values_1min',
                INTERVAL '{config.historian.retention_1min_days} days',
                if_not_exists => TRUE
            );
        """))

        # 1-hour aggregate retention
        conn.execute(text(f"""
            SELECT add_retention_policy('tag_values_1hour',
                INTERVAL '{config.historian.retention_1hour_days} days',
                if_not_exists => TRUE
            );
        """))

        conn.commit()
        logger.info("Retention policies configured")


def setup_compression_policies():
    """Enable compression for older data."""
    engine = get_engine()

    with engine.connect() as conn:
        # Enable compression on tag_values
        conn.execute(text("""
            ALTER TABLE tag_values SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'tag_id'
            );
        """))

        # Compress data older than 7 days
        conn.execute(text("""
            SELECT add_compression_policy('tag_values',
                INTERVAL '7 days',
                if_not_exists => TRUE
            );
        """))

        conn.commit()
        logger.info("Compression policies configured")


def init_database():
    """Full database initialization."""
    logger.info("Initializing database...")

    # Create all tables from models
    from models.base import Base
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables created")

    # Initialize TimescaleDB
    init_timescaledb()

    # Create hypertables for time-series data
    create_hypertable('tag_values', 'time')
    create_hypertable('alarm_events', 'timestamp')
    create_hypertable('sensor_readings', 'timestamp')
    create_hypertable('ml_predictions', 'timestamp')

    # Set up aggregates and policies
    try:
        setup_continuous_aggregates()
        setup_retention_policies()
        setup_compression_policies()
    except Exception as e:
        logger.warning(f"Could not set up TimescaleDB policies (may require hypertables to exist): {e}")

    logger.info("Database initialization complete")
