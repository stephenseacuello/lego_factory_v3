"""
Formal Verification Framework for Manufacturing Systems

Implements formal methods for safety-critical manufacturing:
- TLA+ specifications for distributed protocols
- SPIN/Promela for safety property verification
- Runtime monitoring with temporal logic
- Model checking integration

Reference: ISO 26262, DO-178C, IEC 61508
"""

from .property_spec import (
    LTLFormula,
    CTLFormula,
    SafetyProperty,
    LivenessProperty,
    PropertyType,
)

from .trace_analyzer import (
    TraceEvent,
    TraceAnalyzer,
    Verdict,
)

from .spec_generator import (
    PromelaGenerator,
    TLAGenerator,
    SpecificationContext,
)

__all__ = [
    'LTLFormula',
    'CTLFormula',
    'SafetyProperty',
    'LivenessProperty',
    'PropertyType',
    'TraceEvent',
    'TraceAnalyzer',
    'Verdict',
    'PromelaGenerator',
    'TLAGenerator',
    'SpecificationContext',
]

__version__ = "1.0.0"
