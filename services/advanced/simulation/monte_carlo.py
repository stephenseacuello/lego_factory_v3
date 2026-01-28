"""
Monte Carlo Simulation Engine

LegoMCP World-Class Manufacturing System v5.0
Phase 18: Advanced Simulation Capabilities

Provides:
- Risk-aware capacity planning
- Probabilistic demand forecasting
- Quality yield analysis
- Machine reliability simulation
- Supply chain disruption modeling
"""

import logging
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


class DistributionType(str, Enum):
    """Probability distribution types."""
    NORMAL = "normal"
    TRIANGULAR = "triangular"
    UNIFORM = "uniform"
    EXPONENTIAL = "exponential"
    LOGNORMAL = "lognormal"
    BETA = "beta"
    POISSON = "poisson"
    WEIBULL = "weibull"


@dataclass
class Distribution:
    """A probability distribution specification."""
    dist_type: DistributionType
    params: Dict[str, float] = field(default_factory=dict)

    def sample(self) -> float:
        """Sample a value from this distribution."""
        if self.dist_type == DistributionType.NORMAL:
            return random.gauss(
                self.params.get("mean", 0),
                self.params.get("std", 1)
            )
        elif self.dist_type == DistributionType.TRIANGULAR:
            return random.triangular(
                self.params.get("low", 0),
                self.params.get("high", 1),
                self.params.get("mode", 0.5)
            )
        elif self.dist_type == DistributionType.UNIFORM:
            return random.uniform(
                self.params.get("low", 0),
                self.params.get("high", 1)
            )
        elif self.dist_type == DistributionType.EXPONENTIAL:
            return random.expovariate(
                1 / self.params.get("mean", 1)
            )
        elif self.dist_type == DistributionType.LOGNORMAL:
            return random.lognormvariate(
                self.params.get("mu", 0),
                self.params.get("sigma", 1)
            )
        elif self.dist_type == DistributionType.BETA:
            return random.betavariate(
                self.params.get("alpha", 2),
                self.params.get("beta", 2)
            )
        elif self.dist_type == DistributionType.WEIBULL:
            return random.weibullvariate(
                self.params.get("alpha", 1),  # scale
                self.params.get("beta", 1.5)  # shape
            )
        else:
            return random.random()


@dataclass
class SimulationVariable:
    """A variable in the Monte Carlo simulation."""
    name: str
    distribution: Distribution
    unit: str = ""
    description: str = ""

    # Constraints
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def sample(self) -> float:
        """Sample a constrained value."""
        value = self.distribution.sample()

        if self.min_value is not None:
            value = max(self.min_value, value)
        if self.max_value is not None:
            value = min(self.max_value, value)

        return value


