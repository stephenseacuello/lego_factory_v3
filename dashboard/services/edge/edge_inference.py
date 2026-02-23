"""
Edge Inference Engine - Hardware-Aware Model Execution

LegoMCP World-Class Manufacturing System v6.0
Sprint 6: Edge Deployment & Hardware Optimization

This module provides edge-optimized inference with automatic hardware detection,
precision selection, and runtime optimization across multiple device types.

Supported Backends:
- CUDA/TensorRT: NVIDIA GPUs with FP16/INT8 optimization
- MPS/CoreML: Apple Silicon with Metal acceleration
- ONNX Runtime: Cross-platform CPU/GPU inference
- TFLite: Mobile and edge device optimization
- NCNN: High-performance neural network inference
"""

import asyncio
import hashlib
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from queue import Queue, Empty
import json

import numpy as np

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Supported device types for inference."""
    CUDA = "cuda"           # NVIDIA GPU with CUDA
    TENSORRT = "tensorrt"   # NVIDIA TensorRT optimization
    MPS = "mps"             # Apple Metal Performance Shaders
    COREML = "coreml"       # Apple CoreML
    ONNX_GPU = "onnx_gpu"   # ONNX Runtime with GPU
    ONNX_CPU = "onnx_cpu"   # ONNX Runtime CPU only
    TFLITE = "tflite"       # TensorFlow Lite
    NCNN = "ncnn"           # Tencent NCNN
    OPENVINO = "openvino"   # Intel OpenVINO
    CPU = "cpu"             # Pure CPU fallback


class PrecisionMode(Enum):
    """Model precision modes."""
    FP32 = "fp32"           # Full precision (32-bit float)
    FP16 = "fp16"           # Half precision (16-bit float)
    BF16 = "bf16"           # Brain floating point
    INT8 = "int8"           # 8-bit integer quantization
    INT4 = "int4"           # 4-bit integer quantization
    MIXED = "mixed"         # Mixed precision (FP16 compute, FP32 accumulate)


class InferenceStatus(Enum):
    """Inference execution status."""
    SUCCESS = auto()
    FAILED = auto()
    TIMEOUT = auto()
    OOM = auto()            # Out of memory
    DEVICE_UNAVAILABLE = auto()
    MODEL_NOT_LOADED = auto()
    INVALID_INPUT = auto()


@dataclass
class LatencyProfile:
    """Latency profiling data for inference."""
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0
    total_ms: float = 0.0
    device_transfer_ms: float = 0.0
    memory_mb: float = 0.0

    # Statistical data
    p50_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    p99_ms: Optional[float] = None

    @property
    def throughput_fps(self) -> float:
        """Calculate frames per second."""
        if self.total_ms > 0:
            return 1000.0 / self.total_ms
        return 0.0


@dataclass
class InferenceConfig:
    """Configuration for inference session."""
    model_path: str
    device_type: DeviceType = DeviceType.CPU
    precision: PrecisionMode = PrecisionMode.FP32

    # Performance settings
    batch_size: int = 1
    num_threads: int = 4
    enable_profiling: bool = False
    warmup_iterations: int = 3

    # Input settings
    input_size: Tuple[int, int] = (640, 640)
    normalize: bool = True
    mean: Tuple[float, ...] = (0.485, 0.456, 0.406)
    std: Tuple[float, ...] = (0.229, 0.224, 0.225)

    # Optimization settings
    enable_dynamic_batching: bool = False
    max_batch_wait_ms: float = 5.0
    enable_tensor_cores: bool = True
    enable_cudnn_benchmark: bool = True

    # Memory settings
    max_memory_mb: Optional[int] = None
    enable_memory_growth: bool = True

    # Fallback settings
    fallback_device: Optional[DeviceType] = DeviceType.CPU
    auto_fallback: bool = True


@dataclass
class InferenceResult:
    """Result of model inference."""
    outputs: Dict[str, np.ndarray]
    status: InferenceStatus
    latency: LatencyProfile
    device_used: DeviceType
    precision_used: PrecisionMode
    batch_size: int
    timestamp: datetime = field(default_factory=datetime.now)

    # Detection outputs (for object detection models)
    boxes: Optional[np.ndarray] = None
    scores: Optional[np.ndarray] = None
    classes: Optional[np.ndarray] = None

    # Classification outputs
    class_probs: Optional[np.ndarray] = None
    predicted_class: Optional[int] = None

    # Segmentation outputs
    masks: Optional[np.ndarray] = None

    # Error information
    error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status == InferenceStatus.SUCCESS

    def get_detections(self, confidence_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Get detections above confidence threshold."""
        if self.boxes is None or self.scores is None:
            return []

        detections = []
        for i, (box, score) in enumerate(zip(self.boxes, self.scores)):
            if score >= confidence_threshold:
                detection = {
                    "box": box.tolist(),
                    "score": float(score),
                    "class_id": int(self.classes[i]) if self.classes is not None else 0,
                }
                detections.append(detection)

        return detections


