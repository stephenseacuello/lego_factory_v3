"""
Camera Manager

Handles camera input for live workspace detection.
Supports webcams, USB cameras, and IP cameras.
"""

import time
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Generator, Callable
from dataclasses import dataclass
from enum import Enum
import base64

# Optional imports
try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None
    np = None

logger = logging.getLogger(__name__)


class CameraType(Enum):
    """Camera types."""

    WEBCAM = "webcam"
    USB = "usb"
    IP = "ip"
    FILE = "file"
    MOCK = "mock"


@dataclass
class CameraInfo:
    """Information about a camera."""

    id: int
    name: str
    type: CameraType
    width: int
    height: int
    fps: float
    available: bool
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,  # Convert enum to string
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "available": self.available,
            "url": self.url,
        }


class CameraManager:
    """Manages camera input for detection."""

    def __init__(self):
        """Initialize camera manager."""
        self._cameras: Dict[int, CameraInfo] = {}
        self._active_camera: Optional[int] = None
        self._capture = None
        self._lock = threading.Lock()
        self._stream_thread: Optional[threading.Thread] = None
        self._streaming = False
        self._frame_count = 0
        self._last_frame = None
        self._last_frame_time = 0
        self._frame_callbacks: List[Callable] = []

        # Scan for available cameras
        self._scan_cameras()

    def _scan_cameras(self):
        """Scan for available cameras."""
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available, using mock camera")
            self._cameras[0] = CameraInfo(
                id=0,
                name="Mock Camera",
                type=CameraType.MOCK,
                width=1280,
                height=720,
                fps=30.0,
                available=True,
            )
            return

        # Scan for webcams (try indices 0-4)
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

                self._cameras[i] = CameraInfo(
                    id=i,
                    name=f"Camera {i}",
                    type=CameraType.WEBCAM,
                    width=width,
                    height=height,
                    fps=fps,
                    available=True,
                )
                cap.release()
            else:
                cap.release()

        # Add mock camera as fallback
        if not self._cameras:
            self._cameras[0] = CameraInfo(
                id=0,
                name="Mock Camera",
                type=CameraType.MOCK,
                width=1280,
                height=720,
                fps=30.0,
                available=True,
            )

        logger.info(f"Found {len(self._cameras)} camera(s)")

    def list_cameras(self) -> List[CameraInfo]:
        """List all available cameras."""
        return list(self._cameras.values())

    def get_camera(self, camera_id: int) -> Optional[CameraInfo]:
        """Get camera info by ID."""
        return self._cameras.get(camera_id)

    def add_ip_camera(self, url: str, name: str = None) -> CameraInfo:
        """Add an IP camera."""
        camera_id = max(self._cameras.keys()) + 1 if self._cameras else 100

        camera = CameraInfo(
            id=camera_id,
            name=name or f"IP Camera ({url})",
            type=CameraType.IP,
            width=1920,  # Will be updated on connect
            height=1080,
            fps=30.0,
            available=True,
            url=url,
        )

        self._cameras[camera_id] = camera
        return camera

    def open(self, camera_id: int = 0) -> bool:
        """
        Open a camera for capture.

        Args:
            camera_id: Camera ID to open

        Returns:
            True if successful
        """
        with self._lock:
            if self._capture is not None:
                self.close()

            camera = self._cameras.get(camera_id)
            if not camera:
                logger.error(f"Camera {camera_id} not found")
                return False

            if camera.type == CameraType.MOCK:
                self._active_camera = camera_id
                return True

            if not CV2_AVAILABLE:
                logger.error("OpenCV not available")
                return False

            # Open camera with timeout for IP cameras
            if camera.type == CameraType.IP:
                # Set timeout properties for network streams
                self._capture = cv2.VideoCapture(camera.url, cv2.CAP_FFMPEG)
                self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Give it up to 5 seconds to connect
                self._capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                self._capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
            else:
                self._capture = cv2.VideoCapture(camera_id)

            if not self._capture.isOpened():
                logger.error(f"Failed to open camera {camera_id}")
                self._capture = None
                return False

            # For IP cameras, verify we can actually get a frame
            if camera.type == CameraType.IP:
                ret, _ = self._capture.read()
                if not ret:
                    logger.error(f"Camera {camera_id} opened but no frames available")
                    self._capture.release()
                    self._capture = None
                    return False

            # Update camera info with actual values
            camera.width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            camera.height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            camera.fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0

            self._active_camera = camera_id
            logger.info(
                f"Opened camera {camera_id}: {camera.width}x{camera.height} @ {camera.fps}fps"
            )

            return True

    def close(self):
        """Close the active camera."""
        with self._lock:
            self.stop_stream()

            if self._capture is not None:
                self._capture.release()
                self._capture = None

            self._active_camera = None

    def get_frame(self) -> Optional["np.ndarray"]:
        """
        Get a single frame from the active camera.

        Returns:
            Frame as numpy array (BGR), or None if failed
        """
        camera = self._cameras.get(self._active_camera)
        if not camera:
            return None

        if camera.type == CameraType.MOCK:
            return self._generate_mock_frame(camera)

        with self._lock:
            if self._capture is None or not self._capture.isOpened():
                return None

            ret, frame = self._capture.read()

            if ret:
                self._last_frame = frame
                self._last_frame_time = time.time()
                self._frame_count += 1
                return frame

            return None

    def get_frame_jpeg(self, quality: int = 80) -> Optional[bytes]:
        """
        Get a frame as JPEG bytes.

        Args:
            quality: JPEG quality (1-100)

        Returns:
            JPEG bytes or None
        """
        frame = self.get_frame()

        if frame is None:
            return None

        if not CV2_AVAILABLE:
            return None

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, buffer = cv2.imencode(".jpg", frame, encode_param)

        return buffer.tobytes()

    def get_frame_base64(self, quality: int = 80) -> Optional[str]:
        """
        Get a frame as base64-encoded JPEG.

        Returns:
            Base64 string or None
        """
        jpeg_bytes = self.get_frame_jpeg(quality)

        if jpeg_bytes is None:
            return None

        return base64.b64encode(jpeg_bytes).decode("utf-8")

    def start_stream(self, callback: Callable[["np.ndarray"], None] = None):
        """
        Start continuous frame streaming.

        Args:
            callback: Function to call with each frame
        """
        if self._streaming:
            return

        if callback:
            self._frame_callbacks.append(callback)

        self._streaming = True
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()

    def stop_stream(self):
        """Stop frame streaming."""
        self._streaming = False

        if self._stream_thread:
            self._stream_thread.join(timeout=1.0)
            self._stream_thread = None

        self._frame_callbacks.clear()

    def _stream_loop(self):
        """Internal streaming loop."""
        camera = self._cameras.get(self._active_camera)
        if not camera:
            return

        target_interval = 1.0 / camera.fps

        while self._streaming:
            start_time = time.time()

            frame = self.get_frame()

            if frame is not None:
                for callback in self._frame_callbacks:
                    try:
                        callback(frame)
                    except Exception as e:
                        logger.error(f"Frame callback error: {e}")

            # Maintain frame rate
            elapsed = time.time() - start_time
            if elapsed < target_interval:
                time.sleep(target_interval - elapsed)

    def add_frame_callback(self, callback: Callable[["np.ndarray"], None]):
        """Add a callback for new frames."""
        self._frame_callbacks.append(callback)

    def remove_frame_callback(self, callback: Callable):
        """Remove a frame callback."""
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)

    def _generate_mock_frame(self, camera: CameraInfo) -> "np.ndarray":
        """Generate a mock frame for testing."""
        if not CV2_AVAILABLE or not np:
            return None

        # Create a gradient background
        frame = np.zeros((camera.height, camera.width, 3), dtype=np.uint8)

        # Gray gradient
        for y in range(camera.height):
            gray = int(100 + 50 * (y / camera.height))
            frame[y, :] = (gray, gray, gray)

        # Draw grid (simulating baseplate)
        grid_color = (80, 80, 80)
        cell_w = camera.width // 8
        cell_h = camera.height // 8

        for i in range(9):
            x = i * cell_w
            cv2.line(frame, (x, 0), (x, camera.height), grid_color, 1)

        for i in range(9):
            y = i * cell_h
            cv2.line(frame, (0, y), (camera.width, y), grid_color, 1)

        # Draw some mock bricks
        import random

        random.seed(int(time.time() * 10) % 100)  # Slow variation

        colors = [
            (0, 0, 200),  # Red (BGR)
            (200, 0, 0),  # Blue
            (0, 200, 200),  # Yellow
            (200, 200, 200),  # White
        ]

        for _ in range(5):
            x = random.randint(100, camera.width - 150)
            y = random.randint(100, camera.height - 100)
            w = random.randint(40, 80)
            h = random.randint(25, 50)
            color = random.choice(colors)

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (50, 50, 50), 2)

        # Add timestamp
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(
            frame,
            f"Mock Camera - {timestamp}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            frame,
            f"Frame: {self._frame_count}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
        )

        return frame

    def capture_image(self, filepath: str) -> bool:
        """
        Capture and save a single image.

        Args:
            filepath: Path to save the image

        Returns:
            True if successful
        """
        frame = self.get_frame()

        if frame is None:
            return False

        if not CV2_AVAILABLE:
            return False

        cv2.imwrite(filepath, frame)
        return True

    def set_resolution(self, width: int, height: int) -> bool:
        """Set camera resolution."""
        with self._lock:
            if self._capture is None:
                return False

            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Verify
            actual_w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if self._active_camera in self._cameras:
                self._cameras[self._active_camera].width = actual_w
                self._cameras[self._active_camera].height = actual_h

            return actual_w == width and actual_h == height

    def get_status(self) -> Dict[str, Any]:
        """Get camera manager status."""
        camera = self._cameras.get(self._active_camera)

        return {
            "available_cameras": len(self._cameras),
            "active_camera": self._active_camera,
            "camera_info": camera.to_dict() if camera else None,
            "streaming": self._streaming,
            "frame_count": self._frame_count,
            "last_frame_time": self._last_frame_time,
            "cv2_available": CV2_AVAILABLE,
        }


# Singleton instance
_camera_manager: Optional[CameraManager] = None


def get_camera_manager() -> CameraManager:
    """Get singleton camera manager."""
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = CameraManager()
    return _camera_manager
