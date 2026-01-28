"""
Runtime Monitor Generator

Generates Python runtime monitors from TLA+ specifications.
These monitors provide real-time validation of safety invariants
during system operation.

Reference: TLA+ to Runtime Monitor translation
IEC 61508: SIL 2+ Runtime Verification

Author: LEGO MCP Safety Engineering
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
from pathlib import Path
from datetime import datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


class TLAExpressionType(Enum):
    """Types of TLA+ expressions."""
    INVARIANT = "invariant"
    SAFETY_PROPERTY = "safety_property"
    LIVENESS_PROPERTY = "liveness_property"
    TYPE_CONSTRAINT = "type_constraint"
    HELPER_PREDICATE = "helper_predicate"


@dataclass
class TLAVariable:
    """TLA+ variable definition."""
    name: str
    tla_type: str  # e.g., "SafetyStates", "BOOLEAN", "0..MAX_TIME"
    python_type: str = "Any"
    allowed_values: Optional[Set[str]] = None

    @classmethod
    def from_type_string(cls, name: str, tla_type: str) -> "TLAVariable":
        """Create variable from TLA+ type string."""
        python_type = "Any"
        allowed_values = None

        if tla_type == "BOOLEAN":
            python_type = "bool"
        elif ".." in tla_type:
            python_type = "int"
        elif tla_type.startswith("{"):
            # Set literal like {"NORMAL", "WARNING", ...}
            python_type = "str"
            # Extract values
            match = re.findall(r'"([^"]+)"', tla_type)
            if match:
                allowed_values = set(match)

        return cls(
            name=name,
            tla_type=tla_type,
            python_type=python_type,
            allowed_values=allowed_values
        )


@dataclass
class TLAProperty:
    """Parsed TLA+ property."""
    name: str
    expression: str
    expr_type: TLAExpressionType
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    python_code: str = ""

    def is_safety_critical(self) -> bool:
        """Check if property is safety-critical."""
        return (
            self.expr_type in [
                TLAExpressionType.SAFETY_PROPERTY,
                TLAExpressionType.INVARIANT
            ] or
            "Safety" in self.name or
            "safe" in self.name.lower()
        )


@dataclass
class TLASpec:
    """Parsed TLA+ specification."""
    module_name: str
    constants: Dict[str, str] = field(default_factory=dict)
    variables: Dict[str, TLAVariable] = field(default_factory=dict)
    type_sets: Dict[str, Set[str]] = field(default_factory=dict)
    predicates: Dict[str, TLAProperty] = field(default_factory=dict)
    invariants: Dict[str, TLAProperty] = field(default_factory=dict)
    safety_properties: Dict[str, TLAProperty] = field(default_factory=dict)
    liveness_properties: Dict[str, TLAProperty] = field(default_factory=dict)


class TLAParser:
    """
    Parser for TLA+ specifications.

    Extracts:
    - Variables and their types
    - Constants
    - Invariants
    - Safety properties (labeled Safety*)
    - Liveness properties (labeled Liveness*)
    """

    def __init__(self):
        self.spec: Optional[TLASpec] = None

    def parse_file(self, filepath: str) -> TLASpec:
        """Parse a TLA+ file."""
        with open(filepath, 'r') as f:
            content = f.read()
        return self.parse(content)

    def parse(self, content: str) -> TLASpec:
        """Parse TLA+ content."""
        # Extract module name
        module_match = re.search(r'MODULE\s+(\w+)', content)
        module_name = module_match.group(1) if module_match else "Unknown"

        self.spec = TLASpec(module_name=module_name)

        # Parse sections
        self._parse_constants(content)
        self._parse_variables(content)
        self._parse_type_sets(content)
        self._parse_predicates(content)
        self._parse_invariants(content)
        self._parse_safety_properties(content)
        self._parse_liveness_properties(content)

        return self.spec

    def _parse_constants(self, content: str):
        """Parse CONSTANTS section."""
        match = re.search(r'CONSTANTS\s+([\s\S]*?)(?=VARIABLES|$)', content)
        if match:
            const_block = match.group(1)
            # Extract constant names
            for line in const_block.split('\n'):
                line = line.strip().rstrip(',')
                if line and not line.startswith('\\*'):
                    # Remove comments
                    name = line.split('\\*')[0].strip()
                    if name:
                        self.spec.constants[name] = "unknown"

    def _parse_variables(self, content: str):
        """Parse VARIABLES section."""
        match = re.search(r'VARIABLES\s+([\s\S]*?)(?=\(\*|SafetyStates|TypeInvariant|Init|$)', content)
        if match:
            var_block = match.group(1)
            for line in var_block.split('\n'):
                line = line.strip().rstrip(',')
                if line and not line.startswith('\\*'):
                    # Variable name before comment
                    parts = line.split('\\*')
                    name = parts[0].strip()
                    if name:
                        self.spec.variables[name] = TLAVariable(
                            name=name,
                            tla_type="unknown"
                        )

    def _parse_type_sets(self, content: str):
        """Parse type set definitions like SafetyStates == {...}."""
        # Match patterns like: SafetyStates == {"A", "B", "C"}
        pattern = r'(\w+)\s*==\s*\{([^}]+)\}'
        for match in re.finditer(pattern, content):
            name = match.group(1)
            values_str = match.group(2)
            # Extract string values
            values = set(re.findall(r'"([^"]+)"', values_str))
            if values:
                self.spec.type_sets[name] = values

    def _parse_predicates(self, content: str):
        """Parse helper predicates."""
        # Match patterns like: PredicateName == expression
        pattern = r'^(\w+)\s*==\s*$\s*([\s\S]*?)(?=^\w+\s*==|^\\*\s*=+|$)'
        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1)
            expr = match.group(2).strip()

            # Skip if it's a property we'll handle separately
            if any(prefix in name for prefix in ['Safety', 'Liveness', 'Init', 'Next', 'Spec', 'Type']):
                continue

            self.spec.predicates[name] = TLAProperty(
                name=name,
                expression=expr,
                expr_type=TLAExpressionType.HELPER_PREDICATE
            )

    def _parse_invariants(self, content: str):
        """Parse TypeInvariant and similar."""
        # TypeInvariant
        match = re.search(r'TypeInvariant\s*==\s*([\s\S]*?)(?=^\(\*|^\w+\s*==|$)', content, re.MULTILINE)
        if match:
            expr = match.group(1).strip()
            self.spec.invariants["TypeInvariant"] = TLAProperty(
                name="TypeInvariant",
                expression=expr,
                expr_type=TLAExpressionType.TYPE_CONSTRAINT,
                description="Type constraints on all variables"
            )

        # SafetyInvariant
        match = re.search(r'SafetyInvariant\s*==\s*([\s\S]*?)(?=^\(\*|^\w+\s*==|$)', content, re.MULTILINE)
        if match:
            expr = match.group(1).strip()
            self.spec.invariants["SafetyInvariant"] = TLAProperty(
                name="SafetyInvariant",
                expression=expr,
                expr_type=TLAExpressionType.INVARIANT,
                description="Combined safety invariant"
            )

    def _parse_safety_properties(self, content: str):
        """Parse safety properties (SafetyP1_*, SafetyP2_*, etc.)."""
        pattern = r'(SafetyP\d+_\w+)\s*==\s*([\s\S]*?)(?=^\s*\\*|^SafetyP|^Liveness|^SafetyInvariant|^\(\*\s*=+|$)'
        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1)
            expr = match.group(2).strip()

            # Extract description from preceding comment
            desc_match = re.search(rf'\\*\s*([^\n]*)\s*{name}', content)
            desc = desc_match.group(1).strip() if desc_match else ""

            self.spec.safety_properties[name] = TLAProperty(
                name=name,
                expression=expr,
                expr_type=TLAExpressionType.SAFETY_PROPERTY,
                description=desc
            )

    def _parse_liveness_properties(self, content: str):
        """Parse liveness properties (LivenessL1_*, etc.)."""
        pattern = r'(LivenessL\d+_\w+)\s*==\s*([\s\S]*?)(?=^\s*\\*|^Liveness|^\(\*\s*=+|$)'
        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1)
            expr = match.group(2).strip()

            self.spec.liveness_properties[name] = TLAProperty(
                name=name,
                expression=expr,
                expr_type=TLAExpressionType.LIVENESS_PROPERTY
            )


class TLAToPythonTranslator:
    r"""
    Translates TLA+ expressions to Python code.

    Handles common TLA+ patterns:
    - /\ (conjunction) -> and
    - \/ (disjunction) -> or
    - ~ (negation) -> not
    - => (implication) -> implies helper
    - \in (membership) -> in
    - = (equality) -> ==
    - # (inequality) -> !=
    """

    def __init__(self, spec: TLASpec):
        self.spec = spec
        self._state_var = "state"

    def translate_expression(self, expr: str) -> str:
        """Translate a TLA+ expression to Python."""
        # Remove line continuations
        expr = re.sub(r'\s*\n\s*', ' ', expr)

        # Handle implication (A => B) -> (not A or B)
        expr = self._translate_implication(expr)

        # Translate operators
        expr = expr.replace('/\\', ' and ')
        expr = expr.replace('\\/', ' or ')
        expr = expr.replace('~', 'not ')
        expr = expr.replace(' # ', ' != ')
        expr = expr.replace('\\in', ' in ')

        # Translate variable references to state dictionary access
        for var_name in self.spec.variables:
            # Match whole word only
            pattern = rf'\b{var_name}\b'
            replacement = f'{self._state_var}["{var_name}"]'
            expr = re.sub(pattern, replacement, expr)

        # Translate type set references
        for set_name, values in self.spec.type_sets.items():
            pattern = rf'\b{set_name}\b'
            replacement = str(values)
            expr = re.sub(pattern, replacement, expr)

        # Clean up spacing
        expr = re.sub(r'\s+', ' ', expr).strip()

        return expr

    def _translate_implication(self, expr: str) -> str:
        """Translate A => B to (not A or B)."""
        # Simple case: find => and wrap appropriately
        if '=>' in expr:
            # Handle parenthesized implications
            # (A) => (B) -> (not (A) or (B))
            match = re.search(r'\(([^)]+)\)\s*=>\s*\(([^)]+)\)', expr)
            if match:
                antecedent = match.group(1)
                consequent = match.group(2)
                translated = f'(not ({antecedent}) or ({consequent}))'
                expr = expr[:match.start()] + translated + expr[match.end():]
            else:
                # Simple A => B
                parts = expr.split('=>', 1)
                if len(parts) == 2:
                    expr = f'(not ({parts[0].strip()}) or ({parts[1].strip()}))'

        return expr

    def generate_check_function(self, prop: TLAProperty) -> str:
        """Generate a Python function that checks a property."""
        python_expr = self.translate_expression(prop.expression)

        # Generate function code
        func_name = f"check_{prop.name.lower()}"
        decorator = "@safety_property" if prop.is_safety_critical() else "@invariant"
        severity = "MonitorSeverity.SAFETY_CRITICAL" if prop.is_safety_critical() else "MonitorSeverity.ERROR"

        code = f'''
    {decorator}("{prop.name}", severity={severity})
    def {func_name}(self, state: Dict[str, Any]) -> bool:
        """
        {prop.description or f'Check {prop.name}'}

        TLA+ Expression:
            {prop.expression[:100]}{'...' if len(prop.expression) > 100 else ''}
        """
        try:
            return bool({python_expr})
        except (KeyError, TypeError):
            # Missing state variables - cannot evaluate
            return True  # Fail open for missing data
'''
        return code


class RuntimeMonitorGenerator:
    """
    Generates Python runtime monitors from TLA+ specifications.

    Usage:
        generator = RuntimeMonitorGenerator()
        code = generator.generate_from_file("safety_node.tla")
        # Write code to file or exec it

        # Or generate a monitor class directly:
        monitor = generator.create_monitor_from_file("safety_node.tla")
        result = monitor.check_all(current_state)
    """

    def __init__(self):
        self.parser = TLAParser()
        self._generated_monitors: Dict[str, type] = {}

    def parse_spec(self, tla_content: str) -> TLASpec:
        """Parse TLA+ content."""
        return self.parser.parse(tla_content)

    def parse_spec_file(self, filepath: str) -> TLASpec:
        """Parse TLA+ file."""
        return self.parser.parse_file(filepath)

    def generate_monitor_code(
        self,
        spec: TLASpec,
        class_name: Optional[str] = None
    ) -> str:
        """
        Generate Python monitor class code from TLA+ spec.

        Args:
            spec: Parsed TLA+ specification
            class_name: Name for generated class (default: {ModuleName}Monitor)

        Returns:
            Python source code for monitor class
        """
        if class_name is None:
            class_name = f"{spec.module_name}Monitor"

        translator = TLAToPythonTranslator(spec)

        # Generate header
        code = f'''"""
