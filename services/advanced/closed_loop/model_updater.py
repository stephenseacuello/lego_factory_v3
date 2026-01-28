"""
Model Updater - Online model retraining.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning System
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class UpdateStrategy(Enum):
    """Model update strategies."""
    ONLINE = "online"        # Update with each sample
    MINI_BATCH = "mini_batch"  # Update with small batches
    SCHEDULED = "scheduled"   # Update on schedule
    DRIFT_TRIGGERED = "drift_triggered"  # Update when drift detected


@dataclass
class ModelVersion:
    """Model version tracking."""
    version_id: str
    model_id: str
    created_at: datetime
    training_samples: int
    performance_metrics: Dict[str, float]
    is_active: bool = True


@dataclass
class UpdateResult:
    """Result of model update."""
    success: bool
    model_id: str
    old_version: str
    new_version: str
    samples_used: int
    performance_change: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ModelUpdater:
    """
    Update ML models with production feedback.

    Features:
    - Multiple update strategies
    - Version management
    - Rollback capability
    - A/B testing support
    """

    def __init__(self,
                 strategy: UpdateStrategy = UpdateStrategy.MINI_BATCH,
                 min_batch_size: int = 50,
                 max_batch_size: int = 500):
        self.strategy = strategy
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size

        self._models: Dict[str, Any] = {}
        self._versions: Dict[str, List[ModelVersion]] = {}
        self._pending_samples: Dict[str, List] = {}
        self._update_callbacks: Dict[str, Callable] = {}
        self._last_update: Dict[str, datetime] = {}

    def register_model(self,
                      model_id: str,
                      model: Any,
                      update_callback: Callable) -> None:
        """
        Register a model for updates.

        Args:
            model_id: Model identifier
            model: Model object
            update_callback: Function to call for model update
        """
        self._models[model_id] = model
        self._update_callbacks[model_id] = update_callback
        self._pending_samples[model_id] = []
        self._versions[model_id] = []
        self._last_update[model_id] = datetime.utcnow()

        logger.info(f"Registered model {model_id} for updates")

    async def process_batch(self,
                           model_id: str,
                           events: List[Any]) -> Optional[UpdateResult]:
        """
        Process a batch of feedback events.

        Args:
            model_id: Target model
            events: List of ProductionEvent objects

        Returns:
            UpdateResult if model was updated
        """
        if model_id not in self._models:
            logger.warning(f"Model {model_id} not registered")
            return None

        # Add to pending samples
        self._pending_samples[model_id].extend(events)

        # Check if update should trigger
        should_update = self._should_update(model_id)

        if should_update:
            return await self._update_model(model_id)

        return None

    def _should_update(self, model_id: str) -> bool:
        """Determine if model should be updated."""
        pending = len(self._pending_samples.get(model_id, []))

        if self.strategy == UpdateStrategy.ONLINE:
            return pending > 0

        elif self.strategy == UpdateStrategy.MINI_BATCH:
            return pending >= self.min_batch_size

        elif self.strategy == UpdateStrategy.SCHEDULED:
            last = self._last_update.get(model_id)
            if last:
                return (datetime.utcnow() - last) > timedelta(hours=24)
            return True

        elif self.strategy == UpdateStrategy.DRIFT_TRIGGERED:
            # Only update when explicitly triggered
            return False

        return False

    async def _update_model(self, model_id: str) -> UpdateResult:
        """Perform model update."""
        samples = self._pending_samples[model_id][:self.max_batch_size]

        # Get current version
        current_versions = self._versions.get(model_id, [])
        old_version = current_versions[-1].version_id if current_versions else "v0"

        # Prepare training data
        X, y = self._prepare_training_data(samples)

        # Get update callback
        update_fn = self._update_callbacks.get(model_id)
        if not update_fn:
            return UpdateResult(
                success=False,
                model_id=model_id,
                old_version=old_version,
                new_version=old_version,
                samples_used=0,
                performance_change={}
            )

        try:
            # Execute update
            if asyncio.iscoroutinefunction(update_fn):
                metrics = await update_fn(self._models[model_id], X, y)
            else:
                metrics = update_fn(self._models[model_id], X, y)

            # Create new version
            import uuid
            new_version = f"v{len(current_versions) + 1}_{uuid.uuid4().hex[:6]}"

            version = ModelVersion(
                version_id=new_version,
                model_id=model_id,
                created_at=datetime.utcnow(),
                training_samples=len(samples),
                performance_metrics=metrics or {}
            )
            self._versions[model_id].append(version)

            # Clear processed samples
            self._pending_samples[model_id] = self._pending_samples[model_id][len(samples):]
            self._last_update[model_id] = datetime.utcnow()

            logger.info(f"Updated model {model_id} to version {new_version}")

            return UpdateResult(
                success=True,
                model_id=model_id,
                old_version=old_version,
                new_version=new_version,
                samples_used=len(samples),
                performance_change=metrics or {}
            )

        except Exception as e:
            logger.error(f"Model update failed for {model_id}: {e}")
            return UpdateResult(
                success=False,
                model_id=model_id,
                old_version=old_version,
                new_version=old_version,
                samples_used=0,
                performance_change={'error': str(e)}
            )

    def _prepare_training_data(self, events: List) -> tuple:
        """Prepare training data from events."""
        X = []
        y = []

        for event in events:
            if hasattr(event, 'features') and hasattr(event, 'outcome'):
                X.append(event.features)
                y.append(event.outcome.get('value', event.outcome))

        return X, y

    async def trigger_update(self, model_id: str, reason: str = "") -> Optional[UpdateResult]:
        """Manually trigger model update."""
        logger.info(f"Manual update triggered for {model_id}: {reason}")
        return await self._update_model(model_id)

    def rollback(self, model_id: str, version_id: str) -> bool:
        """Rollback to a previous model version."""
        versions = self._versions.get(model_id, [])

        for v in versions:
            if v.version_id == version_id:
                # Mark all later versions as inactive
                found = False
                for ver in versions:
                    if ver.version_id == version_id:
                        ver.is_active = True
                        found = True
                    elif found:
                        ver.is_active = False

                logger.info(f"Rolled back {model_id} to version {version_id}")
                return True

        return False

    def get_model_versions(self, model_id: str) -> List[ModelVersion]:
        """Get all versions of a model."""
        return self._versions.get(model_id, [])

    def get_statistics(self) -> Dict[str, Any]:
        """Get updater statistics."""
        return {
            'registered_models': list(self._models.keys()),
            'pending_samples': {
                mid: len(samples)
                for mid, samples in self._pending_samples.items()
            },
            'versions': {
                mid: len(versions)
                for mid, versions in self._versions.items()
            },
            'strategy': self.strategy.value
        }
