"""
PINN Training Components

Physics-constrained training infrastructure.
"""

from .physics_loss import PhysicsLossFunction
from .hybrid_trainer import HybridTrainer

__all__ = [
    "PhysicsLossFunction",
    "HybridTrainer",
]
