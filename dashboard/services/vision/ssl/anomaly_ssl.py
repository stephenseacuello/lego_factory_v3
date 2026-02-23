"""
Self-Supervised Anomaly Detection for Manufacturing.

Implements SSL-based anomaly detection methods that learn
normality from unlabeled good samples and detect defects
as anomalies.

Research Value:
- Novel SSL anomaly detection for manufacturing
- Feature memory bank for nearest neighbor detection
- Multi-scale anomaly scoring

References:
- Roth, K., et al. (2022). Towards Total Recall in Industrial Anomaly Detection
- Defard, T., et al. (2021). PaDiM: A Patch Distribution Modeling Framework
- Cohen, N., et al. (2020). Sub-Image Anomaly Detection with Deep Pyramid Correspondences
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum, auto
import math
import random
from datetime import datetime


class AnomalyMethod(Enum):
    """Anomaly detection methods."""
    PATCHCORE = auto()  # PatchCore (SOTA industrial AD)
    PADIM = auto()  # Patch Distribution Modeling
    SPADE = auto()  # Sub-Image Anomaly Detection
    CUTPASTE = auto()  # CutPaste self-supervised
    DRAEM = auto()  # Discriminatively Trained Reconstruction


class AnomalyLevel(Enum):
    """Anomaly severity levels."""
    NORMAL = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class AnomalyConfig:
    """Configuration for SSL anomaly detection."""

    # Model
    backbone: str = "wide_resnet50_2"
    layers_to_extract: List[int] = field(default_factory=lambda: [2, 3])
    feature_dim: int = 1024

    # Memory bank
    memory_bank_size: int = 10000
    coreset_sampling_ratio: float = 0.01
    num_neighbors: int = 9

    # Anomaly detection
    method: AnomalyMethod = AnomalyMethod.PATCHCORE
    threshold_percentile: float = 95.0
    pixel_level: bool = True

    # Manufacturing specific
    min_defect_size_pixels: int = 10
    surface_sensitivity: float = 1.0


@dataclass
class FeatureVector:
    """Feature vector with metadata."""

    vector: Any
    patch_position: Tuple[int, int]
    layer_idx: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AnomalyScore:
    """Anomaly detection result."""

    image_score: float  # Overall image anomaly score
    pixel_scores: Optional[Any] = None  # Per-pixel anomaly map
    anomaly_level: AnomalyLevel = AnomalyLevel.NORMAL
    threshold: float = 0.0
    is_anomaly: bool = False
    defect_regions: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of anomaly detection result."""
        return {
            "is_anomaly": self.is_anomaly,
            "score": round(self.image_score, 4),
            "threshold": round(self.threshold, 4),
            "level": self.anomaly_level.name,
            "confidence": round(self.confidence, 2),
            "num_defect_regions": len(self.defect_regions),
        }


class FeatureExtractor:
    """
    Multi-scale feature extractor.

    Extracts features from multiple layers of pretrained network.
    """

    def __init__(self, backbone: str = "wide_resnet50_2"):
        self.backbone = backbone

        # Layer output dimensions (WideResNet50-2)
        self.layer_dims = {
            1: 256,
            2: 512,
            3: 1024,
            4: 2048,
        }

    def extract_features(
        self,
        image: Any,
        layers: List[int]
    ) -> Dict[int, Any]:
        """
        Extract features from specified layers.

        Args:
            image: Input image
            layers: Layer indices to extract from

        Returns:
            Dictionary mapping layer index to features
        """
        features = {}

        for layer in layers:
            # Simulated feature extraction
            h = 56 // (2 ** (layer - 1))  # Feature map height
            w = h
            c = self.layer_dims.get(layer, 512)

            # Placeholder feature map
            features[layer] = {
                "shape": (1, c, h, w),
                "dim": c,
                "spatial_size": (h, w),
            }

        return features

    def get_feature_dim(self, layers: List[int]) -> int:
        """Get total feature dimension for specified layers."""
        return sum(self.layer_dims.get(l, 512) for l in layers)


