"""
Vision Pipeline Orchestrator - End-to-End Vision Processing

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides:
- Multi-stage pipeline processing
- Parallel and sequential execution
- Result aggregation
- Performance monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
import threading
import uuid
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


class PipelineStage(Enum):
    """Pipeline processing stages."""
    PREPROCESSING = "preprocessing"
    DETECTION = "detection"
    CLASSIFICATION = "classification"
    ANALYSIS = "analysis"
    QUALITY_ASSESSMENT = "quality_assessment"
    EXPLAINABILITY = "explainability"
    POSTPROCESSING = "postprocessing"
    REPORTING = "reporting"


class ExecutionMode(Enum):
    """Pipeline execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"


class PipelineStatus(Enum):
    """Pipeline execution status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StageConfig:
    """Configuration for a pipeline stage."""
    stage: PipelineStage
    enabled: bool = True
    timeout_seconds: float = 30.0
    retry_count: int = 1
    parallel_workers: int = 1
    priority: int = 0
    dependencies: List[PipelineStage] = field(default_factory=list)


@dataclass
class PipelineConfig:
    """Vision pipeline configuration."""
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    max_parallel_workers: int = 4
    enable_caching: bool = True
    cache_ttl_seconds: float = 60.0
    enable_monitoring: bool = True
    fail_fast: bool = False
    stages: List[StageConfig] = field(default_factory=list)


@dataclass
class StageResult:
    """Result from a pipeline stage."""
    stage: PipelineStage
    success: bool
    data: Dict[str, Any]
    duration_ms: float
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    pipeline_id: str
    image_id: str
    success: bool
    total_duration_ms: float
    stage_results: Dict[str, StageResult]
    detections: List[Dict[str, Any]]
    quality_score: float
    defect_count: int
    recommendations: List[str]
    metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PipelineMetrics:
    """Pipeline performance metrics."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_duration_ms: float = 0.0
    stage_durations: Dict[str, float] = field(default_factory=dict)
    throughput_per_second: float = 0.0
    last_execution: Optional[datetime] = None


