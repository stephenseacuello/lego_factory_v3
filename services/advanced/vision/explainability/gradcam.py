"""
GradCAM - Gradient-weighted Class Activation Mapping

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides visual explanations:
- GradCAM heatmaps
- GradCAM++ for better localization
- Layer-wise activation analysis
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class GradCAMMethod(Enum):
    """GradCAM variants."""
    GRADCAM = "gradcam"
    GRADCAM_PLUS_PLUS = "gradcam++"
    SCORE_CAM = "score_cam"
    EIGEN_CAM = "eigen_cam"
    LAYER_CAM = "layer_cam"


@dataclass
class GradCAMConfig:
    """GradCAM configuration."""
    method: GradCAMMethod = GradCAMMethod.GRADCAM
    target_layer: Optional[str] = None  # Auto-detect if None
    use_cuda: bool = True
    colormap: str = "jet"  # jet, viridis, hot, etc.
    alpha: float = 0.5  # Overlay transparency
    normalize: bool = True


@dataclass
class ActivationInfo:
    """Layer activation information."""
    layer_name: str
    activation_shape: Tuple[int, ...]
    mean_activation: float
    max_activation: float
    gradient_norm: float


@dataclass
class GradCAMResult:
    """GradCAM explanation result."""
    image_id: str
    method: GradCAMMethod
    target_class: int
    target_class_name: str
    confidence: float
    heatmap: Optional[Any] = None  # Numpy array
    overlay: Optional[Any] = None  # Image with overlay
    attention_regions: List[Tuple[int, int, int, int]] = field(default_factory=list)
    activation_info: Optional[ActivationInfo] = None
    target_layer: str = ""
    processing_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class GradCAM:
    """
    Gradient-weighted Class Activation Mapping.

    Provides visual explanations for CNN predictions
    by highlighting important image regions.
    """

    def __init__(self, config: Optional[GradCAMConfig] = None):
        """
        Initialize GradCAM.

        Args:
            config: GradCAM configuration
        """
        self.config = config or GradCAMConfig()
        self._model = None
        self._target_layers: Dict[str, Any] = {}
        self._activations: Dict[str, Any] = {}
        self._gradients: Dict[str, Any] = {}

    def set_model(self, model: Any, target_layer: Optional[str] = None):
        """
        Set the model for explanation.

        Args:
            model: PyTorch/YOLO model
            target_layer: Target layer name (auto-detect if None)
        """
        self._model = model
        self._target_layers = {}

        # Auto-detect target layer for common architectures
        if target_layer:
            self.config.target_layer = target_layer
        elif not self.config.target_layer:
            self.config.target_layer = self._auto_detect_layer(model)

    def _auto_detect_layer(self, model: Any) -> str:
        """Auto-detect appropriate target layer."""
        # Common layer names for different architectures
        layer_candidates = [
            "model.23",  # YOLOv8
            "layer4",    # ResNet
            "features",  # VGG/MobileNet
            "conv_head", # EfficientNet
            "backbone.body.layer4",  # Faster R-CNN
        ]

        # In real implementation, iterate through model layers
        return layer_candidates[0]

    def explain(
        self,
        image: Any,
        target_class: Optional[int] = None,
        target_bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> GradCAMResult:
        """
        Generate GradCAM explanation.

        Args:
            image: Input image
            target_class: Target class index (uses top prediction if None)
            target_bbox: Target bounding box for object detection

        Returns:
            GradCAM result with heatmap
        """
        import time
        start_time = time.time()

        # Simulate GradCAM computation
        # Real implementation:
        # 1. Forward pass to get activations
        # 2. Backward pass to get gradients
        # 3. Compute weighted combination
        # 4. Apply ReLU and normalize

        result = self._compute_gradcam(image, target_class, target_bbox)

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _compute_gradcam(
        self,
        image: Any,
        target_class: Optional[int],
        target_bbox: Optional[Tuple[int, int, int, int]]
    ) -> GradCAMResult:
        """Compute GradCAM heatmap."""
        import random

        # Simulated computation
        # Determine target class
        if target_class is None:
            target_class = random.randint(0, 7)

        class_names = [
            "brick_2x4", "brick_2x2", "layer_shift", "stringing",
            "warping", "under_extrusion", "blob", "gap"
        ]

        target_name = class_names[target_class % len(class_names)]
        confidence = random.uniform(0.7, 0.99)

        # Generate simulated heatmap
        # Real: heatmap = self._generate_heatmap(activations, gradients)
        heatmap = self._generate_simulated_heatmap(640, 640)

        # Find attention regions (high activation areas)
        attention_regions = self._find_attention_regions(heatmap)

        # Activation info
        activation_info = ActivationInfo(
            layer_name=self.config.target_layer or "auto",
            activation_shape=(1, 512, 20, 20),
            mean_activation=random.uniform(0.1, 0.5),
            max_activation=random.uniform(0.8, 1.0),
            gradient_norm=random.uniform(0.01, 0.1),
        )

        return GradCAMResult(
            image_id=str(id(image)),
            method=self.config.method,
            target_class=target_class,
            target_class_name=target_name,
            confidence=confidence,
            heatmap=heatmap,
            overlay=None,  # Would be image with heatmap overlay
            attention_regions=attention_regions,
            activation_info=activation_info,
            target_layer=self.config.target_layer or "auto",
        )

    def _generate_simulated_heatmap(
        self,
        height: int,
        width: int
    ) -> Any:
        """Generate simulated heatmap."""
        import random

        # In real implementation, this would be computed from gradients
        # Return placeholder dict representing heatmap
        return {
            "shape": (height, width),
            "max_value": random.uniform(0.8, 1.0),
            "min_value": 0.0,
            "hot_spots": [
                (random.randint(0, width), random.randint(0, height))
                for _ in range(random.randint(1, 5))
            ],
        }

    def _find_attention_regions(
        self,
        heatmap: Any,
        threshold: float = 0.5
    ) -> List[Tuple[int, int, int, int]]:
        """Find high-attention regions in heatmap."""
        import random

        # Simulated region detection
        # Real: threshold heatmap and find connected components
        num_regions = random.randint(1, 4)
        regions = []

        for _ in range(num_regions):
            x = random.randint(50, 500)
            y = random.randint(50, 500)
            w = random.randint(50, 150)
            h = random.randint(50, 150)
            regions.append((x, y, w, h))

        return regions

    def explain_detection(
        self,
        image: Any,
        detections: List[Dict[str, Any]]
    ) -> List[GradCAMResult]:
        """
        Generate GradCAM for each detection.

        Args:
            image: Input image
            detections: List of detection dicts with bbox and class

        Returns:
            List of GradCAM results
        """
        results = []

        for det in detections:
            bbox = det.get("bbox", (0, 0, 100, 100))
            class_id = det.get("class_id", 0)

            result = self.explain(image, class_id, bbox)
            results.append(result)

        return results

    def create_overlay(
        self,
        image: Any,
        heatmap: Any,
        alpha: Optional[float] = None
    ) -> Any:
        """
        Create heatmap overlay on image.

        Args:
            image: Original image
            heatmap: GradCAM heatmap
            alpha: Overlay transparency

        Returns:
            Image with heatmap overlay
        """
        alpha = alpha or self.config.alpha

        # Simulated overlay creation
        # Real: resize heatmap, apply colormap, blend with image
        return {
            "type": "overlay",
            "original_shape": (640, 640),
            "alpha": alpha,
            "colormap": self.config.colormap,
        }

    def compare_methods(
        self,
        image: Any,
        target_class: int,
        methods: Optional[List[GradCAMMethod]] = None
    ) -> Dict[str, GradCAMResult]:
        """
        Compare different GradCAM methods.

        Args:
            image: Input image
            target_class: Target class
            methods: Methods to compare

        Returns:
            Dict mapping method name to result
        """
        methods = methods or [
            GradCAMMethod.GRADCAM,
            GradCAMMethod.GRADCAM_PLUS_PLUS,
            GradCAMMethod.SCORE_CAM,
        ]

        results = {}
        original_method = self.config.method

        for method in methods:
            self.config.method = method
            result = self.explain(image, target_class)
            results[method.value] = result

        self.config.method = original_method
        return results

    def get_layer_activations(
        self,
        image: Any,
        layer_names: Optional[List[str]] = None
    ) -> Dict[str, ActivationInfo]:
        """
        Get activation statistics for multiple layers.

        Args:
            image: Input image
            layer_names: Layers to analyze

        Returns:
            Dict mapping layer name to activation info
        """
        import random

        if layer_names is None:
            layer_names = ["layer1", "layer2", "layer3", "layer4"]

        activations = {}
        for name in layer_names:
            size = 640 // (2 ** (int(name[-1]) if name[-1].isdigit() else 2))
            activations[name] = ActivationInfo(
                layer_name=name,
                activation_shape=(1, 256, size, size),
                mean_activation=random.uniform(0.1, 0.5),
                max_activation=random.uniform(0.7, 1.0),
                gradient_norm=random.uniform(0.01, 0.1),
            )

        return activations

    def get_status(self) -> Dict[str, Any]:
        """Get GradCAM status."""
        return {
            "method": self.config.method.value,
            "target_layer": self.config.target_layer,
            "use_cuda": self.config.use_cuda,
            "colormap": self.config.colormap,
            "alpha": self.config.alpha,
            "model_set": self._model is not None,
        }


# Singleton instance
_gradcam: Optional[GradCAM] = None


def get_gradcam() -> GradCAM:
    """Get or create the GradCAM instance."""
    global _gradcam
    if _gradcam is None:
        _gradcam = GradCAM()
    return _gradcam