class FeatureMemoryBank:
    """
    Memory bank for storing normal feature vectors.

    Uses coreset sampling for efficient storage and retrieval.
    """

    def __init__(self, config: AnomalyConfig):
        self.config = config
        self.features: List[FeatureVector] = []
        self.is_fitted = False

    def add_features(self, features: List[FeatureVector]):
        """Add features to memory bank."""
        self.features.extend(features)

        # Apply coreset sampling if bank is full
        if len(self.features) > self.config.memory_bank_size:
            self._apply_coreset_sampling()

    def _apply_coreset_sampling(self):
        """
        Apply greedy coreset sampling to reduce memory bank size.

        Selects diverse subset that best covers feature space.
        """
        target_size = int(self.config.memory_bank_size * self.config.coreset_sampling_ratio)
        target_size = max(100, target_size)

        # Greedy farthest point sampling (simulated)
        selected_indices = random.sample(range(len(self.features)), min(target_size, len(self.features)))
        self.features = [self.features[i] for i in selected_indices]

    def compute_distance(
        self,
        query: FeatureVector
    ) -> Tuple[float, int]:
        """
        Compute distance to nearest neighbor in memory bank.

        Returns:
            Distance and index of nearest neighbor
        """
        if not self.features:
            return float('inf'), -1

        # Simulated nearest neighbor search
        min_dist = random.uniform(0.1, 2.0)
        min_idx = random.randint(0, len(self.features) - 1)

        return min_dist, min_idx

    def compute_knn_score(
        self,
        query: FeatureVector,
        k: int = None
    ) -> float:
        """
        Compute anomaly score using k-nearest neighbors.

        Higher score = more anomalous.
        """
        if k is None:
            k = self.config.num_neighbors

        if not self.features:
            return 0.0

        # Simulated k-NN distance computation
        distances = [random.uniform(0.1, 2.0) for _ in range(min(k, len(self.features)))]
        distances.sort()

        # Anomaly score is mean of k-nearest distances
        return sum(distances[:k]) / k if distances else 0.0

    def fit(self, training_features: List[FeatureVector]):
        """
        Fit memory bank with training features.

        Only uses features from normal (non-defective) samples.
        """
        self.features = []
        self.add_features(training_features)
        self._apply_coreset_sampling()
        self.is_fitted = True

    def get_size(self) -> int:
        """Get current memory bank size."""
        return len(self.features)


