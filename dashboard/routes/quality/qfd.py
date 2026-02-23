"""
QFD Routes - Quality Function Deployment API

LegoMCP World-Class Manufacturing System v5.0
Phase 11: QFD / House of Quality

Provides:
- House of Quality (HoQ) management
- Customer requirement tracking
- Engineering characteristic mapping
- Relationship matrix management
- LEGO-specific templates
"""

from flask import Blueprint, jsonify, request, render_template

qfd_bp = Blueprint('qfd', __name__, url_prefix='/qfd')


# =============================================================================
# Dashboard Page Route
# =============================================================================

@qfd_bp.route('/page', methods=['GET'])
def qfd_dashboard():
    """Render the QFD/House of Quality dashboard page."""
    return render_template('pages/quality/hoq_dashboard.html')


@qfd_bp.route('/hoq/page', methods=['GET'])
def hoq_dashboard():
    """Render the House of Quality dashboard page (alias)."""
    return render_template('pages/quality/hoq_dashboard.html')

# Try to import QFD models
try:
    from models.qfd import (
        HouseOfQuality,
        CustomerRequirement,
        EngineeringCharacteristic,
        QFDRelationship,
        RelationshipStrength,
        Direction,
        KanoCategory,
        LEGO_REQUIREMENTS,
        LEGO_CHARACTERISTICS,
    )
    QFD_AVAILABLE = True
except ImportError:
    QFD_AVAILABLE = False

# In-memory storage
_hoq_store: dict = {}


def _get_hoq(hoq_id: str):
    """Get HoQ from store."""
    return _hoq_store.get(hoq_id)


@qfd_bp.route('', methods=['GET'])
def list_hoqs():
    """
    List all House of Quality records.

    Query params:
    - part_id: Filter by part ID
    - status: Filter by status (draft, review, approved, active)

    Returns:
        JSON list of HoQ records
    """
    part_id = request.args.get('part_id')
    status = request.args.get('status')

    hoqs = list(_hoq_store.values())

    if part_id:
        hoqs = [h for h in hoqs if h.part_id == part_id]

    if status:
        hoqs = [h for h in hoqs if h.status == status]

    return jsonify({
        'hoqs': [h.to_dict() for h in hoqs],
        'count': len(hoqs)
    })


@qfd_bp.route('', methods=['POST'])
def create_hoq():
    """
    Create a new House of Quality.

    Request body:
    {
        "name": "2x4 Brick QFD",
        "part_id": "PART-001",
        "description": "Quality requirements for standard 2x4 brick",
        "use_lego_template": true  // Auto-add LEGO requirements/characteristics
    }

    Returns:
        JSON with created HoQ
    """
    data = request.get_json() or {}

    if not QFD_AVAILABLE:
        return jsonify({'error': 'QFD models not available'}), 500

    hoq = HouseOfQuality(
        hoq_id='',  # Will be auto-generated
        name=data.get('name', 'New HoQ'),
        part_id=data.get('part_id'),
        description=data.get('description', ''),
    )

    # Add LEGO template if requested
    if data.get('use_lego_template', False):
        # Add customer requirements
        for req_data in LEGO_REQUIREMENTS:
            req = CustomerRequirement(
                requirement_id='',
                requirement_text=req_data['text'],
                importance=req_data['importance'],
                kano_category=KanoCategory(req_data['kano']),
            )
            hoq.add_requirement(req)

        # Add engineering characteristics
        for char_data in LEGO_CHARACTERISTICS:
            char = EngineeringCharacteristic(
                characteristic_id='',
                characteristic_name=char_data['name'],
                unit_of_measure=char_data['unit'],
                target_value=char_data.get('target'),
                direction=Direction(char_data.get('direction', 'target')),
                tolerance=char_data.get('tolerance'),
            )
            hoq.add_characteristic(char)

    _hoq_store[hoq.hoq_id] = hoq

    return jsonify({
        'success': True,
        'hoq': hoq.to_dict()
    }), 201


@qfd_bp.route('/<hoq_id>', methods=['GET'])
def get_hoq(hoq_id: str):
    """
    Get House of Quality by ID.

    Returns:
        JSON with HoQ details including matrix
    """
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    response = hoq.to_dict()
    response['relationship_matrix'] = hoq.get_relationship_matrix()
    response['priority_characteristics'] = [
        c.to_dict() for c in hoq.get_priority_characteristics()
    ]
    response['unmet_requirements'] = [
        r.to_dict() for r in hoq.get_unmet_requirements()
    ]

    return jsonify(response)


