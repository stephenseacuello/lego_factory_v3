"""
Life Cycle Assessment (LCA) Engine for Manufacturing.

This module implements ISO 14040/14044 compliant LCA:
- Cradle-to-grave environmental impact assessment
- Multiple impact categories (GWP, acidification, etc.)
- Ecoinvent database integration
- Multi-objective LCA optimization

Research Value:
- Novel LCA integration for additive manufacturing
- Real-time environmental impact tracking
- Sustainability-aware production planning

References:
- ISO 14040:2006 - Environmental management - Life cycle assessment - Principles and framework
- ISO 14044:2006 - Environmental management - Life cycle assessment - Requirements and guidelines
- Guinée, J.B. (2002). Handbook on Life Cycle Assessment
"""

from .lca_engine import (
    LCAEngine,
    LCAConfig,
    LifeCyclePhase,
    InventoryItem,
    ImpactResult,
    LCAResult,
    ManufacturingLCA,
)
from .impact_categories import (
    ImpactLevel,
    DamageCategory,
    CulturalPerspective,
    CharacterizationFactor,
    NormalizationFactor,
    WeightingFactor,
    ImpactCategory,
    ClimateChange,
    Acidification,
    Eutrophication,
    WaterUse,
    ResourceDepletion,
    HumanToxicity,
    Ecotoxicity,
    ParticulateMatter,
    ImpactProfile,
    ImpactCategoryManager,
    ManufacturingImpactAssessment,
)
from .lca_optimizer import (
    OptimizationObjective,
    DesignVariable,
    OptimizationConstraint,
    Solution,
    ParetoFront,
    LCAObjectiveFunction,
    ManufacturingLCAObjective,
    NSGA2Optimizer,
    LCAOptimizer,
)

__all__ = [
    # LCA Engine
    'LCAEngine',
    'LCAConfig',
    'LifeCyclePhase',
    'InventoryItem',
    'ImpactResult',
    'LCAResult',
    'ManufacturingLCA',
    # Impact Categories
    'ImpactLevel',
    'DamageCategory',
    'CulturalPerspective',
    'CharacterizationFactor',
    'NormalizationFactor',
    'WeightingFactor',
    'ImpactCategory',
    'ClimateChange',
    'Acidification',
    'Eutrophication',
    'WaterUse',
    'ResourceDepletion',
    'HumanToxicity',
    'Ecotoxicity',
    'ParticulateMatter',
    'ImpactProfile',
    'ImpactCategoryManager',
    'ManufacturingImpactAssessment',
    # Optimizer
    'OptimizationObjective',
    'DesignVariable',
    'OptimizationConstraint',
    'Solution',
    'ParetoFront',
    'LCAObjectiveFunction',
    'ManufacturingLCAObjective',
    'NSGA2Optimizer',
    'LCAOptimizer',
]
