"""
Catalog Service

Provides access to the brick catalog with search, filter, and browse capabilities.
"""

from typing import Dict, Any, List, Optional
from dataclasses import asdict

# Import from shared modules
try:
    from brick_catalog_extended import BRICKS, get, search, by_category, stats, Category
    from brick_catalog import BRICK_CATALOG, get_brick, search_bricks

    CATALOG_AVAILABLE = True
except ImportError:
    CATALOG_AVAILABLE = False
    BRICKS = {}


class CatalogService:
    """Service for browsing and searching the brick catalog."""

    @staticmethod
    def get_all_bricks(
        category: str = None,
        search_query: str = None,
        min_width: int = None,
        max_width: int = None,
        min_height: int = None,
        max_height: int = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get bricks with optional filtering and pagination.

        Returns:
            Dict with bricks list and metadata
        """
        if not CATALOG_AVAILABLE:
            return {"bricks": [], "total": 0, "error": "Catalog not available"}

        # Start with all bricks
        if search_query:
            results = search(search_query)
        elif category:
            try:
                cat = Category[category.upper()]
                results = by_category(cat)
            except (KeyError, AttributeError):
                results = list(BRICKS.values())
        else:
            results = list(BRICKS.values())

        # Apply size filters
        if min_width:
            results = [b for b in results if b.studs_x >= min_width]
        if max_width:
            results = [b for b in results if b.studs_x <= max_width]
        if min_height:
            results = [b for b in results if b.height_plates >= min_height]
        if max_height:
            results = [b for b in results if b.height_plates <= max_height]

        total = len(results)

        # Sort
        reverse = sort_order == "desc"
        if sort_by == "name":
            results.sort(key=lambda b: b.name, reverse=reverse)
        elif sort_by == "width":
            results.sort(key=lambda b: b.studs_x, reverse=reverse)
        elif sort_by == "height":
            results.sort(key=lambda b: b.height_plates, reverse=reverse)
        elif sort_by == "size":
            results.sort(key=lambda b: b.studs_x * b.studs_y, reverse=reverse)

        # Paginate
        results = results[offset : offset + limit]

        # Convert to dicts
        bricks = [CatalogService._brick_to_dict(b) for b in results]

        return {
            "bricks": bricks,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def get_brick(brick_id: str) -> Optional[Dict[str, Any]]:
        """Get a single brick by ID."""
        if not CATALOG_AVAILABLE:
            return None

        brick = get(brick_id)
        if brick:
            return CatalogService._brick_to_dict(brick)

        # Try basic catalog
        brick = get_brick(brick_id)
        if brick:
            return CatalogService._basic_brick_to_dict(brick)

        return None

    @staticmethod
    def search_bricks(query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search bricks by name or description."""
        if not CATALOG_AVAILABLE:
            return []

        results = search(query)[:limit]
        return [CatalogService._brick_to_dict(b) for b in results]

    @staticmethod
    def get_categories() -> List[Dict[str, Any]]:
        """Get all categories with counts."""
        if not CATALOG_AVAILABLE:
            return []

        categories = []
        for cat in Category:
            bricks = by_category(cat)
            categories.append(
                {
                    "id": cat.name.lower(),
                    "name": cat.value.replace("_", " ").title(),
                    "count": len(bricks),
                }
            )

        # Sort by count descending
        categories.sort(key=lambda c: c["count"], reverse=True)

        return categories

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get catalog statistics."""
        if not CATALOG_AVAILABLE:
            return {"total": 0, "categories": 0}

        s = stats()
        return {
            "total": s["total"],
            "categories": len(s["by_category"]),
            "by_category": s["by_category"],
        }

    @staticmethod
    def get_similar_bricks(brick_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Get bricks similar to the given brick."""
        if not CATALOG_AVAILABLE:
            return []

        brick = get(brick_id)
        if not brick:
            return []

        # Find bricks with similar dimensions or same category
        similar = []
        for b in BRICKS.values():
            if b.name == brick_id:
                continue

            score = 0
            # Same category
            if b.category == brick.category:
                score += 3
            # Similar width
            if abs(b.studs_x - brick.studs_x) <= 1:
                score += 2
            # Similar depth
            if abs(b.studs_y - brick.studs_y) <= 1:
                score += 2
            # Same height
            if b.height_plates == brick.height_plates:
                score += 1

            if score > 0:
                similar.append((score, b))

        # Sort by score and take top results
        similar.sort(key=lambda x: x[0], reverse=True)
        results = [CatalogService._brick_to_dict(b) for _, b in similar[:limit]]

        return results

    @staticmethod
    def _brick_to_dict(brick) -> Dict[str, Any]:
        """Convert extended brick to dictionary."""
        return {
            "id": brick.name,
            "name": brick.name.replace("_", " ").title(),
            "studs_x": brick.studs_x,
            "studs_y": brick.studs_y,
            "height_plates": brick.height_plates,
            "category": (
                brick.category.value if hasattr(brick.category, "value") else str(brick.category)
            ),
            "width_mm": brick.studs_x * 8.0,
            "depth_mm": brick.studs_y * 8.0,
            "height_mm": brick.height_plates * 3.2,
            "part_number": getattr(brick, "part_number", None),
            "description": getattr(brick, "description", ""),
            "tags": getattr(brick, "tags", []),
            "features": {
                "hollow": getattr(brick, "hollow", True),
                "studs": getattr(brick, "has_studs", True),
                "tubes": getattr(brick, "has_tubes", brick.studs_x >= 2 and brick.studs_y >= 2),
            },
        }

    @staticmethod
    def _basic_brick_to_dict(brick) -> Dict[str, Any]:
        """Convert basic brick definition to dictionary."""
        return {
            "id": brick.id,
            "name": brick.name or brick.id.replace("_", " ").title(),
            "studs_x": brick.studs_x,
            "studs_y": brick.studs_y,
            "height_plates": brick.height_plates,
            "category": brick.category.value if hasattr(brick, "category") else "brick",
            "width_mm": brick.studs_x * 8.0,
            "depth_mm": brick.studs_y * 8.0,
            "height_mm": brick.height_plates * 3.2,
            "part_number": getattr(brick, "part_number", None),
            "features": {},
        }


# Singleton instance
catalog_service = CatalogService()
