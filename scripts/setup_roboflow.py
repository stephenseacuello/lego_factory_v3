#!/usr/bin/env python3
"""
Roboflow Setup Script

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Sets up Roboflow workspace and projects for LEGO manufacturing.
"""

import os
import sys
import argparse
from pathlib import Path


def check_dependencies():
    """Check if required packages are installed."""
    missing = []

    try:
        import roboflow
    except ImportError:
        missing.append("roboflow")

    try:
        from ultralytics import YOLO
    except ImportError:
        missing.append("ultralytics")

    if missing:
        print("Missing dependencies. Install with:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def get_api_key():
    """Get Roboflow API key from environment or user input."""
    api_key = os.environ.get("ROBOFLOW_API_KEY")

    if not api_key:
        print("\nRoboflow API key not found in environment.")
        print("Get your API key from: https://app.roboflow.com/settings/api")
        api_key = input("\nEnter your Roboflow API key: ").strip()

        if api_key:
            # Offer to save to environment
            save = input("Save to ~/.bashrc? (y/n): ").strip().lower()
            if save == 'y':
                bashrc = Path.home() / ".bashrc"
                with open(bashrc, 'a') as f:
                    f.write(f'\nexport ROBOFLOW_API_KEY="{api_key}"\n')
                print(f"API key saved to {bashrc}")
                print("Run 'source ~/.bashrc' to load it.")

    return api_key


def setup_workspace(api_key: str, workspace_name: str = "legomcp"):
    """Set up Roboflow workspace."""
    print(f"\n{'='*60}")
    print("ROBOFLOW WORKSPACE SETUP")
    print(f"{'='*60}")

    try:
        from roboflow import Roboflow

        rf = Roboflow(api_key=api_key)

        # List existing workspaces
        print("\nConnecting to Roboflow...")
        workspace = rf.workspace()

        print(f"\nConnected to workspace: {workspace.name}")
        print(f"  URL: {workspace.url}")

        return rf, workspace

    except Exception as e:
        print(f"\nError connecting to Roboflow: {e}")
        print("\nTo create a new workspace:")
        print("  1. Go to https://app.roboflow.com")
        print("  2. Sign up / Sign in")
        print("  3. Create a new workspace")
        return None, None


def create_projects(rf, workspace):
    """Create LegoMCP projects in Roboflow."""
    print(f"\n{'='*60}")
    print("PROJECT SETUP")
    print(f"{'='*60}")

    projects_config = [
        {
            "name": "lego-bricks",
            "type": "object-detection",
            "description": "LEGO brick detection for manufacturing QC",
            "classes": [
                "brick_2x4", "brick_2x2", "brick_1x4", "brick_1x2", "brick_1x1",
                "plate_2x4", "plate_2x2", "plate_1x4", "plate_1x2",
                "slope_2x2", "slope_1x2", "tile_2x2", "tile_1x4",
                "technic_beam", "technic_pin", "technic_axle",
            ],
        },
        {
            "name": "print-defects",
            "type": "object-detection",
            "description": "3D print defect detection",
            "classes": [
                "layer_shift", "stringing", "warping", "under_extrusion",
                "over_extrusion", "z_wobble", "blob", "gap",
            ],
        },
        {
            "name": "surface-quality",
            "type": "classification",
            "description": "Surface quality classification",
            "classes": [
                "excellent", "good", "acceptable", "poor", "defective",
            ],
        },
    ]

    created_projects = []

    for config in projects_config:
        print(f"\nProject: {config['name']}")
        print(f"  Type: {config['type']}")
        print(f"  Classes: {len(config['classes'])}")

        try:
            # Check if project exists
            try:
                project = workspace.project(config['name'])
                print(f"  Status: Already exists")
            except Exception:
                # Create new project
                print(f"  Status: Creating...")
                project = workspace.create_project(
                    config['name'],
                    config['type'],
                    config['description']
                )
                print(f"  Status: Created")

            created_projects.append({
                "name": config['name'],
                "project": project,
                "classes": config['classes'],
            })

        except Exception as e:
            print(f"  Error: {e}")

    return created_projects


def setup_local_directories():
    """Create local directory structure for datasets."""
    print(f"\n{'='*60}")
    print("LOCAL DIRECTORY SETUP")
    print(f"{'='*60}")

    base_path = Path.cwd()
    directories = [
        "data/datasets/lego-bricks/images/train",
        "data/datasets/lego-bricks/images/valid",
        "data/datasets/lego-bricks/images/test",
        "data/datasets/lego-bricks/labels/train",
        "data/datasets/lego-bricks/labels/valid",
        "data/datasets/lego-bricks/labels/test",
        "data/datasets/print-defects/images/train",
        "data/datasets/print-defects/images/valid",
        "data/datasets/print-defects/images/test",
        "data/datasets/print-defects/labels/train",
        "data/datasets/print-defects/labels/valid",
        "data/datasets/print-defects/labels/test",
        "data/datasets/surface-quality/train",
        "data/datasets/surface-quality/valid",
        "data/datasets/surface-quality/test",
        "models/checkpoints",
        "models/exports/onnx",
        "models/exports/tensorrt",
        "models/exports/coreml",
    ]

    for dir_path in directories:
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {dir_path}")

    # Create data.yaml template for YOLO
    data_yaml_template = """# LEGO Bricks Dataset
# Auto-generated by setup_roboflow.py

path: ./data/datasets/lego-bricks
train: images/train
val: images/valid
test: images/test

# Classes
names:
  0: brick_2x4
  1: brick_2x2
  2: brick_1x4
  3: brick_1x2
  4: brick_1x1
  5: plate_2x4
  6: plate_2x2
  7: plate_1x4
  8: plate_1x2
  9: slope_2x2
  10: slope_1x2
  11: tile_2x2
  12: tile_1x4
  13: technic_beam
  14: technic_pin
  15: technic_axle

nc: 16
"""

    data_yaml_path = base_path / "data/datasets/lego-bricks/data.yaml"
    with open(data_yaml_path, 'w') as f:
        f.write(data_yaml_template)
    print(f"\n  Created: data/datasets/lego-bricks/data.yaml")


def print_next_steps():
    """Print next steps for the user."""
    print(f"\n{'='*60}")
    print("NEXT STEPS")
    print(f"{'='*60}")

    steps = """
1. COLLECT TRAINING DATA
   - Capture images of LEGO bricks in various lighting conditions
   - Capture images of 3D print defects
   - Aim for at least 100 images per class

2. ANNOTATE IN ROBOFLOW
   - Go to your project at https://app.roboflow.com
   - Upload images
   - Use the annotation tool to label objects
   - Create dataset version when ready

3. TRAIN MODEL
   Option A - Train in Roboflow:
     - Generate dataset version with augmentation
     - Start training in Roboflow
     - Download trained weights

   Option B - Train locally:
     - Export dataset in YOLOv8 format
     - Run: python scripts/train_model.py

4. INTEGRATE WITH LEGOMCP
   - Models are automatically loaded by vision services
   - Test with: python -c "from dashboard.services.vision import get_detector"

5. DEPLOY TO EDGE (Optional)
   - Export to TensorRT for Jetson
   - Export to CoreML for Apple devices
   - Export to ONNX for cross-platform

For detailed documentation, see:
  - docs/vision/training.md
  - docs/vision/deployment.md
"""
    print(steps)


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(
        description="Set up Roboflow for LegoMCP Vision AI"
    )
    parser.add_argument(
        "--skip-roboflow",
        action="store_true",
        help="Skip Roboflow setup, only create local directories"
    )
    parser.add_argument(
        "--workspace",
        default="legomcp",
        help="Roboflow workspace name"
    )

    args = parser.parse_args()

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║     LegoMCP Vision AI Setup - Roboflow Integration       ║
    ║                     Version 6.0                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    # Check dependencies
    print("Checking dependencies...")
    if not check_dependencies():
        print("\nInstall missing dependencies and run again.")
        print("  pip install roboflow ultralytics albumentations")
        # Continue anyway for local setup
        if not args.skip_roboflow:
            print("\nContinuing with local setup only...")
            args.skip_roboflow = True

    # Create local directories
    setup_local_directories()

    # Setup Roboflow if not skipped
    if not args.skip_roboflow:
        api_key = get_api_key()

        if api_key:
            rf, workspace = setup_workspace(api_key, args.workspace)

            if rf and workspace:
                projects = create_projects(rf, workspace)

                if projects:
                    print(f"\n{'='*60}")
                    print("SETUP COMPLETE")
                    print(f"{'='*60}")
                    print(f"\nCreated {len(projects)} projects in Roboflow")
        else:
            print("\nNo API key provided. Skipping Roboflow setup.")
    else:
        print("\nSkipped Roboflow setup (--skip-roboflow flag)")

    # Print next steps
    print_next_steps()

    print("\nSetup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
