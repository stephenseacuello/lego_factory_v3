"""
VQE-based Scheduler for Manufacturing Optimization.

This module implements the Variational Quantum Eigensolver (VQE)
for manufacturing scheduling problems:
- Ground state optimization
- Parameterized quantum circuits
- Hybrid quantum-classical optimization

Research Value:
- Alternative variational approach to scheduling
- Comparison with QAOA
- Hardware-efficient ansatz design

References:
- Peruzzo, A., et al. (2014). A variational eigenvalue solver
- Kandala, A., et al. (2017). Hardware-efficient variational quantum eigensolver
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Dict, List, Optional, Set, Any, TypeVar, Generic,
    Callable, Tuple, Union
)
import numpy as np
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# Parameterized Quantum Circuits
# =============================================================================

class GateType(Enum):
    """Types of quantum gates."""
    RX = auto()  # X rotation
    RY = auto()  # Y rotation
    RZ = auto()  # Z rotation
    CX = auto()  # CNOT
    CZ = auto()  # Controlled-Z
    H = auto()  # Hadamard
    SWAP = auto()  # SWAP


@dataclass
class QuantumGate:
    """Represents a quantum gate in a circuit."""
    gate_type: GateType
    qubits: Tuple[int, ...]  # Qubit indices
    parameter: Optional[float] = None  # For parameterized gates
    param_index: Optional[int] = None  # Index in parameter vector


class ParameterizedCircuit:
    """
    Parameterized quantum circuit for VQE.

    Represents a variational ansatz with trainable parameters.
    """

    def __init__(self, n_qubits: int):
        self.n_qubits = n_qubits
        self.gates: List[QuantumGate] = []
        self.n_params = 0
        self._state: Optional[np.ndarray] = None

    def add_gate(
        self,
        gate_type: GateType,
        qubits: Tuple[int, ...],
        parametrized: bool = False
    ) -> None:
        """Add a gate to the circuit."""
        param_idx = None
        if parametrized:
            param_idx = self.n_params
            self.n_params += 1

        self.gates.append(QuantumGate(
            gate_type=gate_type,
            qubits=qubits,
            param_index=param_idx
        ))

    def apply(
        self,
        initial_state: np.ndarray,
        parameters: np.ndarray
    ) -> np.ndarray:
        """
        Apply the circuit to an initial state.

        Uses classical simulation of quantum operations.
        """
        state = initial_state.copy()

        for gate in self.gates:
            theta = 0.0
            if gate.param_index is not None:
                theta = parameters[gate.param_index]

            state = self._apply_gate(state, gate, theta)

        self._state = state
        return state

    def _apply_gate(
        self,
        state: np.ndarray,
        gate: QuantumGate,
        theta: float
    ) -> np.ndarray:
        """Apply a single gate to state."""
        # Simplified classical simulation
        # State is probability amplitudes in computational basis

        if gate.gate_type == GateType.RX:
            # X rotation: affects qubit flip probability
            q = gate.qubits[0]
            flip_prob = np.sin(theta / 2) ** 2
            if np.random.random() < flip_prob:
                state[q] = 1 - state[q]

        elif gate.gate_type == GateType.RY:
            q = gate.qubits[0]
            flip_prob = np.sin(theta / 2) ** 2
            if np.random.random() < flip_prob:
                state[q] = 1 - state[q]

        elif gate.gate_type == GateType.RZ:
            # Z rotation: phase only, doesn't change computational basis
            pass

        elif gate.gate_type == GateType.CX:
            # CNOT: flip target if control is 1
            control, target = gate.qubits
            if state[control] > 0.5:
                state[target] = 1 - state[target]

        elif gate.gate_type == GateType.H:
            # Hadamard: random flip
            q = gate.qubits[0]
            state[q] = np.random.randint(0, 2)

        return state

    def get_gradient(
        self,
        initial_state: np.ndarray,
        parameters: np.ndarray,
        cost_fn: Callable[[np.ndarray], float],
        epsilon: float = 0.01
    ) -> np.ndarray:
        """
        Compute gradient using parameter-shift rule.

        ∂E/∂θ = (E(θ + π/2) - E(θ - π/2)) / 2
        """
        gradient = np.zeros(self.n_params)

        for i in range(self.n_params):
            # Shift up
            params_plus = parameters.copy()
            params_plus[i] += np.pi / 2
            state_plus = self.apply(initial_state.copy(), params_plus)
            cost_plus = cost_fn(state_plus)

            # Shift down
            params_minus = parameters.copy()
            params_minus[i] -= np.pi / 2
            state_minus = self.apply(initial_state.copy(), params_minus)
            cost_minus = cost_fn(state_minus)

            gradient[i] = (cost_plus - cost_minus) / 2

        return gradient


# =============================================================================
# Ansatz Types
# =============================================================================

class AnsatzType(Enum):
    """Types of variational ansatze."""
    HARDWARE_EFFICIENT = auto()
    QAOA_INSPIRED = auto()
    UCCSD = auto()  # Unitary Coupled Cluster
    CUSTOM = auto()


class Ansatz:
    """
    Builds parameterized circuits for VQE.

    Implements various ansatz designs:
    - Hardware-efficient: Layer of rotations + entangling
    - QAOA-inspired: Problem-specific structure
    """

    @staticmethod
    def hardware_efficient(
        n_qubits: int,
        n_layers: int = 2,
        entanglement: str = 'linear'
    ) -> ParameterizedCircuit:
        """
        Build hardware-efficient ansatz.

        Each layer: RY(θ) - RZ(θ) on each qubit + entangling layer
        """
        circuit = ParameterizedCircuit(n_qubits)

        for layer in range(n_layers):
            # Single-qubit rotations
            for q in range(n_qubits):
                circuit.add_gate(GateType.RY, (q,), parametrized=True)
                circuit.add_gate(GateType.RZ, (q,), parametrized=True)

            # Entangling layer
            if entanglement == 'linear':
                for q in range(n_qubits - 1):
                    circuit.add_gate(GateType.CX, (q, q + 1))
            elif entanglement == 'full':
                for q1 in range(n_qubits):
                    for q2 in range(q1 + 1, n_qubits):
                        circuit.add_gate(GateType.CZ, (q1, q2))

        # Final rotation layer
        for q in range(n_qubits):
            circuit.add_gate(GateType.RY, (q,), parametrized=True)

        return circuit

    @staticmethod
    def qaoa_inspired(
        n_qubits: int,
        n_layers: int = 2
    ) -> ParameterizedCircuit:
        """
        Build QAOA-inspired ansatz.

        Alternates between problem-inspired rotations and mixing.
        """
        circuit = ParameterizedCircuit(n_qubits)

        # Initial superposition
        for q in range(n_qubits):
            circuit.add_gate(GateType.H, (q,))

        for layer in range(n_layers):
            # Problem layer (ZZ interactions)
            for q in range(n_qubits - 1):
                circuit.add_gate(GateType.CZ, (q, q + 1))
                circuit.add_gate(GateType.RZ, (q,), parametrized=True)

            # Mixer layer
            for q in range(n_qubits):
                circuit.add_gate(GateType.RX, (q,), parametrized=True)

        return circuit


# =============================================================================
# Classical Optimizers
# =============================================================================

class OptimizerType(Enum):
    """Types of classical optimizers."""
    GRADIENT_DESCENT = auto()
    ADAM = auto()
    SPSA = auto()  # Simultaneous Perturbation
    COBYLA = auto()
    POWELL = auto()


@dataclass
class OptimizerConfig:
    """Configuration for classical optimizer."""
    optimizer_type: OptimizerType = OptimizerType.ADAM
    learning_rate: float = 0.1
    max_iterations: int = 100
    tolerance: float = 1e-6
    beta1: float = 0.9  # For Adam
    beta2: float = 0.999  # For Adam


class ClassicalOptimizer:
    """
    Classical optimizer for VQE parameters.

    Implements gradient-based and gradient-free optimization.
    """

    def __init__(self, config: OptimizerConfig):
        self.config = config

        # Adam state
        self.m = None  # First moment
        self.v = None  # Second moment
        self.t = 0  # Time step

    def step(
        self,
        parameters: np.ndarray,
        gradient: Optional[np.ndarray] = None,
        cost_fn: Optional[Callable[[np.ndarray], float]] = None
    ) -> np.ndarray:
        """Single optimization step."""
        if self.config.optimizer_type == OptimizerType.GRADIENT_DESCENT:
            return self._gradient_descent_step(parameters, gradient)

        elif self.config.optimizer_type == OptimizerType.ADAM:
            return self._adam_step(parameters, gradient)

        elif self.config.optimizer_type == OptimizerType.SPSA:
            return self._spsa_step(parameters, cost_fn)

        return parameters

    def _gradient_descent_step(
        self,
        parameters: np.ndarray,
        gradient: np.ndarray
    ) -> np.ndarray:
        """Standard gradient descent."""
        return parameters - self.config.learning_rate * gradient

    def _adam_step(
        self,
        parameters: np.ndarray,
        gradient: np.ndarray
    ) -> np.ndarray:
        """Adam optimizer step."""
        if self.m is None:
            self.m = np.zeros_like(parameters)
            self.v = np.zeros_like(parameters)

        self.t += 1

        # Update biased first moment
        self.m = self.config.beta1 * self.m + (1 - self.config.beta1) * gradient

        # Update biased second moment
        self.v = self.config.beta2 * self.v + (1 - self.config.beta2) * (gradient ** 2)

        # Bias correction
        m_hat = self.m / (1 - self.config.beta1 ** self.t)
        v_hat = self.v / (1 - self.config.beta2 ** self.t)

        # Update parameters
        return parameters - self.config.learning_rate * m_hat / (np.sqrt(v_hat) + 1e-8)

    def _spsa_step(
        self,
        parameters: np.ndarray,
        cost_fn: Callable[[np.ndarray], float]
    ) -> np.ndarray:
        """SPSA (gradient-free) step."""
        delta = np.random.choice([-1, 1], size=len(parameters))
        c = 0.1  # Perturbation size

        # Estimate gradient
        cost_plus = cost_fn(parameters + c * delta)
        cost_minus = cost_fn(parameters - c * delta)

        gradient_estimate = (cost_plus - cost_minus) / (2 * c * delta)

        return parameters - self.config.learning_rate * gradient_estimate

    def reset(self) -> None:
        """Reset optimizer state."""
        self.m = None
        self.v = None
        self.t = 0


# =============================================================================
# VQE Scheduler
# =============================================================================

@dataclass
class VQEConfig:
    """Configuration for VQE scheduler."""
    n_layers: int = 3
    ansatz_type: AnsatzType = AnsatzType.HARDWARE_EFFICIENT
    optimizer_config: OptimizerConfig = field(
        default_factory=lambda: OptimizerConfig()
    )
    n_shots: int = 1000  # Measurement shots
    gradient_method: str = 'parameter_shift'


class VQEScheduler:
    """
    VQE-based scheduler for manufacturing optimization.

    Uses variational quantum eigensolver to find minimum-cost
    schedule.

    Research Value:
    - Comparison with QAOA approach
    - Ansatz optimization for scheduling
    - Noise-resilient variational methods
    """

    def __init__(
        self,
        config: VQEConfig,
        n_jobs: int,
        n_machines: int,
        n_time_slots: int,
        processing_times: Optional[np.ndarray] = None
    ):
        self.config = config
        self.n_jobs = n_jobs
        self.n_machines = n_machines
        self.n_time_slots = n_time_slots

        # Default processing times
        if processing_times is None:
            processing_times = np.ones((n_jobs, n_machines))
        self.processing_times = processing_times

        # Build encoding (same as QAOA)
        from .qaoa_scheduler import QubitEncoding, ProblemHamiltonian
        self.encoding = QubitEncoding(n_jobs, n_machines, n_time_slots)
        self.hamiltonian = ProblemHamiltonian(self.encoding, processing_times)

        # Build ansatz
        self.circuit = self._build_ansatz()

        # Optimizer
        self.optimizer = ClassicalOptimizer(config.optimizer_config)

        # Training history
        self.history: List[Dict[str, float]] = []

    def _build_ansatz(self) -> ParameterizedCircuit:
        """Build the variational ansatz."""
        n_qubits = self.encoding.n_qubits

        if self.config.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
            return Ansatz.hardware_efficient(n_qubits, self.config.n_layers)
        elif self.config.ansatz_type == AnsatzType.QAOA_INSPIRED:
            return Ansatz.qaoa_inspired(n_qubits, self.config.n_layers)
        else:
            return Ansatz.hardware_efficient(n_qubits, self.config.n_layers)

    def optimize(
        self,
        initial_params: Optional[np.ndarray] = None
    ) -> Tuple[Dict[int, Tuple[int, int]], float]:
        """
        Run VQE optimization.

        Returns:
            Tuple of (best_schedule, best_energy)
        """
        n_params = self.circuit.n_params

        # Initialize parameters
        if initial_params is None:
            initial_params = np.random.uniform(-np.pi, np.pi, n_params)

        params = initial_params.copy()
        best_params = params.copy()
        best_energy = float('inf')

        # Initial state (computational basis |0...0>)
        initial_state = np.zeros(self.encoding.n_qubits)

        # Optimization loop
        for iteration in range(self.config.optimizer_config.max_iterations):
            # Compute cost (expectation value)
            energy, final_state = self._compute_expectation(initial_state, params)

            # Track best
            if energy < best_energy:
                best_energy = energy
                best_params = params.copy()

            self.history.append({
                'iteration': iteration,
                'energy': energy
            })

            # Compute gradient
            if self.config.gradient_method == 'parameter_shift':
                gradient = self.circuit.get_gradient(
                    initial_state,
                    params,
                    lambda s: self.hamiltonian.evaluate(s)
                )
            else:
                # Finite difference
                gradient = self._finite_difference_gradient(
                    initial_state, params
                )

            # Update parameters
            params = self.optimizer.step(params, gradient)

            # Convergence check
            if np.linalg.norm(gradient) < self.config.optimizer_config.tolerance:
                logger.info(f"VQE converged at iteration {iteration}")
                break

        # Get final solution
        best_state = self.circuit.apply(initial_state.copy(), best_params)
        best_schedule = self.encoding.decode_solution(best_state)

        return best_schedule, best_energy

    def _compute_expectation(
        self,
        initial_state: np.ndarray,
        params: np.ndarray
    ) -> Tuple[float, np.ndarray]:
        """
        Compute expectation value <ψ|H|ψ>.

        Uses multiple shots for estimation.
        """
        total_energy = 0.0
        final_state = None

        for _ in range(self.config.n_shots):
            state = self.circuit.apply(initial_state.copy(), params)
            energy = self.hamiltonian.evaluate(state)
            total_energy += energy
            final_state = state

        return total_energy / self.config.n_shots, final_state

    def _finite_difference_gradient(
        self,
        initial_state: np.ndarray,
        params: np.ndarray,
        epsilon: float = 0.01
    ) -> np.ndarray:
        """Compute gradient using finite differences."""
        gradient = np.zeros(len(params))
        base_energy, _ = self._compute_expectation(initial_state, params)

        for i in range(len(params)):
            params_plus = params.copy()
            params_plus[i] += epsilon
            energy_plus, _ = self._compute_expectation(initial_state, params_plus)
            gradient[i] = (energy_plus - base_energy) / epsilon

        return gradient

    def get_schedule_quality(
        self,
        schedule: Dict[int, Tuple[int, int]]
    ) -> Dict[str, float]:
        """Evaluate quality metrics of a schedule."""
        if not schedule:
            return {'makespan': float('inf'), 'utilization': 0.0}

        completion_times = []
        for job_id, (machine_id, start_time) in schedule.items():
            proc_time = self.processing_times[job_id, machine_id] if job_id < len(self.processing_times) else 1
            completion_times.append(start_time + proc_time)

        makespan = max(completion_times) if completion_times else 0

        machine_busy = defaultdict(float)
        for job_id, (machine_id, start_time) in schedule.items():
            proc_time = self.processing_times[job_id, machine_id] if job_id < len(self.processing_times) else 1
            machine_busy[machine_id] += proc_time

        total_available = self.n_machines * makespan if makespan > 0 else 1
        total_busy = sum(machine_busy.values())
        utilization = total_busy / total_available

        return {
            'makespan': float(makespan),
            'utilization': float(utilization),
            'n_scheduled': len(schedule),
            'n_jobs': self.n_jobs
        }

    def analyze_convergence(self) -> Dict[str, Any]:
        """Analyze optimization convergence."""
        if not self.history:
            return {}

        energies = [h['energy'] for h in self.history]

        return {
            'initial_energy': energies[0],
            'final_energy': energies[-1],
            'improvement': (energies[0] - energies[-1]) / abs(energies[0]) if energies[0] != 0 else 0,
            'iterations': len(self.history),
            'converged': len(self.history) < self.config.optimizer_config.max_iterations
        }


# Export public API
__all__ = [
    'VQEConfig',
    'VQEScheduler',
    'Ansatz',
    'AnsatzType',
    'ParameterizedCircuit',
    'GateType',
    'QuantumGate',
    'ClassicalOptimizer',
    'OptimizerType',
    'OptimizerConfig',
]
