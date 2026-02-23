"""
Database Base Configuration

Provides SQLAlchemy setup, connection management, and base model class.
Supports both PostgreSQL (production) and SQLite (development/testing).
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, DateTime, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import QueuePool


# Database URL from environment or default
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://lego_admin:lego_mcp_2024@localhost:5432/lego_manufacturing'
)

# Determine if using SQLite (for development without Docker)
IS_SQLITE = DATABASE_URL.startswith('sqlite')

# Engine configuration
if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={'check_same_thread': False},
        echo=os.environ.get('SQL_ECHO', 'false').lower() == 'true'
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=os.environ.get('SQL_ECHO', 'false').lower() == 'true'
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Scoped session for thread safety
db = scoped_session(SessionLocal)


class BaseModel:
    """
    Base model class with common fields and methods.

    Provides:
    - UUID primary key (PostgreSQL native or string for SQLite)
    - Created/updated timestamps
    - Common query methods
    """

    # Use PostgreSQL UUID type when available
    if IS_SQLITE:
        id = Column('id', type_=str, primary_key=True, default=lambda: str(uuid.uuid4()))
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_by_id(cls, session: Session, id: str) -> Optional['BaseModel']:
        """Get record by ID."""
        return session.query(cls).filter(cls.id == id).first()

    @classmethod
    def get_all(cls, session: Session, limit: int = 100, offset: int = 0) -> list:
        """Get all records with pagination."""
        return session.query(cls).offset(offset).limit(limit).all()

    @classmethod
    def count(cls, session: Session) -> int:
        """Count all records."""
        return session.query(cls).count()

    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"


# Create declarative base with our base model
Base = declarative_base(cls=BaseModel)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all database tables. USE WITH CAUTION."""
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with get_db_session() as session:
            part = Part(name="2x4 Brick")
            session.add(part)
            session.commit()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """
    Dependency for FastAPI/Flask to get database session.

    Usage (Flask):
        @app.route('/parts')
        def list_parts():
            session = next(get_db())
            parts = Part.get_all(session)
            return jsonify([p.to_dict() for p in parts])
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Event listener to set UUID on insert for SQLite compatibility
if IS_SQLITE:
    @event.listens_for(Base, 'before_insert', propagate=True)
    def set_uuid(mapper, connection, target):
        if hasattr(target, 'id') and target.id is None:
            target.id = str(uuid.uuid4())
