"""
Generative Design System - AI-driven part optimization.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from .topology_optimizer import TopologyOptimizer, OptimizedGeometry
from .constraint_engine import ManufacturingConstraints, FDMConstraints
from .lattice_generator import LatticeGenerator, LatticeDesign, LatticeType
from .multi_physics import MultiPhysicsOptimizer, MultiPhysicsResult, PhysicsType
from .fitness import StrengthEvaluator, PrintabilityEvaluator, MaterialUsageEvaluator

__all__ = [
    'TopologyOptimizer',
    'OptimizedGeometry',
    'ManufacturingConstraints',
    'FDMConstraints',
    'LatticeGenerator',
    'LatticeDesign',
    'LatticeType',
    'MultiPhysicsOptimizer',
    'MultiPhysicsResult',
    'PhysicsType',
    'StrengthEvaluator',
    'PrintabilityEvaluator',
    'MaterialUsageEvaluator',
]
