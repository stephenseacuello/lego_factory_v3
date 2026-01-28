"""
Grounding DINO Zero-Shot Object Detection
LegoMCP PhD-Level Manufacturing Platform

Implements Grounding DINO for text-prompted object detection with:
- Zero-shot detection using natural language
- Open-vocabulary object localization
- Integration with SAM for segmentation
- Manufacturing-specific prompts
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class GroundingDINOModel(Enum):
    SWIN_T = "groundingdino_swint_ogc"  # Swin-T backbone
    SWIN_B = "groundingdino_swinb_cogcoor"  # Swin-B backbone (better quality)


@dataclass
class DetectionBox:
    """Single detection bounding box."""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    phrase: str
    phrase_confidence: float
    center: Tuple[int, int] = None

    def __post_init__(self):
        if self.center is None:
            x1, y1, x2, y2 = self.bbox
            self.center = ((x1 + x2) // 2, (y1 + y2) // 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "confidence": float(self.confidence),
            "phrase": self.phrase,
            "phrase_confidence": float(self.phrase_confidence),
            "center": list(self.center),
        }

    @property
    def area(self) -> int:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


@dataclass
class DetectionResult:
    """Complete detection result."""
    boxes: List[DetectionBox]
    image_shape: Tuple[int, int]  # H, W
    text_prompt: str
    inference_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boxes": [b.to_dict() for b in self.boxes],
            "image_shape": list(self.image_shape),
            "text_prompt": self.text_prompt,
            "inference_time_ms": self.inference_time_ms,
            "detection_count": len(self.boxes),
            "metadata": self.metadata,
        }

    @property
    def detection_count(self) -> int:
        return len(self.boxes)

    def filter_by_confidence(self, threshold: float) -> "DetectionResult":
        """Return new result with detections above threshold."""
        filtered = [b for b in self.boxes if b.confidence >= threshold]
        return DetectionResult(
            boxes=filtered,
            image_shape=self.image_shape,
            text_prompt=self.text_prompt,
            inference_time_ms=self.inference_time_ms,
            metadata=self.metadata,
        )

    def filter_by_phrase(self, phrase: str) -> "DetectionResult":
        """Return new result with detections matching phrase."""
        filtered = [b for b in self.boxes if phrase.lower() in b.phrase.lower()]
        return DetectionResult(
            boxes=filtered,
            image_shape=self.image_shape,
            text_prompt=self.text_prompt,
            inference_time_ms=self.inference_time_ms,
            metadata=self.metadata,
        )


class GroundingDINODetector:
    """
    Grounding DINO zero-shot object detector.

    Features:
    - Natural language object detection
    - Open-vocabulary without retraining
    - Manufacturing-specific prompt templates
    - Integration with SAM for segmentation
    """

    def __init__(
        self,
        model_type: GroundingDINOModel = GroundingDINOModel.SWIN_T,
        device: str = "cuda",
        box_threshold: float = 0.35,
        text_threshold: float = 0.25,
    ):
        self.model_type = model_type
        self.device = device
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self._model = None
        self._processor = None

        # Manufacturing prompt templates
        self.prompt_templates = {
            "defects": "scratch . crack . dent . chip . discoloration . contamination",
            "lego_parts": "brick . plate . tile . slope . technic beam . minifigure",
            "quality": "defective part . damaged surface . missing component . misaligned",
            "assembly": "assembled unit . connected parts . complete assembly . partial assembly",
            "packaging": "box . label . tape . padding . container",
        }

    def load_model(self):
        """Load Grounding DINO model."""
        try:
            from groundingdino.util.inference import load_model, load_image, predict, annotate
            from groundingdino.util import box_ops

            # Model paths
            config_path = f"/app/models/groundingdino/{self.model_type.value}.py"
            weights_path = f"/app/models/groundingdino/{self.model_type.value}.pth"

            self._model = load_model(config_path, weights_path)
            self._model.to(self.device)
            self._model.eval()

            logger.info(f"Grounding DINO loaded: {self.model_type.value}")

        except ImportError:
            logger.warning("groundingdino not installed, using mock model")
            self._model = MockGroundingDINO()

        except Exception as e:
            logger.warning(f"Failed to load Grounding DINO: {e}, using mock")
            self._model = MockGroundingDINO()

    def detect(
        self,
        image: np.ndarray,
        text_prompt: str,
        box_threshold: float = None,
        text_threshold: float = None,
    ) -> DetectionResult:
        """
        Detect objects matching text prompt.

        Args:
            image: RGB image (H, W, 3)
            text_prompt: Natural language description of objects
            box_threshold: Detection confidence threshold
            text_threshold: Text matching threshold

        Returns:
            DetectionResult with detected boxes
        """
        if self._model is None:
            self.load_model()

        box_threshold = box_threshold or self.box_threshold
        text_threshold = text_threshold or self.text_threshold

        start_time = time.time()

        try:
            from groundingdino.util.inference import predict
            import torch

            # Prepare image
            image_tensor = self._prepare_image(image)

            # Run detection
            with torch.no_grad():
                boxes, logits, phrases = predict(
                    model=self._model,
                    image=image_tensor,
                    caption=text_prompt,
                    box_threshold=box_threshold,
                    text_threshold=text_threshold,
                )

            # Convert to pixel coordinates
            h, w = image.shape[:2]
            detection_boxes = []

            for box, logit, phrase in zip(boxes, logits, phrases):
                # Box format: cx, cy, w, h (normalized)
                cx, cy, bw, bh = box.tolist()

                # Convert to x1, y1, x2, y2 (pixels)
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                x2 = int((cx + bw / 2) * w)
                y2 = int((cy + bh / 2) * h)

                # Clamp to image bounds
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w))
                y2 = max(0, min(y2, h))

                detection_boxes.append(DetectionBox(
                    bbox=(x1, y1, x2, y2),
                    confidence=float(logit),
                    phrase=phrase,
                    phrase_confidence=float(logit),
                ))

        except (ImportError, AttributeError) as e:
            logger.debug(f"Using mock detection: {e}")
            # Mock detections
            detection_boxes = self._mock_detect(image, text_prompt)

        inference_time = (time.time() - start_time) * 1000

        return DetectionResult(
            boxes=detection_boxes,
            image_shape=image.shape[:2],
            text_prompt=text_prompt,
            inference_time_ms=inference_time,
            metadata={
                "model": self.model_type.value,
                "box_threshold": box_threshold,
                "text_threshold": text_threshold,
            },
        )

    def detect_defects(
        self,
        image: np.ndarray,
        additional_defects: List[str] = None,
    ) -> DetectionResult:
        """
        Detect manufacturing defects using predefined prompts.

        Args:
            image: RGB image
            additional_defects: Extra defect types to detect

        Returns:
            DetectionResult for defects
        """
        prompt = self.prompt_templates["defects"]
        if additional_defects:
            prompt += " . " + " . ".join(additional_defects)

        return self.detect(image, prompt)

    def detect_lego_parts(
        self,
        image: np.ndarray,
        part_types: List[str] = None,
    ) -> DetectionResult:
        """
        Detect LEGO parts in image.

        Args:
            image: RGB image
            part_types: Specific part types to detect

        Returns:
            DetectionResult for LEGO parts
        """
        if part_types:
            prompt = " . ".join(part_types)
        else:
            prompt = self.prompt_templates["lego_parts"]

        return self.detect(image, prompt, box_threshold=0.3)

    def detect_quality_issues(
        self,
        image: np.ndarray,
    ) -> DetectionResult:
        """
        Detect quality issues in manufacturing image.

        Args:
            image: RGB image

        Returns:
            DetectionResult for quality issues
        """
        prompt = self.prompt_templates["quality"]
        return self.detect(image, prompt, box_threshold=0.25)

    def detect_with_sam(
        self,
        image: np.ndarray,
        text_prompt: str,
        sam_segmenter: "SAMSegmenter" = None,
    ) -> Tuple[DetectionResult, List["SegmentationResult"]]:
        """
        Detect objects and segment with SAM.

        Args:
            image: RGB image
            text_prompt: Text description
            sam_segmenter: SAM segmenter instance

        Returns:
            Tuple of (detections, segmentations)
        """
        # First detect with Grounding DINO
        detections = self.detect(image, text_prompt)

        if sam_segmenter is None:
            return detections, []

        # Segment each detection with SAM
        segmentations = []
        for box in detections.boxes:
            seg_result = sam_segmenter.segment_box(image, box.bbox)
            segmentations.append(seg_result)

        return detections, segmentations

    def batch_detect(
        self,
        images: List[np.ndarray],
        text_prompt: str,
    ) -> List[DetectionResult]:
        """
        Detect objects in multiple images.

        Args:
            images: List of RGB images
            text_prompt: Text description

        Returns:
            List of DetectionResult
        """
        results = []
        for image in images:
            result = self.detect(image, text_prompt)
            results.append(result)
        return results

    def _prepare_image(self, image: np.ndarray):
        """Prepare image for model input."""
        try:
            import torch
            from groundingdino.util.inference import load_image
            from PIL import Image

            # Convert to PIL
            pil_image = Image.fromarray(image)

            # Use groundingdino's transform
            transform = self._get_transform()
            image_tensor = transform(pil_image)

            return image_tensor

        except ImportError:
            return image

    def _get_transform(self):
        """Get image transform."""
        try:
            import torch
            from torchvision import transforms

            return transforms.Compose([
                transforms.Resize((800, 800)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
        except ImportError:
            return lambda x: x

    def _mock_detect(
        self,
        image: np.ndarray,
        text_prompt: str,
    ) -> List[DetectionBox]:
        """Generate mock detections for testing."""
        h, w = image.shape[:2]

        # Parse prompt for phrases
        phrases = [p.strip() for p in text_prompt.split(".") if p.strip()]

        detections = []
        np.random.seed(42)

        for i, phrase in enumerate(phrases[:3]):  # Max 3 mock detections
            # Random box
            x1 = np.random.randint(0, w // 2)
            y1 = np.random.randint(0, h // 2)
            x2 = x1 + np.random.randint(50, min(200, w - x1))
            y2 = y1 + np.random.randint(50, min(200, h - y1))

            detections.append(DetectionBox(
                bbox=(x1, y1, x2, y2),
                confidence=0.5 + np.random.rand() * 0.4,
                phrase=phrase,
                phrase_confidence=0.5 + np.random.rand() * 0.4,
            ))

        return detections


class MockGroundingDINO:
    """Mock Grounding DINO for testing."""

    def to(self, device):
        return self

    def eval(self):
        return self