@dataclass
class MonteCarloResult:
    """Results from a Monte Carlo simulation."""
    simulation_id: str
    name: str
    iterations: int

    # Output statistics
    outputs: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Convergence
    converged: bool = False
    convergence_iteration: Optional[int] = None

    # Risk metrics
    var_95: Dict[str, float] = field(default_factory=dict)  # Value at Risk
    cvar_95: Dict[str, float] = field(default_factory=dict)  # Conditional VaR

    # Sensitivity
    sensitivity: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Raw data (optional, for visualization)
    raw_outputs: Dict[str, List[float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "simulation_id": self.simulation_id,
            "name": self.name,
            "iterations": self.iterations,
            "outputs": self.outputs,
            "converged": self.converged,
            "convergence_iteration": self.convergence_iteration,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "sensitivity": self.sensitivity,
        }


class MonteCarloEngine:
    """
    Monte Carlo Simulation Engine.

    Performs probabilistic analysis for manufacturing planning:
    - Capacity planning with demand uncertainty
    - Quality yield prediction
    - Cost estimation with risk
    - Schedule reliability analysis
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        default_iterations: int = 10000,
    ):
        self.seed = seed
        self.default_iterations = default_iterations

        if seed is not None:
            random.seed(seed)

        # Input variables
        self._variables: Dict[str, SimulationVariable] = {}

        # Model function
        self._model: Optional[Callable[[Dict[str, float]], Dict[str, float]]] = None

    def add_variable(self, variable: SimulationVariable) -> None:
        """Add an input variable."""
        self._variables[variable.name] = variable

    def add_variables(self, variables: List[SimulationVariable]) -> None:
        """Add multiple input variables."""
        for var in variables:
            self.add_variable(var)

    def set_model(
        self,
        model: Callable[[Dict[str, float]], Dict[str, float]]
    ) -> None:
        """Set the simulation model function."""
        self._model = model

    def run(
        self,
        iterations: Optional[int] = None,
        name: str = "simulation",
        check_convergence: bool = True,
        convergence_threshold: float = 0.01,
        store_raw: bool = False,
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.

        Args:
            iterations: Number of iterations
            name: Simulation name
            check_convergence: Whether to check for convergence
            convergence_threshold: Coefficient of variation threshold
            store_raw: Whether to store raw output values

        Returns:
            MonteCarloResult
        """
        if not self._model:
            raise ValueError("Model function not set")

        n_iter = iterations or self.default_iterations

        logger.info(f"Starting Monte Carlo simulation: {name}, iterations={n_iter}")

        # Storage for outputs
        all_outputs: Dict[str, List[float]] = {}

        # Track convergence
        running_means: Dict[str, List[float]] = {}
        converged = False
        convergence_iter = None

        for i in range(n_iter):
            # Sample inputs
            inputs = {
                name: var.sample()
                for name, var in self._variables.items()
            }

            # Run model
            outputs = self._model(inputs)

            # Store outputs
            for key, value in outputs.items():
                if key not in all_outputs:
                    all_outputs[key] = []
                all_outputs[key].append(value)

                # Track running mean for convergence
                if check_convergence and key not in running_means:
                    running_means[key] = []

            # Check convergence periodically
            if check_convergence and (i + 1) % 100 == 0 and i > 500:
                all_converged = True
                for key, values in all_outputs.items():
                    current_mean = statistics.mean(values)
                    running_means[key].append(current_mean)

                    if len(running_means[key]) >= 5:
                        recent_means = running_means[key][-5:]
                        cv = statistics.stdev(recent_means) / abs(current_mean) if current_mean != 0 else 0
                        if cv > convergence_threshold:
                            all_converged = False

                if all_converged and not converged:
                    converged = True
                    convergence_iter = i + 1
                    logger.info(f"Simulation converged at iteration {i + 1}")

        # Calculate statistics
        result = MonteCarloResult(
            simulation_id=str(uuid4()),
            name=name,
            iterations=n_iter,
            converged=converged,
            convergence_iteration=convergence_iter,
        )

        for key, values in all_outputs.items():
            sorted_vals = sorted(values)
            n = len(values)

            result.outputs[key] = {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "std": statistics.stdev(values) if n > 1 else 0,
                "min": min(values),
                "max": max(values),
                "p5": sorted_vals[int(n * 0.05)],
                "p25": sorted_vals[int(n * 0.25)],
                "p75": sorted_vals[int(n * 0.75)],
                "p95": sorted_vals[int(n * 0.95)],
            }

            # Value at Risk (95th percentile of losses/costs)
            result.var_95[key] = sorted_vals[int(n * 0.95)]

            # Conditional VaR (expected value beyond VaR)
            var_threshold = result.var_95[key]
            tail_values = [v for v in values if v >= var_threshold]
            result.cvar_95[key] = statistics.mean(tail_values) if tail_values else var_threshold

            if store_raw:
                result.raw_outputs[key] = values

        # Calculate sensitivity (correlation with outputs)
        result.sensitivity = self._calculate_sensitivity(all_outputs)

        logger.info(f"Simulation complete: {name}")

        return result

    def _calculate_sensitivity(
        self,
        outputs: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate sensitivity of outputs to inputs using correlation."""
        sensitivity = {}

        # We would need to store input samples to calculate this properly
        # For now, return empty dict - would be implemented with input tracking

        return sensitivity

    def capacity_planning(
        self,
        demand_distribution: Distribution,
        capacity: float,
        lead_time_distribution: Distribution,
        safety_stock_days: float = 5.0,
        iterations: int = 5000,
    ) -> MonteCarloResult:
        """
        Run capacity planning simulation.

        Args:
            demand_distribution: Daily demand distribution
            capacity: Daily production capacity
            lead_time_distribution: Supplier lead time distribution
            safety_stock_days: Target safety stock in days
            iterations: Number of iterations

        Returns:
            MonteCarloResult with service level and inventory metrics
        """
        self.add_variables([
            SimulationVariable(
                name="daily_demand",
                distribution=demand_distribution,
                min_value=0,
            ),
            SimulationVariable(
                name="lead_time",
                distribution=lead_time_distribution,
                min_value=1,
            ),
        ])

        def capacity_model(inputs: Dict[str, float]) -> Dict[str, float]:
            demand = inputs["daily_demand"]
            lead_time = inputs["lead_time"]

            # Calculate metrics
            demand_during_lead_time = demand * lead_time
            safety_stock = demand * safety_stock_days
            reorder_point = demand_during_lead_time + safety_stock

            # Service level (can we meet demand?)
            can_meet_demand = 1.0 if capacity >= demand else capacity / demand

            # Inventory holding
            avg_inventory = safety_stock + (demand * lead_time / 2)

            return {
                "service_level": can_meet_demand,
                "demand_during_lead_time": demand_during_lead_time,
                "reorder_point": reorder_point,
                "avg_inventory": avg_inventory,
                "capacity_utilization": min(1.0, demand / capacity),
            }

        self.set_model(capacity_model)
        return self.run(iterations=iterations, name="capacity_planning")

    def quality_yield_simulation(
        self,
        process_cpk: float = 1.33,
        inspection_effectiveness: float = 0.95,
        rework_rate: float = 0.3,
        iterations: int = 5000,
    ) -> MonteCarloResult:
        """
        Simulate quality yield with process variation.

        Args:
            process_cpk: Process capability index
            inspection_effectiveness: Probability of detecting defects
            rework_rate: Probability of successful rework
            iterations: Number of iterations

        Returns:
            MonteCarloResult with yield and cost metrics
        """
        # Convert Cpk to defect rate (approximate)
        # Cpk 1.0 ~ 2700 ppm, Cpk 1.33 ~ 63 ppm, Cpk 2.0 ~ 0.002 ppm
        base_defect_rate = 2 * (1 - self._phi(3 * process_cpk))

        self.add_variables([
            SimulationVariable(
                name="defect_rate",
                distribution=Distribution(
                    DistributionType.BETA,
                    {"alpha": 2, "beta": (2 / base_defect_rate) - 2}
                ),
                min_value=0,
                max_value=1,
            ),
            SimulationVariable(
                name="inspection_catch",
                distribution=Distribution(
                    DistributionType.BETA,
                    {"alpha": inspection_effectiveness * 20, "beta": (1 - inspection_effectiveness) * 20}
                ),
                min_value=0,
                max_value=1,
            ),
        ])

        def yield_model(inputs: Dict[str, float]) -> Dict[str, float]:
            defect_rate = inputs["defect_rate"]
            inspection = inputs["inspection_catch"]

            # First pass yield
            fpy = 1 - defect_rate

            # Detected defects
            detected = defect_rate * inspection

            # Escaped defects (reach customer)
            escaped = defect_rate * (1 - inspection)

            # Rework yield
            reworked = detected * rework_rate

            # Final yield
            final_yield = fpy + reworked

            # Cost of quality (as % of production cost)
            scrap_cost = (detected * (1 - rework_rate)) * 1.0  # 100% of unit cost
            rework_cost = reworked * 0.3  # 30% of unit cost
            warranty_cost = escaped * 5.0  # 5x unit cost for field failures
            inspection_cost = 0.02  # 2% for inspection

            coq = scrap_cost + rework_cost + warranty_cost + inspection_cost

            return {
                "first_pass_yield": fpy,
                "final_yield": final_yield,
                "escaped_defects_ppm": escaped * 1_000_000,
                "cost_of_quality_pct": coq * 100,
                "scrap_rate": detected * (1 - rework_rate),
            }

        self.set_model(yield_model)
        return self.run(iterations=iterations, name="quality_yield")

    def machine_reliability(
        self,
        mtbf_hours: float = 500,
        mttr_hours: float = 4,
        planned_maintenance_interval: float = 168,  # Weekly
        iterations: int = 5000,
        horizon_hours: float = 720,  # 30 days
    ) -> MonteCarloResult:
        """
        Simulate machine reliability and availability.

        Args:
            mtbf_hours: Mean time between failures
            mttr_hours: Mean time to repair
            planned_maintenance_interval: Hours between PM
            iterations: Number of iterations
            horizon_hours: Simulation horizon

        Returns:
            MonteCarloResult with availability metrics
        """
        self.add_variables([
            SimulationVariable(
                name="time_to_failure",
                distribution=Distribution(
                    DistributionType.WEIBULL,
                    {"alpha": mtbf_hours, "beta": 1.5}
                ),
                min_value=1,
            ),
            SimulationVariable(
                name="repair_time",
                distribution=Distribution(
                    DistributionType.LOGNORMAL,
                    {"mu": math.log(mttr_hours), "sigma": 0.5}
                ),
                min_value=0.5,
            ),
        ])

        def reliability_model(inputs: Dict[str, float]) -> Dict[str, float]:
            ttf = inputs["time_to_failure"]
            repair = inputs["repair_time"]

            # Simulate uptime over horizon
            current_time = 0
            uptime = 0
            downtime = 0
            failures = 0

            while current_time < horizon_hours:
                # Machine runs until failure or PM (whichever first)
                next_failure = current_time + ttf
                next_pm = ((current_time // planned_maintenance_interval) + 1) * planned_maintenance_interval

                if next_failure < next_pm and next_failure < horizon_hours:
                    # Unplanned failure
                    uptime += next_failure - current_time
                    downtime += repair
                    current_time = next_failure + repair
                    failures += 1
                elif next_pm < horizon_hours:
                    # Planned maintenance
                    uptime += next_pm - current_time
                    pm_duration = 2.0  # Fixed PM duration
                    downtime += pm_duration
                    current_time = next_pm + pm_duration
                else:
                    # End of horizon
                    uptime += horizon_hours - current_time
                    current_time = horizon_hours

            availability = uptime / (uptime + downtime) if (uptime + downtime) > 0 else 1.0

            return {
                "availability": availability,
                "uptime_hours": uptime,
                "downtime_hours": downtime,
                "failures": failures,
                "mtbf_actual": uptime / failures if failures > 0 else horizon_hours,
            }

        self.set_model(reliability_model)
        return self.run(iterations=iterations, name="machine_reliability")

    def cost_estimation(
        self,
        material_cost_distribution: Distribution,
        labor_hours_distribution: Distribution,
        labor_rate: float = 50.0,
        overhead_rate: float = 1.5,
        iterations: int = 5000,
    ) -> MonteCarloResult:
        """
        Monte Carlo cost estimation with uncertainty.

        Args:
            material_cost_distribution: Material cost distribution
            labor_hours_distribution: Labor hours distribution
            labor_rate: Hourly labor rate
            overhead_rate: Overhead multiplier
            iterations: Number of iterations

        Returns:
            MonteCarloResult with cost distribution
        """
        self.add_variables([
            SimulationVariable(
                name="material_cost",
                distribution=material_cost_distribution,
                min_value=0,
            ),
            SimulationVariable(
                name="labor_hours",
                distribution=labor_hours_distribution,
                min_value=0,
            ),
        ])

        def cost_model(inputs: Dict[str, float]) -> Dict[str, float]:
            material = inputs["material_cost"]
            hours = inputs["labor_hours"]

            labor_cost = hours * labor_rate
            overhead = (material + labor_cost) * (overhead_rate - 1)
            total_cost = material + labor_cost + overhead

            return {
                "material_cost": material,
                "labor_cost": labor_cost,
                "overhead": overhead,
                "total_cost": total_cost,
            }

        self.set_model(cost_model)
        return self.run(iterations=iterations, name="cost_estimation")

    @staticmethod
    def _phi(x: float) -> float:
        """Standard normal CDF approximation."""
        # Approximation of the standard normal CDF
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x) / math.sqrt(2)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

        return 0.5 * (1.0 + sign * y)

    def reset(self) -> None:
        """Reset simulation state."""
        self._variables.clear()
        self._model = None


# Convenience functions

def run_capacity_simulation(
    demand_mean: float,
    demand_std: float,
    capacity: float,
    lead_time_mean: float,
    lead_time_std: float,
    iterations: int = 5000,
) -> Dict[str, Any]:
    """Quick capacity planning simulation."""
    engine = MonteCarloEngine()

    result = engine.capacity_planning(
        demand_distribution=Distribution(
            DistributionType.NORMAL,
            {"mean": demand_mean, "std": demand_std}
        ),
        capacity=capacity,
        lead_time_distribution=Distribution(
            DistributionType.NORMAL,
            {"mean": lead_time_mean, "std": lead_time_std}
        ),
        iterations=iterations,
    )

    return result.to_dict()


def run_quality_simulation(
    cpk: float = 1.33,
    inspection_rate: float = 0.95,
    iterations: int = 5000,
) -> Dict[str, Any]:
    """Quick quality yield simulation."""
    engine = MonteCarloEngine()

    result = engine.quality_yield_simulation(
        process_cpk=cpk,
        inspection_effectiveness=inspection_rate,
        iterations=iterations,
    )

    return result.to_dict()


def run_reliability_simulation(
    mtbf: float = 500,
    mttr: float = 4,
    horizon_days: int = 30,
    iterations: int = 5000,
) -> Dict[str, Any]:
    """Quick machine reliability simulation."""
    engine = MonteCarloEngine()

    result = engine.machine_reliability(
        mtbf_hours=mtbf,
        mttr_hours=mttr,
        horizon_hours=horizon_days * 24,
        iterations=iterations,
    )

    return result.to_dict()
