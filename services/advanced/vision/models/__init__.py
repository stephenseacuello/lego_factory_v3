"""
Vision Models - Registry & Hardware-Aware Loading

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Model versioning & registry
- A/B testing support
- Hardware-aware model loading (CUDA, MPS, CPU, Edge)
"""

from .model_registry import (
    ModelRegistry,
    ModelVersion,
    ModelMetadata,
    ModelStatus,
    DeploymentTarget,
    get_model_registry,
)

from .model_loader import (
    ModelLoader,
    HardwareProfile,
    DeviceType,
    ModelFormat,
    LoadedModel,
    get_model_loader,
)

__all__ = [
    # Registry
    "ModelRegistry",
    "ModelVersion",
    "ModelMetadata",
    "ModelStatus",
    "DeploymentTarget",
    "get_model_registry",
    # Loader
    "ModelLoader",
    "HardwareProfile",
    "DeviceType",
    "ModelFormat",
    "LoadedModel",
    "get_model_loader",
]
