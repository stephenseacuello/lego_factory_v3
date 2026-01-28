"""
Explainability Engine - XAI for manufacturing AI decisions.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability
"""

from .shap_explainer import SHAPExplainer
from .lime_explainer import LIMEExplainer
from .attention_viz import AttentionVisualizer
from .explanation_generator import ExplanationGenerator
from .concept_activation import (
    ConceptActivationTester,
    Concept,
    ConceptType,
    ConceptActivationVector,
    TCAVScore,
)

__all__ = [
    'SHAPExplainer',
    'LIMEExplainer',
    'AttentionVisualizer',
    'ExplanationGenerator',
    # TCAV
    'ConceptActivationTester',
    'Concept',
    'ConceptType',
    'ConceptActivationVector',
    'TCAVScore',
]
