"""
Attention Visualization for Vision-Based Quality Inspection.

This module implements attention visualization for:
- Grad-CAM for CNN-based defect detection
- Attention Rollout for Vision Transformers
- Feature map extraction and visualization
- Saliency maps for defect localization

Research Contributions:
- Novel attention visualization for manufacturing defects
- Multi-scale defect attention aggregation
- Real-time attention overlay for HMI systems

References:
- Selvaraju, R.R., et al. (2017). Grad-CAM: Visual Explanations from Deep Networks
- Abnar, S., & Zuidema, W. (2020). Quantifying Attention Flow in Transformers
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class VisualizationType(Enum):
    """Types of attention visualization."""
    GRAD_CAM = "grad_cam"
    GRAD_CAM_PP = "grad_cam_pp"  # Grad-CAM++
    SCORE_CAM = "score_cam"
    ATTENTION_ROLLOUT = "attention_rollout"
    ATTENTION_FLOW = "attention_flow"
    SALIENCY = "saliency"
    INTEGRATED_GRADIENTS = "integrated_gradients"


class AggregationMethod(Enum):
    """Methods for aggregating attention across layers."""
    MEAN = "mean"
    MAX = "max"
    MIN = "min"
    PRODUCT = "product"  # For attention rollout
    WEIGHTED = "weighted"


@dataclass
class AttentionConfig:
    """Configuration for attention visualization."""
    visualization_type: VisualizationType = VisualizationType.GRAD_CAM
    target_layers: List[str] = field(default_factory=list)
    aggregation: AggregationMethod = AggregationMethod.MEAN
    smooth_grad: bool = False
    smooth_samples: int = 20
    smooth_sigma: float = 0.1
    normalize: bool = True
    colormap: str = "jet"  # Colormap for heatmap
    overlay_alpha: float = 0.5


@dataclass
class AttentionMap:
    """Attention map for a single image."""
    image_id: str
    attention: np.ndarray  # (H, W) attention map
    class_idx: Optional[int]  # Target class
    class_name: Optional[str]
    score: float  # Model confidence
    layer_name: str
    visualization_type: VisualizationType
    bounding_boxes: List[Dict]  # Detected defect regions
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def shape(self) -> Tuple[int, int]:
        return self.attention.shape

    def get_top_attention_regions(
        self,
        threshold: float = 0.5,
        min_area: int = 100
    ) -> List[Dict]:
        """Get regions with high attention."""
        # Threshold attention map
        binary = self.attention > threshold

        # Find connected components (simplified)
        regions = self._find_regions(binary, min_area)

        return regions

    def _find_regions(
        self,
        binary: np.ndarray,
        min_area: int
    ) -> List[Dict]:
        """Find connected regions in binary attention map."""
        # Simplified region detection
        regions = []

        # Find bounding box of all high-attention pixels
        rows = np.any(binary, axis=1)
        cols = np.any(binary, axis=0)

        if rows.any() and cols.any():
            y_min, y_max = np.where(rows)[0][[0, -1]]
            x_min, x_max = np.where(cols)[0][[0, -1]]

            area = (y_max - y_min) * (x_max - x_min)
            if area >= min_area:
                regions.append({
                    'x_min': int(x_min),
                    'y_min': int(y_min),
                    'x_max': int(x_max),
                    'y_max': int(y_max),
                    'area': int(area),
                    'mean_attention': float(np.mean(self.attention[y_min:y_max, x_min:x_max]))
                })

        return regions

    def to_dict(self) -> Dict:
        return {
            'image_id': self.image_id,
            'attention_shape': list(self.attention.shape),
            'attention_stats': {
                'min': float(np.min(self.attention)),
                'max': float(np.max(self.attention)),
                'mean': float(np.mean(self.attention)),
                'std': float(np.std(self.attention))
            },
            'class_idx': self.class_idx,
            'class_name': self.class_name,
            'score': float(self.score),
            'layer_name': self.layer_name,
            'visualization_type': self.visualization_type.value,
            'bounding_boxes': self.bounding_boxes,
            'timestamp': self.timestamp.isoformat()
        }


class GradCAM:
    """
    Grad-CAM: Gradient-weighted Class Activation Mapping.

    Generates visual explanations for CNN predictions by
    using gradients flowing into the final convolutional layer.
    """

    def __init__(self, config: Optional[AttentionConfig] = None):
        self.config = config or AttentionConfig()
        self.config.visualization_type = VisualizationType.GRAD_CAM
        self.model = None
        self.feature_maps: Dict[str, np.ndarray] = {}
        self.gradients: Dict[str, np.ndarray] = {}

    def set_model(self, model: Any, target_layers: List[str]):
        """
        Set the model and target layers for Grad-CAM.

        Args:
            model: Trained CNN model
            target_layers: Layer names to compute Grad-CAM
        """
        self.model = model
        self.config.target_layers = target_layers

        # In real implementation, register hooks for feature maps and gradients
        logger.info(f"Grad-CAM configured for layers: {target_layers}")

    def compute(
        self,
        images: np.ndarray,
        target_class: Optional[int] = None,
        image_ids: Optional[List[str]] = None
    ) -> List[AttentionMap]:
        """
        Compute Grad-CAM attention maps.

        Args:
            images: Input images (N, H, W, C) or (N, C, H, W)
            target_class: Target class for Grad-CAM (None = predicted class)
            image_ids: Optional image identifiers

        Returns:
            List of attention maps
        """
        if images.ndim == 3:
            images = images[np.newaxis, ...]

        n_images = len(images)
        if image_ids is None:
            image_ids = [f"image_{i}" for i in range(n_images)]

        attention_maps = []

        for i in range(n_images):
            image = images[i]

            # Get model prediction
            pred_class, pred_score = self._get_prediction(image, target_class)

            # Compute Grad-CAM for each target layer
            for layer_name in self.config.target_layers:
                cam = self._compute_gradcam(image, pred_class, layer_name)

                # Resize to input size
                if image.shape[0] in [1, 3]:  # CHW format
                    target_size = (image.shape[1], image.shape[2])
                else:  # HWC format
                    target_size = (image.shape[0], image.shape[1])

                cam_resized = self._resize_cam(cam, target_size)

                # Normalize
                if self.config.normalize:
                    cam_resized = self._normalize(cam_resized)

                # Detect defect regions
                bboxes = self._detect_defect_regions(cam_resized)

                attention_map = AttentionMap(
                    image_id=image_ids[i],
                    attention=cam_resized,
                    class_idx=pred_class,
                    class_name=f"class_{pred_class}",
                    score=pred_score,
                    layer_name=layer_name,
                    visualization_type=VisualizationType.GRAD_CAM,
                    bounding_boxes=bboxes
                )
                attention_maps.append(attention_map)

        return attention_maps

    def _get_prediction(
        self,
        image: np.ndarray,
        target_class: Optional[int]
    ) -> Tuple[int, float]:
        """Get model prediction for image."""
        # Simulate prediction
        # Real implementation would run inference
        pred_class = target_class if target_class is not None else 0
        pred_score = 0.95

        return pred_class, pred_score

    def _compute_gradcam(
        self,
        image: np.ndarray,
        target_class: int,
        layer_name: str
    ) -> np.ndarray:
        """Compute Grad-CAM for a single image and layer."""
        # Simulated Grad-CAM computation
        # Real implementation would:
        # 1. Forward pass to get feature maps
        # 2. Backward pass to get gradients
        # 3. Global average pool gradients
        # 4. Weight feature maps by gradients
        # 5. ReLU to get positive contributions

        # Simulate feature map size (typically smaller than input)
        if image.shape[0] in [1, 3]:  # CHW
            h, w = image.shape[1] // 8, image.shape[2] // 8
        else:  # HWC
            h, w = image.shape[0] // 8, image.shape[1] // 8

        # Generate simulated Grad-CAM
        # In practice, this comes from gradient computation
        cam = np.random.rand(h, w)

        # Apply ReLU
        cam = np.maximum(cam, 0)

        return cam

    def _resize_cam(
        self,
        cam: np.ndarray,
        target_size: Tuple[int, int]
    ) -> np.ndarray:
        """Resize CAM to target size using bilinear interpolation."""
        from_h, from_w = cam.shape
        to_h, to_w = target_size

        # Simple bilinear interpolation
        y_indices = np.linspace(0, from_h - 1, to_h)
        x_indices = np.linspace(0, from_w - 1, to_w)

        resized = np.zeros((to_h, to_w))

        for i, y in enumerate(y_indices):
            for j, x in enumerate(x_indices):
                y0, y1 = int(np.floor(y)), int(np.ceil(y))
                x0, x1 = int(np.floor(x)), int(np.ceil(x))

                y0, y1 = min(y0, from_h - 1), min(y1, from_h - 1)
                x0, x1 = min(x0, from_w - 1), min(x1, from_w - 1)

                fy, fx = y - y0, x - x0

                resized[i, j] = (
                    cam[y0, x0] * (1 - fy) * (1 - fx) +
                    cam[y1, x0] * fy * (1 - fx) +
                    cam[y0, x1] * (1 - fy) * fx +
                    cam[y1, x1] * fy * fx
                )

        return resized

    def _normalize(self, cam: np.ndarray) -> np.ndarray:
        """Normalize CAM to [0, 1] range."""
        cam_min, cam_max = cam.min(), cam.max()
        if cam_max - cam_min > 0:
            return (cam - cam_min) / (cam_max - cam_min)
        return cam

    def _detect_defect_regions(
        self,
        cam: np.ndarray,
        threshold: float = 0.6
    ) -> List[Dict]:
        """Detect potential defect regions from attention map."""
        binary = cam > threshold

        regions = []
        rows = np.any(binary, axis=1)
        cols = np.any(binary, axis=0)

        if rows.any() and cols.any():
            y_min, y_max = np.where(rows)[0][[0, -1]]
            x_min, x_max = np.where(cols)[0][[0, -1]]

            regions.append({
                'x_min': int(x_min),
                'y_min': int(y_min),
                'x_max': int(x_max),
                'y_max': int(y_max),
                'confidence': float(np.mean(cam[y_min:y_max+1, x_min:x_max+1])),
                'defect_type': 'high_attention_region'
            })

        return regions


class AttentionRollout:
    """
    Attention Rollout for Vision Transformers.

    Aggregates attention across all layers to visualize
    which input patches contribute to the final prediction.
    """

    def __init__(self, config: Optional[AttentionConfig] = None):
        self.config = config or AttentionConfig()
        self.config.visualization_type = VisualizationType.ATTENTION_ROLLOUT
        self.config.aggregation = AggregationMethod.PRODUCT
        self.model = None
        self.attention_weights: List[np.ndarray] = []

    def set_model(self, model: Any):
        """Set the Vision Transformer model."""
        self.model = model
        logger.info("Attention Rollout configured for Vision Transformer")

    def compute(
        self,
        images: np.ndarray,
        image_ids: Optional[List[str]] = None,
        discard_ratio: float = 0.1
    ) -> List[AttentionMap]:
        """
        Compute Attention Rollout.

        Args:
            images: Input images
            image_ids: Optional identifiers
            discard_ratio: Ratio of lowest attention to discard

        Returns:
            List of attention maps
        """
        if images.ndim == 3:
            images = images[np.newaxis, ...]

        n_images = len(images)
        if image_ids is None:
            image_ids = [f"image_{i}" for i in range(n_images)]

        attention_maps = []

        for i in range(n_images):
            image = images[i]

            # Get attention weights from all layers
            layer_attentions = self._get_attention_weights(image)

            # Compute rollout
            rollout = self._compute_rollout(layer_attentions, discard_ratio)

            # Reshape to 2D
            if image.shape[0] in [1, 3]:
                h, w = image.shape[1], image.shape[2]
            else:
                h, w = image.shape[0], image.shape[1]

            # Assume square patches
            patch_size = 16
            grid_size = h // patch_size

            # Reshape rollout to grid (excluding CLS token)
            if len(rollout) > 1:
                attention_2d = rollout[1:].reshape(grid_size, grid_size)
            else:
                attention_2d = rollout.reshape(int(np.sqrt(len(rollout))), -1)

            # Resize to original size
            attention_resized = self._resize_attention(attention_2d, (h, w))

            if self.config.normalize:
                attention_resized = self._normalize(attention_resized)

            attention_map = AttentionMap(
                image_id=image_ids[i],
                attention=attention_resized,
                class_idx=None,
                class_name=None,
                score=1.0,
                layer_name="all_layers",
                visualization_type=VisualizationType.ATTENTION_ROLLOUT,
                bounding_boxes=[]
            )
            attention_maps.append(attention_map)

        return attention_maps

    def _get_attention_weights(self, image: np.ndarray) -> List[np.ndarray]:
        """Get attention weights from all transformer layers."""
        # Simulate attention weights
        # Real implementation would extract from transformer

        n_layers = 12  # Typical ViT depth
        n_heads = 12
        n_patches = 197  # 14x14 patches + CLS token

        layer_attentions = []
        for _ in range(n_layers):
            # Simulate multi-head attention
            attention = np.random.rand(n_heads, n_patches, n_patches)
            # Softmax normalization
            attention = attention / attention.sum(axis=-1, keepdims=True)
            layer_attentions.append(attention)

        return layer_attentions

    def _compute_rollout(
        self,
        layer_attentions: List[np.ndarray],
        discard_ratio: float
    ) -> np.ndarray:
        """Compute attention rollout across layers."""
        n_layers = len(layer_attentions)

        # Average attention across heads
        averaged = [att.mean(axis=0) for att in layer_attentions]

        # Add identity (residual connections)
        n_tokens = averaged[0].shape[0]
        eye = np.eye(n_tokens)
        averaged = [0.5 * a + 0.5 * eye for a in averaged]

        # Renormalize
        averaged = [a / a.sum(axis=-1, keepdims=True) for a in averaged]

        # Rollout: multiply attention matrices
        rollout = averaged[0]
        for attention in averaged[1:]:
            rollout = attention @ rollout

        # Discard low attention
        if discard_ratio > 0:
            flat = rollout.flatten()
            threshold = np.percentile(flat, discard_ratio * 100)
            rollout[rollout < threshold] = 0

        # Get attention from CLS token to patches
        cls_attention = rollout[0, 1:]

        return cls_attention

    def _resize_attention(
        self,
        attention: np.ndarray,
        target_size: Tuple[int, int]
    ) -> np.ndarray:
        """Resize attention to target size."""
        from_h, from_w = attention.shape
        to_h, to_w = target_size

        y_indices = np.linspace(0, from_h - 1, to_h)
        x_indices = np.linspace(0, from_w - 1, to_w)

        resized = np.zeros((to_h, to_w))

        for i, y in enumerate(y_indices):
            for j, x in enumerate(x_indices):
                y0, y1 = int(np.floor(y)), min(int(np.ceil(y)), from_h - 1)
                x0, x1 = int(np.floor(x)), min(int(np.ceil(x)), from_w - 1)
                fy, fx = y - y0, x - x0
                resized[i, j] = (
                    attention[y0, x0] * (1 - fy) * (1 - fx) +
                    attention[y1, x0] * fy * (1 - fx) +
                    attention[y0, x1] * (1 - fy) * fx +
                    attention[y1, x1] * fy * fx
                )

        return resized

    def _normalize(self, attention: np.ndarray) -> np.ndarray:
        """Normalize attention to [0, 1]."""
        att_min, att_max = attention.min(), attention.max()
        if att_max - att_min > 0:
            return (attention - att_min) / (att_max - att_min)
        return attention


class FeatureMapExtractor:
    """Extract and visualize intermediate feature maps."""

    def __init__(self):
        self.model = None
        self.target_layers: List[str] = []
        self.feature_maps: Dict[str, np.ndarray] = {}

    def set_model(self, model: Any, target_layers: List[str]):
        """Set model and target layers."""
        self.model = model
        self.target_layers = target_layers

    def extract(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Extract feature maps for image."""
        # Simulate feature extraction
        feature_maps = {}

        for layer_name in self.target_layers:
            # Simulate different sized feature maps
            if 'conv1' in layer_name:
                h, w = 112, 112
                channels = 64
            elif 'conv2' in layer_name:
                h, w = 56, 56
                channels = 128
            elif 'conv3' in layer_name:
                h, w = 28, 28
                channels = 256
            else:
                h, w = 14, 14
                channels = 512

            feature_maps[layer_name] = np.random.rand(channels, h, w)

        return feature_maps

    def visualize_channel(
        self,
        feature_map: np.ndarray,
        channel_idx: int
    ) -> np.ndarray:
        """Visualize a single channel."""
        channel = feature_map[channel_idx]
        # Normalize
        channel = (channel - channel.min()) / (channel.max() - channel.min() + 1e-8)
        return channel

    def get_channel_statistics(
        self,
        feature_maps: Dict[str, np.ndarray]
    ) -> Dict[str, Dict]:
        """Compute statistics for each feature map."""
        stats = {}

        for layer_name, fmap in feature_maps.items():
            n_channels = fmap.shape[0]
            channel_means = fmap.mean(axis=(1, 2))
            channel_stds = fmap.std(axis=(1, 2))

            # Find most active channels
            sorted_indices = np.argsort(channel_means)[::-1]

            stats[layer_name] = {
                'shape': list(fmap.shape),
                'n_channels': n_channels,
                'mean_activation': float(fmap.mean()),
                'std_activation': float(fmap.std()),
                'sparsity': float(np.mean(fmap == 0)),
                'top_active_channels': sorted_indices[:10].tolist(),
                'channel_means': channel_means.tolist(),
                'channel_stds': channel_stds.tolist()
            }

        return stats


