"""
Quantum-Inspired Scheduling for Manufacturing.

This module provides quantum-inspired optimization algorithms:
- QAOA (Quantum Approximate Optimization Algorithm)
- VQE (Variational Quantum Eigensolver)
- Simulated Quantum Annealing

Research Value:
- Novel quantum-classical hybrid for manufacturing
- Combinatorial optimization for job-shop scheduling
- Scalable near-term quantum algorithms

References:
- Farhi, E., et al. (2014). A Quantum Approximate Optimization Algorithm
- Peruzzo, A., et al. (2014). A variational eigenvalue solver on a photonic quantum processor
"""

from .qaoa_scheduler import (
    QAOAScheduler,
    QAOAConfig,
    QubitEncoding,
    MixerHamiltonian,
    ProblemHamiltonian,
)
from .vqe_scheduler import (
    VQEScheduler,
    VQEConfig,
    Ansatz,
    ParameterizedCircuit,
    ClassicalOptimizer,
)
from .simulated_quantum import (
    SimulatedQuantumAnnealer,
    AnnealingSchedule,
    QuantumState,
    HamiltonianSimulator,
)

__all__ = [
    # QAOA
    'QAOAScheduler',
    'QAOAConfig',
    'QubitEncoding',
    'MixerHamiltonian',
    'ProblemHamiltonian',
    # VQE
    'VQEScheduler',
    'VQEConfig',
    'Ansatz',
    'ParameterizedCircuit',
    'ClassicalOptimizer',
    # Simulated Quantum
    'SimulatedQuantumAnnealer',
    'AnnealingSchedule',
    'QuantumState',
    'HamiltonianSimulator',
]
