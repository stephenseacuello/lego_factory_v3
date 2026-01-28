"""
HOQ to Digital Twin Bridge - Specification-Driven Design & Validation.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 2: Causal AI & Explainability Engine

Bridges House of Quality outputs to Digital Twin design and validation:
- HOQ Specifications → Digital Twin Design Parameters
- HOQ Targets → Validation Criteria
- HOQ Requirements → Test Cases
- Full traceability from customer needs to digital validation

Flow: HOQ → Specifications → Digital Twin Design → Validation
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
import logging
import uuid

from .hoq_engine import (
    HouseOfQuality, HouseOfQualityEngine,
    CustomerRequirement, TechnicalRequirement,
    RelationshipStrength, CorrelationType, KanoType
)
from .qfd_cascade import QFDCascade, QFDCascadeResult, QFDPhase

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation criteria."""
    CRITICAL = "critical"      # Must pass - safety/compatibility
    MAJOR = "major"            # Should pass - core functionality
    MINOR = "minor"            # Nice to have - quality polish
    INFO = "info"              # Informational only


class DesignParameterType(Enum):
    """Types of digital twin design parameters."""
    DIMENSIONAL = "dimensional"      # Physical dimensions
    MATERIAL = "material"            # Material properties
    PROCESS = "process"              # Process parameters
    THERMAL = "thermal"              # Temperature-related
    MECHANICAL = "mechanical"        # Force/stress-related
    SURFACE = "surface"              # Surface quality
    GEOMETRIC = "geometric"          # Geometric tolerances


class TestCaseType(Enum):
    """Types of digital twin test cases."""
    BOUNDARY = "boundary"            # Min/max limits
    NOMINAL = "nominal"              # Target values
    STRESS = "stress"                # Extreme conditions
    INTERACTION = "interaction"      # Multiple parameter interactions
    REGRESSION = "regression"        # Prevent regressions


@dataclass
class DigitalTwinDesignSpec:
    """Digital twin design specification derived from HOQ."""
    spec_id: str
    name: str
    parameter_type: DesignParameterType
    target_value: float
    unit: str
    tolerance_lower: float
    tolerance_upper: float
    direction: str  # "maximize", "minimize", "target"
    priority: float  # 0-100 from HOQ importance
    source_requirement_id: str
    source_customer_reqs: List[str]  # Traced back to customer needs
    validation_severity: ValidationSeverity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "name": self.name,
            "parameter_type": self.parameter_type.value,
            "target_value": self.target_value,
            "unit": self.unit,
            "tolerance_lower": self.tolerance_lower,
            "tolerance_upper": self.tolerance_upper,
            "direction": self.direction,
            "priority": self.priority,
            "source_requirement_id": self.source_requirement_id,
            "source_customer_reqs": self.source_customer_reqs,
            "validation_severity": self.validation_severity.value,
        }


@dataclass
class ValidationCriterion:
    """Validation criterion for digital twin design."""
    criterion_id: str
    name: str
    description: str
    check_type: str  # "range", "minimum", "maximum", "exact", "tolerance"
    target_value: float
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    unit: str
    severity: ValidationSeverity
    source_spec_id: str
    test_method: str
    acceptance_formula: str

    def evaluate(self, actual_value: float) -> Tuple[bool, str]:
        """Evaluate if actual value passes criterion."""
        if self.check_type == "range":
            passed = self.lower_bound <= actual_value <= self.upper_bound
            msg = f"{actual_value} {'within' if passed else 'outside'} [{self.lower_bound}, {self.upper_bound}]"
        elif self.check_type == "minimum":
            passed = actual_value >= self.lower_bound
            msg = f"{actual_value} {'>='}  {self.lower_bound}: {'PASS' if passed else 'FAIL'}"
        elif self.check_type == "maximum":
            passed = actual_value <= self.upper_bound
            msg = f"{actual_value} {'<='}  {self.upper_bound}: {'PASS' if passed else 'FAIL'}"
        elif self.check_type == "tolerance":
            tolerance = (self.upper_bound - self.lower_bound) / 2
            passed = abs(actual_value - self.target_value) <= tolerance
            msg = f"|{actual_value} - {self.target_value}| <= {tolerance}: {'PASS' if passed else 'FAIL'}"
        else:  # exact
            passed = abs(actual_value - self.target_value) < 0.001
            msg = f"{actual_value} == {self.target_value}: {'PASS' if passed else 'FAIL'}"

        return passed, msg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "name": self.name,
            "description": self.description,
            "check_type": self.check_type,
            "target_value": self.target_value,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "unit": self.unit,
            "severity": self.severity.value,
            "source_spec_id": self.source_spec_id,
            "test_method": self.test_method,
            "acceptance_formula": self.acceptance_formula,
        }


