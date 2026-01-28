"""
Vision Pipeline Module - End-to-End Vision Processing

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Vision pipeline orchestration
- Quality integration bridge
- SPC chart integration
"""

from .orchestrator import (
    VisionPipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
    get_vision_pipeline,
)

from .quality_bridge import (
    QualityBridge,
    QualityBridgeConfig,
    VisionQualityEvent,
    get_quality_bridge,
)

from .spc_integration import (
    SPCIntegration,
    SPCConfig,
    VisionMeasurement,
    get_spc_integration,
)


__all__ = [
    # Orchestrator
    "VisionPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    "get_vision_pipeline",
    # Quality Bridge
    "QualityBridge",
    "QualityBridgeConfig",
    "VisionQualityEvent",
    "get_quality_bridge",
    # SPC Integration
    "SPCIntegration",
    "SPCConfig",
    "VisionMeasurement",
    "get_spc_integration",
]
