"""
Vision Analysis - OpenCV-based Image Analysis

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Layer analysis for 3D prints
- Edge detection
- Contour analysis
"""

from .layer_analysis import (
    LayerAnalyzer,
    LayerMeasurement,
    LayerQuality,
    get_layer_analyzer,
)

from .edge_detector import (
    EdgeDetector,
    EdgeDetectionMethod,
    EdgeResult,
    get_edge_detector,
)

from .contour_analyzer import (
    ContourAnalyzer,
    ContourFeatures,
    ShapeClassification,
    get_contour_analyzer,
)

__all__ = [
    # Layer Analysis
    "LayerAnalyzer",
    "LayerMeasurement",
    "LayerQuality",
    "get_layer_analyzer",
    # Edge Detection
    "EdgeDetector",
    "EdgeDetectionMethod",
    "EdgeResult",
    "get_edge_detector",
    # Contour Analysis
    "ContourAnalyzer",
    "ContourFeatures",
    "ShapeClassification",
    "get_contour_analyzer",
]