@qfd_bp.route('/<hoq_id>/requirements', methods=['GET'])
def get_requirements(hoq_id: str):
    """Get customer requirements for a HoQ."""
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    requirements = sorted(
        hoq.customer_requirements,
        key=lambda r: r.relative_weight_percent,
        reverse=True
    )

    return jsonify({
        'hoq_id': hoq_id,
        'requirements': [r.to_dict() for r in requirements],
        'count': len(requirements)
    })


@qfd_bp.route('/<hoq_id>/requirements', methods=['POST'])
def add_requirement(hoq_id: str):
    """
    Add a customer requirement.

    Request body:
    {
        "requirement_text": "Brick should click firmly",
        "importance": 9,
        "kano_category": "must_be",
        "our_rating": 4.0,
        "target_rating": 5.0,
        "sales_point": 1.5
    }

    Returns:
        JSON with added requirement
    """
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    data = request.get_json() or {}

    req = CustomerRequirement(
        requirement_id='',
        requirement_text=data.get('requirement_text', ''),
        importance=int(data.get('importance', 5)),
        kano_category=KanoCategory(data.get('kano_category', 'one_dimensional')),
        our_rating=float(data.get('our_rating', 3.0)),
        competitor_a_rating=float(data.get('competitor_a_rating', 3.0)),
        competitor_b_rating=float(data.get('competitor_b_rating', 3.0)),
        target_rating=float(data.get('target_rating', 4.0)),
        sales_point=float(data.get('sales_point', 1.0)),
    )

    hoq.add_requirement(req)

    return jsonify({
        'success': True,
        'requirement': req.to_dict()
    }), 201


@qfd_bp.route('/<hoq_id>/characteristics', methods=['GET'])
def get_characteristics(hoq_id: str):
    """Get engineering characteristics for a HoQ."""
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    characteristics = sorted(
        hoq.engineering_characteristics,
        key=lambda c: c.relative_importance_percent,
        reverse=True
    )

    return jsonify({
        'hoq_id': hoq_id,
        'characteristics': [c.to_dict() for c in characteristics],
        'count': len(characteristics)
    })


@qfd_bp.route('/<hoq_id>/characteristics', methods=['POST'])
def add_characteristic(hoq_id: str):
    """
    Add an engineering characteristic.

    Request body:
    {
        "characteristic_name": "Stud diameter",
        "unit_of_measure": "mm",
        "direction": "target",
        "target_value": 4.8,
        "tolerance": 0.02,
        "technical_difficulty": 3
    }

    Returns:
        JSON with added characteristic
    """
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    data = request.get_json() or {}

    char = EngineeringCharacteristic(
        characteristic_id='',
        characteristic_name=data.get('characteristic_name', ''),
        unit_of_measure=data.get('unit_of_measure', ''),
        direction=Direction(data.get('direction', 'target')),
        current_value=data.get('current_value'),
        target_value=data.get('target_value'),
        tolerance=data.get('tolerance'),
        technical_difficulty=int(data.get('technical_difficulty', 3)),
    )

    hoq.add_characteristic(char)

    return jsonify({
        'success': True,
        'characteristic': char.to_dict()
    }), 201


@qfd_bp.route('/<hoq_id>/relationships', methods=['GET'])
def get_relationships(hoq_id: str):
    """Get relationship matrix for a HoQ."""
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    return jsonify({
        'hoq_id': hoq_id,
        'relationships': [r.to_dict() for r in hoq.relationships],
        'matrix': hoq.get_relationship_matrix(),
        'count': len(hoq.relationships)
    })


@qfd_bp.route('/<hoq_id>/relationships', methods=['POST'])
def set_relationship(hoq_id: str):
    """
    Set relationship between requirement and characteristic.

    Request body:
    {
        "requirement_id": "req-001",
        "characteristic_id": "char-001",
        "strength": 9  // 0=none, 1=weak, 3=moderate, 9=strong
    }

    Returns:
        JSON with updated HoQ
    """
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    data = request.get_json() or {}

    strength_value = int(data.get('strength', 0))
    strength_map = {0: RelationshipStrength.NONE, 1: RelationshipStrength.WEAK,
                    3: RelationshipStrength.MODERATE, 9: RelationshipStrength.STRONG}
    strength = strength_map.get(strength_value, RelationshipStrength.NONE)

    hoq.set_relationship(
        data.get('requirement_id'),
        data.get('characteristic_id'),
        strength
    )

    return jsonify({
        'success': True,
        'hoq': hoq.to_dict()
    })