class VisionExplainer:
    """
    Unified vision explainability for manufacturing defect detection.

    Combines multiple visualization techniques for
    comprehensive visual explanations.
    """

    def __init__(self, config: Optional[AttentionConfig] = None):
        self.config = config or AttentionConfig()
        self.grad_cam = GradCAM(config)
        self.attention_rollout = AttentionRollout(config)
        self.feature_extractor = FeatureMapExtractor()

        self.defect_classes: List[str] = []
        self.severity_thresholds: Dict[str, float] = {}

    def set_manufacturing_context(
        self,
        defect_classes: List[str],
        severity_thresholds: Dict[str, float]
    ):
        """Set manufacturing defect context."""
        self.defect_classes = defect_classes
        self.severity_thresholds = severity_thresholds

    def explain_defect_detection(
        self,
        image: np.ndarray,
        cnn_model: Any,
        target_layers: List[str],
        image_id: str = "defect_image"
    ) -> Dict:
        """
        Generate comprehensive visual explanation for defect detection.

        Returns multi-method explanation with defect localization.
        """
        # Set up Grad-CAM
        self.grad_cam.set_model(cnn_model, target_layers)

        # Compute Grad-CAM attention maps
        grad_cam_maps = self.grad_cam.compute(
            image[np.newaxis, ...],
            image_ids=[image_id]
        )

        # Extract feature maps
        self.feature_extractor.set_model(cnn_model, target_layers)
        feature_maps = self.feature_extractor.extract(image)
        feature_stats = self.feature_extractor.get_channel_statistics(feature_maps)

        # Aggregate defect regions across visualizations
        defect_regions = self._aggregate_defect_regions(grad_cam_maps)

        # Assess defect severity
        severity_assessment = self._assess_defect_severity(defect_regions, grad_cam_maps)

        return {
            'image_id': image_id,
            'grad_cam': [m.to_dict() for m in grad_cam_maps],
            'feature_statistics': feature_stats,
            'defect_regions': defect_regions,
            'severity_assessment': severity_assessment,
            'recommendations': self._generate_quality_recommendations(severity_assessment)
        }

    def _aggregate_defect_regions(
        self,
        attention_maps: List[AttentionMap]
    ) -> List[Dict]:
        """Aggregate defect regions from multiple attention maps."""
        all_regions = []

        for att_map in attention_maps:
            for bbox in att_map.bounding_boxes:
                region = bbox.copy()
                region['source'] = att_map.layer_name
                region['visualization_type'] = att_map.visualization_type.value
                all_regions.append(region)

        # Merge overlapping regions
        merged = self._merge_overlapping_regions(all_regions)

        return merged

    def _merge_overlapping_regions(
        self,
        regions: List[Dict],
        iou_threshold: float = 0.5
    ) -> List[Dict]:
        """Merge overlapping bounding boxes."""
        if not regions:
            return []

        # Sort by confidence
        regions = sorted(regions, key=lambda x: x.get('confidence', 0), reverse=True)

        merged = []
        used = set()

        for i, r1 in enumerate(regions):
            if i in used:
                continue

            # Find overlapping regions
            group = [r1]
            for j, r2 in enumerate(regions[i+1:], start=i+1):
                if j in used:
                    continue

                iou = self._compute_iou(r1, r2)
                if iou > iou_threshold:
                    group.append(r2)
                    used.add(j)

            # Merge group
            merged_region = {
                'x_min': min(r['x_min'] for r in group),
                'y_min': min(r['y_min'] for r in group),
                'x_max': max(r['x_max'] for r in group),
                'y_max': max(r['y_max'] for r in group),
                'confidence': max(r.get('confidence', 0) for r in group),
                'sources': list(set(r.get('source', 'unknown') for r in group)),
                'n_detections': len(group)
            }
            merged.append(merged_region)
            used.add(i)

        return merged

    def _compute_iou(self, r1: Dict, r2: Dict) -> float:
        """Compute Intersection over Union."""
        x1 = max(r1['x_min'], r2['x_min'])
        y1 = max(r1['y_min'], r2['y_min'])
        x2 = min(r1['x_max'], r2['x_max'])
        y2 = min(r1['y_max'], r2['y_max'])

        if x2 < x1 or y2 < y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)

        area1 = (r1['x_max'] - r1['x_min']) * (r1['y_max'] - r1['y_min'])
        area2 = (r2['x_max'] - r2['x_min']) * (r2['y_max'] - r2['y_min'])

        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def _assess_defect_severity(
        self,
        regions: List[Dict],
        attention_maps: List[AttentionMap]
    ) -> Dict:
        """Assess overall defect severity."""
        if not regions:
            return {
                'severity': 'none',
                'score': 0.0,
                'n_defect_regions': 0,
                'total_defect_area': 0,
                'max_confidence': 0.0
            }

        # Calculate metrics
        total_area = sum(
            (r['x_max'] - r['x_min']) * (r['y_max'] - r['y_min'])
            for r in regions
        )
        max_confidence = max(r.get('confidence', 0) for r in regions)
        n_regions = len(regions)

        # Determine severity level
        if max_confidence > 0.9 or n_regions > 3:
            severity = 'critical'
            score = 1.0
        elif max_confidence > 0.7 or n_regions > 1:
            severity = 'major'
            score = 0.7
        elif max_confidence > 0.5:
            severity = 'minor'
            score = 0.4
        else:
            severity = 'cosmetic'
            score = 0.2

        return {
            'severity': severity,
            'score': score,
            'n_defect_regions': n_regions,
            'total_defect_area': total_area,
            'max_confidence': float(max_confidence)
        }

    def _generate_quality_recommendations(
        self,
        severity: Dict
    ) -> List[str]:
        """Generate quality recommendations based on defect severity."""
        recommendations = []

        if severity['severity'] == 'critical':
            recommendations.extend([
                "REJECT: Critical defects detected - part fails quality inspection",
                "Document defect locations for root cause analysis",
                "Review process parameters for anomalies",
                "Consider production line inspection"
            ])
        elif severity['severity'] == 'major':
            recommendations.extend([
                "HOLD: Major defects detected - requires engineering review",
                "Mark affected areas for potential rework",
                "Compare with tolerance specifications"
            ])
        elif severity['severity'] == 'minor':
            recommendations.extend([
                "CONDITIONAL: Minor defects detected - may be acceptable",
                "Verify against customer specifications",
                "Document for quality trending"
            ])
        elif severity['severity'] == 'cosmetic':
            recommendations.extend([
                "ACCEPT with notes: Cosmetic issues only",
                "Log for process improvement opportunities"
            ])
        else:
            recommendations.append("ACCEPT: No significant defects detected")

        return recommendations


# Alias for backward compatibility
AttentionVisualizer = VisionExplainer