@dataclass
class DigitalTwinTestCase:
    """Test case for digital twin validation."""
    test_id: str
    name: str
    description: str
    test_type: TestCaseType
    parameters: Dict[str, float]  # Parameter name -> test value
    expected_outcomes: Dict[str, Tuple[float, float]]  # Outcome -> (min, max)
    priority: int  # 1-10
    source_criteria: List[str]  # Criterion IDs
    preconditions: List[str]
    steps: List[str]

    @property
    def validation_criteria_ids(self) -> List[str]:
        """Alias for source_criteria for compatibility."""
        return self.source_criteria

    @property
    def input_parameters(self) -> List[Dict[str, Any]]:
        """Get input parameters as list of dicts for UI compatibility."""
        return [{"name": k, "value": v} for k, v in self.parameters.items()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "description": self.description,
            "test_type": self.test_type.value,
            "parameters": self.parameters,
            "input_parameters": self.input_parameters,
            "expected_outcomes": {k: list(v) for k, v in self.expected_outcomes.items()},
            "priority": self.priority,
            "source_criteria": self.source_criteria,
            "validation_criteria_ids": self.validation_criteria_ids,
            "preconditions": self.preconditions,
            "steps": self.steps,
        }


@dataclass
class DigitalTwinDesignPackage:
    """Complete design package for digital twin from HOQ."""
    package_id: str
    name: str
    created_at: datetime
    source_hoq_id: str
    source_cascade_id: Optional[str]
    design_specs: List[DigitalTwinDesignSpec]
    validation_criteria: List[ValidationCriterion]
    test_cases: List[DigitalTwinTestCase]
    traceability_matrix: Dict[str, List[str]]  # customer_req -> [spec_ids]
    conflicts: List[Dict[str, Any]]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "source_hoq_id": self.source_hoq_id,
            "source_cascade_id": self.source_cascade_id,
            "design_specs": [s.to_dict() for s in self.design_specs],
            "validation_criteria": [c.to_dict() for c in self.validation_criteria],
            "test_cases": [t.to_dict() for t in self.test_cases],
            "traceability_matrix": self.traceability_matrix,
            "conflicts": self.conflicts,
            "recommendations": self.recommendations,
            "summary": {
                "total_specs": len(self.design_specs),
                "total_criteria": len(self.validation_criteria),
                "total_tests": len(self.test_cases),
                "critical_criteria": len([c for c in self.validation_criteria
                                         if c.severity == ValidationSeverity.CRITICAL]),
                "conflicts_count": len(self.conflicts),
            }
        }


