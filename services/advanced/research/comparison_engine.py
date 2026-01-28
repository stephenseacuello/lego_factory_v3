"""
Comparison Engine - Experiment and model comparison.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import statistics
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricComparison:
    """Comparison of a single metric across runs."""
    metric_key: str
    values: Dict[str, float]  # run_id -> final value
    best_run_id: str
    best_value: float
    worst_run_id: str
    worst_value: float
    mean: float
    std: float
    improvement_pct: float  # Best vs worst improvement


@dataclass
class ParameterVariation:
    """How a parameter varied across runs."""
    param_key: str
    values: Dict[str, str]  # run_id -> value
    unique_values: List[str]
    is_constant: bool


@dataclass
class ExperimentComparison:
    """Complete comparison of experiment runs."""
    experiment_id: str
    run_ids: List[str]
    metric_comparisons: Dict[str, MetricComparison]
    parameter_variations: Dict[str, ParameterVariation]
    best_overall_run: Optional[str]
    summary: str


class ComparisonEngine:
    """
    Compare experiment runs and model versions.

    Features:
    - Multi-metric comparison
    - Parameter sensitivity analysis
    - Statistical significance testing
    - Visualization data generation
    """

    def __init__(self, experiment_tracker=None, model_registry=None):
        self._tracker = experiment_tracker
        self._registry = model_registry

    def set_experiment_tracker(self, tracker) -> None:
        """Set experiment tracker."""
        self._tracker = tracker

    def set_model_registry(self, registry) -> None:
        """Set model registry."""
        self._registry = registry

    def compare_runs(self,
                    run_ids: List[str],
                    primary_metric: str,
                    maximize: bool = True) -> ExperimentComparison:
        """
        Compare multiple experiment runs.

        Args:
            run_ids: Run IDs to compare
            primary_metric: Metric to optimize
            maximize: Whether higher is better

        Returns:
            Comparison result
        """
        if not self._tracker:
            raise RuntimeError("Experiment tracker not set")

        runs = [self._tracker.get_run(rid) for rid in run_ids]
        runs = [r for r in runs if r is not None]

        if len(runs) < 2:
            raise ValueError("Need at least 2 runs to compare")

        # Get experiment ID from first run
        experiment_id = runs[0].experiment_id

        # Compare metrics
        metric_comparisons = self._compare_metrics(runs, maximize)

        # Analyze parameters
        param_variations = self._analyze_parameters(runs)

        # Find best overall run
        best_run = self._find_best_run(runs, primary_metric, maximize)

        # Generate summary
        summary = self._generate_summary(
            runs, metric_comparisons, param_variations, primary_metric, best_run
        )

        return ExperimentComparison(
            experiment_id=experiment_id,
            run_ids=[r.run_id for r in runs],
            metric_comparisons=metric_comparisons,
            parameter_variations=param_variations,
            best_overall_run=best_run,
            summary=summary
        )

    def _compare_metrics(self,
                        runs: List,
                        maximize: bool) -> Dict[str, MetricComparison]:
        """Compare metrics across runs."""
        comparisons = {}

        # Collect all metric keys
        all_keys = set()
        for run in runs:
            all_keys.update(run.metrics.keys())

        for key in all_keys:
            values = {}
            for run in runs:
                if key in run.metrics and run.metrics[key]:
                    values[run.run_id] = run.metrics[key][-1].value

            if len(values) < 2:
                continue

            value_list = list(values.values())

            if maximize:
                best_id = max(values.keys(), key=lambda k: values[k])
                worst_id = min(values.keys(), key=lambda k: values[k])
            else:
                best_id = min(values.keys(), key=lambda k: values[k])
                worst_id = max(values.keys(), key=lambda k: values[k])

            best_val = values[best_id]
            worst_val = values[worst_id]

            # Calculate improvement
            if worst_val != 0:
                if maximize:
                    improvement = ((best_val - worst_val) / abs(worst_val)) * 100
                else:
                    improvement = ((worst_val - best_val) / abs(worst_val)) * 100
            else:
                improvement = 0.0

            comparisons[key] = MetricComparison(
                metric_key=key,
                values=values,
                best_run_id=best_id,
                best_value=best_val,
                worst_run_id=worst_id,
                worst_value=worst_val,
                mean=statistics.mean(value_list),
                std=statistics.stdev(value_list) if len(value_list) > 1 else 0.0,
                improvement_pct=improvement
            )

        return comparisons

    def _analyze_parameters(self, runs: List) -> Dict[str, ParameterVariation]:
        """Analyze parameter variations."""
        variations = {}

        # Collect all parameter keys
        all_keys = set()
        for run in runs:
            all_keys.update(run.parameters.keys())

        for key in all_keys:
            values = {}
            for run in runs:
                values[run.run_id] = run.parameters.get(key, "N/A")

            unique = list(set(values.values()))

            variations[key] = ParameterVariation(
                param_key=key,
                values=values,
                unique_values=unique,
                is_constant=len(unique) == 1
            )

        return variations

    def _find_best_run(self,
                      runs: List,
                      metric: str,
                      maximize: bool) -> Optional[str]:
        """Find best run by primary metric."""
        candidates = []

        for run in runs:
            if metric in run.metrics and run.metrics[metric]:
                value = run.metrics[metric][-1].value
                candidates.append((run.run_id, value))

        if not candidates:
            return None

        if maximize:
            return max(candidates, key=lambda x: x[1])[0]
        else:
            return min(candidates, key=lambda x: x[1])[0]

    def _generate_summary(self,
                         runs: List,
                         metrics: Dict[str, MetricComparison],
                         params: Dict[str, ParameterVariation],
                         primary_metric: str,
                         best_run: Optional[str]) -> str:
        """Generate human-readable comparison summary."""
        lines = []
        lines.append(f"Compared {len(runs)} runs")

        if best_run:
            best_run_obj = next((r for r in runs if r.run_id == best_run), None)
            if best_run_obj:
                lines.append(f"Best run: {best_run_obj.run_name} ({best_run})")

        if primary_metric in metrics:
            pm = metrics[primary_metric]
            lines.append(f"Primary metric ({primary_metric}):")
            lines.append(f"  - Best: {pm.best_value:.4f}")
            lines.append(f"  - Mean: {pm.mean:.4f} +/- {pm.std:.4f}")
            lines.append(f"  - Improvement: {pm.improvement_pct:.1f}%")

        # List varied parameters
        varied = [k for k, v in params.items() if not v.is_constant]
        if varied:
            lines.append(f"Varied parameters: {', '.join(varied)}")

        return "\n".join(lines)

    def parameter_sensitivity(self,
                             experiment_id: str,
                             parameter: str,
                             metric: str) -> Dict[str, Any]:
        """
        Analyze sensitivity of metric to parameter.

        Args:
            experiment_id: Experiment to analyze
            parameter: Parameter to vary
            metric: Metric to measure

        Returns:
            Sensitivity analysis
        """
        if not self._tracker:
            raise RuntimeError("Experiment tracker not set")

        runs = self._tracker.get_runs(experiment_id)

        # Group runs by parameter value
        groups: Dict[str, List[float]] = {}

        for run in runs:
            param_val = run.parameters.get(parameter)
            if param_val is None:
                continue

            if metric not in run.metrics or not run.metrics[metric]:
                continue

            metric_val = run.metrics[metric][-1].value

            if param_val not in groups:
                groups[param_val] = []
            groups[param_val].append(metric_val)

        # Calculate statistics per group
        analysis = {}
        for param_val, metric_vals in groups.items():
            analysis[param_val] = {
                'count': len(metric_vals),
                'mean': statistics.mean(metric_vals),
                'std': statistics.stdev(metric_vals) if len(metric_vals) > 1 else 0.0,
                'min': min(metric_vals),
                'max': max(metric_vals)
            }

        return {
            'parameter': parameter,
            'metric': metric,
            'groups': analysis
        }

    def compare_models(self,
                      model_names: List[str],
                      metric: str,
                      maximize: bool = True) -> Dict[str, Any]:
        """
        Compare registered models.

        Args:
            model_names: Models to compare
            metric: Metric to compare
            maximize: Whether higher is better

        Returns:
            Model comparison
        """
        if not self._registry:
            raise RuntimeError("Model registry not set")

        results = []

        for name in model_names:
            version = self._registry.get_production_model(name)
            if not version:
                version = self._registry.get_model_version(name)

            if version and metric in version.metrics:
                results.append({
                    'model': name,
                    'version': version.version,
                    'stage': version.stage.value,
                    'value': version.metrics[metric]
                })

        if not results:
            return {'error': 'No models found with specified metric'}

        # Sort by metric
        results.sort(key=lambda x: x['value'], reverse=maximize)

        return {
            'metric': metric,
            'maximize': maximize,
            'rankings': results,
            'best': results[0]['model'] if results else None
        }

    def generate_comparison_table(self,
                                 comparison: ExperimentComparison,
                                 metrics: Optional[List[str]] = None) -> List[List[str]]:
        """
        Generate comparison table data.

        Args:
            comparison: Comparison result
            metrics: Metrics to include (all if None)

        Returns:
            Table as list of rows
        """
        if metrics is None:
            metrics = list(comparison.metric_comparisons.keys())

        # Header row
        rows = [["Metric", "Best", "Best Value", "Mean", "Std", "Improvement"]]

        for metric_key in metrics:
            if metric_key not in comparison.metric_comparisons:
                continue

            mc = comparison.metric_comparisons[metric_key]
            rows.append([
                metric_key,
                mc.best_run_id[:8],
                f"{mc.best_value:.4f}",
                f"{mc.mean:.4f}",
                f"{mc.std:.4f}",
                f"{mc.improvement_pct:.1f}%"
            ])

        return rows

    def export_comparison(self, comparison: ExperimentComparison) -> Dict[str, Any]:
        """Export comparison to dictionary."""
        return {
            'experiment_id': comparison.experiment_id,
            'run_ids': comparison.run_ids,
            'best_overall_run': comparison.best_overall_run,
            'summary': comparison.summary,
            'metrics': {
                key: {
                    'best_run': mc.best_run_id,
                    'best_value': mc.best_value,
                    'mean': mc.mean,
                    'std': mc.std,
                    'improvement_pct': mc.improvement_pct,
                    'values': mc.values
                }
                for key, mc in comparison.metric_comparisons.items()
            },
            'parameters': {
                key: {
                    'is_constant': pv.is_constant,
                    'unique_values': pv.unique_values,
                    'values': pv.values
                }
                for key, pv in comparison.parameter_variations.items()
            }
        }
