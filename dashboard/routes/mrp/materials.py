"""
Material Master Routes - 3D Printing Material Inventory API.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 7: Material Master / Inventory Control

Provides API endpoints for:
- Filament spool CRUD operations
- Material consumption tracking
- Inventory analytics and reporting
- Reorder recommendations
- LEGO-specific material guidance
"""

from flask import Blueprint, jsonify, request, render_template
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

materials_bp = Blueprint('materials', __name__, url_prefix='/materials')


# === Dashboard Page Routes ===

@materials_bp.route('', methods=['GET'])
@materials_bp.route('/page', methods=['GET'])
@materials_bp.route('/dashboard', methods=['GET'])
def materials_dashboard():
    """Render Material Master dashboard page."""
    return render_template('pages/mrp/material_master.html')


# === Spool CRUD API ===

@materials_bp.route('/spools', methods=['GET'])
def list_spools():
    """
    List all filament spools with optional filtering.

    Query params:
    - material_type: Filter by material type (pla, petg, abs, etc.)
    - status: Filter by status (available, in_use, low_stock, empty)
    - color: Filter by color
    - brand: Filter by brand
    """
    try:
        from services.inventory.material_master import get_material_master, MaterialType, MaterialStatus

        mm = get_material_master()

        # Parse filters
        material_type = None
        if request.args.get('material_type'):
            try:
                material_type = MaterialType(request.args.get('material_type'))
            except ValueError:
                pass

        status = None
        if request.args.get('status'):
            try:
                status = MaterialStatus(request.args.get('status'))
            except ValueError:
                pass

        color = request.args.get('color')
        brand = request.args.get('brand')

        spools = mm.get_all_spools(
            material_type=material_type,
            status=status,
            color=color,
            brand=brand
        )

        return jsonify({
            "success": True,
            "spools": [s.to_dict() for s in spools],
            "total": len(spools)
        })
    except Exception as e:
        logger.error(f"Failed to list spools: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools', methods=['POST'])
def add_spool():
    """
    Add a new filament spool to inventory.

    Request body:
    {
        "material_type": "pla",
        "brand": "Polymaker",
        "color": "Red",
        "color_code": "#FF0000",
        "initial_weight_g": 1000,
        "diameter_mm": 1.75,
        "lot_number": "LOT2024-001",
        "supplier": "Amazon",
        "unit_cost": 25.00
    }
    """
    try:
        from services.inventory.material_master import get_material_master, MaterialType

        mm = get_material_master()
        data = request.get_json()

        # Validate material type
        try:
            material_type = MaterialType(data.get('material_type', 'pla'))
        except ValueError:
            return jsonify({"success": False, "error": "Invalid material type"}), 400

        spool = mm.add_spool(
            material_type=material_type,
            brand=data.get('brand', 'Unknown'),
            color=data.get('color', 'Unknown'),
            color_code=data.get('color_code', '#000000'),
            initial_weight_g=data.get('initial_weight_g', 1000),
            diameter_mm=data.get('diameter_mm', 1.75),
            lot_number=data.get('lot_number', ''),
            supplier=data.get('supplier', ''),
            unit_cost=data.get('unit_cost', 0.0)
        )

        return jsonify({
            "success": True,
            "spool": spool.to_dict(),
            "message": f"Added spool {spool.id}: {spool.brand} {spool.color}"
        })
    except Exception as e:
        logger.error(f"Failed to add spool: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools/<spool_id>', methods=['GET'])
def get_spool(spool_id: str):
    """Get spool details by ID."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        spool = mm.get_spool(spool_id)

        if not spool:
            return jsonify({"success": False, "error": "Spool not found"}), 404

        # Get transaction history for this spool
        transactions = mm.get_transactions(spool_id=spool_id, limit=20)

        return jsonify({
            "success": True,
            "spool": spool.to_dict(),
            "transactions": [t.to_dict() for t in transactions]
        })
    except Exception as e:
        logger.error(f"Failed to get spool: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools/<spool_id>', methods=['PUT'])
def update_spool(spool_id: str):
    """Update spool properties."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        data = request.get_json()

        spool = mm.update_spool(spool_id, **data)

        if not spool:
            return jsonify({"success": False, "error": "Spool not found"}), 404

        return jsonify({
            "success": True,
            "spool": spool.to_dict()
        })
    except Exception as e:
        logger.error(f"Failed to update spool: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools/<spool_id>', methods=['DELETE'])
def delete_spool(spool_id: str):
    """Delete a spool from inventory."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        success = mm.delete_spool(spool_id)

        if not success:
            return jsonify({"success": False, "error": "Spool not found"}), 404

        return jsonify({
            "success": True,
            "message": f"Deleted spool {spool_id}"
        })
    except Exception as e:
        logger.error(f"Failed to delete spool: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === Material Consumption ===

@materials_bp.route('/spools/<spool_id>/consume', methods=['POST'])
def consume_material(spool_id: str):
    """
    Record material consumption from a spool.

    Request body:
    {
        "weight_g": 50.0,
        "work_order_id": "WO-001",
        "print_job_id": "PJ-001",
        "printer_id": "PRINTER-01",
        "reason": "2x4 brick print"
    }
    """
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        data = request.get_json()

        weight_g = data.get('weight_g', 0)
        if weight_g <= 0:
            return jsonify({"success": False, "error": "Weight must be positive"}), 400

        transaction = mm.consume_material(
            spool_id=spool_id,
            weight_g=weight_g,
            work_order_id=data.get('work_order_id'),
            print_job_id=data.get('print_job_id'),
            printer_id=data.get('printer_id'),
            reason=data.get('reason', '')
        )

        if not transaction:
            return jsonify({
                "success": False,
                "error": "Failed to consume material (spool not found or insufficient)"
            }), 400

        # Get updated spool
        spool = mm.get_spool(spool_id)

        return jsonify({
            "success": True,
            "transaction": transaction.to_dict(),
            "spool": spool.to_dict() if spool else None
        })
    except Exception as e:
        logger.error(f"Failed to consume material: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools/<spool_id>/adjust', methods=['POST'])
def adjust_weight(spool_id: str):
    """
    Adjust spool weight (e.g., after weighing).

    Request body:
    {
        "new_weight_g": 750.0,
        "reason": "Physical weighing"
    }
    """
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        data = request.get_json()

        new_weight = data.get('new_weight_g', 0)
        if new_weight < 0:
            return jsonify({"success": False, "error": "Weight cannot be negative"}), 400

        transaction = mm.adjust_weight(
            spool_id=spool_id,
            new_weight_g=new_weight,
            reason=data.get('reason', 'Manual adjustment')
        )

        if not transaction:
            return jsonify({"success": False, "error": "Spool not found"}), 404

        spool = mm.get_spool(spool_id)

        return jsonify({
            "success": True,
            "transaction": transaction.to_dict(),
            "spool": spool.to_dict() if spool else None
        })
    except Exception as e:
        logger.error(f"Failed to adjust weight: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools/<spool_id>/load', methods=['POST'])
def load_spool(spool_id: str):
    """
    Mark spool as loaded in a printer.

    Request body:
    {
        "printer_id": "PRINTER-01"
    }
    """
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        data = request.get_json()

        printer_id = data.get('printer_id')
        if not printer_id:
            return jsonify({"success": False, "error": "printer_id required"}), 400

        success = mm.load_spool(spool_id, printer_id)

        if not success:
            return jsonify({"success": False, "error": "Spool not found"}), 404

        spool = mm.get_spool(spool_id)

        return jsonify({
            "success": True,
            "spool": spool.to_dict() if spool else None,
            "message": f"Loaded spool {spool_id} into {printer_id}"
        })
    except Exception as e:
        logger.error(f"Failed to load spool: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/spools/<spool_id>/unload', methods=['POST'])
def unload_spool(spool_id: str):
    """Mark spool as unloaded from printer."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        success = mm.unload_spool(spool_id)

        if not success:
            return jsonify({"success": False, "error": "Spool not found"}), 404

        spool = mm.get_spool(spool_id)

        return jsonify({
            "success": True,
            "spool": spool.to_dict() if spool else None,
            "message": f"Unloaded spool {spool_id}"
        })
    except Exception as e:
        logger.error(f"Failed to unload spool: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === Analytics & Reporting ===

@materials_bp.route('/summary', methods=['GET'])
def inventory_summary():
    """Get inventory summary statistics."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        summary = mm.get_inventory_summary()

        return jsonify({
            "success": True,
            "summary": summary
        })
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/consumption', methods=['GET'])
def consumption_report():
    """
    Get material consumption report.

    Query params:
    - days: Number of days to analyze (default 30)
    - material_type: Filter by material type
    """
    try:
        from services.inventory.material_master import get_material_master, MaterialType

        mm = get_material_master()

        days = request.args.get('days', 30, type=int)

        material_type = None
        if request.args.get('material_type'):
            try:
                material_type = MaterialType(request.args.get('material_type'))
            except ValueError:
                pass

        report = mm.get_consumption_report(days=days, material_type=material_type)

        return jsonify({
            "success": True,
            "report": report
        })
    except Exception as e:
        logger.error(f"Failed to get consumption report: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/reorder', methods=['GET'])
def reorder_recommendations():
    """Get materials that need reordering."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        recommendations = mm.get_reorder_recommendations()

        return jsonify({
            "success": True,
            "recommendations": recommendations
        })
    except Exception as e:
        logger.error(f"Failed to get reorder recommendations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === LEGO-Specific Endpoints ===

@materials_bp.route('/lego/recommendations', methods=['GET'])
def lego_material_recommendations():
    """
    Get recommended materials for LEGO brick printing.

    Query params:
    - outdoor_use: true/false
    - high_strength: true/false
    - flexible: true/false
    """
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()

        outdoor_use = request.args.get('outdoor_use', 'false').lower() == 'true'
        high_strength = request.args.get('high_strength', 'false').lower() == 'true'
        flexible = request.args.get('flexible', 'false').lower() == 'true'

        recommendations = mm.get_lego_recommended_materials(
            outdoor_use=outdoor_use,
            high_strength=high_strength,
            flexible=flexible
        )

        return jsonify({
            "success": True,
            "recommendations": recommendations
        })
    except Exception as e:
        logger.error(f"Failed to get LEGO recommendations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/lego/estimate', methods=['POST'])
def estimate_print_material():
    """
    Estimate material needed for a print.

    Request body:
    {
        "volume_mm3": 5000,
        "material_type": "petg",
        "infill_percent": 20,
        "waste_factor": 1.05
    }
    """
    try:
        from services.inventory.material_master import get_material_master, MaterialType

        mm = get_material_master()
        data = request.get_json()

        try:
            material_type = MaterialType(data.get('material_type', 'pla'))
        except ValueError:
            return jsonify({"success": False, "error": "Invalid material type"}), 400

        volume_mm3 = data.get('volume_mm3', 0)
        if volume_mm3 <= 0:
            return jsonify({"success": False, "error": "volume_mm3 must be positive"}), 400

        estimate = mm.estimate_print_material(
            volume_mm3=volume_mm3,
            material_type=material_type,
            infill_percent=data.get('infill_percent', 20),
            waste_factor=data.get('waste_factor', 1.05)
        )

        return jsonify({
            "success": True,
            "estimate": estimate
        })
    except Exception as e:
        logger.error(f"Failed to estimate material: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === Material Properties ===

@materials_bp.route('/properties', methods=['GET'])
def list_material_properties():
    """Get properties for all material types."""
    try:
        from services.inventory.material_master import MATERIAL_PROPERTIES

        properties = {
            k.value: v.to_dict() for k, v in MATERIAL_PROPERTIES.items()
        }

        return jsonify({
            "success": True,
            "properties": properties
        })
    except Exception as e:
        logger.error(f"Failed to get properties: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/properties/<material_type>', methods=['GET'])
def get_material_properties(material_type: str):
    """Get properties for a specific material type."""
    try:
        from services.inventory.material_master import get_material_master, MaterialType

        mm = get_material_master()

        try:
            mat_type = MaterialType(material_type)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid material type"}), 400

        props = mm.get_material_properties(mat_type)

        if not props:
            return jsonify({"success": False, "error": "Properties not found"}), 404

        return jsonify({
            "success": True,
            "properties": props.to_dict()
        })
    except Exception as e:
        logger.error(f"Failed to get properties: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === Alerts ===

@materials_bp.route('/alerts', methods=['GET'])
def list_alerts():
    """Get material alerts."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()

        include_acknowledged = request.args.get('include_acknowledged', 'false').lower() == 'true'
        alerts = mm.get_alerts(include_acknowledged=include_acknowledged)

        return jsonify({
            "success": True,
            "alerts": [a.to_dict() for a in alerts]
        })
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@materials_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()
        data = request.get_json() or {}

        success = mm.acknowledge_alert(
            alert_id=alert_id,
            acknowledged_by=data.get('acknowledged_by', 'user')
        )

        if not success:
            return jsonify({"success": False, "error": "Alert not found"}), 404

        return jsonify({
            "success": True,
            "message": f"Acknowledged alert {alert_id}"
        })
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# === Transactions ===

@materials_bp.route('/transactions', methods=['GET'])
def list_transactions():
    """
    Get material transaction history.

    Query params:
    - spool_id: Filter by spool
    - type: Filter by transaction type
    - limit: Max records (default 100)
    """
    try:
        from services.inventory.material_master import get_material_master

        mm = get_material_master()

        spool_id = request.args.get('spool_id')
        transaction_type = request.args.get('type')
        limit = request.args.get('limit', 100, type=int)

        transactions = mm.get_transactions(
            spool_id=spool_id,
            transaction_type=transaction_type,
            limit=limit
        )

        return jsonify({
            "success": True,
            "transactions": [t.to_dict() for t in transactions],
            "total": len(transactions)
        })
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