class HOQDigitalTwinBridge:
    """
    Bridge HOQ specifications to Digital Twin design and validation.

    Flow:
    1. HOQ → Design Specifications (dimensional, material, process params)
    2. Specifications → Validation Criteria (pass/fail rules)
    3. Criteria → Test Cases (specific tests to run)
    4. Full traceability back to customer requirements

    Features:
    - Automatic specification generation from HOQ technical requirements
    - Validation criteria with severity levels
    - Test case generation for boundary, nominal, stress testing
    - Conflict detection between requirements
    - Design recommendations based on HOQ analysis
    """

    # Parameter type classification rules
    PARAMETER_TYPE_RULES = {
        "diameter": DesignParameterType.DIMENSIONAL,
        "height": DesignParameterType.DIMENSIONAL,
        "thickness": DesignParameterType.DIMENSIONAL,
        "width": DesignParameterType.DIMENSIONAL,
        "length": DesignParameterType.DIMENSIONAL,
        "temperature": DesignParameterType.THERMAL,
        "nozzle": DesignParameterType.THERMAL,
        "bed": DesignParameterType.THERMAL,
        "cooling": DesignParameterType.THERMAL,
        "force": DesignParameterType.MECHANICAL,
        "clutch": DesignParameterType.MECHANICAL,
        "strength": DesignParameterType.MECHANICAL,
        "adhesion": DesignParameterType.MECHANICAL,
        "surface": DesignParameterType.SURFACE,
        "roughness": DesignParameterType.SURFACE,
        "density": DesignParameterType.MATERIAL,
        "fill": DesignParameterType.MATERIAL,
        "material": DesignParameterType.MATERIAL,
        "speed": DesignParameterType.PROCESS,
        "layer": DesignParameterType.PROCESS,
        "extrusion": DesignParameterType.PROCESS,
        "tolerance": DesignParameterType.GEOMETRIC,
        "geometry": DesignParameterType.GEOMETRIC,
    }

    # Severity rules based on Kano type and keywords
    SEVERITY_RULES = {
        "stud": ValidationSeverity.CRITICAL,
        "clutch": ValidationSeverity.CRITICAL,
        "compatible": ValidationSeverity.CRITICAL,
        "diameter": ValidationSeverity.CRITICAL,
        "color": ValidationSeverity.MAJOR,
        "surface": ValidationSeverity.MAJOR,
        "strength": ValidationSeverity.MAJOR,
        "temperature": ValidationSeverity.MAJOR,
        "speed": ValidationSeverity.MINOR,
        "fill": ValidationSeverity.MINOR,
    }

    def __init__(self):
        self.hoq_engine = HouseOfQualityEngine()
        self.qfd_cascade = QFDCascade()

    def generate_design_package(self,
                                hoq: HouseOfQuality,
                                cascade_result: Optional[QFDCascadeResult] = None,
                                include_tests: bool = True) -> DigitalTwinDesignPackage:
        """
        Generate complete digital twin design package from HOQ.

        Args:
            hoq: House of Quality matrix
            cascade_result: Optional full QFD cascade for deeper specs
            include_tests: Whether to generate test cases

        Returns:
            Complete DigitalTwinDesignPackage
        """
        package_id = str(uuid.uuid4())[:8]

        # Generate design specifications
        design_specs = self._generate_design_specs(hoq, cascade_result)

        # Generate validation criteria
        validation_criteria = self._generate_validation_criteria(design_specs, hoq)

        # Generate test cases
        test_cases = []
        if include_tests:
            test_cases = self._generate_test_cases(validation_criteria, design_specs)

        # Build traceability matrix
        traceability = self._build_traceability_matrix(hoq, design_specs)

        # Detect conflicts
        conflicts = self._detect_design_conflicts(hoq, design_specs)

        # Generate recommendations
        recommendations = self._generate_recommendations(hoq, design_specs, conflicts)

        package = DigitalTwinDesignPackage(
            package_id=package_id,
            name=f"DT Design: {hoq.name}",
            created_at=datetime.now(),
            source_hoq_id=hoq.hoq_id,
            source_cascade_id=cascade_result.cascade_id if cascade_result else None,
            design_specs=design_specs,
            validation_criteria=validation_criteria,
            test_cases=test_cases,
            traceability_matrix=traceability,
            conflicts=conflicts,
            recommendations=recommendations,
        )

        logger.info(f"Generated DT design package '{package.name}' with "
                   f"{len(design_specs)} specs, {len(validation_criteria)} criteria, "
                   f"{len(test_cases)} tests")

        return package

    def _generate_design_specs(self,
                               hoq: HouseOfQuality,
                               cascade: Optional[QFDCascadeResult]) -> List[DigitalTwinDesignSpec]:
        """Generate design specifications from HOQ technical requirements."""
        specs = []

        # Process main HOQ technical requirements
        for tr in hoq.technical_requirements:
            # Determine parameter type
            param_type = self._classify_parameter_type(tr.description)

            # Get priority from HOQ importance scores
            priority = hoq.technical_importance.get(tr.req_id, 50.0)

            # Trace back to customer requirements
            customer_reqs = self._trace_to_customer_reqs(tr.req_id, hoq)

            # Determine severity
            severity = self._determine_severity(tr, customer_reqs, hoq)

            # Calculate tolerances
            tol_lower, tol_upper = self._calculate_tolerances(tr)

            spec = DigitalTwinDesignSpec(
                spec_id=f"DTS_{tr.req_id}",
                name=tr.description,
                parameter_type=param_type,
                target_value=tr.target_value,
                unit=tr.unit,
                tolerance_lower=tol_lower,
                tolerance_upper=tol_upper,
                direction=tr.direction,
                priority=priority,
                source_requirement_id=tr.req_id,
                source_customer_reqs=customer_reqs,
                validation_severity=severity,
            )
            specs.append(spec)

        # If cascade provided, include specs from all phases
        if cascade:
            for phase in cascade.phases[1:]:  # Skip Phase 1 (already processed)
                for tr in phase.hoq.technical_requirements:
                    if not any(s.source_requirement_id == tr.req_id for s in specs):
                        param_type = self._classify_parameter_type(tr.description)
                        priority = phase.hoq.technical_importance.get(tr.req_id, 30.0)
                        tol_lower, tol_upper = self._calculate_tolerances(tr)

                        spec = DigitalTwinDesignSpec(
                            spec_id=f"DTS_P{phase.phase_number}_{tr.req_id}",
                            name=f"[P{phase.phase_number}] {tr.description}",
                            parameter_type=param_type,
                            target_value=tr.target_value,
                            unit=tr.unit,
                            tolerance_lower=tol_lower,
                            tolerance_upper=tol_upper,
                            direction=tr.direction,
                            priority=priority,
                            source_requirement_id=tr.req_id,
                            source_customer_reqs=[],
                            validation_severity=ValidationSeverity.MINOR,
                        )
                        specs.append(spec)

        # Sort by priority
        specs.sort(key=lambda s: -s.priority)

        return specs

    def _generate_validation_criteria(self,
                                      specs: List[DigitalTwinDesignSpec],
                                      hoq: HouseOfQuality) -> List[ValidationCriterion]:
        """Generate validation criteria from design specifications."""
        criteria = []

        for spec in specs:
            # Determine check type based on direction
            if spec.direction == "minimize":
                check_type = "maximum"
                lower = None
                upper = spec.tolerance_upper
            elif spec.direction == "maximize":
                check_type = "minimum"
                lower = spec.tolerance_lower
                upper = None
            else:  # target
                check_type = "tolerance"
                lower = spec.tolerance_lower
                upper = spec.tolerance_upper

            # Generate acceptance formula
            if check_type == "tolerance":
                formula = f"|measured - {spec.target_value}| <= {(upper - lower) / 2:.4f}"
            elif check_type == "maximum":
                formula = f"measured <= {upper}"
            elif check_type == "minimum":
                formula = f"measured >= {lower}"
            else:
                formula = f"measured == {spec.target_value}"

            # Determine test method
            test_method = self._suggest_test_method(spec)

            criterion = ValidationCriterion(
                criterion_id=f"VC_{spec.spec_id}",
                name=f"Validate {spec.name}",
                description=f"Verify {spec.name} meets specification from HOQ",
                check_type=check_type,
                target_value=spec.target_value,
                lower_bound=lower,
                upper_bound=upper,
                unit=spec.unit,
                severity=spec.validation_severity,
                source_spec_id=spec.spec_id,
                test_method=test_method,
                acceptance_formula=formula,
            )
            criteria.append(criterion)

        return criteria

    def _generate_test_cases(self,
                            criteria: List[ValidationCriterion],
                            specs: List[DigitalTwinDesignSpec]) -> List[DigitalTwinTestCase]:
        """Generate test cases from validation criteria."""
        test_cases = []

        # Group criteria by severity for test prioritization
        critical_criteria = [c for c in criteria if c.severity == ValidationSeverity.CRITICAL]
        major_criteria = [c for c in criteria if c.severity == ValidationSeverity.MAJOR]

        # Generate boundary tests for critical specs
        for criterion in critical_criteria:
            spec = next((s for s in specs if s.spec_id == criterion.source_spec_id), None)
            if not spec:
                continue

            # Lower boundary test
            if criterion.lower_bound is not None:
                test_cases.append(DigitalTwinTestCase(
                    test_id=f"TC_BOUND_L_{spec.spec_id}",
                    name=f"Lower Boundary: {spec.name}",
                    description=f"Test {spec.name} at lower boundary ({criterion.lower_bound} {spec.unit})",
                    test_type=TestCaseType.BOUNDARY,
                    parameters={spec.name: criterion.lower_bound},
                    expected_outcomes={spec.name: (criterion.lower_bound, spec.target_value)},
                    priority=10,
                    source_criteria=[criterion.criterion_id],
                    preconditions=["Digital twin initialized", "All other parameters at nominal"],
                    steps=[
                        f"Set {spec.name} to lower boundary value: {criterion.lower_bound}",
                        "Run simulation for 1 cycle",
                        f"Verify output within acceptable range",
                    ],
                ))

            # Upper boundary test
            if criterion.upper_bound is not None:
                test_cases.append(DigitalTwinTestCase(
                    test_id=f"TC_BOUND_U_{spec.spec_id}",
                    name=f"Upper Boundary: {spec.name}",
                    description=f"Test {spec.name} at upper boundary ({criterion.upper_bound} {spec.unit})",
                    test_type=TestCaseType.BOUNDARY,
                    parameters={spec.name: criterion.upper_bound},
                    expected_outcomes={spec.name: (spec.target_value, criterion.upper_bound)},
                    priority=10,
                    source_criteria=[criterion.criterion_id],
                    preconditions=["Digital twin initialized", "All other parameters at nominal"],
                    steps=[
                        f"Set {spec.name} to upper boundary value: {criterion.upper_bound}",
                        "Run simulation for 1 cycle",
                        f"Verify output within acceptable range",
                    ],
                ))

        # Generate nominal tests for major specs
        for criterion in major_criteria:
            spec = next((s for s in specs if s.spec_id == criterion.source_spec_id), None)
            if not spec:
                continue

            test_cases.append(DigitalTwinTestCase(
                test_id=f"TC_NOM_{spec.spec_id}",
                name=f"Nominal: {spec.name}",
                description=f"Test {spec.name} at nominal target ({spec.target_value} {spec.unit})",
                test_type=TestCaseType.NOMINAL,
                parameters={spec.name: spec.target_value},
                expected_outcomes={spec.name: (spec.tolerance_lower, spec.tolerance_upper)},
                priority=8,
                source_criteria=[criterion.criterion_id],
                preconditions=["Digital twin initialized"],
                steps=[
                    f"Set {spec.name} to nominal value: {spec.target_value}",
                    "Run simulation for 3 cycles",
                    f"Verify all outputs within specification",
                ],
            ))

        # Generate interaction tests for correlated parameters
        for criterion1 in critical_criteria[:3]:
            for criterion2 in critical_criteria[3:6]:
                spec1 = next((s for s in specs if s.spec_id == criterion1.source_spec_id), None)
                spec2 = next((s for s in specs if s.spec_id == criterion2.source_spec_id), None)
                if not spec1 or not spec2:
                    continue

                test_cases.append(DigitalTwinTestCase(
                    test_id=f"TC_INT_{spec1.spec_id}_{spec2.spec_id}",
                    name=f"Interaction: {spec1.name} vs {spec2.name}",
                    description=f"Test interaction between {spec1.name} and {spec2.name}",
                    test_type=TestCaseType.INTERACTION,
                    parameters={
                        spec1.name: spec1.target_value,
                        spec2.name: spec2.target_value,
                    },
                    expected_outcomes={
                        spec1.name: (spec1.tolerance_lower, spec1.tolerance_upper),
                        spec2.name: (spec2.tolerance_lower, spec2.tolerance_upper),
                    },
                    priority=7,
                    source_criteria=[criterion1.criterion_id, criterion2.criterion_id],
                    preconditions=["Digital twin initialized"],
                    steps=[
                        f"Set {spec1.name} to {spec1.target_value}",
                        f"Set {spec2.name} to {spec2.target_value}",
                        "Run combined simulation",
                        "Verify no negative interactions",
                    ],
                ))
                break  # Limit interaction tests

        # Sort by priority
        test_cases.sort(key=lambda t: -t.priority)

        return test_cases

    def _build_traceability_matrix(self,
                                   hoq: HouseOfQuality,
                                   specs: List[DigitalTwinDesignSpec]) -> Dict[str, List[str]]:
        """Build traceability from customer requirements to specs."""
        traceability = {}

        for cr in hoq.customer_requirements:
            related_specs = []
            for spec in specs:
                if cr.req_id in spec.source_customer_reqs:
                    related_specs.append(spec.spec_id)
            traceability[cr.req_id] = related_specs

        return traceability

    def _detect_design_conflicts(self,
                                 hoq: HouseOfQuality,
                                 specs: List[DigitalTwinDesignSpec]) -> List[Dict[str, Any]]:
        """Detect conflicts between design specifications."""
        conflicts = []

        # Use HOQ correlation matrix to find conflicts
        for (req1_id, req2_id), corr in hoq.correlation_matrix.items():
            if corr in (CorrelationType.NEGATIVE, CorrelationType.STRONG_NEGATIVE):
                spec1 = next((s for s in specs if req1_id in s.source_requirement_id), None)
                spec2 = next((s for s in specs if req2_id in s.source_requirement_id), None)

                if spec1 and spec2:
                    conflicts.append({
                        "spec1_id": spec1.spec_id,
                        "spec1_name": spec1.name,
                        "spec2_id": spec2.spec_id,
                        "spec2_name": spec2.name,
                        "correlation": corr.name,
                        "impact": "high" if corr == CorrelationType.STRONG_NEGATIVE else "medium",
                        "recommendation": self._suggest_conflict_resolution(spec1, spec2, corr),
                    })

        return conflicts

    def _generate_recommendations(self,
                                  hoq: HouseOfQuality,
                                  specs: List[DigitalTwinDesignSpec],
                                  conflicts: List[Dict[str, Any]]) -> List[str]:
        """Generate design recommendations based on HOQ analysis."""
        recommendations = []

        # Priority-based recommendations
        high_priority_specs = [s for s in specs if s.priority > 70]
        if high_priority_specs:
            recommendations.append(
                f"Focus digital twin calibration on top {len(high_priority_specs)} priority parameters: "
                f"{', '.join(s.name for s in high_priority_specs[:5])}"
            )

        # Critical validation recommendations
        critical_specs = [s for s in specs if s.validation_severity == ValidationSeverity.CRITICAL]
        if critical_specs:
            recommendations.append(
                f"Implement real-time monitoring for {len(critical_specs)} critical parameters "
                f"to ensure LEGO compatibility"
            )

        # Conflict resolution recommendations
        if conflicts:
            recommendations.append(
                f"Resolve {len(conflicts)} parameter conflicts before finalizing digital twin design. "
                f"Consider trade-off analysis or innovative solutions."
            )

        # Coverage recommendations
        orphan_customer_reqs = []
        for cr in hoq.customer_requirements:
            has_coverage = any(cr.req_id in s.source_customer_reqs for s in specs)
            if not has_coverage:
                orphan_customer_reqs.append(cr.req_id)

        if orphan_customer_reqs:
            recommendations.append(
                f"Warning: {len(orphan_customer_reqs)} customer requirements have no digital twin coverage. "
                f"Review requirements: {', '.join(orphan_customer_reqs[:3])}"
            )

        # Process recommendations
        process_specs = [s for s in specs if s.parameter_type == DesignParameterType.PROCESS]
        if process_specs:
            recommendations.append(
                f"Configure digital twin process simulation with {len(process_specs)} process parameters "
                f"derived from QFD Phase 3"
            )

        # Thermal recommendations
        thermal_specs = [s for s in specs if s.parameter_type == DesignParameterType.THERMAL]
        if thermal_specs:
            recommendations.append(
                f"Enable PINN thermal model in digital twin for {len(thermal_specs)} "
                f"temperature-sensitive parameters"
            )

        return recommendations

    def _classify_parameter_type(self, description: str) -> DesignParameterType:
        """Classify parameter type from description."""
        desc_lower = description.lower()

        for keyword, param_type in self.PARAMETER_TYPE_RULES.items():
            if keyword in desc_lower:
                return param_type

        return DesignParameterType.PROCESS  # Default

    def _trace_to_customer_reqs(self,
                                tech_req_id: str,
                                hoq: HouseOfQuality) -> List[str]:
        """Trace technical requirement back to customer requirements."""
        customer_reqs = []

        for (cr_id, tr_id), strength in hoq.relationship_matrix.items():
            if tr_id == tech_req_id and strength != RelationshipStrength.NONE:
                customer_reqs.append(cr_id)

        return customer_reqs

    def _determine_severity(self,
                           tr: TechnicalRequirement,
                           customer_reqs: List[str],
                           hoq: HouseOfQuality) -> ValidationSeverity:
        """Determine validation severity based on requirement analysis."""
        desc_lower = tr.description.lower()

        # Check keyword rules
        for keyword, severity in self.SEVERITY_RULES.items():
            if keyword in desc_lower:
                return severity

        # Check if linked to must-be customer requirements
        for cr in hoq.customer_requirements:
            if cr.req_id in customer_reqs and cr.kano_type == KanoType.MUST_BE:
                return ValidationSeverity.CRITICAL

        # Default based on importance
        importance = hoq.technical_importance.get(tr.req_id, 50)
        if importance > 80:
            return ValidationSeverity.CRITICAL
        elif importance > 50:
            return ValidationSeverity.MAJOR
        else:
            return ValidationSeverity.MINOR

    def _calculate_tolerances(self, tr: TechnicalRequirement) -> Tuple[float, float]:
        """Calculate tolerance bounds for technical requirement."""
        if tr.tolerance:
            return (tr.target_value - tr.tolerance, tr.target_value + tr.tolerance)

        # Default tolerances based on direction and value
        if tr.direction == "minimize":
            return (0, tr.target_value * 1.1)
        elif tr.direction == "maximize":
            return (tr.target_value * 0.9, tr.target_value * 2)
        else:
            # Target: 5% tolerance
            margin = tr.target_value * 0.05 if tr.target_value != 0 else 0.1
            return (tr.target_value - margin, tr.target_value + margin)

    def _suggest_test_method(self, spec: DigitalTwinDesignSpec) -> str:
        """Suggest appropriate test method for specification."""
        test_methods = {
            DesignParameterType.DIMENSIONAL: "Digital caliper measurement simulation",
            DesignParameterType.THERMAL: "Thermal sensor array monitoring",
            DesignParameterType.MECHANICAL: "Force gauge simulation / FEA analysis",
            DesignParameterType.SURFACE: "Surface profilometry simulation",
            DesignParameterType.MATERIAL: "Material property lookup / density calculation",
            DesignParameterType.PROCESS: "Process parameter logging",
            DesignParameterType.GEOMETRIC: "CMM simulation / geometric analysis",
        }
        return test_methods.get(spec.parameter_type, "Direct measurement simulation")

    def _suggest_conflict_resolution(self,
                                     spec1: DigitalTwinDesignSpec,
                                     spec2: DigitalTwinDesignSpec,
                                     correlation: CorrelationType) -> str:
        """Suggest resolution for conflicting specifications."""
        if correlation == CorrelationType.STRONG_NEGATIVE:
            return (f"Critical trade-off: Consider prioritizing {spec1.name if spec1.priority > spec2.priority else spec2.name} "
                   f"based on HOQ priority scores, or explore innovative solutions "
                   f"(e.g., new materials, process modifications)")
        else:
            return (f"Moderate conflict: Optimize {spec1.name} and {spec2.name} together "
                   f"using multi-objective simulation in digital twin")

    def validate_digital_twin(self,
                              package: DigitalTwinDesignPackage,
                              actual_values: Dict[str, float]) -> Dict[str, Any]:
        """
        Validate digital twin measurements against design package.

        Args:
            package: Design package with validation criteria
            actual_values: Measured/simulated values from digital twin

        Returns:
            Validation report with pass/fail status
        """
        results = {
            "package_id": package.package_id,
            "validation_time": datetime.now().isoformat(),
            "overall_pass": True,
            "results": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "critical_failed": 0,
            }
        }

        for criterion in package.validation_criteria:
            spec_name = next(
                (s.name for s in package.design_specs if s.spec_id == criterion.source_spec_id),
                criterion.name
            )

            if spec_name in actual_values:
                passed, message = criterion.evaluate(actual_values[spec_name])

                result = {
                    "criterion_id": criterion.criterion_id,
                    "name": criterion.name,
                    "target": criterion.target_value,
                    "actual": actual_values[spec_name],
                    "passed": passed,
                    "message": message,
                    "severity": criterion.severity.value,
                }
                results["results"].append(result)
                results["summary"]["total"] += 1

                if passed:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    if criterion.severity == ValidationSeverity.CRITICAL:
                        results["summary"]["critical_failed"] += 1
                        results["overall_pass"] = False
                    elif criterion.severity == ValidationSeverity.MAJOR:
                        results["overall_pass"] = False

        return results

    def export_package(self, package: DigitalTwinDesignPackage) -> Dict[str, Any]:
        """
        Export a design package to dictionary format for API responses.

        Args:
            package: Design package to export

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return package.to_dict()

    def get_design_recommendations(self,
                                   package: DigitalTwinDesignPackage) -> List[Dict[str, Any]]:
        """
        Get actionable design recommendations from the package.

        Args:
            package: Design package to analyze

        Returns:
            List of recommendations with priority and actions
        """
        recommendations = []

        # High priority specs that need attention
        high_priority = [s for s in package.design_specs if s.priority > 70]
        if high_priority:
            recommendations.append({
                "type": "focus",
                "priority": "high",
                "title": "Critical Design Parameters",
                "description": f"Focus calibration on {len(high_priority)} high-priority parameters",
                "parameters": [s.name for s in high_priority[:5]],
                "action": "Ensure these parameters are validated first in digital twin"
            })

        # Conflicts that need resolution
        if package.conflicts:
            for conflict in package.conflicts:
                recommendations.append({
                    "type": "conflict",
                    "priority": "high",
                    "title": f"Parameter Conflict: {conflict.get('spec1_name')} vs {conflict.get('spec2_name')}",
                    "description": conflict.get("recommendation", "Resolve trade-off"),
                    "parameters": [conflict.get('spec1_name'), conflict.get('spec2_name')],
                    "action": "Run optimization to find optimal balance"
                })

        # Test coverage gaps
        specs_with_tests = set()
        for tc in package.test_cases:
            for crit_id in tc.validation_criteria_ids:
                crit = next((c for c in package.validation_criteria
                           if c.criterion_id == crit_id), None)
                if crit:
                    specs_with_tests.add(crit.source_spec_id)

        untested_specs = [s for s in package.design_specs if s.spec_id not in specs_with_tests]
        if untested_specs:
            recommendations.append({
                "type": "coverage",
                "priority": "medium",
                "title": "Test Coverage Gap",
                "description": f"{len(untested_specs)} specifications lack test coverage",
                "parameters": [s.name for s in untested_specs[:3]],
                "action": "Add test cases for uncovered parameters"
            })

        return recommendations


# Singleton instance
_hoq_dt_bridge: Optional[HOQDigitalTwinBridge] = None


def get_hoq_digital_twin_bridge() -> HOQDigitalTwinBridge:
    """Get singleton HOQ Digital Twin Bridge instance."""
    global _hoq_dt_bridge
    if _hoq_dt_bridge is None:
        _hoq_dt_bridge = HOQDigitalTwinBridge()
    return _hoq_dt_bridge
