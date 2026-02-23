"""
Device Registry - Multi-Device Management and Orchestration

LegoMCP World-Class Manufacturing System v6.0
Sprint 6: Edge Deployment & Hardware Optimization

This module provides comprehensive device management for edge inference:
- Device discovery and registration
- Capability profiling
- Resource monitoring
- Load balancing and device selection
- Health monitoring and failover
"""

import asyncio
import hashlib
import json
import logging
import os
import platform
import socket
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import concurrent.futures

import numpy as np

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Types of inference devices."""
    NVIDIA_GPU = "nvidia_gpu"
    AMD_GPU = "amd_gpu"
    INTEL_GPU = "intel_gpu"
    APPLE_SILICON = "apple_silicon"
    JETSON = "jetson"
    RASPBERRY_PI = "raspberry_pi"
    CORAL_TPU = "coral_tpu"
    INTEL_NCS = "intel_ncs"
    CPU = "cpu"
    UNKNOWN = "unknown"


class DeviceStatus(Enum):
    """Device operational status."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    INITIALIZING = "initializing"
    UNKNOWN = "unknown"


class HealthStatus(Enum):
    """Device health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class SelectionStrategy(Enum):
    """Device selection strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    FASTEST = "fastest"
    MOST_MEMORY = "most_memory"
    PRIORITY = "priority"
    AFFINITY = "affinity"
    RANDOM = "random"


@dataclass
class DeviceCapability:
    """Device capability specifications."""
    # Compute
    compute_capability: Optional[str] = None  # e.g., "8.6" for NVIDIA
    fp32_tflops: float = 0.0
    fp16_tflops: float = 0.0
    int8_tops: float = 0.0

    # Precision support
    supports_fp32: bool = True
    supports_fp16: bool = False
    supports_bf16: bool = False
    supports_int8: bool = False
    supports_int4: bool = False

    # Memory
    memory_gb: float = 0.0
    memory_bandwidth_gbps: float = 0.0
    shared_memory_kb: int = 0

    # Tensor cores / accelerators
    tensor_cores: int = 0
    has_tensor_cores: bool = False

    # Software support
    cuda_version: Optional[str] = None
    cudnn_version: Optional[str] = None
    tensorrt_version: Optional[str] = None
    openvino_version: Optional[str] = None

    # Inference backends
    supported_backends: List[str] = field(default_factory=list)

    # Model format support
    supported_formats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compute_capability": self.compute_capability,
            "fp32_tflops": self.fp32_tflops,
            "fp16_tflops": self.fp16_tflops,
            "int8_tops": self.int8_tops,
            "supports_fp16": self.supports_fp16,
            "supports_int8": self.supports_int8,
            "memory_gb": self.memory_gb,
            "has_tensor_cores": self.has_tensor_cores,
            "supported_backends": self.supported_backends,
            "supported_formats": self.supported_formats
        }


