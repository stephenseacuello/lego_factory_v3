"""
Vision AI Module
================

LegoMCP PhD-Level Manufacturing Platform
Part of the AI/ML for Quality Research (Phase 5)

This module provides comprehensive computer vision capabilities for
manufacturing quality inspection, defect detection, and visual AI.

Core Capabilities:
------------------
1. **Object Detection**: YOLO11, Faster R-CNN, RetinaNet
2. **Defect Classification**: CNN-based quality classification
3. **Semantic Segmentation**: Pixel-level defect localization
4. **Anomaly Detection**: Unsupervised defect discovery

Architecture:
-------------
The vision system follows a modular architecture:

    Camera -> Preprocessing -> Detection -> Analysis -> Decision
               |                   |           |
               v                   v           v
           Augmentation      Foundation    Quality
                              Models       Decision

Key Components:
---------------

1. **LegoDetector**:
   - YOLO11 object detection (Ultralytics)
   - Real-time brick detection and classification
   - Color classification and matching
   - Batch inference support

2. **CameraManager**:
   - Multi-camera support (USB, IP, industrial)
   - Frame capture and buffering
   - Camera calibration and correction
   - Hardware-accelerated preprocessing

3. **Training Pipeline** (training/):
   - Roboflow integration for dataset management
   - Data augmentation for manufacturing (lighting, defects)
   - Active learning sample selection
   - Transfer learning from pre-trained models

4. **Model Registry** (models/):
   - Version-controlled model storage
   - Hardware-aware model selection
   - Deployment target optimization (CPU, GPU, edge)
   - A/B testing support

5. **Foundation Models** (foundation/):
   - SAM (Segment Anything Model) for zero-shot segmentation
   - DINO/DINOv2 for self-supervised features
   - CLIP for vision-language tasks
   - GroundingDINO for open-vocabulary detection

6. **SSL/Active Learning** (ssl/, active_learning/):
   - Contrastive learning (SimCLR, MoCo)
   - Masked autoencoders
   - Uncertainty-based sample selection
   - Human-in-the-loop annotation

Detection Pipeline:
-------------------
    Input Image
         |
         v
    ┌─────────────┐
    │ Preprocess  │ (resize, normalize, augment)
    └─────────────┘
         |
         v
    ┌─────────────┐
    │  Backbone   │ (YOLOv11, ResNet, ViT)
    └─────────────┘
         |
         v
    ┌─────────────┐
    │    Head     │ (detection, classification)
    └─────────────┘
         |
         v
    ┌─────────────┐
    │ Post-proc   │ (NMS, thresholding)
    └─────────────┘
         |
         v
    Detections + Confidence

Example Usage:
--------------
    from services.vision import (
        LegoDetector,
        get_detector,
        CameraManager,
        ModelRegistry,
    )

    # Initialize detector
    detector = get_detector()

    # Detect bricks in image
    detections = detector.detect(image)
    for det in detections:
        print(f"Found {det.class_name} at {det.bbox} "
              f"(confidence: {det.confidence:.2f})")

    # Camera capture
    camera = CameraManager()
    frame = camera.capture()

    # Continuous inspection
    for frame in camera.stream():
        detections = detector.detect(frame)
        # ... process detections ...

    # Model management
    registry = ModelRegistry()
    model = registry.load_best_model(
        task="defect_detection",
        target="edge_gpu",
    )

Manufacturing Applications:
---------------------------
- **Inline Inspection**: Real-time defect detection on production line
- **Assembly Verification**: Verify correct part placement
- **Dimensional Measurement**: Vision-based metrology
- **Surface Analysis**: Scratch, crack, stain detection
- **Color Matching**: Ensure color consistency

Research Contributions:
-----------------------
- Foundation model fine-tuning for manufacturing
- Self-supervised learning with limited labels
- Active learning for efficient annotation
- Multi-modal fusion (vision + sensor data)

References:
-----------
- Redmon, J. et al. (2016). You Only Look Once (YOLO)
- Kirillov, A. et al. (2023). Segment Anything (SAM)
- Caron, M. et al. (2021). Emerging Properties in Self-Supervised ViTs (DINO)
- Radford, A. et al. (2021). Learning Transferable Visual Models (CLIP)

Author: LegoMCP Team
Version: 2.0.0
"""

# Core Detection
from .detector import (
    LegoDetector,
    BrickDetection,
    DetectionBackend,
    LegoColorClassifier,
    BrickMatcher,
    get_detector,
    reset_detector,
)

