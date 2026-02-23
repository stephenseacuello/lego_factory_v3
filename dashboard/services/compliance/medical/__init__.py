"""
Medical Device Compliance Module (ISO 13485)

PhD-Level Research Implementation:
- Design Control per FDA 21 CFR 820
- Risk Management per ISO 14971
- UDI Traceability per FDA GUDID

Novel Contributions:
- AI-assisted design verification
- Automated risk assessment with ML
- Real-time traceability dashboards

Standards Compliance:
- ISO 13485 (Medical Device QMS)
- ISO 14971 (Risk Management)
- FDA 21 CFR Part 820
- IEC 62304 (Software Lifecycle)
- EU MDR 2017/745
"""

from .design_control import (
    DesignControlManager,
    DesignPhase,
    DesignInput,
    DesignOutput,
    DesignReview,
    DesignVerification,
    DesignValidation,
    DesignTransfer,
    DesignHistoryFile
)
from .risk_management import (
    RiskManager,
    Hazard,
    HazardousSituation,
    Harm,
    RiskAssessment,
    RiskControl,
    RiskLevel,
    RiskMatrix
)
from .traceability import (
    TraceabilityManager,
    UDI,
    ProductionUnit,
    TraceabilityRecord,
    RecallScope
)

__all__ = [
    'DesignControlManager',
    'DesignPhase',
    'DesignInput',
    'DesignOutput',
    'DesignReview',
    'DesignVerification',
    'DesignValidation',
    'DesignTransfer',
    'DesignHistoryFile',
    'RiskManager',
    'Hazard',
    'HazardousSituation',
    'Harm',
    'RiskAssessment',
    'RiskControl',
    'RiskLevel',
    'RiskMatrix',
    'TraceabilityManager',
    'UDI',
    'ProductionUnit',
    'TraceabilityRecord',
    'RecallScope'
]
