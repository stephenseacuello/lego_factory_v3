"""
Genealogy Tracking API Routes.

Provides REST API endpoints for component-to-assembly traceability,
parent-child relationships, and recall support.
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

genealogy_bp = Blueprint('genealogy', __name__, url_prefix='/api/genealogy')

# Lazy service initialization
_genealogy_service = None


def get_genealogy_service():
    """Get or create the genealogy service instance."""
    global _genealogy_service
    if _genealogy_service is None:
        from services.genealogy_service import GenealogyService
        _genealogy_service = GenealogyService()
    return _genealogy_service


# =============================================================================
# Component Management
# =============================================================================

@genealogy_bp.route('/components', methods=['GET'])
def list_components():
    """
    List all registered components.

    Query Parameters:
        component_type: Filter by type (raw_material, component, subassembly, assembly, finished_good)
        part_number: Filter by part number
        lot_number: Filter by lot number
        limit: Maximum results (default 100)
    """
    try:
        service = get_genealogy_service()

        component_type = request.args.get('component_type')
        part_number = request.args.get('part_number')
        lot_number = request.args.get('lot_number')
        limit = request.args.get('limit', 100, type=int)

        components = list(service.components.values())

        if component_type:
            from services.genealogy_service import ComponentType
            try:
                type_enum = ComponentType(component_type)
                components = [c for c in components if c.component_type == type_enum]
            except ValueError:
                pass

        if part_number:
            components = [c for c in components if c.part_number == part_number]

        if lot_number:
            components = [c for c in components if c.lot_number == lot_number]

        # Sort by registration date descending
        components.sort(key=lambda x: x.registration_date, reverse=True)

        # Apply limit
        components = components[:limit]

        return jsonify({
            'success': True,
            'components': [c.to_dict() for c in components],
            'count': len(components)
        })

    except Exception as e:
        logger.error(f"Error listing components: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/components', methods=['POST'])
def register_component():
    """
    Register a new component.

    Request Body:
        part_number: Part number (required)
        component_type: Type - raw_material, component, subassembly, assembly, finished_good (required)
        serial_number: Unique serial number (optional)
        lot_number: Lot/batch number (optional)
        quantity: Quantity (default 1)
        supplier_id: Supplier identifier (optional)
        work_order_id: Associated work order (optional)
        metadata: Additional component metadata (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('part_number') or not data.get('component_type'):
            return jsonify({
                'success': False,
                'error': 'part_number and component_type required'
            }), 400

        service = get_genealogy_service()

        from services.genealogy_service import ComponentType
        try:
            comp_type = ComponentType(data['component_type'])
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'Invalid component_type: {data["component_type"]}'
            }), 400

        component = service.register_component(
            part_number=data['part_number'],
            component_type=comp_type,
            serial_number=data.get('serial_number'),
            lot_number=data.get('lot_number'),
            quantity=data.get('quantity', 1),
            supplier_id=data.get('supplier_id'),
            work_order_id=data.get('work_order_id'),
            metadata=data.get('metadata')
        )

        return jsonify({
            'success': True,
            'component': component.to_dict()
        }), 201

    except Exception as e:
        logger.error(f"Error registering component: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/components/<component_id>', methods=['GET'])
def get_component(component_id: str):
    """Get a specific component by ID."""
    try:
        service = get_genealogy_service()
        component = service.components.get(component_id)

        if not component:
            return jsonify({
                'success': False,
                'error': 'Component not found'
            }), 404

        return jsonify({
            'success': True,
            'component': component.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting component: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/components/serial/<serial_number>', methods=['GET'])
def get_by_serial(serial_number: str):
    """Get component by serial number."""
    try:
        service = get_genealogy_service()
        component = service.get_by_serial(serial_number)

        if not component:
            return jsonify({
                'success': False,
                'error': 'Component not found'
            }), 404

        return jsonify({
            'success': True,
            'component': component.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting by serial: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Relationship Management
# =============================================================================

@genealogy_bp.route('/link', methods=['POST'])
def link_components():
    """
    Link parent and child components.

    Request Body:
        parent_id: Parent component ID (required)
        child_id: Child component ID (required)
        relationship_type: contains, assembled_from, derived_from, replaced_by (default contains)
        quantity_used: Quantity of child used (default 1)
        operation_id: Operation that created link (optional)
        operator_id: Operator who performed linking (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('parent_id') or not data.get('child_id'):
            return jsonify({
                'success': False,
                'error': 'parent_id and child_id required'
            }), 400

        service = get_genealogy_service()

        # Parse relationship type
        rel_type = None
        if data.get('relationship_type'):
            from services.genealogy_service import RelationshipType
            try:
                rel_type = RelationshipType(data['relationship_type'])
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': f'Invalid relationship_type: {data["relationship_type"]}'
                }), 400

        relation = service.link_components(
            parent_id=data['parent_id'],
            child_id=data['child_id'],
            relationship_type=rel_type,
            quantity_used=data.get('quantity_used', 1),
            operation_id=data.get('operation_id'),
            operator_id=data.get('operator_id')
        )

        if relation:
            return jsonify({
                'success': True,
                'relation': relation.to_dict()
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to link components - check component IDs'
            }), 400

    except Exception as e:
        logger.error(f"Error linking components: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/components/<component_id>/children', methods=['GET'])
def get_children(component_id: str):
    """
    Get child components.

    Query Parameters:
        recursive: Include all descendants (default false)
    """
    try:
        service = get_genealogy_service()

        recursive = request.args.get('recursive', 'false').lower() == 'true'

        children = service.get_children(component_id, recursive=recursive)

        return jsonify({
            'success': True,
            'children': children,
            'count': len(children)
        })

    except Exception as e:
        logger.error(f"Error getting children: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/components/<component_id>/parents', methods=['GET'])
def get_parents(component_id: str):
    """
    Get parent components.

    Query Parameters:
        recursive: Include all ancestors (default false)
    """
    try:
        service = get_genealogy_service()

        recursive = request.args.get('recursive', 'false').lower() == 'true'

        parents = service.get_parents(component_id, recursive=recursive)

        return jsonify({
            'success': True,
            'parents': parents,
            'count': len(parents)
        })

    except Exception as e:
        logger.error(f"Error getting parents: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/components/<component_id>/genealogy', methods=['GET'])
def get_full_genealogy(component_id: str):
    """Get complete genealogy tree for a component."""
    try:
        service = get_genealogy_service()

        genealogy = service.get_full_genealogy(component_id)

        if genealogy:
            return jsonify({
                'success': True,
                'genealogy': genealogy
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Component not found'
            }), 404

    except Exception as e:
        logger.error(f"Error getting genealogy: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Recall Support
# =============================================================================

@genealogy_bp.route('/recall/lot/<lot_number>', methods=['GET'])
def find_affected_by_lot(lot_number: str):
    """Find all components affected by a lot number (for recalls)."""
    try:
        service = get_genealogy_service()

        affected = service.find_affected_by_lot(lot_number)

        return jsonify({
            'success': True,
            'lot_number': lot_number,
            'affected': affected
        })

    except Exception as e:
        logger.error(f"Error finding affected by lot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/recall/supplier/<supplier_id>', methods=['GET'])
def find_affected_by_supplier(supplier_id: str):
    """Find all components from a specific supplier."""
    try:
        service = get_genealogy_service()

        affected = service.find_affected_by_supplier(supplier_id)

        return jsonify({
            'success': True,
            'supplier_id': supplier_id,
            'affected': affected
        })

    except Exception as e:
        logger.error(f"Error finding affected by supplier: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/recall/component/<component_id>', methods=['GET'])
def find_affected_by_component(component_id: str):
    """Find all assemblies containing a specific component."""
    try:
        service = get_genealogy_service()

        # Get all parent assemblies recursively
        parents = service.get_parents(component_id, recursive=True)

        component = service.components.get(component_id)

        return jsonify({
            'success': True,
            'source_component': component.to_dict() if component else None,
            'affected_assemblies': parents,
            'total_affected': len(parents)
        })

    except Exception as e:
        logger.error(f"Error finding affected by component: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# BOM Integration
# =============================================================================

@genealogy_bp.route('/bom/<part_number>', methods=['GET'])
def get_bom(part_number: str):
    """Get Bill of Materials for a part."""
    try:
        service = get_genealogy_service()

        bom = service.bom_definitions.get(part_number, [])

        return jsonify({
            'success': True,
            'part_number': part_number,
            'bom': [item.to_dict() for item in bom],
            'total_items': len(bom)
        })

    except Exception as e:
        logger.error(f"Error getting BOM: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@genealogy_bp.route('/bom', methods=['POST'])
def define_bom():
    """
    Define BOM for a part.

    Request Body:
        parent_part_number: Parent part number (required)
        items: List of BOM items (required)
            - child_part_number: Child part number
            - quantity: Quantity required
            - unit_of_measure: UOM (default EA)
            - position: Assembly position (optional)
    """
    try:
        data = request.get_json()

        if not data or not data.get('parent_part_number') or not data.get('items'):
            return jsonify({
                'success': False,
                'error': 'parent_part_number and items required'
            }), 400

        service = get_genealogy_service()

        from services.genealogy_service import BOMItem

        bom_items = []
        for item in data['items']:
            if not item.get('child_part_number') or not item.get('quantity'):
                continue

            bom_item = BOMItem(
                parent_part_number=data['parent_part_number'],
                child_part_number=item['child_part_number'],
                quantity=item['quantity'],
                unit_of_measure=item.get('unit_of_measure', 'EA'),
                position=item.get('position')
            )
            bom_items.append(bom_item)

        service.bom_definitions[data['parent_part_number']] = bom_items

        return jsonify({
            'success': True,
            'parent_part_number': data['parent_part_number'],
            'bom': [item.to_dict() for item in bom_items]
        }), 201

    except Exception as e:
        logger.error(f"Error defining BOM: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Analytics
# =============================================================================

@genealogy_bp.route('/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get genealogy analytics summary."""
    try:
        service = get_genealogy_service()

        from services.genealogy_service import ComponentType

        components = list(service.components.values())
        relations = list(service.relations.values())

        # Count by type
        by_type = {}
        for ct in ComponentType:
            by_type[ct.value] = len([c for c in components if c.component_type == ct])

        # Count by relationship type
        from services.genealogy_service import RelationshipType
        by_relationship = {}
        for rt in RelationshipType:
            by_relationship[rt.value] = len([r for r in relations if r.relationship_type == rt])

        # Unique lots and suppliers
        unique_lots = len(set(c.lot_number for c in components if c.lot_number))
        unique_suppliers = len(set(c.supplier_id for c in components if c.supplier_id))

        return jsonify({
            'success': True,
            'summary': {
                'total_components': len(components),
                'total_relations': len(relations),
                'by_type': by_type,
                'by_relationship': by_relationship,
                'unique_lots': unique_lots,
                'unique_suppliers': unique_suppliers,
                'bom_definitions': len(service.bom_definitions)
            }
        })

    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