@qfd_bp.route('/<hoq_id>/analysis', methods=['GET'])
def get_analysis(hoq_id: str):
    """
    Get QFD analysis results.

    Returns:
        JSON with priority rankings, gaps, and recommendations
    """
    hoq = _get_hoq(hoq_id)
    if not hoq:
        return jsonify({'error': 'HoQ not found'}), 404

    priority_chars = hoq.get_priority_characteristics(5)
    unmet_reqs = hoq.get_unmet_requirements()

    return jsonify({
        'hoq_id': hoq_id,
        'analysis': {
            'top_priority_characteristics': [
                {
                    'name': c.characteristic_name,
                    'importance': c.relative_importance_percent,
                    'meeting_target': c.is_meeting_target()
                }
                for c in priority_chars
            ],
            'unmet_requirements': [
                {
                    'text': r.requirement_text,
                    'gap': r.target_rating - r.our_rating,
                    'importance': r.importance
                }
                for r in unmet_reqs
            ],
            'improvement_opportunities': len(unmet_reqs),
            'completion_percent': (
                100 * (len(hoq.customer_requirements) - len(unmet_reqs)) /
                len(hoq.customer_requirements) if hoq.customer_requirements else 0
            )
        }
    })


@qfd_bp.route('/templates/lego', methods=['GET'])
def get_lego_templates():
    """
    Get LEGO-specific QFD templates.

    Returns:
        JSON with predefined requirements and characteristics
    """
    return jsonify({
        'requirements': LEGO_REQUIREMENTS if QFD_AVAILABLE else [],
        'characteristics': LEGO_CHARACTERISTICS if QFD_AVAILABLE else [],
        'relationship_strengths': {
            'none': 0,
            'weak': 1,
            'moderate': 3,
            'strong': 9
        },
        'kano_categories': ['must_be', 'one_dimensional', 'attractive', 'indifferent', 'reverse'],
        'directions': ['maximize', 'minimize', 'target']
    })


# =============================================================================
# Digital Twin Bridge Routes - HOQ → Specs → DT Design → Validation
# =============================================================================

# Try to import Digital Twin Bridge
try:
    from dashboard.services.quality.qfd import (
        HOQDigitalTwinBridge,
        get_hoq_digital_twin_bridge,
    )
    from dashboard.services.quality.qfd import (
        HouseOfQualityEngine as ServiceHOQEngine,
        QFDCascade,
        CustomerRequirement as ServiceCustomerReq,
        KanoType,
    )
    DT_BRIDGE_AVAILABLE = True
except ImportError:
    DT_BRIDGE_AVAILABLE = False

# In-memory storage for design packages
_design_package_store: dict = {}


