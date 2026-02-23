"""
LEGO Compatibility API - LEGO-specific quality testing.
"""

from flask import Blueprint, jsonify, request, render_template

from models import get_db_session
from services.quality import LegoQualityService

lego_bp = Blueprint('lego', __name__, url_prefix='/lego')


# Dashboard Page Routes
@lego_bp.route('', methods=['GET'])
@lego_bp.route('/page', methods=['GET'])
def lego_testing_page():
    """Render LEGO compatibility testing dashboard page."""
    return render_template('pages/quality/lego_testing.html')


@lego_bp.route('/clutch-power', methods=['POST'])
def test_clutch_power():
    """
    Record clutch power test.

    Request body:
    {
        "inspection_id": "uuid",
        "force_newtons": 2.5,
        "test_type": "stud_connection",
        "notes": "Tested with official 2x4 brick"
    }
    """
    data = request.get_json()

    inspection_id = data.get('inspection_id')
    force_newtons = data.get('force_newtons')

    if not all([inspection_id, force_newtons is not None]):
        return jsonify({'error': 'inspection_id and force_newtons are required'}), 400

    with get_db_session() as session:
        service = LegoQualityService(session)

        result = service.test_clutch_power(
            inspection_id=inspection_id,
            force_newtons=force_newtons,
            test_type=data.get('test_type', 'stud_connection'),
            notes=data.get('notes')
        )

        return jsonify({
            'force_newtons': result.force_newtons,
            'rating': result.rating.value,
            'compatible_with_lego': result.compatible_with_lego,
            'notes': result.notes
        }), 201


@lego_bp.route('/fit-test', methods=['POST'])
def test_stud_fit():
    """
    Record stud fit test.

    Request body:
    {
        "inspection_id": "uuid",
        "fit_result": "optimal",
        "reference_brick": "official_lego",
        "notes": "Clean connection, no wobble"
    }
    """
    data = request.get_json()

    inspection_id = data.get('inspection_id')
    fit_result = data.get('fit_result')

    if not all([inspection_id, fit_result]):
        return jsonify({'error': 'inspection_id and fit_result are required'}), 400

    valid_results = ['too_tight', 'optimal', 'too_loose', 'no_fit']
    if fit_result not in valid_results:
        return jsonify({'error': f'fit_result must be one of: {valid_results}'}), 400

    with get_db_session() as session:
        service = LegoQualityService(session)

        result = service.test_stud_fit(
            inspection_id=inspection_id,
            fit_result=fit_result,
            reference_brick=data.get('reference_brick', 'official_lego'),
            notes=data.get('notes')
        )

        return jsonify(result), 201


@lego_bp.route('/dimensions', methods=['POST'])
def measure_critical_dimensions():
    """
    Measure critical LEGO dimensions.

    Request body:
    {
        "inspection_id": "uuid",
        "manufacturing_process": "fdm",
        "measurements": {
            "stud_diameter": 4.82,
            "stud_height": 1.68,
            "wall_thickness": 1.58
        }
    }
    """
    data = request.get_json()

    inspection_id = data.get('inspection_id')
    measurements = data.get('measurements', {})

    if not inspection_id or not measurements:
        return jsonify({'error': 'inspection_id and measurements are required'}), 400

    with get_db_session() as session:
        service = LegoQualityService(session)

        result = service.measure_critical_dimensions(
            inspection_id=inspection_id,
            measurements=measurements,
            manufacturing_process=data.get('manufacturing_process', 'fdm')
        )

        return jsonify(result), 201


@lego_bp.route('/compatibility-suite', methods=['POST'])
def run_compatibility_suite():
    """
    Run full LEGO compatibility test suite.

    Request body:
    {
        "inspection_id": "uuid",
        "stud_diameter": 4.82,
        "stud_height": 1.68,
        "wall_thickness": 1.58,
        "clutch_force": 2.5,
        "manufacturing_process": "fdm"
    }
    """
    data = request.get_json()

    required = ['inspection_id', 'stud_diameter', 'stud_height', 'wall_thickness']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing required fields: {missing}'}), 400

    with get_db_session() as session:
        service = LegoQualityService(session)

        result = service.run_compatibility_suite(
            inspection_id=data['inspection_id'],
            stud_diameter=data['stud_diameter'],
            stud_height=data['stud_height'],
            wall_thickness=data['wall_thickness'],
            clutch_force=data.get('clutch_force'),
            manufacturing_process=data.get('manufacturing_process', 'fdm')
        )

        return jsonify(result), 201


@lego_bp.route('/adjustments/<inspection_id>', methods=['GET'])
def get_recommended_adjustments(inspection_id: str):
    """Get recommended parameter adjustments based on inspection results."""
    manufacturing_process = request.args.get('process', 'fdm')

    with get_db_session() as session:
        service = LegoQualityService(session)

        adjustments = service.get_recommended_adjustments(
            inspection_id=inspection_id,
            manufacturing_process=manufacturing_process
        )

        return jsonify(adjustments)


@lego_bp.route('/specs', methods=['GET'])
def get_lego_specs():
    """Get LEGO dimension specifications."""
    from lego_specs import LEGO, MANUFACTURING_TOLERANCES

    return jsonify({
        'dimensions': {
            'stud_diameter': {'value': LEGO.STUD_DIAMETER, 'tolerance': LEGO.STUD_TOLERANCE, 'unit': 'mm'},
            'stud_height': {'value': LEGO.STUD_HEIGHT, 'tolerance': 0.05, 'unit': 'mm'},
            'stud_pitch': {'value': LEGO.STUD_PITCH, 'tolerance': 0.02, 'unit': 'mm'},
            'wall_thickness': {'value': LEGO.WALL_THICKNESS, 'tolerance': 0.05, 'unit': 'mm'},
            'brick_height': {'value': LEGO.BRICK_HEIGHT, 'tolerance': 0.05, 'unit': 'mm'},
            'plate_height': {'value': LEGO.PLATE_HEIGHT, 'tolerance': 0.03, 'unit': 'mm'},
            'tube_outer_diameter': {'value': LEGO.TUBE_OUTER_DIAMETER, 'tolerance': 0.05, 'unit': 'mm'},
            'tube_inner_diameter': {'value': LEGO.TUBE_INNER_DIAMETER, 'tolerance': 0.05, 'unit': 'mm'}
        },
        'clutch_power': {
            'min_force': 0.5,
            'optimal_min': 1.0,
            'optimal_max': 3.0,
            'max_force': 5.0,
            'unit': 'N'
        },
        'manufacturing_tolerances': MANUFACTURING_TOLERANCES
    })
