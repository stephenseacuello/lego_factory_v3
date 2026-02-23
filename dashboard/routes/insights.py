"""
Insights Routes

Analytics, charts, and recommendations for the collection.
"""

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from collections import defaultdict

insights_bp = Blueprint("insights", __name__)


@insights_bp.route("/")
def insights_page():
    """Insights and analytics page."""
    from services.inventory import get_inventory_manager
    from services.builds import get_build_planner

    inventory = get_inventory_manager()
    planner = get_build_planner()

    # Collection stats
    stats = inventory.get_statistics()

    # Build suggestions
    suggestions = planner.suggest_builds(max_missing=5)[:5]

    # Recommendations
    recommendations = generate_recommendations(inventory, planner)

    # Color distribution for chart
    color_data = [
        {"color": color, "count": count}
        for color, count in sorted(stats.colors.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # Category distribution for chart
    category_data = [
        {"category": cat, "count": count}
        for cat, count in sorted(stats.categories.items(), key=lambda x: x[1], reverse=True)
    ]

    return render_template(
        "pages/insights.html",
        stats=stats.__dict__,
        color_data=color_data,
        category_data=category_data,
        top_bricks=stats.top_bricks,
        suggestions=suggestions,
        recommendations=recommendations,
    )


@insights_bp.route("/stats")
def get_stats():
    """Get collection statistics."""
    from services.inventory import get_inventory_manager

    inventory = get_inventory_manager()
    stats = inventory.get_statistics()

    return jsonify(stats.__dict__)


@insights_bp.route("/colors")
def color_distribution():
    """Get color distribution data."""
    from services.inventory import get_inventory_manager

    inventory = get_inventory_manager()
    stats = inventory.get_statistics()

    data = [
        {"color": color, "count": count}
        for color, count in sorted(stats.colors.items(), key=lambda x: x[1], reverse=True)
    ]

    return jsonify(data)


@insights_bp.route("/categories")
def category_distribution():
    """Get category distribution data."""
    from services.inventory import get_inventory_manager

    inventory = get_inventory_manager()
    stats = inventory.get_statistics()

    data = [
        {"category": cat, "count": count}
        for cat, count in sorted(stats.categories.items(), key=lambda x: x[1], reverse=True)
    ]

    return jsonify(data)


@insights_bp.route("/top-bricks")
def top_bricks():
    """Get most common bricks."""
    from services.inventory import get_inventory_manager

    limit = int(request.args.get("limit", 10))

    inventory = get_inventory_manager()
    stats = inventory.get_statistics()

    return jsonify(stats.top_bricks[:limit])


@insights_bp.route("/recommendations")
def get_recommendations():
    """Get personalized recommendations."""
    from services.inventory import get_inventory_manager
    from services.builds import get_build_planner

    inventory = get_inventory_manager()
    planner = get_build_planner()

    recommendations = generate_recommendations(inventory, planner)

    return jsonify(recommendations)


@insights_bp.route("/what-can-i-build")
def what_can_i_build():
    """Find builds possible with current inventory."""
    from services.builds import get_build_planner

    max_missing = int(request.args.get("max_missing", 0))

    planner = get_build_planner()
    suggestions = planner.suggest_builds(max_missing=max_missing)

    # Filter to only buildable
    buildable = [s for s in suggestions if s["check"]["can_build"]]

    return jsonify({"buildable": buildable, "count": len(buildable)})


@insights_bp.route("/gaps")
def find_gaps():
    """Find pieces that would unlock the most builds."""
    from services.inventory import get_inventory_manager
    from services.builds import get_build_planner

    planner = get_build_planner()

    # Get all builds and their missing parts
    gap_counter = defaultdict(int)

    for build in planner.get_all_builds():
        check = planner.check_build(build.id)
        if check and not check.can_build:
            for missing in check.missing:
                key = f"{missing['brick_id']}_{missing['color']}"
                gap_counter[key] += 1

    # Sort by how many builds each piece would help
    gaps = [
        {
            "brick_id": key.rsplit("_", 1)[0],
            "color": key.rsplit("_", 1)[1],
            "builds_unlocked": count,
        }
        for key, count in sorted(gap_counter.items(), key=lambda x: x[1], reverse=True)
    ][:20]

    return jsonify(gaps)


@insights_bp.route("/duplicates")
def find_duplicates():
    """Find bricks with high quantities (potential duplicates to trade)."""
    from services.inventory import get_inventory_manager

    threshold = int(request.args.get("threshold", 10))

    inventory = get_inventory_manager()
    items = inventory.get_inventory(sort_by="quantity", sort_order="desc")

    duplicates = [item.to_dict() for item in items if item.quantity >= threshold]

    return jsonify(duplicates)


@insights_bp.route("/value-estimate")
def value_estimate():
    """Get estimated collection value."""
    from services.inventory import get_inventory_manager

    inventory = get_inventory_manager()
    stats = inventory.get_statistics()

    # More detailed value breakdown
    by_category = {}
    for cat, count in stats.categories.items():
        price = inventory.PRICE_ESTIMATES.get(cat, 0.10)
        by_category[cat] = {
            "count": count,
            "price_per_piece": price,
            "subtotal": round(count * price, 2),
        }

    return jsonify(
        {
            "total_pieces": stats.total_pieces,
            "estimated_value": stats.estimated_value,
            "by_category": by_category,
            "disclaimer": "Estimates are approximate and based on average market prices.",
        }
    )


def generate_recommendations(inventory, planner) -> list:
    """Generate personalized recommendations."""
    recommendations = []

    stats = inventory.get_statistics()

    # Recommendation: Collection size milestones
    if stats.total_pieces > 0:
        if stats.total_pieces >= 1000:
            recommendations.append(
                {
                    "type": "milestone",
                    "icon": "🏆",
                    "title": "Collection Milestone!",
                    "message": f"You have {stats.total_pieces:,} pieces! You're a serious collector.",
                    "priority": "high",
                }
            )
        elif stats.total_pieces >= 500:
            next_milestone = 1000
            remaining = next_milestone - stats.total_pieces
            recommendations.append(
                {
                    "type": "milestone",
                    "icon": "📈",
                    "title": "Growing Collection",
                    "message": f"Only {remaining} more pieces to reach {next_milestone:,}!",
                    "priority": "medium",
                }
            )

    # Recommendation: Based on color dominance
    if stats.colors:
        top_color = max(stats.colors.items(), key=lambda x: x[1])
        if top_color[1] >= 50:
            recommendations.append(
                {
                    "type": "observation",
                    "icon": "🎨",
                    "title": f'You love {top_color[0].replace("_", " ").title()}!',
                    "message": f"You have {top_color[1]} {top_color[0]} pieces. Consider a monochrome build!",
                    "priority": "low",
                }
            )

    # Recommendation: Build suggestions
    suggestions = planner.suggest_builds(max_missing=5)
    if suggestions:
        best = suggestions[0]
        if best["check"]["can_build"]:
            recommendations.append(
                {
                    "type": "build",
                    "icon": "🏗️",
                    "title": "Ready to Build!",
                    "message": f'You can build "{best["build"]["name"]}" right now!',
                    "priority": "high",
                    "action": f'/builds/{best["build"]["id"]}',
                }
            )
        else:
            missing = best["check"]["parts_missing"]
            recommendations.append(
                {
                    "type": "build",
                    "icon": "🧩",
                    "title": "Almost There!",
                    "message": f'"{best["build"]["name"]}" needs only {missing} more parts!',
                    "priority": "medium",
                    "action": f'/builds/{best["build"]["id"]}',
                }
            )

    # Recommendation: Variety
    if stats.unique_types < 20 and stats.total_pieces > 100:
        recommendations.append(
            {
                "type": "suggestion",
                "icon": "🌈",
                "title": "Add Variety",
                "message": "Your collection has many duplicates. Consider adding different brick types!",
                "priority": "low",
            }
        )

    # Recommendation: Missing categories
    all_categories = {"brick", "plate", "tile", "slope", "technic"}
    owned_categories = set(stats.categories.keys())
    missing_cats = all_categories - owned_categories

    if missing_cats:
        missing_str = ", ".join(c.title() for c in list(missing_cats)[:2])
        recommendations.append(
            {
                "type": "suggestion",
                "icon": "➕",
                "title": "Expand Your Collection",
                "message": f"You don't have any {missing_str} yet. They open up new building possibilities!",
                "priority": "low",
            }
        )

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 2))

    return recommendations