@dataclass
class ResourceMetrics:
    """Real-time resource metrics."""
    # GPU metrics
    gpu_utilization_percent: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0
    gpu_memory_percent: float = 0.0
    gpu_temperature_c: float = 0.0
    gpu_power_w: float = 0.0
    gpu_clock_mhz: int = 0

    # CPU metrics
    cpu_utilization_percent: float = 0.0
    cpu_temperature_c: float = 0.0

    # Memory metrics
    system_memory_used_mb: float = 0.0
    system_memory_total_mb: float = 0.0
    system_memory_percent: float = 0.0

    # Inference metrics
    active_sessions: int = 0
    queued_requests: int = 0
    avg_latency_ms: float = 0.0
    throughput_fps: float = 0.0

    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def gpu_memory_available_mb(self) -> float:
        return self.gpu_memory_total_mb - self.gpu_memory_used_mb

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_utilization_percent": self.gpu_utilization_percent,
            "gpu_memory_used_mb": self.gpu_memory_used_mb,
            "gpu_memory_total_mb": self.gpu_memory_total_mb,
            "gpu_memory_percent": self.gpu_memory_percent,
            "gpu_temperature_c": self.gpu_temperature_c,
            "cpu_utilization_percent": self.cpu_utilization_percent,
            "system_memory_percent": self.system_memory_percent,
            "active_sessions": self.active_sessions,
            "avg_latency_ms": self.avg_latency_ms,
            "throughput_fps": self.throughput_fps,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DeviceProfile:
    """Hardware profile for edge device."""
    name: str
    device_type: DeviceType
    precision: str = "fp32"
    image_size: Tuple[int, int] = (640, 640)
    batch_size: int = 1
    num_threads: int = 4

    # Performance targets
    target_fps: float = 30.0
    max_latency_ms: float = 100.0
    max_memory_mb: Optional[int] = None

    # Backend preferences
    preferred_backend: str = "onnx"
    fallback_backends: List[str] = field(default_factory=lambda: ["cpu"])

    # Optimizations
    enable_tensor_cores: bool = True
    enable_cudnn_benchmark: bool = True
    use_fp16_accumulation: bool = False

    @classmethod
    def jetson_nano(cls) -> "DeviceProfile":
        """Profile for NVIDIA Jetson Nano."""
        return cls(
            name="jetson_nano",
            device_type=DeviceType.JETSON,
            precision="fp16",
            image_size=(416, 416),
            batch_size=1,
            num_threads=4,
            target_fps=15.0,
            max_latency_ms=100.0,
            max_memory_mb=2048,
            preferred_backend="tensorrt"
        )

    @classmethod
    def jetson_xavier(cls) -> "DeviceProfile":
        """Profile for NVIDIA Jetson Xavier."""
        return cls(
            name="jetson_xavier",
            device_type=DeviceType.JETSON,
            precision="fp16",
            image_size=(640, 640),
            batch_size=4,
            num_threads=6,
            target_fps=30.0,
            max_latency_ms=50.0,
            max_memory_mb=8192,
            preferred_backend="tensorrt"
        )

    @classmethod
    def raspberry_pi4(cls) -> "DeviceProfile":
        """Profile for Raspberry Pi 4."""
        return cls(
            name="raspberry_pi4",
            device_type=DeviceType.RASPBERRY_PI,
            precision="int8",
            image_size=(320, 320),
            batch_size=1,
            num_threads=4,
            target_fps=5.0,
            max_latency_ms=250.0,
            max_memory_mb=1024,
            preferred_backend="tflite",
            fallback_backends=["ncnn"]
        )

    @classmethod
    def coral_tpu(cls) -> "DeviceProfile":
        """Profile for Google Coral Edge TPU."""
        return cls(
            name="coral_tpu",
            device_type=DeviceType.CORAL_TPU,
            precision="int8",
            image_size=(512, 512),
            batch_size=1,
            num_threads=4,
            target_fps=30.0,
            max_latency_ms=50.0,
            max_memory_mb=512,
            preferred_backend="edgetpu"
        )

    @classmethod
    def nvidia_rtx(cls) -> "DeviceProfile":
        """Profile for NVIDIA RTX GPUs."""
        return cls(
            name="nvidia_rtx",
            device_type=DeviceType.NVIDIA_GPU,
            precision="fp16",
            image_size=(640, 640),
            batch_size=16,
            num_threads=8,
            target_fps=60.0,
            max_latency_ms=20.0,
            preferred_backend="tensorrt",
            enable_tensor_cores=True
        )

    @classmethod
    def apple_m1(cls) -> "DeviceProfile":
        """Profile for Apple M1/M2 chips."""
        return cls(
            name="apple_m1",
            device_type=DeviceType.APPLE_SILICON,
            precision="fp16",
            image_size=(640, 640),
            batch_size=8,
            num_threads=8,
            target_fps=45.0,
            max_latency_ms=30.0,
            preferred_backend="coreml",
            fallback_backends=["mps", "cpu"]
        )

    @classmethod
    def cpu_only(cls) -> "DeviceProfile":
        """Profile for CPU-only inference."""
        return cls(
            name="cpu_only",
            device_type=DeviceType.CPU,
            precision="fp32",
            image_size=(640, 640),
            batch_size=1,
            num_threads=8,
            target_fps=10.0,
            max_latency_ms=150.0,
            preferred_backend="onnx",
            fallback_backends=["openvino"]
        )


