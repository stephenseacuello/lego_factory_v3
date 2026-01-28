"""
LEGO Factory v3 - Base Models
=============================
SQLAlchemy base classes and mixins.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Column, DateTime, String, Boolean, Integer, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    def soft_delete(self, deleted_by: str = None):
        """Mark record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by


class UUIDMixin:
    """Mixin for UUID primary key."""

    @declared_attr
    def id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4
        )


class AuditMixin:
    """Mixin for audit fields."""

    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class VersionMixin:
    """Mixin for optimistic locking."""

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    @staticmethod
    def increment_version(mapper, connection, target):
        target.version += 1


# Register version increment event
@event.listens_for(VersionMixin, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    if hasattr(target, 'version'):
        target.version += 1


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """Standard base model with UUID and timestamps."""
    __abstract__ = True


class AuditedModel(BaseModel, AuditMixin, SoftDeleteMixin):
    """Base model with full audit trail."""
    __abstract__ = True


class VersionedModel(AuditedModel, VersionMixin):
    """Base model with versioning for optimistic locking."""
    __abstract__ = True
