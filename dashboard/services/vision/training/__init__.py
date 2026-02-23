"""
Vision Training Pipeline

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Roboflow workspace management
- Dataset versioning
- LEGO-specific data augmentation
"""

from .roboflow_client import (
    RoboflowClient,
    RoboflowWorkspace,
    RoboflowProject,
    RoboflowDataset,
    get_roboflow_client,
)

from .dataset_manager import (
    DatasetManager,
    DatasetVersion,
    DatasetSplit,
    AnnotationFormat,
    get_dataset_manager,
)

from .augmentation import (
    LegoAugmentation,
    AugmentationConfig,
    AugmentationType,
    get_augmentation_pipeline,
)

__all__ = [
    # Roboflow
    "RoboflowClient",
    "RoboflowWorkspace",
    "RoboflowProject",
    "RoboflowDataset",
    "get_roboflow_client",
    # Dataset
    "DatasetManager",
    "DatasetVersion",
    "DatasetSplit",
    "AnnotationFormat",
    "get_dataset_manager",
    # Augmentation
    "LegoAugmentation",
    "AugmentationConfig",
    "AugmentationType",
    "get_augmentation_pipeline",
]
