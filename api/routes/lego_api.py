"""
LEGO Factory v3 - LEGO Brick Design API
=======================================
REST API endpoints for LEGO brick design and manufacturing.

Provides endpoints for:
- Brick catalog browsing
- Custom brick design
- Dimension calculations
- Slicing integration
- Export jobs
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

logger = logging.getLogger(__name__)

lego_api_bp = Blueprint('lego_api', __name__, url_prefix='/api/lego')


# ─────────────────────────────────────────────────────────────────────────────
# Brick Catalog
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/catalog', methods=['GET'])
@jwt_required()
def get_catalog():
    """
    Get brick catalog with optional filtering.

    Query params:
    - category: Filter by category (basic, plate, tile, slope, technic, etc.)
    - tag: Filter by tag
    - search: Search in brick names
    - studs_x: Filter by x-dimension
    - studs_y: Filter by y-dimension
    """
    try:
        from services.lego.brick_catalog import (
            search_bricks, get_catalog_stats, BrickCategory
        )

        category_str = request.args.get('category')
        tag = request.args.get('tag')
        search = request.args.get('search')
        studs_x = request.args.get('studs_x', type=int)
        studs_y = request.args.get('studs_y', type=int)

        category = BrickCategory(category_str) if category_str else None

        bricks = search_bricks(
            category=category,
            tag=tag,
            search=search,
            studs_x=studs_x,
            studs_y=studs_y
        )

        return jsonify({
            'bricks': [b.to_dict() for b in bricks],
            'count': len(bricks),
            'filters': {
                'category': category_str,
                'tag': tag,
                'search': search,
                'studs_x': studs_x,
                'studs_y': studs_y,
            },
        })

    except Exception as e:
        logger.warning(f"Catalog error: {e}")
        return _demo_catalog()


@lego_api_bp.route('/catalog/stats', methods=['GET'])
@jwt_required()
def get_catalog_stats():
    """Get catalog statistics."""
    try:
        from services.lego.brick_catalog import get_catalog_stats
        stats = get_catalog_stats()
        return jsonify(stats)
    except Exception as e:
        logger.warning(f"Stats error: {e}")
        return jsonify({
            'total_bricks': 150,
            'by_category': {
                'basic': 45,
                'plate': 40,
                'tile': 30,
                'slope': 20,
                'technic': 15,
            },
            'unique_tags': 25,
        })


@lego_api_bp.route('/catalog/categories', methods=['GET'])
@jwt_required()
def list_categories():
    """List all brick categories."""
    try:
        from services.lego.brick_catalog import list_categories
        categories = list_categories()
        return jsonify({
            'categories': categories,
            'count': len(categories),
        })
    except Exception as e:
        logger.warning(f"Categories error: {e}")
        return jsonify({
            'categories': [
                'basic', 'plate', 'tile', 'slope', 'curved',
                'wedge', 'technic', 'modified', 'special'
            ],
            'count': 9,
        })


@lego_api_bp.route('/catalog/tags', methods=['GET'])
@jwt_required()
def list_tags():
    """List all unique tags in the catalog."""
    try:
        from services.lego.brick_catalog import list_tags
        tags = list_tags()
        return jsonify({
            'tags': tags,
            'count': len(tags),
        })
    except Exception as e:
        logger.warning(f'Exception in lego_api.py: {e}')
        return jsonify({
            'tags': ['basic', 'plate', 'brick', 'tile', 'slope', 'technic'],
            'count': 6,
        })


@lego_api_bp.route('/catalog/<brick_id>', methods=['GET'])
@jwt_required()
def get_brick(brick_id: str):
    """Get a specific brick definition."""
    try:
        from services.lego.brick_catalog import get_brick
        brick = get_brick(brick_id)
        if not brick:
            return jsonify({'error': 'Brick not found'}), 404
        return jsonify(brick.to_dict())
    except Exception as e:
        logger.warning(f"Get brick error: {e}")
        return jsonify({'error': 'Brick not found'}), 404


# ─────────────────────────────────────────────────────────────────────────────
# Brick Design & Dimensions
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/dimensions', methods=['GET'])
@jwt_required()
def calculate_dimensions():
    """
    Calculate brick dimensions.

    Query params:
    - studs_x: Number of studs in X (required)
    - studs_y: Number of studs in Y (required)
    - height_units: Height in brick units (default: 1.0)
    - include_clearance: Include manufacturing clearance (default: false)
    """
    try:
        from services.lego.lego_specs import (
            brick_dimensions, brick_dimensions_with_clearance,
            stud_positions, tube_positions, calculate_volume, calculate_weight, LEGO
        )

        studs_x = request.args.get('studs_x', type=int)
        studs_y = request.args.get('studs_y', type=int)
        height_units = request.args.get('height_units', 1.0, type=float)
        include_clearance = request.args.get('include_clearance', 'false') == 'true'

        if not studs_x or not studs_y:
            return jsonify({'error': 'studs_x and studs_y required'}), 400

        if include_clearance:
            width, depth, height = brick_dimensions_with_clearance(studs_x, studs_y, height_units)
        else:
            width, depth, height = brick_dimensions(studs_x, studs_y, height_units)

        volume = calculate_volume(studs_x, studs_y, height_units, hollow=True)
        weight_abs = calculate_weight(volume, 'abs')
        weight_pla = calculate_weight(volume, 'pla')

        return jsonify({
            'studs_x': studs_x,
            'studs_y': studs_y,
            'height_units': height_units,
            'dimensions_mm': {
                'width': round(width, 3),
                'depth': round(depth, 3),
                'height': round(height, 3),
            },
            'stud_count': studs_x * studs_y,
            'tube_count': max(0, (studs_x - 1) * (studs_y - 1)),
            'stud_positions': stud_positions(studs_x, studs_y)[:4],  # First 4 for preview
            'tube_positions': tube_positions(studs_x, studs_y)[:4],
            'volume_mm3': round(volume, 2),
            'weight_g': {
                'abs': round(weight_abs, 3),
                'pla': round(weight_pla, 3),
            },
            'stud_pitch': LEGO.STUD_PITCH,
        })

    except Exception as e:
        logger.error(f"Dimension calculation error: {e}")
        return jsonify({'error': str(e)}), 500


@lego_api_bp.route('/design', methods=['POST'])
@jwt_required()
def design_custom_brick():
    """
    Design a custom brick.

    JSON body:
    - name: Brick name (required)
    - studs_x: Studs in X (required)
    - studs_y: Studs in Y (required)
    - height_units: Height in brick units (default: 1.0)
    - brick_type: Type (standard, plate, tile, slope, technic)
    - hollow: Whether brick is hollow (default: true)
    - slope_angle: Slope angle if type is slope
    - has_holes: Add technic holes if type is technic
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name')
    studs_x = data.get('studs_x')
    studs_y = data.get('studs_y')

    if not all([name, studs_x, studs_y]):
        return jsonify({'error': 'name, studs_x, and studs_y required'}), 400

    try:
        from services.lego.lego_specs import (
            brick_dimensions, calculate_volume, calculate_weight,
            BRICK_TYPES, MANUFACTURING_TOLERANCES
        )

        height_units = data.get('height_units', 1.0)
        brick_type = data.get('brick_type', 'standard')
        hollow = data.get('hollow', True)

        type_config = BRICK_TYPES.get(brick_type, BRICK_TYPES['standard'])
        if 'height_units' in type_config and not data.get('height_units'):
            height_units = type_config['height_units']

        width, depth, height = brick_dimensions(studs_x, studs_y, height_units)
        volume = calculate_volume(studs_x, studs_y, height_units, hollow=hollow)

        design = {
            'brick_id': f"custom_{name.lower().replace(' ', '_')}",
            'name': name,
            'studs_x': studs_x,
            'studs_y': studs_y,
            'height_units': height_units,
            'brick_type': brick_type,
            'hollow': hollow,
            'has_studs': type_config.get('has_studs', True),
            'dimensions_mm': {
                'width': round(width, 3),
                'depth': round(depth, 3),
                'height': round(height, 3),
            },
            'volume_mm3': round(volume, 2),
            'estimated_weights_g': {
                'abs': round(calculate_weight(volume, 'abs'), 3),
                'pla': round(calculate_weight(volume, 'pla'), 3),
                'petg': round(calculate_weight(volume, 'petg'), 3),
            },
            'manufacturing': {
                'recommended_process': 'fdm_fine' if studs_x * studs_y <= 8 else 'fdm_standard',
                'tolerances': MANUFACTURING_TOLERANCES.get('fdm_fine', {}),
            },
        }

        if brick_type == 'slope':
            design['slope_angle'] = data.get('slope_angle', 45.0)

        if brick_type == 'technic':
            design['has_holes'] = True
            design['hole_count'] = max(studs_x, studs_y)

        return jsonify(design), 201

    except Exception as e:
        logger.error(f"Design error: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Specifications & Standards
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/specs', methods=['GET'])
@jwt_required()
def get_lego_specs():
    """Get LEGO dimension specifications."""
    try:
        from services.lego.lego_specs import LEGO, MATERIAL_PROPERTIES, MANUFACTURING_TOLERANCES

        return jsonify({
            'fundamental_units': {
                'ldu': LEGO.LDU,
                'stud_pitch': LEGO.STUD_PITCH,
            },
            'stud': {
                'diameter': LEGO.STUD_DIAMETER,
                'height': LEGO.STUD_HEIGHT,
                'inner_diameter': LEGO.STUD_INNER_DIAMETER,
            },
            'heights': {
                'brick': LEGO.BRICK_HEIGHT,
                'plate': LEGO.PLATE_HEIGHT,
                'tile': LEGO.TILE_HEIGHT,
            },
            'wall': {
                'thickness': LEGO.WALL_THICKNESS,
                'top_thickness': LEGO.TOP_THICKNESS,
            },
            'clearance': {
                'per_side': LEGO.CLEARANCE_PER_SIDE,
                'inter_brick': LEGO.INTER_BRICK_GAP,
            },
            'tubes': {
                'outer_diameter': LEGO.TUBE_OUTER_DIAMETER,
                'inner_diameter': LEGO.TUBE_INNER_DIAMETER,
            },
            'technic': {
                'pin_hole_diameter': LEGO.TECHNIC_PIN_HOLE_DIAMETER,
                'axle_hole_size': LEGO.TECHNIC_AXLE_HOLE_SIZE,
                'hole_spacing': LEGO.TECHNIC_HOLE_SPACING,
            },
            'slope_angles': [18, 33, 45, 65, 75],
        })

    except Exception as e:
        logger.warning(f"Specs error: {e}")
        return _demo_specs()


@lego_api_bp.route('/specs/materials', methods=['GET'])
@jwt_required()
def get_materials():
    """Get material properties."""
    try:
        from services.lego.lego_specs import MATERIAL_PROPERTIES
        return jsonify({
            'materials': MATERIAL_PROPERTIES,
            'recommended': 'pla',
        })
    except Exception as e:
        logger.warning(f'Exception in lego_api.py: {e}')
        return jsonify({
            'materials': {
                'pla': {'density': 1.24, 'melt_temp': 215, 'bed_temp': 60},
                'abs': {'density': 1.05, 'melt_temp': 232, 'bed_temp': 100},
                'petg': {'density': 1.27, 'melt_temp': 240, 'bed_temp': 85},
            },
            'recommended': 'pla',
        })


@lego_api_bp.route('/specs/tolerances', methods=['GET'])
@jwt_required()
def get_tolerances():
    """Get manufacturing tolerances."""
    try:
        from services.lego.lego_specs import MANUFACTURING_TOLERANCES
        return jsonify({
            'processes': MANUFACTURING_TOLERANCES,
            'recommended': 'fdm_fine',
        })
    except Exception as e:
        logger.warning(f'Exception in lego_api.py: {e}')
        return jsonify({
            'processes': {
                'fdm_standard': {'general': 0.15, 'stud': 0.20},
                'fdm_fine': {'general': 0.10, 'stud': 0.15},
                'sla_resin': {'general': 0.05, 'stud': 0.08},
            },
            'recommended': 'fdm_fine',
        })


# ─────────────────────────────────────────────────────────────────────────────
# Slicing Integration
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/slice', methods=['POST'])
@jwt_required()
def slice_brick():
    """
    Generate G-code for a brick design.

    JSON body:
    - brick_id: Brick ID from catalog or custom design
    - material: pla, abs, petg (default: pla)
    - quality: draft, standard, quality (default: quality)
    - model_file: Path to STL file (optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    brick_id = data.get('brick_id')
    material = data.get('material', 'pla')
    quality = data.get('quality', 'quality')

    try:
        from services.lego.slicer_client import get_slicer_client

        client = get_slicer_client()
        if not client:
            return jsonify({
                'error': 'Slicer service not available',
                'suggestion': 'Start slicer service with: docker-compose up -d slicer'
            }), 503

        # Get profile based on material/quality
        profile = f"lego_{material}_{quality}"

        # If custom design, we would generate STL first
        # For now, return job status
        return jsonify({
            'status': 'queued',
            'brick_id': brick_id,
            'profile': profile,
            'material': material,
            'quality': quality,
            'message': 'Slicing job submitted',
        })

    except Exception as e:
        logger.error(f"Slice error: {e}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Export Jobs (for manufacturing)
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/exports', methods=['GET'])
@jwt_required()
def list_exports():
    """List export jobs."""
    # Demo data - would connect to export job database
    return jsonify({
        'exports': [
            {
                'export_id': 'EXP-001',
                'brick_id': 'brick_2x4',
                'format': 'gcode',
                'status': 'completed',
                'created_at': '2024-01-18T10:00:00Z',
            },
            {
                'export_id': 'EXP-002',
                'brick_id': 'custom_gear_24t',
                'format': 'stl',
                'status': 'processing',
                'created_at': '2024-01-18T11:30:00Z',
            },
        ],
        'count': 2,
    })


@lego_api_bp.route('/exports', methods=['POST'])
@jwt_required()
def create_export():
    """
    Create an export job.

    JSON body:
    - brick_id: Brick ID to export (required)
    - format: stl, step, gcode (default: stl)
    - options: Format-specific options
    """
    data = request.get_json()
    if not data or 'brick_id' not in data:
        return jsonify({'error': 'brick_id required'}), 400

    brick_id = data['brick_id']
    export_format = data.get('format', 'stl')

    # Would create actual export job
    import uuid
    export_id = f"EXP-{uuid.uuid4().hex[:6].upper()}"

    return jsonify({
        'export_id': export_id,
        'brick_id': brick_id,
        'format': export_format,
        'status': 'queued',
        'message': 'Export job created',
    }), 201


@lego_api_bp.route('/exports/<export_id>', methods=['GET'])
@jwt_required()
def get_export(export_id: str):
    """Get export job status."""
    # Demo response
    return jsonify({
        'export_id': export_id,
        'brick_id': 'brick_2x4',
        'format': 'gcode',
        'status': 'completed',
        'output_file': f'/exports/{export_id}.gcode',
        'file_size_bytes': 125000,
        'print_time_minutes': 45,
        'material_grams': 8.5,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Common Brick Presets
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/presets', methods=['GET'])
@jwt_required()
def get_presets():
    """Get common brick presets."""
    try:
        from services.lego.lego_specs import COMMON_BRICKS

        return jsonify({
            'presets': COMMON_BRICKS,
            'count': len(COMMON_BRICKS),
        })

    except Exception as e:
        logger.warning(f'Exception in lego_api.py: {e}')
        return jsonify({
            'presets': [
                {'name': '1x1', 'studs_x': 1, 'studs_y': 1},
                {'name': '2x2', 'studs_x': 2, 'studs_y': 2},
                {'name': '2x4', 'studs_x': 2, 'studs_y': 4},
                {'name': '4x4', 'studs_x': 4, 'studs_y': 4},
            ],
            'count': 4,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Additional Convenience Endpoints
# ─────────────────────────────────────────────────────────────────────────────

# In-memory storage for designs
_design_storage = {}


@lego_api_bp.route('/dimensions/<brick_spec>', methods=['GET'])
@jwt_required()
def get_dimensions_by_spec(brick_spec: str):
    """
    Get dimensions for a brick specification like "2x4".

    Examples: /dimensions/2x4, /dimensions/1x1, /dimensions/4x6
    """
    try:
        # Parse brick spec (e.g., "2x4" -> studs_x=2, studs_y=4)
        parts = brick_spec.lower().replace('x', ' ').split()
        if len(parts) != 2:
            return jsonify({'error': f'Invalid brick spec: {brick_spec}. Use format like 2x4'}), 400

        studs_x = int(parts[0])
        studs_y = int(parts[1])

        # LEGO standard dimensions
        STUD_PITCH = 8.0  # mm
        BRICK_HEIGHT = 9.6  # mm
        PLATE_HEIGHT = 3.2  # mm

        width = studs_x * STUD_PITCH
        depth = studs_y * STUD_PITCH
        brick_height = BRICK_HEIGHT
        plate_height = PLATE_HEIGHT

        return jsonify({
            'spec': brick_spec,
            'studs_x': studs_x,
            'studs_y': studs_y,
            'stud_count': studs_x * studs_y,
            'dimensions_mm': {
                'width': width,
                'depth': depth,
                'brick_height': brick_height,
                'plate_height': plate_height,
            },
            'volume_mm3': {
                'brick': round(width * depth * brick_height * 0.3, 2),  # ~30% fill
                'plate': round(width * depth * plate_height * 0.3, 2),
            },
            'weight_g': {
                'brick_pla': round(width * depth * brick_height * 0.3 * 0.00124, 3),
                'plate_pla': round(width * depth * plate_height * 0.3 * 0.00124, 3),
            },
        })
    except ValueError:
        return jsonify({'error': f'Invalid brick spec: {brick_spec}. Use format like 2x4'}), 400


@lego_api_bp.route('/colors', methods=['GET'])
@jwt_required()
def get_colors():
    """Get available LEGO colors."""
    return jsonify({
        'colors': [
            {'id': 'red', 'name': 'Red', 'hex': '#C91A09', 'rgb': [201, 26, 9]},
            {'id': 'blue', 'name': 'Blue', 'hex': '#0055BF', 'rgb': [0, 85, 191]},
            {'id': 'yellow', 'name': 'Yellow', 'hex': '#F2CD37', 'rgb': [242, 205, 55]},
            {'id': 'green', 'name': 'Green', 'hex': '#237841', 'rgb': [35, 120, 65]},
            {'id': 'black', 'name': 'Black', 'hex': '#05131D', 'rgb': [5, 19, 29]},
            {'id': 'white', 'name': 'White', 'hex': '#FFFFFF', 'rgb': [255, 255, 255]},
            {'id': 'orange', 'name': 'Orange', 'hex': '#FE8A18', 'rgb': [254, 138, 24]},
            {'id': 'dark_gray', 'name': 'Dark Bluish Gray', 'hex': '#6C6E68', 'rgb': [108, 110, 104]},
            {'id': 'light_gray', 'name': 'Light Bluish Gray', 'hex': '#A0A5A9', 'rgb': [160, 165, 169]},
            {'id': 'brown', 'name': 'Reddish Brown', 'hex': '#582A12', 'rgb': [88, 42, 18]},
            {'id': 'tan', 'name': 'Tan', 'hex': '#E4CD9E', 'rgb': [228, 205, 158]},
            {'id': 'lime', 'name': 'Lime', 'hex': '#BBE90B', 'rgb': [187, 233, 11]},
            {'id': 'dark_blue', 'name': 'Dark Blue', 'hex': '#0A3463', 'rgb': [10, 52, 99]},
            {'id': 'dark_red', 'name': 'Dark Red', 'hex': '#720E0F', 'rgb': [114, 14, 15]},
            {'id': 'bright_pink', 'name': 'Bright Pink', 'hex': '#E4ADC8', 'rgb': [228, 173, 200]},
        ],
        'count': 15,
        'note': 'Official LEGO color palette subset',
    })


@lego_api_bp.route('/designs', methods=['GET'])
@jwt_required()
def list_designs():
    """List all custom brick designs."""
    designs = list(_design_storage.values())
    return jsonify({
        'designs': designs,
        'count': len(designs),
    })


@lego_api_bp.route('/designs/<design_id>', methods=['GET'])
@jwt_required()
def get_design(design_id: str):
    """Get a specific design."""
    design = _design_storage.get(design_id)
    if not design:
        return jsonify({'error': 'Design not found'}), 404
    return jsonify(design)


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_catalog():
    """Return demo catalog."""
    return jsonify({
        'bricks': [
            {
                'id': 'brick_2x4',
                'name': 'Brick 2x4',
                'category': 'basic',
                'studs_x': 2,
                'studs_y': 4,
                'height_units': 1.0,
                'tags': ['basic', 'brick', '2x4'],
            },
            {
                'id': 'plate_2x2',
                'name': 'Plate 2x2',
                'category': 'plate',
                'studs_x': 2,
                'studs_y': 2,
                'height_units': 0.333,
                'tags': ['plate', '2x2'],
            },
            {
                'id': 'tile_1x2',
                'name': 'Tile 1x2',
                'category': 'tile',
                'studs_x': 1,
                'studs_y': 2,
                'height_units': 0.333,
                'tags': ['tile', '1x2'],
            },
            {
                'id': 'slope_45_2x2',
                'name': 'Slope 45 2x2',
                'category': 'slope',
                'studs_x': 2,
                'studs_y': 2,
                'height_units': 1.0,
                'tags': ['slope', '45deg', '2x2'],
            },
        ],
        'count': 4,
        'filters': {},
    })


def _demo_specs():
    """Return demo specs."""
    return jsonify({
        'fundamental_units': {
            'ldu': 1.6,
            'stud_pitch': 8.0,
        },
        'stud': {
            'diameter': 4.8,
            'height': 1.7,
        },
        'heights': {
            'brick': 9.6,
            'plate': 3.2,
            'tile': 3.2,
        },
        'wall': {
            'thickness': 1.6,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Parts Catalog API (SKU-based manufacturing catalog)
# ─────────────────────────────────────────────────────────────────────────────

@lego_api_bp.route('/parts-catalog', methods=['GET'])
@jwt_required(optional=True)
def get_parts_catalog():
    """
    Get the LEGO parts master catalog.

    Query params:
    - category: Filter by category (brick, plate, tile, slope_45, etc.)
    - search: Search in part names
    - limit: Max results (default 100)
    """
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoPart, PartCategory

        category_str = request.args.get('category')
        search = request.args.get('search')
        limit = request.args.get('limit', 100, type=int)

        with get_db_session() as session:
            query = session.query(LegoPart).filter(LegoPart.is_active == True)

            if category_str:
                try:
                    category = PartCategory(category_str)
                    query = query.filter(LegoPart.category == category)
                except ValueError:
                    pass

            if search:
                query = query.filter(LegoPart.name.ilike(f'%{search}%'))

            parts = query.limit(limit).all()

            return jsonify({
                'parts': [p.to_dict() for p in parts],
                'count': len(parts),
                'filters': {
                    'category': category_str,
                    'search': search,
                },
            })

    except Exception as e:
        logger.warning(f"Parts catalog error: {e}")
        return _demo_parts_catalog()


@lego_api_bp.route('/parts-catalog/<part_number>', methods=['GET'])
@jwt_required(optional=True)
def get_part_by_number(part_number: str):
    """Get a specific part by part number."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoPart

        with get_db_session() as session:
            part = session.query(LegoPart).filter_by(part_number=part_number).first()
            if not part:
                return jsonify({'error': 'Part not found'}), 404
            return jsonify(part.to_dict())

    except Exception as e:
        logger.warning(f"Get part error: {e}")
        return jsonify({'error': 'Part not found'}), 404


@lego_api_bp.route('/materials-catalog', methods=['GET'])
@jwt_required(optional=True)
def get_materials_catalog():
    """Get available manufacturing materials."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoMaterial

        with get_db_session() as session:
            materials = session.query(LegoMaterial).filter(LegoMaterial.is_active == True).all()
            return jsonify({
                'materials': [m.to_dict() for m in materials],
                'count': len(materials),
            })

    except Exception as e:
        logger.warning(f"Materials catalog error: {e}")
        return _demo_materials_catalog()


@lego_api_bp.route('/colors-catalog', methods=['GET'])
@jwt_required(optional=True)
def get_colors_catalog():
    """Get available colors for products."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoColor

        material = request.args.get('material')

        with get_db_session() as session:
            query = session.query(LegoColor).filter(LegoColor.is_active == True)
            colors = query.all()

            # Filter by material compatibility if specified
            if material:
                colors = [c for c in colors if material in (c.compatible_materials or [])]

            return jsonify({
                'colors': [c.to_dict() for c in colors],
                'count': len(colors),
            })

    except Exception as e:
        logger.warning(f"Colors catalog error: {e}")
        return _demo_colors_catalog()


@lego_api_bp.route('/products', methods=['GET'])
@jwt_required(optional=True)
def get_products():
    """
    Get manufactured products (SKUs).

    Query params:
    - part_number: Filter by part number
    - material: Filter by material code
    - color: Filter by color code
    - limit: Max results (default 100)
    """
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct

        part_number = request.args.get('part_number')
        material = request.args.get('material')
        color = request.args.get('color')
        limit = request.args.get('limit', 100, type=int)

        with get_db_session() as session:
            query = session.query(LegoProduct).filter(LegoProduct.is_active == True)

            if part_number:
                query = query.filter(LegoProduct.part_number == part_number)
            if material:
                query = query.filter(LegoProduct.material_code == material)
            if color:
                query = query.filter(LegoProduct.color_code == color)

            products = query.limit(limit).all()

            return jsonify({
                'products': [p.to_dict() for p in products],
                'count': len(products),
            })

    except Exception as e:
        logger.warning(f"Products error: {e}")
        return _demo_products()


@lego_api_bp.route('/products/<sku>', methods=['GET'])
@jwt_required(optional=True)
def get_product_by_sku(sku: str):
    """Get a product by SKU."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct

        with get_db_session() as session:
            product = session.query(LegoProduct).filter_by(sku=sku).first()
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            return jsonify(product.to_dict())

    except Exception as e:
        logger.warning(f"Get product error: {e}")
        return jsonify({'error': 'Product not found'}), 404


@lego_api_bp.route('/products', methods=['POST'])
@jwt_required(optional=True)
def create_product():
    """
    Create a new product (SKU).

    JSON body:
    - part_number: LEGO part number (required)
    - material_code: Material code (required)
    - color_code: Color code (required)
    - routing_id: Routing ID for manufacturing
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    part_number = data.get('part_number')
    material_code = data.get('material_code')
    color_code = data.get('color_code')

    if not all([part_number, material_code, color_code]):
        return jsonify({'error': 'part_number, material_code, and color_code required'}), 400

    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoPart, LegoMaterial

        with get_db_session() as session:
            # Check if product already exists
            sku = LegoProduct.generate_sku(part_number, material_code, color_code)
            existing = session.query(LegoProduct).filter_by(sku=sku).first()
            if existing:
                return jsonify({'error': f'Product {sku} already exists'}), 409

            # Create product
            product = LegoProduct(
                sku=sku,
                part_number=part_number,
                material_code=material_code,
                color_code=color_code,
                routing_id=data.get('routing_id'),
            )

            # Calculate weight if possible
            part = session.query(LegoPart).filter_by(part_number=part_number).first()
            material = session.query(LegoMaterial).filter_by(code=material_code).first()
            if part and material and part.volume_mm3:
                product.weight_grams = material.calculate_weight(part.volume_mm3)

            session.add(product)
            session.commit()

            return jsonify({
                'message': 'Product created',
                'product': product.to_dict(),
            }), 201

    except Exception as e:
        logger.error(f"Create product error: {e}")
        return jsonify({'error': str(e)}), 500


@lego_api_bp.route('/products/<sku>/bom', methods=['GET'])
@jwt_required(optional=True)
def get_product_bom(sku: str):
    """Get bill of materials for a product."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoProductBOM

        with get_db_session() as session:
            product = session.query(LegoProduct).filter_by(sku=sku).first()
            if not product:
                return jsonify({'error': 'Product not found'}), 404

            bom_items = session.query(LegoProductBOM).filter_by(product_sku=sku).order_by(LegoProductBOM.sequence).all()

            return jsonify({
                'product_sku': sku,
                'bom': [item.to_dict() for item in bom_items],
                'count': len(bom_items),
            })

    except Exception as e:
        logger.warning(f"Get BOM error: {e}")
        return jsonify({'product_sku': sku, 'bom': [], 'count': 0})


@lego_api_bp.route('/products/<sku>/bom/calculated', methods=['GET'])
@jwt_required(optional=True)
def get_calculated_bom(sku: str):
    """
    Calculate BOM from part specifications without storing.

    Returns calculated material requirements based on:
    - Part volume and material density
    - Support material needs (based on geometry)
    - Packaging materials
    """
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoPart, LegoMaterial, PartCategory, ProcessType

        with get_db_session() as session:
            product = session.query(LegoProduct).filter_by(sku=sku).first()
            if not product:
                return jsonify({'error': 'Product not found'}), 404

            part = session.query(LegoPart).filter_by(part_number=product.part_number).first()
            material = session.query(LegoMaterial).filter_by(code=product.material_code).first()

            if not part or not material:
                return jsonify({'error': 'Part or material not found'}), 404

            bom_items = []
            sequence = 10

            # Calculate weight if not set
            weight_grams = product.weight_grams
            if not weight_grams and part.volume_mm3:
                weight_grams = material.calculate_weight(part.volume_mm3)
            elif not weight_grams:
                # Estimate from dimensions
                estimated_volume = part.studs_length * part.studs_width * part.height_plates * 50
                weight_grams = material.density_g_cm3 * estimated_volume / 1000
                weight_grams = max(weight_grams, 0.5)

            # Waste factors by process
            waste_factor = 1.10 if material.process_type in (ProcessType.FDM, ProcessType.SLA) else 1.05

            # 1. Primary material
            bom_items.append({
                'material_sku': f"RAW-{material.code}",
                'material_name': f"{material.name} (Raw)",
                'quantity': round(weight_grams * waste_factor, 2),
                'unit': 'grams',
                'sequence': sequence,
                'notes': f"Primary material with {int((waste_factor-1)*100)}% waste allowance",
                'cost_estimate': round(float(material.cost_per_gram or 0) * weight_grams * waste_factor, 4) if material.cost_per_gram else None,
            })
            sequence += 10

            # 2. Support material (for FDM/SLA with certain part types)
            if material.process_type in (ProcessType.FDM, ProcessType.SLA):
                support_factors = {
                    PartCategory.SLOPE_45: 0.15,
                    PartCategory.SLOPE_33: 0.10,
                    PartCategory.SLOPE_INVERTED: 0.20,
                    PartCategory.WEDGE: 0.15,
                    PartCategory.SPECIAL: 0.20,
                    PartCategory.TECHNIC: 0.05,
                }
                support_factor = support_factors.get(part.category, 0.0)

                if getattr(part, 'is_inverted', False):
                    support_factor += 0.10
                if getattr(part, 'slope_angle', 0) and part.slope_angle > 40:
                    support_factor += 0.05

                if support_factor > 0:
                    support_weight = round(weight_grams * support_factor, 2)
                    if support_weight >= 0.1:
                        bom_items.append({
                            'material_sku': f"SUP-{material.code}",
                            'material_name': f"{material.code} Support Material",
                            'quantity': support_weight,
                            'unit': 'grams',
                            'sequence': sequence,
                            'notes': "Support material (removed during post-processing)",
                        })
                        sequence += 10

            # 3. Packaging
            is_large = (part.studs_length * part.studs_width >= 8) or (weight_grams > 10)
            bom_items.append({
                'material_sku': 'PKG-BAG-L' if is_large else 'PKG-BAG-S',
                'material_name': 'Large Poly Bag' if is_large else 'Small Poly Bag',
                'quantity': 1,
                'unit': 'each',
                'sequence': sequence,
                'notes': 'Protective packaging',
            })
            sequence += 10

            # 4. Label
            bom_items.append({
                'material_sku': 'PKG-LABEL',
                'material_name': 'Product Label',
                'quantity': 1,
                'unit': 'each',
                'sequence': sequence,
                'notes': f'SKU label: {sku}',
            })

            return jsonify({
                'product_sku': sku,
                'calculated_bom': bom_items,
                'count': len(bom_items),
                'source': 'calculated',
                'part_info': {
                    'part_number': part.part_number,
                    'name': part.name,
                    'category': part.category.value if part.category else None,
                    'volume_mm3': part.volume_mm3,
                    'weight_grams': round(weight_grams, 2),
                },
            })

    except Exception as e:
        logger.error(f"Calculate BOM error: {e}")
        return jsonify({'error': str(e)}), 500


@lego_api_bp.route('/products/<sku>/bom', methods=['PUT'])
@jwt_required(optional=True)
def update_product_bom(sku: str):
    """
    Update or replace BOM for a product.

    JSON body:
    - items: List of BOM items to set
      - material_sku: Material SKU (required)
      - material_name: Display name (required)
      - quantity: Amount (required)
      - unit: Unit of measure (default: 'each')
      - sequence: Order in BOM (default: auto-assigned)
      - notes: Optional notes
    - replace_all: If true, delete existing BOM first (default: false)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    items = data.get('items', [])
    replace_all = data.get('replace_all', False)

    if not items:
        return jsonify({'error': 'items array required'}), 400

    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoProduct, LegoProductBOM

        with get_db_session() as session:
            product = session.query(LegoProduct).filter_by(sku=sku).first()
            if not product:
                return jsonify({'error': 'Product not found'}), 404

            # Delete existing BOM if replace_all
            if replace_all:
                session.query(LegoProductBOM).filter_by(product_sku=sku).delete()

            # Add new BOM items
            added_count = 0
            sequence = 10

            for item in items:
                material_sku = item.get('material_sku')
                material_name = item.get('material_name')
                quantity = item.get('quantity')

                if not all([material_sku, material_name, quantity]):
                    continue

                bom_entry = LegoProductBOM(
                    product_sku=sku,
                    material_sku=material_sku,
                    material_name=material_name,
                    quantity=quantity,
                    unit=item.get('unit', 'each'),
                    sequence=item.get('sequence', sequence),
                    notes=item.get('notes'),
                )
                session.add(bom_entry)
                added_count += 1
                sequence += 10

            session.commit()

            # Return updated BOM
            bom_items = session.query(LegoProductBOM).filter_by(product_sku=sku).order_by(LegoProductBOM.sequence).all()

            return jsonify({
                'message': 'BOM updated',
                'product_sku': sku,
                'items_added': added_count,
                'bom': [item.to_dict() for item in bom_items],
                'count': len(bom_items),
            })

    except Exception as e:
        logger.error(f"Update BOM error: {e}")
        return jsonify({'error': str(e)}), 500


@lego_api_bp.route('/routings', methods=['GET'])
@jwt_required(optional=True)
def get_routings():
    """Get available manufacturing routings."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoRouting

        process_type = request.args.get('process_type')

        with get_db_session() as session:
            query = session.query(LegoRouting).filter(LegoRouting.is_active == True)

            if process_type:
                from models.lego.parts_catalog import ProcessType
                try:
                    pt = ProcessType(process_type)
                    query = query.filter(LegoRouting.process_type == pt)
                except ValueError:
                    pass

            routings = query.all()

            return jsonify({
                'routings': [r.to_dict() for r in routings],
                'count': len(routings),
            })

    except Exception as e:
        logger.warning(f"Routings error: {e}")
        return _demo_routings()


@lego_api_bp.route('/routings/<routing_id>', methods=['GET'])
@jwt_required(optional=True)
def get_routing_by_id(routing_id: str):
    """Get a routing with its operations."""
    try:
        from config.database import get_db_session
        from models.lego.parts_catalog import LegoRouting

        with get_db_session() as session:
            routing = session.query(LegoRouting).filter_by(routing_id=routing_id).first()
            if not routing:
                return jsonify({'error': 'Routing not found'}), 404
            return jsonify(routing.to_dict())

    except Exception as e:
        logger.warning(f"Get routing error: {e}")
        return jsonify({'error': 'Routing not found'}), 404


# ─────────────────────────────────────────────────────────────────────────────
# Parts Catalog Demo Data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_parts_catalog():
    """Return demo parts catalog."""
    return jsonify({
        'parts': [
            {'part_number': '3001', 'name': 'Brick 2x4', 'category': 'brick', 'studs': {'length': 4, 'width': 2, 'count': 8}, 'height_plates': 3},
            {'part_number': '3020', 'name': 'Plate 2x4', 'category': 'plate', 'studs': {'length': 4, 'width': 2, 'count': 8}, 'height_plates': 1},
            {'part_number': '3068', 'name': 'Tile 2x2', 'category': 'tile', 'studs': {'length': 2, 'width': 2, 'count': 0}, 'height_plates': 1},
            {'part_number': '3040', 'name': 'Slope 45° 1x2', 'category': 'slope_45', 'studs': {'length': 2, 'width': 1, 'count': 2}, 'height_plates': 3},
            {'part_number': '3700', 'name': 'Technic Brick 1x2', 'category': 'technic', 'studs': {'length': 2, 'width': 1, 'count': 2}, 'height_plates': 3},
        ],
        'count': 5,
        'filters': {},
        'demo': True,
    })


def _demo_materials_catalog():
    """Return demo materials catalog."""
    return jsonify({
        'materials': [
            {'code': 'ABS', 'name': 'ABS Plastic', 'process_type': 'fdm', 'density_g_cm3': 1.04},
            {'code': 'PLA', 'name': 'PLA Plastic', 'process_type': 'fdm', 'density_g_cm3': 1.24},
            {'code': 'PETG', 'name': 'PETG Plastic', 'process_type': 'fdm', 'density_g_cm3': 1.27},
            {'code': 'ALU', 'name': '6061-T6 Aluminum', 'process_type': 'cnc_mill', 'density_g_cm3': 2.70},
            {'code': 'BRS', 'name': '360 Brass', 'process_type': 'cnc_mill', 'density_g_cm3': 8.50},
        ],
        'count': 5,
        'demo': True,
    })


def _demo_colors_catalog():
    """Return demo colors catalog."""
    return jsonify({
        'colors': [
            {'code': 'RED', 'name': 'Bright Red', 'hex_code': '#C4281B', 'compatible_materials': ['ABS', 'PLA', 'PETG']},
            {'code': 'BLU', 'name': 'Bright Blue', 'hex_code': '#0055BF', 'compatible_materials': ['ABS', 'PLA', 'PETG']},
            {'code': 'YEL', 'name': 'Bright Yellow', 'hex_code': '#F2CD37', 'compatible_materials': ['ABS', 'PLA', 'PETG']},
            {'code': 'BLK', 'name': 'Black', 'hex_code': '#1B2A34', 'compatible_materials': ['ABS', 'PLA', 'PETG']},
            {'code': 'WHT', 'name': 'White', 'hex_code': '#FFFFFF', 'compatible_materials': ['ABS', 'PLA', 'PETG']},
            {'code': 'RAW', 'name': 'Raw/Unfinished', 'is_metal_finish': True, 'compatible_materials': ['ALU', 'BRS', 'SST']},
        ],
        'count': 6,
        'demo': True,
    })


def _demo_products():
    """Return demo products."""
    return jsonify({
        'products': [
            {'sku': '3001-ABS-RED', 'part_number': '3001', 'material_code': 'ABS', 'color_code': 'RED', 'part_name': 'Brick 2x4', 'weight_grams': 2.3},
            {'sku': '3001-ABS-BLU', 'part_number': '3001', 'material_code': 'ABS', 'color_code': 'BLU', 'part_name': 'Brick 2x4', 'weight_grams': 2.3},
            {'sku': '3001-ALU-RAW', 'part_number': '3001', 'material_code': 'ALU', 'color_code': 'RAW', 'part_name': 'Brick 2x4', 'weight_grams': 6.0},
            {'sku': '3020-ABS-RED', 'part_number': '3020', 'material_code': 'ABS', 'color_code': 'RED', 'part_name': 'Plate 2x4', 'weight_grams': 0.8},
            {'sku': '3040-ABS-BLK', 'part_number': '3040', 'material_code': 'ABS', 'color_code': 'BLK', 'part_name': 'Slope 45° 1x2', 'weight_grams': 0.5},
        ],
        'count': 5,
        'demo': True,
    })


def _demo_routings():
    """Return demo routings."""
    return jsonify({
        'routings': [
            {
                'routing_id': 'FDM-STANDARD',
                'name': 'FDM 3D Print Standard',
                'process_type': 'fdm',
                'estimated_time_min': 45,
                'operations': [
                    {'sequence': 10, 'name': 'Slice Model', 'operation_type': 'setup', 'run_time_min': 2},
                    {'sequence': 20, 'name': '3D Print', 'operation_type': 'machining', 'setup_time_min': 5, 'run_time_min': 30},
                    {'sequence': 30, 'name': 'Remove Supports', 'operation_type': 'manual', 'run_time_min': 5},
                    {'sequence': 40, 'name': 'Quality Check', 'operation_type': 'qc', 'run_time_min': 3},
                ]
            },
            {
                'routing_id': 'CNC-STANDARD',
                'name': 'CNC Mill Standard',
                'process_type': 'cnc_mill',
                'estimated_time_min': 60,
                'operations': [
                    {'sequence': 10, 'name': 'CAM Setup', 'operation_type': 'setup', 'run_time_min': 10},
                    {'sequence': 20, 'name': 'Stock Prep', 'operation_type': 'manual', 'run_time_min': 5},
                    {'sequence': 30, 'name': 'CNC Roughing', 'operation_type': 'machining', 'setup_time_min': 10, 'run_time_min': 15},
                    {'sequence': 40, 'name': 'CNC Finishing', 'operation_type': 'machining', 'setup_time_min': 2, 'run_time_min': 10},
                    {'sequence': 50, 'name': 'Deburr', 'operation_type': 'manual', 'run_time_min': 5},
                    {'sequence': 60, 'name': 'Quality Check', 'operation_type': 'qc', 'run_time_min': 3},
                ]
            },
        ],
        'count': 2,
        'demo': True,
    })