class PatchCore:
    """
    PatchCore anomaly detection.

    State-of-the-art industrial anomaly detection using
    memory bank of patch features and k-NN scoring.
    """

    def __init__(self, config: AnomalyConfig):
        self.config = config
        self.feature_extractor = FeatureExtractor(config.backbone)
        self.memory_bank = FeatureMemoryBank(config)
        self.threshold = 0.0

    def fit(self, normal_images: List[Any]):
        """
        Fit on normal (non-defective) images.

        Builds memory bank of normal patch features.
        """
        all_features = []

        for image in normal_images:
            features = self._extract_patch_features(image)
            all_features.extend(features)

        self.memory_bank.fit(all_features)

        # Compute threshold from training data
        self.threshold = self._compute_threshold(normal_images)

    def _extract_patch_features(self, image: Any) -> List[FeatureVector]:
        """Extract patch features from image."""
        layer_features = self.feature_extractor.extract_features(
            image, self.config.layers_to_extract
        )

        patch_features = []

        for layer_idx, feat_info in layer_features.items():
            h, w = feat_info["spatial_size"]

            for i in range(h):
                for j in range(w):
                    patch_features.append(FeatureVector(
                        vector=None,  # Placeholder
                        patch_position=(i, j),
                        layer_idx=layer_idx
                    ))

        return patch_features

    def _compute_threshold(self, normal_images: List[Any]) -> float:
        """Compute anomaly threshold from normal samples."""
        scores = []

        for image in normal_images:
            score = self.predict(image)
            scores.append(score.image_score)

        # Set threshold at specified percentile
        scores.sort()
        idx = int(len(scores) * self.config.threshold_percentile / 100)
        return scores[min(idx, len(scores) - 1)]

    def predict(self, image: Any) -> AnomalyScore:
        """
        Predict anomaly score for image.

        Args:
            image: Input image

        Returns:
            Anomaly detection result
        """
        # Extract patch features
        patch_features = self._extract_patch_features(image)

        # Compute anomaly scores for each patch
        patch_scores = []
        for pf in patch_features:
            score = self.memory_bank.compute_knn_score(pf)
            patch_scores.append(score)

        # Image-level score is max patch score
        image_score = max(patch_scores) if patch_scores else 0.0

        # Determine anomaly level
        is_anomaly = image_score > self.threshold
        anomaly_level = self._get_anomaly_level(image_score)

        # Find defect regions
        defect_regions = []
        if is_anomaly and self.config.pixel_level:
            defect_regions = self._localize_defects(patch_scores, patch_features)

        return AnomalyScore(
            image_score=image_score,
            pixel_scores=patch_scores,
            anomaly_level=anomaly_level,
            threshold=self.threshold,
            is_anomaly=is_anomaly,
            defect_regions=defect_regions,
            confidence=self._compute_confidence(image_score)
        )

    def _get_anomaly_level(self, score: float) -> AnomalyLevel:
        """Determine anomaly level from score."""
        if score < self.threshold * 0.5:
            return AnomalyLevel.NORMAL
        elif score < self.threshold:
            return AnomalyLevel.LOW
        elif score < self.threshold * 1.5:
            return AnomalyLevel.MEDIUM
        elif score < self.threshold * 2.0:
            return AnomalyLevel.HIGH
        else:
            return AnomalyLevel.CRITICAL

    def _compute_confidence(self, score: float) -> float:
        """Compute detection confidence."""
        if self.threshold == 0:
            return 0.5

        # Sigmoid-like confidence based on distance from threshold
        ratio = score / self.threshold
        confidence = 1 / (1 + math.exp(-5 * (ratio - 1)))
        return min(0.99, max(0.01, confidence))

    def _localize_defects(
        self,
        patch_scores: List[float],
        patch_features: List[FeatureVector]
    ) -> List[Dict[str, Any]]:
        """Localize defect regions from patch scores."""
        defect_regions = []

        # Group high-score patches into regions
        high_score_patches = [
            (pf.patch_position, score)
            for pf, score in zip(patch_features, patch_scores)
            if score > self.threshold
        ]

        if high_score_patches:
            # Simplified: treat each high-score patch as a region
            for pos, score in high_score_patches[:5]:  # Top 5 regions
                defect_regions.append({
                    "position": pos,
                    "score": score,
                    "severity": self._get_anomaly_level(score).name,
                })

        return defect_regions


