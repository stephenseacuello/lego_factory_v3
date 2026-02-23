#!/usr/bin/env python3
"""
HOQ to Digital Twin - Complete Workflow Example

Demonstrates the full flow from customer requirements through
House of Quality to Digital Twin design and validation.

LEGO MCP v6.0 - World-Class Manufacturing Research Platform

Flow:
1. Define customer requirements (Voice of Customer)
2. Build House of Quality with technical specifications
3. Execute 4-Phase QFD Cascade
4. Generate Digital Twin Design Package
5. Configure Digital Twin from package
6. Validate Digital Twin against HOQ specs

Usage:
    python scripts/hoq_to_digital_twin_example.py
"""

import sys
import os
from datetime import datetime
import importlib.util

# Check dependencies
try:
    import numpy
except ImportError:
    print("ERROR: numpy is required. Install with: pip install numpy")
    sys.exit(1)

# Add parent directory to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)


def load_module_direct(module_name, file_path):
    """Load a module directly from file path, bypassing package __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main():
    print("=" * 70)
    print("HOQ to Digital Twin - Complete Workflow Example")
    print("LEGO MCP v6.0 - World-Class Manufacturing")
    print("=" * 70)
    print()

    # =========================================================================
    # Step 1: Define Customer Requirements (Voice of Customer)
    # =========================================================================
    print("STEP 1: Defining Customer Requirements")
    print("-" * 50)

    # Load modules directly to avoid sqlalchemy dependency
    hoq_engine_mod = load_module_direct(
        "hoq_engine",
        os.path.join(ROOT_DIR, "dashboard/services/quality/qfd/hoq_engine.py")
    )
    qfd_cascade_mod = load_module_direct(
        "qfd_cascade",
        os.path.join(ROOT_DIR, "dashboard/services/quality/qfd/qfd_cascade.py")
    )
    hoq_dt_bridge_mod = load_module_direct(
        "hoq_dt_bridge",
        os.path.join(ROOT_DIR, "dashboard/services/quality/qfd/hoq_digital_twin_bridge.py")
    )

    HouseOfQualityEngine = hoq_engine_mod.HouseOfQualityEngine
    CustomerRequirement = hoq_engine_mod.CustomerRequirement
    TechnicalRequirement = hoq_engine_mod.TechnicalRequirement
    KanoType = hoq_engine_mod.KanoType
    QFDCascade = qfd_cascade_mod.QFDCascade
    get_hoq_digital_twin_bridge = hoq_dt_bridge_mod.get_hoq_digital_twin_bridge

    # LEGO brick customer requirements (typical VOC)
    customer_requirements = [
        CustomerRequirement(
            req_id="CR_001",
            description="Bricks connect firmly with official LEGO",
            importance=10.0,
            kano_type=KanoType.MUST_BE,
            category="compatibility",
            source="customer_survey"
        ),
        CustomerRequirement(
            req_id="CR_002",
            description="Easy to separate by hand",
            importance=8.0,
            kano_type=KanoType.ONE_DIMENSIONAL,
            category="usability",
            source="customer_survey"
        ),
        CustomerRequirement(
            req_id="CR_003",
            description="Accurate color matching",
            importance=7.0,
            kano_type=KanoType.ONE_DIMENSIONAL,
            category="appearance",
            source="focus_group"
        ),
        CustomerRequirement(
            req_id="CR_004",
            description="Smooth surface finish",
            importance=6.0,
            kano_type=KanoType.ATTRACTIVE,
            category="appearance",
            source="focus_group"
        ),
        CustomerRequirement(
            req_id="CR_005",
            description="Strong and durable",
            importance=9.0,
            kano_type=KanoType.MUST_BE,
            category="durability",
            source="customer_survey"
        ),
    ]

    print(f"  Defined {len(customer_requirements)} customer requirements:")
    for cr in customer_requirements:
        print(f"    [{cr.kano_type.value:15}] {cr.description} (importance: {cr.importance})")

    # =========================================================================
    # Step 2: Build House of Quality
    # =========================================================================
    print()
    print("STEP 2: Building House of Quality (HOQ)")
    print("-" * 50)

    hoq_engine = HouseOfQualityEngine()

    # Technical requirements that address customer needs
    technical_requirements = [
        TechnicalRequirement(
            req_id="TR_001",
            description="Stud diameter",
            unit="mm",
            target_value=4.8,
            direction="target",
            tolerance=0.02,
            difficulty=7
        ),
        TechnicalRequirement(
            req_id="TR_002",
            description="Stud height",
            unit="mm",
            target_value=1.7,
            direction="target",
            tolerance=0.05,
            difficulty=6
        ),
        TechnicalRequirement(
            req_id="TR_003",
            description="Clutch force",
            unit="N",
            target_value=2.0,
            direction="target",
            tolerance=0.5,
            difficulty=8
        ),
        TechnicalRequirement(
            req_id="TR_004",
            description="Surface roughness Ra",
            unit="um",
            target_value=0.8,
            direction="minimize",
            difficulty=5
        ),
        TechnicalRequirement(
            req_id="TR_005",
            description="Color accuracy deltaE",
            unit="deltaE",
            target_value=1.0,
            direction="minimize",
            difficulty=4
        ),
        TechnicalRequirement(
            req_id="TR_006",
            description="Wall thickness",
            unit="mm",
            target_value=1.5,
            direction="target",
            tolerance=0.05,
            difficulty=5
        ),
    ]

    hoq = hoq_engine.build_hoq(
        name="LEGO 2x4 Brick HOQ",
        customer_reqs=customer_requirements,
        technical_reqs=technical_requirements
    )

    print(f"  Built HOQ: {hoq.name}")
    print(f"  - WHATs (Customer Reqs): {len(hoq.customer_requirements)}")
    print(f"  - HOWs (Technical Reqs): {len(hoq.technical_requirements)}")
    print(f"  - Relationships mapped: {len(hoq.relationship_matrix)}")
    print()
    print("  Technical Priority Ranking:")
    for req_id, score in hoq.get_priority_technicals(5):
        tr = next((t for t in technical_requirements if t.req_id == req_id), None)
        if tr:
            print(f"    {score:6.1f}% - {tr.description} ({tr.target_value} {tr.unit})")

    # =========================================================================
    # Step 3: Execute 4-Phase QFD Cascade
    # =========================================================================
    print()
    print("STEP 3: Executing 4-Phase QFD Cascade")
    print("-" * 50)

    cascade = QFDCascade()
    cascade_result = cascade.execute_cascade(
        project_name="LEGO 2x4 Brick Production",
        customer_requirements=customer_requirements
    )

    print(f"  Cascade ID: {cascade_result.cascade_id}")
    print(f"  Project: {cascade_result.project_name}")
    print()
    for phase in cascade_result.phases:
        print(f"  Phase {phase.phase_number}: {phase.phase_name}")
        print(f"    - Inputs: {len(phase.inputs)} requirements")
        print(f"    - Outputs: {len(phase.outputs)} specifications")
        top = phase.hoq.get_priority_technicals(1)
        if top:
            print(f"    - Top Priority: {top[0][0]} (score: {top[0][1]:.1f})")

    print()
    print(f"  Critical Path: {' -> '.join(cascade_result.critical_path[:4])}...")

    # =========================================================================
    # Step 4: Generate Digital Twin Design Package
    # =========================================================================
    print()
    print("STEP 4: Generating Digital Twin Design Package")
    print("-" * 50)

    bridge = get_hoq_digital_twin_bridge()
    design_package = bridge.generate_design_package(
        hoq=hoq,
        cascade_result=cascade_result,
        include_tests=True
    )

    print(f"  Package ID: {design_package.package_id}")
    print(f"  Package Name: {design_package.name}")
    print(f"  Created: {design_package.created_at}")
    print()
    print(f"  Design Specifications: {len(design_package.design_specs)}")
    for spec in design_package.design_specs[:5]:
        print(f"    [{spec.validation_severity.value:8}] {spec.name}: "
              f"{spec.target_value} {spec.unit} "
              f"[{spec.tolerance_lower:.4f} - {spec.tolerance_upper:.4f}]")

    print()
    print(f"  Validation Criteria: {len(design_package.validation_criteria)}")
    for vc in design_package.validation_criteria[:3]:
        print(f"    - {vc.name}: {vc.acceptance_formula}")

    print()
    print(f"  Test Cases Generated: {len(design_package.test_cases)}")
    for tc in design_package.test_cases[:3]:
        print(f"    [{tc.test_type.value:11}] {tc.name}")

    print()
    print(f"  Recommendations ({len(design_package.recommendations)}):")
    for rec in design_package.recommendations[:3]:
        print(f"    - {rec[:70]}...")

    # =========================================================================
    # Step 5: Configure Digital Twin from Package
    # =========================================================================
    print()
    print("STEP 5: Configuring Digital Twin from HOQ Package")
    print("-" * 50)

    # Create a minimal in-memory twin manager for demo
    # (avoiding full import chain that requires database)
    class SimpleTwinManager:
        """Minimal twin manager for demo purposes."""

        def __init__(self):
            self._cache = {}

        def configure_from_hoq_package(self, work_center_id, design_package):
            snapshot = {
                'work_center_id': work_center_id,
                'process_params': {},
                'metadata': {}
            }

            result = {
                'work_center_id': work_center_id,
                'package_id': design_package.get('package_id'),
                'configured_at': datetime.utcnow().isoformat(),
                'specs_applied': [],
                'validation_rules': [],
                'monitoring_enabled': [],
            }

            for spec in design_package.get('design_specs', []):
                param_name = spec.get('name', '').lower().replace(' ', '_')
                snapshot['process_params'][param_name] = spec.get('target_value', 0)
                snapshot['metadata'][f"hoq_spec_{spec.get('spec_id')}"] = spec
                result['specs_applied'].append(spec.get('spec_id'))

            snapshot['metadata']['hoq_validation_criteria'] = design_package.get('validation_criteria', [])
            snapshot['metadata']['hoq_traceability'] = design_package.get('traceability_matrix', {})
            snapshot['metadata']['hoq_package_id'] = design_package.get('package_id')
            result['validation_rules'] = [c.get('criterion_id') for c in design_package.get('validation_criteria', [])]

            critical_specs = [s for s in design_package.get('design_specs', [])
                            if s.get('validation_severity') == 'critical']
            for spec in critical_specs:
                param_name = spec.get('name', '').lower().replace(' ', '_')
                result['monitoring_enabled'].append(param_name)

            self._cache[work_center_id] = snapshot
            return result

        def validate_against_hoq(self, work_center_id, measured_values=None):
            snapshot = self._cache.get(work_center_id, {})
            criteria = snapshot.get('metadata', {}).get('hoq_validation_criteria', [])
            values = measured_values or snapshot.get('process_params', {})

            results = {
                'work_center_id': work_center_id,
                'validation_time': datetime.utcnow().isoformat(),
                'hoq_package_id': snapshot.get('metadata', {}).get('hoq_package_id'),
                'overall_pass': True,
                'total_criteria': len(criteria),
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'details': [],
            }

            for criterion in criteria:
                param_name = criterion.get('name', '').replace('Validate ', '').lower().replace(' ', '_')
                if param_name not in values:
                    results['skipped'] += 1
                    results['details'].append({
                        'criterion_id': criterion.get('criterion_id'),
                        'status': 'skip',
                        'message': f"Parameter '{param_name}' not found",
                    })
                    continue

                actual = values[param_name]
                target = criterion.get('target_value', 0)
                lower = criterion.get('lower_bound')
                upper = criterion.get('upper_bound')

                if lower is not None and upper is not None:
                    passed = lower <= actual <= upper
                    message = f"{actual} {'within' if passed else 'outside'} [{lower:.4f}, {upper:.4f}]"
                else:
                    tolerance = abs(target * 0.05)
                    passed = abs(actual - target) <= tolerance
                    message = f"|{actual} - {target}| <= {tolerance:.4f}: {'PASS' if passed else 'FAIL'}"

                results['details'].append({
                    'criterion_id': criterion.get('criterion_id'),
                    'status': 'pass' if passed else 'fail',
                    'expected': target,
                    'actual': actual,
                    'message': message,
                    'severity': criterion.get('severity'),
                })

                if passed:
                    results['passed'] += 1
                else:
                    results['failed'] += 1
                    if criterion.get('severity') in ('critical', 'major'):
                        results['overall_pass'] = False

            results['pass_rate'] = (results['passed'] / results['total_criteria'] * 100
                                    if results['total_criteria'] > 0 else 0)
            return results

        def get_hoq_traceability(self, work_center_id):
            snapshot = self._cache.get(work_center_id, {})
            return {
                'work_center_id': work_center_id,
                'hoq_package_id': snapshot.get('metadata', {}).get('hoq_package_id'),
                'traceability_matrix': snapshot.get('metadata', {}).get('hoq_traceability', {}),
                'configured_specs': [
                    k.replace('hoq_spec_', '') for k in snapshot.get('metadata', {}).keys()
                    if k.startswith('hoq_spec_')
                ],
                'validation_criteria_count': len(
                    snapshot.get('metadata', {}).get('hoq_validation_criteria', [])
                ),
            }

    twin_manager = SimpleTwinManager()

    # Configure digital twin from design package
    config_result = twin_manager.configure_from_hoq_package(
        work_center_id="PRINTER-001",
        design_package=design_package.to_dict()
    )

    print(f"  Work Center: {config_result['work_center_id']}")
    print(f"  Configured at: {config_result['configured_at']}")
    print(f"  Specs Applied: {len(config_result['specs_applied'])}")
    print(f"  Validation Rules: {len(config_result['validation_rules'])}")
    print(f"  Monitoring Enabled: {config_result['monitoring_enabled']}")

    # =========================================================================
    # Step 6: Validate Digital Twin Against HOQ
    # =========================================================================
    print()
    print("STEP 6: Validating Digital Twin Against HOQ Specifications")
    print("-" * 50)

    # Simulate measured values (close to targets for demo)
    measured_values = {
        "stud_diameter": 4.81,        # Target: 4.8
        "stud_height": 1.68,          # Target: 1.7
        "clutch_force": 2.1,          # Target: 2.0
        "surface_roughness_ra": 0.75, # Target: 0.8 (minimize)
        "color_accuracy_deltae": 1.2, # Target: 1.0 (minimize)
        "wall_thickness": 1.48,       # Target: 1.5
    }

    print("  Measured Values:")
    for param, value in measured_values.items():
        print(f"    {param}: {value}")

    validation_result = twin_manager.validate_against_hoq(
        work_center_id="PRINTER-001",
        measured_values=measured_values
    )

    print()
    print(f"  Validation Results:")
    print(f"    Overall Pass: {validation_result.get('overall_pass', 'N/A')}")
    print(f"    Pass Rate: {validation_result.get('pass_rate', 0):.1f}%")
    print(f"    Passed: {validation_result.get('passed', 0)}")
    print(f"    Failed: {validation_result.get('failed', 0)}")
    print(f"    Skipped: {validation_result.get('skipped', 0)}")

    print()
    print("  Detailed Results:")
    for detail in validation_result.get('details', [])[:6]:
        status_icon = "PASS" if detail['status'] == 'pass' else "FAIL" if detail['status'] == 'fail' else "SKIP"
        print(f"    [{status_icon}] {detail.get('message', 'N/A')}")

    # =========================================================================
    # Step 7: Get Traceability
    # =========================================================================
    print()
    print("STEP 7: HOQ Traceability Report")
    print("-" * 50)

    traceability = twin_manager.get_hoq_traceability("PRINTER-001")
    print(f"  Package ID: {traceability.get('hoq_package_id')}")
    print(f"  Configured Specs: {len(traceability.get('configured_specs', []))}")
    print(f"  Validation Criteria: {traceability.get('validation_criteria_count', 0)}")

    print()
    print("  Customer Requirement -> Spec Traceability:")
    for cr_id, spec_ids in list(traceability.get('traceability_matrix', {}).items())[:5]:
        cr = next((c for c in customer_requirements if c.req_id == cr_id), None)
        if cr:
            print(f"    {cr_id} ({cr.description[:30]}...)")
            for spec_id in spec_ids[:2]:
                print(f"      -> {spec_id}")

    # =========================================================================
    # Summary
    # =========================================================================
    print()
    print("=" * 70)
    print("WORKFLOW COMPLETE - SUMMARY")
    print("=" * 70)
    print()
    print("  The complete HOQ to Digital Twin flow has been demonstrated:")
    print()
    print("  1. Voice of Customer     : 5 customer requirements captured")
    print("  2. House of Quality      : Matrix built with relationship analysis")
    print("  3. QFD Cascade           : 4-phase deployment from customer to production")
    print("  4. Design Package        : Specs, validation criteria, and tests generated")
    print("  5. Digital Twin Config   : Twin configured with HOQ-derived parameters")
    print("  6. Validation            : Twin validated against HOQ specifications")
    print("  7. Traceability          : Full trace from customer needs to validation")
    print()
    print("  This workflow ensures that customer requirements flow through to")
    print("  digital twin validation, with complete traceability at every step.")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
