"""
Builds Routes

Build planning, parts checking, and shopping lists.
"""

from flask import Blueprint, render_template, request, jsonify, Response

builds_bp = Blueprint("builds", __name__)


@builds_bp.route("/")
def builds_page():
    """Build planner page."""
    from services.builds import get_build_planner

    planner = get_build_planner()
    builds = planner.get_all_builds()

    # Get check results for each build
    build_data = []
    for build in builds:
        check = planner.check_build(build.id)
        build_data.append({"build": build.to_dict(), "check": check.to_dict() if check else None})

    # Sort by completion percentage
    build_data.sort(
        key=lambda x: x["check"]["completion_percent"] if x["check"] else 0, reverse=True
    )

    return render_template("pages/builds.html", builds=build_data)


@builds_bp.route("/<build_id>")
def build_detail(build_id):
    """Build detail page."""
    from services.builds import get_build_planner

    planner = get_build_planner()
    build = planner.get_build(build_id)

    if not build:
        return render_template("errors/404.html", message="Build not found"), 404

    check = planner.check_build(build_id)
    substitutes = planner.find_substitutes(check.missing) if check else {}
    shopping = planner.generate_shopping_list(build_id)

    return render_template(
        "pages/build_detail.html",
        build=build.to_dict(),
        check=check.to_dict() if check else None,
        substitutes=substitutes,
        shopping=shopping,
    )


@builds_bp.route("/create", methods=["POST"])
def create_build():
    """Create a new build."""
    from services.builds import get_build_planner

    data = request.get_json()

    planner = get_build_planner()
    build = planner.create_build(
        name=data.get("name", "New Build"),
        parts=data.get("parts", []),
        description=data.get("description", ""),
        image_url=data.get("image_url", ""),
    )

    return jsonify({"success": True, "build": build.to_dict()})


@builds_bp.route("/<build_id>/delete", methods=["POST"])
def delete_build(build_id):
    """Delete a build."""
    from services.builds import get_build_planner

    planner = get_build_planner()
    success = planner.delete_build(build_id)

    return jsonify({"success": success})


@builds_bp.route("/<build_id>/check")
def check_build(build_id):
    """Check build against inventory."""
    from services.builds import get_build_planner

    planner = get_build_planner()
    check = planner.check_build(build_id)

    if check:
        return jsonify(check.to_dict())
    else:
        return jsonify({"error": "Build not found"}), 404


@builds_bp.route("/<build_id>/substitutes")
def get_substitutes(build_id):
    """Get substitute suggestions for missing parts."""
    from services.builds import get_build_planner

    planner = get_build_planner()
    check = planner.check_build(build_id)

    if not check:
        return jsonify({"error": "Build not found"}), 404

    substitutes = planner.find_substitutes(check.missing)

    return jsonify({"build_id": build_id, "substitutes": substitutes})


@builds_bp.route("/<build_id>/shopping")
def shopping_list(build_id):
    """Get shopping list for missing parts."""
    from services.builds import get_build_planner

    planner = get_build_planner()
    shopping = planner.generate_shopping_list(build_id)

    return jsonify(shopping)


@builds_bp.route("/<build_id>/export")
def export_build(build_id):
    """Export build parts list."""
    from services.builds import get_build_planner

    format = request.args.get("format", "json")

    planner = get_build_planner()
    content = planner.export_build(build_id, format)

    if not content:
        return jsonify({"error": "Build not found"}), 404

    if format == "csv":
        return Response(
            content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=build_{build_id}.csv"},
        )
    else:
        return Response(
            content,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename=build_{build_id}.json"},
        )


@builds_bp.route("/import", methods=["POST"])
def import_build():
    """Import a build from file."""
    from services.builds import get_build_planner

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    format = request.form.get("format", "rebrickable")
    name = request.form.get("name")

    content = file.read().decode("utf-8")

    planner = get_build_planner()

    try:
        if format == "bricklink":
            build = planner.import_bricklink(content, name)
        else:
            build = planner.import_rebrickable(content, name)

        return jsonify({"success": True, "build": build.to_dict()})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@builds_bp.route("/suggest")
def suggest_builds():
    """Get build suggestions based on inventory."""
    from services.builds import get_build_planner

    max_missing = int(request.args.get("max_missing", 10))

    planner = get_build_planner()
    suggestions = planner.suggest_builds(max_missing)

    return jsonify({"suggestions": suggestions, "count": len(suggestions)})


@builds_bp.route("/add-from-catalog", methods=["POST"])
def add_from_catalog():
    """Create a simple build from catalog brick."""
    from services.builds import get_build_planner
    from services.catalog_service import CatalogService

    data = request.get_json()
    brick_id = data.get("brick_id")
    color = data.get("color", "unknown")
    quantity = data.get("quantity", 1)

    # Get brick info from catalog
    brick = CatalogService.get_brick(brick_id)

    if not brick:
        return jsonify({"error": "Brick not found in catalog"}), 404

    planner = get_build_planner()
    build = planner.create_build(
        name=f"Quick Build - {brick['name']}",
        parts=[
            {
                "brick_id": brick_id,
                "brick_name": brick["name"],
                "color": color,
                "quantity": quantity,
                "category": brick.get("category", "brick"),
            }
        ],
        description=f"Quick build using {quantity}x {brick['name']}",
    )

    return jsonify({"success": True, "build": build.to_dict()})
