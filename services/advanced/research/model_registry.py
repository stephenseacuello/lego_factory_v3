"""
Model Registry - Versioned model storage and management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class ModelStage(Enum):
    """Model lifecycle stage."""
    NONE = "none"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class ModelVersion:
    """Specific version of a registered model."""
    version: int
    model_id: str
    run_id: Optional[str]  # Link to experiment run
    source_path: str
    stage: ModelStage = ModelStage.NONE
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    signature: Optional[Dict[str, Any]] = None
    requirements: List[str] = field(default_factory=list)


@dataclass
class RegisteredModel:
    """Registered model with multiple versions."""
    model_id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    versions: List[int] = field(default_factory=list)
    latest_version: int = 0


class ModelRegistry:
    """
    Central registry for ML models.

    Features:
    - Model versioning
    - Stage transitions (staging, production)
    - Model metadata and lineage
    - Input/output signatures
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self._models: Dict[str, RegisteredModel] = {}
        self._versions: Dict[str, Dict[int, ModelVersion]] = {}

    def register_model(self,
                      name: str,
                      source_path: str,
                      run_id: Optional[str] = None,
                      description: str = "",
                      tags: Optional[Dict[str, str]] = None,
                      metrics: Optional[Dict[str, float]] = None) -> ModelVersion:
        """
        Register a new model or version.

        Args:
            name: Model name
            source_path: Path to model artifacts
            run_id: Associated experiment run
            description: Version description
            tags: Model tags
            metrics: Performance metrics

        Returns:
            Created model version
        """
        # Get or create registered model
        model = self.get_model_by_name(name)

        if model is None:
            model = RegisteredModel(
                model_id=str(uuid.uuid4())[:8],
                name=name,
                description=description,
                tags=tags or {}
            )
            self._models[model.model_id] = model
            self._versions[model.model_id] = {}
            logger.info(f"Registered new model: {name}")

        # Create new version
        new_version_num = model.latest_version + 1

        version = ModelVersion(
            version=new_version_num,
            model_id=model.model_id,
            run_id=run_id,
            source_path=source_path,
            description=description,
            tags=tags or {},
            metrics=metrics or {}
        )

        self._versions[model.model_id][new_version_num] = version
        model.versions.append(new_version_num)
        model.latest_version = new_version_num
        model.last_updated_at = datetime.utcnow()

        logger.info(f"Created model version: {name} v{new_version_num}")
        return version

    def get_model(self, model_id: str) -> Optional[RegisteredModel]:
        """Get model by ID."""
        return self._models.get(model_id)

    def get_model_by_name(self, name: str) -> Optional[RegisteredModel]:
        """Get model by name."""
        for model in self._models.values():
            if model.name == name:
                return model
        return None

    def get_model_version(self,
                         model_name: str,
                         version: Optional[int] = None) -> Optional[ModelVersion]:
        """
        Get specific model version.

        Args:
            model_name: Model name
            version: Version number (latest if None)

        Returns:
            Model version or None
        """
        model = self.get_model_by_name(model_name)
        if not model:
            return None

        if version is None:
            version = model.latest_version

        return self._versions.get(model.model_id, {}).get(version)

    def get_model_versions(self, model_name: str) -> List[ModelVersion]:
        """Get all versions of a model."""
        model = self.get_model_by_name(model_name)
        if not model:
            return []

        versions = self._versions.get(model.model_id, {})
        return [versions[v] for v in sorted(versions.keys())]

    def transition_stage(self,
                        model_name: str,
                        version: int,
                        stage: ModelStage) -> bool:
        """
        Transition model version to new stage.

        Args:
            model_name: Model name
            version: Version number
            stage: Target stage

        Returns:
            Success status
        """
        model = self.get_model_by_name(model_name)
        if not model:
            logger.error(f"Model not found: {model_name}")
            return False

        version_obj = self._versions.get(model.model_id, {}).get(version)
        if not version_obj:
            logger.error(f"Version not found: {model_name} v{version}")
            return False

        # If transitioning to production, archive current production version
        if stage == ModelStage.PRODUCTION:
            for v in self._versions.get(model.model_id, {}).values():
                if v.stage == ModelStage.PRODUCTION:
                    v.stage = ModelStage.ARCHIVED
                    logger.info(f"Archived: {model_name} v{v.version}")

        old_stage = version_obj.stage
        version_obj.stage = stage
        model.last_updated_at = datetime.utcnow()

        logger.info(f"Transitioned {model_name} v{version}: {old_stage.value} -> {stage.value}")
        return True

    def get_latest_version_by_stage(self,
                                   model_name: str,
                                   stage: ModelStage) -> Optional[ModelVersion]:
        """Get latest model version in specific stage."""
        model = self.get_model_by_name(model_name)
        if not model:
            return None

        versions = self._versions.get(model.model_id, {})

        for v_num in sorted(versions.keys(), reverse=True):
            v = versions[v_num]
            if v.stage == stage:
                return v

        return None

    def get_production_model(self, model_name: str) -> Optional[ModelVersion]:
        """Get production version of model."""
        return self.get_latest_version_by_stage(model_name, ModelStage.PRODUCTION)

    def set_model_signature(self,
                           model_name: str,
                           version: int,
                           inputs: Dict[str, str],
                           outputs: Dict[str, str]) -> bool:
        """
        Set input/output signature for model version.

        Args:
            model_name: Model name
            version: Version number
            inputs: Input schema {name: dtype}
            outputs: Output schema {name: dtype}

        Returns:
            Success status
        """
        version_obj = self.get_model_version(model_name, version)
        if not version_obj:
            return False

        version_obj.signature = {
            'inputs': inputs,
            'outputs': outputs
        }
        return True

    def set_model_requirements(self,
                              model_name: str,
                              version: int,
                              requirements: List[str]) -> bool:
        """Set Python requirements for model version."""
        version_obj = self.get_model_version(model_name, version)
        if not version_obj:
            return False

        version_obj.requirements = requirements
        return True

    def update_model_tags(self,
                         model_name: str,
                         tags: Dict[str, str]) -> bool:
        """Update tags for registered model."""
        model = self.get_model_by_name(model_name)
        if not model:
            return False

        model.tags.update(tags)
        model.last_updated_at = datetime.utcnow()
        return True

    def update_version_tags(self,
                           model_name: str,
                           version: int,
                           tags: Dict[str, str]) -> bool:
        """Update tags for model version."""
        version_obj = self.get_model_version(model_name, version)
        if not version_obj:
            return False

        version_obj.tags.update(tags)
        return True

    def search_models(self,
                     name_filter: Optional[str] = None,
                     tag_filter: Optional[Dict[str, str]] = None) -> List[RegisteredModel]:
        """
        Search registered models.

        Args:
            name_filter: Substring match on name
            tag_filter: Required tags

        Returns:
            Matching models
        """
        results = list(self._models.values())

        if name_filter:
            results = [m for m in results if name_filter.lower() in m.name.lower()]

        if tag_filter:
            results = [
                m for m in results
                if all(m.tags.get(k) == v for k, v in tag_filter.items())
            ]

        return results

    def delete_model_version(self, model_name: str, version: int) -> bool:
        """Delete specific model version."""
        model = self.get_model_by_name(model_name)
        if not model:
            return False

        if version not in model.versions:
            return False

        del self._versions[model.model_id][version]
        model.versions.remove(version)

        if model.latest_version == version:
            model.latest_version = max(model.versions) if model.versions else 0

        model.last_updated_at = datetime.utcnow()
        logger.info(f"Deleted version: {model_name} v{version}")
        return True

    def delete_model(self, model_name: str) -> bool:
        """Delete registered model and all versions."""
        model = self.get_model_by_name(model_name)
        if not model:
            return False

        if model.model_id in self._versions:
            del self._versions[model.model_id]

        del self._models[model.model_id]
        logger.info(f"Deleted model: {model_name}")
        return True

    def list_models(self) -> List[RegisteredModel]:
        """List all registered models."""
        return list(self._models.values())

    def export_model_info(self, model_name: str) -> Dict[str, Any]:
        """Export model info as dictionary."""
        model = self.get_model_by_name(model_name)
        if not model:
            return {}

        versions = self.get_model_versions(model_name)

        return {
            'model_id': model.model_id,
            'name': model.name,
            'description': model.description,
            'created_at': model.created_at.isoformat(),
            'last_updated_at': model.last_updated_at.isoformat(),
            'tags': model.tags,
            'latest_version': model.latest_version,
            'versions': [
                {
                    'version': v.version,
                    'stage': v.stage.value,
                    'run_id': v.run_id,
                    'source_path': v.source_path,
                    'created_at': v.created_at.isoformat(),
                    'description': v.description,
                    'metrics': v.metrics
                }
                for v in versions
            ]
        }
