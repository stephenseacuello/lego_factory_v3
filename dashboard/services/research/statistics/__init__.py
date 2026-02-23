"""
Statistical Testing - Hypothesis testing for manufacturing experiments.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Infrastructure
"""

from .hypothesis_testing import HypothesisTester, TestResult, TestType
from .power_analysis import PowerAnalyzer, SampleSizeResult
from .bayesian_testing import BayesianTester, BayesianResult
from .ab_testing import (
    ABTestAnalyzer,
    ABTestConfig,
    ABTestResult,
    TestType as ABTestType,
    MetricType,
    TestStatus,
    SequentialBoundary,
    calculate_sample_size,
    run_ab_test,
)
from .multi_arm_bandit import (
    MultiArmedBandit,
    ContextualBandit,
    BanditConfig,
    BanditResult,
    BanditAlgorithm,
    RewardType,
    Arm,
    EpsilonGreedy,
    UCB1,
    ThompsonSampling,
    EXP3,
    create_bandit,
    create_contextual_bandit,
)
from .causal_inference import (
    CausalInferenceEngine,
    CausalEstimate,
    CATEEstimate,
    EstimationMethod,
    TreatmentAssignment,
    PropensityScore,
    estimate_treatment_effect,
    difference_in_differences,
)

__all__ = [
    # Hypothesis Testing
    'HypothesisTester',
    'TestResult',
    'TestType',
    'PowerAnalyzer',
    'SampleSizeResult',
    'BayesianTester',
    'BayesianResult',
    # A/B Testing
    'ABTestAnalyzer',
    'ABTestConfig',
    'ABTestResult',
    'ABTestType',
    'MetricType',
    'TestStatus',
    'SequentialBoundary',
    'calculate_sample_size',
    'run_ab_test',
    # Multi-Armed Bandit
    'MultiArmedBandit',
    'ContextualBandit',
    'BanditConfig',
    'BanditResult',
    'BanditAlgorithm',
    'RewardType',
    'Arm',
    'EpsilonGreedy',
    'UCB1',
    'ThompsonSampling',
    'EXP3',
    'create_bandit',
    'create_contextual_bandit',
    # Causal Inference
    'CausalInferenceEngine',
    'CausalEstimate',
    'CATEEstimate',
    'EstimationMethod',
    'TreatmentAssignment',
    'PropensityScore',
    'estimate_treatment_effect',
    'difference_in_differences',
]
