"""
Property-Based Testing Framework

Implements property-based testing for manufacturing system
verification following QuickCheck/Hypothesis patterns.

Reference: QuickCheck, Hypothesis, DO-178C MC/DC
"""

import logging
import random
import functools
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, Type, TypeVar, Union
from datetime import datetime
from enum import Enum
import traceback
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class TestResult(Enum):
    """Property test result."""
    PASSED = "passed"
    FAILED = "failed"
    GAVE_UP = "gave_up"      # Too many invalid inputs
    ERROR = "error"          # Exception during test


@dataclass
class Shrink:
    """Shrunk counterexample."""
    original: Any
    shrunk: Any
    shrink_steps: int


@dataclass
class PropertyResult:
    """Result of property testing."""
    name: str
    result: TestResult
    iterations: int = 0
    counterexample: Optional[Any] = None
    shrunk_counterexample: Optional[Shrink] = None
    exception: Optional[str] = None
    seed: Optional[int] = None
    duration_ms: float = 0.0
    coverage: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "result": self.result.value,
            "iterations": self.iterations,
            "counterexample": str(self.counterexample) if self.counterexample else None,
            "exception": self.exception,
            "seed": self.seed,
            "duration_ms": self.duration_ms
        }


#==============================================================================
# Generators
#==============================================================================

class Generator(Generic[T]):
    """Base class for value generators."""

    def generate(self, size: int, rng: random.Random) -> T:
        """Generate a value of the given size."""
        raise NotImplementedError

    def shrink(self, value: T) -> List[T]:
        """Generate smaller values for shrinking."""
        return []


