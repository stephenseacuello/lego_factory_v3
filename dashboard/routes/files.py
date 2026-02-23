"""
Files Routes

File browser for generated STL, G-code, and preview files.
"""

from flask import Blueprint, render_template, request, jsonify, send_file, abort
from services.file_service import FileService

files_bp = Blueprint("files", __name__)


@files_bp.route("/")
@files_bp.route("/<path:directory>")
def browse(directory=""):
    """File browser page."""
    sort_by = request.args.get("sort", "name")
    sort_order = request.args.get("order", "asc")
    file_type = request.args.get("type")

    # Get files and directories
    result = FileService.list_files(
        directory=directory, file_type=file_type, sort_by=sort_by, sort_order=sort_order
    )

    # Get directory tree for sidebar
    tree = FileService.get_directory_tree()

    # Get storage stats
    stats = FileService.get_storage_stats()

    return render_template(
        "pages/files.html",
        files=result["files"],
        directories=result["directories"],
        current_path=directory,
        parent_path=result["parent"],
        tree=tree,
        stats=stats,
        sort_by=sort_by,
        sort_order=sort_order,
        file_type=file_type,
        total_files=result["total_files"],
        total_size=result["total_size_formatted"],
    )


@files_bp.route("/download/<path:file_path>")
def download(file_path):
    """Download a file."""
    full_path = FileService.get_file_path(file_path)

    if not full_path:
        abort(404)

    return send_file(full_path, as_attachment=True, download_name=full_path.name)


@files_bp.route("/view/<path:file_path>")
def view_file(file_path):
    """View file details."""
    file_info = FileService.get_file(file_path)

    if not file_info:
        abort(404)

    return render_template("pages/file_detail.html", file=file_info)


@files_bp.route("/preview/<path:file_path>")
def preview(file_path):
    """Get file for preview (STL, images)."""
    full_path = FileService.get_file_path(file_path)

    if not full_path:
        abort(404)

    return send_file(full_path)


@files_bp.route("/delete", methods=["POST"])
def delete_file():
    """Delete a file or directory."""
    data = request.get_json()
    file_path = data.get("path")

    if not file_path:
        return jsonify({"success": False, "error": "No path provided"})

    result = FileService.delete_file(file_path)
    return jsonify(result)


@files_bp.route("/mkdir", methods=["POST"])
def create_directory():
    """Create a new directory."""
    data = request.get_json()
    dir_path = data.get("path")

    if not dir_path:
        return jsonify({"success": False, "error": "No path provided"})

    result = FileService.create_directory(dir_path)
    return jsonify(result)


@files_bp.route("/stats")
def get_stats():
    """Get storage statistics."""
    stats = FileService.get_storage_stats()
    return jsonify(stats)


@files_bp.route("/clear", methods=["POST"])
def clear_files():
    """Clear files."""
    data = request.get_json() or {}
    file_type = data.get("type")

    result = FileService.clear_all(file_type=file_type)
    return jsonify(result)


@files_bp.route("/info/<path:file_path>")
def file_info(file_path):
    """Get file info as JSON."""
    file_info = FileService.get_file(file_path)

    if not file_info:
        return jsonify({"error": "File not found"}), 404

    return jsonify(file_info)
