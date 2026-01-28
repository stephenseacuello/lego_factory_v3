"""
Batch Operations for LEGO MCP

Handles batch creation, export, and processing of multiple bricks.
Includes progress tracking, error recovery, and parallel execution.
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import traceback


# ============================================================================
# ENUMS
# ============================================================================


class BatchStatus(Enum):
    """Status of a batch operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Some items failed
    FAILED = "failed"
    CANCELLED = "cancelled"


class ItemStatus(Enum):
    """Status of an individual item in a batch."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class BatchItem:
    """A single item in a batch operation."""

    index: int
    params: Dict[str, Any]
    status: ItemStatus = ItemStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    duration_ms: float = 0
    component_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "duration_ms": self.duration_ms,
            "component_name": self.component_name,
        }


@dataclass
class BatchOperation:
    """A batch operation containing multiple items."""

    id: str
    operation_type: str
    items: List[BatchItem]
    status: BatchStatus = BatchStatus.PENDING

    # Progress
    completed: int = 0
    failed: int = 0
    total: int = 0

    # Timing
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Options
    max_retries: int = 3
    retry_delay_ms: int = 1000
    stop_on_error: bool = False
    parallel: bool = False
    max_parallel: int = 4

    # Callbacks
    on_progress: Optional[Callable[[int, int], None]] = None
    on_item_complete: Optional[Callable[[BatchItem], None]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "operation_type": self.operation_type,
            "status": self.status.value,
            "progress": {
                "completed": self.completed,
                "failed": self.failed,
                "total": self.total,
                "percent": (
                    round((self.completed + self.failed) / self.total * 100, 1)
                    if self.total > 0
                    else 0
                ),
            },
            "timing": {
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "duration_ms": (
                    (self.completed_at - self.started_at) * 1000
                    if self.completed_at and self.started_at
                    else None
                ),
            },
            "items": [item.to_dict() for item in self.items],
        }


# ============================================================================
# BATCH EXECUTOR
# ============================================================================


class BatchExecutor:
    """
    Executes batch operations with progress tracking and error recovery.

    Features:
    - Progress tracking with callbacks
    - Automatic retries on failure
    - Parallel execution option
    - Stop on error option
    - Detailed result reporting
    """

    def __init__(self, fusion_client=None, slicer_client=None):
        self.fusion_client = fusion_client
        self.slicer_client = slicer_client
        self._active_batches: Dict[str, BatchOperation] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _generate_id(self) -> str:
        """Generate a batch ID."""
        import hashlib
        import os

        timestamp = str(time.time()).replace(".", "")
        random_part = hashlib.md5(os.urandom(8)).hexdigest()[:6]
        return f"batch_{timestamp}_{random_part}"

    async def _execute_item(
        self, item: BatchItem, handler: Callable, batch: BatchOperation
    ) -> bool:
        """Execute a single batch item with retries."""
        while item.attempts < batch.max_retries:
            item.attempts += 1
            item.status = ItemStatus.RUNNING if item.attempts == 1 else ItemStatus.RETRYING

            start_time = time.time()

            try:
                result = await handler(item.params)

                item.duration_ms = (time.time() - start_time) * 1000
                item.result = result
                item.status = ItemStatus.COMPLETED
                item.component_name = result.get("component_name")

                batch.completed += 1

                if batch.on_item_complete:
                    batch.on_item_complete(item)

                return True

            except Exception as e:
                item.error = str(e)

                if item.attempts < batch.max_retries:
                    # Wait before retry
                    await asyncio.sleep(batch.retry_delay_ms / 1000)
                else:
                    item.status = ItemStatus.FAILED
                    item.duration_ms = (time.time() - start_time) * 1000
                    batch.failed += 1

                    if batch.stop_on_error:
                        return False

        return True

    async def execute_batch(
        self,
        operation_type: str,
        items: List[Dict[str, Any]],
        handler: Callable,
        options: Dict[str, Any] = None,
    ) -> BatchOperation:
        """
        Execute a batch operation.

        Args:
            operation_type: Type of operation (create_brick, export, etc.)
            items: List of parameter dictionaries for each item
            handler: Async function to execute for each item
            options: Batch options (max_retries, parallel, etc.)

        Returns:
            BatchOperation with results
        """
        options = options or {}

        # Create batch operation
        batch = BatchOperation(
            id=self._generate_id(),
            operation_type=operation_type,
            items=[BatchItem(index=i, params=params) for i, params in enumerate(items)],
            total=len(items),
            max_retries=options.get("max_retries", 3),
            retry_delay_ms=options.get("retry_delay_ms", 1000),
            stop_on_error=options.get("stop_on_error", False),
            parallel=options.get("parallel", False),
            max_parallel=options.get("max_parallel", 4),
        )

        self._active_batches[batch.id] = batch
        batch.status = BatchStatus.RUNNING
        batch.started_at = time.time()

        try:
            if batch.parallel:
                # Parallel execution
                await self._execute_parallel(batch, handler)
            else:
                # Sequential execution
                await self._execute_sequential(batch, handler)

            # Determine final status
            if batch.failed == 0:
                batch.status = BatchStatus.COMPLETED
            elif batch.completed == 0:
                batch.status = BatchStatus.FAILED
            else:
                batch.status = BatchStatus.PARTIAL

        except asyncio.CancelledError:
            batch.status = BatchStatus.CANCELLED
            # Mark remaining items as skipped
            for item in batch.items:
                if item.status in [ItemStatus.PENDING, ItemStatus.RUNNING]:
                    item.status = ItemStatus.SKIPPED
        except Exception as e:
            batch.status = BatchStatus.FAILED
            batch.items[-1].error = str(e)

        batch.completed_at = time.time()

        return batch

    async def _execute_sequential(self, batch: BatchOperation, handler: Callable):
        """Execute items sequentially."""
        for item in batch.items:
            success = await self._execute_item(item, handler, batch)

            if batch.on_progress:
                batch.on_progress(batch.completed + batch.failed, batch.total)

            if not success and batch.stop_on_error:
                # Skip remaining items
                for remaining in batch.items[item.index + 1 :]:
                    remaining.status = ItemStatus.SKIPPED
                break

    async def _execute_parallel(self, batch: BatchOperation, handler: Callable):
        """Execute items in parallel with semaphore."""
        semaphore = asyncio.Semaphore(batch.max_parallel)

        async def execute_with_semaphore(item: BatchItem):
            async with semaphore:
                await self._execute_item(item, handler, batch)

                if batch.on_progress:
                    batch.on_progress(batch.completed + batch.failed, batch.total)

        await asyncio.gather(
            *[execute_with_semaphore(item) for item in batch.items], return_exceptions=True
        )

    def get_batch(self, batch_id: str) -> Optional[BatchOperation]:
        """Get a batch operation by ID."""
        return self._active_batches.get(batch_id)

    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a running batch operation."""
        batch = self._active_batches.get(batch_id)
        if batch and batch.status == BatchStatus.RUNNING:
            batch.status = BatchStatus.CANCELLED
            return True
        return False

    def list_batches(self) -> List[Dict[str, Any]]:
        """List all batch operations."""
        return [
            {
                "id": batch.id,
                "operation_type": batch.operation_type,
                "status": batch.status.value,
                "progress": f"{batch.completed + batch.failed}/{batch.total}",
            }
            for batch in self._active_batches.values()
        ]


