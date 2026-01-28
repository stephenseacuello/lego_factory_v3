# LegoMCP Core Module
from .brick_modeler import BrickModeler, BrickResult
from .cam_processor import CAMProcessor
from .generative_bridge import (
    GenerativeBridge,
    get_bridge,
    OptimizedGeometry,
    DesignSpace,
    LoadCase,
    Constraint,
    MaterialSpec,
    SimulationResult,
    GeometryFormat,
    OptimizationType,
)

__all__ = [
    'BrickModeler',
    'BrickResult',
    'CAMProcessor',
    'GenerativeBridge',
    'get_bridge',
    'OptimizedGeometry',
    'DesignSpace',
    'LoadCase',
    'Constraint',
    'MaterialSpec',
    'SimulationResult',
    'GeometryFormat',
    'OptimizationType',
]
