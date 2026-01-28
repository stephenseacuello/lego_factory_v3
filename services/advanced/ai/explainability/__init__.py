"""
Explainable AI (XAI) Module
===========================

LegoMCP PhD-Level Manufacturing Platform
Part of the Research Foundation (Phase 1)

This module provides interpretable machine learning explanations for
manufacturing AI predictions. Explainability is critical for:

1. **Regulatory Compliance**: FDA, ISO 9001, ISO 13485 require traceable decisions
2. **Operator Trust**: Humans need to understand AI recommendations
3. **Debugging**: Identify model failures and biases
4. **Process Improvement**: Learn from AI insights to improve manufacturing

Why Explainability Matters in Manufacturing:
--------------------------------------------
- **Quality Decisions**: "Why did the model flag this part as defective?"
- **Process Control**: "Which parameters most influence yield?"
- **Root Cause Analysis**: "What caused this batch failure?"
- **Regulatory Audits**: "Show evidence for this quality classification"

Components:
-----------

1. **SHAPExplainer** (SHapley Additive exPlanations):
   - Game-theoretic approach to feature importance
   - Provides both global and local explanations
   - Handles any model type (model-agnostic)
   - Mathematically grounded (Shapley values)
   - Best for: Feature importance, model debugging

2. **LIMEExplainer** (Local Interpretable Model-agnostic Explanations):
   - Explains individual predictions locally
   - Creates simple surrogate models around predictions
   - Works with any black-box model
   - Human-readable explanations
   - Best for: Explaining specific decisions

3. **AttentionVisualizer**:
   - Visualizes attention in neural networks
   - GradCAM for CNN feature importance
   - Attention rollout for transformers
   - Feature map extraction
   - Best for: Vision models, defect detection

4. **CounterfactualExplainer**:
   - Answers "What would need to change for a different outcome?"
   - Minimal changes for classification flip
   - Actionable insights for process improvement
   - Best for: Understanding decision boundaries

Manufacturing-Specific Features:
--------------------------------
- **ManufacturingSHAP**: Explain quality predictions with process context
- **ManufacturingLIME**: Operator-friendly explanations
- **ManufacturingCounterfactual**: Process parameter recommendations

Example Usage:
--------------
    from services.ai.explainability import (
        SHAPExplainer,
        LIMEExplainer,
        AttentionVisualizer,
        CounterfactualExplainer,
    )

    # SHAP for global feature importance
    shap = SHAPExplainer(model, background_data=train_data)
    importance = shap.explain_global(test_data)
    shap.plot_summary()

    # LIME for individual prediction
    lime = LIMEExplainer(model, feature_names=sensor_names)
    explanation = lime.explain_instance(sample, num_features=10)
    print(explanation.as_text())

    # Attention visualization for defect detection
    viz = AttentionVisualizer(model)
    heatmap = viz.gradcam(image, target_class="crack")
    viz.overlay_on_image(image, heatmap)

    # Counterfactual for process improvement
    cf = CounterfactualExplainer(model, feature_ranges=param_ranges)
    changes = cf.generate(
        instance=current_params,
        desired_outcome="good_quality",
        max_changes=3,
    )
    print(f"To achieve good quality, change: {changes}")

Integration with Quality Systems:
---------------------------------
- Auto-generate explanation reports for QMS
- Log explanations for batch records
- Flag uncertain predictions for human review
- Provide evidence for regulatory submissions

References:
-----------
- Lundberg, S.M., & Lee, S.I. (2017). A Unified Approach to Interpreting
  Model Predictions. NeurIPS.
- Ribeiro, M.T. et al. (2016). "Why Should I Trust You?": Explaining the
  Predictions of Any Classifier. KDD.
- Selvaraju, R.R. et al. (2017). Grad-CAM: Visual Explanations from Deep
  Networks. ICCV.
- Wachter, S. et al. (2017). Counterfactual Explanations without Opening
  the Black Box. Harvard Journal of Law & Technology.

Author: LegoMCP Team
Version: 2.0.0
"""

# SHAP Explanations
from .shap_explainer import (
    SHAPExplainer,
    SHAPConfig,
    FeatureImportance,
    SHAPVisualization,
    ManufacturingSHAP,
)

# LIME Explanations
from .lime_explainer import (
    LIMEExplainer,
    LIMEConfig,
    LocalExplanation,
    LIMEVisualization,
    ManufacturingLIME,
)

# Attention Visualization
from .attention_viz import (
    AttentionVisualizer,
    GradCAM,
    AttentionRollout,
    FeatureMapExtractor,
    VisionExplainer,
)

# Counterfactual Explanations
from .counterfactual import (
    CounterfactualExplainer,
    CounterfactualConfig,
    WhatIfAnalysis,
    CausalExplainer,
    ManufacturingCounterfactual,
)

__all__ = [
    # SHAP
    "SHAPExplainer",
    "SHAPConfig",
    "FeatureImportance",
    "SHAPVisualization",
    "ManufacturingSHAP",

    # LIME
    "LIMEExplainer",
    "LIMEConfig",
    "LocalExplanation",
    "LIMEVisualization",
    "ManufacturingLIME",

    # Attention
    "AttentionVisualizer",
    "GradCAM",
    "AttentionRollout",
    "FeatureMapExtractor",
    "VisionExplainer",

    # Counterfactual
    "CounterfactualExplainer",
    "CounterfactualConfig",
    "WhatIfAnalysis",
    "CausalExplainer",
    "ManufacturingCounterfactual",
]

__version__ = "2.0.0"
__author__ = "LegoMCP Team"
