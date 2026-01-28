"""
File Service

Handles file browsing, management, and operations for generated files.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import mimetypes


class FileService:
    """Service for managing generated files (STL, G-code, previews)."""

    # Base output directory
    OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

    # Supported file types
    FILE_TYPES = {
        ".stl": {"type": "stl", "name": "STL Model", "icon": "📦", "preview": True},
        ".step": {"type": "step", "name": "STEP Model", "icon": "📐", "preview": False},
        ".stp": {"type": "step", "name": "STEP Model", "icon": "📐", "preview": False},
        ".3mf": {"type": "3mf", "name": "3MF Model", "icon": "🎨", "preview": False},
        ".obj": {"type": "obj", "name": "OBJ Model", "icon": "🔷", "preview": True},
        ".gcode": {"type": "gcode", "name": "G-Code", "icon": "🖨️", "preview": True},
        ".nc": {"type": "gcode", "name": "NC Code", "icon": "🔧", "preview": True},
        ".png": {"type": "image", "name": "PNG Image", "icon": "🖼️", "preview": True},
        ".jpg": {"type": "image", "name": "JPEG Image", "icon": "🖼️", "preview": True},
        ".jpeg": {"type": "image", "name": "JPEG Image", "icon": "🖼️", "preview": True},
    }

    @classmethod
    def set_output_dir(cls, path: str):
        """Set the output directory."""
        cls.OUTPUT_DIR = Path(path)

    @classmethod
    def get_directory_tree(cls) -> Dict[str, Any]:
        """Get the directory tree structure."""
        if not cls.OUTPUT_DIR.exists():
            return {"name": "output", "type": "directory", "children": []}

        def build_tree(path: Path, depth: int = 0) -> Dict[str, Any]:
            if depth > 5:  # Prevent infinite recursion
                return None

            node = {
                "name": path.name,
                "path": str(path.relative_to(cls.OUTPUT_DIR)),
                "type": "directory" if path.is_dir() else "file",
            }

            if path.is_dir():
                children = []
                try:
                    for child in sorted(path.iterdir()):
                        if child.name.startswith("."):
                            continue
                        child_node = build_tree(child, depth + 1)
                        if child_node:
                            children.append(child_node)
                except PermissionError:
                    pass
                node["children"] = children
            else:
                node["size"] = path.stat().st_size
                node["extension"] = path.suffix.lower()
                file_info = cls.FILE_TYPES.get(node["extension"], {})
                node["file_type"] = file_info.get("type", "unknown")
                node["icon"] = file_info.get("icon", "📄")

            return node

        return build_tree(cls.OUTPUT_DIR)

    @classmethod
    def list_files(
        cls,
        directory: str = "",
        file_type: str = None,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        List files in a directory.

        Args:
            directory: Relative path within output directory
            file_type: Filter by file type (stl, gcode, etc.)
            sort_by: Sort field (name, size, modified)
            sort_order: Sort order (asc, desc)
        """
        target_dir = cls.OUTPUT_DIR / directory if directory else cls.OUTPUT_DIR

        if not target_dir.exists():
            return {"files": [], "directories": [], "path": directory}

        files = []
        directories = []

        try:
            for item in target_dir.iterdir():
                if item.name.startswith("."):
                    continue

                if item.is_dir():
                    directories.append(
                        {
                            "name": item.name,
                            "path": str(item.relative_to(cls.OUTPUT_DIR)),
                            "type": "directory",
                            "icon": "📁",
                        }
                    )
                else:
                    ext = item.suffix.lower()
                    file_info = cls.FILE_TYPES.get(ext, {})

                    # Apply type filter
                    if file_type and file_info.get("type") != file_type:
                        continue

                    stat = item.stat()
                    files.append(
                        {
                            "name": item.name,
                            "path": str(item.relative_to(cls.OUTPUT_DIR)),
                            "type": "file",
                            "extension": ext,
                            "file_type": file_info.get("type", "unknown"),
                            "type_name": file_info.get("name", "File"),
                            "icon": file_info.get("icon", "📄"),
                            "size": stat.st_size,
                            "size_formatted": cls._format_size(stat.st_size),
                            "modified": stat.st_mtime,
                            "modified_formatted": cls._format_date(stat.st_mtime),
                            "can_preview": file_info.get("preview", False),
                        }
                    )
        except PermissionError:
            pass

        # Sort files
        reverse = sort_order == "desc"
        if sort_by == "name":
            files.sort(key=lambda f: f["name"].lower(), reverse=reverse)
            directories.sort(key=lambda d: d["name"].lower(), reverse=reverse)
        elif sort_by == "size":
            files.sort(key=lambda f: f["size"], reverse=reverse)
        elif sort_by == "modified":
            files.sort(key=lambda f: f["modified"], reverse=reverse)
        elif sort_by == "type":
            files.sort(key=lambda f: f["file_type"], reverse=reverse)

        return {
            "files": files,
            "directories": directories,
            "path": directory,
            "parent": str(Path(directory).parent) if directory else None,
            "total_files": len(files),
            "total_size": sum(f["size"] for f in files),
            "total_size_formatted": cls._format_size(sum(f["size"] for f in files)),
        }

    @classmethod
    def get_file(cls, file_path: str) -> Optional[Dict[str, Any]]:
        """Get file details."""
        full_path = cls.OUTPUT_DIR / file_path

        if not full_path.exists() or not full_path.is_file():
            return None

        ext = full_path.suffix.lower()
        file_info = cls.FILE_TYPES.get(ext, {})
        stat = full_path.stat()

        return {
            "name": full_path.name,
            "path": file_path,
            "full_path": str(full_path),
            "extension": ext,
            "file_type": file_info.get("type", "unknown"),
            "type_name": file_info.get("name", "File"),
            "icon": file_info.get("icon", "📄"),
            "size": stat.st_size,
            "size_formatted": cls._format_size(stat.st_size),
            "modified": stat.st_mtime,
            "modified_formatted": cls._format_date(stat.st_mtime),
            "created": stat.st_ctime,
            "created_formatted": cls._format_date(stat.st_ctime),
            "can_preview": file_info.get("preview", False),
            "mime_type": mimetypes.guess_type(str(full_path))[0],
        }

    @classmethod
    def get_file_path(cls, file_path: str) -> Optional[Path]:
        """Get the full filesystem path for a file."""
        full_path = cls.OUTPUT_DIR / file_path
        if full_path.exists() and full_path.is_file():
            return full_path
        return None

    @classmethod
    def delete_file(cls, file_path: str) -> Dict[str, Any]:
        """Delete a file."""
        full_path = cls.OUTPUT_DIR / file_path

        if not full_path.exists():
            return {"success": False, "error": "File not found"}

        # Security check - ensure within output directory
        try:
            full_path.relative_to(cls.OUTPUT_DIR)
        except ValueError:
            return {"success": False, "error": "Invalid path"}

        try:
            if full_path.is_dir():
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
            return {"success": True, "deleted": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def create_directory(cls, dir_path: str) -> Dict[str, Any]:
        """Create a new directory."""
        full_path = cls.OUTPUT_DIR / dir_path

        # Security check
        try:
            full_path.relative_to(cls.OUTPUT_DIR)
        except ValueError:
            return {"success": False, "error": "Invalid path"}

        try:
            full_path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "created": dir_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def get_storage_stats(cls) -> Dict[str, Any]:
        """Get storage statistics."""
        total_size = 0
        file_count = 0
        type_counts = {}

        if cls.OUTPUT_DIR.exists():
            for file_path in cls.OUTPUT_DIR.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    file_count += 1
                    size = file_path.stat().st_size
                    total_size += size

                    ext = file_path.suffix.lower()
                    file_type = cls.FILE_TYPES.get(ext, {}).get("type", "other")
                    if file_type not in type_counts:
                        type_counts[file_type] = {"count": 0, "size": 0}
                    type_counts[file_type]["count"] += 1
                    type_counts[file_type]["size"] += size

        return {
            "total_files": file_count,
            "total_size": total_size,
            "total_size_formatted": cls._format_size(total_size),
            "by_type": type_counts,
        }

    @classmethod
    def clear_all(cls, file_type: str = None) -> Dict[str, Any]:
        """Clear all files, optionally filtered by type."""
        deleted = 0
        errors = []

        if cls.OUTPUT_DIR.exists():
            for file_path in cls.OUTPUT_DIR.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    ext = file_path.suffix.lower()
                    ft = cls.FILE_TYPES.get(ext, {}).get("type")

                    if file_type and ft != file_type:
                        continue

                    try:
                        file_path.unlink()
                        deleted += 1
                    except Exception as e:
                        errors.append(f"{file_path.name}: {e}")

        return {"success": len(errors) == 0, "deleted": deleted, "errors": errors}

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @staticmethod
    def _format_date(timestamp: float) -> str:
        """Format timestamp in human-readable format."""
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()

        if dt.date() == now.date():
            return dt.strftime("Today %H:%M")
        elif (now - dt).days == 1:
            return dt.strftime("Yesterday %H:%M")
        elif (now - dt).days < 7:
            return dt.strftime("%A %H:%M")
        else:
            return dt.strftime("%Y-%m-%d %H:%M")


# Singleton instance
file_service = FileService()
