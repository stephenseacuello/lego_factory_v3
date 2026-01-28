"""
LEGO Factory v3 - Stochastic Models for Simulation
====================================================
Random event models for breakdowns, quality defects, material shortages, etc.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


# Default parameters if config file not found
DEFAULT_MACHINE_PARAMS = {
    'bambu-ps1': {'mtbf_hours': 120, 'mttr_hours': 1.0, 'defect_rate': 0.01, 'setup_cv': 0.10, 'process_cv': 0.08},
    'bambu-ps2': {'mtbf_hours': 120, 'mttr_hours': 1.0, 'defect_rate': 0.01, 'setup_cv': 0.10, 'process_cv': 0.08},
    'prusa-mk4-1': {'mtbf_hours': 100, 'mttr_hours': 1.5, 'defect_rate': 0.015, 'setup_cv': 0.12, 'process_cv': 0.10},
    'prusa-mk4-2': {'mtbf_hours': 100, 'mttr_hours': 1.5, 'defect_rate': 0.015, 'setup_cv': 0.12, 'process_cv': 0.10},
    'formlabs-3l': {'mtbf_hours': 80, 'mttr_hours': 2.0, 'defect_rate': 0.02, 'setup_cv': 0.15, 'process_cv': 0.12},
    'bantam-explorer': {'mtbf_hours': 80, 'mttr_hours': 2.0, 'defect_rate': 0.02, 'setup_cv': 0.15, 'process_cv': 0.12},
    'nomad-883': {'mtbf_hours': 90, 'mttr_hours': 1.5, 'defect_rate': 0.018, 'setup_cv': 0.12, 'process_cv': 0.10},
    'k40-laser': {'mtbf_hours': 150, 'mttr_hours': 0.5, 'defect_rate': 0.008, 'setup_cv': 0.08, 'process_cv': 0.06},
    'emblaser-2': {'mtbf_hours': 160, 'mttr_hours': 0.5, 'defect_rate': 0.007, 'setup_cv': 0.08, 'process_cv': 0.06},
    'assembly-1': {'mtbf_hours': 500, 'mttr_hours': 0.25, 'defect_rate': 0.005, 'setup_cv': 0.05, 'process_cv': 0.05},
    'inspection-1': {'mtbf_hours': 1000, 'mttr_hours': 0.25, 'defect_rate': 0.002, 'setup_cv': 0.05, 'process_cv': 0.05},
}

DEFAULT_GLOBAL_PARAMS = {
    'material_shortage_probability': 0.03,
    'shortage_delay_hours': [1, 4],
}


def load_simulation_params() -> Dict[str, Any]:
    """Load simulation parameters from config file."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'simulation_params.json'

    try:
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load simulation params: {e}")

    return {
        'machines': DEFAULT_MACHINE_PARAMS,
        'global': DEFAULT_GLOBAL_PARAMS,
    }


@dataclass
class MachineParams:
    """Parameters for machine-specific stochastic models."""
    mtbf_hours: float = 100.0
    mttr_hours: float = 1.0
    defect_rate: float = 0.01
    setup_cv: float = 0.10
    process_cv: float = 0.10
    weibull_shape: float = 2.0  # Shape parameter for Weibull


class BreakdownModel:
    """
    Model for machine breakdowns.

    Uses Weibull distribution for time-to-failure and
    lognormal for repair duration.
    """

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng()
        self.params = load_simulation_params()

    def get_machine_params(self, machine_id: str) -> MachineParams:
        """Get parameters for specific machine."""
        machine_params = self.params.get('machines', {}).get(machine_id, {})
        return MachineParams(
            mtbf_hours=machine_params.get('mtbf_hours', 100.0),
            mttr_hours=machine_params.get('mttr_hours', 1.0),
            defect_rate=machine_params.get('defect_rate', 0.01),
            setup_cv=machine_params.get('setup_cv', 0.10),
            process_cv=machine_params.get('process_cv', 0.10),
        )

    def time_to_failure(self, params: Optional[MachineParams] = None) -> float:
        """
        Generate time to next failure in hours.

        Uses Weibull distribution: shape controls wear-out pattern.
        Shape > 1: increasing failure rate (wear-out)
        Shape = 1: constant failure rate (random failures)
        Shape < 1: decreasing failure rate (infant mortality)
        """
        params = params or MachineParams()

        # Weibull scale from MTBF
        # For Weibull, mean = scale * gamma(1 + 1/shape)
        from scipy.special import gamma as gamma_func
        scale = params.mtbf_hours / gamma_func(1 + 1/params.weibull_shape)

        return self.rng.weibull(params.weibull_shape) * scale

    def repair_duration(self, params: Optional[MachineParams] = None) -> float:
        """
        Generate repair duration in hours.

        Uses lognormal distribution - repairs can occasionally take much longer.
        """
        params = params or MachineParams()

        # Lognormal parameters from MTTR
        # Mean of lognormal = exp(mu + sigma^2/2)
        sigma = 0.5  # Moderate variability
        mu = np.log(params.mttr_hours) - (sigma**2 / 2)

        return self.rng.lognormal(mu, sigma)