class VisionPipeline:
    """
    End-to-end vision processing pipeline.

    Features:
    - Multi-stage processing
    - Parallel execution
    - Result caching
    - Performance monitoring
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize vision pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()

        # Stage handlers
        self._stage_handlers: Dict[PipelineStage, Callable] = {}

        # Initialize default stages
        self._init_default_stages()

        # Execution state
        self._status = PipelineStatus.IDLE
        self._current_pipeline_id: Optional[str] = None

        # Caching
        self._cache: Dict[str, Tuple[PipelineResult, datetime]] = {}

        # Metrics
        self._metrics = PipelineMetrics()

        # Thread pool for parallel execution
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.max_parallel_workers
        )

        # Thread safety
        self._lock = threading.RLock()

        # Event callbacks
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def register_stage(
        self,
        stage: PipelineStage,
        handler: Callable[[Any, Dict[str, Any]], Dict[str, Any]]
    ):
        """
        Register a stage handler.

        Args:
            stage: Pipeline stage
            handler: Handler function (image, context) -> result
        """
        self._stage_handlers[stage] = handler

    def execute(
        self,
        image: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> PipelineResult:
        """
        Execute the vision pipeline.

        Args:
            image: Input image
            context: Additional context

        Returns:
            Pipeline execution result
        """
        pipeline_id = str(uuid.uuid4())
        context = context or {}
        context["pipeline_id"] = pipeline_id

        start_time = time.time()

        with self._lock:
            self._status = PipelineStatus.RUNNING
            self._current_pipeline_id = pipeline_id
            self._metrics.total_executions += 1

        # Check cache
        cache_key = self._get_cache_key(image, context)
        if self.config.enable_caching:
            cached = self._get_cached_result(cache_key)
            if cached:
                return cached

        try:
            # Execute stages
            stage_results = {}
            accumulated_data = {"image": image, **context}

            stages = self._get_ordered_stages()

            if self.config.execution_mode == ExecutionMode.PARALLEL:
                stage_results = self._execute_parallel(
                    image, accumulated_data, stages
                )
            else:
                stage_results = self._execute_sequential(
                    image, accumulated_data, stages
                )

            # Check for failures
            success = all(r.success for r in stage_results.values())

            if not success and self.config.fail_fast:
                self._status = PipelineStatus.FAILED
            else:
                self._status = PipelineStatus.COMPLETED

            # Aggregate results
            result = self._aggregate_results(
                pipeline_id, image, stage_results, context
            )

            # Update metrics
            duration_ms = (time.time() - start_time) * 1000
            result.total_duration_ms = duration_ms
            self._update_metrics(result, stage_results)

            # Cache result
            if self.config.enable_caching and success:
                self._cache_result(cache_key, result)

            # Emit completion event
            self._emit_event("pipeline_completed", result)

            with self._lock:
                self._metrics.successful_executions += 1

            return result

        except Exception as e:
            with self._lock:
                self._status = PipelineStatus.FAILED
                self._metrics.failed_executions += 1

            duration_ms = (time.time() - start_time) * 1000

            return PipelineResult(
                pipeline_id=pipeline_id,
                image_id=context.get("image_id", str(id(image))),
                success=False,
                total_duration_ms=duration_ms,
                stage_results={},
                detections=[],
                quality_score=0.0,
                defect_count=0,
                recommendations=[],
                metadata={"error": str(e)},
            )

    def execute_batch(
        self,
        images: List[Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[PipelineResult]:
        """
        Execute pipeline on multiple images.

        Args:
            images: List of images
            context: Shared context

        Returns:
            List of results
        """
        context = context or {}
        results = []

        futures = []
        for i, image in enumerate(images):
            img_context = {**context, "batch_index": i}
            future = self._executor.submit(self.execute, image, img_context)
            futures.append(future)

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(PipelineResult(
                    pipeline_id=str(uuid.uuid4()),
                    image_id="unknown",
                    success=False,
                    total_duration_ms=0,
                    stage_results={},
                    detections=[],
                    quality_score=0,
                    defect_count=0,
                    recommendations=[],
                    metadata={"error": str(e)},
                ))

        return results

    def add_callback(
        self,
        event: str,
        callback: Callable[[PipelineResult], None]
    ):
        """
        Add event callback.

        Args:
            event: Event name
            callback: Callback function
        """
        self._callbacks[event].append(callback)

    def get_metrics(self) -> PipelineMetrics:
        """Get pipeline metrics."""
        return self._metrics

    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        return {
            "status": self._status.value,
            "current_pipeline_id": self._current_pipeline_id,
            "total_executions": self._metrics.total_executions,
            "successful_executions": self._metrics.successful_executions,
            "failed_executions": self._metrics.failed_executions,
            "avg_duration_ms": self._metrics.avg_duration_ms,
            "cache_size": len(self._cache),
            "registered_stages": list(self._stage_handlers.keys()),
        }

    def clear_cache(self):
        """Clear result cache."""
        self._cache.clear()

    def _init_default_stages(self):
        """Initialize default stage handlers."""
        self._stage_handlers = {
            PipelineStage.PREPROCESSING: self._stage_preprocessing,
            PipelineStage.DETECTION: self._stage_detection,
            PipelineStage.CLASSIFICATION: self._stage_classification,
            PipelineStage.ANALYSIS: self._stage_analysis,
            PipelineStage.QUALITY_ASSESSMENT: self._stage_quality,
            PipelineStage.EXPLAINABILITY: self._stage_explainability,
            PipelineStage.POSTPROCESSING: self._stage_postprocessing,
            PipelineStage.REPORTING: self._stage_reporting,
        }

    def _get_ordered_stages(self) -> List[PipelineStage]:
        """Get stages in execution order."""
        if self.config.stages:
            return [s.stage for s in self.config.stages if s.enabled]

        return [
            PipelineStage.PREPROCESSING,
            PipelineStage.DETECTION,
            PipelineStage.CLASSIFICATION,
            PipelineStage.ANALYSIS,
            PipelineStage.QUALITY_ASSESSMENT,
            PipelineStage.EXPLAINABILITY,
            PipelineStage.POSTPROCESSING,
            PipelineStage.REPORTING,
        ]

    def _execute_sequential(
        self,
        image: Any,
        accumulated_data: Dict[str, Any],
        stages: List[PipelineStage]
    ) -> Dict[str, StageResult]:
        """Execute stages sequentially."""
        results = {}

        for stage in stages:
            handler = self._stage_handlers.get(stage)
            if handler is None:
                continue

            start_time = time.time()

            try:
                stage_data = handler(image, accumulated_data)
                accumulated_data.update(stage_data)

                results[stage.value] = StageResult(
                    stage=stage,
                    success=True,
                    data=stage_data,
                    duration_ms=(time.time() - start_time) * 1000,
                )

            except Exception as e:
                results[stage.value] = StageResult(
                    stage=stage,
                    success=False,
                    data={},
                    duration_ms=(time.time() - start_time) * 1000,
                    error=str(e),
                )

                if self.config.fail_fast:
                    break

        return results

    def _execute_parallel(
        self,
        image: Any,
        accumulated_data: Dict[str, Any],
        stages: List[PipelineStage]
    ) -> Dict[str, StageResult]:
        """Execute independent stages in parallel."""
        results = {}

        # Group stages by dependencies
        # For simplicity, execute preprocessing first, then others in parallel

        # Sequential stages
        sequential = [PipelineStage.PREPROCESSING, PipelineStage.POSTPROCESSING, PipelineStage.REPORTING]
        parallel = [s for s in stages if s not in sequential]

        # Execute preprocessing first
        if PipelineStage.PREPROCESSING in stages:
            result = self._execute_stage(
                PipelineStage.PREPROCESSING, image, accumulated_data
            )
            results[PipelineStage.PREPROCESSING.value] = result
            accumulated_data.update(result.data)

        # Execute parallel stages
        futures = {}
        for stage in parallel:
            if stage in stages:
                future = self._executor.submit(
                    self._execute_stage, stage, image, accumulated_data.copy()
                )
                futures[stage] = future

        for stage, future in futures.items():
            try:
                result = future.result(timeout=30)
                results[stage.value] = result
                accumulated_data.update(result.data)
            except Exception as e:
                results[stage.value] = StageResult(
                    stage=stage,
                    success=False,
                    data={},
                    duration_ms=0,
                    error=str(e),
                )

        # Execute postprocessing and reporting
        for stage in [PipelineStage.POSTPROCESSING, PipelineStage.REPORTING]:
            if stage in stages:
                result = self._execute_stage(stage, image, accumulated_data)
                results[stage.value] = result
                accumulated_data.update(result.data)

        return results

    def _execute_stage(
        self,
        stage: PipelineStage,
        image: Any,
        data: Dict[str, Any]
    ) -> StageResult:
        """Execute a single stage."""
        handler = self._stage_handlers.get(stage)
        if handler is None:
            return StageResult(
                stage=stage,
                success=False,
                data={},
                duration_ms=0,
                error="No handler registered",
            )

        start_time = time.time()

        try:
            result_data = handler(image, data)
            return StageResult(
                stage=stage,
                success=True,
                data=result_data,
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return StageResult(
                stage=stage,
                success=False,
                data={},
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    def _stage_preprocessing(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Preprocessing stage."""
        import random

        # Simulated preprocessing
        return {
            "preprocessed": True,
            "image_size": (640, 640),
            "normalized": True,
            "color_space": "RGB",
        }

    def _stage_detection(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detection stage."""
        import random

        # Simulated YOLO detection
        num_detections = random.randint(0, 5)
        detections = []

        for i in range(num_detections):
            detections.append({
                "class": random.choice(["brick_2x4", "brick_2x2", "layer_shift", "stringing"]),
                "confidence": random.uniform(0.7, 0.99),
                "bbox": [
                    random.randint(0, 500),
                    random.randint(0, 500),
                    random.randint(50, 140),
                    random.randint(50, 140),
                ],
            })

        return {
            "detections": detections,
            "detection_count": len(detections),
            "inference_time_ms": random.uniform(10, 50),
        }

    def _stage_classification(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classification stage."""
        import random

        detections = context.get("detections", [])

        classified = []
        for det in detections:
            classified.append({
                **det,
                "subclass": random.choice(["good", "defect", "uncertain"]),
                "classification_confidence": random.uniform(0.8, 0.99),
            })

        return {
            "classified_detections": classified,
        }

    def _stage_analysis(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analysis stage."""
        import random

        detections = context.get("detections", [])

        # Count defects
        defects = [d for d in detections if d.get("class") in ["layer_shift", "stringing", "warping"]]

        return {
            "defect_count": len(defects),
            "defect_types": list(set(d["class"] for d in defects)),
            "layer_quality": random.uniform(0.7, 1.0),
            "surface_quality": random.uniform(0.7, 1.0),
        }

    def _stage_quality(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Quality assessment stage."""
        import random

        defect_count = context.get("defect_count", 0)
        layer_quality = context.get("layer_quality", 0.9)
        surface_quality = context.get("surface_quality", 0.9)

        # Calculate overall quality score
        defect_penalty = min(0.5, defect_count * 0.1)
        quality_score = (layer_quality + surface_quality) / 2 - defect_penalty

        # Determine grade
        if quality_score >= 0.9:
            grade = "A"
        elif quality_score >= 0.8:
            grade = "B"
        elif quality_score >= 0.7:
            grade = "C"
        else:
            grade = "F"

        return {
            "quality_score": max(0, quality_score),
            "quality_grade": grade,
            "pass_inspection": quality_score >= 0.7,
        }

    def _stage_explainability(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Explainability stage."""
        import random

        detections = context.get("detections", [])

        explanations = []
        for det in detections:
            explanations.append({
                "detection_class": det.get("class"),
                "explanation_type": "gradcam",
                "top_regions": [
                    {"x": random.randint(0, 600), "y": random.randint(0, 600), "importance": random.uniform(0.5, 1.0)}
                    for _ in range(3)
                ],
            })

        return {
            "explanations": explanations,
            "explainability_available": True,
        }

    def _stage_postprocessing(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Postprocessing stage."""
        # Generate recommendations
        recommendations = []

        defect_count = context.get("defect_count", 0)
        quality_score = context.get("quality_score", 1.0)

        if defect_count > 0:
            recommendations.append(f"Review {defect_count} detected defect(s)")

        if quality_score < 0.8:
            recommendations.append("Quality score below threshold - manual inspection recommended")

        if "layer_shift" in context.get("defect_types", []):
            recommendations.append("Check Z-axis calibration")

        return {
            "recommendations": recommendations,
            "requires_attention": defect_count > 0 or quality_score < 0.8,
        }

    def _stage_reporting(
        self,
        image: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reporting stage."""
        return {
            "report_generated": True,
            "report_format": "json",
            "include_visualizations": True,
        }

    def _aggregate_results(
        self,
        pipeline_id: str,
        image: Any,
        stage_results: Dict[str, StageResult],
        context: Dict[str, Any]
    ) -> PipelineResult:
        """Aggregate stage results into final result."""
        # Collect all data
        all_data = {}
        for result in stage_results.values():
            all_data.update(result.data)

        return PipelineResult(
            pipeline_id=pipeline_id,
            image_id=context.get("image_id", str(id(image))),
            success=all(r.success for r in stage_results.values()),
            total_duration_ms=0,  # Set by caller
            stage_results=stage_results,
            detections=all_data.get("detections", []),
            quality_score=all_data.get("quality_score", 0.0),
            defect_count=all_data.get("defect_count", 0),
            recommendations=all_data.get("recommendations", []),
            metadata={
                "quality_grade": all_data.get("quality_grade"),
                "pass_inspection": all_data.get("pass_inspection"),
                "requires_attention": all_data.get("requires_attention"),
            },
        )

    def _update_metrics(
        self,
        result: PipelineResult,
        stage_results: Dict[str, StageResult]
    ):
        """Update performance metrics."""
        with self._lock:
            # Update average duration
            n = self._metrics.total_executions
            old_avg = self._metrics.avg_duration_ms
            self._metrics.avg_duration_ms = (
                (old_avg * (n - 1) + result.total_duration_ms) / n
            )

            # Update stage durations
            for stage_name, stage_result in stage_results.items():
                if stage_name not in self._metrics.stage_durations:
                    self._metrics.stage_durations[stage_name] = stage_result.duration_ms
                else:
                    old = self._metrics.stage_durations[stage_name]
                    self._metrics.stage_durations[stage_name] = (old + stage_result.duration_ms) / 2

            self._metrics.last_execution = datetime.utcnow()

    def _get_cache_key(self, image: Any, context: Dict[str, Any]) -> str:
        """Generate cache key."""
        image_id = context.get("image_id", str(id(image)))
        return f"{image_id}_{hash(frozenset(context.items()))}"

    def _get_cached_result(self, key: str) -> Optional[PipelineResult]:
        """Get cached result if valid."""
        if key not in self._cache:
            return None

        result, cached_at = self._cache[key]
        age = (datetime.utcnow() - cached_at).total_seconds()

        if age > self.config.cache_ttl_seconds:
            del self._cache[key]
            return None

        return result

    def _cache_result(self, key: str, result: PipelineResult):
        """Cache a result."""
        self._cache[key] = (result, datetime.utcnow())

    def _emit_event(self, event: str, data: Any):
        """Emit event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception:
                pass


# Singleton instance
_vision_pipeline: Optional[VisionPipeline] = None


def get_vision_pipeline() -> VisionPipeline:
    """Get or create the vision pipeline instance."""
    global _vision_pipeline
    if _vision_pipeline is None:
        _vision_pipeline = VisionPipeline()
    return _vision_pipeline
