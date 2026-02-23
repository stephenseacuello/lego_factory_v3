"""
Formal Verification Pipeline
============================

LEGO MCP DoD/ONR-Class Manufacturing System v8.0

Comprehensive verification infrastructure for safety-critical
manufacturing software (IEC 61508 SIL 2+).

Features:
- Static analysis integration (Clang, Cppcheck, Coverity)
- Property-based testing with Hypothesis
- Model checking (TLA+, SPIN/Promela)
- Contract programming (Design by Contract)
- MISRA C++ 2023 compliance
- Fuzz testing
- Runtime monitors from specifications

V8.0 Features:
- TLA+ model checker wrapper for CI integration
- SPIN/Promela verification support
- Runtime monitor generation from TLA+ invariants
- Safety property verification (IEC 61508)
- Liveness property verification

Reference: DO-178C, IEC 61508, MISRA C++:2023, TLA+ Specification Language
"""

from .static_analysis import StaticAnalyzer, AnalysisResult, Severity
from .property_testing import PropertyTester, invariant, precondition, postcondition
from .model_checker import ModelChecker, StateModel, TemporalProperty
from .contracts import Contract, ContractViolation, requires, ensures

# V8 Enhanced Model Checking
try:
    from .model_checker import (
        TLAModelChecker,
        SPINModelChecker,
        ModelCheckResult,
        SafetyProperty,
        LivenessProperty,
        InvariantViolation,
        CounterExample,
        StateSpace,
        run_tlc,
        run_spin,
    )
except ImportError:
    TLAModelChecker = None
    SPINModelChecker = None
    ModelCheckResult = None
    SafetyProperty = None
    LivenessProperty = None
    InvariantViolation = None
    CounterExample = None
    StateSpace = None
    run_tlc = None
    run_spin = None

# V8 Runtime Monitors
try:
    from .runtime_monitors import (
        RuntimeMonitor,
        MonitorResult,
        SafetyMonitor,
        TimingMonitor,
        InvariantMonitor,
        generate_monitor_from_tla,
    )
except ImportError:
    RuntimeMonitor = None
    MonitorResult = None
    SafetyMonitor = None
    TimingMonitor = None
    InvariantMonitor = None
    generate_monitor_from_tla = None

__all__ = [
    # Static Analysis
    "StaticAnalyzer",
    "AnalysisResult",
    "Severity",
    # Property Testing
    "PropertyTester",
    "invariant",
    "precondition",
    "postcondition",
    # Model Checking Core
    "ModelChecker",
    "StateModel",
    "TemporalProperty",
    # Contracts
    "Contract",
    "ContractViolation",
    "requires",
    "ensures",
    # V8 Enhanced Model Checking
    "TLAModelChecker",
    "SPINModelChecker",
    "ModelCheckResult",
    "SafetyProperty",
    "LivenessProperty",
    "InvariantViolation",
    "CounterExample",
    "StateSpace",
    "run_tlc",
    "run_spin",
    # V8 Runtime Monitors
    "RuntimeMonitor",
    "MonitorResult",
    "SafetyMonitor",
    "TimingMonitor",
    "InvariantMonitor",
    "generate_monitor_from_tla",
]

__version__ = "8.0.0"