# ============================================================================
# BATCH BRICK CREATION
# ============================================================================


async def batch_create_bricks(
    brick_definitions: List[Dict[str, Any]], fusion_client, options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create multiple bricks in a batch.

    Args:
        brick_definitions: List of brick definition dicts
        fusion_client: Fusion 360 client
        options: Batch options

    Returns:
        Batch result with all created bricks
    """
    executor = BatchExecutor(fusion_client=fusion_client)

    async def create_brick(params):
        return await fusion_client.create_brick(params)

    batch = await executor.execute_batch("create_brick", brick_definitions, create_brick, options)

    return batch.to_dict()


async def batch_export_stl(
    components: List[str],
    output_dir: str,
    fusion_client,
    refinement: str = "medium",
    options: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Export multiple components to STL.

    Args:
        components: List of component names
        output_dir: Output directory
        fusion_client: Fusion 360 client
        refinement: STL quality level
        options: Batch options

    Returns:
        Batch result with all exports
    """
    import os

    executor = BatchExecutor(fusion_client=fusion_client)

    # Create export params
    export_params = [
        {
            "component_name": comp,
            "output_path": os.path.join(output_dir, f"{comp}.stl"),
            "refinement": refinement,
        }
        for comp in components
    ]

    async def export_stl(params):
        return await fusion_client.export_stl(
            params["component_name"], params["output_path"], params["refinement"]
        )

    batch = await executor.execute_batch("export_stl", export_params, export_stl, options)

    return batch.to_dict()


async def batch_slice(
    stl_files: List[str], printer: str, quality: str, slicer_client, options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Slice multiple STL files.

    Args:
        stl_files: List of STL file paths
        printer: Printer profile
        quality: Quality preset
        slicer_client: Slicer client
        options: Batch options

    Returns:
        Batch result with all sliced files
    """
    executor = BatchExecutor(slicer_client=slicer_client)

    slice_params = [{"stl_path": stl, "printer": printer, "quality": quality} for stl in stl_files]

    async def slice_file(params):
        return await slicer_client.slice(params["stl_path"], params["printer"], params["quality"])

    batch = await executor.execute_batch("slice", slice_params, slice_file, options)

    return batch.to_dict()


# ============================================================================
# BRICK SET GENERATION
# ============================================================================


def generate_brick_set(set_type: str) -> List[Dict[str, Any]]:
    """
    Generate a set of brick definitions.

    Args:
        set_type: Type of set to generate

    Returns:
        List of brick definitions
    """
    sets = {
        "basic": [
            # Basic building bricks
            {"name": "brick_1x1", "width_studs": 1, "depth_studs": 1, "height_plates": 3},
            {"name": "brick_1x2", "width_studs": 1, "depth_studs": 2, "height_plates": 3},
            {"name": "brick_1x3", "width_studs": 1, "depth_studs": 3, "height_plates": 3},
            {"name": "brick_1x4", "width_studs": 1, "depth_studs": 4, "height_plates": 3},
            {"name": "brick_1x6", "width_studs": 1, "depth_studs": 6, "height_plates": 3},
            {"name": "brick_2x2", "width_studs": 2, "depth_studs": 2, "height_plates": 3},
            {"name": "brick_2x3", "width_studs": 2, "depth_studs": 3, "height_plates": 3},
            {"name": "brick_2x4", "width_studs": 2, "depth_studs": 4, "height_plates": 3},
            {"name": "brick_2x6", "width_studs": 2, "depth_studs": 6, "height_plates": 3},
            {"name": "brick_2x8", "width_studs": 2, "depth_studs": 8, "height_plates": 3},
        ],
        "plates": [
            # Plates
            {"name": "plate_1x1", "width_studs": 1, "depth_studs": 1, "height_plates": 1},
            {"name": "plate_1x2", "width_studs": 1, "depth_studs": 2, "height_plates": 1},
            {"name": "plate_1x4", "width_studs": 1, "depth_studs": 4, "height_plates": 1},
            {"name": "plate_1x6", "width_studs": 1, "depth_studs": 6, "height_plates": 1},
            {"name": "plate_2x2", "width_studs": 2, "depth_studs": 2, "height_plates": 1},
            {"name": "plate_2x3", "width_studs": 2, "depth_studs": 3, "height_plates": 1},
            {"name": "plate_2x4", "width_studs": 2, "depth_studs": 4, "height_plates": 1},
            {"name": "plate_2x6", "width_studs": 2, "depth_studs": 6, "height_plates": 1},
            {"name": "plate_4x4", "width_studs": 4, "depth_studs": 4, "height_plates": 1},
            {"name": "plate_4x8", "width_studs": 4, "depth_studs": 8, "height_plates": 1},
        ],
        "slopes": [
            # Slope bricks
            {
                "name": "slope_45_2x1",
                "width_studs": 2,
                "depth_studs": 1,
                "height_plates": 3,
                "features": {"slope": {"angle": 45, "direction": "front"}},
            },
            {
                "name": "slope_45_2x2",
                "width_studs": 2,
                "depth_studs": 2,
                "height_plates": 3,
                "features": {"slope": {"angle": 45, "direction": "front"}},
            },
            {
                "name": "slope_45_2x3",
                "width_studs": 2,
                "depth_studs": 3,
                "height_plates": 3,
                "features": {"slope": {"angle": 45, "direction": "front"}},
            },
            {
                "name": "slope_33_3x1",
                "width_studs": 3,
                "depth_studs": 1,
                "height_plates": 3,
                "features": {"slope": {"angle": 33, "direction": "front"}},
            },
            {
                "name": "slope_65_2x1",
                "width_studs": 2,
                "depth_studs": 1,
                "height_plates": 3,
                "features": {"slope": {"angle": 65, "direction": "front"}},
            },
        ],
        "technic": [
            # Technic beams
            {
                "name": "technic_1x2",
                "width_studs": 1,
                "depth_studs": 2,
                "height_plates": 3,
                "features": {"technic_holes": [{"axis": "x", "type": "pin"}]},
            },
            {
                "name": "technic_1x4",
                "width_studs": 1,
                "depth_studs": 4,
                "height_plates": 3,
                "features": {"technic_holes": [{"axis": "x", "type": "pin"}]},
            },
            {
                "name": "technic_1x6",
                "width_studs": 1,
                "depth_studs": 6,
                "height_plates": 3,
                "features": {"technic_holes": [{"axis": "x", "type": "pin"}]},
            },
            {
                "name": "technic_1x8",
                "width_studs": 1,
                "depth_studs": 8,
                "height_plates": 3,
                "features": {"technic_holes": [{"axis": "x", "type": "pin"}]},
            },
            {
                "name": "technic_1x12",
                "width_studs": 1,
                "depth_studs": 12,
                "height_plates": 3,
                "features": {"technic_holes": [{"axis": "x", "type": "pin"}]},
            },
        ],
        "tiles": [
            # Tiles (smooth tops)
            {
                "name": "tile_1x1",
                "width_studs": 1,
                "depth_studs": 1,
                "height_plates": 1,
                "features": {"studs": False},
            },
            {
                "name": "tile_1x2",
                "width_studs": 1,
                "depth_studs": 2,
                "height_plates": 1,
                "features": {"studs": False},
            },
            {
                "name": "tile_1x4",
                "width_studs": 1,
                "depth_studs": 4,
                "height_plates": 1,
                "features": {"studs": False},
            },
            {
                "name": "tile_2x2",
                "width_studs": 2,
                "depth_studs": 2,
                "height_plates": 1,
                "features": {"studs": False},
            },
            {
                "name": "tile_2x4",
                "width_studs": 2,
                "depth_studs": 4,
                "height_plates": 1,
                "features": {"studs": False},
            },
        ],
        "starter": [
            # Starter set - mix of essentials
            {"name": "brick_2x4", "width_studs": 2, "depth_studs": 4, "height_plates": 3},
            {"name": "brick_2x2", "width_studs": 2, "depth_studs": 2, "height_plates": 3},
            {"name": "brick_1x4", "width_studs": 1, "depth_studs": 4, "height_plates": 3},
            {"name": "plate_2x4", "width_studs": 2, "depth_studs": 4, "height_plates": 1},
            {"name": "plate_4x4", "width_studs": 4, "depth_studs": 4, "height_plates": 1},
            {
                "name": "slope_45_2x2",
                "width_studs": 2,
                "depth_studs": 2,
                "height_plates": 3,
                "features": {"slope": {"angle": 45, "direction": "front"}},
            },
            {
                "name": "tile_2x2",
                "width_studs": 2,
                "depth_studs": 2,
                "height_plates": 1,
                "features": {"studs": False},
            },
        ],
        "all_1x": [
            # All 1-wide bricks
            {"name": "brick_1x1", "width_studs": 1, "depth_studs": 1, "height_plates": 3},
            {"name": "brick_1x2", "width_studs": 1, "depth_studs": 2, "height_plates": 3},
            {"name": "brick_1x3", "width_studs": 1, "depth_studs": 3, "height_plates": 3},
            {"name": "brick_1x4", "width_studs": 1, "depth_studs": 4, "height_plates": 3},
            {"name": "brick_1x6", "width_studs": 1, "depth_studs": 6, "height_plates": 3},
            {"name": "brick_1x8", "width_studs": 1, "depth_studs": 8, "height_plates": 3},
            {"name": "brick_1x10", "width_studs": 1, "depth_studs": 10, "height_plates": 3},
            {"name": "brick_1x12", "width_studs": 1, "depth_studs": 12, "height_plates": 3},
        ],
    }

    return sets.get(set_type, sets["basic"])


def generate_grid_bricks(
    sizes: List[Tuple[int, int]], height_plates: int = 3, include_plates: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate bricks for a grid of sizes.

    Args:
        sizes: List of (width, depth) tuples
        height_plates: Height in plates
        include_plates: Also generate plates for each size

    Returns:
        List of brick definitions
    """
    bricks = []

    for width, depth in sizes:
        bricks.append(
            {
                "name": f"brick_{width}x{depth}",
                "width_studs": width,
                "depth_studs": depth,
                "height_plates": height_plates,
            }
        )

        if include_plates:
            bricks.append(
                {
                    "name": f"plate_{width}x{depth}",
                    "width_studs": width,
                    "depth_studs": depth,
                    "height_plates": 1,
                }
            )

    return bricks


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

BATCH_TOOLS = {
    "batch_create_bricks": {
        "description": """Create multiple LEGO bricks in a single batch operation.

Supports:
- Parallel or sequential execution
- Automatic retries on failure
- Progress tracking
- Detailed result reporting

Set types: basic, plates, slopes, technic, tiles, starter, all_1x""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_definitions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of brick definitions to create",
                },
                "set_type": {
                    "type": "string",
                    "enum": ["basic", "plates", "slopes", "technic", "tiles", "starter", "all_1x"],
                    "description": "OR use a predefined set type instead of definitions",
                },
                "parallel": {
                    "type": "boolean",
                    "default": False,
                    "description": "Execute in parallel",
                },
                "max_retries": {
                    "type": "integer",
                    "default": 3,
                    "description": "Maximum retries per brick",
                },
                "stop_on_error": {
                    "type": "boolean",
                    "default": False,
                    "description": "Stop batch on first error",
                },
            },
        },
    },
    "batch_export_stl": {
        "description": "Export multiple components to STL files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of component names to export",
                },
                "output_dir": {"type": "string", "description": "Output directory for STL files"},
                "refinement": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "ultra"],
                    "default": "medium",
                },
                "parallel": {"type": "boolean", "default": True},
            },
            "required": ["components", "output_dir"],
        },
    },
    "batch_slice": {
        "description": "Slice multiple STL files to G-code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stl_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of STL file paths",
                },
                "printer": {"type": "string", "description": "Printer profile name"},
                "quality": {
                    "type": "string",
                    "enum": ["draft", "normal", "quality", "ultra", "lego"],
                    "default": "lego",
                },
            },
            "required": ["stl_files", "printer"],
        },
    },
    "generate_brick_set": {
        "description": "Generate a predefined set of brick definitions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "set_type": {
                    "type": "string",
                    "enum": ["basic", "plates", "slopes", "technic", "tiles", "starter", "all_1x"],
                    "description": "Type of brick set to generate",
                }
            },
            "required": ["set_type"],
        },
    },
}
