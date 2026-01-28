"""
Batch Operations for LEGO Brick Manufacturing

Provides functionality to:
- Create multiple bricks at once
- Export multiple bricks in multiple formats
- Generate G-code for multiple bricks
- Process brick sets from files
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import asyncio


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class BatchJob:
    """A batch processing job."""

    id: str
    name: str
    created_at: datetime
    status: str = "pending"  # pending, running, completed, failed
    progress: float = 0.0
    items_total: int = 0
    items_completed: int = 0
    items_failed: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "progress": self.progress,
            "items_total": self.items_total,
            "items_completed": self.items_completed,
            "items_failed": self.items_failed,
            "results": self.results,
            "errors": self.errors,
        }


@dataclass
class BrickSpec:
    """Specification for a brick to create in batch."""

    name: str
    width: int
    depth: int
    height_plates: int = 3
    brick_type: str = "standard"
    features: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# BATCH MANAGER
# ============================================================================


class BatchManager:
    """
    Manages batch processing jobs for LEGO brick operations.
    """

    def __init__(self):
        self._jobs: Dict[str, BatchJob] = {}
        self._job_counter = 0

    def _generate_job_id(self) -> str:
        """Generate unique job ID."""
        self._job_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"batch_{timestamp}_{self._job_counter}"

    def create_job(self, name: str, items_total: int) -> BatchJob:
        """Create a new batch job."""
        job_id = self._generate_job_id()
        job = BatchJob(id=job_id, name=name, created_at=datetime.now(), items_total=items_total)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, status: Optional[str] = None) -> List[BatchJob]:
        """List all jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def update_progress(self, job_id: str, completed: int, failed: int = 0):
        """Update job progress."""
        job = self._jobs.get(job_id)
        if job:
            job.items_completed = completed
            job.items_failed = failed
            job.progress = (completed + failed) / job.items_total if job.items_total > 0 else 0

    def complete_job(self, job_id: str, results: List[Dict[str, Any]], errors: List[str] = None):
        """Mark job as completed."""
        job = self._jobs.get(job_id)
        if job:
            job.status = "completed" if not errors else "completed_with_errors"
            job.results = results
            job.errors = errors or []
            job.progress = 1.0


# ============================================================================
# BATCH OPERATIONS
# ============================================================================