@dataclass
class InferenceBatch:
    """Batch of inputs for inference."""
    inputs: List[np.ndarray]
    metadata: List[Dict[str, Any]] = field(default_factory=list)
    priority: int = 0
    deadline_ms: Optional[float] = None
    callback: Optional[Callable[[List[InferenceResult]], None]] = None

    @property
    def size(self) -> int:
        return len(self.inputs)


class InferenceSession:
    """Manages an inference session for a specific model."""

    def __init__(
        self,
        config: InferenceConfig,
        session_id: Optional[str] = None
    ):
        self.config = config
        self.session_id = session_id or self._generate_session_id()
        self.model = None
        self.is_loaded = False
        self.device = config.device_type
        self.precision = config.precision

        # Statistics
        self._inference_count = 0
        self._total_latency_ms = 0.0
        self._latency_history: List[float] = []
        self._lock = threading.Lock()

        # Dynamic batching
        self._batch_queue: Queue = Queue()
        self._batch_thread: Optional[threading.Thread] = None
        self._stop_batching = threading.Event()

        logger.info(f"Created inference session {self.session_id}")

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        content = f"{self.config.model_path}:{time.time()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def load_model(self) -> bool:
        """Load model for inference."""
        try:
            logger.info(f"Loading model: {self.config.model_path}")

            # Detect available hardware
            self.device = self._detect_best_device()
            self.precision = self._select_precision()

            # Load model based on device type
            self.model = self._load_model_for_device()

            if self.model is None:
                logger.error("Failed to load model")
                return False

            # Warmup
            self._warmup()

            self.is_loaded = True
            logger.info(f"Model loaded on {self.device.value} with {self.precision.value}")

            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            if self.config.auto_fallback and self.config.fallback_device:
                logger.info(f"Falling back to {self.config.fallback_device.value}")
                self.config.device_type = self.config.fallback_device
                return self.load_model()
            return False

    def _detect_best_device(self) -> DeviceType:
        """Detect best available device for inference."""
        requested = self.config.device_type

        # Check CUDA availability
        if requested in (DeviceType.CUDA, DeviceType.TENSORRT):
            if self._is_cuda_available():
                if requested == DeviceType.TENSORRT and self._is_tensorrt_available():
                    return DeviceType.TENSORRT
                return DeviceType.CUDA

        # Check MPS availability (Apple Silicon)
        if requested in (DeviceType.MPS, DeviceType.COREML):
            if self._is_mps_available():
                return DeviceType.MPS

        # Check OpenVINO availability
        if requested == DeviceType.OPENVINO:
            if self._is_openvino_available():
                return DeviceType.OPENVINO

        # ONNX Runtime
        if requested in (DeviceType.ONNX_GPU, DeviceType.ONNX_CPU):
            return requested

        # Fallback to CPU
        logger.warning(f"Requested device {requested.value} not available, using CPU")
        return DeviceType.CPU

    def _select_precision(self) -> PrecisionMode:
        """Select best precision for device."""
        requested = self.config.precision

        # TensorRT supports all precisions
        if self.device == DeviceType.TENSORRT:
            return requested

        # CUDA supports FP32, FP16, and mixed
        if self.device == DeviceType.CUDA:
            if requested in (PrecisionMode.INT8, PrecisionMode.INT4):
                return PrecisionMode.FP16  # Fallback for non-TensorRT
            return requested

        # MPS supports FP32 and FP16
        if self.device == DeviceType.MPS:
            if requested in (PrecisionMode.INT8, PrecisionMode.INT4):
                return PrecisionMode.FP16
            return requested

        # CPU typically uses FP32
        if self.device == DeviceType.CPU:
            if requested != PrecisionMode.FP32:
                logger.info(f"Using FP32 for CPU (requested: {requested.value})")
            return PrecisionMode.FP32

        return PrecisionMode.FP32

    def _is_cuda_available(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            pass

        # Alternative check without PyTorch
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def _is_tensorrt_available(self) -> bool:
        """Check if TensorRT is available."""
        try:
            import tensorrt
            return True
        except ImportError:
            return False

    def _is_mps_available(self) -> bool:
        """Check if Apple MPS is available."""
        try:
            import torch
            return torch.backends.mps.is_available()
        except:
            return False

    def _is_openvino_available(self) -> bool:
        """Check if OpenVINO is available."""
        try:
            from openvino.runtime import Core
            return True
        except ImportError:
            return False

    def _load_model_for_device(self) -> Any:
        """Load model optimized for target device."""
        model_path = Path(self.config.model_path)

        if not model_path.exists():
            logger.error(f"Model file not found: {model_path}")
            return None

        try:
            # YOLO/Ultralytics models
            if model_path.suffix in ('.pt', '.pth'):
                return self._load_pytorch_model(model_path)

            # ONNX models
            elif model_path.suffix == '.onnx':
                return self._load_onnx_model(model_path)

            # TensorRT engines
            elif model_path.suffix in ('.engine', '.trt'):
                return self._load_tensorrt_model(model_path)

            # CoreML models
            elif model_path.suffix == '.mlmodel':
                return self._load_coreml_model(model_path)

            # TFLite models
            elif model_path.suffix == '.tflite':
                return self._load_tflite_model(model_path)

            else:
                logger.error(f"Unsupported model format: {model_path.suffix}")
                return None

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None

    def _load_pytorch_model(self, model_path: Path) -> Any:
        """Load PyTorch model."""
        try:
            import torch

            # Determine device string
            if self.device == DeviceType.CUDA:
                device = "cuda:0"
            elif self.device == DeviceType.MPS:
                device = "mps"
            else:
                device = "cpu"

            # Try loading as YOLO model
            try:
                from ultralytics import YOLO
                model = YOLO(str(model_path))
                model.to(device)

                # Set precision
                if self.precision == PrecisionMode.FP16 and device != "cpu":
                    model.model.half()

                return model
            except ImportError:
                pass

            # Load as generic PyTorch model
            model = torch.load(model_path, map_location=device)
            if hasattr(model, 'eval'):
                model.eval()

            return model

        except Exception as e:
            logger.error(f"Failed to load PyTorch model: {e}")
            return None

    def _load_onnx_model(self, model_path: Path) -> Any:
        """Load ONNX model with ONNX Runtime."""
        try:
            import onnxruntime as ort

            # Select execution provider
            providers = []
            if self.device in (DeviceType.CUDA, DeviceType.TENSORRT, DeviceType.ONNX_GPU):
                if 'CUDAExecutionProvider' in ort.get_available_providers():
                    providers.append('CUDAExecutionProvider')
                if 'TensorrtExecutionProvider' in ort.get_available_providers():
                    providers.insert(0, 'TensorrtExecutionProvider')

            if self.device == DeviceType.OPENVINO:
                if 'OpenVINOExecutionProvider' in ort.get_available_providers():
                    providers.append('OpenVINOExecutionProvider')

            # Always include CPU as fallback
            providers.append('CPUExecutionProvider')

            # Session options
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = self.config.num_threads

            if self.config.enable_profiling:
                sess_options.enable_profiling = True

            session = ort.InferenceSession(
                str(model_path),
                sess_options,
                providers=providers
            )

            logger.info(f"ONNX session using providers: {session.get_providers()}")

            return session

        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            return None

    def _load_tensorrt_model(self, model_path: Path) -> Any:
        """Load TensorRT engine."""
        try:
            import tensorrt as trt
            import pycuda.driver as cuda
            import pycuda.autoinit

            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)

            with open(model_path, 'rb') as f:
                engine_data = f.read()

            runtime = trt.Runtime(TRT_LOGGER)
            engine = runtime.deserialize_cuda_engine(engine_data)
            context = engine.create_execution_context()

            return {
                'engine': engine,
                'context': context,
                'runtime': runtime
            }

        except Exception as e:
            logger.error(f"Failed to load TensorRT engine: {e}")
            return None

    def _load_coreml_model(self, model_path: Path) -> Any:
        """Load CoreML model."""
        try:
            import coremltools as ct

            model = ct.models.MLModel(str(model_path))
            return model

        except Exception as e:
            logger.error(f"Failed to load CoreML model: {e}")
            return None

    def _load_tflite_model(self, model_path: Path) -> Any:
        """Load TensorFlow Lite model."""
        try:
            import tensorflow as tf

            interpreter = tf.lite.Interpreter(model_path=str(model_path))
            interpreter.allocate_tensors()

            return interpreter

        except Exception as e:
            logger.error(f"Failed to load TFLite model: {e}")
            return None

    def _warmup(self):
        """Warmup model with dummy inputs."""
        if not self.model:
            return

        logger.info(f"Warming up model with {self.config.warmup_iterations} iterations")

        # Create dummy input
        h, w = self.config.input_size
        dummy = np.random.randn(1, 3, h, w).astype(np.float32)

        for _ in range(self.config.warmup_iterations):
            try:
                self._run_inference(dummy)
            except Exception as e:
                logger.warning(f"Warmup iteration failed: {e}")

    def infer(
        self,
        inputs: Union[np.ndarray, List[np.ndarray]],
        preprocess: bool = True
    ) -> InferenceResult:
        """Run inference on inputs."""
        if not self.is_loaded:
            return InferenceResult(
                outputs={},
                status=InferenceStatus.MODEL_NOT_LOADED,
                latency=LatencyProfile(),
                device_used=self.device,
                precision_used=self.precision,
                batch_size=0,
                error_message="Model not loaded"
            )

        latency = LatencyProfile()
        start_time = time.perf_counter()

        try:
            # Ensure batch dimension
            if isinstance(inputs, np.ndarray):
                if inputs.ndim == 3:
                    inputs = np.expand_dims(inputs, 0)
                batch_inputs = inputs
            else:
                batch_inputs = np.stack(inputs)

            batch_size = batch_inputs.shape[0]

            # Preprocess
            preprocess_start = time.perf_counter()
            if preprocess:
                batch_inputs = self._preprocess(batch_inputs)
            latency.preprocess_ms = (time.perf_counter() - preprocess_start) * 1000

            # Inference
            inference_start = time.perf_counter()
            outputs = self._run_inference(batch_inputs)
            latency.inference_ms = (time.perf_counter() - inference_start) * 1000

            # Postprocess
            postprocess_start = time.perf_counter()
            processed_outputs = self._postprocess(outputs)
            latency.postprocess_ms = (time.perf_counter() - postprocess_start) * 1000

            latency.total_ms = (time.perf_counter() - start_time) * 1000

            # Update statistics
            self._update_statistics(latency.total_ms)

            # Build result
            result = InferenceResult(
                outputs=processed_outputs,
                status=InferenceStatus.SUCCESS,
                latency=latency,
                device_used=self.device,
                precision_used=self.precision,
                batch_size=batch_size
            )

            # Extract detection outputs if available
            if 'boxes' in processed_outputs:
                result.boxes = processed_outputs['boxes']
            if 'scores' in processed_outputs:
                result.scores = processed_outputs['scores']
            if 'classes' in processed_outputs:
                result.classes = processed_outputs['classes']
            if 'masks' in processed_outputs:
                result.masks = processed_outputs['masks']
            if 'class_probs' in processed_outputs:
                result.class_probs = processed_outputs['class_probs']
                result.predicted_class = int(np.argmax(result.class_probs))

            return result

        except Exception as e:
            logger.error(f"Inference failed: {e}")
            latency.total_ms = (time.perf_counter() - start_time) * 1000

            # Check for OOM
            if "out of memory" in str(e).lower() or "oom" in str(e).lower():
                status = InferenceStatus.OOM
            else:
                status = InferenceStatus.FAILED

            return InferenceResult(
                outputs={},
                status=status,
                latency=latency,
                device_used=self.device,
                precision_used=self.precision,
                batch_size=0,
                error_message=str(e)
            )

    def _preprocess(self, inputs: np.ndarray) -> np.ndarray:
        """Preprocess inputs for inference."""
        # Assume inputs are [B, H, W, C] or [B, C, H, W]
        if inputs.shape[-1] == 3:
            # Convert HWC to CHW
            inputs = np.transpose(inputs, (0, 3, 1, 2))

        # Resize if needed
        h, w = self.config.input_size
        if inputs.shape[2:] != (h, w):
            # Would use cv2.resize in production
            pass

        # Normalize
        if self.config.normalize:
            inputs = inputs.astype(np.float32) / 255.0
            mean = np.array(self.config.mean).reshape(1, 3, 1, 1)
            std = np.array(self.config.std).reshape(1, 3, 1, 1)
            inputs = (inputs - mean) / std

        # Convert precision
        if self.precision == PrecisionMode.FP16:
            inputs = inputs.astype(np.float16)

        return inputs

    def _run_inference(self, inputs: np.ndarray) -> Dict[str, np.ndarray]:
        """Run model inference."""
        if self.model is None:
            return {}

        # Handle different model types
        try:
            # Ultralytics YOLO
            if hasattr(self.model, 'predict'):
                results = self.model.predict(inputs, verbose=False)
                return self._parse_yolo_results(results)

            # ONNX Runtime
            if hasattr(self.model, 'run'):
                input_name = self.model.get_inputs()[0].name
                outputs = self.model.run(None, {input_name: inputs})
                output_names = [o.name for o in self.model.get_outputs()]
                return dict(zip(output_names, outputs))

            # TensorFlow Lite
            if hasattr(self.model, 'set_tensor'):
                input_details = self.model.get_input_details()
                output_details = self.model.get_output_details()

                self.model.set_tensor(input_details[0]['index'], inputs)
                self.model.invoke()

                outputs = {}
                for detail in output_details:
                    outputs[detail['name']] = self.model.get_tensor(detail['index'])
                return outputs

            # TensorRT
            if isinstance(self.model, dict) and 'engine' in self.model:
                return self._run_tensorrt_inference(inputs)

            # Generic PyTorch
            if hasattr(self.model, 'forward'):
                import torch
                with torch.no_grad():
                    tensor_input = torch.from_numpy(inputs)
                    if self.device == DeviceType.CUDA:
                        tensor_input = tensor_input.cuda()
                    elif self.device == DeviceType.MPS:
                        tensor_input = tensor_input.to('mps')

                    output = self.model(tensor_input)

                    if isinstance(output, torch.Tensor):
                        return {'output': output.cpu().numpy()}
                    elif isinstance(output, (tuple, list)):
                        return {f'output_{i}': o.cpu().numpy() for i, o in enumerate(output)}
                    else:
                        return {'output': output}

            logger.warning("Unknown model type, returning empty outputs")
            return {}

        except Exception as e:
            logger.error(f"Inference error: {e}")
            raise

    def _parse_yolo_results(self, results) -> Dict[str, np.ndarray]:
        """Parse Ultralytics YOLO results."""
        outputs = {}

        if results and len(results) > 0:
            result = results[0]

            if hasattr(result, 'boxes') and result.boxes is not None:
                boxes = result.boxes
                outputs['boxes'] = boxes.xyxy.cpu().numpy()
                outputs['scores'] = boxes.conf.cpu().numpy()
                outputs['classes'] = boxes.cls.cpu().numpy()

            if hasattr(result, 'masks') and result.masks is not None:
                outputs['masks'] = result.masks.data.cpu().numpy()

            if hasattr(result, 'probs') and result.probs is not None:
                outputs['class_probs'] = result.probs.data.cpu().numpy()

        return outputs

    def _run_tensorrt_inference(self, inputs: np.ndarray) -> Dict[str, np.ndarray]:
        """Run TensorRT inference."""
        import pycuda.driver as cuda

        engine = self.model['engine']
        context = self.model['context']

        # Allocate buffers
        bindings = []
        outputs = {}

        for i in range(engine.num_bindings):
            name = engine.get_binding_name(i)
            dtype = engine.get_binding_dtype(i)
            shape = engine.get_binding_shape(i)

            size = np.prod(shape)

            if engine.binding_is_input(i):
                # Input binding
                d_input = cuda.mem_alloc(inputs.nbytes)
                cuda.memcpy_htod(d_input, inputs)
                bindings.append(int(d_input))
            else:
                # Output binding
                h_output = np.empty(shape, dtype=np.float32)
                d_output = cuda.mem_alloc(h_output.nbytes)
                bindings.append(int(d_output))
                outputs[name] = (h_output, d_output)

        # Execute
        context.execute_v2(bindings)

        # Copy outputs back
        result = {}
        for name, (h_output, d_output) in outputs.items():
            cuda.memcpy_dtoh(h_output, d_output)
            result[name] = h_output

        return result

    def _postprocess(self, outputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Postprocess model outputs."""
        # Apply NMS if detection outputs
        if 'boxes' in outputs and 'scores' in outputs:
            outputs = self._apply_nms(outputs)

        return outputs

    def _apply_nms(
        self,
        outputs: Dict[str, np.ndarray],
        iou_threshold: float = 0.45,
        score_threshold: float = 0.25
    ) -> Dict[str, np.ndarray]:
        """Apply Non-Maximum Suppression to detections."""
        boxes = outputs.get('boxes', np.array([]))
        scores = outputs.get('scores', np.array([]))
        classes = outputs.get('classes', np.array([]))

        if len(boxes) == 0:
            return outputs

        # Filter by score
        mask = scores >= score_threshold
        boxes = boxes[mask]
        scores = scores[mask]
        classes = classes[mask]

        if len(boxes) == 0:
            outputs['boxes'] = np.array([])
            outputs['scores'] = np.array([])
            outputs['classes'] = np.array([])
            return outputs

        # Simple NMS implementation
        keep = []
        order = np.argsort(scores)[::-1]

        while len(order) > 0:
            i = order[0]
            keep.append(i)

            if len(order) == 1:
                break

            xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
            yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
            xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
            yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)
            intersection = w * h

            area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
            area_order = (boxes[order[1:], 2] - boxes[order[1:], 0]) * (boxes[order[1:], 3] - boxes[order[1:], 1])

            iou = intersection / (area_i + area_order - intersection + 1e-6)

            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        outputs['boxes'] = boxes[keep]
        outputs['scores'] = scores[keep]
        outputs['classes'] = classes[keep]

        return outputs

    def _update_statistics(self, latency_ms: float):
        """Update inference statistics."""
        with self._lock:
            self._inference_count += 1
            self._total_latency_ms += latency_ms
            self._latency_history.append(latency_ms)

            # Keep only last 1000 entries
            if len(self._latency_history) > 1000:
                self._latency_history = self._latency_history[-1000:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get inference statistics."""
        with self._lock:
            if not self._latency_history:
                return {
                    "inference_count": 0,
                    "avg_latency_ms": 0,
                    "throughput_fps": 0
                }

            latencies = np.array(self._latency_history)
            avg_latency = np.mean(latencies)

            return {
                "inference_count": self._inference_count,
                "avg_latency_ms": float(avg_latency),
                "min_latency_ms": float(np.min(latencies)),
                "max_latency_ms": float(np.max(latencies)),
                "p50_latency_ms": float(np.percentile(latencies, 50)),
                "p95_latency_ms": float(np.percentile(latencies, 95)),
                "p99_latency_ms": float(np.percentile(latencies, 99)),
                "throughput_fps": 1000.0 / avg_latency if avg_latency > 0 else 0,
                "device": self.device.value,
                "precision": self.precision.value
            }

    def unload(self):
        """Unload model and free resources."""
        self._stop_batching.set()

        if self._batch_thread and self._batch_thread.is_alive():
            self._batch_thread.join(timeout=5.0)

        self.model = None
        self.is_loaded = False

        # Clear GPU memory
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass

        logger.info(f"Unloaded inference session {self.session_id}")


class EdgeInference:
    """
    Edge Inference Engine - Hardware-aware inference with automatic optimization.

    Features:
    - Automatic hardware detection (CUDA, MPS, CPU, etc.)
    - Dynamic precision selection (FP32, FP16, INT8)
    - Model caching and session management
    - Dynamic batching for throughput optimization
    - Fallback handling for device unavailability
    """

    def __init__(
        self,
        models_dir: Optional[str] = None,
        cache_size: int = 5,
        default_device: DeviceType = DeviceType.CPU
    ):
        self.models_dir = Path(models_dir) if models_dir else Path("models")
        self.cache_size = cache_size
        self.default_device = default_device

        # Session management
        self._sessions: Dict[str, InferenceSession] = {}
        self._session_order: List[str] = []  # LRU order
        self._lock = threading.Lock()

        # Hardware info
        self._available_devices = self._detect_available_devices()

        logger.info(f"EdgeInference initialized with devices: {[d.value for d in self._available_devices]}")

    def _detect_available_devices(self) -> List[DeviceType]:
        """Detect available inference devices."""
        devices = [DeviceType.CPU]  # Always available

        # Check CUDA
        try:
            import torch
            if torch.cuda.is_available():
                devices.append(DeviceType.CUDA)

                # Check TensorRT
                try:
                    import tensorrt
                    devices.append(DeviceType.TENSORRT)
                except ImportError:
                    pass
        except ImportError:
            pass

        # Check MPS (Apple Silicon)
        try:
            import torch
            if torch.backends.mps.is_available():
                devices.append(DeviceType.MPS)
        except:
            pass

        # Check OpenVINO
        try:
            from openvino.runtime import Core
            devices.append(DeviceType.OPENVINO)
        except ImportError:
            pass

        # ONNX Runtime is typically available if installed
        try:
            import onnxruntime
            devices.append(DeviceType.ONNX_CPU)
            if 'CUDAExecutionProvider' in onnxruntime.get_available_providers():
                devices.append(DeviceType.ONNX_GPU)
        except ImportError:
            pass

        return devices

    @property
    def available_devices(self) -> List[DeviceType]:
        """Get list of available devices."""
        return self._available_devices.copy()

    def get_best_device(self) -> DeviceType:
        """Get best available device for inference."""
        priority = [
            DeviceType.TENSORRT,
            DeviceType.CUDA,
            DeviceType.MPS,
            DeviceType.ONNX_GPU,
            DeviceType.OPENVINO,
            DeviceType.ONNX_CPU,
            DeviceType.CPU
        ]

        for device in priority:
            if device in self._available_devices:
                return device

        return DeviceType.CPU

    def create_session(
        self,
        model_path: str,
        config: Optional[InferenceConfig] = None
    ) -> InferenceSession:
        """Create new inference session for a model."""
        if config is None:
            config = InferenceConfig(
                model_path=model_path,
                device_type=self.get_best_device()
            )
        else:
            config.model_path = model_path

        session = InferenceSession(config)

        if session.load_model():
            with self._lock:
                # Add to cache
                self._sessions[session.session_id] = session
                self._session_order.append(session.session_id)

                # Evict oldest if cache full
                while len(self._sessions) > self.cache_size:
                    oldest_id = self._session_order.pop(0)
                    oldest = self._sessions.pop(oldest_id)
                    oldest.unload()

            return session
        else:
            raise RuntimeError(f"Failed to load model: {model_path}")

    def get_session(self, session_id: str) -> Optional[InferenceSession]:
        """Get existing inference session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                # Update LRU order
                self._session_order.remove(session_id)
                self._session_order.append(session_id)
            return session

    def infer(
        self,
        model_path: str,
        inputs: Union[np.ndarray, List[np.ndarray]],
        config: Optional[InferenceConfig] = None
    ) -> InferenceResult:
        """Run inference on inputs using specified model."""
        # Check if session exists
        model_hash = hashlib.md5(model_path.encode()).hexdigest()[:12]
        session = None

        with self._lock:
            for sid, sess in self._sessions.items():
                if sess.config.model_path == model_path:
                    session = sess
                    break

        # Create session if needed
        if session is None:
            session = self.create_session(model_path, config)

        return session.infer(inputs)

    async def infer_async(
        self,
        model_path: str,
        inputs: Union[np.ndarray, List[np.ndarray]],
        config: Optional[InferenceConfig] = None
    ) -> InferenceResult:
        """Async inference for non-blocking execution."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.infer(model_path, inputs, config)
        )

    def infer_batch(
        self,
        model_path: str,
        batch: InferenceBatch,
        config: Optional[InferenceConfig] = None
    ) -> List[InferenceResult]:
        """Run inference on a batch of inputs."""
        results = []

        # Stack inputs if possible
        try:
            stacked = np.stack(batch.inputs)
            result = self.infer(model_path, stacked, config)

            # Split results back to individual
            for i in range(batch.size):
                individual_result = InferenceResult(
                    outputs={k: v[i:i+1] if v.ndim > 0 else v for k, v in result.outputs.items()},
                    status=result.status,
                    latency=result.latency,
                    device_used=result.device_used,
                    precision_used=result.precision_used,
                    batch_size=1
                )
                results.append(individual_result)

        except Exception as e:
            # Fall back to individual inference
            for inp in batch.inputs:
                result = self.infer(model_path, inp, config)
                results.append(result)

        # Execute callback if provided
        if batch.callback:
            batch.callback(results)

        return results

    def get_hardware_info(self) -> Dict[str, Any]:
        """Get detailed hardware information."""
        info = {
            "available_devices": [d.value for d in self._available_devices],
            "best_device": self.get_best_device().value,
            "active_sessions": len(self._sessions),
            "cuda": {},
            "mps": {},
            "cpu": {}
        }

        # CUDA info
        try:
            import torch
            if torch.cuda.is_available():
                info["cuda"] = {
                    "available": True,
                    "device_count": torch.cuda.device_count(),
                    "current_device": torch.cuda.current_device(),
                    "device_name": torch.cuda.get_device_name(0),
                    "memory_total_gb": torch.cuda.get_device_properties(0).total_memory / (1024**3),
                    "memory_allocated_gb": torch.cuda.memory_allocated(0) / (1024**3),
                    "memory_cached_gb": torch.cuda.memory_reserved(0) / (1024**3),
                    "cuda_version": torch.version.cuda
                }
        except:
            info["cuda"]["available"] = False

        # MPS info
        try:
            import torch
            info["mps"] = {
                "available": torch.backends.mps.is_available(),
                "built": torch.backends.mps.is_built()
            }
        except:
            info["mps"]["available"] = False

        # CPU info
        import multiprocessing
        info["cpu"] = {
            "cores": multiprocessing.cpu_count(),
        }

        return info

    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all active sessions."""
        stats = {}
        with self._lock:
            for session_id, session in self._sessions.items():
                stats[session_id] = session.get_statistics()
        return stats

    def clear_cache(self):
        """Clear all cached sessions."""
        with self._lock:
            for session in self._sessions.values():
                session.unload()
            self._sessions.clear()
            self._session_order.clear()

        logger.info("Cleared all inference sessions")

    def close(self):
        """Close edge inference engine and free resources."""
        self.clear_cache()
        logger.info("EdgeInference closed")


# Singleton instance
_edge_inference: Optional[EdgeInference] = None


def get_edge_inference() -> EdgeInference:
    """Get singleton EdgeInference instance."""
    global _edge_inference
    if _edge_inference is None:
        _edge_inference = EdgeInference()
    return _edge_inference