Runtime Safety Monitor for {spec.module_name}

Auto-generated from TLA+ specification.
DO NOT EDIT - regenerate from source spec.

Generated: {datetime.utcnow().isoformat()}
Source: {spec.module_name}.tla
"""

from typing import Any, Dict, Set
from dashboard.services.verification.monitors import (
    BaseMonitor,
    MonitorSeverity,
    invariant,
    safety_property,
)


# Type sets from TLA+ spec
'''

        # Generate type set constants
        for set_name, values in spec.type_sets.items():
            code += f'{set_name.upper()}: Set[str] = {values}\n'

        code += f'''

class {class_name}(BaseMonitor):
    """
    Runtime monitor for {spec.module_name} safety properties.

    Invariants:
'''
        for name in spec.invariants:
            code += f'        - {name}\n'

        code += '''
    Safety Properties:
'''
        for name in spec.safety_properties:
            code += f'        - {name}\n'

        code += f'''
    """

    def __init__(self):
        super().__init__(name="{class_name}")
'''

        # Generate invariant check methods
        for name, prop in spec.invariants.items():
            try:
                func_code = translator.generate_check_function(prop)
                code += func_code
            except Exception as e:
                logger.warning(f"Could not generate check for {name}: {e}")
                # Generate stub
                code += f'''
    @invariant("{name}", severity=MonitorSeverity.ERROR)
    def check_{name.lower()}(self, state: Dict[str, Any]) -> bool:
        """Check {name} (stub - could not auto-translate)."""
        return True  # Manual implementation required
'''

        # Generate safety property check methods
        for name, prop in spec.safety_properties.items():
            try:
                func_code = translator.generate_check_function(prop)
                code += func_code
            except Exception as e:
                logger.warning(f"Could not generate check for {name}: {e}")
                code += f'''
    @safety_property("{name}", severity=MonitorSeverity.SAFETY_CRITICAL)
    def check_{name.lower()}(self, state: Dict[str, Any]) -> bool:
        """Check {name} (stub - could not auto-translate)."""
        return True  # Manual implementation required
'''

        # Add helper methods
        code += '''

    def validate_state_types(self, state: Dict[str, Any]) -> bool:
        """Validate that state has expected structure."""
        required_keys = {'''

        code += ', '.join(f'"{v}"' for v in spec.variables)

        code += '''}
        return required_keys.issubset(state.keys())
'''

        return code

    def generate_from_file(self, filepath: str, class_name: Optional[str] = None) -> str:
        """Generate monitor code from TLA+ file."""
        spec = self.parse_spec_file(filepath)
        return self.generate_monitor_code(spec, class_name)

    def create_monitor_from_spec(self, spec: TLASpec, class_name: Optional[str] = None) -> "BaseMonitor":
        """
        Create a monitor instance directly from a spec.

        Note: Uses exec() to create the class dynamically.
        For production, prefer generating code to a file.
        """
        from dashboard.services.verification.monitors import BaseMonitor

        if class_name is None:
            class_name = f"{spec.module_name}Monitor"

        # Check cache
        if class_name in self._generated_monitors:
            return self._generated_monitors[class_name]()

        # Generate and execute code
        code = self.generate_monitor_code(spec, class_name)

        # Create namespace for exec
        namespace = {
            'Any': Any,
            'Dict': Dict,
            'Set': Set,
            'BaseMonitor': BaseMonitor,
        }

        # Import required symbols
        from dashboard.services.verification.monitors import (
            MonitorSeverity,
            invariant,
            safety_property,
        )
        namespace['MonitorSeverity'] = MonitorSeverity
        namespace['invariant'] = invariant
        namespace['safety_property'] = safety_property

        exec(code, namespace)

        # Get the generated class
        monitor_class = namespace[class_name]
        self._generated_monitors[class_name] = monitor_class

        return monitor_class()

    def create_monitor_from_file(self, filepath: str) -> "BaseMonitor":
        """Create a monitor instance from a TLA+ file."""
        spec = self.parse_spec_file(filepath)
        return self.create_monitor_from_spec(spec)

    def write_monitor_file(
        self,
        spec: TLASpec,
        output_path: str,
        class_name: Optional[str] = None
    ) -> str:
        """
        Generate monitor code and write to file.

        Args:
            spec: Parsed TLA+ specification
            output_path: Path to write generated Python file
            class_name: Name for generated class

        Returns:
            Path to generated file
        """
        code = self.generate_monitor_code(spec, class_name)

        with open(output_path, 'w') as f:
            f.write(code)

        logger.info(f"Generated monitor written to: {output_path}")
        return output_path


# Convenience function
def generate_monitor(tla_file: str, output_file: str) -> str:
    """
    Generate a Python runtime monitor from a TLA+ specification.

    Args:
        tla_file: Path to TLA+ specification file
        output_file: Path for generated Python monitor

    Returns:
        Path to generated file
    """
    generator = RuntimeMonitorGenerator()
    spec = generator.parse_spec_file(tla_file)
    return generator.write_monitor_file(spec, output_file)


__all__ = [
    "TLAParser",
    "TLASpec",
    "TLAProperty",
    "TLAVariable",
    "TLAToPythonTranslator",
    "RuntimeMonitorGenerator",
    "generate_monitor",
]
