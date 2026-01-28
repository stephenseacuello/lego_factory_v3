"""
LEGO Factory v3 - ISA-88 Recipe Models
=======================================
Recipe management models following ISA-88 standard.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, ForeignKey, Index, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import BaseModel, AuditedModel, VersionedModel


class RecipeType(PyEnum):
    """ISA-88 Recipe types."""
    GENERAL = "general"      # Site-wide default
    SITE = "site"            # Site-specific
    MASTER = "master"        # Master recipe (versioned template)
    CONTROL = "control"      # Control recipe (work order instance)


class RecipeStatus(PyEnum):
    """Recipe lifecycle status."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RELEASED = "released"
    OBSOLETE = "obsolete"
    REJECTED = "rejected"


class ApprovalStatus(PyEnum):
    """Approval workflow status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MasterRecipe(VersionedModel):
    """
    ISA-88 Master Recipe.

    Master recipes are versioned templates that define how to
    produce a product. They contain G-code, parameters, and
    quality specifications.
    """
    __tablename__ = 'master_recipes'

    # Identification
    recipe_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Version (combined with recipe_id for uniqueness)
    recipe_version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)

    # Classification
    recipe_type: Mapped[RecipeType] = mapped_column(Enum(RecipeType), default=RecipeType.MASTER)
    status: Mapped[RecipeStatus] = mapped_column(Enum(RecipeStatus), default=RecipeStatus.DRAFT)

    # Product
    product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Machine requirements
    machine_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    required_capabilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # G-code content
    gcode_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gcode_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gcode_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Parameters
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"feed_rate": 1000, "spindle_rpm": 12000, "tool_number": 1}

    # Print profile (for 3D printing)
    print_profile: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"layer_height": 0.2, "infill": 20, "supports": true}

    # Material requirements
    materials: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Example: [{"item_id": "PLA-WHITE", "quantity": 50, "unit": "g"}]

    # Tool requirements
    tools: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Example: [{"tool_number": 1, "tool_type": "end_mill", "diameter": 6}]

    # Quality specifications
    quality_specs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Example: {"tolerance_mm": 0.1, "surface_finish": "Ra 1.6"}

    # Estimated times
    estimated_cycle_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_setup_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Approval tracking
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Release tracking
    released_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    control_recipes = relationship("ControlRecipe", back_populates="master_recipe", lazy="dynamic")
    approvals = relationship("RecipeApproval", back_populates="recipe", lazy="dynamic")

    __table_args__ = (
        Index('ix_recipes_id_version', 'recipe_id', 'recipe_version', unique=True),
        Index('ix_recipes_status', 'status'),
        Index('ix_recipes_product', 'product_id'),
    )

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'recipe_id': self.recipe_id,
            'name': self.name,
            'description': self.description,
            'recipe_version': self.recipe_version,
            'is_latest': self.is_latest,
            'recipe_type': self.recipe_type.value,
            'status': self.status.value,
            'product_id': self.product_id,
            'machine_type': self.machine_type,
            'parameters': self.parameters,
            'estimated_cycle_time_seconds': self.estimated_cycle_time_seconds,
            'version': self.version,
        }


class ControlRecipe(AuditedModel):
    """
    ISA-88 Control Recipe.

    Control recipes are instances of master recipes created for
    specific work orders. They may have parameter overrides.
    """
    __tablename__ = 'control_recipes'

    # Reference to master
    master_recipe_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('master_recipes.id'), nullable=False)
    master_recipe = relationship("MasterRecipe", back_populates="control_recipes")

    # Work order reference (filled in when MES module exists)
    work_order_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Parameter overrides
    parameter_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Machine assignment
    machine_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('machines.id'), nullable=True)

    # Execution status
    status: Mapped[str] = mapped_column(String(50), default='pending')  # pending, loaded, running, completed, aborted
    loaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Actual times
    actual_cycle_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_setup_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Results
    parts_produced: Mapped[int] = mapped_column(Integer, default=0)
    parts_rejected: Mapped[int] = mapped_column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'master_recipe_id': str(self.master_recipe_id),
            'work_order_id': str(self.work_order_id) if self.work_order_id else None,
            'machine_id': str(self.machine_id) if self.machine_id else None,
            'status': self.status,
            'parameter_overrides': self.parameter_overrides,
            'parts_produced': self.parts_produced,
            'parts_rejected': self.parts_rejected,
        }


class RecipeApproval(AuditedModel):
    """Recipe approval workflow."""
    __tablename__ = 'recipe_approvals'

    recipe_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('master_recipes.id'), nullable=False)
    recipe = relationship("MasterRecipe", back_populates="approvals")

    # Approval details
    approver: Mapped[str] = mapped_column(String(100), nullable=False)
    approval_role: Mapped[str] = mapped_column(String(50), nullable=False)  # engineering, quality, production
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RecipeParameter(AuditedModel):
    """Recipe parameter definitions for templating."""
    __tablename__ = 'recipe_parameters'

    recipe_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('master_recipes.id'), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # float, int, string, bool
    default_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    units: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
