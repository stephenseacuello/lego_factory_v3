"""
Data Versioning - DVC-style data versioning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
import hashlib
import json
import shutil
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataVersion:
    """Version of a dataset."""
    version_id: str
    dataset_name: str
    checksum: str
    size_bytes: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    source_path: str = ""
    stored_path: str = ""
    description: str = ""
    schema: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    tags: Dict[str, str] = field(default_factory=dict)
    parent_version: Optional[str] = None


class DataVersioning:
    """
    Version control for datasets.

    Features:
    - Content-addressable storage
    - Deduplication via checksums
    - Schema tracking
    - Statistics capture
    - Lineage tracking
    """

    def __init__(self, storage_path: str = "./data_versions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._versions: Dict[str, DataVersion] = {}
        self._datasets: Dict[str, List[str]] = {}  # name -> version_ids
        self._load_index()

    def _load_index(self) -> None:
        """Load version index from storage."""
        index_path = self.storage_path / "index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)

                for item in data.get('versions', []):
                    version = DataVersion(
                        version_id=item['version_id'],
                        dataset_name=item['dataset_name'],
                        checksum=item['checksum'],
                        size_bytes=item['size_bytes'],
                        created_at=datetime.fromisoformat(item['created_at']),
                        source_path=item.get('source_path', ''),
                        stored_path=item.get('stored_path', ''),
                        description=item.get('description', ''),
                        schema=item.get('schema'),
                        stats=item.get('stats'),
                        tags=item.get('tags', {}),
                        parent_version=item.get('parent_version')
                    )
                    self._versions[version.version_id] = version

                    if version.dataset_name not in self._datasets:
                        self._datasets[version.dataset_name] = []
                    self._datasets[version.dataset_name].append(version.version_id)

                logger.info(f"Loaded {len(self._versions)} data versions")
            except Exception as e:
                logger.error(f"Failed to load data version index: {e}")

    def _save_index(self) -> None:
        """Save version index to storage."""
        data = {
            'versions': [
                {
                    'version_id': v.version_id,
                    'dataset_name': v.dataset_name,
                    'checksum': v.checksum,
                    'size_bytes': v.size_bytes,
                    'created_at': v.created_at.isoformat(),
                    'source_path': v.source_path,
                    'stored_path': v.stored_path,
                    'description': v.description,
                    'schema': v.schema,
                    'stats': v.stats,
                    'tags': v.tags,
                    'parent_version': v.parent_version
                }
                for v in self._versions.values()
            ]
        }

        with open(self.storage_path / "index.json", 'w') as f:
            json.dump(data, f, indent=2)

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute checksum of file or directory."""
        sha256 = hashlib.sha256()

        if file_path.is_file():
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    sha256.update(chunk)
        else:
            # For directories, hash all files
            for f in sorted(file_path.rglob('*')):
                if f.is_file():
                    sha256.update(f.name.encode())
                    with open(f, 'rb') as fh:
                        for chunk in iter(lambda: fh.read(8192), b''):
                            sha256.update(chunk)

        return sha256.hexdigest()

    def _get_size(self, file_path: Path) -> int:
        """Get size of file or directory."""
        if file_path.is_file():
            return file_path.stat().st_size
        else:
            return sum(f.stat().st_size for f in file_path.rglob('*') if f.is_file())

    def track(self,
             source_path: str,
             dataset_name: str,
             description: str = "",
             schema: Optional[Dict[str, Any]] = None,
             stats: Optional[Dict[str, Any]] = None,
             tags: Optional[Dict[str, str]] = None,
             copy_data: bool = True) -> DataVersion:
        """
        Track a new version of a dataset.

        Args:
            source_path: Path to dataset file/directory
            dataset_name: Name of the dataset
            description: Version description
            schema: Data schema definition
            stats: Dataset statistics
            tags: Version tags
            copy_data: Whether to copy data to storage

        Returns:
            Created data version
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Dataset not found: {source_path}")

        checksum = self._compute_checksum(source)
        size = self._get_size(source)

        # Check for duplicate
        for v in self._versions.values():
            if v.checksum == checksum:
                logger.info(f"Dataset already tracked: {v.version_id}")
                return v

        # Create version ID
        version_id = f"{dataset_name}_{checksum[:8]}"

        # Store data
        stored_path = ""
        if copy_data:
            dest_dir = self.storage_path / version_id
            dest_dir.mkdir(parents=True, exist_ok=True)

            if source.is_file():
                stored_path = str(dest_dir / source.name)
                shutil.copy2(source, stored_path)
            else:
                stored_path = str(dest_dir / source.name)
                shutil.copytree(source, stored_path)

        # Get parent version
        parent_version = None
        if dataset_name in self._datasets and self._datasets[dataset_name]:
            parent_version = self._datasets[dataset_name][-1]

        version = DataVersion(
            version_id=version_id,
            dataset_name=dataset_name,
            checksum=checksum,
            size_bytes=size,
            source_path=str(source),
            stored_path=stored_path,
            description=description,
            schema=schema,
            stats=stats,
            tags=tags or {},
            parent_version=parent_version
        )

        self._versions[version_id] = version

        if dataset_name not in self._datasets:
            self._datasets[dataset_name] = []
        self._datasets[dataset_name].append(version_id)

        self._save_index()
        logger.info(f"Tracked data version: {version_id}")

        return version

    def get_version(self, version_id: str) -> Optional[DataVersion]:
        """Get version by ID."""
        return self._versions.get(version_id)

    def get_latest_version(self, dataset_name: str) -> Optional[DataVersion]:
        """Get latest version of a dataset."""
        if dataset_name not in self._datasets or not self._datasets[dataset_name]:
            return None

        latest_id = self._datasets[dataset_name][-1]
        return self._versions.get(latest_id)

    def get_versions(self, dataset_name: str) -> List[DataVersion]:
        """Get all versions of a dataset."""
        if dataset_name not in self._datasets:
            return []

        return [
            self._versions[vid]
            for vid in self._datasets[dataset_name]
            if vid in self._versions
        ]

    def checkout(self, version_id: str, destination: str) -> bool:
        """
        Checkout a data version to destination.

        Args:
            version_id: Version ID
            destination: Destination path

        Returns:
            Success status
        """
        version = self._versions.get(version_id)
        if not version:
            logger.error(f"Version not found: {version_id}")
            return False

        if not version.stored_path:
            logger.error("No stored data for this version")
            return False

        source = Path(version.stored_path)
        dest = Path(destination)

        try:
            if source.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            else:
                shutil.copytree(source, dest, dirs_exist_ok=True)

            logger.info(f"Checked out {version_id} to {destination}")
            return True

        except Exception as e:
            logger.error(f"Checkout failed: {e}")
            return False

    def diff(self,
            version_a: str,
            version_b: str) -> Dict[str, Any]:
        """
        Compare two versions.

        Returns metadata diff (data content diff not supported).
        """
        a = self._versions.get(version_a)
        b = self._versions.get(version_b)

        if not a or not b:
            return {'error': 'Version not found'}

        return {
            'same_content': a.checksum == b.checksum,
            'size_diff_bytes': b.size_bytes - a.size_bytes,
            'schema_changed': a.schema != b.schema,
            'stats_a': a.stats,
            'stats_b': b.stats,
            'tags_a': a.tags,
            'tags_b': b.tags
        }

    def list_datasets(self) -> List[str]:
        """List all tracked datasets."""
        return list(self._datasets.keys())

    def get_lineage(self, version_id: str) -> List[DataVersion]:
        """Get version lineage (ancestors)."""
        lineage = []
        current_id = version_id

        while current_id:
            version = self._versions.get(current_id)
            if not version:
                break
            lineage.append(version)
            current_id = version.parent_version

        return lineage

    def update_stats(self,
                    version_id: str,
                    stats: Dict[str, Any]) -> bool:
        """Update statistics for a version."""
        version = self._versions.get(version_id)
        if not version:
            return False

        version.stats = stats
        self._save_index()
        return True

    def update_tags(self,
                   version_id: str,
                   tags: Dict[str, str]) -> bool:
        """Update tags for a version."""
        version = self._versions.get(version_id)
        if not version:
            return False

        version.tags.update(tags)
        self._save_index()
        return True

    def verify_integrity(self, version_id: str) -> bool:
        """Verify stored data matches checksum."""
        version = self._versions.get(version_id)
        if not version or not version.stored_path:
            return False

        stored = Path(version.stored_path)
        if not stored.exists():
            return False

        current_checksum = self._compute_checksum(stored)
        return current_checksum == version.checksum

    def delete_version(self, version_id: str) -> bool:
        """Delete a version."""
        version = self._versions.get(version_id)
        if not version:
            return False

        # Remove stored data
        if version.stored_path:
            stored = Path(version.stored_path)
            if stored.exists():
                if stored.is_file():
                    stored.unlink()
                else:
                    shutil.rmtree(stored.parent)

        # Remove from index
        del self._versions[version_id]

        if version.dataset_name in self._datasets:
            self._datasets[version.dataset_name] = [
                vid for vid in self._datasets[version.dataset_name]
                if vid != version_id
            ]

        self._save_index()
        logger.info(f"Deleted version: {version_id}")
        return True

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        total_size = sum(v.size_bytes for v in self._versions.values())

        return {
            'total_datasets': len(self._datasets),
            'total_versions': len(self._versions),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }
