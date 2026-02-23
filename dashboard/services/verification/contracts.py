"""
Design by Contract Implementation

Implements contract programming for safety-critical
manufacturing software.

Reference: Eiffel DbC, DO-178C, IEC 61508
"""

import logging
import functools
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, get_type_hints
from datetime import datetime
from enum import Enum
import traceback
import threading

logger = logging.getLogger(__name__)

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class ContractMode(Enum):
    """Contract enforcement mode."""
    ENABLED = "enabled"        # Full enforcement
    DISABLED = "disabled"      # No checking
    LOGGING = "logging"        # Log violations but don't raise
    ASSERT = "assert"          # Use assertions (can be disabled)


class ViolationType(Enum):
    """Type of contract violation."""
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    INVARIANT = "invariant"
    TYPE = "type"


@dataclass
class ContractViolation(Exception):
    """Exception raised when a contract is violated."""
    violation_type: ViolationType
    contract_name: str
    message: str
    function_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    location: str = ""

    def __str__(self) -> str:
        return (
            f"{self.violation_type.value.upper()} VIOLATION in {self.function_name}: "
            f"{self.message}"
        )


@dataclass
class ContractStatistics:
    """Statistics about contract checks."""
    total_checks: int = 0
    precondition_checks: int = 0
    postcondition_checks: int = 0
    invariant_checks: int = 0
    violations: int = 0
    violations_by_type: Dict[ViolationType, int] = field(default_factory=dict)


class ContractConfig:
    """Global contract configuration."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.mode = ContractMode.ENABLED
        self.collect_statistics = True
        self.statistics = ContractStatistics()
        self.violation_handlers: List[Callable[[ContractViolation], None]] = []

    def set_mode(self, mode: ContractMode) -> None:
        """Set contract enforcement mode."""
        self.mode = mode
        logger.info(f"Contract mode set to: {mode.value}")

    def add_violation_handler(self, handler: Callable[[ContractViolation], None]) -> None:
        """Add a violation handler."""
        self.violation_handlers.append(handler)

    def record_check(self, violation_type: ViolationType) -> None:
        """Record a contract check."""
        if not self.collect_statistics:
            return
        self.statistics.total_checks += 1
        if violation_type == ViolationType.PRECONDITION:
            self.statistics.precondition_checks += 1
        elif violation_type == ViolationType.POSTCONDITION:
            self.statistics.postcondition_checks += 1
        elif violation_type == ViolationType.INVARIANT:
            self.statistics.invariant_checks += 1

    def record_violation(self, violation: ContractViolation) -> None:
        """Record a contract violation."""
        if not self.collect_statistics:
            return
        self.statistics.violations += 1
        vtype = violation.violation_type
        self.statistics.violations_by_type[vtype] = \
            self.statistics.violations_by_type.get(vtype, 0) + 1

        # Call handlers
        for handler in self.violation_handlers:
            try:
                handler(violation)
            except Exception as e:
                logger.error(f"Violation handler failed: {e}")


def get_config() -> ContractConfig:
    """Get global contract configuration."""
    return ContractConfig()


class Contract:
    """
    Contract specification for a function or method.

    Usage:
        >>> @Contract(
        ...     requires=lambda x: x > 0,
        ...     ensures=lambda result: result >= 0,
        ...     old_values=['x']
        ... )
        ... def sqrt(x: float) -> float:
        ...     return x ** 0.5
    """

    def __init__(
        self,
        requires: Optional[Union[Callable[..., bool], List[Callable[..., bool]]]] = None,
        ensures: Optional[Union[Callable[..., bool], List[Callable[..., bool]]]] = None,
        old_values: Optional[List[str]] = None,
        modifies: Optional[List[str]] = None
    ):
        """
        Initialize contract.

        Args:
            requires: Precondition(s) - checked before function execution
            ensures: Postcondition(s) - checked after function execution
            old_values: Parameters whose old values should be captured
            modifies: Parameters that the function may modify (frame condition)
        """
        self.requires = [requires] if callable(requires) else (requires or [])
        self.ensures = [ensures] if callable(ensures) else (ensures or [])
        self.old_values = old_values or []
        self.modifies = modifies or []

    def __call__(self, func: F) -> F:
        """Apply contract to function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            config = get_config()

            if config.mode == ContractMode.DISABLED:
                return func(*args, **kwargs)

            # Get function signature for parameter names
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            all_args = dict(bound_args.arguments)

            # Capture old values
            old = {}
            for name in self.old_values:
                if name in all_args:
                    # Deep copy for mutable objects
                    import copy
                    try:
                        old[name] = copy.deepcopy(all_args[name])
                    except Exception:
                        old[name] = all_args[name]

            # Check preconditions
            for i, pre in enumerate(self.requires):
                config.record_check(ViolationType.PRECONDITION)
                try:
                    if not self._check_condition(pre, all_args):
                        violation = ContractViolation(
                            violation_type=ViolationType.PRECONDITION,
                            contract_name=f"requires[{i}]",
                            message=self._get_condition_message(pre),
                            function_name=func.__name__,
                            arguments=all_args,
                            location=f"{func.__module__}.{func.__qualname__}"
                        )
                        self._handle_violation(violation, config)
                except Exception as e:
                    logger.warning(f"Precondition check failed with exception: {e}")

            # Execute function
            result = func(*args, **kwargs)

            # Check postconditions
            for i, post in enumerate(self.ensures):
                config.record_check(ViolationType.POSTCONDITION)
                try:
                    # Build context for postcondition
                    context = {
                        **all_args,
                        'result': result,
                        'old': old
                    }
                    if not self._check_condition(post, context, result):
                        violation = ContractViolation(
                            violation_type=ViolationType.POSTCONDITION,
                            contract_name=f"ensures[{i}]",
                            message=self._get_condition_message(post),
                            function_name=func.__name__,
                            arguments=all_args,
                            result=result,
                            location=f"{func.__module__}.{func.__qualname__}"
                        )
                        self._handle_violation(violation, config)
                except Exception as e:
                    logger.warning(f"Postcondition check failed with exception: {e}")

            return result

        # Attach contract info for introspection
        wrapper._contract = self
        return wrapper

    def _check_condition(
        self,
        condition: Callable,
        context: Dict[str, Any],
        result: Any = None
    ) -> bool:
        """Check a condition with given context."""
        sig = inspect.signature(condition)
        params = list(sig.parameters.keys())

        # Try to match parameters
        kwargs = {}
        for param in params:
            if param == 'result':
                kwargs[param] = result
            elif param in context:
                kwargs[param] = context[param]
            elif param == 'old':
                kwargs[param] = context.get('old', {})

        # If single parameter and no match, pass result
        if len(params) == 1 and not kwargs:
            return condition(result)

        try:
            return condition(**kwargs)
        except TypeError:
            # Fallback: try positional
            try:
                return condition(*context.values())
            except Exception:
                return condition(result)

    def _get_condition_message(self, condition: Callable) -> str:
        """Get descriptive message for condition."""
        if hasattr(condition, '__doc__') and condition.__doc__:
            return condition.__doc__.strip()
        if hasattr(condition, '__name__'):
            return f"Condition '{condition.__name__}' not satisfied"
        return "Contract condition not satisfied"

    def _handle_violation(
        self,
        violation: ContractViolation,
        config: ContractConfig
    ) -> None:
        """Handle a contract violation."""
        config.record_violation(violation)

        if config.mode == ContractMode.LOGGING:
            logger.error(str(violation))
        elif config.mode == ContractMode.ASSERT:
            assert False, str(violation)
        elif config.mode == ContractMode.ENABLED:
            raise violation


