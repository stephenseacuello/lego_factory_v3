"""
Data Augmentation - LEGO-Specific Transformations

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides LEGO-optimized augmentation:
- Color-preserving transforms
- Brick-specific augmentations
- 3D print defect simulation
- Albumentations integration
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
import random
import math


class AugmentationType(Enum):
    """Types of augmentation."""
    GEOMETRIC = "geometric"
    COLOR = "color"
    NOISE = "noise"
    BLUR = "blur"
    CUTOUT = "cutout"
    MOSAIC = "mosaic"
    MIXUP = "mixup"
    LEGO_SPECIFIC = "lego_specific"
    DEFECT_SIMULATION = "defect_simulation"


@dataclass
class AugmentationConfig:
    """Configuration for augmentation pipeline."""
    # Geometric transforms
    horizontal_flip: float = 0.5
    vertical_flip: float = 0.0  # Not typical for LEGO
    rotation_limit: int = 15
    scale_range: Tuple[float, float] = (0.8, 1.2)
    translate_range: Tuple[float, float] = (-0.1, 0.1)
    shear_limit: int = 5

    # Color transforms
    brightness_limit: float = 0.2
    contrast_limit: float = 0.2
    saturation_limit: float = 0.3
    hue_shift_limit: int = 10

    # Noise/blur
    gaussian_noise_var: Tuple[float, float] = (10.0, 50.0)
    motion_blur_limit: int = 7
    gaussian_blur_limit: int = 7

    # Cutout/dropout
    cutout_num_holes: int = 8
    cutout_max_size: int = 32
    coarse_dropout_prob: float = 0.3

    # Advanced
    mosaic_prob: float = 0.5
    mixup_prob: float = 0.3
    copy_paste_prob: float = 0.2

    # LEGO-specific
    stud_highlight_prob: float = 0.3
    color_jitter_prob: float = 0.4
    plastic_reflection_prob: float = 0.2

    # Output
    target_size: Tuple[int, int] = (640, 640)


@dataclass
class AugmentedImage:
    """Result of augmentation."""
    image_data: Any  # numpy array or tensor
    bboxes: List[List[float]]  # [x, y, w, h] normalized
    class_ids: List[int]
    augmentations_applied: List[str]
    original_size: Tuple[int, int]
    new_size: Tuple[int, int]


class LegoAugmentation:
    """
    LEGO-specific data augmentation pipeline.

    Provides augmentation transforms optimized for:
    - LEGO brick detection
    - Color preservation (LEGO colors are distinctive)
    - 3D print defect detection
    """

    def __init__(self, config: Optional[AugmentationConfig] = None):
        """
        Initialize augmentation pipeline.

        Args:
            config: Augmentation configuration
        """
        self.config = config or AugmentationConfig()
        self._transforms: List[Dict[str, Any]] = []
        self._build_pipeline()

    def _build_pipeline(self):
        """Build the augmentation pipeline."""
        cfg = self.config

        # Geometric transforms
        self._transforms.extend([
            {
                "name": "HorizontalFlip",
                "type": AugmentationType.GEOMETRIC,
                "prob": cfg.horizontal_flip,
                "params": {},
            },
            {
                "name": "ShiftScaleRotate",
                "type": AugmentationType.GEOMETRIC,
                "prob": 0.5,
                "params": {
                    "shift_limit": cfg.translate_range[1],
                    "scale_limit": (cfg.scale_range[0] - 1, cfg.scale_range[1] - 1),
                    "rotate_limit": cfg.rotation_limit,
                },
            },
            {
                "name": "Affine",
                "type": AugmentationType.GEOMETRIC,
                "prob": 0.3,
                "params": {
                    "shear": (-cfg.shear_limit, cfg.shear_limit),
                },
            },
        ])

        # Color transforms (careful with LEGO colors)
        self._transforms.extend([
            {
                "name": "RandomBrightnessContrast",
                "type": AugmentationType.COLOR,
                "prob": 0.5,
                "params": {
                    "brightness_limit": cfg.brightness_limit,
                    "contrast_limit": cfg.contrast_limit,
                },
            },
            {
                "name": "HueSaturationValue",
                "type": AugmentationType.COLOR,
                "prob": 0.3,  # Lower for LEGO to preserve colors
                "params": {
                    "hue_shift_limit": cfg.hue_shift_limit,
                    "sat_shift_limit": int(cfg.saturation_limit * 100),
                    "val_shift_limit": 20,
                },
            },
            {
                "name": "CLAHE",
                "type": AugmentationType.COLOR,
                "prob": 0.2,
                "params": {
                    "clip_limit": 2.0,
                },
            },
        ])

        # Noise and blur
        self._transforms.extend([
            {
                "name": "GaussNoise",
                "type": AugmentationType.NOISE,
                "prob": 0.2,
                "params": {
                    "var_limit": cfg.gaussian_noise_var,
                },
            },
            {
                "name": "MotionBlur",
                "type": AugmentationType.BLUR,
                "prob": 0.1,
                "params": {
                    "blur_limit": cfg.motion_blur_limit,
                },
            },
            {
                "name": "GaussianBlur",
                "type": AugmentationType.BLUR,
                "prob": 0.1,
                "params": {
                    "blur_limit": cfg.gaussian_blur_limit,
                },
            },
        ])

        # Cutout/dropout
        self._transforms.extend([
            {
                "name": "CoarseDropout",
                "type": AugmentationType.CUTOUT,
                "prob": cfg.coarse_dropout_prob,
                "params": {
                    "max_holes": cfg.cutout_num_holes,
                    "max_height": cfg.cutout_max_size,
                    "max_width": cfg.cutout_max_size,
                },
            },
        ])

        # LEGO-specific transforms
        self._transforms.extend([
            {
                "name": "LegoStudHighlight",
                "type": AugmentationType.LEGO_SPECIFIC,
                "prob": cfg.stud_highlight_prob,
                "params": {
                    "intensity": 0.3,
                },
            },
            {
                "name": "PlasticReflection",
                "type": AugmentationType.LEGO_SPECIFIC,
                "prob": cfg.plastic_reflection_prob,
                "params": {
                    "reflection_intensity": 0.2,
                },
            },
            {
                "name": "LegoColorJitter",
                "type": AugmentationType.LEGO_SPECIFIC,
                "prob": cfg.color_jitter_prob,
                "params": {
                    "color_shift": 5,  # Small shift to preserve LEGO colors
                },
            },
        ])

    def apply(
        self,
        image: Any,
        bboxes: List[List[float]],
        class_ids: List[int]
    ) -> AugmentedImage:
        """
        Apply augmentation pipeline to image.

        Args:
            image: Input image (numpy array)
            bboxes: List of bounding boxes [x, y, w, h] normalized
            class_ids: List of class IDs

        Returns:
            Augmented image with transformed annotations
        """
        applied = []
        current_bboxes = bboxes.copy()
        current_classes = class_ids.copy()

        # Simulate augmentation (actual implementation would use albumentations)
        for transform in self._transforms:
            if random.random() < transform["prob"]:
                applied.append(transform["name"])
                # Apply transform (simulated)
                current_bboxes = self._transform_bboxes(
                    current_bboxes,
                    transform["name"]
                )

        # Filter out invalid boxes
        valid_bboxes = []
        valid_classes = []
        for bbox, cls in zip(current_bboxes, current_classes):
            if self._is_valid_bbox(bbox):
                valid_bboxes.append(bbox)
                valid_classes.append(cls)

        return AugmentedImage(
            image_data=image,  # Would be transformed image
            bboxes=valid_bboxes,
            class_ids=valid_classes,
            augmentations_applied=applied,
            original_size=(640, 640),
            new_size=self.config.target_size,
        )

    def _transform_bboxes(
        self,
        bboxes: List[List[float]],
        transform_name: str
    ) -> List[List[float]]:
        """Transform bounding boxes based on augmentation."""
        # Simulated bbox transformation
        transformed = []
        for bbox in bboxes:
            x, y, w, h = bbox
            # Add small random perturbation (simulating transform effect)
            noise = random.uniform(-0.01, 0.01)
            transformed.append([
                max(0, min(1, x + noise)),
                max(0, min(1, y + noise)),
                max(0.01, w),
                max(0.01, h),
            ])
        return transformed

    def _is_valid_bbox(self, bbox: List[float]) -> bool:
        """Check if bounding box is valid."""
        x, y, w, h = bbox
        if w <= 0.01 or h <= 0.01:
            return False
        if x < 0 or y < 0 or x + w > 1 or y + h > 1:
            return False
        return True

    def get_albumentations_pipeline(self) -> Dict[str, Any]:
        """
        Get Albumentations-compatible pipeline config.

        Returns:
            Pipeline configuration for albumentations
        """
        cfg = self.config

        return {
            "transform": "Compose",
            "bbox_params": {
                "format": "yolo",
                "label_fields": ["class_labels"],
                "min_visibility": 0.3,
            },
            "transforms": [
                {
                    "name": "HorizontalFlip",
                    "p": cfg.horizontal_flip,
                },
                {
                    "name": "ShiftScaleRotate",
                    "shift_limit": cfg.translate_range[1],
                    "scale_limit": 0.2,
                    "rotate_limit": cfg.rotation_limit,
                    "p": 0.5,
                },
                {
                    "name": "RandomBrightnessContrast",
                    "brightness_limit": cfg.brightness_limit,
                    "contrast_limit": cfg.contrast_limit,
                    "p": 0.5,
                },
                {
                    "name": "HueSaturationValue",
                    "hue_shift_limit": cfg.hue_shift_limit,
                    "sat_shift_limit": int(cfg.saturation_limit * 100),
                    "val_shift_limit": 20,
                    "p": 0.3,
                },
                {
                    "name": "GaussNoise",
                    "var_limit": cfg.gaussian_noise_var,
                    "p": 0.2,
                },
                {
                    "name": "MotionBlur",
                    "blur_limit": cfg.motion_blur_limit,
                    "p": 0.1,
                },
                {
                    "name": "CoarseDropout",
                    "max_holes": cfg.cutout_num_holes,
                    "max_height": cfg.cutout_max_size,
                    "max_width": cfg.cutout_max_size,
                    "p": cfg.coarse_dropout_prob,
                },
                {
                    "name": "Resize",
                    "height": cfg.target_size[0],
                    "width": cfg.target_size[1],
                    "p": 1.0,
                },
            ],
        }

    def mosaic_augmentation(
        self,
        images: List[Any],
        all_bboxes: List[List[List[float]]],
        all_class_ids: List[List[int]],
        output_size: Tuple[int, int] = (640, 640)
    ) -> AugmentedImage:
        """
        Apply mosaic augmentation (combine 4 images).

        Args:
            images: List of 4 images
            all_bboxes: List of bboxes for each image
            all_class_ids: List of class IDs for each image
            output_size: Output image size

        Returns:
            Mosaic augmented image
        """
        if len(images) != 4:
            raise ValueError("Mosaic requires exactly 4 images")

        # Combine bboxes with quadrant offset
        combined_bboxes = []
        combined_classes = []

        quadrants = [(0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5)]
        for i, (bboxes, classes) in enumerate(zip(all_bboxes, all_class_ids)):
            ox, oy = quadrants[i]
            for bbox, cls in zip(bboxes, classes):
                x, y, w, h = bbox
                # Scale to quadrant
                new_bbox = [
                    ox + x * 0.5,
                    oy + y * 0.5,
                    w * 0.5,
                    h * 0.5,
                ]
                if self._is_valid_bbox(new_bbox):
                    combined_bboxes.append(new_bbox)
                    combined_classes.append(cls)

        return AugmentedImage(
            image_data=None,  # Would be combined mosaic image
            bboxes=combined_bboxes,
            class_ids=combined_classes,
            augmentations_applied=["Mosaic4"],
            original_size=output_size,
            new_size=output_size,
        )

    def simulate_defect(
        self,
        image: Any,
        defect_type: str,
        intensity: float = 0.5
    ) -> Any:
        """
        Simulate 3D print defects for training.

        Args:
            image: Input image
            defect_type: Type of defect to simulate
            intensity: Defect intensity (0-1)

        Returns:
            Image with simulated defect
        """
        defect_params = {
            "layer_shift": {
                "description": "Horizontal layer displacement",
                "params": {"shift_pixels": int(intensity * 20)},
            },
            "stringing": {
                "description": "Thin filament strings between parts",
                "params": {"string_count": int(intensity * 10)},
            },
            "warping": {
                "description": "Corner/edge lifting from bed",
                "params": {"warp_amount": intensity * 0.3},
            },
            "under_extrusion": {
                "description": "Gaps in extrusion",
                "params": {"gap_frequency": intensity},
            },
            "over_extrusion": {
                "description": "Excess material blob",
                "params": {"blob_size": intensity},
            },
            "z_wobble": {
                "description": "Wavy layer lines",
                "params": {"wobble_amplitude": intensity * 5},
            },
        }

        params = defect_params.get(defect_type, {})

        return {
            "image": image,
            "defect_type": defect_type,
            "intensity": intensity,
            "params": params.get("params", {}),
            "description": params.get("description", "Unknown defect"),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get augmentation pipeline status."""
        return {
            "num_transforms": len(self._transforms),
            "target_size": self.config.target_size,
            "mosaic_prob": self.config.mosaic_prob,
            "mixup_prob": self.config.mixup_prob,
            "transforms": [
                {
                    "name": t["name"],
                    "type": t["type"].value,
                    "prob": t["prob"],
                }
                for t in self._transforms
            ],
        }


