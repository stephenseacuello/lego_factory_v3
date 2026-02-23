"""
QFD Engine - Quality Function Deployment / House of Quality.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Flow: HOQ → Specifications → Digital Twin Design → Validation
"""

from .hoq_engine import HouseOfQualityEngine, HouseOfQuality
from .voice_of_customer import VoiceOfCustomerAnalyzer, CustomerRequirement
from .qfd_cascade import QFDCascade
from .technical_requirements import TechnicalRequirementsManager, TechnicalRequirement
from .relationship_matrix import RelationshipMatrix, RelationshipStrength, Relationship
from .correlation_matrix import CorrelationMatrix, CorrelationType, Correlation
from .competitive_analysis import CompetitiveAnalyzer, Competitor, CompetitiveGap
from .target_setter import TargetSetter, TargetRecommendation, TargetSet, TargetStrategy

# Digital Twin Bridge - HOQ to DT Design & Validation
from .hoq_digital_twin_bridge import (
    HOQDigitalTwinBridge,
    DigitalTwinDesignPackage,
    DigitalTwinDesignSpec,
    ValidationCriterion,
    DigitalTwinTestCase,
    ValidationSeverity,
    DesignParameterType,
    TestCaseType,
    get_hoq_digital_twin_bridge,
)

__all__ = [
    # Core HOQ/QFD
    'HouseOfQualityEngine',
    'HouseOfQuality',
    'VoiceOfCustomerAnalyzer',
    'CustomerRequirement',
    'QFDCascade',
    'TechnicalRequirementsManager',
    'TechnicalRequirement',
    'RelationshipMatrix',
    'RelationshipStrength',
    'Relationship',
    'CorrelationMatrix',
    'CorrelationType',
    'Correlation',
    'CompetitiveAnalyzer',
    'Competitor',
    'CompetitiveGap',
    'TargetSetter',
    'TargetRecommendation',
    'TargetSet',
    'TargetStrategy',
    # Digital Twin Bridge
    'HOQDigitalTwinBridge',
    'DigitalTwinDesignPackage',
    'DigitalTwinDesignSpec',
    'ValidationCriterion',
    'DigitalTwinTestCase',
    'ValidationSeverity',
    'DesignParameterType',
    'TestCaseType',
    'get_hoq_digital_twin_bridge',
]
