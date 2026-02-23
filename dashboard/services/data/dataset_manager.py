"""
Dataset Manager - Versioned Dataset Management.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides dataset versioning, lineage tracking, and reproducible data access.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import hashlib
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class DatasetStatus(Enum):
    """Dataset lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DatasetType(Enum):
    """Types of datasets in manufacturing."""
    QUALITY_IMAGES = "quality_images"
    SENSOR_DATA = "sensor_data"
    PRINT_LOGS = "print_logs"
    DEFECT_ANNOTATIONS = "defect_annotations"
    CAD_MODELS = "cad_models"
    GCODE_FILES = "gcode_files"
    TRAINING_DATA = "training_data"
    EVALUATION_DATA = "evaluation_data"
    PRODUCTION_METRICS = "production_metrics"


@dataclass
class DatasetVersion:
    """A specific version of a dataset."""
    version_id: str
    version_number: str
    dataset_id: str
    created_at: datetime
    created_by: str
    commit_hash: str
    parent_version: Optional[str]
    size_bytes: int
    record_count: int
    schema_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "dataset_id": self.dataset_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "commit_hash": self.commit_hash,
            "parent_version": self.parent_version,
            "size_bytes": self.size_bytes,
            "record_count": self.record_count,
            "schema_hash": self.schema_hash,
            "metadata": self.metadata,
            "tags": self.tags,
        }


@dataclass
class Dataset:
    """A versioned dataset for manufacturing research."""
    dataset_id: str
    name: str
    description: str
    dataset_type: DatasetType
    status: DatasetStatus
    created_at: datetime
    updated_at: datetime
    owner: str
    current_version: Optional[str]
    versions: List[DatasetVersion] = field(default_factory=list)
    schema: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    access_policy: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "description": self.description,
            "dataset_type": self.dataset_type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "owner": self.owner,
            "current_version": self.current_version,
            "versions": [v.to_dict() for v in self.versions],
            "schema": self.schema,
            "lineage": self.lineage,
            "access_policy": self.access_policy,
        }


