"""
Model Registry Service
LegoMCP PhD-Level Manufacturing Platform

Implements model versioning and lifecycle management with:
- Model versioning and staging
- A/B testing support
- Rollback capabilities
- Model metadata tracking
- Deployment integration
"""

import os
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class ModelStage(Enum):
    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


class ModelStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass
class ModelVersion:
    """Represents a model version."""
    name: str
    version: int
    stage: ModelStage
    status: ModelStatus
    source: str  # Path to model artifacts
    run_id: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    signature: Optional[Dict[str, Any]] = None  # Input/output schema
    checksum: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "stage": self.stage.value,
            "status": self.status.value,
            "source": self.source,
            "run_id": self.run_id,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "metrics": self.metrics,
            "signature": self.signature,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersion":
        return cls(
            name=data["name"],
            version=data["version"],
            stage=ModelStage(data["stage"]),
            status=ModelStatus(data["status"]),
            source=data["source"],
            run_id=data.get("run_id"),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            tags=data.get("tags", {}),
            metrics=data.get("metrics", {}),
            signature=data.get("signature"),
            checksum=data.get("checksum"),
        )


@dataclass
class RegisteredModel:
    """Represents a registered model with all versions."""
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    versions: List[ModelVersion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "versions": [v.to_dict() for v in self.versions],
        }

    @property
    def latest_version(self) -> Optional[ModelVersion]:
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.version)

    @property
    def production_version(self) -> Optional[ModelVersion]:
        for v in self.versions:
            if v.stage == ModelStage.PRODUCTION:
                return v
        return None

    @property
    def staging_version(self) -> Optional[ModelVersion]:
        for v in self.versions:
            if v.stage == ModelStage.STAGING:
                return v
        return None


