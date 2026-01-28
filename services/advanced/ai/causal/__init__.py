"""
Causal Inference Module
=======================

LegoMCP PhD-Level Manufacturing Platform
Part of the Advanced AI/ML Operations (Phase 8.2)

This module provides comprehensive causal analysis capabilities for
manufacturing processes, enabling:

1. **Root Cause Analysis**: Identify true causes of defects and failures
2. **Process Optimization**: Understand which parameters actually matter
3. **What-If Analysis**: Predict outcomes of process changes
4. **Treatment Effect Estimation**: Measure impact of interventions

Key Concepts:
-------------
- **Causal Discovery**: Learn causal structure from observational data
- **Treatment Effects**: Estimate causal impact of interventions
- **Counterfactuals**: "What would have happened if...?"
- **Root Cause Analysis**: Trace problems back to their origins

Why Causal Inference for Manufacturing?
---------------------------------------
Correlation is not causation. Traditional ML finds patterns but can't
distinguish:
- "Temperature correlates with defects" (maybe both caused by humidity)
- "Temperature causes defects" (actionable insight)

Causal inference answers questions like:
- "If we increase pressure by 10%, what happens to yield?"
- "Why did this batch fail?"
- "Which process change would have the biggest impact?"

Components:
-----------
1. **CausalDiscovery**: Learn causal graphs from data
   - PC Algorithm (constraint-based)
   - NOTEARS (continuous optimization)
   - LiNGAM (linear non-Gaussian)

2. **TreatmentEffectEstimator**: Estimate intervention effects
   - IPW (Inverse Propensity Weighting)
   - DML (Double Machine Learning)
   - Meta-learners (S, T, X)
   - Causal Forest

3. **CounterfactualEngine**: What-if analysis
   - Counterfactual generation
   - Scenario comparison
   - Sensitivity analysis

4. **RootCauseAnalyzer**: Manufacturing RCA
   - 6M framework (Man, Machine, Material, Method, Measurement, Environment)
   - Granger causality
   - Transfer entropy

Example Usage:
--------------
    from services.ai.causal import (
        CausalDiscovery,
        TreatmentEffectEstimator,
        RootCauseAnalyzer,
    )

    # Discover causal structure
    discovery = CausalDiscovery()
    graph = discovery.discover(process_data, variable_names)

    # Estimate treatment effect
    estimator = TreatmentEffectEstimator()
    effect = estimator.estimate_manufacturing_effect(
        outcome=defect_rate,
        treatment=temperature_setting,
        process_params=other_params,
        treatment_name="high_temperature",
    )

    # Analyze root cause
    analyzer = RootCauseAnalyzer()
    causes = analyzer.analyze_manufacturing_defect(
        process_data=sensor_data,
        defect_indicator=defects,
        defect_type="surface_crack",
        feature_names=sensor_names,
    )

References:
-----------
- Pearl, J. (2009). Causality: Models, Reasoning, and Inference
- Peters, J. et al. (2017). Elements of Causal Inference
- Spirtes, P. et al. (2000). Causation, Prediction, and Search

Author: LegoMCP Team
Version: 2.0.0
"""

# Causal Structure Discovery
from .causal_discovery import (
    CausalDiscovery,
    CausalGraph,
    CausalEdge,
    DiscoveryAlgorithm,
    CausalDiscoveryBase,
    PCAlgorithm,
    NOTEARSAlgorithm,
    LiNGAMAlgorithm,
    causal_discovery,  # Global instance
)

# Treatment Effect Estimation
from .treatment_effects import (
    TreatmentEffectEstimator,
    TreatmentResult,
    TreatmentMethod,
)

# Counterfactual Analysis
from .counterfactual_engine import (
    CounterfactualEngine,
    CounterfactualResult,
    CounterfactualMethod,
    ScenarioResult,
)

# Root Cause Analysis
from .root_cause_analyzer import (
    RootCauseAnalyzer,
    RootCauseResult,
    RCAMethod,
    CauseCandidate,
)

__all__ = [
    # Causal Discovery
    "CausalDiscovery",
    "CausalGraph",
    "CausalEdge",
    "DiscoveryAlgorithm",
    "CausalDiscoveryBase",
    "PCAlgorithm",
    "NOTEARSAlgorithm",
    "LiNGAMAlgorithm",
    "causal_discovery",

    # Treatment Effects
    "TreatmentEffectEstimator",
    "TreatmentResult",
    "TreatmentMethod",

    # Counterfactuals
    "CounterfactualEngine",
    "CounterfactualResult",
    "CounterfactualMethod",
    "ScenarioResult",

    # Root Cause Analysis
    "RootCauseAnalyzer",
    "RootCauseResult",
    "RCAMethod",
    "CauseCandidate",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