@qfd_bp.route('/<hoq_id>/design-package', methods=['POST'])
def generate_design_package(hoq_id: str):
    """
    Generate a Digital Twin Design Package from HOQ.

    This is the core HOQ → Specifications → DT Design flow.

    Request body (optional):
    {
        "include_tests": true,        // Generate test cases
        "include_cascade": true,      // Include 4-phase QFD cascade
        "customer_requirements": [    // Optional: use these instead of stored HOQ
            {"id": "CR1", "description": "...", "importance": 9}
        ]
    }

    Returns:
        JSON with complete design package including specs, validation criteria, and tests
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    data = request.get_json() or {}
    include_tests = data.get('include_tests', True)
    include_cascade = data.get('include_cascade', False)

    # Get or build HOQ
    hoq = _get_hoq(hoq_id)

    if not hoq and data.get('customer_requirements'):
        # Build HOQ from provided requirements
        engine = ServiceHOQEngine()
        customer_reqs = [
            ServiceCustomerReq(
                req_id=r.get('id', f'CR_{i}'),
                description=r.get('description', ''),
                importance=float(r.get('importance', 5)),
                kano_type=KanoType(r.get('kano_type', 'one_dimensional')),
                category=r.get('category', 'customer')
            )
            for i, r in enumerate(data['customer_requirements'])
        ]

        # Use cascade for complete flow
        if include_cascade:
            cascade = QFDCascade()
            cascade_result = cascade.execute_cascade(f"HOQ-{hoq_id}", customer_reqs)
            service_hoq = cascade_result.phases[0].hoq
        else:
            # Build single HOQ with LEGO design specs
            from dashboard.services.quality.qfd.hoq_engine import TechnicalRequirement
            design_specs = [
                TechnicalRequirement(req_id="DS_001", description="Stud diameter",
                                    unit="mm", target_value=4.8, direction="target", tolerance=0.02),
                TechnicalRequirement(req_id="DS_002", description="Stud height",
                                    unit="mm", target_value=1.7, direction="target", tolerance=0.05),
                TechnicalRequirement(req_id="DS_003", description="Clutch force",
                                    unit="N", target_value=2.0, direction="target", tolerance=0.5),
                TechnicalRequirement(req_id="DS_004", description="Surface roughness Ra",
                                    unit="um", target_value=0.8, direction="minimize"),
                TechnicalRequirement(req_id="DS_005", description="Color accuracy deltaE",
                                    unit="deltaE", target_value=1.0, direction="minimize"),
                TechnicalRequirement(req_id="DS_006", description="Wall thickness",
                                    unit="mm", target_value=1.5, direction="target", tolerance=0.05),
            ]
            service_hoq = engine.build_hoq(f"HOQ-{hoq_id}", customer_reqs, design_specs)
            cascade_result = None
    elif hoq:
        # Convert stored HOQ to service HOQ format
        engine = ServiceHOQEngine()
        customer_reqs = [
            ServiceCustomerReq(
                req_id=r.requirement_id,
                description=r.requirement_text,
                importance=float(r.importance),
                kano_type=KanoType.ONE_DIMENSIONAL,
                category='customer'
            )
            for r in hoq.customer_requirements
        ]

        if include_cascade:
            cascade = QFDCascade()
            cascade_result = cascade.execute_cascade(hoq.name, customer_reqs)
            service_hoq = cascade_result.phases[0].hoq
        else:
            from dashboard.services.quality.qfd.hoq_engine import TechnicalRequirement
            design_specs = [
                TechnicalRequirement(
                    req_id=c.characteristic_id,
                    description=c.characteristic_name,
                    unit=c.unit_of_measure,
                    target_value=c.target_value or 0,
                    direction=c.direction.value if hasattr(c.direction, 'value') else 'target',
                    tolerance=c.tolerance
                )
                for c in hoq.engineering_characteristics
            ]
            service_hoq = engine.build_hoq(hoq.name, customer_reqs, design_specs)
            cascade_result = None
    else:
        return jsonify({'error': 'HOQ not found and no requirements provided'}), 404

    # Generate design package using bridge
    bridge = get_hoq_digital_twin_bridge()
    package = bridge.generate_design_package(
        hoq=service_hoq,
        cascade_result=cascade_result,
        include_tests=include_tests
    )

    # Export to dict
    package_dict = bridge.export_package(package)

    # Store for later retrieval
    _design_package_store[hoq_id] = package

    return jsonify({
        'success': True,
        'hoq_id': hoq_id,
        'package': package_dict,
        'summary': {
            'total_specs': len(package.design_specs),
            'total_validation_criteria': len(package.validation_criteria),
            'total_test_cases': len(package.test_cases),
            'critical_specs': len([s for s in package.design_specs
                                  if s.validation_severity.value == 'critical']),
            'traceability_complete': len(package.traceability_matrix) > 0
        }
    }), 201


@qfd_bp.route('/<hoq_id>/design-package', methods=['GET'])
def get_design_package(hoq_id: str):
    """
    Get existing Digital Twin Design Package.

    Returns:
        JSON with design package or 404 if not found
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    package = _design_package_store.get(hoq_id)
    if not package:
        return jsonify({'error': 'Design package not found. Generate one first.'}), 404

    bridge = get_hoq_digital_twin_bridge()
    return jsonify({
        'hoq_id': hoq_id,
        'package': bridge.export_package(package)
    })