async def batch_create_bricks(
    brick_specs: List[BrickSpec], fusion_client: Any, on_progress: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Create multiple bricks in batch.

    Args:
        brick_specs: List of brick specifications
        fusion_client: Fusion 360 client
        on_progress: Optional callback(current, total, brick_name)

    Returns:
        Batch result with created bricks and any errors
    """
    results = []
    errors = []
    total = len(brick_specs)

    for i, spec in enumerate(brick_specs):
        try:
            # Build brick definition
            from custom_brick_builder import CustomBrickBuilder

            builder = CustomBrickBuilder()
            builder.set_base(spec.width, spec.depth, spec.height_plates)

            # Apply features
            if spec.features.get("hollow", True):
                builder.hollow_bottom()
            else:
                builder.solid_bottom()

            if spec.features.get("studs", True):
                builder.add_studs()

            if spec.features.get("tubes", True) and spec.width >= 2 and spec.depth >= 2:
                builder.add_tubes()

            brick_def = builder.build(spec.name)

            # Create in Fusion 360
            result = await fusion_client.create_brick(brick_def)

            results.append(
                {
                    "name": spec.name,
                    "success": result.get("success", False),
                    "component_name": result.get("component_name"),
                    "error": result.get("error"),
                }
            )

        except Exception as e:
            results.append({"name": spec.name, "success": False, "error": str(e)})
            errors.append(f"{spec.name}: {str(e)}")

        if on_progress:
            on_progress(i + 1, total, spec.name)

    successful = sum(1 for r in results if r.get("success"))

    return {
        "total": total,
        "successful": successful,
        "failed": total - successful,
        "results": results,
        "errors": errors,
    }


async def batch_export(
    components: List[str],
    output_dir: str,
    formats: List[str],
    fusion_client: Any,
    on_progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Export multiple components in multiple formats.

    Args:
        components: List of component names
        output_dir: Output directory
        formats: List of format names (stl, step, 3mf, obj)
        fusion_client: Fusion 360 client
        on_progress: Optional callback(current, total, component, format)

    Returns:
        Batch export results
    """
    from tools.export_tools import EXPORT_FORMATS

    results = []
    errors = []

    # Calculate total operations
    total = len(components) * len(formats)
    current = 0

    for component in components:
        for fmt in formats:
            current += 1

            if fmt not in EXPORT_FORMATS:
                errors.append(f"Unknown format: {fmt}")
                continue

            ext = EXPORT_FORMATS[fmt]["extension"]
            output_path = os.path.join(output_dir, f"{component}{ext}")

            try:
                if fmt == "stl":
                    result = await fusion_client.export_stl(component, output_path)
                elif fmt == "step":
                    result = await fusion_client.export_step(component, output_path)
                elif fmt == "3mf":
                    result = await fusion_client.export_3mf(component, output_path)
                else:
                    result = await fusion_client.export_generic(component, output_path, fmt)

                results.append(
                    {
                        "component": component,
                        "format": fmt,
                        "path": output_path,
                        "success": result.get("success", False),
                        "error": result.get("error"),
                    }
                )

            except Exception as e:
                results.append(
                    {"component": component, "format": fmt, "success": False, "error": str(e)}
                )
                errors.append(f"{component}.{fmt}: {str(e)}")

            if on_progress:
                on_progress(current, total, component, fmt)

    successful = sum(1 for r in results if r.get("success"))

    return {
        "total": total,
        "successful": successful,
        "failed": total - successful,
        "results": results,
        "errors": errors,
    }


async def batch_slice(
    stl_files: List[str],
    printer: str,
    material: str,
    quality: str,
    slicer_client: Any,
    on_progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Slice multiple STL files to G-code.

    Args:
        stl_files: List of STL file paths
        printer: Printer profile
        material: Material profile
        quality: Quality preset
        slicer_client: Slicer service client
        on_progress: Optional callback

    Returns:
        Batch slicing results
    """
    results = []
    errors = []
    total = len(stl_files)

    for i, stl_path in enumerate(stl_files):
        try:
            result = await slicer_client.slice(stl_path, printer, quality)

            results.append(
                {
                    "input": stl_path,
                    "output": result.get("path"),
                    "success": result.get("success", False),
                    "time_min": result.get("estimated_time_min"),
                    "error": result.get("error"),
                }
            )

        except Exception as e:
            results.append({"input": stl_path, "success": False, "error": str(e)})
            errors.append(f"{stl_path}: {str(e)}")

        if on_progress:
            on_progress(i + 1, total, stl_path)

    successful = sum(1 for r in results if r.get("success"))
    total_time = sum(r.get("time_min", 0) for r in results if r.get("success"))

    return {
        "total": total,
        "successful": successful,
        "failed": total - successful,
        "total_print_time_min": total_time,
        "results": results,
        "errors": errors,
    }


# ============================================================================
# BRICK SET PROCESSING
# ============================================================================


def load_brick_set(filepath: str) -> List[BrickSpec]:
    """
    Load brick specifications from a JSON file.

    Expected format:
    {
        "name": "My Brick Set",
        "bricks": [
            {"name": "brick1", "width": 2, "depth": 4},
            {"name": "brick2", "width": 1, "depth": 2, "height_plates": 1}
        ]
    }
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    bricks = []
    for brick_data in data.get("bricks", []):
        bricks.append(
            BrickSpec(
                name=brick_data.get("name", "unnamed"),
                width=brick_data.get("width", 2),
                depth=brick_data.get("depth", 2),
                height_plates=brick_data.get("height_plates", 3),
                brick_type=brick_data.get("type", "standard"),
                features=brick_data.get("features", {}),
            )
        )

    return bricks


def save_batch_results(filepath: str, results: Dict[str, Any]):
    """Save batch results to a JSON file."""
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2, default=str)


# ============================================================================
# PREDEFINED BRICK SETS
# ============================================================================


def get_basic_brick_set() -> List[BrickSpec]:
    """Get a basic set of common LEGO bricks."""
    return [
        BrickSpec("brick_1x1", 1, 1, 3),
        BrickSpec("brick_1x2", 1, 2, 3),
        BrickSpec("brick_1x4", 1, 4, 3),
        BrickSpec("brick_2x2", 2, 2, 3),
        BrickSpec("brick_2x4", 2, 4, 3),
        BrickSpec("brick_2x6", 2, 6, 3),
        BrickSpec("plate_1x2", 1, 2, 1),
        BrickSpec("plate_2x4", 2, 4, 1),
        BrickSpec("tile_1x2", 1, 2, 1, features={"studs": False}),
        BrickSpec("tile_2x2", 2, 2, 1, features={"studs": False}),
    ]


def get_technic_brick_set() -> List[BrickSpec]:
    """Get a set of Technic bricks."""
    return [
        BrickSpec(
            "technic_1x2", 1, 2, 3, "technic", {"technic_holes": {"axis": "x", "type": "pin"}}
        ),
        BrickSpec(
            "technic_1x4", 1, 4, 3, "technic", {"technic_holes": {"axis": "x", "type": "pin"}}
        ),
        BrickSpec(
            "technic_1x6", 1, 6, 3, "technic", {"technic_holes": {"axis": "x", "type": "pin"}}
        ),
        BrickSpec(
            "technic_1x8", 1, 8, 3, "technic", {"technic_holes": {"axis": "x", "type": "pin"}}
        ),
    ]


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

BATCH_TOOLS = {
    "batch_create_bricks": {
        "description": """Create multiple LEGO bricks in a single operation.

Provide a list of brick specifications and all will be created in Fusion 360.
Useful for creating sets of related bricks.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bricks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "width": {"type": "integer"},
                            "depth": {"type": "integer"},
                            "height_plates": {"type": "integer", "default": 3},
                            "type": {"type": "string", "default": "standard"},
                            "features": {"type": "object"},
                        },
                        "required": ["name", "width", "depth"],
                    },
                    "description": "List of brick specifications",
                }
            },
            "required": ["bricks"],
        },
    },
    "batch_export": {
        "description": "Export multiple components in multiple formats.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of component names",
                },
                "output_dir": {"type": "string", "description": "Output directory"},
                "formats": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["stl"],
                    "description": "Export formats (stl, step, 3mf, obj)",
                },
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
                "printer": {"type": "string", "description": "Printer profile"},
                "material": {"type": "string", "default": "pla"},
                "quality": {"type": "string", "default": "fine"},
            },
            "required": ["stl_files", "printer"],
        },
    },
    "create_basic_brick_set": {
        "description": "Create a set of 10 basic/common LEGO bricks.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "list_batch_jobs": {
        "description": "List all batch jobs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "completed", "failed"],
                    "description": "Filter by status (optional)",
                }
            },
        },
    },
}
