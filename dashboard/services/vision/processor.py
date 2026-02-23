"""
Vision Processing Service Entry Point

LegoMCP World-Class Manufacturing Platform v2.0
ISO 23247 Compliant Digital Twin Implementation

Background service for real-time vision processing:
- Camera stream ingestion
- Defect detection
- Layer inspection
- 3D defect mapping
- Quality monitoring

Usage:
    python -m dashboard.services.vision.processor

Author: LegoMCP Team
Version: 2.0.0
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed")

# Try to import OpenCV
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("opencv-python not installed")

# Import vision services
try:
    from .defect_mapping_3d import (
        DefectMapping3DService,
        get_defect_mapping_service,
        Defect2D,
        DefectType,
        DefectSeverity,
    )
    DEFECT_MAPPING_AVAILABLE = True
except ImportError as e:
    DEFECT_MAPPING_AVAILABLE = False
    logger.warning(f"Defect mapping not available: {e}")

# Import defect detector if available
try:
    from .defect_detector import DefectDetector
    DEFECT_DETECTOR_AVAILABLE = True
except ImportError:
    DEFECT_DETECTOR_AVAILABLE = False

# Import layer inspector if available
try:
    from .layer_inspector import LayerInspector
    LAYER_INSPECTOR_AVAILABLE = True
except ImportError:
    LAYER_INSPECTOR_AVAILABLE = False


class VisionProcessor:
    """
    Real-time vision processing service.

    Handles:
    - Camera stream ingestion (USB, IP, RTSP)
    - Frame preprocessing
    - Defect detection
    - Layer inspection
    - 3D defect mapping
    - Result publishing
    """

    def __init__(
        self,
        camera_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        processing_fps: float = 10.0
    ):
        self.camera_url = camera_url or os.getenv("CAMERA_STREAM_URL", "")
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.processing_fps = processing_fps

        # Services
        self.defect_mapping: Optional[DefectMapping3DService] = None
        self.defect_detector = None
        self.layer_inspector = None
        self.redis_client = None

        # Camera
        self.camera = None
        self.camera_id = "main_camera"

        # Processing state
        self.running = False
        self.current_layer = 0
        self.frame_count = 0

        # Detection settings
        self.defect_detection_enabled = os.getenv("DEFECT_DETECTION_ENABLED", "true").lower() == "true"
        self.layer_inspection_enabled = os.getenv("LAYER_INSPECTION_ENABLED", "true").lower() == "true"

        # Statistics
        self.stats = {
            "frames_processed": 0,
            "defects_detected": 0,
            "layers_inspected": 0,
            "errors": 0,
            "avg_processing_time_ms": 0.0,
            "start_time": None,
        }

        # Processing time tracking
        self._processing_times: List[float] = []
        self._max_time_samples = 100

    async def initialize(self) -> None:
        """Initialize services and connections."""
        logger.info("Initializing Vision Processor...")

        # Initialize defect mapping
        if DEFECT_MAPPING_AVAILABLE:
            self.defect_mapping = get_defect_mapping_service()
            self.defect_mapping.setup_default_cameras()
            logger.info("Defect mapping service initialized")

        # Initialize defect detector
        if DEFECT_DETECTOR_AVAILABLE:
            try:
                self.defect_detector = DefectDetector()
                logger.info("Defect detector initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize defect detector: {e}")

        # Initialize layer inspector
        if LAYER_INSPECTOR_AVAILABLE:
            try:
                self.layer_inspector = LayerInspector()
                logger.info("Layer inspector initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize layer inspector: {e}")

        # Initialize Redis
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(self.redis_url)
                self.redis_client.ping()
                logger.info(f"Connected to Redis")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self.redis_client = None

        # Initialize camera
        if self.camera_url and CV2_AVAILABLE:
            await self.init_camera()
        else:
            logger.info("Running in simulation mode (no camera)")

    async def init_camera(self) -> bool:
        """Initialize camera capture."""
        try:
            # Try to parse as integer for USB camera
            if self.camera_url.isdigit():
                self.camera = cv2.VideoCapture(int(self.camera_url))
            else:
                # URL-based camera (IP, RTSP, etc.)
                self.camera = cv2.VideoCapture(self.camera_url)

            if self.camera.isOpened():
                logger.info(f"Camera initialized: {self.camera_url}")
                return True
            else:
                logger.error(f"Failed to open camera: {self.camera_url}")
                return False

        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            return False

    async def process_frame(self, frame: Any) -> Dict[str, Any]:
        """Process a single frame."""
        start_time = time.time()
        results = {
            "frame_id": self.frame_count,
            "timestamp": datetime.utcnow().isoformat(),
            "detections": [],
            "layer_info": None,
        }

        try:
            # Defect detection
            if self.defect_detection_enabled and self.defect_detector:
                detections = await self.detect_defects(frame)
                results["detections"] = detections

                # Map to 3D
                if self.defect_mapping:
                    for det in detections:
                        defect_3d = self.defect_mapping.map_detection_to_3d(det)
                        if defect_3d:
                            self.stats["defects_detected"] += 1

            # Layer inspection
            if self.layer_inspection_enabled and self.layer_inspector:
                layer_info = await self.inspect_layer(frame)
                results["layer_info"] = layer_info
                self.stats["layers_inspected"] += 1

        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            self.stats["errors"] += 1

        # Track processing time
        processing_time = (time.time() - start_time) * 1000
        self._processing_times.append(processing_time)
        if len(self._processing_times) > self._max_time_samples:
            self._processing_times.pop(0)
        self.stats["avg_processing_time_ms"] = sum(self._processing_times) / len(self._processing_times)

        self.stats["frames_processed"] += 1

        return results

    async def detect_defects(self, frame: Any) -> List[Defect2D]:
        """Run defect detection on a frame."""
        detections = []

        if self.defect_detector:
            try:
                # Run detector
                raw_detections = self.defect_detector.detect(frame)

                for det in raw_detections:
                    defect = Defect2D(
                        detection_id=f"det_{self.frame_count}_{len(detections)}",
                        camera_id=self.camera_id,
                        defect_type=DefectType[det.get("type", "UNKNOWN").upper()],
                        confidence=det.get("confidence", 0.5),
                        bbox_x=det.get("x", 0.5),
                        bbox_y=det.get("y", 0.5),
                        bbox_width=det.get("width", 0.1),
                        bbox_height=det.get("height", 0.1),
                        layer_number=self.current_layer,
                    )
                    detections.append(defect)

            except Exception as e:
                logger.error(f"Defect detection error: {e}")

        return detections

    async def inspect_layer(self, frame: Any) -> Optional[Dict[str, Any]]:
        """Run layer inspection on a frame."""
        if self.layer_inspector:
            try:
                result = self.layer_inspector.inspect(frame, self.current_layer)
                return result
            except Exception as e:
                logger.error(f"Layer inspection error: {e}")
        return None

    async def simulate_detection(self) -> List[Defect2D]:
        """Simulate defect detection for testing."""
        import random

        detections = []

        # Random chance of detection
        if random.random() < 0.1:  # 10% chance per frame
            defect_types = list(DefectType)
            defect_type = random.choice(defect_types)

            defect = Defect2D(
                detection_id=f"sim_det_{self.frame_count}",
                camera_id=self.camera_id,
                defect_type=defect_type,
                confidence=0.5 + random.random() * 0.4,
                bbox_x=random.random() * 0.8 + 0.1,
                bbox_y=random.random() * 0.8 + 0.1,
                bbox_width=0.05 + random.random() * 0.1,
                bbox_height=0.05 + random.random() * 0.1,
                layer_number=self.current_layer,
            )
            detections.append(defect)

            # Map to 3D
            if self.defect_mapping:
                defect_3d = self.defect_mapping.map_detection_to_3d(defect)
                if defect_3d:
                    self.stats["defects_detected"] += 1
                    logger.info(
                        f"Simulated defect: {defect_type.name} at layer {self.current_layer}"
                    )

        return detections

    async def publish_results(self, results: Dict[str, Any]) -> None:
        """Publish processing results to Redis."""
        if self.redis_client:
            try:
                # Publish to channel
                self.redis_client.publish(
                    "vision:results",
                    json.dumps(results, default=str)
                )

                # Store latest result
                self.redis_client.setex(
                    "vision:latest_result",
                    60,
                    json.dumps(results, default=str)
                )

                # Store defect summary
                if self.defect_mapping:
                    summary = self.defect_mapping.get_defect_summary()
                    self.redis_client.set(
                        "vision:defect_summary",
                        json.dumps(summary)
                    )

            except Exception as e:
                logger.warning(f"Failed to publish results: {e}")

    async def publish_health_status(self) -> None:
        """Publish worker health status."""
        if self.redis_client:
            try:
                status = {
                    "worker": "vision_processor",
                    "status": "healthy" if self.running else "stopped",
                    "stats": self.stats,
                    "current_layer": self.current_layer,
                    "camera_connected": self.camera is not None and self.camera.isOpened() if CV2_AVAILABLE else False,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                self.redis_client.setex(
                    "worker:vision_processor:health",
                    60,
                    json.dumps(status)
                )
            except Exception as e:
                logger.warning(f"Failed to publish health status: {e}")

    async def subscribe_to_layer_updates(self) -> None:
        """Subscribe to layer update notifications."""
        if self.redis_client:
            try:
                pubsub = self.redis_client.pubsub()
                pubsub.subscribe("print:layer_change")

                for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            new_layer = data.get("layer", self.current_layer)
                            if new_layer != self.current_layer:
                                self.current_layer = new_layer
                                if self.defect_mapping:
                                    self.defect_mapping.set_current_layer(new_layer)
                                logger.info(f"Layer updated to {new_layer}")
                        except Exception as e:
                            logger.warning(f"Failed to process layer update: {e}")

            except Exception as e:
                logger.warning(f"Layer subscription error: {e}")

    async def run(self) -> None:
        """Main processing loop."""
        self.running = True
        self.stats["start_time"] = datetime.utcnow().isoformat()

        await self.initialize()

        frame_interval = 1.0 / self.processing_fps
        logger.info(f"Vision Processor started. FPS: {self.processing_fps}")

        # Start layer subscription in background
        asyncio.create_task(self.subscribe_to_layer_updates())

        while self.running:
            try:
                cycle_start = time.time()

                # Capture or simulate frame
                if self.camera and CV2_AVAILABLE:
                    ret, frame = self.camera.read()
                    if ret:
                        results = await self.process_frame(frame)
                    else:
                        logger.warning("Failed to capture frame")
                        await asyncio.sleep(1.0)
                        continue
                else:
                    # Simulation mode
                    await self.simulate_detection()
                    results = {
                        "frame_id": self.frame_count,
                        "timestamp": datetime.utcnow().isoformat(),
                        "mode": "simulation",
                    }

                self.frame_count += 1

                # Publish results
                await self.publish_results(results)

                # Publish health every 10 frames
                if self.frame_count % 10 == 0:
                    await self.publish_health_status()

                # Maintain frame rate
                elapsed = time.time() - cycle_start
                if elapsed < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Processing error: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(1.0)

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down Vision Processor...")
        self.running = False

        # Release camera
        if self.camera and CV2_AVAILABLE:
            self.camera.release()

        # Clear health status
        if self.redis_client:
            try:
                self.redis_client.delete("worker:vision_processor:health")
            except Exception:
                pass

        # Export final defect report
        if self.defect_mapping:
            export = self.defect_mapping.export_for_unity()
            logger.info(f"Final defect summary: {export['summary']}")

        logger.info("Vision Processor shutdown complete")


async def main():
    """Main entry point."""
    camera_url = os.getenv("CAMERA_STREAM_URL", "")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    processing_fps = float(os.getenv("VISION_FPS", "10"))

    processor = VisionProcessor(
        camera_url=camera_url,
        redis_url=redis_url,
        processing_fps=processing_fps
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(processor.shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    try:
        await processor.run()
    except KeyboardInterrupt:
        await processor.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