@qfd_bp.route('/<hoq_id>/validate', methods=['POST'])
def validate_digital_twin(hoq_id: str):
    """
    Validate a Digital Twin against the design package.

    Request body:
    {
        "actual_values": {
            "SPEC_DS_001": 4.81,    // Actual stud diameter
            "SPEC_DS_002": 1.68,    // Actual stud height
            "SPEC_DS_003": 2.1,     // Actual clutch force
            ...
        }
    }

    Returns:
        JSON with validation results including pass/fail per criterion
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    package = _design_package_store.get(hoq_id)
    if not package:
        return jsonify({'error': 'Design package not found. Generate one first.'}), 404

    data = request.get_json() or {}
    actual_values = data.get('actual_values', {})

    if not actual_values:
        return jsonify({'error': 'actual_values required'}), 400

    bridge = get_hoq_digital_twin_bridge()
    results = bridge.validate_digital_twin(package, actual_values)

    return jsonify({
        'hoq_id': hoq_id,
        'validation_results': results,
        'overall_pass': results.get('overall_pass', False),
        'summary': {
            'total_criteria': results.get('total_criteria', 0),
            'passed': results.get('passed', 0),
            'failed': results.get('failed', 0),
            'skipped': results.get('skipped', 0),
            'pass_rate': results.get('pass_rate', 0)
        }
    })


@qfd_bp.route('/<hoq_id>/traceability', methods=['GET'])
def get_traceability_matrix(hoq_id: str):
    """
    Get full traceability matrix: Customer Reqs → Specs → Validation.

    Query params:
    - format: "matrix" (default) or "list"

    Returns:
        JSON with traceability from customer requirements to test cases
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    package = _design_package_store.get(hoq_id)
    if not package:
        return jsonify({'error': 'Design package not found. Generate one first.'}), 404

    output_format = request.args.get('format', 'matrix')

    if output_format == 'list':
        # Flat list format
        traceability_list = []
        for customer_req_id, spec_ids in package.traceability_matrix.items():
            for spec_id in spec_ids:
                spec = next((s for s in package.design_specs if s.spec_id == spec_id), None)
                criteria = [c for c in package.validation_criteria if c.source_spec_id == spec_id]
                tests = [t for t in package.test_cases if any(
                    c.criterion_id in t.validation_criteria_ids for c in criteria
                )]

                traceability_list.append({
                    'customer_requirement': customer_req_id,
                    'spec': {
                        'id': spec_id,
                        'name': spec.name if spec else 'Unknown',
                        'target': spec.target_value if spec else None,
                        'unit': spec.unit if spec else None
                    },
                    'validation_criteria': [
                        {'id': c.criterion_id, 'name': c.name, 'severity': c.severity.value}
                        for c in criteria
                    ],
                    'test_cases': [
                        {'id': t.test_id, 'name': t.name, 'type': t.test_type.value}
                        for t in tests
                    ]
                })

        return jsonify({
            'hoq_id': hoq_id,
            'format': 'list',
            'traceability': traceability_list
        })
    else:
        # Matrix format
        return jsonify({
            'hoq_id': hoq_id,
            'format': 'matrix',
            'customer_to_specs': package.traceability_matrix,
            'specs': [
                {
                    'id': s.spec_id,
                    'name': s.name,
                    'source_customer_reqs': s.source_customer_reqs,
                    'validation_severity': s.validation_severity.value
                }
                for s in package.design_specs
            ],
            'validation_criteria': [
                {
                    'id': c.criterion_id,
                    'name': c.name,
                    'source_spec': c.source_spec_id,
                    'severity': c.severity.value
                }
                for c in package.validation_criteria
            ],
            'test_coverage': {
                'total_specs': len(package.design_specs),
                'specs_with_tests': len(set(
                    c.source_spec_id for c in package.validation_criteria
                    if any(c.criterion_id in t.validation_criteria_ids for t in package.test_cases)
                )),
                'total_test_cases': len(package.test_cases)
            }
        })