def requires(*conditions: Callable[..., bool]):
    """
    Decorator for specifying preconditions.

    Usage:
        @requires(lambda x: x > 0)
        def sqrt(x: float) -> float:
            return x ** 0.5
    """
    def decorator(func: F) -> F:
        return Contract(requires=list(conditions))(func)
    return decorator


def ensures(*conditions: Callable[..., bool]):
    """
    Decorator for specifying postconditions.

    Usage:
        @ensures(lambda result: result >= 0)
        def abs_value(x: float) -> float:
            return abs(x)
    """
    def decorator(func: F) -> F:
        return Contract(ensures=list(conditions))(func)
    return decorator


def contract(
    requires: Optional[List[Callable[..., bool]]] = None,
    ensures: Optional[List[Callable[..., bool]]] = None
):
    """
    Combined contract decorator.

    Usage:
        @contract(
            requires=[lambda x: x >= 0],
            ensures=[lambda result: result >= 0]
        )
        def sqrt(x: float) -> float:
            return x ** 0.5
    """
    return Contract(requires=requires, ensures=ensures)


class ClassContract:
    """
    Class-level contract with invariants.

    Usage:
        >>> @ClassContract(
        ...     invariants=[lambda self: self.balance >= 0]
        ... )
        ... class BankAccount:
        ...     def __init__(self, initial: float):
        ...         self.balance = initial
    """

    def __init__(
        self,
        invariants: Optional[List[Callable[[Any], bool]]] = None
    ):
        self.invariants = invariants or []

    def __call__(self, cls: Type[T]) -> Type[T]:
        """Apply invariant checking to class."""
        original_init = cls.__init__

        invariants = self.invariants

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self._check_invariants()

        def _check_invariants(self):
            config = get_config()
            if config.mode == ContractMode.DISABLED:
                return

            for i, inv in enumerate(invariants):
                config.record_check(ViolationType.INVARIANT)
                try:
                    if not inv(self):
                        violation = ContractViolation(
                            violation_type=ViolationType.INVARIANT,
                            contract_name=f"invariant[{i}]",
                            message=inv.__doc__ if inv.__doc__ else "Invariant violated",
                            function_name=cls.__name__,
                            location=f"{cls.__module__}.{cls.__qualname__}"
                        )
                        config.record_violation(violation)
                        if config.mode == ContractMode.ENABLED:
                            raise violation
                        elif config.mode == ContractMode.LOGGING:
                            logger.error(str(violation))
                except ContractViolation:
                    raise
                except Exception as e:
                    logger.warning(f"Invariant check failed with exception: {e}")

        cls.__init__ = new_init
        cls._check_invariants = _check_invariants

        # Wrap all public methods to check invariants after call
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not name.startswith('_') and name != '_check_invariants':
                setattr(cls, name, self._wrap_method(method))

        return cls

    def _wrap_method(self, method: Callable) -> Callable:
        """Wrap method to check invariants after execution."""
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            self._check_invariants()
            return result
        return wrapper


