#!/bin/bash
#
# LEGO MCP - Path Setup Script
#
# This script creates the necessary directory structure and symlinks
# so that Fusion 360 exports (which go to ~/Documents/LegoMCP/exports)
# are accessible to the Docker slicer service (which reads from ./output).
#
# Run this once after cloning the project:
#   chmod +x scripts/setup-paths.sh
#   ./scripts/setup-paths.sh
#

set -e

# Get project directory (parent of scripts/)
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXPORT_DIR="$HOME/Documents/LegoMCP/exports"

echo "LEGO MCP Path Setup"
echo "==================="
echo "Project directory: $PROJECT_DIR"
echo "Export directory:  $EXPORT_DIR"
echo ""

# Create project output directories
echo "Creating output directories..."
mkdir -p "$PROJECT_DIR/output/stl"
mkdir -p "$PROJECT_DIR/output/gcode/3dprint"
mkdir -p "$PROJECT_DIR/output/gcode/milling"
mkdir -p "$PROJECT_DIR/output/gcode/laser"

# Create LegoMCP exports base directory
echo "Creating Fusion 360 export directory..."
mkdir -p "$EXPORT_DIR"

# Remove existing symlinks or directories if they exist
if [ -L "$EXPORT_DIR/stl" ] || [ -d "$EXPORT_DIR/stl" ]; then
    echo "Removing existing stl link/directory..."
    rm -rf "$EXPORT_DIR/stl"
fi

if [ -L "$EXPORT_DIR/gcode" ] || [ -d "$EXPORT_DIR/gcode" ]; then
    echo "Removing existing gcode link/directory..."
    rm -rf "$EXPORT_DIR/gcode"
fi

# Create symlinks from Fusion 360 export location to project output
echo "Creating symlinks..."
ln -sf "$PROJECT_DIR/output/stl" "$EXPORT_DIR/stl"
ln -sf "$PROJECT_DIR/output/gcode" "$EXPORT_DIR/gcode"

echo ""
echo "Path setup complete!"
echo ""
echo "Fusion 360 exports will now be accessible to Docker:"
echo "  STL files:  $EXPORT_DIR/stl -> $PROJECT_DIR/output/stl"
echo "  G-code:     $EXPORT_DIR/gcode -> $PROJECT_DIR/output/gcode"
echo ""
echo "Docker slicer service mounts:"
echo "  ./output/stl -> /input/stl (read-only)"
echo "  ./output     -> /output (read-write)"
echo ""
echo "You can now run: docker-compose up -d"
