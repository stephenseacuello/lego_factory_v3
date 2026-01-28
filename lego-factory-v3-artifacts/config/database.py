"""
Database Configuration for LEGO Factory
PostgreSQL with TimescaleDB extension for historian
"""

import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Database URL from environment or default
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://lego_factory:lego_factory@localhost:5432/lego_factory'
)

# Engine configuration
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_pre_ping=True,  # Verify connections before use
    echo=os.environ.get('SQL_ECHO', 'false').lower() == 'true'
)

# Session factory
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
Session = scoped_session(SessionFactory)

# Base class for all models
Base = declarative_base()


@contextmanager
def get_session():
    """Context manager for database sessions"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def get_db():
    """FastAPI dependency for database sessions"""
    session = Session()
    try:
        yield session
    finally:
        session.close()


def init_database():
    """Initialize database with required extensions and tables"""
    with engine.connect() as conn:
        # Enable TimescaleDB extension
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            logger.info("TimescaleDB extension enabled")
        except Exception as e:
            logger.warning(f"Could not enable TimescaleDB: {e}")
        
        # Enable UUID extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
        
        # Enable pg_trgm for text search
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(engine)
    logger.info("Database tables created")


def create_hypertable(table_name: str, time_column: str = 'time', chunk_interval: str = '7 days'):
    """Convert a table to a TimescaleDB hypertable"""
    with engine.connect() as conn:
        try:
            conn.execute(text(f"""
                SELECT create_hypertable(
                    '{table_name}', 
                    '{time_column}',
                    chunk_time_interval => INTERVAL '{chunk_interval}',
                    if_not_exists => TRUE
                );
            """))
            conn.commit()
            logger.info(f"Hypertable created for {table_name}")
        except Exception as e:
            logger.warning(f"Could not create hypertable for {table_name}: {e}")


def add_compression_policy(table_name: str, compress_after: str = '7 days'):
    """Add compression policy to a hypertable"""
    with engine.connect() as conn:
        try:
            # Enable compression
            conn.execute(text(f"""
                ALTER TABLE {table_name} SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'tag_id'
                );
            """))
            
            # Add compression policy
            conn.execute(text(f"""
                SELECT add_compression_policy(
                    '{table_name}', 
                    INTERVAL '{compress_after}',
                    if_not_exists => TRUE
                );
            """))
            conn.commit()
            logger.info(f"Compression policy added for {table_name}")
        except Exception as e:
            logger.warning(f"Could not add compression policy for {table_name}: {e}")


def add_retention_policy(table_name: str, drop_after: str = '2 years'):
    """Add retention policy to automatically drop old data"""
    with engine.connect() as conn:
        try:
            conn.execute(text(f"""
                SELECT add_retention_policy(
                    '{table_name}', 
                    INTERVAL '{drop_after}',
                    if_not_exists => TRUE
                );
            """))
            conn.commit()
            logger.info(f"Retention policy added for {table_name}")
        except Exception as e:
            logger.warning(f"Could not add retention policy for {table_name}: {e}")


# Connection event listeners
@event.listens_for(engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """Set search path on new connections"""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public;")
    cursor.close()


class DatabaseHealth:
    """Database health check utilities"""
    
    @staticmethod
    def check_connection() -> bool:
        """Check if database is reachable"""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    @staticmethod
    def check_timescaledb() -> bool:
        """Check if TimescaleDB extension is available"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT installed_version FROM pg_available_extensions WHERE name = 'timescaledb'"
                ))
                row = result.fetchone()
                return row is not None and row[0] is not None
        except Exception:
            return False
    
    @staticmethod
    def get_table_sizes() -> dict:
        """Get sizes of all tables"""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    schemaname || '.' || tablename AS table_name,
                    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
                LIMIT 20;
            """))
            return {row[0]: row[1] for row in result.fetchall()}
    
    @staticmethod
    def get_hypertable_info() -> list:
        """Get information about hypertables"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        hypertable_name,
                        num_chunks,
                        compression_enabled
                    FROM timescaledb_information.hypertables;
                """))
                return [dict(row._mapping) for row in result.fetchall()]
        except Exception:
            return []
