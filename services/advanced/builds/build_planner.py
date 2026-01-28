"""
Build Planner Service

Plan builds, check against inventory, find substitutes,
and generate shopping lists.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
import csv
import io


@dataclass
class BuildPart:
    """A part needed for a build."""

    brick_id: str
    brick_name: str
    color: str
    quantity: int
    category: str = "brick"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Build:
    """A LEGO build/set."""

    id: str
    name: str
    description: str
    parts: List[BuildPart]
    image_url: str = ""
    source: str = "custom"  # custom, rebrickable, bricklink
    source_id: str = ""  # External ID if imported
    created: str = ""
    total_parts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["parts"] = [p.to_dict() if isinstance(p, BuildPart) else p for p in self.parts]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Build":
        parts = [BuildPart(**p) if isinstance(p, dict) else p for p in data.get("parts", [])]
        data["parts"] = parts
        return cls(**data)


@dataclass
class BuildCheck:
    """Result of checking a build against inventory."""

    build_id: str
    can_build: bool
    total_parts: int
    parts_owned: int
    parts_missing: int
    have: List[Dict[str, Any]]
    missing: List[Dict[str, Any]]
    completion_percent: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BuildPlanner:
    """Plan and track LEGO builds."""

    def __init__(self, storage_path: str = None):
        """Initialize build planner."""
        if storage_path is None:
            storage_path = Path(__file__).parent.parent / "data" / "builds.json"

        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._builds: Dict[str, Build] = {}
        self._load()

    def _load(self):
        """Load saved builds."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    self._builds = {
                        k: Build.from_dict(v) for k, v in data.get("builds", {}).items()
                    }
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Could not load builds: {e}")

    def _save(self):
        """Save builds."""
        data = {
            "version": "1.0",
            "updated": datetime.now().isoformat(),
            "builds": {k: v.to_dict() for k, v in self._builds.items()},
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def create_build(
        self, name: str, parts: List[Dict[str, Any]], description: str = "", image_url: str = ""
    ) -> Build:
        """Create a new custom build."""
        build_id = f"build_{int(datetime.now().timestamp())}"

        build_parts = [
            BuildPart(
                brick_id=p.get("brick_id"),
                brick_name=p.get("brick_name", p.get("brick_id", "").replace("_", " ").title()),
                color=p.get("color", "unknown"),
                quantity=p.get("quantity", 1),
                category=p.get("category", "brick"),
            )
            for p in parts
        ]

        build = Build(
            id=build_id,
            name=name,
            description=description,
            parts=build_parts,
            image_url=image_url,
            source="custom",
            created=datetime.now().isoformat(),
            total_parts=sum(p.quantity for p in build_parts),
        )

        self._builds[build_id] = build
        self._save()

        return build

    def get_build(self, build_id: str) -> Optional[Build]:
        """Get a build by ID."""
        return self._builds.get(build_id)

    def get_all_builds(self) -> List[Build]:
        """Get all builds."""
        return list(self._builds.values())

    def delete_build(self, build_id: str) -> bool:
        """Delete a build."""
        if build_id in self._builds:
            del self._builds[build_id]
            self._save()
            return True
        return False

    def check_build(self, build_id: str) -> Optional[BuildCheck]:
        """Check if we can build a set with current inventory."""
        from services.inventory import get_inventory_manager

        build = self._builds.get(build_id)
        if not build:
            return None

        inventory = get_inventory_manager()

        have = []
        missing = []

        for part in build.parts:
            item = inventory.get_item(part.brick_id, part.color)
            owned = item.quantity if item else 0

            if owned >= part.quantity:
                have.append(
                    {
                        "brick_id": part.brick_id,
                        "brick_name": part.brick_name,
                        "color": part.color,
                        "needed": part.quantity,
                        "owned": owned,
                    }
                )
            else:
                missing.append(
                    {
                        "brick_id": part.brick_id,
                        "brick_name": part.brick_name,
                        "color": part.color,
                        "needed": part.quantity,
                        "owned": owned,
                        "short": part.quantity - owned,
                    }
                )

        total = len(build.parts)
        owned_count = len(have)

        return BuildCheck(
            build_id=build_id,
            can_build=len(missing) == 0,
            total_parts=total,
            parts_owned=owned_count,
            parts_missing=len(missing),
            have=have,
            missing=missing,
            completion_percent=round(owned_count / total * 100, 1) if total > 0 else 0,
        )

    def find_substitutes(self, missing: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find substitute pieces in inventory for missing parts.

        Returns dict mapping brick_id to list of possible substitutes.
        """
        from services.inventory import get_inventory_manager

        inventory = get_inventory_manager()
        substitutes = {}

        for part in missing:
            brick_id = part["brick_id"]
            needed = part["short"]
            subs = []

            # Get all items of same brick type (any color)
            items = inventory.get_by_brick_id(brick_id)

            for item in items:
                if item.color != part["color"] and item.quantity > 0:
                    subs.append(
                        {
                            "brick_id": item.brick_id,
                            "color": item.color,
                            "available": item.quantity,
                            "can_substitute": item.quantity >= needed,
                        }
                    )

            # Also look for similar sizes
            # e.g., if missing 2x4, check 2x3 or 2x6
            similar = self._find_similar_bricks(brick_id)
            for sim_id in similar:
                sim_items = inventory.get_by_brick_id(sim_id)
                for item in sim_items:
                    if item.quantity > 0:
                        subs.append(
                            {
                                "brick_id": item.brick_id,
                                "color": item.color,
                                "available": item.quantity,
                                "similar": True,
                                "can_substitute": item.quantity >= needed,
                            }
                        )

            if subs:
                substitutes[brick_id] = subs

        return substitutes

    def _find_similar_bricks(self, brick_id: str) -> List[str]:
        """Find similar brick IDs (same type, similar size)."""
        similar = []

        # Parse size from brick_id (e.g., "brick_2x4" -> 2, 4)
        import re

        match = re.search(r"(\d+)x(\d+)", brick_id)

        if match:
            w, h = int(match.group(1)), int(match.group(2))
            base_type = brick_id.split("_")[0]  # e.g., "brick", "plate"

            # Generate similar sizes
            for dw in [-1, 0, 1]:
                for dh in [-1, 0, 1]:
                    if dw == 0 and dh == 0:
                        continue

                    nw, nh = w + dw, h + dh
                    if nw >= 1 and nh >= 1:
                        similar.append(f"{base_type}_{nw}x{nh}")

        return similar

    def generate_shopping_list(self, build_id: str) -> Dict[str, Any]:
        """Generate a shopping list for missing parts."""
        check = self.check_build(build_id)
        if not check:
            return {"error": "Build not found"}

        build = self._builds[build_id]

        # Aggregate missing by brick type
        aggregated = {}
        for part in check.missing:
            key = f"{part['brick_id']}_{part['color']}"
            if key in aggregated:
                aggregated[key]["quantity"] += part["short"]
            else:
                aggregated[key] = {
                    "brick_id": part["brick_id"],
                    "brick_name": part["brick_name"],
                    "color": part["color"],
                    "quantity": part["short"],
                }

        return {
            "build_id": build_id,
            "build_name": build.name,
            "items": list(aggregated.values()),
            "total_items": len(aggregated),
            "total_pieces": sum(p["quantity"] for p in aggregated.values()),
        }

    def import_rebrickable(self, csv_content: str, name: str = None) -> Build:
        """Import a build from Rebrickable CSV format."""
        reader = csv.DictReader(io.StringIO(csv_content))

        parts = []
        for row in reader:
            parts.append(
                {
                    "brick_id": row.get("part_num", "").lower().replace("-", "_"),
                    "brick_name": row.get("part_name", ""),
                    "color": row.get("color_name", "unknown").lower().replace(" ", "_"),
                    "quantity": int(row.get("quantity", 1)),
                    "category": row.get("part_cat_name", "brick").lower(),
                }
            )

        build_name = name or f"Imported Build {datetime.now().strftime('%Y-%m-%d')}"

        return self.create_build(
            name=build_name, parts=parts, description="Imported from Rebrickable"
        )

    def import_bricklink(self, xml_content: str, name: str = None) -> Build:
        """Import a build from BrickLink XML format."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_content)
        parts = []

        for item in root.findall(".//ITEM"):
            parts.append(
                {
                    "brick_id": item.findtext("ITEMID", "").lower().replace("-", "_"),
                    "brick_name": item.findtext("ITEMNAME", ""),
                    "color": item.findtext("COLORNAME", "unknown").lower().replace(" ", "_"),
                    "quantity": int(item.findtext("MINQTY", item.findtext("QTY", "1"))),
                    "category": item.findtext("ITEMTYPE", "P"),
                }
            )

        build_name = name or f"Imported Build {datetime.now().strftime('%Y-%m-%d')}"

        return self.create_build(
            name=build_name, parts=parts, description="Imported from BrickLink"
        )

    def suggest_builds(self, max_missing: int = 10) -> List[Dict[str, Any]]:
        """
        Suggest builds that can be completed or nearly completed.

        Args:
            max_missing: Max missing parts to consider

        Returns:
            List of builds with check results, sorted by completion
        """
        suggestions = []

        for build_id, build in self._builds.items():
            check = self.check_build(build_id)
            if check and check.parts_missing <= max_missing:
                suggestions.append({"build": build.to_dict(), "check": check.to_dict()})

        # Sort by completion percentage descending
        suggestions.sort(key=lambda x: x["check"]["completion_percent"], reverse=True)

        return suggestions

    def export_build(self, build_id: str, format: str = "json") -> str:
        """Export a build."""
        build = self._builds.get(build_id)
        if not build:
            return ""

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["brick_id", "brick_name", "color", "quantity", "category"])

            for part in build.parts:
                writer.writerow(
                    [part.brick_id, part.brick_name, part.color, part.quantity, part.category]
                )

            return output.getvalue()
        else:
            return json.dumps(build.to_dict(), indent=2)


# Singleton instance
_build_planner: Optional[BuildPlanner] = None


def get_build_planner() -> BuildPlanner:
    """Get singleton build planner."""
    global _build_planner
    if _build_planner is None:
        _build_planner = BuildPlanner()
    return _build_planner
