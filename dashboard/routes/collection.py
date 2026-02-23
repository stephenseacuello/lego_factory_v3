"""
Collection Routes

Full inventory management for the LEGO collection.
"""

from flask import Blueprint, render_template, request, jsonify, Response
import json

collection_bp = Blueprint("collection", __name__)


@collection_bp.route("/")
def collection_page():
    """Main collection page."""
    from services.inventory import get_inventory_manager

    manager = get_inventory_manager()

    # Get query params
    category = request.args.get("category")
    color = request.args.get("color")
    search = request.args.get("q")
    sort_by = request.args.get("sort", "quantity")
    sort_order = request.args.get("order", "desc")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    # Get inventory
    offset = (page - 1) * per_page
    items = manager.get_inventory(
        category=category,
        color=color,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=per_page,
        offset=offset,
    )

    # Get all items for total count
    all_items = manager.get_inventory(category=category, color=color, search=search)
    total = len(all_items)
    total_pages = (total + per_page - 1) // per_page

    # Get stats
    stats = manager.get_statistics()

    # Get filter options
    categories = manager.get_all_categories()
    colors = manager.get_all_colors()

    return render_template(
        "pages/collection.html",
        items=[i.to_dict() for i in items],
        stats=stats.__dict__,
        categories=categories,
        colors=colors,
        current_category=category,
        current_color=color,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )


@collection_bp.route("/add", methods=["POST"])
def add_brick():
    """Add brick to collection."""
    from services.inventory import get_inventory_manager

    data = request.get_json()

    manager = get_inventory_manager()
    item = manager.add_brick(
        brick_id=data.get("brick_id"),
        quantity=data.get("quantity", 1),
        color=data.get("color", "unknown"),
        category=data.get("category", "brick"),
        brick_name=data.get("brick_name"),
        notes=data.get("notes", ""),
        source=data.get("source", "manual"),
    )

    return jsonify({"success": True, "item": item.to_dict()})


@collection_bp.route("/remove", methods=["POST"])
def remove_brick():
    """Remove brick from collection."""
    from services.inventory import get_inventory_manager

    data = request.get_json()

    manager = get_inventory_manager()
    success = manager.remove_brick(
        brick_id=data.get("brick_id"),
        color=data.get("color", "unknown"),
        quantity=data.get("quantity", 1),
    )

    return jsonify({"success": success})


@collection_bp.route("/update", methods=["POST"])
def update_quantity():
    """Update brick quantity."""
    from services.inventory import get_inventory_manager

    data = request.get_json()

    manager = get_inventory_manager()
    item = manager.update_quantity(
        brick_id=data.get("brick_id"), color=data.get("color"), quantity=data.get("quantity")
    )

    if item:
        return jsonify({"success": True, "item": item.to_dict()})
    else:
        return jsonify({"success": True, "deleted": True})


@collection_bp.route("/item/<brick_id>/<color>")
def get_item(brick_id, color):
    """Get a specific inventory item."""
    from services.inventory import get_inventory_manager

    manager = get_inventory_manager()
    item = manager.get_item(brick_id, color)

    if item:
        return jsonify(item.to_dict())
    else:
        return jsonify({"error": "Not found"}), 404


@collection_bp.route("/stats")
def get_stats():
    """Get collection statistics."""
    from services.inventory import get_inventory_manager

    manager = get_inventory_manager()
    stats = manager.get_statistics()

    return jsonify(stats.__dict__)


@collection_bp.route("/check-parts", methods=["POST"])
def check_parts():
    """Check if we have parts for a build."""
    from services.inventory import get_inventory_manager

    data = request.get_json()
    parts_list = data.get("parts", [])

    manager = get_inventory_manager()
    result = manager.check_parts(parts_list)

    return jsonify(result)


@collection_bp.route("/export")
def export_collection():
    """Export collection."""
    from services.inventory import get_inventory_manager

    format = request.args.get("format", "json")

    manager = get_inventory_manager()

    if format == "csv":
        filepath = manager.export_csv()
        with open(filepath, "r") as f:
            content = f.read()

        return Response(
            content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=lego_collection.csv"},
        )
    else:
        data = manager.export_json()

        return Response(
            json.dumps(data, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=lego_collection.json"},
        )


@collection_bp.route("/import", methods=["POST"])
def import_collection():
    """Import collection from file."""
    from services.inventory import get_inventory_manager

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    format = request.form.get("format", "csv")
    merge = request.form.get("merge", "true").lower() == "true"

    manager = get_inventory_manager()

    content = file.read().decode("utf-8")

    try:
        if format == "bricklink":
            count = manager.import_bricklink(content)
        elif format == "rebrickable":
            count = manager.import_rebrickable(content)
        else:
            # Save to temp file for CSV import
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
                f.write(content)
                temp_path = f.name

            count = manager.import_csv(temp_path, merge=merge)

            import os

            os.unlink(temp_path)

        return jsonify({"success": True, "imported": count, "message": f"Imported {count} items"})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@collection_bp.route("/clear", methods=["POST"])
def clear_collection():
    """Clear entire collection."""
    from services.inventory import get_inventory_manager

    # Require confirmation
    data = request.get_json()
    if not data.get("confirm"):
        return jsonify({"error": "Confirmation required"}), 400

    manager = get_inventory_manager()
    count = manager.clear_all()

    return jsonify({"success": True, "deleted": count, "message": f"Deleted {count} items"})


@collection_bp.route("/search")
def search_collection():
    """Search collection (for autocomplete)."""
    from services.inventory import get_inventory_manager

    query = request.args.get("q", "")
    limit = int(request.args.get("limit", 10))

    if len(query) < 2:
        return jsonify([])

    manager = get_inventory_manager()
    items = manager.get_inventory(search=query, limit=limit)

    return jsonify([i.to_dict() for i in items])


@collection_bp.route("/by-brick/<brick_id>")
def get_by_brick(brick_id):
    """Get all colors of a specific brick type."""
    from services.inventory import get_inventory_manager

    manager = get_inventory_manager()
    items = manager.get_by_brick_id(brick_id)

    return jsonify([i.to_dict() for i in items])


@collection_bp.route("/bulk-add", methods=["POST"])
def bulk_add():
    """Add multiple bricks at once."""
    from services.inventory import get_inventory_manager

    data = request.get_json()
    bricks = data.get("bricks", [])

    manager = get_inventory_manager()
    added = []

    for brick in bricks:
        item = manager.add_brick(
            brick_id=brick.get("brick_id"),
            quantity=brick.get("quantity", 1),
            color=brick.get("color", "unknown"),
            category=brick.get("category", "brick"),
            source="bulk",
        )
        added.append(item.to_dict())

    return jsonify({"success": True, "added": len(added), "items": added})
