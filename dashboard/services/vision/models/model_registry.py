"""
Model Registry - Versioning & A/B Testing

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Provides model management:
- Model versioning
- A/B testing
- Deployment tracking
- Performance metrics
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import uuid
import hashlib


class ModelStatus(Enum):
    """Model deployment status."""
    DRAFT = "draft"
    TESTING = "testing"
    STAGED = "staged"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DeploymentTarget(Enum):
    """Deployment target environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    EDGE = "edge"
    CLOUD = "cloud"


class ModelTask(Enum):
    """Model task types."""
    OBJECT_DETECTION = "object_detection"
    CLASSIFICATION = "classification"
    SEGMENTATION = "segmentation"
    POSE_ESTIMATION = "pose_estimation"


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    map50: float = 0.0  # mAP@0.5
    map50_95: float = 0.0  # mAP@0.5:0.95
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    inference_time_ms: float = 0.0
    fps: float = 0.0
    memory_mb: float = 0.0
    flops: float = 0.0
    params_million: float = 0.0


@dataclass
class ModelMetadata:
    """Model metadata."""
    framework: str  # yolov8, yolov11, etc.
    architecture: str  # yolov8n, yolov8s, etc.
    input_size: Tuple[int, int, int]  # (channels, height, width)
    classes: List[str]
    num_classes: int
    training_dataset: str
    training_epochs: int
    batch_size: int
    optimizer: str
    learning_rate: float
    augmentation_config: Dict[str, Any] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelVersion:
    """A versioned model."""
    model_id: str
    version: int
    name: str
    description: str
    task: ModelTask
    status: ModelStatus
    metadata: ModelMetadata
    metrics: ModelMetrics
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    checkpoint_path: Optional[str] = None
    onnx_path: Optional[str] = None
    tensorrt_path: Optional[str] = None
    coreml_path: Optional[str] = None
    checksum: str = ""
    parent_version: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    deployment_targets: List[DeploymentTarget] = field(default_factory=list)


@dataclass
class ABTest:
    """A/B test configuration."""
    test_id: str
    name: str
    description: str
    model_a_id: str
    model_a_version: int
    model_b_id: str
    model_b_version: int
    traffic_split: float  # Percentage to model A (0-1)
    status: str  # active, paused, completed
    start_date: datetime
    end_date: Optional[datetime] = None
    metrics_a: Dict[str, float] = field(default_factory=dict)
    metrics_b: Dict[str, float] = field(default_factory=dict)
    winner: Optional[str] = None  # "A", "B", or None