class QualityModel:
    """
    Model for quality defects.

    Uses Bernoulli trials for defect occurrence.
    """

    DEFECT_TYPES = {
        'dimensional': 0.4,      # Out of tolerance
        'surface': 0.3,          # Surface defects
        'structural': 0.15,      # Internal defects
        'cosmetic': 0.15,        # Visual imperfections
    }

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng()
        self.params = load_simulation_params()

    def get_machine_params(self, machine_id: str) -> MachineParams:
        """Get parameters for specific machine."""
        machine_params = self.params.get('machines', {}).get(machine_id, {})
        return MachineParams(
            defect_rate=machine_params.get('defect_rate', 0.01),
        )

    def check_quality(self, params: Optional[MachineParams] = None) -> bool:
        """
        Check if quality defect occurs.

        Returns True if defect occurred.
        """
        params = params or MachineParams()
        return self.rng.random() < params.defect_rate

    def get_defect_type(self) -> str:
        """Get type of defect when one occurs."""
        types = list(self.DEFECT_TYPES.keys())
        weights = list(self.DEFECT_TYPES.values())
        return self.rng.choice(types, p=weights)

    def generate_defect(self, params: Optional[MachineParams] = None) -> Optional[Dict[str, Any]]:
        """
        Generate a defect if one occurs.

        Returns defect info dict or None.
        """
        if self.check_quality(params):
            return {
                'type': self.get_defect_type(),
                'severity': self.rng.choice(['minor', 'major', 'critical'], p=[0.6, 0.3, 0.1]),
            }
        return None


class MaterialShortageModel:
    """
    Model for material shortages.

    Uses Bernoulli trials for shortage occurrence.
    """

    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng()
        self.params = load_simulation_params()

        global_params = self.params.get('global', DEFAULT_GLOBAL_PARAMS)
        self.probability = global_params.get('material_shortage_probability', 0.03)
        self.delay_range = global_params.get('shortage_delay_hours', [1, 4])

    def check_shortage(self) -> bool:
        """Check if material shortage occurs."""
        return self.rng.random() < self.probability

    def delay(self) -> float:
        """Generate delay duration in hours when shortage occurs."""
        return self.rng.uniform(self.delay_range[0], self.delay_range[1])


class SetupVariabilityModel:
    """
    Model for setup time variability.

    Adds random variation to nominal setup times.
    """

    def __init__(self, cv: float = 0.15, rng: Optional[np.random.Generator] = None):
        self.default_cv = cv
        self.rng = rng or np.random.default_rng()
        self.params = load_simulation_params()

    def get_cv(self, machine_id: Optional[str] = None) -> float:
        """Get coefficient of variation for machine."""
        if machine_id:
            machine_params = self.params.get('machines', {}).get(machine_id, {})
            return machine_params.get('setup_cv', self.default_cv)
        return self.default_cv

    def actual_setup(self, nominal: float, machine_id: Optional[str] = None) -> float:
        """
        Generate actual setup time from nominal.

        Uses normal distribution truncated at 50% of nominal.
        """
        cv = self.get_cv(machine_id)
        sigma = nominal * cv

        actual = self.rng.normal(nominal, sigma)
        return max(nominal * 0.5, actual)  # At least 50% of nominal


class ProcessTimeModel:
    """
    Model for process time variability.

    Adds random variation to nominal processing times.
    """

    def __init__(self, cv: float = 0.10, rng: Optional[np.random.Generator] = None):
        self.default_cv = cv
        self.rng = rng or np.random.default_rng()
        self.params = load_simulation_params()

    def get_cv(self, machine_id: Optional[str] = None) -> float:
        """Get coefficient of variation for machine."""
        if machine_id:
            machine_params = self.params.get('machines', {}).get(machine_id, {})
            return machine_params.get('process_cv', self.default_cv)
        return self.default_cv

    def actual_time(self, nominal: float, machine_id: Optional[str] = None) -> float:
        """
        Generate actual processing time from nominal.

        Uses normal distribution truncated at 50% of nominal.
        """
        cv = self.get_cv(machine_id)
        sigma = nominal * cv

        actual = self.rng.normal(nominal, sigma)
        return max(nominal * 0.5, actual)


class ArrivalModel:
    """
    Model for job arrivals (for dynamic scenarios).

    Uses exponential distribution for inter-arrival times.
    """

    def __init__(self, mean_interarrival_hours: float = 1.0, rng: Optional[np.random.Generator] = None):
        self.mean_interarrival = mean_interarrival_hours
        self.rng = rng or np.random.default_rng()

    def time_to_next_arrival(self) -> float:
        """Generate time to next job arrival in hours."""
        return self.rng.exponential(self.mean_interarrival)

    def generate_arrivals(self, duration_hours: float) -> list:
        """Generate arrival times over a duration."""
        arrivals = []
        current_time = 0.0

        while current_time < duration_hours:
            inter_arrival = self.time_to_next_arrival()
            current_time += inter_arrival
            if current_time < duration_hours:
                arrivals.append(current_time)

        return arrivals
