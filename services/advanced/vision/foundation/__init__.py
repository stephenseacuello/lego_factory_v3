"""
Foundation Models for Vision
LegoMCP PhD-Level Manufacturing Platform

Provides state-of-the-art foundation models:
- SAM (Segment Anything Model) - Universal segmentation
- DINOv2 - Self-supervised visual features
- GroundingDINO - Zero-shot object detection
- CLIP - Vision-language understanding
"""

from .sam_segmenter import SAMSegmenter, SegmentationResult
from .dino_features import DINOFeatureExtractor, FeatureResult
from .grounding_dino import GroundingDINODetector, DetectionResult
from .clip_classifier import CLIPClassifier, ClassificationResult

__all__ = [
    "SAMSegmenter",
    "SegmentationResult",
    "DINOFeatureExtractor",
    "FeatureResult",
    "GroundingDINODetector",
    "DetectionResult",
    "CLIPClassifier",
    "ClassificationResult",
]