@dataclass
class DeviceInfo:
    """Complete device information."""
    device_id: str
    name: str
    device_type: DeviceType
    status: DeviceStatus = DeviceStatus.UNKNOWN
    health: HealthStatus = HealthStatus.UNKNOWN

    # Hardware info
    capability: DeviceCapability = field(default_factory=DeviceCapability)
    profile: Optional[DeviceProfile] = None

    # Network info
    hostname: str = ""
    ip_address: str = ""
    port: int = 0

    # Metadata
    location: str = ""
    tags: Set[str] = field(default_factory=set)
    priority: int = 0

    # State
    last_seen: datetime = field(default_factory=datetime.now)
    registered_at: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    last_error: Optional[str] = None

    # Metrics
    current_metrics: Optional[ResourceMetrics] = None

    def is_available(self) -> bool:
        """Check if device is available for inference."""
        return self.status == DeviceStatus.ONLINE and self.health != HealthStatus.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "status": self.status.value,
            "health": self.health.value,
            "capability": self.capability.to_dict(),
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "location": self.location,
            "tags": list(self.tags),
            "priority": self.priority,
            "last_seen": self.last_seen.isoformat(),
            "error_count": self.error_count,
            "current_metrics": self.current_metrics.to_dict() if self.current_metrics else None
        }


