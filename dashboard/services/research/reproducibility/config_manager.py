"""
Config Manager - Experiment configuration versioning.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import hashlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConfigVersion:
    """Versioned configuration snapshot."""
    version_id: str
    name: str
    config: Dict[str, Any]
    checksum: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    parent_version: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    description: str = ""


class ConfigManager:
    """
    Manage and version experiment configurations.

    Features:
    - Configuration versioning
    - Diff between versions
    - Schema validation
    - Inheritance and overrides
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./configs")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._versions: Dict[str, ConfigVersion] = {}
        self._current_version: Optional[str] = None
        self._load_versions()

    def _load_versions(self) -> None:
        """Load versions from storage."""
        index_path = self.storage_path / "index.json"
        if index_path.exists():
            try:
                with open(index_path, 'r') as f:
                    data = json.load(f)

                for item in data.get('versions', []):
                    version = ConfigVersion(
                        version_id=item['version_id'],
                        name=item['name'],
                        config=item['config'],
                        checksum=item['checksum'],
                        created_at=datetime.fromisoformat(item['created_at']),
                        parent_version=item.get('parent_version'),
                        tags=item.get('tags', {}),
                        description=item.get('description', '')
                    )
                    self._versions[version.version_id] = version

                self._current_version = data.get('current_version')
                logger.info(f"Loaded {len(self._versions)} config versions")
            except Exception as e:
                logger.error(f"Failed to load config versions: {e}")

    def _save_versions(self) -> None:
        """Save versions to storage."""
        data = {
            'current_version': self._current_version,
            'versions': [
                {
                    'version_id': v.version_id,
                    'name': v.name,
                    'config': v.config,
                    'checksum': v.checksum,
                    'created_at': v.created_at.isoformat(),
                    'parent_version': v.parent_version,
                    'tags': v.tags,
                    'description': v.description
                }
                for v in self._versions.values()
            ]
        }

        with open(self.storage_path / "index.json", 'w') as f:
            json.dump(data, f, indent=2)

    def _compute_checksum(self, config: Dict[str, Any]) -> str:
        """Compute checksum of configuration."""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:12]

    def create_version(self,
                      name: str,
                      config: Dict[str, Any],
                      parent_version: Optional[str] = None,
                      description: str = "",
                      tags: Optional[Dict[str, str]] = None) -> ConfigVersion:
        """
        Create new configuration version.

        Args:
            name: Version name
            config: Configuration dictionary
            parent_version: Parent version ID (for inheritance)
            description: Version description
            tags: Version tags

        Returns:
            Created version
        """
        checksum = self._compute_checksum(config)

        # Check if identical config exists
        for v in self._versions.values():
            if v.checksum == checksum:
                logger.info(f"Config already exists as version {v.version_id}")
                return v

        version = ConfigVersion(
            version_id=checksum[:8],
            name=name,
            config=config.copy(),
            checksum=checksum,
            parent_version=parent_version,
            description=description,
            tags=tags or {}
        )

        self._versions[version.version_id] = version
        self._current_version = version.version_id
        self._save_versions()

        logger.info(f"Created config version: {name} ({version.version_id})")
        return version

    def get_version(self, version_id: str) -> Optional[ConfigVersion]:
        """Get version by ID."""
        return self._versions.get(version_id)

    def get_current_version(self) -> Optional[ConfigVersion]:
        """Get current active version."""
        if self._current_version:
            return self._versions.get(self._current_version)
        return None

    def set_current_version(self, version_id: str) -> bool:
        """Set current active version."""
        if version_id not in self._versions:
            logger.error(f"Version not found: {version_id}")
            return False

        self._current_version = version_id
        self._save_versions()
        return True

    def get_config(self, version_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for version.

        Args:
            version_id: Version ID (current if None)

        Returns:
            Configuration dictionary
        """
        if version_id is None:
            version_id = self._current_version

        if version_id is None:
            return {}

        version = self._versions.get(version_id)
        if version is None:
            return {}

        # Apply inheritance
        if version.parent_version:
            parent_config = self.get_config(version.parent_version)
            return self._merge_configs(parent_config, version.config)

        return version.config.copy()

    def _merge_configs(self,
                      base: Dict[str, Any],
                      override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configurations with override."""
        result = base.copy()

        for key, value in override.items():
            if (key in result and
                isinstance(result[key], dict) and
                isinstance(value, dict)):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def diff_versions(self,
                     version_a: str,
                     version_b: str) -> Dict[str, Any]:
        """
        Get differences between two versions.

        Args:
            version_a: First version ID
            version_b: Second version ID

        Returns:
            Dictionary of differences
        """
        config_a = self.get_config(version_a)
        config_b = self.get_config(version_b)

        return self._compute_diff(config_a, config_b, "")

    def _compute_diff(self,
                     dict_a: Dict,
                     dict_b: Dict,
                     path: str) -> Dict[str, Any]:
        """Compute recursive diff between dictionaries."""
        diff = {
            'added': {},
            'removed': {},
            'changed': {}
        }

        all_keys = set(dict_a.keys()) | set(dict_b.keys())

        for key in all_keys:
            full_path = f"{path}.{key}" if path else key

            if key not in dict_a:
                diff['added'][full_path] = dict_b[key]
            elif key not in dict_b:
                diff['removed'][full_path] = dict_a[key]
            elif dict_a[key] != dict_b[key]:
                if isinstance(dict_a[key], dict) and isinstance(dict_b[key], dict):
                    nested = self._compute_diff(dict_a[key], dict_b[key], full_path)
                    for k, v in nested.items():
                        diff[k].update(v)
                else:
                    diff['changed'][full_path] = {
                        'old': dict_a[key],
                        'new': dict_b[key]
                    }

        return diff

    def list_versions(self) -> List[ConfigVersion]:
        """List all versions."""
        versions = list(self._versions.values())
        versions.sort(key=lambda v: v.created_at, reverse=True)
        return versions

    def search_versions(self,
                       name_filter: Optional[str] = None,
                       tags: Optional[Dict[str, str]] = None) -> List[ConfigVersion]:
        """Search versions by name or tags."""
        results = list(self._versions.values())

        if name_filter:
            results = [v for v in results if name_filter.lower() in v.name.lower()]

        if tags:
            results = [
                v for v in results
                if all(v.tags.get(k) == val for k, val in tags.items())
            ]

        return results

    def export_version(self, version_id: str, output_path: str) -> bool:
        """Export version to file."""
        config = self.get_config(version_id)
        if not config:
            return False

        try:
            with open(output_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False

    def import_config(self,
                     input_path: str,
                     name: str,
                     description: str = "") -> Optional[ConfigVersion]:
        """Import configuration from file."""
        try:
            with open(input_path, 'r') as f:
                config = json.load(f)

            return self.create_version(name, config, description=description)

        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return None

    def delete_version(self, version_id: str) -> bool:
        """Delete a version."""
        if version_id not in self._versions:
            return False

        # Don't delete if it's a parent of another version
        for v in self._versions.values():
            if v.parent_version == version_id:
                logger.error(f"Cannot delete - version {v.version_id} depends on it")
                return False

        del self._versions[version_id]

        if self._current_version == version_id:
            self._current_version = None

        self._save_versions()
        return True
