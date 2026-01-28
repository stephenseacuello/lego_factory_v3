"""
MLflow Experiment Tracking
LegoMCP PhD-Level Manufacturing Platform

Implements comprehensive ML experiment tracking with:
- Experiment and run management
- Parameter, metric, and artifact logging
- Model versioning and registry
- Hyperparameter comparison
- Visualization support
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class RunStatus(Enum):
    RUNNING = "RUNNING"
    SCHEDULED = "SCHEDULED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    KILLED = "KILLED"


@dataclass
class ExperimentRun:
    """Represents an ML experiment run."""
    run_id: str
    experiment_id: str
    experiment_name: str
    run_name: str
    status: RunStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "run_name": self.run_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "tags": self.tags,
            "artifacts": self.artifacts,
        }


class MLflowTracker:
    """
    MLflow-based experiment tracking for manufacturing ML.

    Features:
    - Experiment organization by project/task
    - Comprehensive parameter logging
    - Real-time metric tracking
    - Artifact storage (models, plots, data)
    - Run comparison and analysis
    - Model registry integration
    """

    def __init__(
        self,
        tracking_uri: str = None,
        artifact_location: str = None,
        default_experiment: str = "legomcp-default",
    ):
        self.tracking_uri = tracking_uri or os.environ.get(
            "MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"
        )
        self.artifact_location = artifact_location or os.environ.get(
            "MLFLOW_ARTIFACT_ROOT", "/app/mlflow-artifacts"
        )
        self.default_experiment = default_experiment
        self._client = None
        self._current_run = None
        self._initialized = False

        # Manufacturing-specific experiment templates
        self.experiment_templates = {
            "quality_prediction": {
                "tags": {"domain": "quality", "task": "prediction"},
                "metrics": ["accuracy", "precision", "recall", "f1", "auc_roc"],
            },
            "defect_detection": {
                "tags": {"domain": "vision", "task": "detection"},
                "metrics": ["mAP", "mAP50", "mAP75", "precision", "recall"],
            },
            "scheduling_optimization": {
                "tags": {"domain": "scheduling", "task": "optimization"},
                "metrics": ["makespan", "tardiness", "oee", "utilization"],
            },
            "predictive_maintenance": {
                "tags": {"domain": "maintenance", "task": "prediction"},
                "metrics": ["rul_mae", "rul_rmse", "precision", "recall"],
            },
            "demand_forecasting": {
                "tags": {"domain": "planning", "task": "forecasting"},
                "metrics": ["mape", "rmse", "mae", "smape"],
            },
        }

    def initialize(self):
        """Initialize MLflow client."""
        try:
            import mlflow
            from mlflow.tracking import MlflowClient

            mlflow.set_tracking_uri(self.tracking_uri)
            self._client = MlflowClient(self.tracking_uri)
            self._initialized = True

            logger.info(f"MLflow initialized: {self.tracking_uri}")

        except ImportError:
            logger.warning("mlflow not installed, using mock tracker")
            self._client = MockMlflowClient()
            self._initialized = True

    @property
    def client(self):
        if not self._initialized:
            self.initialize()
        return self._client

    def create_experiment(
        self,
        name: str,
        template: str = None,
        tags: Dict[str, str] = None,
    ) -> str:
        """
        Create or get experiment.

        Args:
            name: Experiment name
            template: Optional template from experiment_templates
            tags: Additional tags

        Returns:
            Experiment ID
        """
        try:
            import mlflow

            # Get or create experiment
            experiment = mlflow.get_experiment_by_name(name)
            if experiment:
                return experiment.experiment_id

            # Apply template if specified
            all_tags = {}
            if template and template in self.experiment_templates:
                all_tags.update(self.experiment_templates[template].get("tags", {}))
            if tags:
                all_tags.update(tags)

            experiment_id = mlflow.create_experiment(
                name,
                artifact_location=f"{self.artifact_location}/{name}",
                tags=all_tags,
            )

            logger.info(f"Created experiment: {name} ({experiment_id})")
            return experiment_id

        except Exception as e:
            logger.error(f"Failed to create experiment: {e}")
            return "mock-experiment-id"

    @contextmanager
    def start_run(
        self,
        experiment_name: str = None,
        run_name: str = None,
        tags: Dict[str, str] = None,
        nested: bool = False,
    ):
        """
        Context manager for experiment runs.

        Args:
            experiment_name: Experiment name
            run_name: Run name
            tags: Run tags
            nested: Allow nested runs

        Yields:
            ExperimentRun object
        """
        experiment_name = experiment_name or self.default_experiment
        run_name = run_name or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        try:
            import mlflow

            # Ensure experiment exists
            experiment_id = self.create_experiment(experiment_name)

            # Start run
            with mlflow.start_run(
                experiment_id=experiment_id,
                run_name=run_name,
                nested=nested,
                tags=tags,
            ) as run:
                self._current_run = ExperimentRun(
                    run_id=run.info.run_id,
                    experiment_id=experiment_id,
                    experiment_name=experiment_name,
                    run_name=run_name,
                    status=RunStatus.RUNNING,
                    start_time=datetime.utcnow(),
                    tags=tags or {},
                )

                try:
                    yield self._current_run
                    self._current_run.status = RunStatus.FINISHED
                except Exception as e:
                    self._current_run.status = RunStatus.FAILED
                    mlflow.log_param("error", str(e))
                    raise
                finally:
                    self._current_run.end_time = datetime.utcnow()
                    self._current_run = None

        except ImportError:
            # Mock run context
            self._current_run = ExperimentRun(
                run_id="mock-run-id",
                experiment_id="mock-experiment-id",
                experiment_name=experiment_name,
                run_name=run_name,
                status=RunStatus.RUNNING,
                start_time=datetime.utcnow(),
                tags=tags or {},
            )
            try:
                yield self._current_run
                self._current_run.status = RunStatus.FINISHED
            except Exception:
                self._current_run.status = RunStatus.FAILED
                raise
            finally:
                self._current_run.end_time = datetime.utcnow()
                self._current_run = None

    def log_params(self, params: Dict[str, Any]):
        """Log parameters to current run."""
        try:
            import mlflow

            # Flatten nested params
            flat_params = self._flatten_dict(params)
            mlflow.log_params(flat_params)

            if self._current_run:
                self._current_run.parameters.update(flat_params)

        except ImportError:
            if self._current_run:
                self._current_run.parameters.update(params)

    def log_param(self, key: str, value: Any):
        """Log single parameter."""
        self.log_params({key: value})

    def log_metrics(self, metrics: Dict[str, float], step: int = None):
        """Log metrics to current run."""
        try:
            import mlflow

            for key, value in metrics.items():
                mlflow.log_metric(key, value, step=step)

            if self._current_run:
                self._current_run.metrics.update(metrics)

        except ImportError:
            if self._current_run:
                self._current_run.metrics.update(metrics)

    def log_metric(self, key: str, value: float, step: int = None):
        """Log single metric."""
        self.log_metrics({key: value}, step=step)

    def log_artifact(self, local_path: str, artifact_path: str = None):
        """Log artifact file."""
        try:
            import mlflow

            mlflow.log_artifact(local_path, artifact_path)

            if self._current_run:
                self._current_run.artifacts.append(local_path)

        except ImportError:
            if self._current_run:
                self._current_run.artifacts.append(local_path)

    def log_artifacts(self, local_dir: str, artifact_path: str = None):
        """Log all files in directory."""
        try:
            import mlflow

            mlflow.log_artifacts(local_dir, artifact_path)

        except ImportError:
            pass

    def log_model(
        self,
        model: Any,
        artifact_path: str,
        registered_model_name: str = None,
        **kwargs,
    ):
        """
        Log ML model.

        Args:
            model: Model object (sklearn, pytorch, tensorflow, etc.)
            artifact_path: Path in artifact store
            registered_model_name: Name for model registry
        """
        try:
            import mlflow

            # Detect model type and log appropriately
            model_type = type(model).__module__.split('.')[0]

            if model_type == "sklearn":
                mlflow.sklearn.log_model(
                    model,
                    artifact_path,
                    registered_model_name=registered_model_name,
                    **kwargs,
                )
            elif model_type == "torch":
                mlflow.pytorch.log_model(
                    model,
                    artifact_path,
                    registered_model_name=registered_model_name,
                    **kwargs,
                )
            elif model_type == "tensorflow":
                mlflow.tensorflow.log_model(
                    model,
                    artifact_path,
                    registered_model_name=registered_model_name,
                    **kwargs,
                )
            else:
                # Generic model logging
                mlflow.pyfunc.log_model(
                    artifact_path,
                    python_model=model,
                    registered_model_name=registered_model_name,
                    **kwargs,
                )

            logger.info(f"Logged model to {artifact_path}")

        except ImportError:
            logger.warning("mlflow not available, model not logged")

    def log_figure(self, figure: Any, artifact_path: str):
        """Log matplotlib/plotly figure."""
        try:
            import mlflow

            mlflow.log_figure(figure, artifact_path)

        except ImportError:
            pass

    def log_dict(self, dictionary: Dict[str, Any], artifact_path: str):
        """Log dictionary as JSON artifact."""
        try:
            import mlflow

            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False
            ) as f:
                json.dump(dictionary, f, indent=2, default=str)
                temp_path = f.name

            mlflow.log_artifact(temp_path, artifact_path)
            os.unlink(temp_path)

        except ImportError:
            pass

    def log_confusion_matrix(
        self,
        y_true: List[Any],
        y_pred: List[Any],
        labels: List[str] = None,
    ):
        """Log confusion matrix as artifact."""
        try:
            import mlflow
            from sklearn.metrics import confusion_matrix
            import matplotlib.pyplot as plt
            import seaborn as sns

            cm = confusion_matrix(y_true, y_pred)

            fig, ax = plt.subplots(figsize=(10, 8))
            sns.heatmap(
                cm,
                annot=True,
                fmt='d',
                cmap='Blues',
                xticklabels=labels,
                yticklabels=labels,
                ax=ax,
            )
            ax.set_xlabel('Predicted')
            ax.set_ylabel('Actual')
            ax.set_title('Confusion Matrix')

            mlflow.log_figure(fig, "confusion_matrix.png")
            plt.close(fig)

        except ImportError:
            pass

    def set_tag(self, key: str, value: str):
        """Set run tag."""
        try:
            import mlflow

            mlflow.set_tag(key, value)

            if self._current_run:
                self._current_run.tags[key] = value

        except ImportError:
            if self._current_run:
                self._current_run.tags[key] = value

    def set_tags(self, tags: Dict[str, str]):
        """Set multiple tags."""
        for key, value in tags.items():
            self.set_tag(key, value)

    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        """Get run by ID."""
        try:
            run = self.client.get_run(run_id)
            return ExperimentRun(
                run_id=run.info.run_id,
                experiment_id=run.info.experiment_id,
                experiment_name="",  # Would need to look up
                run_name=run.data.tags.get("mlflow.runName", ""),
                status=RunStatus(run.info.status),
                start_time=datetime.fromtimestamp(run.info.start_time / 1000),
                end_time=(
                    datetime.fromtimestamp(run.info.end_time / 1000)
                    if run.info.end_time else None
                ),
                parameters=run.data.params,
                metrics=run.data.metrics,
                tags=run.data.tags,
            )
        except Exception as e:
            logger.error(f"Failed to get run: {e}")
            return None

    def search_runs(
        self,
        experiment_names: List[str] = None,
        filter_string: str = None,
        order_by: List[str] = None,
        max_results: int = 100,
    ) -> List[ExperimentRun]:
        """Search for runs matching criteria."""
        try:
            import mlflow

            experiment_ids = []
            if experiment_names:
                for name in experiment_names:
                    exp = mlflow.get_experiment_by_name(name)
                    if exp:
                        experiment_ids.append(exp.experiment_id)

            runs = mlflow.search_runs(
                experiment_ids=experiment_ids if experiment_ids else None,
                filter_string=filter_string,
                order_by=order_by,
                max_results=max_results,
            )

            results = []
            for _, row in runs.iterrows():
                results.append(ExperimentRun(
                    run_id=row["run_id"],
                    experiment_id=row.get("experiment_id", ""),
                    experiment_name="",
                    run_name=row.get("tags.mlflow.runName", ""),
                    status=RunStatus(row["status"]),
                    start_time=row["start_time"],
                    end_time=row.get("end_time"),
                    parameters={k.replace("params.", ""): v for k, v in row.items() if k.startswith("params.")},
                    metrics={k.replace("metrics.", ""): v for k, v in row.items() if k.startswith("metrics.")},
                    tags={k.replace("tags.", ""): v for k, v in row.items() if k.startswith("tags.")},
                ))

            return results

        except Exception as e:
            logger.error(f"Failed to search runs: {e}")
            return []

    def compare_runs(
        self,
        run_ids: List[str],
        metrics: List[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Compare multiple runs."""
        comparison = {}

        for run_id in run_ids:
            run = self.get_run(run_id)
            if run:
                run_data = {
                    "parameters": run.parameters,
                    "metrics": (
                        {k: v for k, v in run.metrics.items() if k in metrics}
                        if metrics else run.metrics
                    ),
                    "status": run.status.value,
                    "duration": (
                        (run.end_time - run.start_time).total_seconds()
                        if run.end_time else None
                    ),
                }
                comparison[run_id] = run_data

        return comparison

    def get_best_run(
        self,
        experiment_name: str,
        metric: str,
        maximize: bool = True,
    ) -> Optional[ExperimentRun]:
        """Get best run by metric."""
        order = "DESC" if maximize else "ASC"
        runs = self.search_runs(
            experiment_names=[experiment_name],
            order_by=[f"metrics.{metric} {order}"],
            max_results=1,
        )
        return runs[0] if runs else None

    def _flatten_dict(
        self,
        d: Dict[str, Any],
        parent_key: str = "",
        sep: str = ".",
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


class MockMlflowClient:
    """Mock MLflow client for testing."""

    def get_run(self, run_id):
        return None

    def search_runs(self, *args, **kwargs):
        return []


# Global instance
mlflow_tracker = MLflowTracker()
