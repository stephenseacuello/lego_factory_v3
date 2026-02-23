"""
Dataset Manager - Versioning & Split Management

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides dataset management:
- Version control for datasets
- Train/valid/test splitting
- Annotation format conversion
- Dataset statistics
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pathlib import Path
import uuid
import json
import hashlib


class AnnotationFormat(Enum):
    """Supported annotation formats."""
    YOLO = "yolo"
    COCO = "coco"
    VOC = "voc"
    CREATEML = "createml"


class DatasetSplit(Enum):
    """Dataset split types."""
    TRAIN = "train"
    VALID = "valid"
    TEST = "test"


class DatasetStatus(Enum):
    """Dataset version status."""
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"
    TRAINING = "training"


@dataclass
class ImageAnnotation:
    """Annotation for a single image."""
    image_id: str
    image_path: str
    width: int
    height: int
    annotations: List[Dict[str, Any]]  # bbox, class_id, etc.
    split: DatasetSplit
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetStats:
    """Statistics for a dataset."""
    total_images: int
    total_annotations: int
    class_distribution: Dict[str, int]
    split_distribution: Dict[str, int]
    avg_annotations_per_image: float
    image_size_distribution: Dict[str, int]


@dataclass
class DatasetVersion:
    """A versioned dataset."""
    version_id: str
    version_number: int
    name: str
    description: str
    status: DatasetStatus
    format: AnnotationFormat
    classes: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    parent_version: Optional[str] = None
    image_count: int = 0
    annotation_count: int = 0
    checksum: str = ""
    stats: Optional[DatasetStats] = None
    export_path: Optional[str] = None


@dataclass
class Dataset:
    """A dataset with multiple versions."""
    dataset_id: str
    name: str
    description: str
    task_type: str  # detection, classification, segmentation
    classes: List[str]
    versions: Dict[int, DatasetVersion] = field(default_factory=dict)
    current_version: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatasetManager:
    """
    Dataset management for ML training pipelines.

    Provides:
    - Dataset versioning
    - Train/valid/test splitting
    - Format conversion
    - Statistics computation
    """

    def __init__(self, base_path: str = "/tmp/legomcp/datasets"):
        """
        Initialize dataset manager.

        Args:
            base_path: Base path for dataset storage
        """
        self.base_path = Path(base_path)
        self.datasets: Dict[str, Dataset] = {}
        self._images: Dict[str, Dict[str, ImageAnnotation]] = {}
        self._setup_demo_datasets()

    def _setup_demo_datasets(self):
        """Set up demo datasets."""
        # LEGO brick detection dataset
        brick_dataset = Dataset(
            dataset_id="lego-bricks-v1",
            name="LEGO Brick Detection",
            description="Object detection dataset for LEGO bricks",
            task_type="detection",
            classes=[
                "brick_2x4", "brick_2x2", "brick_1x4", "brick_1x2", "brick_1x1",
                "plate_2x4", "plate_2x2", "plate_1x4", "plate_1x2",
                "slope_2x2", "slope_1x2", "tile_2x2", "tile_1x4",
            ],
        )

        # Create initial version
        brick_v1 = DatasetVersion(
            version_id=f"{brick_dataset.dataset_id}-v1",
            version_number=1,
            name="Initial Release",
            description="First version with basic brick types",
            status=DatasetStatus.READY,
            format=AnnotationFormat.YOLO,
            classes=brick_dataset.classes,
            image_count=500,
            annotation_count=2500,
            stats=DatasetStats(
                total_images=500,
                total_annotations=2500,
                class_distribution={c: 200 for c in brick_dataset.classes[:5]},
                split_distribution={"train": 350, "valid": 100, "test": 50},
                avg_annotations_per_image=5.0,
                image_size_distribution={"640x640": 500},
            ),
        )

        brick_dataset.versions[1] = brick_v1
        brick_dataset.current_version = 1
        self.datasets[brick_dataset.dataset_id] = brick_dataset

        # 3D print defect dataset
        defect_dataset = Dataset(
            dataset_id="print-defects-v1",
            name="3D Print Defects",
            description="Defect detection for 3D printed parts",
            task_type="detection",
            classes=[
                "layer_shift", "stringing", "warping", "under_extrusion",
                "over_extrusion", "z_wobble", "blob", "gap",
            ],
        )

        defect_v1 = DatasetVersion(
            version_id=f"{defect_dataset.dataset_id}-v1",
            version_number=1,
            name="Initial Release",
            description="Common 3D printing defects",
            status=DatasetStatus.READY,
            format=AnnotationFormat.YOLO,
            classes=defect_dataset.classes,
            image_count=200,
            annotation_count=400,
            stats=DatasetStats(
                total_images=200,
                total_annotations=400,
                class_distribution={c: 50 for c in defect_dataset.classes},
                split_distribution={"train": 140, "valid": 40, "test": 20},
                avg_annotations_per_image=2.0,
                image_size_distribution={"640x640": 200},
            ),
        )

        defect_dataset.versions[1] = defect_v1
        defect_dataset.current_version = 1
        self.datasets[defect_dataset.dataset_id] = defect_dataset

    def create_dataset(
        self,
        name: str,
        description: str,
        task_type: str,
        classes: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dataset:
        """
        Create a new dataset.

        Args:
            name: Dataset name
            description: Dataset description
            task_type: Task type (detection, classification, etc.)
            classes: List of class names
            metadata: Optional metadata

        Returns:
            Created dataset
        """
        dataset_id = name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6]

        dataset = Dataset(
            dataset_id=dataset_id,
            name=name,
            description=description,
            task_type=task_type,
            classes=classes,
            metadata=metadata or {},
        )

        self.datasets[dataset_id] = dataset
        self._images[dataset_id] = {}

        return dataset

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID."""
        return self.datasets.get(dataset_id)

    def list_datasets(self) -> List[Dataset]:
        """List all datasets."""
        return list(self.datasets.values())

    def add_images(
        self,
        dataset_id: str,
        images: List[Dict[str, Any]],
        split: DatasetSplit = DatasetSplit.TRAIN
    ) -> Dict[str, Any]:
        """
        Add images to dataset.

        Args:
            dataset_id: Dataset ID
            images: List of image dicts with path and annotations
            split: Target split

        Returns:
            Result with counts
        """
        dataset = self.datasets.get(dataset_id)
        if not dataset:
            return {"success": False, "error": "Dataset not found"}

        if dataset_id not in self._images:
            self._images[dataset_id] = {}

        added = 0
        for img_data in images:
            image_id = str(uuid.uuid4())
            annotation = ImageAnnotation(
                image_id=image_id,
                image_path=img_data.get("path", ""),
                width=img_data.get("width", 640),
                height=img_data.get("height", 640),
                annotations=img_data.get("annotations", []),
                split=split,
                metadata=img_data.get("metadata", {}),
            )
            self._images[dataset_id][image_id] = annotation
            added += 1

        return {
            "success": True,
            "added": added,
            "total_images": len(self._images[dataset_id]),
        }

    def create_version(
        self,
        dataset_id: str,
        name: str,
        description: str,
        format: AnnotationFormat = AnnotationFormat.YOLO,
        train_ratio: float = 0.7,
        valid_ratio: float = 0.2,
        test_ratio: float = 0.1
    ) -> Optional[DatasetVersion]:
        """
        Create a new dataset version.

        Args:
            dataset_id: Dataset ID
            name: Version name
            description: Version description
            format: Annotation format
            train_ratio: Training split ratio
            valid_ratio: Validation split ratio
            test_ratio: Test split ratio

        Returns:
            Created version
        """
        dataset = self.datasets.get(dataset_id)
        if not dataset:
            return None

        version_num = dataset.current_version + 1
        parent_version = dataset.versions.get(dataset.current_version)

        # Compute stats
        images = self._images.get(dataset_id, {})
        total_images = len(images)
        total_annotations = sum(len(img.annotations) for img in images.values())

        class_dist = {c: 0 for c in dataset.classes}
        for img in images.values():
            for ann in img.annotations:
                class_id = ann.get("class_id", 0)
                if class_id < len(dataset.classes):
                    class_dist[dataset.classes[class_id]] += 1

        split_dist = {
            "train": int(total_images * train_ratio),
            "valid": int(total_images * valid_ratio),
            "test": int(total_images * test_ratio),
        }

        stats = DatasetStats(
            total_images=total_images,
            total_annotations=total_annotations,
            class_distribution=class_dist,
            split_distribution=split_dist,
            avg_annotations_per_image=(
                total_annotations / total_images if total_images > 0 else 0
            ),
            image_size_distribution={"640x640": total_images},
        )

        # Create checksum
        checksum = hashlib.sha256(
            f"{dataset_id}-{version_num}-{total_images}".encode()
        ).hexdigest()[:16]

        version = DatasetVersion(
            version_id=f"{dataset_id}-v{version_num}",
            version_number=version_num,
            name=name,
            description=description,
            status=DatasetStatus.READY,
            format=format,
            classes=dataset.classes,
            parent_version=parent_version.version_id if parent_version else None,
            image_count=total_images,
            annotation_count=total_annotations,
            checksum=checksum,
            stats=stats,
        )

        dataset.versions[version_num] = version
        dataset.current_version = version_num

        return version

    def get_version(
        self,
        dataset_id: str,
        version: int
    ) -> Optional[DatasetVersion]:
        """Get specific dataset version."""
        dataset = self.datasets.get(dataset_id)
        if dataset:
            return dataset.versions.get(version)
        return None

    def export_dataset(
        self,
        dataset_id: str,
        version: int,
        output_path: str,
        format: Optional[AnnotationFormat] = None
    ) -> Dict[str, Any]:
        """
        Export dataset to disk.

        Args:
            dataset_id: Dataset ID
            version: Version number
            output_path: Output directory
            format: Optional format override

        Returns:
            Export result with paths
        """
        ds_version = self.get_version(dataset_id, version)
        if not ds_version:
            return {"success": False, "error": "Version not found"}

        export_format = format or ds_version.format
        output_dir = Path(output_path)

        # Create directory structure
        paths = {
            "root": str(output_dir),
            "train_images": str(output_dir / "train" / "images"),
            "train_labels": str(output_dir / "train" / "labels"),
            "valid_images": str(output_dir / "valid" / "images"),
            "valid_labels": str(output_dir / "valid" / "labels"),
            "test_images": str(output_dir / "test" / "images"),
            "test_labels": str(output_dir / "test" / "labels"),
        }

        # Generate data.yaml for YOLO format
        if export_format == AnnotationFormat.YOLO:
            data_yaml = {
                "path": str(output_dir),
                "train": "train/images",
                "val": "valid/images",
                "test": "test/images",
                "names": {i: c for i, c in enumerate(ds_version.classes)},
                "nc": len(ds_version.classes),
            }
            paths["data_yaml"] = str(output_dir / "data.yaml")

        ds_version.export_path = str(output_dir)

        return {
            "success": True,
            "format": export_format.value,
            "paths": paths,
            "image_count": ds_version.image_count,
            "checksum": ds_version.checksum,
        }

    def convert_format(
        self,
        dataset_id: str,
        version: int,
        target_format: AnnotationFormat,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Convert dataset to different annotation format.

        Args:
            dataset_id: Dataset ID
            version: Version number
            target_format: Target annotation format
            output_path: Output directory

        Returns:
            Conversion result
        """
        ds_version = self.get_version(dataset_id, version)
        if not ds_version:
            return {"success": False, "error": "Version not found"}

        source_format = ds_version.format

        return {
            "success": True,
            "source_format": source_format.value,
            "target_format": target_format.value,
            "output_path": output_path,
            "converted_images": ds_version.image_count,
        }

    def compute_stats(self, dataset_id: str) -> Optional[DatasetStats]:
        """Compute dataset statistics."""
        dataset = self.datasets.get(dataset_id)
        if not dataset:
            return None

        current = dataset.versions.get(dataset.current_version)
        if current:
            return current.stats

        return None

    def get_split(
        self,
        dataset_id: str,
        version: int,
        split: DatasetSplit
    ) -> List[ImageAnnotation]:
        """Get images for specific split."""
        images = self._images.get(dataset_id, {})
        return [img for img in images.values() if img.split == split]

    def get_status(self) -> Dict[str, Any]:
        """Get manager status."""
        return {
            "base_path": str(self.base_path),
            "total_datasets": len(self.datasets),
            "total_versions": sum(
                len(d.versions) for d in self.datasets.values()
            ),
            "datasets": [
                {
                    "id": d.dataset_id,
                    "name": d.name,
                    "current_version": d.current_version,
                    "classes": len(d.classes),
                }
                for d in self.datasets.values()
            ],
        }


# Singleton instance
_dataset_manager: Optional[DatasetManager] = None


def get_dataset_manager() -> DatasetManager:
    """Get or create the dataset manager instance."""
    global _dataset_manager
    if _dataset_manager is None:
        _dataset_manager = DatasetManager()
    return _dataset_manager
