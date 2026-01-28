"""
Artifact Store - Dataset and model artifact management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, BinaryIO, Dict, List, Optional
from pathlib import Path
from enum import Enum
import hashlib
import uuid
import shutil
import json
import logging

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Type of artifact."""
    MODEL = "model"
    DATASET = "dataset"
    FIGURE = "figure"
    REPORT = "report"
    CODE = "code"
    CONFIG = "config"
    OTHER = "other"


@dataclass
class Artifact:
    """Stored artifact metadata."""
    artifact_id: str
    name: str
    artifact_type: ArtifactType
    path: str
    size_bytes: int
    checksum: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    run_id: Optional[str] = None
    experiment_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ArtifactStore:
    """
    Central store for experiment artifacts.

    Features:
    - Artifact versioning with checksums
    - Lazy loading for large artifacts
    - Metadata search
    - Linked artifacts (datasets -> models)
    """

    def __init__(self, root_path: str = "./artifacts"):
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)
        self._artifacts: Dict[str, Artifact] = {}
        self._index_path = self.root_path / "index.json"
        self._load_index()

    def _load_index(self) -> None:
        """Load artifact index from disk."""
        if self._index_path.exists():
            try:
                with open(self._index_path, 'r') as f:
                    data = json.load(f)

                for item in data.get('artifacts', []):
                    artifact = Artifact(
                        artifact_id=item['artifact_id'],
                        name=item['name'],
                        artifact_type=ArtifactType(item['artifact_type']),
                        path=item['path'],
                        size_bytes=item['size_bytes'],
                        checksum=item['checksum'],
                        created_at=datetime.fromisoformat(item['created_at']),
                        run_id=item.get('run_id'),
                        experiment_id=item.get('experiment_id'),
                        tags=item.get('tags', {}),
                        metadata=item.get('metadata', {})
                    )
                    self._artifacts[artifact.artifact_id] = artifact

                logger.info(f"Loaded {len(self._artifacts)} artifacts from index")
            except Exception as e:
                logger.error(f"Failed to load artifact index: {e}")

    def _save_index(self) -> None:
        """Save artifact index to disk."""
        data = {
            'artifacts': [
                {
                    'artifact_id': a.artifact_id,
                    'name': a.name,
                    'artifact_type': a.artifact_type.value,
                    'path': a.path,
                    'size_bytes': a.size_bytes,
                    'checksum': a.checksum,
                    'created_at': a.created_at.isoformat(),
                    'run_id': a.run_id,
                    'experiment_id': a.experiment_id,
                    'tags': a.tags,
                    'metadata': a.metadata
                }
                for a in self._artifacts.values()
            ]
        }

        with open(self._index_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()[:16]

    def log_artifact(self,
                    source_path: str,
                    name: Optional[str] = None,
                    artifact_type: ArtifactType = ArtifactType.OTHER,
                    run_id: Optional[str] = None,
                    experiment_id: Optional[str] = None,
                    tags: Optional[Dict[str, str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Artifact:
        """
        Store an artifact.

        Args:
            source_path: Path to artifact file/directory
            name: Artifact name (defaults to filename)
            artifact_type: Type of artifact
            run_id: Associated experiment run
            experiment_id: Associated experiment
            tags: Artifact tags
            metadata: Additional metadata

        Returns:
            Created artifact
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Artifact not found: {source_path}")

        artifact_id = str(uuid.uuid4())[:8]
        name = name or source.name

        # Create destination directory
        dest_dir = self.root_path / artifact_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy artifact
        if source.is_file():
            dest_path = dest_dir / source.name
            shutil.copy2(source, dest_path)
            size = dest_path.stat().st_size
            checksum = self._compute_checksum(dest_path)
        else:
            dest_path = dest_dir / source.name
            shutil.copytree(source, dest_path)
            # Calculate total size
            size = sum(f.stat().st_size for f in dest_path.rglob('*') if f.is_file())
            checksum = "dir_" + artifact_id

        artifact = Artifact(
            artifact_id=artifact_id,
            name=name,
            artifact_type=artifact_type,
            path=str(dest_path),
            size_bytes=size,
            checksum=checksum,
            run_id=run_id,
            experiment_id=experiment_id,
            tags=tags or {},
            metadata=metadata or {}
        )

        self._artifacts[artifact_id] = artifact
        self._save_index()

        logger.info(f"Logged artifact: {name} ({artifact_id})")
        return artifact

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID."""
        return self._artifacts.get(artifact_id)

    def get_artifact_path(self, artifact_id: str) -> Optional[Path]:
        """Get path to artifact files."""
        artifact = self._artifacts.get(artifact_id)
        if artifact:
            return Path(artifact.path)
        return None

    def download_artifact(self, artifact_id: str, destination: str) -> bool:
        """
        Download artifact to destination.

        Args:
            artifact_id: Artifact ID
            destination: Destination path

        Returns:
            Success status
        """
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            logger.error(f"Artifact not found: {artifact_id}")
            return False

        source = Path(artifact.path)
        dest = Path(destination)

        try:
            if source.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            else:
                shutil.copytree(source, dest, dirs_exist_ok=True)

            logger.info(f"Downloaded artifact {artifact_id} to {destination}")
            return True

        except Exception as e:
            logger.error(f"Failed to download artifact: {e}")
            return False

    def search_artifacts(self,
                        artifact_type: Optional[ArtifactType] = None,
                        run_id: Optional[str] = None,
                        experiment_id: Optional[str] = None,
                        tags: Optional[Dict[str, str]] = None,
                        name_filter: Optional[str] = None) -> List[Artifact]:
        """
        Search artifacts.

        Args:
            artifact_type: Filter by type
            run_id: Filter by run
            experiment_id: Filter by experiment
            tags: Required tags
            name_filter: Substring match on name

        Returns:
            Matching artifacts
        """
        results = list(self._artifacts.values())

        if artifact_type:
            results = [a for a in results if a.artifact_type == artifact_type]

        if run_id:
            results = [a for a in results if a.run_id == run_id]

        if experiment_id:
            results = [a for a in results if a.experiment_id == experiment_id]

        if tags:
            results = [
                a for a in results
                if all(a.tags.get(k) == v for k, v in tags.items())
            ]

        if name_filter:
            results = [
                a for a in results
                if name_filter.lower() in a.name.lower()
            ]

        return results

    def get_artifacts_for_run(self, run_id: str) -> List[Artifact]:
        """Get all artifacts for an experiment run."""
        return [a for a in self._artifacts.values() if a.run_id == run_id]

    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact."""
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            return False

        # Remove files
        artifact_dir = self.root_path / artifact_id
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)

        del self._artifacts[artifact_id]
        self._save_index()

        logger.info(f"Deleted artifact: {artifact_id}")
        return True

    def update_tags(self, artifact_id: str, tags: Dict[str, str]) -> bool:
        """Update artifact tags."""
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            return False

        artifact.tags.update(tags)
        self._save_index()
        return True

    def update_metadata(self, artifact_id: str, metadata: Dict[str, Any]) -> bool:
        """Update artifact metadata."""
        artifact = self._artifacts.get(artifact_id)
        if not artifact:
            return False

        artifact.metadata.update(metadata)
        self._save_index()
        return True

    def list_artifacts(self,
                      limit: int = 100,
                      offset: int = 0) -> List[Artifact]:
        """List all artifacts with pagination."""
        artifacts = sorted(
            self._artifacts.values(),
            key=lambda a: a.created_at,
            reverse=True
        )
        return artifacts[offset:offset + limit]

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get artifact storage statistics."""
        total_size = sum(a.size_bytes for a in self._artifacts.values())
        by_type = {}

        for a in self._artifacts.values():
            type_name = a.artifact_type.value
            if type_name not in by_type:
                by_type[type_name] = {'count': 0, 'size_bytes': 0}
            by_type[type_name]['count'] += 1
            by_type[type_name]['size_bytes'] += a.size_bytes

        return {
            'total_artifacts': len(self._artifacts),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'by_type': by_type
        }
