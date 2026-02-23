"""
Catalog Routes

Brick catalog browsing and viewing.
"""

from flask import Blueprint, render_template, request, jsonify
from services.catalog_service import CatalogService

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.route("/")
def list_bricks():
    """Brick catalog list view."""
    # Get query params
    category = request.args.get("category")
    search_query = request.args.get("q", "")
    sort_by = request.args.get("sort", "name")
    sort_order = request.args.get("order", "asc")
    view = request.args.get("view", "grid")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 48))

    # Calculate offset
    offset = (page - 1) * per_page

    # Get bricks
    result = CatalogService.get_all_bricks(
        category=category,
        search_query=search_query if search_query else None,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=per_page,
        offset=offset,
    )

    # Get categories for sidebar
    categories = CatalogService.get_categories()

    # Calculate pagination
    total_pages = (result["total"] + per_page - 1) // per_page

    return render_template(
        "pages/catalog/list.html",
        bricks=result["bricks"],
        total=result["total"],
        categories=categories,
        current_category=category,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order,
        view=view,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        has_more=result["has_more"],
    )


@catalog_bp.route("/<brick_id>")
def brick_detail(brick_id):
    """Single brick detail view."""
    brick = CatalogService.get_brick(brick_id)

    if not brick:
        return render_template("errors/404.html", message=f'Brick "{brick_id}" not found'), 404

    # Get similar bricks
    similar = CatalogService.get_similar_bricks(brick_id, limit=6)

    return render_template("pages/catalog/detail.html", brick=brick, similar_bricks=similar)


@catalog_bp.route("/search")
def search():
    """Search bricks (for autocomplete)."""
    query = request.args.get("q", "")
    limit = int(request.args.get("limit", 10))

    if not query or len(query) < 2:
        return jsonify([])

    results = CatalogService.search_bricks(query, limit=limit)

    return jsonify(results)
