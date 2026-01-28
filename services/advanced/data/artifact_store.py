"""
Artifact Store - Binary Artifact Storage and Management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides versioned storage for models, figures, logs, and other artifacts.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, BinaryIO
from datetime import datetime
from enum import Enum
from pathlib import Path
import hashlib
import logging
import uuid

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of artifacts."""
    MODEL = "model"
    CHECKPOINT = "checkpoint"
    FIGURE = "figure"
    LOG = "log"
    CONFIG = "config"
    DATASET_SAMPLE = "dataset_sample"
    REPORT = "report"
    GCODE = "gcode"
    STL = "stl"
    CAD = "cad"
    ONNX = "onnx"
    TENSORRT = "tensorrt"


@dataclass
class Artifact:
    """A stored artifact."""
    artifact_id: str
    name: str
    artifact_type: ArtifactType
    experiment_id: Optional[str]
    run_id: Optional[str]
    version: str
    file_path: str
    size_bytes: int
    content_hash: str
    mime_type: str
    created_at: datetime
    created_by: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "version": self.version,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "content_hash": self.content_hash,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
            "tags": self.tags,
        }


class ArtifactStore:
    """
    Manages artifact storage and retrieval.

    Features:
    - Content-addressable storage
    - Deduplication via content hash
    - Version tracking
    - Experiment/run association
    - Streaming upload/download
    """

    MIME_TYPES = {
        ArtifactType.MODEL: "application/octet-stream",
        ArtifactType.CHECKPOINT: "application/octet-stream",
        ArtifactType.FIGURE: "image/png",
        ArtifactType.LOG: "text/plain",
        ArtifactType.CONFIG: "application/json",
        ArtifactType.REPORT: "application/pdf",
        ArtifactType.GCODE: "text/x-gcode",
        ArtifactType.STL: "model/stl",
        ArtifactType.CAD: "application/x-step",
        ArtifactType.ONNX: "application/x-onnx",
        ArtifactType.TENSORRT: "application/x-tensorrt",
    }

    def __init__(self, storage_root: str = "/data/artifacts"):
        self.storage_root = Path(storage_root)
        self.artifacts: Dict[str, Artifact] = {}
        self.hash_index: Dict[str, str] = {}  # content_hash -> artifact_id
        self._storage_used = 0
        self._storage_quota = 500_000_000_000  # 500GB
        self._initialize_sample_artifacts()

    def _initialize_sample_artifacts(self):
        """Initialize with sample artifacts for development."""
        samples = [
            Artifact(
                artifact_id="art-model-001",
                name="quality_predictor_v2.3.1.pt",
                artifact_type=ArtifactType.MODEL,
                experiment_id="EXP-2024-0155",
                run_id="run-abc123",
                version="2.3.1",
                file_path="/data/artifacts/models/quality_predictor_v2.3.1.pt",
                size_bytes=156_000_000,
                content_hash="sha256:abc123def456",
                mime_type="application/octet-stream",
                created_at=datetime.now(),
                created_by="quality_team",
                metadata={"accuracy": 0.987, "framework": "PyTorch", "architecture": "ResNet50"},
                tags=["production", "quality"],
            ),
            Artifact(
                artifact_id="art-figure-001",
                name="confusion_matrix.png",
                artifact_type=ArtifactType.FIGURE,
                experiment_id="EXP-2024-0155",
                run_id="run-abc123",
                version="1.0.0",
                file_path="/data/artifacts/figures/confusion_matrix.png",
                size_bytes=234_000,
                content_hash="sha256:fig123abc",
                mime_type="image/png",
                created_at=datetime.now(),
                created_by="quality_team",
                metadata={"format": "PNG", "resolution": "1200x1200"},
                tags=["visualization"],
            ),
            Artifact(
                artifact_id="art-checkpoint-001",
                name="model_checkpoint_epoch50.pt",
                artifact_type=ArtifactType.CHECKPOINT,
                experiment_id="EXP-2024-0156",
                run_id="run-xyz789",
                version="50",
                file_path="/data/artifacts/checkpoints/model_checkpoint_epoch50.pt",
                size_bytes=156_000_000,
                content_hash="sha256:chk50xyz",
                mime_type="application/octet-stream",
                created_at=datetime.now(),
                created_by="ml_team",
                metadata={"epoch": 50, "loss": 0.0234, "val_accuracy": 0.978},
                tags=["training"],
            ),
        ]

        for artifact in samples:
            self.artifacts[artifact.artifact_id] = artifact
            self.hash_index[artifact.content_hash] = artifact.artifact_id
            self._storage_used += artifact.size_bytes

    def store(
        self,
        name: str,
        artifact_type: ArtifactType,
        content: bytes,
        experiment_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version: str = "1.0.0",
        created_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Artifact:
        """Store a new artifact."""
        # Calculate content hash
        content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"

        # Check for duplicates
        if content_hash in self.hash_index:
            existing_id = self.hash_index[content_hash]
            logger.info(f"Artifact with same content exists: {existing_id}")
            return self.artifacts[existing_id]

        # Check storage quota
        if self._storage_used + len(content) > self._storage_quota:
            raise ValueError("Storage quota exceeded")

        artifact_id = f"art-{artifact_type.value}-{uuid.uuid4().hex[:8]}"

        # Determine file path
        type_dir = artifact_type.value + "s"
        file_path = f"/data/artifacts/{type_dir}/{name}"

        artifact = Artifact(
            artifact_id=artifact_id,
            name=name,
            artifact_type=artifact_type,
            experiment_id=experiment_id,
            run_id=run_id,
            version=version,
            file_path=file_path,
            size_bytes=len(content),
            content_hash=content_hash,
            mime_type=self.MIME_TYPES.get(artifact_type, "application/octet-stream"),
            created_at=datetime.now(),
            created_by=created_by,
            metadata=metadata or {},
            tags=tags or [],
        )

        self.artifacts[artifact_id] = artifact
        self.hash_index[content_hash] = artifact_id
        self._storage_used += len(content)

        logger.info(f"Stored artifact: {artifact_id} ({len(content)} bytes)")

        return artifact

    def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact metadata by ID."""
        return self.artifacts.get(artifact_id)

    def get_by_hash(self, content_hash: str) -> Optional[Artifact]:
        """Get artifact by content hash."""
        artifact_id = self.hash_index.get(content_hash)
        if artifact_id:
            return self.artifacts.get(artifact_id)
        return None

    def list_artifacts(
        self,
        artifact_type: Optional[ArtifactType] = None,
        experiment_id: Optional[str] = None,
        run_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Artifact]:
        """List artifacts with optional filtering."""
        results = list(self.artifacts.values())

        if artifact_type:
            results = [a for a in results if a.artifact_type == artifact_type]
        if experiment_id:
            results = [a for a in results if a.experiment_id == experiment_id]
        if run_id:
            results = [a for a in results if a.run_id == run_id]
        if tags:
            results = [a for a in results if any(t in a.tags for t in tags)]

        return sorted(results, key=lambda a: a.created_at, reverse=True)

    def delete(self, artifact_id: str) -> bool:
        """Delete an artifact."""
        artifact = self.artifacts.get(artifact_id)
        if not artifact:
            return False

        del self.artifacts[artifact_id]
        if artifact.content_hash in self.hash_index:
            del self.hash_index[artifact.content_hash]
        self._storage_used -= artifact.size_bytes

        logger.info(f"Deleted artifact: {artifact_id}")
        return True

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        type_stats = {}
        for artifact in self.artifacts.values():
            type_name = artifact.artifact_type.value
            if type_name not in type_stats:
                type_stats[type_name] = {"count": 0, "size_bytes": 0}
            type_stats[type_name]["count"] += 1
            type_stats[type_name]["size_bytes"] += artifact.size_bytes

        return {
            "total_artifacts": len(self.artifacts),
            "storage_used": self._storage_used,
            "storage_quota": self._storage_quota,
            "storage_percent": round(self._storage_used / self._storage_quota * 100, 2),
            "by_type": type_stats,
        }

    def get_experiment_artifacts(
        self,
        experiment_id: str,
    ) -> Dict[str, List[Artifact]]:
        """Get all artifacts for an experiment, grouped by type."""
        artifacts = self.list_artifacts(experiment_id=experiment_id)

        grouped = {}
        for artifact in artifacts:
            type_name = artifact.artifact_type.value
            if type_name not in grouped:
                grouped[type_name] = []
            grouped[type_name].append(artifact)

        return grouped

    def copy_artifact(
        self,
        artifact_id: str,
        new_experiment_id: str,
        new_run_id: Optional[str] = None,
    ) -> Artifact:
        """Copy an artifact to a new experiment/run."""
        original = self.get(artifact_id)
        if not original:
            raise ValueError(f"Artifact not found: {artifact_id}")

        new_artifact_id = f"art-{original.artifact_type.value}-{uuid.uuid4().hex[:8]}"

        new_artifact = Artifact(
            artifact_id=new_artifact_id,
            name=original.name,
            artifact_type=original.artifact_type,
            experiment_id=new_experiment_id,
            run_id=new_run_id,
            version=original.version,
            file_path=original.file_path,  # Same content, same path
            size_bytes=original.size_bytes,
            content_hash=original.content_hash,
            mime_type=original.mime_type,
            created_at=datetime.now(),
            created_by="system",
            metadata={**original.metadata, "copied_from": artifact_id},
            tags=original.tags.copy(),
        )

        self.artifacts[new_artifact_id] = new_artifact
        # Don't increment storage - same content

        return new_artifact