class DatasetManager:
    """
    Manages versioned datasets for manufacturing research.

    Features:
    - Semantic versioning for datasets
    - Schema evolution tracking
    - Data lineage and provenance
    - Reproducible data access
    - Access control policies
    """

    def __init__(self, storage_path: str = "/data/datasets"):
        self.storage_path = storage_path
        self.datasets: Dict[str, Dataset] = {}
        self._initialize_sample_datasets()

    def _initialize_sample_datasets(self):
        """Initialize with sample datasets for development."""
        # Quality inspection images dataset
        quality_ds = Dataset(
            dataset_id="ds-quality-images-001",
            name="LEGO Brick Quality Images",
            description="Annotated images for quality inspection model training",
            dataset_type=DatasetType.QUALITY_IMAGES,
            status=DatasetStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            owner="quality_team",
            current_version="2.3.0",
            schema={
                "image_format": "PNG",
                "resolution": "1920x1080",
                "color_space": "RGB",
                "annotations": "COCO format",
            },
            lineage={
                "source": "Production Line Camera System",
                "collection_period": "2023-01 to 2024-01",
                "annotation_method": "Manual + AI-assisted",
            },
        )

        # Add version history
        quality_ds.versions = [
            DatasetVersion(
                version_id=str(uuid.uuid4()),
                version_number="2.3.0",
                dataset_id=quality_ds.dataset_id,
                created_at=datetime.now(),
                created_by="quality_team",
                commit_hash="abc123def",
                parent_version="2.2.0",
                size_bytes=2_500_000_000,
                record_count=15000,
                schema_hash="sha256:abc123",
                metadata={"training_split": 0.8, "validation_split": 0.1},
                tags=["production", "validated"],
            ),
            DatasetVersion(
                version_id=str(uuid.uuid4()),
                version_number="2.2.0",
                dataset_id=quality_ds.dataset_id,
                created_at=datetime.now(),
                created_by="quality_team",
                commit_hash="xyz789abc",
                parent_version="2.1.0",
                size_bytes=2_200_000_000,
                record_count=12500,
                schema_hash="sha256:xyz789",
                metadata={"training_split": 0.8},
                tags=["production"],
            ),
        ]

        self.datasets[quality_ds.dataset_id] = quality_ds

        # Sensor data dataset
        sensor_ds = Dataset(
            dataset_id="ds-sensor-data-001",
            name="Printer Sensor Telemetry",
            description="Real-time sensor data from 3D printers",
            dataset_type=DatasetType.SENSOR_DATA,
            status=DatasetStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            owner="manufacturing_team",
            current_version="1.5.0",
            schema={
                "format": "Parquet",
                "columns": ["timestamp", "printer_id", "temperature", "humidity", "vibration"],
                "sampling_rate": "1Hz",
            },
        )
        self.datasets[sensor_ds.dataset_id] = sensor_ds

    def create_dataset(
        self,
        name: str,
        description: str,
        dataset_type: DatasetType,
        owner: str,
        schema: Dict[str, Any],
        lineage: Optional[Dict[str, Any]] = None,
    ) -> Dataset:
        """Create a new dataset."""
        dataset_id = f"ds-{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"

        dataset = Dataset(
            dataset_id=dataset_id,
            name=name,
            description=description,
            dataset_type=dataset_type,
            status=DatasetStatus.DRAFT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            owner=owner,
            current_version=None,
            schema=schema,
            lineage=lineage or {},
        )

        self.datasets[dataset_id] = dataset
        logger.info(f"Created dataset: {dataset_id}")

        return dataset

    def create_version(
        self,
        dataset_id: str,
        version_number: str,
        created_by: str,
        size_bytes: int,
        record_count: int,
        data_hash: str,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> DatasetVersion:
        """Create a new version of a dataset."""
        if dataset_id not in self.datasets:
            raise ValueError(f"Dataset not found: {dataset_id}")

        dataset = self.datasets[dataset_id]

        # Calculate schema hash
        schema_hash = hashlib.sha256(
            json.dumps(dataset.schema, sort_keys=True).encode()
        ).hexdigest()[:16]

        version = DatasetVersion(
            version_id=str(uuid.uuid4()),
            version_number=version_number,
            dataset_id=dataset_id,
            created_at=datetime.now(),
            created_by=created_by,
            commit_hash=data_hash,
            parent_version=dataset.current_version,
            size_bytes=size_bytes,
            record_count=record_count,
            schema_hash=f"sha256:{schema_hash}",
            metadata=metadata or {},
            tags=tags or [],
        )

        dataset.versions.append(version)
        dataset.current_version = version_number
        dataset.updated_at = datetime.now()

        if dataset.status == DatasetStatus.DRAFT:
            dataset.status = DatasetStatus.ACTIVE

        logger.info(f"Created version {version_number} for dataset {dataset_id}")

        return version

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID."""
        return self.datasets.get(dataset_id)

    def get_version(
        self,
        dataset_id: str,
        version: Optional[str] = None,
    ) -> Optional[DatasetVersion]:
        """Get a specific version of a dataset."""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return None

        target_version = version or dataset.current_version

        for v in dataset.versions:
            if v.version_number == target_version:
                return v

        return None

    def list_datasets(
        self,
        dataset_type: Optional[DatasetType] = None,
        status: Optional[DatasetStatus] = None,
        owner: Optional[str] = None,
    ) -> List[Dataset]:
        """List datasets with optional filtering."""
        results = list(self.datasets.values())

        if dataset_type:
            results = [d for d in results if d.dataset_type == dataset_type]
        if status:
            results = [d for d in results if d.status == status]
        if owner:
            results = [d for d in results if d.owner == owner]

        return results

    def compare_versions(
        self,
        dataset_id: str,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        """Compare two versions of a dataset."""
        v_a = self.get_version(dataset_id, version_a)
        v_b = self.get_version(dataset_id, version_b)

        if not v_a or not v_b:
            raise ValueError("Version not found")

        return {
            "dataset_id": dataset_id,
            "version_a": version_a,
            "version_b": version_b,
            "size_diff": v_b.size_bytes - v_a.size_bytes,
            "record_diff": v_b.record_count - v_a.record_count,
            "schema_changed": v_a.schema_hash != v_b.schema_hash,
            "time_diff_hours": (v_b.created_at - v_a.created_at).total_seconds() / 3600,
        }

    def get_lineage(self, dataset_id: str) -> Dict[str, Any]:
        """Get full lineage information for a dataset."""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_id}")

        version_chain = []
        for v in sorted(dataset.versions, key=lambda x: x.created_at):
            version_chain.append({
                "version": v.version_number,
                "parent": v.parent_version,
                "created_at": v.created_at.isoformat(),
                "created_by": v.created_by,
            })

        return {
            "dataset_id": dataset_id,
            "name": dataset.name,
            "source_lineage": dataset.lineage,
            "version_chain": version_chain,
            "current_version": dataset.current_version,
        }

    def register_transformation(
        self,
        source_dataset_id: str,
        target_dataset_id: str,
        transformation_type: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Register a data transformation for lineage tracking."""
        source = self.get_dataset(source_dataset_id)
        target = self.get_dataset(target_dataset_id)

        if not source or not target:
            raise ValueError("Source or target dataset not found")

        transformation = {
            "id": str(uuid.uuid4()),
            "source": source_dataset_id,
            "source_version": source.current_version,
            "target": target_dataset_id,
            "transformation_type": transformation_type,
            "parameters": parameters,
            "created_at": datetime.now().isoformat(),
        }

        target.lineage["transformations"] = target.lineage.get("transformations", [])
        target.lineage["transformations"].append(transformation)

        return transformation