# Camera Management
from .camera_manager import (
    CameraManager,
    CameraInfo,
    CameraType,
    get_camera_manager,
)

# Training Pipeline
from .training import (
    RoboflowClient,
    RoboflowWorkspace,
    RoboflowProject,
    RoboflowDataset,
    get_roboflow_client,
    DatasetManager,
    DatasetVersion,
    DatasetSplit,
    AnnotationFormat,
    get_dataset_manager,
    LegoAugmentation,
    AugmentationConfig,
    AugmentationType,
    get_augmentation_pipeline,
)

# Model Registry & Loader
from .models import (
    ModelRegistry,
    ModelVersion,
    ModelMetadata,
    ModelStatus,
    DeploymentTarget,
    get_model_registry,
    ModelLoader,
    HardwareProfile,
    DeviceType,
    ModelFormat,
    LoadedModel,
    get_model_loader,
)

# Foundation Models
from .foundation import (
    SAMSegmenter,
    DINOFeatureExtractor,
    CLIPClassifier,
    GroundingDINODetector,
)

# SSL & Active Learning
from .ssl import (
    ContrastiveLearner,
    MaskedAutoencoder,
    SSLAnomalyDetector,
)

from .active_learning import (
    UncertaintySampler,
    DiversitySampler,
    HITLManager,
)

# 3D Defect Mapping (ISO 23247 compliant)
from .defect_mapping_3d import (
    DefectMapping3DService,
    Defect2D,
    Defect3D,
    DefectCluster,
    QualityHeatmap,
    Vector3D,
    CameraCalibration,
    CameraModel,
    DefectType,
    DefectSeverity,
    get_defect_mapping_service,
)

# Vision Processor (Background service)
from .processor import (
    VisionProcessor,
)

# Quality Heatmap Generator
from .quality_heatmap import (
    QualityHeatmapGenerator,
    HeatmapType,
    InterpolationMethod,
    ColorScale,
    BoundingBox,
    QualityDataPoint,
    HeatmapCell,
    Heatmap,
    HeatmapConfig,
    TemporalTrendAnalyzer,
    RootCauseAnalyzer,
    get_quality_heatmap_generator,
)

__all__ = [
    # Detector
    "LegoDetector",
    "BrickDetection",
    "DetectionBackend",
    "LegoColorClassifier",
    "BrickMatcher",
    "get_detector",
    "reset_detector",

    # Camera
    "CameraManager",
    "CameraInfo",
    "CameraType",
    "get_camera_manager",

    # Training
    "RoboflowClient",
    "RoboflowWorkspace",
    "RoboflowProject",
    "RoboflowDataset",
    "get_roboflow_client",
    "DatasetManager",
    "DatasetVersion",
    "DatasetSplit",
    "AnnotationFormat",
    "get_dataset_manager",
    "LegoAugmentation",
    "AugmentationConfig",
    "AugmentationType",
    "get_augmentation_pipeline",

    # Models
    "ModelRegistry",
    "ModelVersion",
    "ModelMetadata",
    "ModelStatus",
    "DeploymentTarget",
    "get_model_registry",
    "ModelLoader",
    "HardwareProfile",
    "DeviceType",
    "ModelFormat",
    "LoadedModel",
    "get_model_loader",

    # Foundation
    "SAMSegmenter",
    "DINOFeatureExtractor",
    "CLIPClassifier",
    "GroundingDINODetector",

    # SSL
    "ContrastiveLearner",
    "MaskedAutoencoder",
    "SSLAnomalyDetector",

    # Active Learning
    "UncertaintySampler",
    "DiversitySampler",
    "HITLManager",

    # 3D Defect Mapping
    "DefectMapping3DService",
    "Defect2D",
    "Defect3D",
    "DefectCluster",
    "QualityHeatmap",
    "Vector3D",
    "CameraCalibration",
    "CameraModel",
    "DefectType",
    "DefectSeverity",
    "get_defect_mapping_service",

    # Vision Processor
    "VisionProcessor",

    # Quality Heatmap
    "QualityHeatmapGenerator",
    "HeatmapType",
    "InterpolationMethod",
    "ColorScale",
    "BoundingBox",
    "QualityDataPoint",
    "HeatmapCell",
    "Heatmap",
    "HeatmapConfig",
    "TemporalTrendAnalyzer",
    "RootCauseAnalyzer",
    "get_quality_heatmap_generator",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
