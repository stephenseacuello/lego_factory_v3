"""
Inventory Manager

Manages the user's LEGO brick collection with full CRUD operations,
import/export, and statistics.
"""

import json
import os
import csv
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict


class BrickColor(Enum):
    """Official LEGO colors."""

    RED = "red"
    BRIGHT_RED = "bright_red"
    BLUE = "blue"
    BRIGHT_BLUE = "bright_blue"
    YELLOW = "yellow"
    BRIGHT_YELLOW = "bright_yellow"
    GREEN = "green"
    BRIGHT_GREEN = "bright_green"
    WHITE = "white"
    BLACK = "black"
    LIGHT_GRAY = "light_gray"
    DARK_GRAY = "dark_gray"
    ORANGE = "orange"
    BROWN = "brown"
    TAN = "tan"
    PINK = "pink"
    PURPLE = "purple"
    LIME = "lime"
    AZURE = "azure"
    DARK_BLUE = "dark_blue"
    DARK_RED = "dark_red"
    DARK_GREEN = "dark_green"
    TRANS_CLEAR = "trans_clear"
    TRANS_RED = "trans_red"
    TRANS_BLUE = "trans_blue"
    TRANS_YELLOW = "trans_yellow"
    TRANS_GREEN = "trans_green"
    UNKNOWN = "unknown"


@dataclass
class InventoryItem:
    """A single inventory entry."""

    id: str
    brick_id: str  # Catalog brick ID (e.g., "brick_2x4")
    brick_name: str  # Human readable name
    color: str  # Color name
    quantity: int  # How many we have
    category: str  # Brick category
    added_date: str  # ISO date when first added
    last_updated: str  # ISO date of last update
    notes: str = ""  # Optional notes
    source: str = "manual"  # How it was added (manual, scan, import)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InventoryItem":
        return cls(**data)


@dataclass
class InventoryStats:
    """Collection statistics."""

    total_pieces: int
    unique_types: int
    unique_colors: int
    categories: Dict[str, int]
    colors: Dict[str, int]
    top_bricks: List[Tuple[str, int]]
    estimated_value: float
    last_updated: str