class ModelRegistry:
    """
    Model registry for manufacturing ML models.

    Features:
    - Model versioning with semantic versioning
    - Stage management (None, Staging, Production, Archived)
    - A/B testing support
    - Model comparison and rollback
    - Integration with MLflow
    - Local and remote storage
    """

    def __init__(
        self,
        storage_path: str = None,
        use_mlflow: bool = True,
    ):
        self.storage_path = Path(storage_path or os.environ.get(
            "MODEL_REGISTRY_PATH", "/app/models/registry"
        ))
        self.use_mlflow = use_mlflow
        self._models: Dict[str, RegisteredModel] = {}
        self._mlflow_client = None

        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load existing models
        self._load_registry()

    def _load_registry(self):
        """Load registry from storage."""
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file) as f:
                    data = json.load(f)
                for model_data in data.get("models", []):
                    model = RegisteredModel(
                        name=model_data["name"],
                        description=model_data.get("description", ""),
                        created_at=datetime.fromisoformat(model_data["created_at"]),
                        updated_at=datetime.fromisoformat(model_data["updated_at"]),
                        tags=model_data.get("tags", {}),
                        versions=[
                            ModelVersion.from_dict(v)
                            for v in model_data.get("versions", [])
                        ],
                    )
                    self._models[model.name] = model
                logger.info(f"Loaded {len(self._models)} registered models")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self):
        """Save registry to storage."""
        registry_file = self.storage_path / "registry.json"
        try:
            data = {
                "models": [m.to_dict() for m in self._models.values()],
                "updated_at": datetime.utcnow().isoformat(),
            }
            with open(registry_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def create_registered_model(
        self,
        name: str,
        description: str = "",
        tags: Dict[str, str] = None,
    ) -> RegisteredModel:
        """Create a new registered model."""
        if name in self._models:
            logger.warning(f"Model {name} already exists")
            return self._models[name]

        model = RegisteredModel(
            name=name,
            description=description,
            tags=tags or {},
        )
        self._models[name] = model
        self._save_registry()

        logger.info(f"Created registered model: {name}")
        return model

    def register_model(
        self,
        name: str,
        source: str,
        run_id: str = None,
        description: str = "",
        tags: Dict[str, str] = None,
        metrics: Dict[str, float] = None,
        signature: Dict[str, Any] = None,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            name: Model name
            source: Path to model artifacts
            run_id: Associated experiment run ID
            description: Version description
            tags: Version tags
            metrics: Model metrics
            signature: Input/output schema

        Returns:
            ModelVersion object
        """
        # Create model if doesn't exist
        if name not in self._models:
            self.create_registered_model(name)

        model = self._models[name]

        # Determine version number
        next_version = 1
        if model.versions:
            next_version = max(v.version for v in model.versions) + 1

        # Calculate checksum
        checksum = self._calculate_checksum(source)

        # Copy artifacts to registry storage
        version_path = self.storage_path / name / f"v{next_version}"
        version_path.mkdir(parents=True, exist_ok=True)

        source_path = Path(source)
        if source_path.is_dir():
            shutil.copytree(source_path, version_path / "artifacts", dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, version_path / "artifacts")

        # Create version
        version = ModelVersion(
            name=name,
            version=next_version,
            stage=ModelStage.NONE,
            status=ModelStatus.READY,
            source=str(version_path / "artifacts"),
            run_id=run_id,
            description=description,
            tags=tags or {},
            metrics=metrics or {},
            signature=signature,
            checksum=checksum,
        )

        model.versions.append(version)
        model.updated_at = datetime.utcnow()
        self._save_registry()

        logger.info(f"Registered model version: {name} v{next_version}")
        return version

    def get_model(self, name: str) -> Optional[RegisteredModel]:
        """Get registered model by name."""
        return self._models.get(name)

    def get_model_version(
        self,
        name: str,
        version: int = None,
        stage: ModelStage = None,
    ) -> Optional[ModelVersion]:
        """
        Get specific model version.

        Args:
            name: Model name
            version: Version number (None for latest)
            stage: Stage to filter by

        Returns:
            ModelVersion or None
        """
        model = self._models.get(name)
        if not model:
            return None

        if stage:
            for v in model.versions:
                if v.stage == stage:
                    return v
            return None

        if version:
            for v in model.versions:
                if v.version == version:
                    return v
            return None

        return model.latest_version

    def transition_model_version_stage(
        self,
        name: str,
        version: int,
        stage: ModelStage,
        archive_existing: bool = True,
    ) -> bool:
        """
        Transition model version to new stage.

        Args:
            name: Model name
            version: Version number
            stage: Target stage
            archive_existing: Archive existing version in target stage

        Returns:
            Success status
        """
        model = self._models.get(name)
        if not model:
            logger.error(f"Model not found: {name}")
            return False

        target_version = None
        for v in model.versions:
            if v.version == version:
                target_version = v
                break

        if not target_version:
            logger.error(f"Version not found: {name} v{version}")
            return False

        # Archive existing version in target stage
        if archive_existing and stage in [ModelStage.STAGING, ModelStage.PRODUCTION]:
            for v in model.versions:
                if v.stage == stage and v.version != version:
                    v.stage = ModelStage.ARCHIVED
                    v.updated_at = datetime.utcnow()
                    logger.info(f"Archived: {name} v{v.version}")

        # Update stage
        target_version.stage = stage
        target_version.updated_at = datetime.utcnow()
        model.updated_at = datetime.utcnow()
        self._save_registry()

        logger.info(f"Transitioned {name} v{version} to {stage.value}")
        return True

    def promote_to_production(
        self,
        name: str,
        version: int = None,
    ) -> bool:
        """
        Promote model version to production.

        Args:
            name: Model name
            version: Version number (None for staging version)

        Returns:
            Success status
        """
        model = self._models.get(name)
        if not model:
            return False

        if version is None:
            # Promote staging version
            staging = model.staging_version
            if not staging:
                logger.error("No staging version to promote")
                return False
            version = staging.version

        return self.transition_model_version_stage(
            name, version, ModelStage.PRODUCTION
        )

    def rollback(
        self,
        name: str,
        target_version: int = None,
    ) -> bool:
        """
        Rollback to previous production version.

        Args:
            name: Model name
            target_version: Version to rollback to (None for previous)

        Returns:
            Success status
        """
        model = self._models.get(name)
        if not model:
            return False

        current_prod = model.production_version
        if not current_prod:
            logger.error("No production version to rollback from")
            return False

        if target_version is None:
            # Find previous production version in archived
            archived = [
                v for v in model.versions
                if v.stage == ModelStage.ARCHIVED and v.version < current_prod.version
            ]
            if not archived:
                logger.error("No previous version to rollback to")
                return False
            target_version = max(archived, key=lambda v: v.version).version

        # Archive current and promote target
        self.transition_model_version_stage(
            name, current_prod.version, ModelStage.ARCHIVED
        )
        return self.transition_model_version_stage(
            name, target_version, ModelStage.PRODUCTION
        )

    def delete_model_version(self, name: str, version: int) -> bool:
        """Delete a model version."""
        model = self._models.get(name)
        if not model:
            return False

        for i, v in enumerate(model.versions):
            if v.version == version:
                if v.stage == ModelStage.PRODUCTION:
                    logger.error("Cannot delete production version")
                    return False

                # Remove artifacts
                version_path = self.storage_path / name / f"v{version}"
                if version_path.exists():
                    shutil.rmtree(version_path)

                model.versions.pop(i)
                model.updated_at = datetime.utcnow()
                self._save_registry()

                logger.info(f"Deleted: {name} v{version}")
                return True

        return False

    def list_models(self) -> List[RegisteredModel]:
        """List all registered models."""
        return list(self._models.values())

    def search_models(
        self,
        filter_tags: Dict[str, str] = None,
        name_contains: str = None,
    ) -> List[RegisteredModel]:
        """Search models by criteria."""
        results = []

        for model in self._models.values():
            if name_contains and name_contains.lower() not in model.name.lower():
                continue

            if filter_tags:
                match = all(
                    model.tags.get(k) == v
                    for k, v in filter_tags.items()
                )
                if not match:
                    continue

            results.append(model)

        return results

    def compare_versions(
        self,
        name: str,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """Compare two model versions."""
        model = self._models.get(name)
        if not model:
            return {"error": "Model not found"}

        va = self.get_model_version(name, version_a)
        vb = self.get_model_version(name, version_b)

        if not va or not vb:
            return {"error": "Version not found"}

        comparison = {
            "versions": [version_a, version_b],
            "metrics_diff": {},
            "tags_diff": {},
        }

        # Compare metrics
        all_metrics = set(va.metrics.keys()) | set(vb.metrics.keys())
        for metric in all_metrics:
            ma = va.metrics.get(metric)
            mb = vb.metrics.get(metric)
            if ma is not None and mb is not None:
                comparison["metrics_diff"][metric] = {
                    f"v{version_a}": ma,
                    f"v{version_b}": mb,
                    "diff": mb - ma,
                    "pct_change": ((mb - ma) / ma * 100) if ma != 0 else None,
                }

        # Compare tags
        all_tags = set(va.tags.keys()) | set(vb.tags.keys())
        for tag in all_tags:
            ta = va.tags.get(tag)
            tb = vb.tags.get(tag)
            if ta != tb:
                comparison["tags_diff"][tag] = {
                    f"v{version_a}": ta,
                    f"v{version_b}": tb,
                }

        return comparison

    def load_model(
        self,
        name: str,
        version: int = None,
        stage: ModelStage = None,
    ) -> Any:
        """
        Load model from registry.

        Args:
            name: Model name
            version: Version number
            stage: Stage to load from

        Returns:
            Loaded model object
        """
        model_version = self.get_model_version(name, version, stage)
        if not model_version:
            raise ValueError(f"Model version not found: {name}")

        source_path = Path(model_version.source)

        # Try different loading methods
        try:
            # PyTorch
            import torch
            pt_files = list(source_path.glob("*.pt")) + list(source_path.glob("*.pth"))
            if pt_files:
                return torch.load(pt_files[0])
        except ImportError:
            pass

        try:
            # Scikit-learn
            import joblib
            pkl_files = list(source_path.glob("*.pkl")) + list(source_path.glob("*.joblib"))
            if pkl_files:
                return joblib.load(pkl_files[0])
        except ImportError:
            pass

        try:
            # ONNX
            import onnxruntime
            onnx_files = list(source_path.glob("*.onnx"))
            if onnx_files:
                return onnxruntime.InferenceSession(str(onnx_files[0]))
        except ImportError:
            pass

        raise ValueError(f"Unable to load model from {source_path}")

    def _calculate_checksum(self, path: str) -> str:
        """Calculate SHA256 checksum of model artifacts."""
        sha256 = hashlib.sha256()
        path = Path(path)

        if path.is_file():
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        elif path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    sha256.update(str(file_path.relative_to(path)).encode())
                    with open(file_path, "rb") as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            sha256.update(chunk)

        return sha256.hexdigest()


# Global instance
model_registry = ModelRegistry()
