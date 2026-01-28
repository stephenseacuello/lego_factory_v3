"""
Camera Service for Vision Features.

Provides:
- Camera device management
- Image capture
- Video streaming
- Frame processing
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Callable, AsyncIterator
from datetime import datetime
from enum import Enum
import io

logger = logging.getLogger(__name__)


class CameraState(Enum):
    """Camera states."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    STREAMING = "streaming"
    CAPTURING = "capturing"
    ERROR = "error"


@dataclass
class CameraConfig:
    """Camera configuration."""
    device_id: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    auto_exposure: bool = True
    exposure: int = -6  # Manual exposure value
    auto_focus: bool = True
    focus: int = 0      # Manual focus value


@dataclass
class CapturedImage:
    """A captured image."""
    data: bytes
    format: str = "jpeg"
    width: int = 0
    height: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


class CameraService:
    """
    Manages camera devices for vision features.

    Features:
    - Multi-camera support
    - Image capture
    - Video streaming
    - Frame callbacks
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        """Initialize camera service."""
        self.config = config or CameraConfig()
        self._state = CameraState.DISCONNECTED
        self._capture = None
        self._streaming = False
        self._frame_callbacks: List[Callable] = []

    @property
    def state(self) -> CameraState:
        """Get current camera state."""
        return self._state

    def connect(self) -> bool:
        """
        Connect to the camera device.

        Returns:
            True if connected successfully
        """
        try:
            import cv2

            self._capture = cv2.VideoCapture(self.config.device_id)

            if not self._capture.isOpened():
                logger.error(f"Failed to open camera {self.config.device_id}")
                self._state = CameraState.ERROR
                return False

            # Configure camera
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.config.fps)

            if not self.config.auto_exposure:
                self._capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
                self._capture.set(cv2.CAP_PROP_EXPOSURE, self.config.exposure)

            if not self.config.auto_focus:
                self._capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                self._capture.set(cv2.CAP_PROP_FOCUS, self.config.focus)

            self._state = CameraState.CONNECTED
            logger.info(f"Camera {self.config.device_id} connected")
            return True

        except ImportError:
            logger.error("opencv-python not installed")
            self._state = CameraState.ERROR
            return False
        except Exception as e:
            logger.error(f"Camera connection error: {e}")
            self._state = CameraState.ERROR
            return False

    def disconnect(self):
        """Disconnect from the camera."""
        if self._capture:
            self._capture.release()
            self._capture = None
        self._state = CameraState.DISCONNECTED
        logger.info("Camera disconnected")

    def capture(self, format: str = "jpeg", quality: int = 90) -> Optional[CapturedImage]:
        """
        Capture a single frame.

        Args:
            format: Image format (jpeg, png)
            quality: JPEG quality (0-100)

        Returns:
            Captured image or None if failed
        """
        if self._state not in [CameraState.CONNECTED, CameraState.STREAMING]:
            if not self.connect():
                return None

        try:
            import cv2
            import numpy as np

            self._state = CameraState.CAPTURING

            ret, frame = self._capture.read()

            if not ret:
                logger.error("Failed to capture frame")
                return None

            # Encode frame
            if format.lower() == "png":
                success, buffer = cv2.imencode(".png", frame)
            else:
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                success, buffer = cv2.imencode(".jpg", frame, encode_params)

            if not success:
                logger.error("Failed to encode frame")
                return None

            self._state = CameraState.CONNECTED

            return CapturedImage(
                data=buffer.tobytes(),
                format=format,
                width=frame.shape[1],
                height=frame.shape[0],
                metadata={
                    "device_id": self.config.device_id,
                    "quality": quality if format == "jpeg" else None,
                },
            )

        except Exception as e:
            logger.error(f"Capture error: {e}")
            self._state = CameraState.ERROR
            return None

    async def stream_frames(
        self,
        format: str = "jpeg",
        quality: int = 80,
    ) -> AsyncIterator[CapturedImage]:
        """
        Stream frames from the camera.

        Args:
            format: Image format
            quality: JPEG quality

        Yields:
            Captured images
        """
        if self._state == CameraState.DISCONNECTED:
            if not self.connect():
                return

        self._streaming = True
        self._state = CameraState.STREAMING

        try:
            import cv2

            while self._streaming:
                ret, frame = self._capture.read()

                if not ret:
                    await asyncio.sleep(0.01)
                    continue

                # Encode frame
                if format.lower() == "png":
                    success, buffer = cv2.imencode(".png", frame)
                else:
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                    success, buffer = cv2.imencode(".jpg", frame, encode_params)

                if success:
                    image = CapturedImage(
                        data=buffer.tobytes(),
                        format=format,
                        width=frame.shape[1],
                        height=frame.shape[0],
                    )

                    # Call frame callbacks
                    for callback in self._frame_callbacks:
                        try:
                            callback(image)
                        except Exception as e:
                            logger.error(f"Frame callback error: {e}")

                    yield image

                # Control frame rate
                await asyncio.sleep(1.0 / self.config.fps)

        except Exception as e:
            logger.error(f"Streaming error: {e}")

        finally:
            self._streaming = False
            self._state = CameraState.CONNECTED

    def stop_streaming(self):
        """Stop the video stream."""
        self._streaming = False

    def register_frame_callback(self, callback: Callable[[CapturedImage], None]):
        """Register a callback for frame capture."""
        self._frame_callbacks.append(callback)

    def get_available_cameras(self) -> List[dict]:
        """
        Get list of available cameras.

        Returns:
            List of camera info dictionaries
        """
        cameras = []

        try:
            import cv2

            # Check first 10 device IDs
            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = int(cap.get(cv2.CAP_PROP_FPS))

                    cameras.append({
                        "device_id": i,
                        "width": width,
                        "height": height,
                        "fps": fps,
                        "name": f"Camera {i}",
                    })
                    cap.release()

        except ImportError:
            logger.warning("opencv-python not installed")
        except Exception as e:
            logger.error(f"Error listing cameras: {e}")

        return cameras

    def set_exposure(self, exposure: int):
        """Set manual exposure value."""
        if self._capture:
            import cv2
            self._capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            self._capture.set(cv2.CAP_PROP_EXPOSURE, exposure)
            self.config.exposure = exposure
            self.config.auto_exposure = False

    def set_auto_exposure(self, enabled: bool = True):
        """Enable/disable auto exposure."""
        if self._capture:
            import cv2
            self._capture.set(
                cv2.CAP_PROP_AUTO_EXPOSURE,
                0.75 if enabled else 0.25
            )
            self.config.auto_exposure = enabled

    def set_focus(self, focus: int):
        """Set manual focus value."""
        if self._capture:
            import cv2
            self._capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self._capture.set(cv2.CAP_PROP_FOCUS, focus)
            self.config.focus = focus
            self.config.auto_focus = False

    def set_auto_focus(self, enabled: bool = True):
        """Enable/disable auto focus."""
        if self._capture:
            import cv2
            self._capture.set(cv2.CAP_PROP_AUTOFOCUS, 1 if enabled else 0)
            self.config.auto_focus = enabled


class ImagePreprocessor:
    """
    Preprocesses images for better analysis.

    Applies:
    - Rotation/orientation correction
    - Brightness/contrast adjustment
    - Noise reduction
    - Edge enhancement
    """

    @staticmethod
    def auto_orient(image_data: bytes) -> bytes:
        """Auto-orient image based on EXIF data."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            import io

            image = Image.open(io.BytesIO(image_data))

            # Get EXIF orientation
            exif = image._getexif()
            if exif:
                for tag_id, value in exif.items():
                    if TAGS.get(tag_id) == "Orientation":
                        if value == 3:
                            image = image.rotate(180)
                        elif value == 6:
                            image = image.rotate(270)
                        elif value == 8:
                            image = image.rotate(90)
                        break

            output = io.BytesIO()
            image.save(output, format="JPEG", quality=95)
            return output.getvalue()

        except Exception as e:
            logger.warning(f"Auto-orient failed: {e}")
            return image_data

    @staticmethod
    def enhance_for_ocr(image_data: bytes) -> bytes:
        """Enhance image for better OCR results."""
        try:
            import cv2
            import numpy as np

            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Apply adaptive thresholding
            enhanced = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            # Denoise
            enhanced = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)

            # Encode back
            success, buffer = cv2.imencode(".png", enhanced)
            if success:
                return buffer.tobytes()

            return image_data

        except Exception as e:
            logger.warning(f"OCR enhancement failed: {e}")
            return image_data

    @staticmethod
    def enhance_for_inspection(image_data: bytes) -> bytes:
        """Enhance image for defect detection."""
        try:
            import cv2
            import numpy as np

            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Increase contrast
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)

            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)

            lab = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

            # Sharpen
            kernel = np.array([[-1, -1, -1],
                               [-1, 9, -1],
                               [-1, -1, -1]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)

            success, buffer = cv2.imencode(".jpg", enhanced, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if success:
                return buffer.tobytes()

            return image_data

        except Exception as e:
            logger.warning(f"Inspection enhancement failed: {e}")
            return image_data

    @staticmethod
    def crop_to_region(
        image_data: bytes,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> bytes:
        """Crop image to a specific region."""
        try:
            import cv2
            import numpy as np

            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            cropped = image[y:y + height, x:x + width]

            success, buffer = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if success:
                return buffer.tobytes()

            return image_data

        except Exception as e:
            logger.warning(f"Crop failed: {e}")
            return image_data