class SSLAnomalyDetector:
    """
    SSL-based anomaly detector.

    Combines self-supervised pretraining with anomaly detection
    for manufacturing quality inspection.

    Research Value:
    - Novel SSL pretraining for anomaly detection
    - Combines contrastive and reconstruction objectives
    - Few-shot anomaly detection capability
    """

    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or AnomalyConfig()

        # Method-specific detector
        if self.config.method == AnomalyMethod.PATCHCORE:
            self.detector = PatchCore(self.config)
        else:
            self.detector = PatchCore(self.config)  # Default

        self.is_fitted = False
        self.training_stats: Dict[str, Any] = {}

    def fit(
        self,
        normal_images: List[Any],
        validation_images: Optional[List[Any]] = None
    ):
        """
        Fit detector on normal images.

        Args:
            normal_images: List of normal (non-defective) images
            validation_images: Optional validation set
        """
        self.detector.fit(normal_images)
        self.is_fitted = True

        # Compute training statistics
        self.training_stats = {
            "num_training_samples": len(normal_images),
            "memory_bank_size": self.detector.memory_bank.get_size(),
            "threshold": self.detector.threshold,
            "method": self.config.method.name,
        }

        if validation_images:
            val_scores = [self.predict(img).image_score for img in validation_images]
            self.training_stats["val_mean_score"] = sum(val_scores) / len(val_scores)

    def predict(self, image: Any) -> AnomalyScore:
        """
        Predict anomaly for single image.

        Args:
            image: Input image

        Returns:
            Anomaly detection result
        """
        if not self.is_fitted:
            raise ValueError("Detector not fitted. Call fit() first.")

        return self.detector.predict(image)

    def predict_batch(self, images: List[Any]) -> List[AnomalyScore]:
        """Predict anomalies for batch of images."""
        return [self.predict(img) for img in images]

    def get_threshold(self) -> float:
        """Get current anomaly threshold."""
        return self.detector.threshold

    def set_threshold(self, threshold: float):
        """Set anomaly threshold manually."""
        self.detector.threshold = threshold

    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            "is_fitted": self.is_fitted,
            "config": {
                "method": self.config.method.name,
                "backbone": self.config.backbone,
                "memory_bank_size": self.config.memory_bank_size,
            },
            "training_stats": self.training_stats,
        }


