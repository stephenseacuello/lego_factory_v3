"""
Workspace State Manager

Tracks the current state of bricks on the physical workspace (baseplate).
This is the "live" state that syncs with the camera feed.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import threading


@dataclass
class WorkspaceBrick:
    """A brick currently on the workspace."""

    id: str  # Unique ID for this detection
    brick_id: str  # Catalog brick ID
    brick_name: str  # Human readable name
    color: str  # Detected color
    color_rgb: Tuple[int, int, int]  # RGB values
    confidence: float  # Detection confidence
    position: Tuple[int, int]  # Center position (x, y) in pixels
    grid_position: str  # Grid coordinate (e.g., "A3")
    bbox: Tuple[int, int, int, int]  # Bounding box (x1, y1, x2, y2)
    first_seen: float  # Timestamp when first detected
    last_seen: float  # Timestamp of last detection
    stable: bool = False  # True if brick hasn't moved recently

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkspaceBrick":
        # Handle tuple conversion
        data["color_rgb"] = tuple(data["color_rgb"])
        data["position"] = tuple(data["position"])
        data["bbox"] = tuple(data["bbox"])
        return cls(**data)


@dataclass
class WorkspaceConfig:
    """Workspace calibration and settings."""

    # Baseplate dimensions (in studs) - 16x32 grey baseplate
    width_studs: int = 32  # Long side (columns A-P repeated twice or A-AF)
    height_studs: int = 16  # Short side (rows 1-16)

    # Camera frame dimensions
    frame_width: int = 1280
    frame_height: int = 720

    # Region of interest (where baseplate is in frame)
    roi_x1: int = 100
    roi_y1: int = 50
    roi_x2: int = 1180
    roi_y2: int = 670

    # Stability settings
    stability_threshold_px: int = 10  # Pixels of movement to consider "moved"
    stability_time_s: float = 0.5  # Seconds without movement to be "stable"

    # Detection settings
    # Note: Set very low for Roboflow models that return low confidence on real photos
    min_confidence: float = 0.001
    iou_threshold: float = 0.5  # For matching detections across frames


class WorkspaceStateManager:
    """Manages the real-time state of the workspace."""

    def __init__(self, storage_path: str = None):
        """Initialize workspace state manager."""
        if storage_path is None:
            storage_path = Path(__file__).parent.parent / "data" / "workspace_state.json"

        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._bricks: Dict[str, WorkspaceBrick] = {}
        self._config = WorkspaceConfig()
        self._lock = threading.Lock()
        self._frame_count = 0
        self._last_update = 0

        self._load()

    def _load(self):
        """Load saved workspace state."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)

                    # Load config
                    if "config" in data:
                        self._config = WorkspaceConfig(**data["config"])

                    # Load bricks
                    self._bricks = {
                        k: WorkspaceBrick.from_dict(v) for k, v in data.get("bricks", {}).items()
                    }
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Warning: Could not load workspace state: {e}")

    def _save(self):
        """Save workspace state."""
        data = {
            "updated": datetime.now().isoformat(),
            "config": asdict(self._config),
            "bricks": {k: v.to_dict() for k, v in self._bricks.items()},
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def update_from_detections(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update workspace state from new detections.

        This is the main method called by the vision system.
        It matches new detections to existing bricks and handles
        additions/removals.

        Args:
            detections: List of detection dicts from vision system

        Returns:
            Dict with added, removed, updated, and current bricks
        """
        now = time.time()

        with self._lock:
            self._frame_count += 1

            added = []
            updated = []
            matched_ids = set()

            for det in detections:
                if det.get("confidence", 0) < self._config.min_confidence:
                    continue

                # Try to match to existing brick
                match_id = self._find_matching_brick(det)

                if match_id:
                    # Update existing brick
                    brick = self._bricks[match_id]
                    old_pos = brick.position

                    brick.last_seen = now
                    brick.confidence = det["confidence"]
                    brick.position = tuple(det["center"])
                    brick.bbox = tuple(det["bbox"])

                    # Check stability
                    moved = (
                        self._distance(old_pos, brick.position)
                        > self._config.stability_threshold_px
                    )
                    if moved:
                        brick.stable = False
                    elif now - brick.first_seen > self._config.stability_time_s:
                        brick.stable = True

                    matched_ids.add(match_id)
                    updated.append(brick.to_dict())
                else:
                    # New brick
                    brick_id = f"wb_{int(now * 1000)}_{len(self._bricks)}"

                    brick = WorkspaceBrick(
                        id=brick_id,
                        brick_id=det.get("brick_id", "unknown"),
                        brick_name=det.get("brick_name", "Unknown Brick"),
                        color=det.get("color", "unknown"),
                        color_rgb=tuple(det.get("color_rgb", (128, 128, 128))),
                        confidence=det["confidence"],
                        position=tuple(det["center"]),
                        grid_position=det.get("grid_position", "A1"),
                        bbox=tuple(det["bbox"]),
                        first_seen=now,
                        last_seen=now,
                        stable=False,
                    )

                    self._bricks[brick_id] = brick
                    added.append(brick.to_dict())
                    matched_ids.add(brick_id)

            # Find removed bricks (not seen in this frame)
            removed = []
            stale_threshold = 1.0  # 1 second without detection = removed

            for brick_id, brick in list(self._bricks.items()):
                if brick_id not in matched_ids:
                    if now - brick.last_seen > stale_threshold:
                        removed.append(brick.to_dict())
                        del self._bricks[brick_id]

            self._last_update = now

            # Save periodically (every 30 frames)
            if self._frame_count % 30 == 0:
                self._save()

        return {
            "added": added,
            "removed": removed,
            "updated": updated,
            "current": [b.to_dict() for b in self._bricks.values()],
            "count": len(self._bricks),
            "frame": self._frame_count,
        }

    def _find_matching_brick(self, detection: Dict[str, Any]) -> Optional[str]:
        """Find existing brick that matches this detection."""
        det_center = detection.get("center", (0, 0))
        det_bbox = detection.get("bbox", (0, 0, 0, 0))

        best_match = None
        best_iou = 0

        for brick_id, brick in self._bricks.items():
            # Calculate IoU (Intersection over Union)
            iou = self._calculate_iou(brick.bbox, det_bbox)

            if iou > self._config.iou_threshold and iou > best_iou:
                best_match = brick_id
                best_iou = iou

        return best_match

    def _calculate_iou(self, box1: Tuple, box2: Tuple) -> float:
        """Calculate Intersection over Union of two boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 < x1 or y2 < y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)

        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def _distance(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """Calculate Euclidean distance between two points."""
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def get_current_bricks(self) -> List[WorkspaceBrick]:
        """Get all bricks currently on workspace."""
        with self._lock:
            return list(self._bricks.values())

    def get_brick(self, brick_id: str) -> Optional[WorkspaceBrick]:
        """Get a specific brick by ID."""
        return self._bricks.get(brick_id)

    def get_bricks_at_grid(self, grid_position: str) -> List[WorkspaceBrick]:
        """Get bricks at a specific grid position."""
        return [b for b in self._bricks.values() if b.grid_position == grid_position]

    def get_summary(self) -> Dict[str, Any]:
        """Get workspace summary."""
        with self._lock:
            bricks = list(self._bricks.values())

            by_type = defaultdict(int)
            by_color = defaultdict(int)

            for brick in bricks:
                by_type[brick.brick_name] += 1
                by_color[brick.color] += 1

            return {
                "total_bricks": len(bricks),
                "stable_bricks": sum(1 for b in bricks if b.stable),
                "by_type": dict(by_type),
                "by_color": dict(by_color),
                "last_update": self._last_update,
                "frame_count": self._frame_count,
            }

    def clear(self):
        """Clear all bricks from workspace."""
        with self._lock:
            self._bricks = {}
            self._frame_count = 0
            self._save()

    def get_config(self) -> WorkspaceConfig:
        """Get workspace configuration."""
        return self._config

    def update_config(self, **kwargs) -> WorkspaceConfig:
        """Update workspace configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

        self._save()
        return self._config

    def calibrate_from_corners(
        self,
        top_left: Tuple[int, int],
        top_right: Tuple[int, int],
        bottom_left: Tuple[int, int],
        bottom_right: Tuple[int, int],
    ):
        """Calibrate workspace from corner positions."""
        self._config.roi_x1 = top_left[0]
        self._config.roi_y1 = top_left[1]
        self._config.roi_x2 = bottom_right[0]
        self._config.roi_y2 = bottom_right[1]

        self._save()

    def pixel_to_grid(self, x: int, y: int) -> str:
        """Convert pixel coordinates to grid position."""
        config = self._config

        # Normalize to 0-1 within ROI
        norm_x = (x - config.roi_x1) / (config.roi_x2 - config.roi_x1)
        norm_y = (y - config.roi_y1) / (config.roi_y2 - config.roi_y1)

        # Clamp to valid range
        norm_x = max(0, min(1, norm_x))
        norm_y = max(0, min(1, norm_y))

        # Convert to grid coordinates
        col = int(norm_x * 8)  # A-H
        row = int(norm_y * 8)  # 1-8

        col_letter = chr(ord("A") + min(col, 7))
        row_number = min(row + 1, 8)

        return f"{col_letter}{row_number}"

    def add_all_to_inventory(self) -> List[Dict[str, Any]]:
        """
        Add all current workspace bricks to permanent inventory.

        Returns list of items added.
        """
        from .inventory_manager import get_inventory_manager

        manager = get_inventory_manager()
        added = []

        with self._lock:
            for brick in self._bricks.values():
                if brick.stable and brick.confidence >= 0.7:
                    item = manager.add_brick(
                        brick_id=brick.brick_id, quantity=1, color=brick.color, source="workspace"
                    )
                    added.append(item.to_dict())

        return added


# Singleton instance
_workspace_manager: Optional[WorkspaceStateManager] = None


def get_workspace_manager() -> WorkspaceStateManager:
    """Get singleton workspace state manager."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceStateManager()
    return _workspace_manager
