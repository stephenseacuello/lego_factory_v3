"""
Active Learning - Efficient human-in-the-loop labeling.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 4: Closed-Loop Learning
"""

from .query_strategy import QueryStrategy, UncertaintySampling, DiversitySampling
from .oracle_interface import OracleInterface, LabelRequest, LabelResponse
from .sample_selector import SampleSelector, SelectionResult

__all__ = [
    'QueryStrategy',
    'UncertaintySampling',
    'DiversitySampling',
    'OracleInterface',
    'LabelRequest',
    'LabelResponse',
    'SampleSelector',
    'SelectionResult',
]