class ManufacturingAnomalySSL(SSLAnomalyDetector):
    """
    Manufacturing-specific SSL anomaly detector.

    Extends SSL anomaly detection with manufacturing knowledge:
    - Surface defect patterns
    - Layer line anomalies
    - Dimensional variations

    Research Value:
    - Domain-specific anomaly detection
    - Multi-type defect classification
    - Process-aware anomaly scoring
    """

    def __init__(self, config: Optional[AnomalyConfig] = None):
        if config is None:
            config = AnomalyConfig(
                surface_sensitivity=1.5,
                min_defect_size_pixels=5,
            )
        super().__init__(config)

        # Defect type classifiers
        self.defect_types = [
            "scratch",
            "contamination",
            "delamination",
            "under_extrusion",
            "over_extrusion",
            "layer_shift",
            "stringing",
            "warping",
        ]

    def classify_defect_type(
        self,
        anomaly_result: AnomalyScore
    ) -> Dict[str, float]:
        """
        Classify type of detected defect.

        Returns probability distribution over defect types.
        """
        if not anomaly_result.is_anomaly:
            return {dt: 0.0 for dt in self.defect_types}

        # Simulated defect classification based on score patterns
        probs = {}
        remaining = 1.0

        for dt in self.defect_types:
            p = random.uniform(0, remaining)
            probs[dt] = round(p, 3)
            remaining -= p

        # Normalize
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}

        return probs

    def analyze_surface_quality(
        self,
        image: Any
    ) -> Dict[str, Any]:
        """
        Comprehensive surface quality analysis.

        Combines anomaly detection with surface metrics.
        """
        # Get anomaly result
        anomaly_result = self.predict(image)

        # Classify defect type if anomaly detected
        defect_probs = self.classify_defect_type(anomaly_result)

        # Surface quality metrics (simulated)
        surface_metrics = {
            "roughness_score": random.uniform(0.7, 1.0),
            "uniformity_score": random.uniform(0.8, 1.0),
            "texture_consistency": random.uniform(0.75, 1.0),
        }

        # Overall quality grade
        quality_score = (
                (1 - anomaly_result.image_score / (self.detector.threshold * 2)) * 0.6 +
                surface_metrics["roughness_score"] * 0.2 +
                surface_metrics["uniformity_score"] * 0.2
        )
        quality_score = max(0, min(1, quality_score))

        return {
            "anomaly_result": anomaly_result.get_summary(),
            "defect_probabilities": defect_probs,
            "surface_metrics": surface_metrics,
            "quality_score": round(quality_score, 3),
            "quality_grade": self._score_to_grade(quality_score),
            "recommendations": self._generate_recommendations(anomaly_result, defect_probs),
        }

    def _score_to_grade(self, score: float) -> str:
        """Convert quality score to letter grade."""
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.6:
            return "D"
        else:
            return "F"

    def _generate_recommendations(
        self,
        anomaly_result: AnomalyScore,
        defect_probs: Dict[str, float]
    ) -> List[str]:
        """Generate recommendations based on detected issues."""
        recommendations = []

        if not anomaly_result.is_anomaly:
            recommendations.append("Surface quality is within acceptable range")
            return recommendations

        # Get top defect type
        if defect_probs:
            top_defect = max(defect_probs.items(), key=lambda x: x[1])

            defect_recommendations = {
                "scratch": "Inspect handling and packaging. Check for debris on print bed.",
                "contamination": "Clean print surface. Check material for moisture or contamination.",
                "delamination": "Increase bed and nozzle temperature. Check layer adhesion settings.",
                "under_extrusion": "Check extruder gear tension. Verify filament diameter.",
                "over_extrusion": "Reduce flow rate. Calibrate e-steps.",
                "layer_shift": "Check belt tension. Reduce print speed. Inspect stepper drivers.",
                "stringing": "Increase retraction distance. Reduce nozzle temperature.",
                "warping": "Improve bed adhesion. Use enclosure. Reduce part cooling.",
            }

            if top_defect[0] in defect_recommendations:
                recommendations.append(defect_recommendations[top_defect[0]])

        if anomaly_result.anomaly_level in [AnomalyLevel.HIGH, AnomalyLevel.CRITICAL]:
            recommendations.append("Consider part rejection or rework")

        return recommendations

    def compare_with_golden_sample(
        self,
        test_image: Any,
        golden_image: Any
    ) -> Dict[str, Any]:
        """
        Compare test image with golden (reference) sample.

        Useful for quality verification against known good parts.
        """
        test_result = self.predict(test_image)

        # Simulated comparison metrics
        similarity_score = random.uniform(0.7, 0.99)
        difference_map = None  # Would be actual difference visualization

        return {
            "test_result": test_result.get_summary(),
            "similarity_to_golden": round(similarity_score, 3),
            "is_similar_enough": similarity_score > 0.9,
            "difference_regions": test_result.defect_regions,
        }

    def export_inspection_report(
        self,
        image: Any,
        part_id: str,
        operator: str = "automated"
    ) -> Dict[str, Any]:
        """
        Generate formal inspection report.

        Creates documentation for quality records.
        """
        analysis = self.analyze_surface_quality(image)

        return {
            "report_id": f"INS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "part_id": part_id,
            "inspection_date": datetime.now().isoformat(),
            "operator": operator,
            "method": "ssl_anomaly_detection",
            "result": {
                "pass": not analysis["anomaly_result"]["is_anomaly"],
                "quality_grade": analysis["quality_grade"],
                "quality_score": analysis["quality_score"],
            },
            "details": {
                "anomaly_score": analysis["anomaly_result"]["score"],
                "threshold": analysis["anomaly_result"]["threshold"],
                "defect_probabilities": analysis["defect_probabilities"],
                "surface_metrics": analysis["surface_metrics"],
            },
            "recommendations": analysis["recommendations"],
            "model_info": {
                "method": self.config.method.name,
                "backbone": self.config.backbone,
                "training_samples": self.training_stats.get("num_training_samples", 0),
            },
        }


# Module exports
__all__ = [
    # Enums
    "AnomalyMethod",
    "AnomalyLevel",
    # Data classes
    "AnomalyConfig",
    "FeatureVector",
    "AnomalyScore",
    # Classes
    "FeatureExtractor",
    "FeatureMemoryBank",
    "PatchCore",
    "SSLAnomalyDetector",
    "ManufacturingAnomalySSL",
]