# Factory function
def get_augmentation_pipeline(
    config: Optional[AugmentationConfig] = None,
    preset: str = "default"
) -> LegoAugmentation:
    """
    Get augmentation pipeline with optional preset.

    Args:
        config: Custom configuration
        preset: Preset name (default, light, heavy, lego, defect)

    Returns:
        Configured augmentation pipeline
    """
    presets = {
        "default": AugmentationConfig(),
        "light": AugmentationConfig(
            horizontal_flip=0.3,
            rotation_limit=10,
            brightness_limit=0.1,
            mosaic_prob=0.0,
            mixup_prob=0.0,
        ),
        "heavy": AugmentationConfig(
            horizontal_flip=0.5,
            rotation_limit=30,
            brightness_limit=0.3,
            contrast_limit=0.3,
            mosaic_prob=0.7,
            mixup_prob=0.5,
            coarse_dropout_prob=0.5,
        ),
        "lego": AugmentationConfig(
            horizontal_flip=0.5,
            rotation_limit=15,
            hue_shift_limit=5,  # Preserve LEGO colors
            stud_highlight_prob=0.5,
            plastic_reflection_prob=0.3,
            color_jitter_prob=0.2,
        ),
        "defect": AugmentationConfig(
            horizontal_flip=0.5,
            rotation_limit=5,  # Less rotation for defect patterns
            brightness_limit=0.15,
            gaussian_noise_var=(5.0, 30.0),
            mosaic_prob=0.3,
        ),
    }

    if config:
        return LegoAugmentation(config)

    return LegoAugmentation(presets.get(preset, presets["default"]))