class InventoryManager:
    """Manages the complete brick inventory."""

    # Approximate prices per piece (USD) by category
    PRICE_ESTIMATES = {
        "brick": 0.10,
        "plate": 0.08,
        "tile": 0.07,
        "slope": 0.12,
        "technic": 0.15,
        "special": 0.20,
        "minifig": 2.50,
        "default": 0.10,
    }

    def __init__(self, storage_path: str = None):
        """Initialize inventory manager."""
        if storage_path is None:
            storage_path = Path(__file__).parent.parent / "data" / "inventory.json"

        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._inventory: Dict[str, InventoryItem] = {}
        self._load()

    def _load(self):
        """Load inventory from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    self._inventory = {
                        k: InventoryItem.from_dict(v) for k, v in data.get("items", {}).items()
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load inventory: {e}")
                self._inventory = {}
        else:
            self._inventory = {}

    def _save(self):
        """Save inventory to storage."""
        data = {
            "version": "1.0",
            "updated": datetime.now().isoformat(),
            "items": {k: v.to_dict() for k, v in self._inventory.items()},
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def _get_item_key(self, brick_id: str, color: str) -> str:
        """Generate unique key for brick+color combination."""
        return f"{brick_id}_{color}"

    def add_brick(
        self,
        brick_id: str,
        quantity: int = 1,
        color: str = "unknown",
        category: str = "brick",
        brick_name: str = None,
        notes: str = "",
        source: str = "manual",
    ) -> InventoryItem:
        """
        Add brick(s) to inventory.

        If brick+color already exists, increases quantity.
        Otherwise creates new entry.
        """
        key = self._get_item_key(brick_id, color)
        now = datetime.now().isoformat()

        if key in self._inventory:
            # Update existing
            item = self._inventory[key]
            item.quantity += quantity
            item.last_updated = now
            if notes:
                item.notes = notes
        else:
            # Create new
            if brick_name is None:
                brick_name = brick_id.replace("_", " ").title()

            item = InventoryItem(
                id=key,
                brick_id=brick_id,
                brick_name=brick_name,
                color=color,
                quantity=quantity,
                category=category,
                added_date=now,
                last_updated=now,
                notes=notes,
                source=source,
            )
            self._inventory[key] = item

        self._save()
        return item

    def remove_brick(self, brick_id: str, color: str = "unknown", quantity: int = 1) -> bool:
        """
        Remove brick(s) from inventory.

        Returns True if successful, False if not enough pieces.
        """
        key = self._get_item_key(brick_id, color)

        if key not in self._inventory:
            return False

        item = self._inventory[key]

        if item.quantity < quantity:
            return False

        item.quantity -= quantity
        item.last_updated = datetime.now().isoformat()

        # Remove if quantity is 0
        if item.quantity <= 0:
            del self._inventory[key]

        self._save()
        return True

    def update_quantity(self, brick_id: str, color: str, quantity: int) -> Optional[InventoryItem]:
        """Set quantity directly."""
        key = self._get_item_key(brick_id, color)

        if key not in self._inventory:
            return None

        if quantity <= 0:
            del self._inventory[key]
            self._save()
            return None

        item = self._inventory[key]
        item.quantity = quantity
        item.last_updated = datetime.now().isoformat()

        self._save()
        return item

    def get_item(self, brick_id: str, color: str) -> Optional[InventoryItem]:
        """Get a specific inventory item."""
        key = self._get_item_key(brick_id, color)
        return self._inventory.get(key)

    def get_inventory(
        self,
        category: str = None,
        color: str = None,
        search: str = None,
        sort_by: str = "quantity",
        sort_order: str = "desc",
        limit: int = None,
        offset: int = 0,
    ) -> List[InventoryItem]:
        """
        Get inventory with optional filters.

        Args:
            category: Filter by category
            color: Filter by color
            search: Search in brick name
            sort_by: Sort field (quantity, name, color, category, added_date)
            sort_order: asc or desc
            limit: Max results
            offset: Offset for pagination
        """
        items = list(self._inventory.values())

        # Apply filters
        if category:
            items = [i for i in items if i.category.lower() == category.lower()]

        if color:
            items = [i for i in items if i.color.lower() == color.lower()]

        if search:
            search_lower = search.lower()
            items = [
                i
                for i in items
                if search_lower in i.brick_name.lower() or search_lower in i.brick_id.lower()
            ]

        # Sort
        reverse = sort_order == "desc"
        if sort_by == "quantity":
            items.sort(key=lambda x: x.quantity, reverse=reverse)
        elif sort_by == "name":
            items.sort(key=lambda x: x.brick_name.lower(), reverse=reverse)
        elif sort_by == "color":
            items.sort(key=lambda x: x.color, reverse=reverse)
        elif sort_by == "category":
            items.sort(key=lambda x: x.category, reverse=reverse)
        elif sort_by == "added_date":
            items.sort(key=lambda x: x.added_date, reverse=reverse)

        # Paginate
        if limit:
            items = items[offset : offset + limit]
        elif offset:
            items = items[offset:]

        return items

    def get_by_brick_id(self, brick_id: str) -> List[InventoryItem]:
        """Get all colors of a specific brick type."""
        return [i for i in self._inventory.values() if i.brick_id == brick_id]

    def get_statistics(self) -> InventoryStats:
        """Get collection statistics."""
        items = list(self._inventory.values())

        if not items:
            return InventoryStats(
                total_pieces=0,
                unique_types=0,
                unique_colors=0,
                categories={},
                colors={},
                top_bricks=[],
                estimated_value=0.0,
                last_updated=datetime.now().isoformat(),
            )

        # Aggregate stats
        total_pieces = sum(i.quantity for i in items)
        unique_types = len(set(i.brick_id for i in items))
        unique_colors = len(set(i.color for i in items))

        # By category
        categories = defaultdict(int)
        for item in items:
            categories[item.category] += item.quantity

        # By color
        colors = defaultdict(int)
        for item in items:
            colors[item.color] += item.quantity

        # Top bricks
        brick_totals = defaultdict(int)
        for item in items:
            brick_totals[item.brick_name] += item.quantity
        top_bricks = sorted(brick_totals.items(), key=lambda x: x[1], reverse=True)[:10]

        # Estimated value
        value = 0.0
        for item in items:
            price = self.PRICE_ESTIMATES.get(item.category, self.PRICE_ESTIMATES["default"])
            value += item.quantity * price

        return InventoryStats(
            total_pieces=total_pieces,
            unique_types=unique_types,
            unique_colors=unique_colors,
            categories=dict(categories),
            colors=dict(colors),
            top_bricks=top_bricks,
            estimated_value=round(value, 2),
            last_updated=datetime.now().isoformat(),
        )

    def check_parts(self, parts_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if we have parts for a build.

        Args:
            parts_list: List of {brick_id, color, quantity} dicts

        Returns:
            Dict with have, missing, and can_build status
        """
        have = []
        missing = []

        for part in parts_list:
            brick_id = part.get("brick_id")
            color = part.get("color", "unknown")
            needed = part.get("quantity", 1)

            item = self.get_item(brick_id, color)
            owned = item.quantity if item else 0

            if owned >= needed:
                have.append(
                    {"brick_id": brick_id, "color": color, "needed": needed, "owned": owned}
                )
            else:
                missing.append(
                    {
                        "brick_id": brick_id,
                        "color": color,
                        "needed": needed,
                        "owned": owned,
                        "short": needed - owned,
                    }
                )

        return {
            "can_build": len(missing) == 0,
            "have": have,
            "missing": missing,
            "total_parts": len(parts_list),
            "parts_owned": len(have),
            "parts_missing": len(missing),
        }

    def export_csv(self, filepath: str = None) -> str:
        """Export inventory to CSV."""
        if filepath is None:
            filepath = self.storage_path.parent / "inventory_export.csv"

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["brick_id", "brick_name", "color", "quantity", "category", "notes"])

            for item in self._inventory.values():
                writer.writerow(
                    [
                        item.brick_id,
                        item.brick_name,
                        item.color,
                        item.quantity,
                        item.category,
                        item.notes,
                    ]
                )

        return str(filepath)

    def export_json(self) -> Dict[str, Any]:
        """Export inventory as JSON dict."""
        return {
            "version": "1.0",
            "exported": datetime.now().isoformat(),
            "stats": asdict(self.get_statistics()),
            "items": [item.to_dict() for item in self._inventory.values()],
        }

    def import_csv(self, filepath: str, merge: bool = True) -> int:
        """
        Import inventory from CSV.

        Args:
            filepath: Path to CSV file
            merge: If True, add to existing. If False, replace.

        Returns:
            Number of items imported
        """
        if not merge:
            self._inventory = {}

        count = 0
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)

            for row in reader:
                self.add_brick(
                    brick_id=row.get("brick_id", row.get("part_num", "")),
                    quantity=int(row.get("quantity", row.get("qty", 1))),
                    color=row.get("color", "unknown"),
                    category=row.get("category", "brick"),
                    brick_name=row.get("brick_name", row.get("name", None)),
                    source="import",
                )
                count += 1

        return count

    def import_bricklink(self, xml_content: str) -> int:
        """Import from BrickLink XML format."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_content)
        count = 0

        for item in root.findall(".//ITEM"):
            part_num = item.findtext("ITEMID", "")
            color = item.findtext("COLOR", "unknown")
            qty = int(item.findtext("MINQTY", item.findtext("QTY", "1")))

            if part_num:
                self.add_brick(
                    brick_id=part_num.lower().replace("-", "_"),
                    quantity=qty,
                    color=self._map_bricklink_color(color),
                    source="bricklink",
                )
                count += 1

        return count

    def import_rebrickable(self, csv_content: str) -> int:
        """Import from Rebrickable CSV format."""
        import io

        count = 0
        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            part_num = row.get("part_num", "")
            color = row.get("color_name", "unknown")
            qty = int(row.get("quantity", 1))

            if part_num:
                self.add_brick(
                    brick_id=part_num.lower().replace("-", "_"),
                    quantity=qty,
                    color=color.lower().replace(" ", "_"),
                    brick_name=row.get("part_name"),
                    source="rebrickable",
                )
                count += 1

        return count

    def _map_bricklink_color(self, bl_color: str) -> str:
        """Map BrickLink color codes to our color names."""
        bl_mapping = {
            "1": "white",
            "2": "tan",
            "3": "yellow",
            "4": "orange",
            "5": "red",
            "6": "green",
            "7": "blue",
            "8": "brown",
            "9": "light_gray",
            "10": "dark_gray",
            "11": "black",
            "12": "trans_clear",
            "15": "trans_red",
            "17": "trans_yellow",
        }
        return bl_mapping.get(bl_color, "unknown")

    def clear_all(self) -> int:
        """Clear entire inventory. Returns count of deleted items."""
        count = len(self._inventory)
        self._inventory = {}
        self._save()
        return count

    def get_all_categories(self) -> List[str]:
        """Get list of all categories in inventory."""
        return sorted(set(i.category for i in self._inventory.values()))

    def get_all_colors(self) -> List[str]:
        """Get list of all colors in inventory."""
        return sorted(set(i.color for i in self._inventory.values()))


# Singleton instance
_inventory_manager: Optional[InventoryManager] = None


def get_inventory_manager() -> InventoryManager:
    """Get singleton inventory manager instance."""
    global _inventory_manager
    if _inventory_manager is None:
        _inventory_manager = InventoryManager()
    return _inventory_manager
