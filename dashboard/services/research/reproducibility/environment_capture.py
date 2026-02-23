"""
Environment Capture - Runtime environment recording.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import sys
import os
import platform
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentSnapshot:
    """Snapshot of runtime environment."""
    snapshot_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    python_version: str = ""
    platform_info: Dict[str, str] = field(default_factory=dict)
    packages: Dict[str, str] = field(default_factory=dict)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    gpu_info: Optional[Dict[str, Any]] = None
    hardware_info: Dict[str, Any] = field(default_factory=dict)
    custom_info: Dict[str, Any] = field(default_factory=dict)


class EnvironmentCapture:
    """
    Capture and compare runtime environments.

    Features:
    - Python version and packages
    - System information
    - GPU availability
    - Environment variables (filtered)
    """

    # Environment variables to capture (whitelist approach for security)
    SAFE_ENV_VARS = [
        'PATH',
        'PYTHONPATH',
        'VIRTUAL_ENV',
        'CONDA_DEFAULT_ENV',
        'CUDA_VISIBLE_DEVICES',
        'TF_CPP_MIN_LOG_LEVEL',
        'OMP_NUM_THREADS',
        'MKL_NUM_THREADS',
    ]

    def __init__(self):
        self._snapshots: Dict[str, EnvironmentSnapshot] = {}

    def capture(self,
               snapshot_id: Optional[str] = None,
               include_packages: bool = True,
               custom_info: Optional[Dict[str, Any]] = None) -> EnvironmentSnapshot:
        """
        Capture current environment.

        Args:
            snapshot_id: Optional ID (generated if None)
            include_packages: Whether to capture installed packages
            custom_info: Additional custom information

        Returns:
            Environment snapshot
        """
        if snapshot_id is None:
            snapshot_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        snapshot = EnvironmentSnapshot(
            snapshot_id=snapshot_id,
            python_version=sys.version,
            platform_info=self._get_platform_info(),
            environment_vars=self._get_environment_vars(),
            hardware_info=self._get_hardware_info(),
            custom_info=custom_info or {}
        )

        if include_packages:
            snapshot.packages = self._get_packages()

        snapshot.gpu_info = self._get_gpu_info()

        self._snapshots[snapshot_id] = snapshot
        logger.info(f"Captured environment: {snapshot_id}")

        return snapshot

    def _get_platform_info(self) -> Dict[str, str]:
        """Get platform information."""
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_implementation': platform.python_implementation(),
            'python_version': platform.python_version(),
        }

    def _get_environment_vars(self) -> Dict[str, str]:
        """Get safe environment variables."""
        env_vars = {}
        for var in self.SAFE_ENV_VARS:
            if var in os.environ:
                env_vars[var] = os.environ[var]
        return env_vars

    def _get_packages(self) -> Dict[str, str]:
        """Get installed Python packages."""
        packages = {}

        try:
            # Try importlib.metadata (Python 3.8+)
            from importlib.metadata import distributions
            for dist in distributions():
                packages[dist.metadata['Name']] = dist.metadata['Version']
        except ImportError:
            try:
                # Fallback to pkg_resources
                import pkg_resources
                for dist in pkg_resources.working_set:
                    packages[dist.project_name] = dist.version
            except ImportError:
                logger.warning("Cannot capture package info")

        return packages

    def _get_hardware_info(self) -> Dict[str, Any]:
        """Get hardware information."""
        info = {
            'cpu_count': os.cpu_count(),
        }

        try:
            import psutil
            info['memory_total_gb'] = round(psutil.virtual_memory().total / (1024**3), 2)
            info['memory_available_gb'] = round(psutil.virtual_memory().available / (1024**3), 2)
            info['disk_total_gb'] = round(psutil.disk_usage('/').total / (1024**3), 2)
        except ImportError:
            pass

        return info

    def _get_gpu_info(self) -> Optional[Dict[str, Any]]:
        """Get GPU information if available."""
        gpu_info = None

        # Try PyTorch
        try:
            import torch
            if torch.cuda.is_available():
                gpu_info = {
                    'cuda_available': True,
                    'cuda_version': torch.version.cuda,
                    'device_count': torch.cuda.device_count(),
                    'devices': []
                }
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpu_info['devices'].append({
                        'name': props.name,
                        'memory_gb': round(props.total_memory / (1024**3), 2),
                        'compute_capability': f"{props.major}.{props.minor}"
                    })
            else:
                gpu_info = {'cuda_available': False}
        except ImportError:
            pass

        return gpu_info

    def get_snapshot(self, snapshot_id: str) -> Optional[EnvironmentSnapshot]:
        """Get snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def compare_snapshots(self,
                         snapshot_a: str,
                         snapshot_b: str) -> Dict[str, Any]:
        """
        Compare two environment snapshots.

        Args:
            snapshot_a: First snapshot ID
            snapshot_b: Second snapshot ID

        Returns:
            Comparison result
        """
        a = self._snapshots.get(snapshot_a)
        b = self._snapshots.get(snapshot_b)

        if not a or not b:
            return {'error': 'Snapshot not found'}

        comparison = {
            'python_version_match': a.python_version == b.python_version,
            'platform_match': a.platform_info == b.platform_info,
            'package_diffs': self._compare_packages(a.packages, b.packages),
            'env_var_diffs': self._compare_dicts(a.environment_vars, b.environment_vars),
        }

        return comparison

    def _compare_packages(self,
                         packages_a: Dict[str, str],
                         packages_b: Dict[str, str]) -> Dict[str, Any]:
        """Compare package versions."""
        all_packages = set(packages_a.keys()) | set(packages_b.keys())

        return {
            'added': {
                p: packages_b[p] for p in all_packages
                if p in packages_b and p not in packages_a
            },
            'removed': {
                p: packages_a[p] for p in all_packages
                if p in packages_a and p not in packages_b
            },
            'changed': {
                p: {'old': packages_a[p], 'new': packages_b[p]}
                for p in all_packages
                if p in packages_a and p in packages_b and packages_a[p] != packages_b[p]
            }
        }

    def _compare_dicts(self,
                      dict_a: Dict[str, str],
                      dict_b: Dict[str, str]) -> Dict[str, Any]:
        """Compare two dictionaries."""
        all_keys = set(dict_a.keys()) | set(dict_b.keys())

        return {
            'added': {k: dict_b[k] for k in all_keys if k in dict_b and k not in dict_a},
            'removed': {k: dict_a[k] for k in all_keys if k in dict_a and k not in dict_b},
            'changed': {
                k: {'old': dict_a[k], 'new': dict_b[k]}
                for k in all_keys
                if k in dict_a and k in dict_b and dict_a[k] != dict_b[k]
            }
        }

    def export_snapshot(self, snapshot_id: str, output_path: str) -> bool:
        """Export snapshot to JSON file."""
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return False

        data = {
            'snapshot_id': snapshot.snapshot_id,
            'created_at': snapshot.created_at.isoformat(),
            'python_version': snapshot.python_version,
            'platform_info': snapshot.platform_info,
            'packages': snapshot.packages,
            'environment_vars': snapshot.environment_vars,
            'gpu_info': snapshot.gpu_info,
            'hardware_info': snapshot.hardware_info,
            'custom_info': snapshot.custom_info
        }

        try:
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to export snapshot: {e}")
            return False

    def generate_requirements(self, snapshot_id: str) -> str:
        """Generate requirements.txt from snapshot."""
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return ""

        lines = []
        for package, version in sorted(snapshot.packages.items()):
            lines.append(f"{package}=={version}")

        return "\n".join(lines)

    def check_reproducibility(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Check if current environment can reproduce snapshot.

        Returns warnings for any differences.
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return {'error': 'Snapshot not found'}

        current = self.capture(include_packages=True)
        comparison = self.compare_snapshots(current.snapshot_id, snapshot_id)

        warnings = []
        errors = []

        # Check Python version
        if not comparison['python_version_match']:
            errors.append(f"Python version mismatch: {current.python_version} vs {snapshot.python_version}")

        # Check packages
        pkg_diffs = comparison['package_diffs']
        if pkg_diffs['changed']:
            for pkg, versions in pkg_diffs['changed'].items():
                warnings.append(f"Package version changed: {pkg} ({versions['old']} -> {versions['new']})")

        if pkg_diffs['removed']:
            for pkg in pkg_diffs['removed']:
                errors.append(f"Missing package: {pkg}")

        return {
            'reproducible': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