@dataclass
class Model:
    """A model with multiple versions."""
    model_id: str
    name: str
    description: str
    task: ModelTask
    versions: Dict[int, ModelVersion] = field(default_factory=dict)
    current_version: int = 0
    production_version: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """
    Model registry for versioning and deployment management.

    Provides:
    - Model versioning
    - A/B testing
    - Deployment tracking
    - Performance comparison
    """

    def __init__(self, storage_path: str = "/tmp/legomcp/models"):
        """
        Initialize model registry.

        Args:
            storage_path: Path for model storage
        """
        self.storage_path = storage_path
        self.models: Dict[str, Model] = {}
        self.ab_tests: Dict[str, ABTest] = {}
        self._setup_demo_models()

    def _setup_demo_models(self):
        """Set up demo models."""
        # LEGO brick detection model
        brick_model = Model(
            model_id="lego-detector",
            name="LEGO Brick Detector",
            description="YOLOv8-based LEGO brick detection",
            task=ModelTask.OBJECT_DETECTION,
        )

        brick_v1 = ModelVersion(
            model_id=brick_model.model_id,
            version=1,
            name="Initial Release",
            description="First trained model on 500 images",
            task=ModelTask.OBJECT_DETECTION,
            status=ModelStatus.PRODUCTION,
            metadata=ModelMetadata(
                framework="ultralytics",
                architecture="yolov8n",
                input_size=(3, 640, 640),
                classes=[
                    "brick_2x4", "brick_2x2", "brick_1x4", "brick_1x2",
                    "plate_2x4", "plate_2x2", "slope_2x2", "tile_2x2",
                ],
                num_classes=8,
                training_dataset="lego-bricks-v1",
                training_epochs=100,
                batch_size=16,
                optimizer="AdamW",
                learning_rate=0.001,
            ),
            metrics=ModelMetrics(
                map50=0.85,
                map50_95=0.72,
                precision=0.88,
                recall=0.82,
                f1_score=0.85,
                inference_time_ms=12.5,
                fps=80,
                memory_mb=48,
                params_million=3.2,
            ),
            checkpoint_path="/models/lego-detector/v1/best.pt",
            tags=["production", "lego", "detection"],
            deployment_targets=[DeploymentTarget.PRODUCTION],
        )

        brick_model.versions[1] = brick_v1
        brick_model.current_version = 1
        brick_model.production_version = 1
        self.models[brick_model.model_id] = brick_model

        # 3D print defect model
        defect_model = Model(
            model_id="defect-detector",
            name="3D Print Defect Detector",
            description="Detects common 3D printing defects",
            task=ModelTask.OBJECT_DETECTION,
        )

        defect_v1 = ModelVersion(
            model_id=defect_model.model_id,
            version=1,
            name="Beta Release",
            description="Initial defect detection model",
            task=ModelTask.OBJECT_DETECTION,
            status=ModelStatus.TESTING,
            metadata=ModelMetadata(
                framework="ultralytics",
                architecture="yolov8s",
                input_size=(3, 640, 640),
                classes=[
                    "layer_shift", "stringing", "warping", "under_extrusion",
                    "over_extrusion", "z_wobble", "blob", "gap",
                ],
                num_classes=8,
                training_dataset="print-defects-v1",
                training_epochs=150,
                batch_size=8,
                optimizer="AdamW",
                learning_rate=0.0005,
            ),
            metrics=ModelMetrics(
                map50=0.78,
                map50_95=0.65,
                precision=0.80,
                recall=0.75,
                f1_score=0.77,
                inference_time_ms=18.5,
                fps=54,
                memory_mb=85,
                params_million=11.2,
            ),
            checkpoint_path="/models/defect-detector/v1/best.pt",
            tags=["testing", "defects", "quality"],
            deployment_targets=[DeploymentTarget.STAGING],
        )

        defect_model.versions[1] = defect_v1
        defect_model.current_version = 1
        self.models[defect_model.model_id] = defect_model

    def register_model(
        self,
        name: str,
        description: str,
        task: ModelTask,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Model:
        """
        Register a new model.

        Args:
            name: Model name
            description: Model description
            task: Model task type
            metadata: Optional metadata

        Returns:
            Registered model
        """
        model_id = name.lower().replace(" ", "-")

        model = Model(
            model_id=model_id,
            name=name,
            description=description,
            task=task,
            metadata=metadata or {},
        )

        self.models[model_id] = model
        return model

    def get_model(self, model_id: str) -> Optional[Model]:
        """Get model by ID."""
        return self.models.get(model_id)

    def list_models(
        self,
        task: Optional[ModelTask] = None,
        status: Optional[ModelStatus] = None
    ) -> List[Model]:
        """
        List models with optional filtering.

        Args:
            task: Filter by task type
            status: Filter by status (of production version)

        Returns:
            List of matching models
        """
        models = list(self.models.values())

        if task:
            models = [m for m in models if m.task == task]

        if status:
            models = [
                m for m in models
                if m.production_version and
                m.versions.get(m.production_version, ModelVersion(
                    model_id="", version=0, name="", description="",
                    task=ModelTask.OBJECT_DETECTION, status=ModelStatus.DRAFT,
                    metadata=ModelMetadata(
                        framework="", architecture="", input_size=(3, 640, 640),
                        classes=[], num_classes=0, training_dataset="",
                        training_epochs=0, batch_size=0, optimizer="",
                        learning_rate=0.0
                    ), metrics=ModelMetrics()
                )).status == status
            ]

        return models

    def create_version(
        self,
        model_id: str,
        name: str,
        description: str,
        metadata: ModelMetadata,
        metrics: ModelMetrics,
        checkpoint_path: str,
        tags: Optional[List[str]] = None
    ) -> Optional[ModelVersion]:
        """
        Create a new model version.

        Args:
            model_id: Model ID
            name: Version name
            description: Version description
            metadata: Model metadata
            metrics: Performance metrics
            checkpoint_path: Path to model checkpoint
            tags: Optional tags

        Returns:
            Created version
        """
        model = self.models.get(model_id)
        if not model:
            return None

        version_num = model.current_version + 1

        # Generate checksum
        checksum = hashlib.sha256(
            f"{model_id}-{version_num}-{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        version = ModelVersion(
            model_id=model_id,
            version=version_num,
            name=name,
            description=description,
            task=model.task,
            status=ModelStatus.DRAFT,
            metadata=metadata,
            metrics=metrics,
            checkpoint_path=checkpoint_path,
            checksum=checksum,
            parent_version=model.current_version if model.current_version > 0 else None,
            tags=tags or [],
        )

        model.versions[version_num] = version
        model.current_version = version_num

        return version

    def get_version(
        self,
        model_id: str,
        version: int
    ) -> Optional[ModelVersion]:
        """Get specific model version."""
        model = self.models.get(model_id)
        if model:
            return model.versions.get(version)
        return None

    def get_production_version(self, model_id: str) -> Optional[ModelVersion]:
        """Get production version of model."""
        model = self.models.get(model_id)
        if model and model.production_version:
            return model.versions.get(model.production_version)
        return None

    def promote_version(
        self,
        model_id: str,
        version: int,
        target_status: ModelStatus
    ) -> bool:
        """
        Promote model version to new status.

        Args:
            model_id: Model ID
            version: Version number
            target_status: Target status

        Returns:
            True if promotion successful
        """
        model = self.models.get(model_id)
        if not model:
            return False

        mv = model.versions.get(version)
        if not mv:
            return False

        mv.status = target_status
        mv.updated_at = datetime.utcnow()

        if target_status == ModelStatus.PRODUCTION:
            # Demote current production version
            if model.production_version and model.production_version != version:
                old_prod = model.versions.get(model.production_version)
                if old_prod:
                    old_prod.status = ModelStatus.DEPRECATED
            model.production_version = version

        return True

    def compare_versions(
        self,
        model_id: str,
        version_a: int,
        version_b: int
    ) -> Dict[str, Any]:
        """
        Compare two model versions.

        Args:
            model_id: Model ID
            version_a: First version
            version_b: Second version

        Returns:
            Comparison results
        """
        va = self.get_version(model_id, version_a)
        vb = self.get_version(model_id, version_b)

        if not va or not vb:
            return {"error": "Version not found"}

        return {
            "model_id": model_id,
            "version_a": version_a,
            "version_b": version_b,
            "metrics_comparison": {
                "map50": {
                    "a": va.metrics.map50,
                    "b": vb.metrics.map50,
                    "diff": vb.metrics.map50 - va.metrics.map50,
                    "improvement": (
                        (vb.metrics.map50 - va.metrics.map50) / va.metrics.map50 * 100
                        if va.metrics.map50 > 0 else 0
                    ),
                },
                "map50_95": {
                    "a": va.metrics.map50_95,
                    "b": vb.metrics.map50_95,
                    "diff": vb.metrics.map50_95 - va.metrics.map50_95,
                },
                "inference_time_ms": {
                    "a": va.metrics.inference_time_ms,
                    "b": vb.metrics.inference_time_ms,
                    "diff": vb.metrics.inference_time_ms - va.metrics.inference_time_ms,
                    "speedup": (
                        va.metrics.inference_time_ms / vb.metrics.inference_time_ms
                        if vb.metrics.inference_time_ms > 0 else 0
                    ),
                },
                "memory_mb": {
                    "a": va.metrics.memory_mb,
                    "b": vb.metrics.memory_mb,
                    "diff": vb.metrics.memory_mb - va.metrics.memory_mb,
                },
            },
            "recommendation": self._get_recommendation(va, vb),
        }

    def _get_recommendation(
        self,
        va: ModelVersion,
        vb: ModelVersion
    ) -> str:
        """Generate recommendation based on comparison."""
        map_improvement = vb.metrics.map50 - va.metrics.map50
        speed_improvement = va.metrics.inference_time_ms - vb.metrics.inference_time_ms

        if map_improvement > 0.02 and speed_improvement >= 0:
            return f"Recommend v{vb.version}: Better accuracy with same/better speed"
        elif map_improvement > 0.05:
            return f"Recommend v{vb.version}: Significantly better accuracy"
        elif speed_improvement > 5 and map_improvement >= -0.01:
            return f"Recommend v{vb.version}: Much faster with minimal accuracy loss"
        elif map_improvement < -0.02:
            return f"Keep v{va.version}: New version has lower accuracy"
        else:
            return "Similar performance - consider other factors"

    def create_ab_test(
        self,
        name: str,
        description: str,
        model_a_id: str,
        model_a_version: int,
        model_b_id: str,
        model_b_version: int,
        traffic_split: float = 0.5
    ) -> Optional[ABTest]:
        """
        Create an A/B test between two model versions.

        Args:
            name: Test name
            description: Test description
            model_a_id: Model A ID
            model_a_version: Model A version
            model_b_id: Model B ID
            model_b_version: Model B version
            traffic_split: Traffic to model A (0-1)

        Returns:
            Created A/B test
        """
        # Validate models exist
        va = self.get_version(model_a_id, model_a_version)
        vb = self.get_version(model_b_id, model_b_version)

        if not va or not vb:
            return None

        test = ABTest(
            test_id=str(uuid.uuid4()),
            name=name,
            description=description,
            model_a_id=model_a_id,
            model_a_version=model_a_version,
            model_b_id=model_b_id,
            model_b_version=model_b_version,
            traffic_split=traffic_split,
            status="active",
            start_date=datetime.utcnow(),
        )

        self.ab_tests[test.test_id] = test
        return test

    def get_ab_test_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get A/B test results."""
        test = self.ab_tests.get(test_id)
        if not test:
            return None

        return {
            "test_id": test.test_id,
            "name": test.name,
            "status": test.status,
            "model_a": f"{test.model_a_id}@v{test.model_a_version}",
            "model_b": f"{test.model_b_id}@v{test.model_b_version}",
            "traffic_split": test.traffic_split,
            "metrics_a": test.metrics_a,
            "metrics_b": test.metrics_b,
            "winner": test.winner,
            "start_date": test.start_date.isoformat(),
            "end_date": test.end_date.isoformat() if test.end_date else None,
        }

    def select_model_for_inference(
        self,
        model_id: str,
        ab_test_id: Optional[str] = None
    ) -> Optional[ModelVersion]:
        """
        Select model version for inference (handles A/B testing).

        Args:
            model_id: Model ID
            ab_test_id: Optional A/B test ID

        Returns:
            Selected model version
        """
        import random

        if ab_test_id:
            test = self.ab_tests.get(ab_test_id)
            if test and test.status == "active":
                if random.random() < test.traffic_split:
                    return self.get_version(test.model_a_id, test.model_a_version)
                else:
                    return self.get_version(test.model_b_id, test.model_b_version)

        # Return production version
        return self.get_production_version(model_id)

    def get_status(self) -> Dict[str, Any]:
        """Get registry status."""
        return {
            "storage_path": self.storage_path,
            "total_models": len(self.models),
            "total_versions": sum(
                len(m.versions) for m in self.models.values()
            ),
            "production_models": len([
                m for m in self.models.values()
                if m.production_version
            ]),
            "active_ab_tests": len([
                t for t in self.ab_tests.values()
                if t.status == "active"
            ]),
            "models": [
                {
                    "id": m.model_id,
                    "name": m.name,
                    "task": m.task.value,
                    "versions": len(m.versions),
                    "production": m.production_version,
                }
                for m in self.models.values()
            ],
        }


# Singleton instance
_model_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get or create the model registry instance."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry
