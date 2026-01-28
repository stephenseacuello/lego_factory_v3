"""
Experiment Tracker - MLflow-style experiment tracking.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid
import json
import logging

logger = logging.getLogger(__name__)


class RunStatus(Enum):
    """Status of experiment run."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


@dataclass
class Metric:
    """Single metric measurement."""
    key: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    step: int = 0


@dataclass
class Parameter:
    """Experiment parameter."""
    key: str
    value: str


@dataclass
class Run:
    """Single experiment run."""
    run_id: str
    experiment_id: str
    run_name: str
    status: RunStatus = RunStatus.RUNNING
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, List[Metric]] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Experiment:
    """Experiment container for multiple runs."""
    experiment_id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    runs: List[str] = field(default_factory=list)


class ExperimentTracker:
    """
    Track manufacturing experiments with full reproducibility.

    Features:
    - Parameter logging
    - Metric tracking with history
    - Artifact storage
    - Run comparison
    - Tag-based organization
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self._experiments: Dict[str, Experiment] = {}
        self._runs: Dict[str, Run] = {}
        self._active_run: Optional[str] = None

    def create_experiment(self,
                         name: str,
                         description: str = "",
                         tags: Optional[Dict[str, str]] = None) -> Experiment:
        """
        Create a new experiment.

        Args:
            name: Experiment name
            description: Description of experiment goals
            tags: Optional tags for organization

        Returns:
            Created experiment
        """
        # Check if experiment with name exists
        for exp in self._experiments.values():
            if exp.name == name:
                logger.info(f"Experiment '{name}' already exists")
                return exp

        experiment = Experiment(
            experiment_id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            tags=tags or {}
        )
        self._experiments[experiment.experiment_id] = experiment
        logger.info(f"Created experiment: {name} ({experiment.experiment_id})")
        return experiment

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self._experiments.get(experiment_id)

    def get_experiment_by_name(self, name: str) -> Optional[Experiment]:
        """Get experiment by name."""
        for exp in self._experiments.values():
            if exp.name == name:
                return exp
        return None

    def start_run(self,
                 experiment_id: str,
                 run_name: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None) -> Run:
        """
        Start a new run within an experiment.

        Args:
            experiment_id: Parent experiment ID
            run_name: Optional run name
            tags: Optional run tags

        Returns:
            Created run
        """
        if experiment_id not in self._experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        run = Run(
            run_id=str(uuid.uuid4())[:8],
            experiment_id=experiment_id,
            run_name=run_name or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            tags=tags or {}
        )

        self._runs[run.run_id] = run
        self._experiments[experiment_id].runs.append(run.run_id)
        self._active_run = run.run_id

        logger.info(f"Started run: {run.run_name} ({run.run_id})")
        return run

    def end_run(self, status: RunStatus = RunStatus.COMPLETED) -> None:
        """End the current active run."""
        if self._active_run is None:
            logger.warning("No active run to end")
            return

        run = self._runs[self._active_run]
        run.status = status
        run.end_time = datetime.utcnow()

        logger.info(f"Ended run: {run.run_name} with status {status.value}")
        self._active_run = None

    def log_param(self, key: str, value: Any) -> None:
        """Log a parameter for the current run."""
        if self._active_run is None:
            raise RuntimeError("No active run - call start_run() first")

        run = self._runs[self._active_run]
        run.parameters[key] = str(value)

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log multiple parameters."""
        for key, value in params.items():
            self.log_param(key, value)

    def log_metric(self, key: str, value: float, step: Optional[int] = None) -> None:
        """
        Log a metric for the current run.

        Args:
            key: Metric name
            value: Metric value
            step: Optional step number for time series
        """
        if self._active_run is None:
            raise RuntimeError("No active run - call start_run() first")

        run = self._runs[self._active_run]

        if key not in run.metrics:
            run.metrics[key] = []

        metric = Metric(
            key=key,
            value=value,
            step=step if step is not None else len(run.metrics[key])
        )
        run.metrics[key].append(metric)

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        """Log multiple metrics."""
        for key, value in metrics.items():
            self.log_metric(key, value, step)

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag for the current run."""
        if self._active_run is None:
            raise RuntimeError("No active run")

        run = self._runs[self._active_run]
        run.tags[key] = value

    def log_artifact(self, artifact_path: str) -> None:
        """Log an artifact path for the current run."""
        if self._active_run is None:
            raise RuntimeError("No active run")

        run = self._runs[self._active_run]
        run.artifacts.append(artifact_path)

    def get_run(self, run_id: str) -> Optional[Run]:
        """Get run by ID."""
        return self._runs.get(run_id)

    def get_runs(self,
                experiment_id: str,
                status: Optional[RunStatus] = None) -> List[Run]:
        """Get runs for an experiment."""
        if experiment_id not in self._experiments:
            return []

        experiment = self._experiments[experiment_id]
        runs = [self._runs[rid] for rid in experiment.runs if rid in self._runs]

        if status:
            runs = [r for r in runs if r.status == status]

        return runs

    def search_runs(self,
                   experiment_ids: Optional[List[str]] = None,
                   filter_string: Optional[str] = None,
                   max_results: int = 100) -> List[Run]:
        """
        Search runs with filters.

        Args:
            experiment_ids: Experiments to search
            filter_string: Simple key=value filter
            max_results: Maximum results to return

        Returns:
            Matching runs
        """
        if experiment_ids:
            runs = []
            for exp_id in experiment_ids:
                runs.extend(self.get_runs(exp_id))
        else:
            runs = list(self._runs.values())

        # Apply simple filter
        if filter_string:
            # Parse simple "key=value" or "metrics.key>value" format
            if '=' in filter_string:
                key, value = filter_string.split('=', 1)
                key = key.strip()
                value = value.strip()

                if key.startswith('params.'):
                    param_key = key[7:]
                    runs = [r for r in runs if r.parameters.get(param_key) == value]
                elif key.startswith('tags.'):
                    tag_key = key[5:]
                    runs = [r for r in runs if r.tags.get(tag_key) == value]

        return runs[:max_results]

    def get_metric_history(self, run_id: str, metric_key: str) -> List[Metric]:
        """Get metric history for a run."""
        run = self._runs.get(run_id)
        if not run:
            return []
        return run.metrics.get(metric_key, [])

    def list_experiments(self) -> List[Experiment]:
        """List all experiments."""
        return list(self._experiments.values())

    def delete_experiment(self, experiment_id: str) -> bool:
        """Delete experiment and its runs."""
        if experiment_id not in self._experiments:
            return False

        experiment = self._experiments[experiment_id]

        # Delete runs
        for run_id in experiment.runs:
            if run_id in self._runs:
                del self._runs[run_id]

        del self._experiments[experiment_id]
        logger.info(f"Deleted experiment: {experiment_id}")
        return True

    def export_run(self, run_id: str) -> Dict[str, Any]:
        """Export run data as dictionary."""
        run = self._runs.get(run_id)
        if not run:
            return {}

        return {
            'run_id': run.run_id,
            'experiment_id': run.experiment_id,
            'run_name': run.run_name,
            'status': run.status.value,
            'start_time': run.start_time.isoformat(),
            'end_time': run.end_time.isoformat() if run.end_time else None,
            'parameters': run.parameters,
            'metrics': {
                key: [{'value': m.value, 'step': m.step, 'timestamp': m.timestamp.isoformat()}
                      for m in metrics]
                for key, metrics in run.metrics.items()
            },
            'tags': run.tags,
            'artifacts': run.artifacts
        }

    def get_best_run(self,
                    experiment_id: str,
                    metric_key: str,
                    maximize: bool = True) -> Optional[Run]:
        """Get best run by metric value."""
        runs = self.get_runs(experiment_id, status=RunStatus.COMPLETED)

        best_run = None
        best_value = float('-inf') if maximize else float('inf')

        for run in runs:
            metrics = run.metrics.get(metric_key, [])
            if not metrics:
                continue

            final_value = metrics[-1].value

            if maximize and final_value > best_value:
                best_value = final_value
                best_run = run
            elif not maximize and final_value < best_value:
                best_value = final_value
                best_run = run

        return best_run