class ResourceMonitor:
    """Real-time resource monitoring for devices."""

    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._metrics_history: Dict[str, List[ResourceMetrics]] = defaultdict(list)
        self._max_history = 1000
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[str, ResourceMetrics], None]] = []

    def start(self):
        """Start resource monitoring."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Resource monitor started")

    def stop(self):
        """Stop resource monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Resource monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Get local device metrics
                metrics = self._collect_local_metrics()
                device_id = self._get_local_device_id()

                with self._lock:
                    self._metrics_history[device_id].append(metrics)
                    if len(self._metrics_history[device_id]) > self._max_history:
                        self._metrics_history[device_id] = self._metrics_history[device_id][-self._max_history:]

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(device_id, metrics)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

            except Exception as e:
                logger.error(f"Monitoring error: {e}")

            time.sleep(self.poll_interval)

    def _get_local_device_id(self) -> str:
        """Get local device ID."""
        hostname = socket.gethostname()
        return hashlib.md5(hostname.encode()).hexdigest()[:12]

    def _collect_local_metrics(self) -> ResourceMetrics:
        """Collect metrics from local device."""
        metrics = ResourceMetrics()

        # GPU metrics (NVIDIA)
        try:
            metrics.update(self._get_nvidia_metrics())
        except:
            pass

        # CPU metrics
        try:
            import psutil
            metrics.cpu_utilization_percent = psutil.cpu_percent()

            mem = psutil.virtual_memory()
            metrics.system_memory_used_mb = mem.used / (1024 * 1024)
            metrics.system_memory_total_mb = mem.total / (1024 * 1024)
            metrics.system_memory_percent = mem.percent
        except ImportError:
            pass

        return metrics

    def _get_nvidia_metrics(self) -> Dict[str, float]:
        """Get NVIDIA GPU metrics using nvidia-smi."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.gr",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 6:
                    return {
                        "gpu_utilization_percent": float(parts[0]),
                        "gpu_memory_used_mb": float(parts[1]),
                        "gpu_memory_total_mb": float(parts[2]),
                        "gpu_memory_percent": float(parts[1]) / float(parts[2]) * 100 if float(parts[2]) > 0 else 0,
                        "gpu_temperature_c": float(parts[3]),
                        "gpu_power_w": float(parts[4]) if parts[4] != "[N/A]" else 0,
                        "gpu_clock_mhz": int(parts[5]) if parts[5] != "[N/A]" else 0
                    }
        except:
            pass

        return {}

    def register_callback(self, callback: Callable[[str, ResourceMetrics], None]):
        """Register callback for metrics updates."""
        self._callbacks.append(callback)

    def get_current_metrics(self, device_id: str) -> Optional[ResourceMetrics]:
        """Get current metrics for device."""
        with self._lock:
            history = self._metrics_history.get(device_id, [])
            return history[-1] if history else None

    def get_metrics_history(
        self,
        device_id: str,
        duration_minutes: int = 60
    ) -> List[ResourceMetrics]:
        """Get metrics history for device."""
        with self._lock:
            history = self._metrics_history.get(device_id, [])
            cutoff = datetime.now() - timedelta(minutes=duration_minutes)
            return [m for m in history if m.timestamp >= cutoff]

    def get_average_metrics(self, device_id: str, duration_minutes: int = 5) -> Optional[ResourceMetrics]:
        """Get average metrics over time period."""
        history = self.get_metrics_history(device_id, duration_minutes)
        if not history:
            return None

        avg = ResourceMetrics()
        n = len(history)

        avg.gpu_utilization_percent = sum(m.gpu_utilization_percent for m in history) / n
        avg.gpu_memory_used_mb = sum(m.gpu_memory_used_mb for m in history) / n
        avg.gpu_memory_total_mb = history[-1].gpu_memory_total_mb
        avg.gpu_temperature_c = sum(m.gpu_temperature_c for m in history) / n
        avg.cpu_utilization_percent = sum(m.cpu_utilization_percent for m in history) / n
        avg.system_memory_percent = sum(m.system_memory_percent for m in history) / n

        return avg


class DeviceSelector:
    """Intelligent device selection for inference."""

    def __init__(self, registry: "DeviceRegistry"):
        self.registry = registry
        self._round_robin_index = 0
        self._affinity_map: Dict[str, str] = {}  # model_id -> device_id
        self._lock = threading.Lock()

    def select(
        self,
        strategy: SelectionStrategy = SelectionStrategy.LEAST_LOADED,
        filter_tags: Optional[Set[str]] = None,
        filter_types: Optional[Set[DeviceType]] = None,
        model_id: Optional[str] = None,
        min_memory_mb: Optional[int] = None,
        required_precision: Optional[str] = None
    ) -> Optional[DeviceInfo]:
        """Select best device based on strategy."""
        # Get available devices
        devices = self.registry.get_available_devices()

        if not devices:
            return None

        # Apply filters
        if filter_tags:
            devices = [d for d in devices if d.tags & filter_tags]

        if filter_types:
            devices = [d for d in devices if d.device_type in filter_types]

        if min_memory_mb:
            devices = [
                d for d in devices
                if d.current_metrics and d.current_metrics.gpu_memory_available_mb >= min_memory_mb
            ]

        if required_precision:
            devices = [
                d for d in devices
                if self._supports_precision(d, required_precision)
            ]

        if not devices:
            return None

        # Select based on strategy
        if strategy == SelectionStrategy.ROUND_ROBIN:
            return self._select_round_robin(devices)
        elif strategy == SelectionStrategy.LEAST_LOADED:
            return self._select_least_loaded(devices)
        elif strategy == SelectionStrategy.FASTEST:
            return self._select_fastest(devices)
        elif strategy == SelectionStrategy.MOST_MEMORY:
            return self._select_most_memory(devices)
        elif strategy == SelectionStrategy.PRIORITY:
            return self._select_by_priority(devices)
        elif strategy == SelectionStrategy.AFFINITY:
            return self._select_by_affinity(devices, model_id)
        elif strategy == SelectionStrategy.RANDOM:
            return self._select_random(devices)
        else:
            return devices[0]

    def _supports_precision(self, device: DeviceInfo, precision: str) -> bool:
        """Check if device supports precision."""
        cap = device.capability
        if precision == "fp16":
            return cap.supports_fp16
        elif precision == "int8":
            return cap.supports_int8
        elif precision == "bf16":
            return cap.supports_bf16
        return True  # FP32 always supported

    def _select_round_robin(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """Round-robin selection."""
        with self._lock:
            device = devices[self._round_robin_index % len(devices)]
            self._round_robin_index += 1
            return device

    def _select_least_loaded(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """Select least loaded device."""
        def load_score(d: DeviceInfo) -> float:
            if d.current_metrics is None:
                return 0.5  # Unknown load
            return (
                d.current_metrics.gpu_utilization_percent * 0.4 +
                d.current_metrics.gpu_memory_percent * 0.3 +
                d.current_metrics.cpu_utilization_percent * 0.2 +
                min(d.current_metrics.active_sessions * 10, 100) * 0.1
            )

        return min(devices, key=load_score)

    def _select_fastest(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """Select fastest device."""
        def speed_score(d: DeviceInfo) -> float:
            cap = d.capability
            return cap.fp16_tflops * 2 + cap.fp32_tflops + cap.int8_tops * 0.5

        return max(devices, key=speed_score)

    def _select_most_memory(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """Select device with most available memory."""
        def memory_score(d: DeviceInfo) -> float:
            if d.current_metrics:
                return d.current_metrics.gpu_memory_available_mb
            return d.capability.memory_gb * 1024

        return max(devices, key=memory_score)

    def _select_by_priority(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """Select by priority."""
        return max(devices, key=lambda d: d.priority)

    def _select_by_affinity(
        self,
        devices: List[DeviceInfo],
        model_id: Optional[str]
    ) -> DeviceInfo:
        """Select based on model affinity."""
        if model_id and model_id in self._affinity_map:
            affinity_device_id = self._affinity_map[model_id]
            for d in devices:
                if d.device_id == affinity_device_id:
                    return d

        # Fallback to least loaded
        return self._select_least_loaded(devices)

    def _select_random(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """Random selection."""
        import random
        return random.choice(devices)

    def set_affinity(self, model_id: str, device_id: str):
        """Set model-device affinity."""
        with self._lock:
            self._affinity_map[model_id] = device_id

    def clear_affinity(self, model_id: str):
        """Clear model affinity."""
        with self._lock:
            self._affinity_map.pop(model_id, None)


class DeviceRegistry:
    """
    Central registry for inference devices.

    Manages device discovery, registration, health monitoring,
    and provides intelligent device selection for inference workloads.
    """

    def __init__(
        self,
        enable_monitoring: bool = True,
        health_check_interval: float = 30.0
    ):
        self._devices: Dict[str, DeviceInfo] = {}
        self._lock = threading.RLock()

        # Monitoring
        self._monitor = ResourceMonitor() if enable_monitoring else None
        if self._monitor:
            self._monitor.register_callback(self._on_metrics_update)

        # Device selector
        self._selector = DeviceSelector(self)

        # Health checking
        self._health_check_interval = health_check_interval
        self._health_thread: Optional[threading.Thread] = None
        self._running = False

        # Event callbacks
        self._on_device_added: List[Callable[[DeviceInfo], None]] = []
        self._on_device_removed: List[Callable[[str], None]] = []
        self._on_status_changed: List[Callable[[DeviceInfo, DeviceStatus], None]] = []

        logger.info("DeviceRegistry initialized")

    def start(self):
        """Start the registry services."""
        if self._running:
            return

        self._running = True

        # Start resource monitor
        if self._monitor:
            self._monitor.start()

        # Start health check thread
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

        # Auto-discover local devices
        self._discover_local_devices()

        logger.info("DeviceRegistry started")

    def stop(self):
        """Stop the registry services."""
        self._running = False

        if self._monitor:
            self._monitor.stop()

        if self._health_thread:
            self._health_thread.join(timeout=5.0)

        logger.info("DeviceRegistry stopped")

    def _discover_local_devices(self):
        """Discover local inference devices."""
        # Discover NVIDIA GPUs
        self._discover_nvidia_gpus()

        # Discover Apple Silicon
        self._discover_apple_silicon()

        # Always register CPU
        self._register_cpu()

        logger.info(f"Discovered {len(self._devices)} devices")

    def _discover_nvidia_gpus(self):
        """Discover NVIDIA GPUs."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = [p.strip() for p in line.split(", ")]
                        if len(parts) >= 4:
                            gpu_index = int(parts[0])
                            gpu_name = parts[1]
                            memory_mb = float(parts[2].replace(" MiB", ""))

                            device_id = f"nvidia_gpu_{gpu_index}"

                            capability = DeviceCapability(
                                memory_gb=memory_mb / 1024,
                                supports_fp16=True,
                                supports_int8=True,
                                has_tensor_cores="RTX" in gpu_name or "A100" in gpu_name or "H100" in gpu_name,
                                supported_backends=["cuda", "tensorrt", "onnx"],
                                supported_formats=[".pt", ".onnx", ".engine"]
                            )

                            # Get compute capability
                            try:
                                import torch
                                if torch.cuda.is_available():
                                    cc = torch.cuda.get_device_capability(gpu_index)
                                    capability.compute_capability = f"{cc[0]}.{cc[1]}"
                            except:
                                pass

                            device = DeviceInfo(
                                device_id=device_id,
                                name=gpu_name,
                                device_type=DeviceType.NVIDIA_GPU,
                                status=DeviceStatus.ONLINE,
                                health=HealthStatus.HEALTHY,
                                capability=capability,
                                profile=DeviceProfile.nvidia_rtx(),
                                hostname=socket.gethostname()
                            )

                            self.register(device)

        except Exception as e:
            logger.debug(f"NVIDIA discovery failed: {e}")

    def _discover_apple_silicon(self):
        """Discover Apple Silicon devices."""
        if platform.system() != "Darwin":
            return

        try:
            import torch
            if torch.backends.mps.is_available():
                device_id = "apple_mps_0"

                # Estimate memory from system
                import subprocess
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True
                )
                total_memory_gb = int(result.stdout.strip()) / (1024**3) if result.returncode == 0 else 8

                # Apple Silicon uses unified memory, estimate GPU portion
                gpu_memory_gb = total_memory_gb * 0.75

                capability = DeviceCapability(
                    memory_gb=gpu_memory_gb,
                    supports_fp16=True,
                    supported_backends=["mps", "coreml", "onnx"],
                    supported_formats=[".pt", ".mlmodel", ".onnx"]
                )

                device = DeviceInfo(
                    device_id=device_id,
                    name="Apple Silicon GPU",
                    device_type=DeviceType.APPLE_SILICON,
                    status=DeviceStatus.ONLINE,
                    health=HealthStatus.HEALTHY,
                    capability=capability,
                    profile=DeviceProfile.apple_m1(),
                    hostname=socket.gethostname()
                )

                self.register(device)

        except Exception as e:
            logger.debug(f"Apple Silicon discovery failed: {e}")

    def _register_cpu(self):
        """Register CPU as fallback device."""
        import multiprocessing

        device_id = "cpu_0"
        cpu_count = multiprocessing.cpu_count()

        capability = DeviceCapability(
            supports_fp32=True,
            supported_backends=["onnx", "openvino", "tflite"],
            supported_formats=[".onnx", ".xml", ".tflite"]
        )

        device = DeviceInfo(
            device_id=device_id,
            name=f"CPU ({cpu_count} cores)",
            device_type=DeviceType.CPU,
            status=DeviceStatus.ONLINE,
            health=HealthStatus.HEALTHY,
            capability=capability,
            profile=DeviceProfile.cpu_only(),
            hostname=socket.gethostname(),
            priority=-10  # Low priority
        )

        self.register(device)

    def register(self, device: DeviceInfo) -> bool:
        """Register a device."""
        with self._lock:
            self._devices[device.device_id] = device
            logger.info(f"Registered device: {device.device_id} ({device.name})")

            for callback in self._on_device_added:
                try:
                    callback(device)
                except Exception as e:
                    logger.error(f"Device added callback error: {e}")

            return True

    def unregister(self, device_id: str) -> bool:
        """Unregister a device."""
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                logger.info(f"Unregistered device: {device_id}")

                for callback in self._on_device_removed:
                    try:
                        callback(device_id)
                    except Exception as e:
                        logger.error(f"Device removed callback error: {e}")

                return True
            return False

    def get(self, device_id: str) -> Optional[DeviceInfo]:
        """Get device by ID."""
        with self._lock:
            return self._devices.get(device_id)

    def get_all(self) -> List[DeviceInfo]:
        """Get all registered devices."""
        with self._lock:
            return list(self._devices.values())

    def get_available_devices(self) -> List[DeviceInfo]:
        """Get all available devices."""
        with self._lock:
            return [d for d in self._devices.values() if d.is_available()]

    def get_by_type(self, device_type: DeviceType) -> List[DeviceInfo]:
        """Get devices by type."""
        with self._lock:
            return [d for d in self._devices.values() if d.device_type == device_type]

    def get_by_tag(self, tag: str) -> List[DeviceInfo]:
        """Get devices by tag."""
        with self._lock:
            return [d for d in self._devices.values() if tag in d.tags]

    def select_device(
        self,
        strategy: SelectionStrategy = SelectionStrategy.LEAST_LOADED,
        **kwargs
    ) -> Optional[DeviceInfo]:
        """Select best device using strategy."""
        return self._selector.select(strategy, **kwargs)

    def update_status(self, device_id: str, status: DeviceStatus):
        """Update device status."""
        with self._lock:
            device = self._devices.get(device_id)
            if device:
                old_status = device.status
                device.status = status
                device.last_seen = datetime.now()

                if old_status != status:
                    for callback in self._on_status_changed:
                        try:
                            callback(device, old_status)
                        except Exception as e:
                            logger.error(f"Status change callback error: {e}")

    def update_health(self, device_id: str, health: HealthStatus, error: Optional[str] = None):
        """Update device health."""
        with self._lock:
            device = self._devices.get(device_id)
            if device:
                device.health = health
                if error:
                    device.error_count += 1
                    device.last_error = error

    def _on_metrics_update(self, device_id: str, metrics: ResourceMetrics):
        """Handle metrics update from monitor."""
        with self._lock:
            device = self._devices.get(device_id)
            if device:
                device.current_metrics = metrics
                device.last_seen = datetime.now()

                # Update health based on metrics
                if metrics.gpu_temperature_c > 90:
                    device.health = HealthStatus.CRITICAL
                elif metrics.gpu_temperature_c > 80:
                    device.health = HealthStatus.DEGRADED
                elif metrics.gpu_memory_percent > 95:
                    device.health = HealthStatus.DEGRADED
                else:
                    device.health = HealthStatus.HEALTHY

    def _health_check_loop(self):
        """Periodic health check loop."""
        while self._running:
            try:
                self._check_device_health()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            time.sleep(self._health_check_interval)

    def _check_device_health(self):
        """Check health of all devices."""
        now = datetime.now()
        timeout = timedelta(seconds=self._health_check_interval * 3)

        with self._lock:
            for device in self._devices.values():
                if now - device.last_seen > timeout:
                    if device.status != DeviceStatus.OFFLINE:
                        self.update_status(device.device_id, DeviceStatus.OFFLINE)
                        logger.warning(f"Device {device.device_id} went offline")

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            devices = list(self._devices.values())

            return {
                "total_devices": len(devices),
                "online": sum(1 for d in devices if d.status == DeviceStatus.ONLINE),
                "offline": sum(1 for d in devices if d.status == DeviceStatus.OFFLINE),
                "healthy": sum(1 for d in devices if d.health == HealthStatus.HEALTHY),
                "by_type": {
                    t.value: sum(1 for d in devices if d.device_type == t)
                    for t in DeviceType
                    if any(d.device_type == t for d in devices)
                },
                "total_gpu_memory_gb": sum(
                    d.capability.memory_gb
                    for d in devices
                    if d.device_type != DeviceType.CPU
                )
            }

    def to_dict(self) -> Dict[str, Any]:
        """Export registry to dictionary."""
        with self._lock:
            return {
                "devices": {
                    device_id: device.to_dict()
                    for device_id, device in self._devices.items()
                },
                "statistics": self.get_statistics()
            }

    # Event callbacks
    def on_device_added(self, callback: Callable[[DeviceInfo], None]):
        """Register callback for device addition."""
        self._on_device_added.append(callback)

    def on_device_removed(self, callback: Callable[[str], None]):
        """Register callback for device removal."""
        self._on_device_removed.append(callback)

    def on_status_changed(self, callback: Callable[[DeviceInfo, DeviceStatus], None]):
        """Register callback for status changes."""
        self._on_status_changed.append(callback)


# Singleton instance
_device_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """Get singleton DeviceRegistry instance."""
    global _device_registry
    if _device_registry is None:
        _device_registry = DeviceRegistry()
        _device_registry.start()
    return _device_registry
