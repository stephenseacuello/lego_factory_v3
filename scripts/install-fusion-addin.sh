#!/usr/bin/env bash
# Install the LegoMCP Fusion 360 add-in
# Usage: ./scripts/install-fusion-addin.sh [--symlink|--copy]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ADDIN_SRC="$REPO_ROOT/fusion360-addin/LegoMCP"

if [ ! -d "$ADDIN_SRC" ]; then
    echo "ERROR: Add-in source not found at $ADDIN_SRC"
    exit 1
fi

# Detect OS and set target
case "$(uname -s)" in
    Darwin*)
        ADDINS_DIR="$HOME/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns"
        ;;
    MINGW*|CYGWIN*|MSYS*)
        ADDINS_DIR="$APPDATA/Autodesk/Autodesk Fusion 360/API/AddIns"
        ;;
    *)
        echo "ERROR: Unsupported OS. Fusion 360 runs on macOS and Windows only."
        exit 1
        ;;
esac

ADDIN_DEST="$ADDINS_DIR/LegoMCP"
MODE="${1:---symlink}"

echo "Source:  $ADDIN_SRC"
echo "Target:  $ADDIN_DEST"
echo "Mode:    $MODE"
echo ""

mkdir -p "$ADDINS_DIR"

if [ "$MODE" = "--symlink" ]; then
    ln -sfn "$ADDIN_SRC" "$ADDIN_DEST"
    echo "Symlink created."
    echo "Changes to fusion360-addin/LegoMCP/ are reflected automatically after Fusion restart."
elif [ "$MODE" = "--copy" ]; then
    rm -rf "$ADDIN_DEST"
    cp -r "$ADDIN_SRC" "$ADDIN_DEST"
    echo "Files copied."
    echo "Note: Re-run this script after git pull to update."
else
    echo "Usage: $0 [--symlink|--copy]"
    echo "  --symlink  (default) Create symlink — repo changes auto-reflected"
    echo "  --copy     Copy files — must re-run after updates"
    exit 1
fi

echo ""
echo "Next steps:"
echo "  1. Open Fusion 360"
echo "  2. Go to Tools > Add-Ins (Shift+S)"
echo "  3. Find LegoMCP and click Run"
echo "  4. Verify: curl http://127.0.0.1:8767/health"
