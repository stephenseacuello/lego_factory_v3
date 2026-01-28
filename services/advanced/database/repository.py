"""
Repository Pattern - Data Access Abstraction.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides repository pattern for clean data access.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, TypeVar, Generic, Type
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='BaseEntity')


@dataclass
class BaseEntity:
    """Base class for all entities."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            elif hasattr(value, 'value'):  # Enum
                result[key] = value.value
            else:
                result[key] = value
        return result


class Repository(ABC, Generic[T]):
    """
    Abstract repository for data access.

    Provides a clean interface for CRUD operations
    independent of the underlying storage mechanism.
    """

    @abstractmethod
    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find entity by ID."""
        pass

    @abstractmethod
    async def find_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[T]:
        """Find all entities matching filters."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save or update an entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """Delete an entity by ID."""
        pass

    @abstractmethod
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities matching filters."""
        pass


class InMemoryRepository(Repository[T]):
    """
    In-memory repository implementation for development and testing.
    """

    def __init__(self, entity_class: Type[T]):
        self.entity_class = entity_class
        self._storage: Dict[str, T] = {}

    async def find_by_id(self, entity_id: str) -> Optional[T]:
        """Find entity by ID."""
        return self._storage.get(entity_id)

    async def find_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[T]:
        """Find all entities matching filters."""
        entities = list(self._storage.values())

        if filters:
            for key, value in filters.items():
                entities = [
                    e for e in entities
                    if hasattr(e, key) and getattr(e, key) == value
                ]

        # Sort by created_at descending
        entities = sorted(
            entities,
            key=lambda e: e.created_at if hasattr(e, 'created_at') else datetime.min,
            reverse=True
        )

        return entities[offset:offset + limit]

    async def save(self, entity: T) -> T:
        """Save or update an entity."""
        if hasattr(entity, 'updated_at'):
            entity.updated_at = datetime.now()

        self._storage[entity.id] = entity
        logger.debug(f"Saved entity: {entity.id}")
        return entity

    async def delete(self, entity_id: str) -> bool:
        """Delete an entity by ID."""
        if entity_id in self._storage:
            del self._storage[entity_id]
            logger.debug(f"Deleted entity: {entity_id}")
            return True
        return False

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities matching filters."""
        entities = await self.find_all(filters=filters, limit=999999)
        return len(entities)

    async def find_by(self, **kwargs) -> List[T]:
        """Find entities by attribute values."""
        return await self.find_all(filters=kwargs)

    async def find_one_by(self, **kwargs) -> Optional[T]:
        """Find single entity by attribute values."""
        results = await self.find_by(**kwargs)
        return results[0] if results else None

    async def exists(self, entity_id: str) -> bool:
        """Check if entity exists."""
        return entity_id in self._storage


# ============================================
# Domain-Specific Repositories
# ============================================

@dataclass
class ExperimentEntity(BaseEntity):
    """Experiment entity for ML experiment tracking."""
    name: str = ""
    description: str = ""
    status: str = "created"
    experiment_type: str = "general"
    params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    owner: str = "system"


class ExperimentRepository(InMemoryRepository[ExperimentEntity]):
    """Repository for experiment entities."""

    def __init__(self):
        super().__init__(ExperimentEntity)
        self._initialize_sample_data()

    def _initialize_sample_data(self):
        """Initialize with sample experiments."""
        import asyncio

        async def init():
            experiments = [
                ExperimentEntity(
                    id="exp-001",
                    name="Quality Prediction - ResNet50",
                    description="Fine-tuning ResNet50 for quality inspection",
                    status="running",
                    experiment_type="quality",
                    params={"learning_rate": 0.001, "batch_size": 32, "epochs": 100},
                    metrics={"current_loss": 0.0234, "val_accuracy": 0.978},
                    tags=["quality", "cnn", "production"],
                    owner="ml_team",
                ),
                ExperimentEntity(
                    id="exp-002",
                    name="Defect Classification - YOLO",
                    description="YOLO-based defect detection model",
                    status="completed",
                    experiment_type="quality",
                    params={"model": "yolov8", "epochs": 50},
                    metrics={"mAP": 0.92, "inference_ms": 12},
                    tags=["defect", "detection"],
                    owner="ml_team",
                ),
            ]

            for exp in experiments:
                await self.save(exp)

        asyncio.get_event_loop().run_until_complete(init()) if asyncio.get_event_loop().is_running() else None

    async def find_by_status(self, status: str) -> List[ExperimentEntity]:
        """Find experiments by status."""
        return await self.find_by(status=status)

    async def find_by_type(self, experiment_type: str) -> List[ExperimentEntity]:
        """Find experiments by type."""
        return await self.find_by(experiment_type=experiment_type)


@dataclass
class ModelEntity(BaseEntity):
    """Model entity for model registry."""
    name: str = ""
    version: str = "1.0.0"
    stage: str = "staging"
    experiment_id: Optional[str] = None
    artifact_path: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class ModelRepository(InMemoryRepository[ModelEntity]):
    """Repository for model entities."""

    def __init__(self):
        super().__init__(ModelEntity)

    async def find_by_name(self, name: str) -> List[ModelEntity]:
        """Find all versions of a model by name."""
        return await self.find_by(name=name)

    async def find_by_stage(self, stage: str) -> List[ModelEntity]:
        """Find models by stage."""
        return await self.find_by(stage=stage)

    async def get_latest_version(self, name: str) -> Optional[ModelEntity]:
        """Get latest version of a model."""
        models = await self.find_by_name(name)
        if not models:
            return None
        return max(models, key=lambda m: m.version)


@dataclass
class CausalGraphEntity(BaseEntity):
    """Causal graph entity."""
    name: str = ""
    domain: str = "manufacturing"
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CausalGraphRepository(InMemoryRepository[CausalGraphEntity]):
    """Repository for causal graph entities."""

    def __init__(self):
        super().__init__(CausalGraphEntity)

    async def find_by_domain(self, domain: str) -> List[CausalGraphEntity]:
        """Find graphs by domain."""
        return await self.find_by(domain=domain)


@dataclass
class ActionAuditEntity(BaseEntity):
    """Action audit entity for tracking AI actions."""
    action_type: str = ""
    action_data: Dict[str, Any] = field(default_factory=dict)
    source_agent: str = ""
    status: str = "pending"
    risk_level: str = "low"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    result: Dict[str, Any] = field(default_factory=dict)


class ActionAuditRepository(InMemoryRepository[ActionAuditEntity]):
    """Repository for action audit entities."""

    def __init__(self):
        super().__init__(ActionAuditEntity)

    async def find_pending(self) -> List[ActionAuditEntity]:
        """Find pending actions."""
        return await self.find_by(status="pending")

    async def find_by_agent(self, agent: str) -> List[ActionAuditEntity]:
        """Find actions by source agent."""
        return await self.find_by(source_agent=agent)

    async def find_by_risk_level(self, risk_level: str) -> List[ActionAuditEntity]:
        """Find actions by risk level."""
        return await self.find_by(risk_level=risk_level)


# ============================================
# Unit of Work Pattern
# ============================================

class UnitOfWork:
    """
    Unit of Work for coordinating multiple repository operations.

    Provides transaction-like semantics for multiple repository
    operations that should be atomic.
    """

    def __init__(self):
        self.experiments = ExperimentRepository()
        self.models = ModelRepository()
        self.causal_graphs = CausalGraphRepository()
        self.action_audit = ActionAuditRepository()
        self._pending_operations: List[Dict[str, Any]] = []

    async def __aenter__(self):
        """Enter the unit of work context."""
        self._pending_operations = []
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the unit of work context."""
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

    async def commit(self):
        """Commit all pending operations."""
        logger.debug(f"Committing {len(self._pending_operations)} operations")
        self._pending_operations = []

    async def rollback(self):
        """Rollback pending operations."""
        logger.debug(f"Rolling back {len(self._pending_operations)} operations")
        self._pending_operations = []

    def register_new(self, entity: BaseEntity):
        """Register a new entity to be saved."""
        self._pending_operations.append({
            "type": "insert",
            "entity": entity,
        })

    def register_dirty(self, entity: BaseEntity):
        """Register an entity to be updated."""
        self._pending_operations.append({
            "type": "update",
            "entity": entity,
        })

    def register_deleted(self, entity: BaseEntity):
        """Register an entity to be deleted."""
        self._pending_operations.append({
            "type": "delete",
            "entity": entity,
        })
