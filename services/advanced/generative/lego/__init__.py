"""
LEGO-Specific Generative Design - Optimize LEGO brick designs.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 3: Generative Design System
"""

from .clutch_optimizer import ClutchOptimizer
from .fdm_compensator import FDMCompensator
from .multi_brick_generator import MultiBrickGenerator, BrickAssembly, GeneratedDesign
from .compatibility_validator import CompatibilityValidator, ValidationResult, CompatibilityLevel

__all__ = [
    'ClutchOptimizer',
    'FDMCompensator',
    'MultiBrickGenerator',
    'BrickAssembly',
    'GeneratedDesign',
    'CompatibilityValidator',
    'ValidationResult',
    'CompatibilityLevel',
]