@qfd_bp.route('/<hoq_id>/cascade', methods=['POST'])
def execute_qfd_cascade(hoq_id: str):
    """
    Execute 4-phase QFD cascade and generate design package.

    This runs the complete flow:
    Phase 1: Product Planning (Customer → Design)
    Phase 2: Part Deployment (Design → Parts)
    Phase 3: Process Planning (Parts → Process)
    Phase 4: Production Planning (Process → Production)

    Then generates Digital Twin design specs from the cascade.

    Request body:
    {
        "customer_requirements": [
            {"id": "CR1", "description": "Bricks connect firmly", "importance": 9},
            {"id": "CR2", "description": "Easy to separate", "importance": 8}
        ],
        "project_name": "2x4 LEGO Brick"
    }

    Returns:
        JSON with cascade results and design package
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    data = request.get_json() or {}
    customer_reqs_data = data.get('customer_requirements', [])
    project_name = data.get('project_name', f'Project-{hoq_id}')

    if not customer_reqs_data:
        return jsonify({'error': 'customer_requirements required'}), 400

    # Build customer requirements
    customer_reqs = [
        ServiceCustomerReq(
            req_id=r.get('id', f'CR_{i}'),
            description=r.get('description', ''),
            importance=float(r.get('importance', 5)),
            kano_type=KanoType(r.get('kano_type', 'one_dimensional')),
            category=r.get('category', 'customer')
        )
        for i, r in enumerate(customer_reqs_data)
    ]

    # Execute cascade
    cascade = QFDCascade()
    cascade_result = cascade.execute_cascade(project_name, customer_reqs)

    # Generate design package from cascade
    bridge = get_hoq_digital_twin_bridge()
    package = bridge.generate_design_package(
        hoq=cascade_result.phases[0].hoq,
        cascade_result=cascade_result,
        include_tests=True
    )

    # Store package
    _design_package_store[hoq_id] = package

    # Export cascade
    cascade_export = cascade.export_cascade(cascade_result)

    return jsonify({
        'success': True,
        'hoq_id': hoq_id,
        'cascade': {
            'cascade_id': cascade_result.cascade_id,
            'project_name': cascade_result.project_name,
            'phases': [
                {
                    'number': p.phase_number,
                    'name': p.phase_name,
                    'inputs': len(p.inputs),
                    'outputs': len(p.outputs),
                    'top_priority': p.hoq.get_priority_technicals(1)[0] if p.hoq.technical_importance else None
                }
                for p in cascade_result.phases
            ],
            'critical_path': cascade_result.critical_path,
            'summary': cascade_result.summary
        },
        'design_package': {
            'total_specs': len(package.design_specs),
            'total_validation_criteria': len(package.validation_criteria),
            'total_test_cases': len(package.test_cases)
        }
    }), 201


@qfd_bp.route('/<hoq_id>/recommendations', methods=['GET'])
def get_design_recommendations(hoq_id: str):
    """
    Get actionable design recommendations from HOQ analysis.

    Analyzes the design package and provides prioritized recommendations
    for focus areas, conflict resolution, and test coverage improvements.

    Returns:
        JSON with prioritized recommendations and actions
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    package = _design_package_store.get(hoq_id)
    if not package:
        return jsonify({'error': 'Design package not found. Generate one first.'}), 404

    bridge = get_hoq_digital_twin_bridge()
    recommendations = bridge.get_design_recommendations(package)

    return jsonify({
        'hoq_id': hoq_id,
        'package_id': package.package_id,
        'recommendations': recommendations,
        'summary': {
            'total_recommendations': len(recommendations),
            'high_priority': len([r for r in recommendations if r.get('priority') == 'high']),
            'conflicts': len([r for r in recommendations if r.get('type') == 'conflict']),
            'coverage_gaps': len([r for r in recommendations if r.get('type') == 'coverage']),
        }
    })


