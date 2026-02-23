"""
LEGO Brick Detector

YOLO11 + Roboflow integration for detecting and identifying LEGO bricks.
Supports multiple detection backends and color classification.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Generator
from dataclasses import dataclass, asdict
from enum import Enum
import threading

# Optional imports - graceful degradation if not installed
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    YOLO = None

try:
    from roboflow import Roboflow

    ROBOFLOW_AVAILABLE = True
except ImportError:
    ROBOFLOW_AVAILABLE = False
    Roboflow = None

try:
    from inference_sdk import InferenceHTTPClient

    INFERENCE_SDK_AVAILABLE = True
except ImportError:
    INFERENCE_SDK_AVAILABLE = False
    InferenceHTTPClient = None

logger = logging.getLogger(__name__)


class DetectionBackend(Enum):
    """Available detection backends."""

    YOLO_LOCAL = "yolo_local"  # Local YOLO11 model
    ROBOFLOW_API = "roboflow_api"  # Roboflow hosted inference
    ROBOFLOW_LOCAL = "roboflow_local"  # Roboflow Inference local
    MOCK = "mock"  # Mock detector for testing


@dataclass
class BrickDetection:
    """A detected LEGO brick."""

    brick_id: str  # Matched catalog ID
    brick_name: str  # Human readable name
    color: str  # Detected color name
    color_rgb: Tuple[int, int, int]  # RGB values
    confidence: float  # Detection confidence (0-1)
    bbox: Tuple[int, int, int, int]  # Bounding box (x1, y1, x2, y2)
    center: Tuple[int, int]  # Center point (x, y)
    grid_position: str  # Grid coordinate (e.g., "A3")
    area_px: int  # Area in pixels
    class_name: str = ""  # Raw class name from model

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LegoColorClassifier:
    """Classify official LEGO brick colors."""

    # Official LEGO colors with RGB values
    LEGO_COLORS = {
        "red": (201, 26, 9),
        "bright_red": (255, 0, 0),
        "dark_red": (114, 0, 18),
        "blue": (0, 87, 168),
        "bright_blue": (0, 85, 191),
        "dark_blue": (25, 50, 90),
        "medium_blue": (90, 147, 219),
        "yellow": (247, 209, 23),
        "bright_yellow": (255, 240, 0),
        "green": (0, 150, 36),
        "bright_green": (0, 200, 0),
        "dark_green": (0, 69, 26),
        "lime": (166, 209, 47),
        "white": (255, 255, 255),
        "black": (27, 42, 52),
        "light_gray": (160, 165, 169),
        "dark_gray": (91, 103, 112),
        "light_bluish_gray": (175, 181, 189),
        "dark_bluish_gray": (108, 110, 104),
        "orange": (254, 138, 24),
        "bright_orange": (255, 126, 20),
        "brown": (88, 57, 39),
        "reddish_brown": (89, 51, 21),
        "tan": (228, 205, 158),
        "dark_tan": (149, 125, 98),
        "pink": (255, 192, 203),
        "bright_pink": (255, 105, 180),
        "magenta": (255, 0, 127),
        "purple": (104, 37, 130),
        "dark_purple": (63, 26, 74),
        "lavender": (180, 168, 209),
        "azure": (0, 175, 202),
        "medium_azure": (66, 192, 251),
        "dark_azure": (0, 138, 173),
        "coral": (255, 127, 80),
        "nougat": (204, 142, 104),
        "medium_nougat": (170, 125, 85),
        "trans_clear": (255, 255, 255),
        "trans_red": (255, 0, 0),
        "trans_blue": (0, 0, 255),
        "trans_yellow": (255, 255, 0),
        "trans_green": (0, 255, 0),
        "trans_orange": (255, 128, 0),
    }

    def __init__(self):
        """Initialize color classifier."""
        # Pre-compute color arrays for faster matching
        self._color_names = list(self.LEGO_COLORS.keys())
        if NUMPY_AVAILABLE:
            self._color_values = np.array(list(self.LEGO_COLORS.values()))

    def classify(self, roi: "np.ndarray") -> Tuple[str, Tuple[int, int, int]]:
        """
        Classify the dominant LEGO color in a region.

        Args:
            roi: Region of interest (BGR image from OpenCV)

        Returns:
            Tuple of (color_name, (r, g, b))
        """
        if not NUMPY_AVAILABLE or roi is None or roi.size == 0:
            return "unknown", (128, 128, 128)

        # Convert BGR to RGB
        if len(roi.shape) == 3 and roi.shape[2] == 3:
            roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB) if CV2_AVAILABLE else roi
        else:
            return "unknown", (128, 128, 128)

        # Get dominant color using center region (avoid edges)
        h, w = roi_rgb.shape[:2]
        margin = max(1, min(h, w) // 4)
        center_region = roi_rgb[margin : h - margin, margin : w - margin]

        if center_region.size == 0:
            center_region = roi_rgb

        # Calculate mean color
        mean_color = np.mean(center_region.reshape(-1, 3), axis=0).astype(int)

        # Find closest LEGO color
        distances = np.sqrt(np.sum((self._color_values - mean_color) ** 2, axis=1))
        closest_idx = np.argmin(distances)

        color_name = self._color_names[closest_idx]
        color_rgb = tuple(self.LEGO_COLORS[color_name])

        return color_name, color_rgb

    def get_all_colors(self) -> Dict[str, Tuple[int, int, int]]:
        """Get all available LEGO colors."""
        return self.LEGO_COLORS.copy()


class BrickMatcher:
    """Match detected bricks to the catalog."""

    def __init__(self):
        """Initialize brick matcher."""
        self._catalog_loaded = False
        self._catalog = {}
        self._load_catalog()

    def _load_catalog(self):
        """Load brick catalog for matching."""
        try:
            from brick_catalog_extended import BRICKS, search, get

            self._catalog = BRICKS
            self._search = search
            self._get = get
            self._catalog_loaded = True
        except ImportError:
            logger.warning("Brick catalog not available for matching")
            self._catalog_loaded = False

    def match(self, class_name: str, bbox_size: Tuple[int, int] = None) -> Tuple[str, str]:
        """
        Match a detection class name to catalog brick.

        Args:
            class_name: Raw class name from model
            bbox_size: Optional (width, height) of bounding box for size hints

        Returns:
            Tuple of (brick_id, brick_name)
        """
        if not self._catalog_loaded:
            return class_name, class_name.replace("_", " ").title()

        # Clean up class name
        clean_name = class_name.lower().strip()
        clean_name = clean_name.replace(" ", "_").replace("-", "_")

        # Common YOLO class name mappings
        class_mapping = {
            "lego_brick": "brick_2x4",
            "lego_2x4": "brick_2x4",
            "lego_2x2": "brick_2x2",
            "lego_1x2": "brick_1x2",
            "lego_1x4": "brick_1x4",
            "brick": "brick_2x4",
            "plate": "plate_2x4",
            "tile": "tile_2x2",
            "slope": "slope_45_2x2",
            "technic": "technic_brick_1x6",
        }

        # Try direct mapping
        if clean_name in class_mapping:
            clean_name = class_mapping[clean_name]

        # Try exact match
        brick = self._get(clean_name)
        if brick:
            return brick.name, brick.name.replace("_", " ").title()

        # Try search
        results = self._search(class_name)
        if results:
            best = results[0]
            return best.name, best.name.replace("_", " ").title()

        # Parse size from class name (e.g., "2x4", "1x2")
        import re

        size_match = re.search(r"(\d+)x(\d+)", class_name)
        if size_match:
            w, h = size_match.groups()
            guessed_id = f"brick_{w}x{h}"
            brick = self._get(guessed_id)
            if brick:
                return brick.name, brick.name.replace("_", " ").title()

        # Fallback to raw class name
        return clean_name, class_name.replace("_", " ").title()


class LegoDetector:
    """
    Main LEGO brick detector.

    Supports multiple backends:
    - YOLO11 local (fastest, requires ultralytics)
    - Roboflow API (easiest, requires API key)
    - Roboflow local (good balance, requires inference package)
    - Mock (for testing without ML dependencies)
    """

    # Pre-trained LEGO models on Roboflow Universe (workspace/project/version)
    ROBOFLOW_MODELS = {
        "lego-bricks-v1": ("autodash", "lego-bricks-uwgtj", 1),
        "lego-bricks-v2": ("lego-gbeqo", "lego-bricks-gelcm", 1),
        "lego-detection": ("legos-3oate", "lego-detection-fsxai", 1),
    }

    def __init__(
        self,
        backend: DetectionBackend = None,
        model_path: str = None,
        roboflow_api_key: str = None,
        roboflow_model_id: str = None,
        confidence_threshold: float = 0.5,
        device: str = "auto",
        grid_size: Tuple[int, int] = (32, 16),  # 16x32 baseplate (32 cols, 16 rows)
    ):
        """
        Initialize detector.

        Args:
            backend: Detection backend to use (auto-selected if None)
            model_path: Path to local YOLO model
            roboflow_api_key: Roboflow API key
            roboflow_model_id: Roboflow model ID
            confidence_threshold: Minimum confidence for detections
            device: Device for inference ("cpu", "cuda", "mps", "auto")
            grid_size: Grid dimensions for position mapping
        """
        self.confidence_threshold = confidence_threshold
        self.grid_size = grid_size
        self.color_classifier = LegoColorClassifier()
        self.brick_matcher = BrickMatcher()

        # Auto-select backend if not specified
        if backend is None:
            backend = self._auto_select_backend(roboflow_api_key)

        self.backend = backend
        self._model = None
        self._client = None

        # Initialize based on backend
        if backend == DetectionBackend.YOLO_LOCAL:
            self._init_yolo(model_path, device)
        elif backend == DetectionBackend.ROBOFLOW_API:
            self._init_roboflow_api(roboflow_api_key, roboflow_model_id)
        elif backend == DetectionBackend.ROBOFLOW_LOCAL:
            self._init_roboflow_local(roboflow_model_id)
        elif backend == DetectionBackend.MOCK:
            logger.info("Using mock detector")

        logger.info(f"LegoDetector initialized with backend: {backend.value}")

    def _auto_select_backend(self, api_key: str = None) -> DetectionBackend:
        """Auto-select best available backend."""
        if YOLO_AVAILABLE:
            return DetectionBackend.YOLO_LOCAL
        elif api_key and INFERENCE_SDK_AVAILABLE:
            return DetectionBackend.ROBOFLOW_API
        elif ROBOFLOW_AVAILABLE:
            return DetectionBackend.ROBOFLOW_LOCAL
        else:
            logger.warning("No ML backend available, using mock detector")
            return DetectionBackend.MOCK

    def _init_yolo(self, model_path: str, device: str):
        """Initialize YOLO11 model."""
        if not YOLO_AVAILABLE:
            raise ImportError("ultralytics not installed. Install with: pip install ultralytics")

        # Use provided path or download default
        if model_path is None:
            model_path = "yolo11n.pt"  # Nano model - fastest

        logger.info(f"Loading YOLO model: {model_path}")
        self._model = YOLO(model_path)

        if device != "auto":
            self._model.to(device)

    def _init_roboflow_api(self, api_key: str, model_id: str):
        """Initialize Roboflow API client using roboflow package."""
        if not ROBOFLOW_AVAILABLE:
            raise ImportError(
                "roboflow not installed. Install with: pip install roboflow"
            )

        if not api_key:
            api_key = os.environ.get("ROBOFLOW_API_KEY")

        if not api_key:
            raise ValueError(
                "Roboflow API key required. Set ROBOFLOW_API_KEY environment variable."
            )

        # Initialize Roboflow client
        rf = Roboflow(api_key=api_key)

        # Parse model_id or use default
        if model_id:
            # Support formats: "workspace/project/version" or "project/version"
            parts = model_id.split("/")
            if len(parts) == 3:
                workspace, project, version = parts
                version = int(version)
            elif len(parts) == 2:
                # Use workspace from API key
                project, version = parts
                version = int(version)
                workspace = None
            else:
                # Use default model
                workspace, project, version = self.ROBOFLOW_MODELS["lego-bricks-v1"]
        else:
            workspace, project, version = self.ROBOFLOW_MODELS["lego-bricks-v1"]

        # Load the model
        logger.info(f"Loading Roboflow model: {project}/v{version}")
        try:
            if workspace:
                self._rf_project = rf.workspace(workspace).project(project)
            else:
                self._rf_project = rf.workspace().project(project)
            self._model = self._rf_project.version(version).model
            self._model_id = f"{project}/{version}"
            logger.info(f"Roboflow model loaded: {self._model_id}")
        except Exception as e:
            logger.error(f"Failed to load Roboflow model: {e}")
            raise

    def _init_roboflow_local(self, model_id: str):
        """Initialize Roboflow local inference using inference SDK."""
        try:
            from inference_sdk import InferenceHTTPClient

            # Get local inference server URL from environment
            inference_url = os.environ.get("ROBOFLOW_INFERENCE_URL", "http://localhost:9001")
            api_key = os.environ.get("ROBOFLOW_API_KEY", "")

            self._inference_client = InferenceHTTPClient(
                api_url=inference_url,
                api_key=api_key
            )
            self._model_id = model_id or os.environ.get("ROBOFLOW_MODEL", "robymarworker/lego-emmet-b200-object-detection/1")
            logger.info(f"Initialized local inference at {inference_url} with model {self._model_id}")
        except ImportError:
            raise ImportError("inference-sdk not installed. Install with: pip install inference-sdk")

    def detect(self, frame: "np.ndarray") -> List[BrickDetection]:
        """
        Detect bricks in a frame.

        Args:
            frame: BGR image from OpenCV (numpy array)

        Returns:
            List of BrickDetection objects
        """
        if self.backend == DetectionBackend.YOLO_LOCAL:
            return self._detect_yolo(frame)
        elif self.backend == DetectionBackend.ROBOFLOW_API:
            return self._detect_roboflow_api(frame)
        elif self.backend == DetectionBackend.ROBOFLOW_LOCAL:
            return self._detect_roboflow_local(frame)
        else:
            return self._detect_mock(frame)

    def _detect_yolo(self, frame: "np.ndarray") -> List[BrickDetection]:
        """Detect using local YOLO11 model."""
        results = self._model(frame, conf=self.confidence_threshold, verbose=False)
        detections = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = self._model.names.get(cls, f"class_{cls}")

                # Extract ROI for color classification
                roi = frame[y1:y2, x1:x2]
                color, color_rgb = self.color_classifier.classify(roi)

                # Match to catalog
                brick_id, brick_name = self.brick_matcher.match(class_name, (x2 - x1, y2 - y1))

                # Calculate position
                center = ((x1 + x2) // 2, (y1 + y2) // 2)
                grid_pos = self._calculate_grid_position(center, frame.shape)

                detections.append(
                    BrickDetection(
                        brick_id=brick_id,
                        brick_name=brick_name,
                        color=color,
                        color_rgb=color_rgb,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        center=center,
                        grid_position=grid_pos,
                        area_px=(x2 - x1) * (y2 - y1),
                        class_name=class_name,
                    )
                )

        return detections

    def _detect_roboflow_api(self, frame: "np.ndarray") -> List[BrickDetection]:
        """Detect using Roboflow API via roboflow package."""
        import tempfile

        # Save frame to temporary file (roboflow package needs file path)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cv2.imwrite(tmp.name, frame)
            tmp_path = tmp.name

        try:
            # Run prediction
            result = self._model.predict(
                tmp_path,
                confidence=int(self.confidence_threshold * 100),
                overlap=30
            ).json()
        finally:
            # Clean up temp file
            import os as os_module
            try:
                os_module.unlink(tmp_path)
            except Exception:
                pass

        detections = []

        for pred in result.get("predictions", []):
            x = int(pred["x"])
            y = int(pred["y"])
            w = int(pred["width"])
            h = int(pred["height"])

            x1 = x - w // 2
            y1 = y - h // 2
            x2 = x + w // 2
            y2 = y + h // 2

            conf = float(pred.get("confidence", 0)) / 100.0  # Convert from percentage
            class_name = pred.get("class", "unknown")

            # Skip low confidence
            if conf < self.confidence_threshold:
                continue

            # Extract ROI for color
            roi = frame[max(0, y1) : y2, max(0, x1) : x2]
            color, color_rgb = self.color_classifier.classify(roi)

            # Match to catalog
            brick_id, brick_name = self.brick_matcher.match(class_name, (w, h))

            # Grid position
            grid_pos = self._calculate_grid_position((x, y), frame.shape)

            detections.append(
                BrickDetection(
                    brick_id=brick_id,
                    brick_name=brick_name,
                    color=color,
                    color_rgb=color_rgb,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    center=(x, y),
                    grid_position=grid_pos,
                    area_px=w * h,
                    class_name=class_name,
                )
            )

        return detections

    def _detect_roboflow_local(self, frame: "np.ndarray") -> List[BrickDetection]:
        """Detect using local Roboflow inference server."""
        # Use inference SDK client to call local server
        # Note: confidence filtering done below, not in infer() call
        result = self._inference_client.infer(
            self._model_id,
            frame
        )

        detections = []

        # Handle both dict and object response formats
        predictions = result.get("predictions", []) if isinstance(result, dict) else []

        for pred in predictions:
            x = int(pred.get("x", 0))
            y = int(pred.get("y", 0))
            w = int(pred.get("width", 0))
            h = int(pred.get("height", 0))

            x1, y1 = x - w // 2, y - h // 2
            x2, y2 = x + w // 2, y + h // 2

            conf = float(pred.get("confidence", 0))
            class_name = pred.get("class", "unknown")

            if conf < self.confidence_threshold:
                continue

            roi = frame[max(0, y1) : y2, max(0, x1) : x2]
            color, color_rgb = self.color_classifier.classify(roi)
            brick_id, brick_name = self.brick_matcher.match(class_name)
            grid_pos = self._calculate_grid_position((x, y), frame.shape)

            detections.append(
                BrickDetection(
                    brick_id=brick_id,
                    brick_name=brick_name,
                    color=color,
                    color_rgb=color_rgb,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    center=(x, y),
                    grid_position=grid_pos,
                    area_px=w * h,
                    class_name=class_name,
                )
            )

        return detections

    def _detect_mock(self, frame: "np.ndarray") -> List[BrickDetection]:
        """Mock detector for testing without ML dependencies."""
        import random

        h, w = frame.shape[:2] if frame is not None else (720, 1280)

        # Generate random mock detections
        mock_bricks = [
            ("brick_2x4", "Brick 2x4"),
            ("brick_2x2", "Brick 2x2"),
            ("plate_4x4", "Plate 4x4"),
            ("tile_2x2", "Tile 2x2"),
            ("slope_45_2x2", "Slope 45 2x2"),
        ]

        colors = ["red", "blue", "yellow", "white", "black", "green"]

        detections = []
        num_bricks = random.randint(3, 8)

        for i in range(num_bricks):
            brick_id, brick_name = random.choice(mock_bricks)
            color = random.choice(colors)
            color_rgb = self.color_classifier.LEGO_COLORS.get(color, (128, 128, 128))

            # Random position
            cx = random.randint(100, w - 100)
            cy = random.randint(100, h - 100)
            bw = random.randint(40, 80)
            bh = random.randint(30, 60)

            detections.append(
                BrickDetection(
                    brick_id=brick_id,
                    brick_name=brick_name,
                    color=color,
                    color_rgb=color_rgb,
                    confidence=random.uniform(0.7, 0.99),
                    bbox=(cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2),
                    center=(cx, cy),
                    grid_position=self._calculate_grid_position((cx, cy), (h, w)),
                    area_px=bw * bh,
                    class_name=brick_id,
                )
            )

        return detections

    def _calculate_grid_position(
        self, center: Tuple[int, int], frame_shape: Tuple[int, ...]
    ) -> str:
        """Calculate grid position from pixel coordinates."""
        h, w = frame_shape[:2]
        cols, rows = self.grid_size

        col = int(center[0] / w * cols)
        row = int(center[1] / h * rows)

        col = max(0, min(cols - 1, col))
        row = max(0, min(rows - 1, row))

        # Use numeric format "col-row" for grids larger than 26 columns
        col_number = col + 1
        row_number = row + 1

        return f"{col_number}-{row_number}"

    def get_info(self) -> Dict[str, Any]:
        """Get detector information."""
        return {
            "backend": self.backend.value,
            "confidence_threshold": self.confidence_threshold,
            "grid_size": self.grid_size,
            "yolo_available": YOLO_AVAILABLE,
            "roboflow_available": ROBOFLOW_AVAILABLE,
            "inference_sdk_available": INFERENCE_SDK_AVAILABLE,
            "cv2_available": CV2_AVAILABLE,
            "numpy_available": NUMPY_AVAILABLE,
        }


# Singleton instance
_detector: Optional[LegoDetector] = None
_detector_lock = threading.Lock()


def get_detector(**kwargs) -> LegoDetector:
    """Get singleton detector instance."""
    global _detector
    with _detector_lock:
        if _detector is None:
            # Read configuration from environment if not provided
            if 'backend' not in kwargs:
                backend_str = os.environ.get("DETECTION_BACKEND", "auto")
                backend_map = {
                    "yolo": DetectionBackend.YOLO_LOCAL,
                    "yolo_local": DetectionBackend.YOLO_LOCAL,
                    "roboflow": DetectionBackend.ROBOFLOW_API,
                    "roboflow_api": DetectionBackend.ROBOFLOW_API,
                    "roboflow_local": DetectionBackend.ROBOFLOW_LOCAL,
                    "local": DetectionBackend.ROBOFLOW_LOCAL,
                    "mock": DetectionBackend.MOCK,
                }
                if backend_str in backend_map:
                    kwargs['backend'] = backend_map[backend_str]

            if 'roboflow_api_key' not in kwargs:
                kwargs['roboflow_api_key'] = os.environ.get("ROBOFLOW_API_KEY")

            if 'roboflow_model_id' not in kwargs:
                kwargs['roboflow_model_id'] = os.environ.get("ROBOFLOW_MODEL")

            if 'confidence_threshold' not in kwargs:
                threshold_str = os.environ.get("DETECTION_THRESHOLD", "0.5")
                try:
                    kwargs['confidence_threshold'] = float(threshold_str)
                except ValueError:
                    kwargs['confidence_threshold'] = 0.5

            _detector = LegoDetector(**kwargs)
    return _detector


def reset_detector():
    """Reset detector instance."""
    global _detector
    with _detector_lock:
        _detector = None
