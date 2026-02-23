"""
AI Services - Manufacturing Intelligence Layer
===============================================

LEGO MCP DoD/ONR-Class Manufacturing System v8.0
Trusted AI/ML with Safety Guardrails

Provides AI-powered intelligence for manufacturing operations:
- Claude-powered decision support with guardrails
- Causal discovery and root cause analysis
- Uncertainty quantification for risk-aware decisions
- Explainable AI (SHAP, LIME, counterfactuals)
- Physics-informed predictions
- Human-in-loop escalation

V8.0 Features:
- Causal Discovery: PC algorithm, Granger causality, DoWhy
- Uncertainty Quantification: MC Dropout, Deep Ensembles, Conformal
- Explainability: SHAP, LIME, counterfactuals, attention maps
- AI Guardrails: Input validation, output verification, hallucination detection
- AutoML: Optuna hyperparameter tuning
- Drift Detection: Data and concept drift monitoring

Reference Standards:
- IEC 61508 (Safety-related AI decisions)
- ISO/IEC 23053 (AI/ML in industrial systems)

Author: LEGO MCP AI Engineering
Version: 8.0.0
"""

from .manufacturing_copilot import (
    ManufacturingCopilot,
    CopilotConfig,
    CopilotResponse,
)

from .context_builder import (
    ContextBuilder,
    ProductionContext,
    ContextType,
)

from .decision_recommender import (
    DecisionRecommender,
    DecisionType,
    Decision,
    DecisionConfidence,
)

from .anomaly_explainer import (
    AnomalyExplainer,
    AnomalyExplanation,
    AnomalyType,
)

# V8 Causal Discovery
try:
    from .causal_discovery import (
        CausalDiscoveryEngine,
        CausalGraph,
        PCAlgorithm,
        GrangerCausality,
        DoWhyEstimator,
        CausalEffect,
        InterventionResult,
    )
except ImportError:
    CausalDiscoveryEngine = None
    CausalGraph = None
    PCAlgorithm = None
    GrangerCausality = None
    DoWhyEstimator = None
    CausalEffect = None
    InterventionResult = None

# V8 Uncertainty Quantification
try:
    from .uncertainty_quantification import (
        UncertaintyQuantifier,
        MCDropout,
        DeepEnsemble,
        ConformalPredictor,
        TemperatureScaling,
        UncertaintyResult,
        CalibrationMetrics,
    )
except ImportError:
    UncertaintyQuantifier = None
    MCDropout = None
    DeepEnsemble = None
    ConformalPredictor = None
    TemperatureScaling = None
    UncertaintyResult = None
    CalibrationMetrics = None

# V8 Explainability
try:
    from .explainability import (
        ExplainabilityEngine,
        SHAPExplainer,
        LIMEExplainer,
        CounterfactualExplainer,
        AttentionVisualizer,
        FeatureImportance,
        LocalExplanation,
        CounterfactualResult,
    )
except ImportError:
    ExplainabilityEngine = None
    SHAPExplainer = None
    LIMEExplainer = None
    CounterfactualExplainer = None
    AttentionVisualizer = None
    FeatureImportance = None
    LocalExplanation = None
    CounterfactualResult = None

# V8 AutoML
from .automl import (
    OptunaTuner,
    ObjectiveDirection,
    SamplerType,
    PrunerType,
    HyperparameterSpace,
    OptimizationResult,
)

# V8 Monitoring
from .monitoring import (
    DriftType,
    DriftSeverity,
    DriftMethod,
    DriftResult,
    StatisticalDriftDetector,
    StreamingDriftDetector,
    ModelDriftMonitor,
    get_or_create_monitor,
)

__all__ = [
    # Copilot
    'ManufacturingCopilot',
    'CopilotConfig',
    'CopilotResponse',

    # Context
    'ContextBuilder',
    'ProductionContext',
    'ContextType',

    # Decisions
    'DecisionRecommender',
    'DecisionType',
    'Decision',
    'DecisionConfidence',

    # Anomalies
    'AnomalyExplainer',
    'AnomalyExplanation',
    'AnomalyType',

    # V8 Causal Discovery
    'CausalDiscoveryEngine',
    'CausalGraph',
    'PCAlgorithm',
    'GrangerCausality',
    'DoWhyEstimator',
    'CausalEffect',
    'InterventionResult',

    # V8 Uncertainty Quantification
    'UncertaintyQuantifier',
    'MCDropout',
    'DeepEnsemble',
    'ConformalPredictor',
    'TemperatureScaling',
    'UncertaintyResult',
    'CalibrationMetrics',

    # V8 Explainability
    'ExplainabilityEngine',
    'SHAPExplainer',
    'LIMEExplainer',
    'CounterfactualExplainer',
    'AttentionVisualizer',
    'FeatureImportance',
    'LocalExplanation',
    'CounterfactualResult',

    # V8 AutoML
    'OptunaTuner',
    'ObjectiveDirection',
    'SamplerType',
    'PrunerType',
    'HyperparameterSpace',
    'OptimizationResult',

    # V8 Monitoring
    'DriftType',
    'DriftSeverity',
    'DriftMethod',
    'DriftResult',
    'StatisticalDriftDetector',
    'StreamingDriftDetector',
    'ModelDriftMonitor',
    'get_or_create_monitor',
]

__version__ = "8.0.0"