@qfd_bp.route('/<hoq_id>/summary', methods=['GET'])
def get_package_summary(hoq_id: str):
    """
    Get a comprehensive summary of the design package.

    Returns key metrics, critical parameters, and overall status.

    Returns:
        JSON with package summary
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    package = _design_package_store.get(hoq_id)
    if not package:
        return jsonify({'error': 'Design package not found. Generate one first.'}), 404

    # Calculate metrics
    critical_specs = [s for s in package.design_specs
                     if s.validation_severity.value == 'critical']
    major_specs = [s for s in package.design_specs
                  if s.validation_severity.value == 'major']

    # Top priority parameters
    sorted_specs = sorted(package.design_specs, key=lambda s: -s.priority)

    return jsonify({
        'hoq_id': hoq_id,
        'package_id': package.package_id,
        'name': package.name,
        'created_at': package.created_at.isoformat(),
        'metrics': {
            'total_design_specs': len(package.design_specs),
            'critical_specs': len(critical_specs),
            'major_specs': len(major_specs),
            'validation_criteria': len(package.validation_criteria),
            'test_cases': len(package.test_cases),
            'conflicts': len(package.conflicts),
            'customer_requirements_traced': len(package.traceability_matrix),
        },
        'critical_parameters': [
            {
                'name': s.name,
                'target': s.target_value,
                'unit': s.unit,
                'tolerance': f"{s.tolerance_lower:.4f} - {s.tolerance_upper:.4f}",
                'priority': s.priority
            }
            for s in critical_specs[:5]
        ],
        'top_priority_parameters': [
            {
                'name': s.name,
                'target': s.target_value,
                'unit': s.unit,
                'priority': s.priority,
                'severity': s.validation_severity.value
            }
            for s in sorted_specs[:5]
        ],
        'recommendations_summary': package.recommendations[:3] if package.recommendations else []
    })


@qfd_bp.route('/batch-validate', methods=['POST'])
def batch_validate_twins():
    """
    Validate multiple digital twins against their design packages.

    Request body:
    {
        "validations": [
            {
                "hoq_id": "hoq-001",
                "work_center_id": "PRINTER-001",
                "actual_values": {"Stud diameter": 4.81, ...}
            },
            {
                "hoq_id": "hoq-002",
                "work_center_id": "PRINTER-002",
                "actual_values": {...}
            }
        ]
    }

    Returns:
        JSON with validation results for all twins
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    data = request.get_json() or {}
    validations = data.get('validations', [])

    if not validations:
        return jsonify({'error': 'validations array required'}), 400

    bridge = get_hoq_digital_twin_bridge()
    results = []
    overall_pass = True
    total_passed = 0
    total_failed = 0

    for validation in validations:
        hoq_id = validation.get('hoq_id')
        work_center_id = validation.get('work_center_id', hoq_id)
        actual_values = validation.get('actual_values', {})

        package = _design_package_store.get(hoq_id)
        if not package:
            results.append({
                'hoq_id': hoq_id,
                'work_center_id': work_center_id,
                'status': 'error',
                'error': 'Design package not found'
            })
            continue

        if not actual_values:
            results.append({
                'hoq_id': hoq_id,
                'work_center_id': work_center_id,
                'status': 'skipped',
                'error': 'No actual_values provided'
            })
            continue

        validation_result = bridge.validate_digital_twin(package, actual_values)

        result_entry = {
            'hoq_id': hoq_id,
            'work_center_id': work_center_id,
            'status': 'pass' if validation_result.get('overall_pass') else 'fail',
            'passed': validation_result.get('summary', {}).get('passed', 0),
            'failed': validation_result.get('summary', {}).get('failed', 0),
            'pass_rate': validation_result.get('summary', {}).get('pass_rate', 0),
        }

        results.append(result_entry)

        if validation_result.get('overall_pass'):
            total_passed += 1
        else:
            total_failed += 1
            overall_pass = False

    return jsonify({
        'batch_results': results,
        'overall_pass': overall_pass,
        'summary': {
            'total_twins': len(validations),
            'passed': total_passed,
            'failed': total_failed,
            'errors': len([r for r in results if r.get('status') == 'error']),
            'skipped': len([r for r in results if r.get('status') == 'skipped']),
        }
    })