#==============================================================================
# Manufacturing-Specific Contracts
#==============================================================================

def positive(x: float) -> bool:
    """Value must be positive."""
    return x > 0


def non_negative(x: float) -> bool:
    """Value must be non-negative."""
    return x >= 0


def in_range(min_val: float, max_val: float):
    """Value must be in range [min, max]."""
    def check(x: float) -> bool:
        return min_val <= x <= max_val
    check.__doc__ = f"Value must be in range [{min_val}, {max_val}]"
    return check


def temperature_valid(temp: float) -> bool:
    """Temperature must be in valid range for manufacturing."""
    return -50.0 <= temp <= 500.0


def pressure_valid(pressure: float) -> bool:
    """Pressure must be in valid range."""
    return 0.0 <= pressure <= 100.0


def percentage(value: float) -> bool:
    """Value must be a valid percentage (0-100)."""
    return 0.0 <= value <= 100.0


def not_empty(collection) -> bool:
    """Collection must not be empty."""
    return len(collection) > 0


def valid_equipment_id(eq_id: str) -> bool:
    """Equipment ID must follow naming convention."""
    import re
    return bool(re.match(r'^[A-Z]+-\d{3,}$', eq_id))


def valid_job_id(job_id: str) -> bool:
    """Job ID must follow naming convention."""
    import re
    return bool(re.match(r'^JOB-\d{4,}$', job_id))


#==============================================================================
# Safety Contracts for Manufacturing
#==============================================================================

class SafetyContract:
    """
    Safety-critical contract with additional verification.

    For use in safety-critical code per IEC 61508.
    """

    def __init__(
        self,
        safety_level: int = 2,  # SIL level 1-4
        requires: Optional[List[Callable[..., bool]]] = None,
        ensures: Optional[List[Callable[..., bool]]] = None,
        timeout_ms: Optional[float] = None
    ):
        self.safety_level = safety_level
        self.requires = requires or []
        self.ensures = ensures or []
        self.timeout_ms = timeout_ms

    def __call__(self, func: F) -> F:
        """Apply safety contract to function."""
        base_contract = Contract(
            requires=self.requires,
            ensures=self.ensures
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            start = time.time()

            try:
                # Apply base contract
                result = base_contract(func)(*args, **kwargs)

                # Check timing constraint
                if self.timeout_ms:
                    elapsed_ms = (time.time() - start) * 1000
                    if elapsed_ms > self.timeout_ms:
                        logger.warning(
                            f"Safety-critical function {func.__name__} "
                            f"exceeded timeout: {elapsed_ms:.2f}ms > {self.timeout_ms}ms"
                        )

                return result

            except ContractViolation as cv:
                # Log safety-critical violation
                logger.critical(
                    f"SAFETY VIOLATION (SIL-{self.safety_level}) in {func.__name__}: "
                    f"{cv.message}"
                )
                raise

        wrapper._safety_contract = self
        wrapper._safety_level = self.safety_level
        return wrapper


def safety_critical(
    sil_level: int = 2,
    requires: Optional[List[Callable[..., bool]]] = None,
    ensures: Optional[List[Callable[..., bool]]] = None,
    timeout_ms: Optional[float] = None
):
    """
    Decorator for safety-critical functions.

    Usage:
        @safety_critical(sil_level=2, timeout_ms=100)
        def emergency_stop():
            # ...
    """
    return SafetyContract(
        safety_level=sil_level,
        requires=requires,
        ensures=ensures,
        timeout_ms=timeout_ms
    )
