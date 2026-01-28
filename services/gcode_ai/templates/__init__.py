"""
G-code Templates for common machining operations.

Provides pre-built, parameterized G-code templates for:
- Drilling: spot drill, drill, peck drill, tapping
- Pocketing: rectangular, circular, adaptive
- Profiling: 2D contour, 2.5D, with tabs
"""

from .drilling import DrillingTemplates
from .pocketing import PocketingTemplates
from .profiling import ProfilingTemplates

__all__ = [
    "DrillingTemplates",
    "PocketingTemplates",
    "ProfilingTemplates",
]