@qfd_bp.route('/<hoq_id>/export', methods=['GET'])
def export_design_package(hoq_id: str):
    """
    Export design package in various formats.

    Query params:
    - format: "json" (default), "csv", "summary"

    Returns:
        Design package in requested format
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    package = _design_package_store.get(hoq_id)
    if not package:
        return jsonify({'error': 'Design package not found. Generate one first.'}), 404

    export_format = request.args.get('format', 'json')
    bridge = get_hoq_digital_twin_bridge()

    if export_format == 'csv':
        # Generate CSV export
        import io
        output = io.StringIO()

        # Header
        output.write("Design Package Export - " + package.name + "\n")
        output.write("Generated: " + package.created_at.isoformat() + "\n\n")

        # Design Specs
        output.write("DESIGN SPECIFICATIONS\n")
        output.write("Spec ID,Name,Target,Unit,Lower Tolerance,Upper Tolerance,Severity,Priority\n")
        for spec in package.design_specs:
            output.write(f"{spec.spec_id},{spec.name},{spec.target_value},{spec.unit},"
                        f"{spec.tolerance_lower},{spec.tolerance_upper},"
                        f"{spec.validation_severity.value},{spec.priority}\n")

        output.write("\nVALIDATION CRITERIA\n")
        output.write("Criterion ID,Name,Check Type,Target,Lower Bound,Upper Bound,Severity\n")
        for vc in package.validation_criteria:
            output.write(f"{vc.criterion_id},{vc.name},{vc.check_type},{vc.target_value},"
                        f"{vc.lower_bound or ''},{vc.upper_bound or ''},{vc.severity.value}\n")

        output.write("\nTEST CASES\n")
        output.write("Test ID,Name,Type,Priority,Criteria Count\n")
        for tc in package.test_cases:
            output.write(f"{tc.test_id},{tc.name},{tc.test_type.value},"
                        f"{tc.priority},{len(tc.validation_criteria_ids)}\n")

        csv_content = output.getvalue()

        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=design_package_{hoq_id}.csv'}
        )

    elif export_format == 'summary':
        # Generate summary report
        critical_specs = [s for s in package.design_specs
                        if s.validation_severity.value == 'critical']

        return jsonify({
            'hoq_id': hoq_id,
            'package_name': package.name,
            'export_format': 'summary',
            'executive_summary': {
                'total_specs': len(package.design_specs),
                'critical_specs': len(critical_specs),
                'validation_criteria': len(package.validation_criteria),
                'test_cases': len(package.test_cases),
                'conflicts': len(package.conflicts),
                'recommendations': len(package.recommendations),
            },
            'critical_parameters': [
                {
                    'name': s.name,
                    'target': f"{s.target_value} {s.unit}",
                    'tolerance': f"+/- {(s.tolerance_upper - s.tolerance_lower) / 2:.4f}",
                }
                for s in critical_specs
            ],
            'key_recommendations': package.recommendations[:5],
            'traceability_coverage': {
                'customer_requirements_traced': len(package.traceability_matrix),
                'specs_per_requirement': sum(len(v) for v in package.traceability_matrix.values()) / max(len(package.traceability_matrix), 1),
            }
        })

    else:
        # JSON export (default)
        return jsonify({
            'hoq_id': hoq_id,
            'export_format': 'json',
            'package': bridge.export_package(package)
        })


@qfd_bp.route('/compare', methods=['POST'])
def compare_design_packages():
    """
    Compare two design packages to identify differences.

    Request body:
    {
        "package_a": "hoq-001",
        "package_b": "hoq-002"
    }

    Returns:
        JSON with comparison results
    """
    if not DT_BRIDGE_AVAILABLE:
        return jsonify({'error': 'Digital Twin Bridge not available'}), 500

    data = request.get_json() or {}
    package_a_id = data.get('package_a')
    package_b_id = data.get('package_b')

    if not package_a_id or not package_b_id:
        return jsonify({'error': 'Both package_a and package_b IDs required'}), 400

    package_a = _design_package_store.get(package_a_id)
    package_b = _design_package_store.get(package_b_id)

    if not package_a:
        return jsonify({'error': f'Package {package_a_id} not found'}), 404
    if not package_b:
        return jsonify({'error': f'Package {package_b_id} not found'}), 404

    # Compare specs
    specs_a = {s.name: s for s in package_a.design_specs}
    specs_b = {s.name: s for s in package_b.design_specs}

    common_specs = set(specs_a.keys()) & set(specs_b.keys())
    only_in_a = set(specs_a.keys()) - set(specs_b.keys())
    only_in_b = set(specs_b.keys()) - set(specs_a.keys())

    spec_differences = []
    for name in common_specs:
        a = specs_a[name]
        b = specs_b[name]
        if a.target_value != b.target_value or a.tolerance_lower != b.tolerance_lower:
            spec_differences.append({
                'spec_name': name,
                'package_a': {
                    'target': a.target_value,
                    'tolerance': f"{a.tolerance_lower} - {a.tolerance_upper}",
                    'severity': a.validation_severity.value,
                },
                'package_b': {
                    'target': b.target_value,
                    'tolerance': f"{b.tolerance_lower} - {b.tolerance_upper}",
                    'severity': b.validation_severity.value,
                },
                'target_diff': abs(a.target_value - b.target_value),
            })

    return jsonify({
        'package_a': package_a_id,
        'package_b': package_b_id,
        'comparison': {
            'total_specs_a': len(package_a.design_specs),
            'total_specs_b': len(package_b.design_specs),
            'common_specs': len(common_specs),
            'only_in_a': list(only_in_a),
            'only_in_b': list(only_in_b),
            'spec_differences': spec_differences,
            'criteria_count_a': len(package_a.validation_criteria),
            'criteria_count_b': len(package_b.validation_criteria),
            'test_count_a': len(package_a.test_cases),
            'test_count_b': len(package_b.test_cases),
        },
        'summary': {
            'identical': len(spec_differences) == 0 and len(only_in_a) == 0 and len(only_in_b) == 0,
            'differences_found': len(spec_differences),
            'specs_added': len(only_in_b),
            'specs_removed': len(only_in_a),
        }
    })


@qfd_bp.route('/digital-twin-bridge/page', methods=['GET'])
def digital_twin_bridge_page():
    """Render the HOQ to Digital Twin Bridge dashboard page."""
    return render_template('pages/quality/hoq_dt_bridge.html')