class IntGenerator(Generator[int]):
    """Generate integers."""

    def __init__(self, min_val: int = -1000000, max_val: int = 1000000):
        self.min_val = min_val
        self.max_val = max_val

    def generate(self, size: int, rng: random.Random) -> int:
        # Scale range by size
        scaled_min = max(self.min_val, -size * 100)
        scaled_max = min(self.max_val, size * 100)
        return rng.randint(scaled_min, scaled_max)

    def shrink(self, value: int) -> List[int]:
        if value == 0:
            return []
        shrinks = [0]
        if value > 0:
            shrinks.extend([value // 2, value - 1])
        else:
            shrinks.extend([value // 2, value + 1])
        return [s for s in shrinks if s != value]


class FloatGenerator(Generator[float]):
    """Generate floats."""

    def __init__(self, min_val: float = -1e6, max_val: float = 1e6):
        self.min_val = min_val
        self.max_val = max_val

    def generate(self, size: int, rng: random.Random) -> float:
        scaled_min = max(self.min_val, -size * 100.0)
        scaled_max = min(self.max_val, size * 100.0)
        return rng.uniform(scaled_min, scaled_max)

    def shrink(self, value: float) -> List[float]:
        if value == 0.0:
            return []
        shrinks = [0.0, int(value), value / 2]
        return [s for s in shrinks if s != value]


class StringGenerator(Generator[str]):
    """Generate strings."""

    def __init__(
        self,
        min_len: int = 0,
        max_len: int = 100,
        alphabet: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ):
        self.min_len = min_len
        self.max_len = max_len
        self.alphabet = alphabet

    def generate(self, size: int, rng: random.Random) -> str:
        length = rng.randint(self.min_len, min(self.max_len, size + 1))
        return ''.join(rng.choices(self.alphabet, k=length))

    def shrink(self, value: str) -> List[str]:
        if len(value) == 0:
            return []
        shrinks = [
            "",
            value[:len(value) // 2],
            value[1:],
            value[:-1]
        ]
        return [s for s in shrinks if s != value and len(s) >= self.min_len]


class ListGenerator(Generator[List[T]]):
    """Generate lists."""

    def __init__(
        self,
        element_gen: Generator[T],
        min_len: int = 0,
        max_len: int = 100
    ):
        self.element_gen = element_gen
        self.min_len = min_len
        self.max_len = max_len

    def generate(self, size: int, rng: random.Random) -> List[T]:
        length = rng.randint(self.min_len, min(self.max_len, size + 1))
        return [self.element_gen.generate(size, rng) for _ in range(length)]

    def shrink(self, value: List[T]) -> List[List[T]]:
        if len(value) <= self.min_len:
            return []
        shrinks = [
            value[:len(value) // 2],
            value[1:],
            value[:-1]
        ]
        # Also try shrinking individual elements
        for i, elem in enumerate(value):
            for shrunk_elem in self.element_gen.shrink(elem):
                shrinks.append(value[:i] + [shrunk_elem] + value[i+1:])
        return [s for s in shrinks if len(s) >= self.min_len]


class DictGenerator(Generator[Dict[str, T]]):
    """Generate dictionaries."""

    def __init__(
        self,
        key_gen: Generator[str],
        value_gen: Generator[T],
        min_len: int = 0,
        max_len: int = 20
    ):
        self.key_gen = key_gen
        self.value_gen = value_gen
        self.min_len = min_len
        self.max_len = max_len

    def generate(self, size: int, rng: random.Random) -> Dict[str, T]:
        length = rng.randint(self.min_len, min(self.max_len, size + 1))
        return {
            self.key_gen.generate(size, rng): self.value_gen.generate(size, rng)
            for _ in range(length)
        }


class OneOfGenerator(Generator[T]):
    """Generate from one of multiple generators."""

    def __init__(self, generators: List[Generator[T]]):
        self.generators = generators

    def generate(self, size: int, rng: random.Random) -> T:
        gen = rng.choice(self.generators)
        return gen.generate(size, rng)


class ConstantGenerator(Generator[T]):
    """Generate a constant value."""

    def __init__(self, value: T):
        self.value = value

    def generate(self, size: int, rng: random.Random) -> T:
        return self.value


#==============================================================================
# Manufacturing-Specific Generators
#==============================================================================

@dataclass
class BrickSpec:
    """LEGO brick specification."""
    studs_x: int
    studs_y: int
    height_plates: int
    color: str


class BrickSpecGenerator(Generator[BrickSpec]):
    """Generate valid LEGO brick specifications."""

    VALID_STUDS = [1, 2, 3, 4, 6, 8, 10, 12, 16]
    VALID_HEIGHTS = [1, 2, 3]  # In plate units
    VALID_COLORS = ["RED", "BLUE", "GREEN", "YELLOW", "BLACK", "WHITE"]

    def generate(self, size: int, rng: random.Random) -> BrickSpec:
        return BrickSpec(
            studs_x=rng.choice(self.VALID_STUDS),
            studs_y=rng.choice(self.VALID_STUDS),
            height_plates=rng.choice(self.VALID_HEIGHTS),
            color=rng.choice(self.VALID_COLORS)
        )

    def shrink(self, value: BrickSpec) -> List[BrickSpec]:
        shrinks = []
        # Try smaller dimensions
        if value.studs_x > 1:
            shrinks.append(BrickSpec(1, value.studs_y, value.height_plates, value.color))
        if value.studs_y > 1:
            shrinks.append(BrickSpec(value.studs_x, 1, value.height_plates, value.color))
        if value.height_plates > 1:
            shrinks.append(BrickSpec(value.studs_x, value.studs_y, 1, value.color))
        return shrinks


@dataclass
class TemperatureReading:
    """Temperature sensor reading."""
    value: float
    sensor_id: str
    zone: str


class TemperatureGenerator(Generator[TemperatureReading]):
    """Generate temperature readings."""

    ZONES = ["extruder", "bed", "chamber", "ambient"]

    def __init__(self, min_temp: float = 15.0, max_temp: float = 300.0):
        self.min_temp = min_temp
        self.max_temp = max_temp

    def generate(self, size: int, rng: random.Random) -> TemperatureReading:
        zone = rng.choice(self.ZONES)
        # Zone-specific ranges
        if zone == "extruder":
            temp = rng.uniform(180.0, 260.0)
        elif zone == "bed":
            temp = rng.uniform(40.0, 110.0)
        elif zone == "chamber":
            temp = rng.uniform(30.0, 70.0)
        else:
            temp = rng.uniform(15.0, 35.0)

        return TemperatureReading(
            value=temp,
            sensor_id=f"TEMP-{rng.randint(1, 10):03d}",
            zone=zone
        )


#==============================================================================
# Property Decorators
#==============================================================================

def invariant(condition: Callable[..., bool]):
    """
    Decorator to mark a class invariant.

    The condition is checked after every method call.
    """
    def decorator(cls):
        original_init = cls.__init__

        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if not condition(self):
                raise AssertionError(f"Invariant violated after __init__: {condition.__doc__ or condition.__name__}")

        cls.__init__ = new_init

        # Wrap all methods
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if not name.startswith('_'):
                setattr(cls, name, _wrap_with_invariant(method, condition))

        return cls
    return decorator


def _wrap_with_invariant(method, condition):
    """Wrap method to check invariant after execution."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        if not condition(self):
            raise AssertionError(
                f"Invariant violated after {method.__name__}: "
                f"{condition.__doc__ or condition.__name__}"
            )
        return result
    return wrapper


def precondition(condition: Callable[..., bool]):
    """
    Decorator to specify a function precondition.

    Usage:
        @precondition(lambda x: x > 0)
        def sqrt(x):
            return x ** 0.5
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not condition(*args, **kwargs):
                raise AssertionError(
                    f"Precondition failed for {func.__name__}: "
                    f"{condition.__doc__ or 'condition not met'}"
                )
            return func(*args, **kwargs)
        wrapper._precondition = condition
        return wrapper
    return decorator


def postcondition(condition: Callable[[Any], bool]):
    """
    Decorator to specify a function postcondition.

    Usage:
        @postcondition(lambda result: result >= 0)
        def abs_value(x):
            return abs(x)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not condition(result):
                raise AssertionError(
                    f"Postcondition failed for {func.__name__}: "
                    f"{condition.__doc__ or 'condition not met'}"
                )
            return result
        wrapper._postcondition = condition
        return wrapper
    return decorator


#==============================================================================
# Property Tester
#==============================================================================

class PropertyTester:
    """
    Property-based testing engine.

    Generates random inputs and tests properties,
    automatically shrinking counterexamples.

    Usage:
        >>> tester = PropertyTester()
        >>> @tester.property
        ... def test_sort_preserves_length(xs: List[int]) -> bool:
        ...     return len(sorted(xs)) == len(xs)
        >>> results = tester.run_all()
    """

    def __init__(
        self,
        max_examples: int = 100,
        max_shrinks: int = 500,
        seed: Optional[int] = None,
        verbosity: int = 1
    ):
        """
        Initialize property tester.

        Args:
            max_examples: Maximum number of examples to generate
            max_shrinks: Maximum shrinking attempts
            seed: Random seed for reproducibility
            verbosity: Output verbosity (0=silent, 1=normal, 2=verbose)
        """
        self.max_examples = max_examples
        self.max_shrinks = max_shrinks
        self.seed = seed or random.randint(0, 2**32)
        self.verbosity = verbosity
        self.rng = random.Random(self.seed)
        self.properties: List[Tuple[str, Callable, Dict[str, Generator]]] = []

        # Type to generator mapping
        self.type_generators: Dict[type, Generator] = {
            int: IntGenerator(),
            float: FloatGenerator(),
            str: StringGenerator(),
            bool: OneOfGenerator([ConstantGenerator(True), ConstantGenerator(False)]),
            BrickSpec: BrickSpecGenerator(),
            TemperatureReading: TemperatureGenerator()
        }

        logger.info(f"PropertyTester initialized: seed={self.seed}")

    def register_generator(self, type_: type, generator: Generator) -> None:
        """Register a generator for a type."""
        self.type_generators[type_] = generator

    def property(self, func: Callable[..., bool]) -> Callable[..., bool]:
        """
        Decorator to register a property.

        Usage:
            @tester.property
            def test_my_property(x: int, y: int) -> bool:
                return x + y == y + x
        """
        # Infer generators from type hints
        sig = inspect.signature(func)
        generators = {}

        for name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                type_hint = param.annotation

                # Handle List, Dict generics
                origin = getattr(type_hint, '__origin__', None)
                if origin is list:
                    args = getattr(type_hint, '__args__', (Any,))
                    elem_gen = self.type_generators.get(args[0], ConstantGenerator(None))
                    generators[name] = ListGenerator(elem_gen)
                elif origin is dict:
                    generators[name] = DictGenerator(
                        StringGenerator(), IntGenerator()
                    )
                else:
                    generators[name] = self.type_generators.get(
                        type_hint, ConstantGenerator(None)
                    )

        self.properties.append((func.__name__, func, generators))
        return func

    def check_property(
        self,
        func: Callable[..., bool],
        generators: Dict[str, Generator]
    ) -> PropertyResult:
        """Run property check."""
        import time
        start_time = time.time()

        for i in range(self.max_examples):
            # Generate inputs
            size = min(i + 1, 100)  # Grow size with iterations
            inputs = {
                name: gen.generate(size, self.rng)
                for name, gen in generators.items()
            }

            try:
                result = func(**inputs)
                if not result:
                    # Property failed - attempt shrinking
                    shrunk = self._shrink(func, generators, inputs)

                    return PropertyResult(
                        name=func.__name__,
                        result=TestResult.FAILED,
                        iterations=i + 1,
                        counterexample=inputs,
                        shrunk_counterexample=shrunk,
                        seed=self.seed,
                        duration_ms=(time.time() - start_time) * 1000
                    )

            except Exception as e:
                return PropertyResult(
                    name=func.__name__,
                    result=TestResult.ERROR,
                    iterations=i + 1,
                    counterexample=inputs,
                    exception=traceback.format_exc(),
                    seed=self.seed,
                    duration_ms=(time.time() - start_time) * 1000
                )

        return PropertyResult(
            name=func.__name__,
            result=TestResult.PASSED,
            iterations=self.max_examples,
            seed=self.seed,
            duration_ms=(time.time() - start_time) * 1000
        )

    def _shrink(
        self,
        func: Callable[..., bool],
        generators: Dict[str, Generator],
        failing_inputs: Dict[str, Any]
    ) -> Optional[Shrink]:
        """Attempt to shrink a counterexample."""
        current = failing_inputs.copy()
        shrink_steps = 0

        for _ in range(self.max_shrinks):
            improved = False

            for name, gen in generators.items():
                for shrunk_value in gen.shrink(current[name]):
                    test_inputs = current.copy()
                    test_inputs[name] = shrunk_value

                    try:
                        if not func(**test_inputs):
                            # Still failing - accept shrink
                            current = test_inputs
                            shrink_steps += 1
                            improved = True
                            break
                    except Exception:
                        # Exception counts as failure for shrinking
                        current = test_inputs
                        shrink_steps += 1
                        improved = True
                        break

                if improved:
                    break

            if not improved:
                break

        if shrink_steps > 0:
            return Shrink(
                original=failing_inputs,
                shrunk=current,
                shrink_steps=shrink_steps
            )
        return None

    def run_all(self) -> List[PropertyResult]:
        """Run all registered properties."""
        results = []
        for name, func, generators in self.properties:
            if self.verbosity >= 1:
                logger.info(f"Testing property: {name}")

            result = self.check_property(func, generators)
            results.append(result)

            if self.verbosity >= 1:
                status = "PASSED" if result.result == TestResult.PASSED else "FAILED"
                logger.info(f"  {status} ({result.iterations} examples)")

                if result.shrunk_counterexample:
                    logger.info(f"  Shrunk counterexample: {result.shrunk_counterexample.shrunk}")

        return results

    def run_property(self, name: str) -> Optional[PropertyResult]:
        """Run a specific property by name."""
        for prop_name, func, generators in self.properties:
            if prop_name == name:
                return self.check_property(func, generators)
        return None


# Factory functions for common generators
def integers(min_val: int = -1000000, max_val: int = 1000000) -> IntGenerator:
    """Create integer generator."""
    return IntGenerator(min_val, max_val)


def floats(min_val: float = -1e6, max_val: float = 1e6) -> FloatGenerator:
    """Create float generator."""
    return FloatGenerator(min_val, max_val)


def text(min_len: int = 0, max_len: int = 100, alphabet: Optional[str] = None) -> StringGenerator:
    """Create string generator."""
    return StringGenerator(min_len, max_len, alphabet or "abcdefghijklmnopqrstuvwxyz")


def lists(element_gen: Generator[T], min_len: int = 0, max_len: int = 100) -> ListGenerator[T]:
    """Create list generator."""
    return ListGenerator(element_gen, min_len, max_len)


def one_of(*generators: Generator[T]) -> OneOfGenerator[T]:
    """Create generator that picks from alternatives."""
    return OneOfGenerator(list(generators))


def constant(value: T) -> ConstantGenerator[T]:
    """Create constant generator."""
    return ConstantGenerator(value)
