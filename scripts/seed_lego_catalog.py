#!/usr/bin/env python3
"""
LEGO Factory v3 - Seed LEGO Parts Catalog
==========================================
Seeds the database with 45 LEGO parts, materials, colors, and routings.

Usage:
    python scripts/seed_lego_catalog.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from config.database import get_db_session
from models.lego.parts_catalog import (
    PartCategory, MaterialType, ProcessType,
    LegoPart, LegoMaterial, LegoColor, LegoProduct,
    LegoProductBOM, LegoRouting, LegoRoutingOperation
)

# =============================================================================
# LEGO PARTS CATALOG (45 parts)
# =============================================================================

LEGO_PARTS = [
    # BRICKS (11 parts) - Height = 3 plates
    {"part_number": "3005", "name": "Brick 1x1", "category": PartCategory.BRICK, "studs_length": 1, "studs_width": 1, "height_plates": 3},
    {"part_number": "3004", "name": "Brick 1x2", "category": PartCategory.BRICK, "studs_length": 2, "studs_width": 1, "height_plates": 3},
    {"part_number": "3622", "name": "Brick 1x3", "category": PartCategory.BRICK, "studs_length": 3, "studs_width": 1, "height_plates": 3},
    {"part_number": "3010", "name": "Brick 1x4", "category": PartCategory.BRICK, "studs_length": 4, "studs_width": 1, "height_plates": 3},
    {"part_number": "3009", "name": "Brick 1x6", "category": PartCategory.BRICK, "studs_length": 6, "studs_width": 1, "height_plates": 3},
    {"part_number": "3008", "name": "Brick 1x8", "category": PartCategory.BRICK, "studs_length": 8, "studs_width": 1, "height_plates": 3},
    {"part_number": "3003", "name": "Brick 2x2", "category": PartCategory.BRICK, "studs_length": 2, "studs_width": 2, "height_plates": 3},
    {"part_number": "3002", "name": "Brick 2x3", "category": PartCategory.BRICK, "studs_length": 3, "studs_width": 2, "height_plates": 3},
    {"part_number": "3001", "name": "Brick 2x4", "category": PartCategory.BRICK, "studs_length": 4, "studs_width": 2, "height_plates": 3},
    {"part_number": "2456", "name": "Brick 2x6", "category": PartCategory.BRICK, "studs_length": 6, "studs_width": 2, "height_plates": 3},
    {"part_number": "3007", "name": "Brick 2x8", "category": PartCategory.BRICK, "studs_length": 8, "studs_width": 2, "height_plates": 3},

    # PLATES (11 parts) - Height = 1 plate
    {"part_number": "3024", "name": "Plate 1x1", "category": PartCategory.PLATE, "studs_length": 1, "studs_width": 1, "height_plates": 1},
    {"part_number": "3023", "name": "Plate 1x2", "category": PartCategory.PLATE, "studs_length": 2, "studs_width": 1, "height_plates": 1},
    {"part_number": "3623", "name": "Plate 1x3", "category": PartCategory.PLATE, "studs_length": 3, "studs_width": 1, "height_plates": 1},
    {"part_number": "3710", "name": "Plate 1x4", "category": PartCategory.PLATE, "studs_length": 4, "studs_width": 1, "height_plates": 1},
    {"part_number": "3666", "name": "Plate 1x6", "category": PartCategory.PLATE, "studs_length": 6, "studs_width": 1, "height_plates": 1},
    {"part_number": "3460", "name": "Plate 1x8", "category": PartCategory.PLATE, "studs_length": 8, "studs_width": 1, "height_plates": 1},
    {"part_number": "3022", "name": "Plate 2x2", "category": PartCategory.PLATE, "studs_length": 2, "studs_width": 2, "height_plates": 1},
    {"part_number": "3021", "name": "Plate 2x3", "category": PartCategory.PLATE, "studs_length": 3, "studs_width": 2, "height_plates": 1},
    {"part_number": "3020", "name": "Plate 2x4", "category": PartCategory.PLATE, "studs_length": 4, "studs_width": 2, "height_plates": 1},
    {"part_number": "3795", "name": "Plate 2x6", "category": PartCategory.PLATE, "studs_length": 6, "studs_width": 2, "height_plates": 1},
    {"part_number": "3034", "name": "Plate 2x8", "category": PartCategory.PLATE, "studs_length": 8, "studs_width": 2, "height_plates": 1},

    # TILES (5 parts) - Plates without studs, Height = 1 plate
    {"part_number": "3070", "name": "Tile 1x1", "category": PartCategory.TILE, "studs_length": 1, "studs_width": 1, "height_plates": 1, "has_studs": False},
    {"part_number": "3069", "name": "Tile 1x2", "category": PartCategory.TILE, "studs_length": 2, "studs_width": 1, "height_plates": 1, "has_studs": False},
    {"part_number": "63864", "name": "Tile 1x3", "category": PartCategory.TILE, "studs_length": 3, "studs_width": 1, "height_plates": 1, "has_studs": False},
    {"part_number": "2431", "name": "Tile 1x4", "category": PartCategory.TILE, "studs_length": 4, "studs_width": 1, "height_plates": 1, "has_studs": False},
    {"part_number": "3068", "name": "Tile 2x2", "category": PartCategory.TILE, "studs_length": 2, "studs_width": 2, "height_plates": 1, "has_studs": False},

    # SLOPES 45° (4 parts)
    {"part_number": "54200", "name": "Cheese Slope 1x1x2/3", "category": PartCategory.SLOPE_45, "studs_length": 1, "studs_width": 1, "height_plates": 2, "slope_angle": 45.0, "has_studs": False},
    {"part_number": "3040", "name": "Slope 45° 1x2", "category": PartCategory.SLOPE_45, "studs_length": 2, "studs_width": 1, "height_plates": 3, "slope_angle": 45.0},
    {"part_number": "3039", "name": "Slope 45° 2x2", "category": PartCategory.SLOPE_45, "studs_length": 2, "studs_width": 2, "height_plates": 3, "slope_angle": 45.0},
    {"part_number": "3037", "name": "Slope 45° 2x4", "category": PartCategory.SLOPE_45, "studs_length": 4, "studs_width": 2, "height_plates": 3, "slope_angle": 45.0},

    # SLOPES 33° (2 parts)
    {"part_number": "3298", "name": "Slope 33° 2x3", "category": PartCategory.SLOPE_33, "studs_length": 3, "studs_width": 2, "height_plates": 3, "slope_angle": 33.0},
    {"part_number": "3299", "name": "Slope 33° 2x4", "category": PartCategory.SLOPE_33, "studs_length": 4, "studs_width": 2, "height_plates": 3, "slope_angle": 33.0},

    # INVERTED SLOPES (3 parts)
    {"part_number": "3665", "name": "Inverted Slope 45° 1x2", "category": PartCategory.SLOPE_INVERTED, "studs_length": 2, "studs_width": 1, "height_plates": 3, "slope_angle": 45.0, "is_inverted": True},
    {"part_number": "3660", "name": "Inverted Slope 45° 2x2", "category": PartCategory.SLOPE_INVERTED, "studs_length": 2, "studs_width": 2, "height_plates": 3, "slope_angle": 45.0, "is_inverted": True},
    {"part_number": "3747", "name": "Inverted Slope 45° 2x3", "category": PartCategory.SLOPE_INVERTED, "studs_length": 3, "studs_width": 2, "height_plates": 3, "slope_angle": 45.0, "is_inverted": True},

    # WEDGES (4 parts)
    {"part_number": "43722", "name": "Wedge 2x2 Right", "category": PartCategory.WEDGE, "studs_length": 2, "studs_width": 2, "height_plates": 3, "side": "right"},
    {"part_number": "43723", "name": "Wedge 2x2 Left", "category": PartCategory.WEDGE, "studs_length": 2, "studs_width": 2, "height_plates": 3, "side": "left"},
    {"part_number": "41769", "name": "Wedge 2x4 Right", "category": PartCategory.WEDGE, "studs_length": 4, "studs_width": 2, "height_plates": 3, "side": "right"},
    {"part_number": "41770", "name": "Wedge 2x4 Left", "category": PartCategory.WEDGE, "studs_length": 4, "studs_width": 2, "height_plates": 3, "side": "left"},

    # TECHNIC (3 parts) - Bricks with holes
    {"part_number": "3700", "name": "Technic Brick 1x2", "category": PartCategory.TECHNIC, "studs_length": 2, "studs_width": 1, "height_plates": 3, "has_holes": True, "hole_count": 1},
    {"part_number": "3701", "name": "Technic Brick 1x4", "category": PartCategory.TECHNIC, "studs_length": 4, "studs_width": 1, "height_plates": 3, "has_holes": True, "hole_count": 3},
    {"part_number": "3702", "name": "Technic Brick 1x8", "category": PartCategory.TECHNIC, "studs_length": 8, "studs_width": 1, "height_plates": 3, "has_holes": True, "hole_count": 7},

    # SPECIAL (2 parts)
    {"part_number": "4070", "name": "Brick Modified 1x1 Headlight", "category": PartCategory.SPECIAL, "studs_length": 1, "studs_width": 1, "height_plates": 3, "subcategory": "modified"},
    {"part_number": "87087", "name": "Brick Modified 1x1 Stud on Side", "category": PartCategory.SPECIAL, "studs_length": 1, "studs_width": 1, "height_plates": 3, "subcategory": "modified"},
]

# =============================================================================
# MATERIALS
# =============================================================================

MATERIALS = [
    # PLASTICS (3D Printing - FDM)
    {
        "code": "ABS",
        "name": "ABS Plastic",
        "description": "Acrylonitrile Butadiene Styrene - closest to real LEGO material",
        "material_type": MaterialType.PLASTIC_FDM,
        "process_type": ProcessType.FDM,
        "default_machine_id": "bambu-ps1",
        "density_g_cm3": 1.04,
        "cost_per_gram": Decimal("0.025"),
        "process_params": {"nozzle_temp": 240, "bed_temp": 100, "print_speed": 60}
    },
    {
        "code": "PLA",
        "name": "PLA Plastic",
        "description": "Polylactic Acid - biodegradable, easy to print",
        "material_type": MaterialType.PLASTIC_FDM,
        "process_type": ProcessType.FDM,
        "default_machine_id": "bambu-ps1",
        "density_g_cm3": 1.24,
        "cost_per_gram": Decimal("0.020"),
        "process_params": {"nozzle_temp": 210, "bed_temp": 60, "print_speed": 70}
    },
    {
        "code": "PETG",
        "name": "PETG Plastic",
        "description": "Polyethylene Terephthalate Glycol - durable and flexible",
        "material_type": MaterialType.PLASTIC_FDM,
        "process_type": ProcessType.FDM,
        "default_machine_id": "bambu-ps1",
        "density_g_cm3": 1.27,
        "cost_per_gram": Decimal("0.028"),
        "process_params": {"nozzle_temp": 230, "bed_temp": 80, "print_speed": 55}
    },

    # PLASTICS (3D Printing - SLA)
    {
        "code": "RES",
        "name": "Photopolymer Resin",
        "description": "UV-curable resin for high-detail prints",
        "material_type": MaterialType.PLASTIC_SLA,
        "process_type": ProcessType.SLA,
        "default_machine_id": "formlabs-3",
        "density_g_cm3": 1.10,
        "cost_per_gram": Decimal("0.080"),
        "process_params": {"layer_height": 0.025, "exposure_time": 2.5}
    },

    # METALS (CNC Machining)
    {
        "code": "ALU",
        "name": "6061-T6 Aluminum",
        "description": "Lightweight aluminum alloy - aerospace grade",
        "material_type": MaterialType.METAL_CNC,
        "process_type": ProcessType.CNC_MILL,
        "default_machine_id": "bantam-explorer",
        "density_g_cm3": 2.70,
        "cost_per_gram": Decimal("0.015"),
        "process_params": {"spindle_speed": 12000, "feed_rate": 500, "depth_of_cut": 0.5}
    },
    {
        "code": "BRS",
        "name": "360 Brass",
        "description": "Free-machining brass - decorative finish",
        "material_type": MaterialType.METAL_CNC,
        "process_type": ProcessType.CNC_MILL,
        "default_machine_id": "bantam-explorer",
        "density_g_cm3": 8.50,
        "cost_per_gram": Decimal("0.035"),
        "process_params": {"spindle_speed": 8000, "feed_rate": 300, "depth_of_cut": 0.3}
    },
    {
        "code": "SST",
        "name": "303 Stainless Steel",
        "description": "Corrosion resistant stainless steel",
        "material_type": MaterialType.METAL_CNC,
        "process_type": ProcessType.CNC_MILL,
        "default_machine_id": "bantam-explorer",
        "density_g_cm3": 8.00,
        "cost_per_gram": Decimal("0.025"),
        "process_params": {"spindle_speed": 5000, "feed_rate": 150, "depth_of_cut": 0.2}
    },
]

# =============================================================================
# COLORS
# =============================================================================

COLORS = [
    # Standard LEGO Colors (for plastics)
    {"code": "RED", "name": "Bright Red", "hex_code": "#C4281B", "lego_id": 21, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "BLU", "name": "Bright Blue", "hex_code": "#0055BF", "lego_id": 23, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "YEL", "name": "Bright Yellow", "hex_code": "#F2CD37", "lego_id": 24, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "GRN", "name": "Bright Green", "hex_code": "#237841", "lego_id": 28, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "BLK", "name": "Black", "hex_code": "#1B2A34", "lego_id": 26, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "WHT", "name": "White", "hex_code": "#FFFFFF", "lego_id": 1, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "ORG", "name": "Bright Orange", "hex_code": "#FE8A18", "lego_id": 106, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "TAN", "name": "Tan", "hex_code": "#E4CD9E", "lego_id": 5, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "GRY", "name": "Light Bluish Gray", "hex_code": "#A0A5A9", "lego_id": 194, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "DGY", "name": "Dark Bluish Gray", "hex_code": "#6C6E68", "lego_id": 199, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "BRN", "name": "Reddish Brown", "hex_code": "#582A12", "lego_id": 192, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "LBL", "name": "Light Blue", "hex_code": "#9FC3E9", "lego_id": 212, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "PNK", "name": "Bright Pink", "hex_code": "#E4ADC8", "lego_id": 222, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "LIM", "name": "Lime", "hex_code": "#BBE90B", "lego_id": 119, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},
    {"code": "PRP", "name": "Medium Lavender", "hex_code": "#AC78BA", "lego_id": 324, "compatible_materials": ["ABS", "PLA", "PETG", "RES"]},

    # Metal Finishes
    {"code": "RAW", "name": "Raw/Unfinished", "is_metal_finish": True, "finish_type": "raw", "compatible_materials": ["ALU", "BRS", "SST"]},
    {"code": "ANO-RED", "name": "Anodized Red", "hex_code": "#8B0000", "is_metal_finish": True, "finish_type": "anodized", "compatible_materials": ["ALU"]},
    {"code": "ANO-BLU", "name": "Anodized Blue", "hex_code": "#00008B", "is_metal_finish": True, "finish_type": "anodized", "compatible_materials": ["ALU"]},
    {"code": "ANO-BLK", "name": "Anodized Black", "hex_code": "#1C1C1C", "is_metal_finish": True, "finish_type": "anodized", "compatible_materials": ["ALU"]},
    {"code": "POL", "name": "Polished", "is_metal_finish": True, "finish_type": "polished", "compatible_materials": ["ALU", "BRS", "SST"]},
    {"code": "BRU", "name": "Brushed", "is_metal_finish": True, "finish_type": "brushed", "compatible_materials": ["ALU", "BRS", "SST"]},
]

# =============================================================================
# ROUTINGS
# =============================================================================

ROUTINGS = [
    # FDM 3D Printing Routing
    {
        "routing_id": "FDM-STANDARD",
        "name": "FDM 3D Print Standard",
        "description": "Standard routing for FDM 3D printed parts",
        "process_type": ProcessType.FDM,
        "estimated_time_min": 68,
        "operations": [
            {"sequence": 10, "name": "Material Picking", "operation_type": "assembly", "machine_id": "niryo-ned2", "eligible_machines": ["niryo-ned2", "xarm-lite6"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot picks filament spool and loads build plate"},
            {"sequence": 20, "name": "FDM Printing", "operation_type": "printing_fdm", "machine_id": "bambu-ps1", "eligible_machines": ["bambu-ps1", "creality-cr30"], "setup_time_min": 5, "run_time_min": 45, "instructions": "Print part on Bambu Lab printer"},
            {"sequence": 30, "name": "Inspection", "operation_type": "inspection", "machine_id": "software", "eligible_machines": ["software"], "setup_time_min": 0, "run_time_min": 10, "instructions": "Automated vision inspection of printed part"},
            {"sequence": 40, "name": "Packaging", "operation_type": "packaging", "machine_id": "xarm-lite6", "eligible_machines": ["xarm-lite6", "niryo-ned2"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot bags and labels part"},
            {"sequence": 50, "name": "Shipping", "operation_type": "custom", "machine_id": "niryo-conveyor", "eligible_machines": ["niryo-conveyor"], "setup_time_min": 0, "run_time_min": 3, "instructions": "Conveyor moves packaged part to shipping area"},
        ]
    },

    # SLA Resin Printing Routing
    {
        "routing_id": "SLA-STANDARD",
        "name": "SLA Resin Print Standard",
        "description": "Standard routing for SLA resin printed parts",
        "process_type": ProcessType.SLA,
        "estimated_time_min": 113,
        "operations": [
            {"sequence": 10, "name": "Material Picking", "operation_type": "assembly", "machine_id": "niryo-ned2", "eligible_machines": ["niryo-ned2", "xarm-lite6"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot loads resin tray and build platform"},
            {"sequence": 20, "name": "SLA Printing", "operation_type": "printing_sla", "machine_id": "formlabs-3", "eligible_machines": ["formlabs-3"], "setup_time_min": 10, "run_time_min": 90, "instructions": "Print part on Form 3"},
            {"sequence": 30, "name": "Inspection", "operation_type": "inspection", "machine_id": "software", "eligible_machines": ["software"], "setup_time_min": 0, "run_time_min": 10, "instructions": "Automated vision inspection of printed part"},
            {"sequence": 40, "name": "Packaging", "operation_type": "packaging", "machine_id": "xarm-lite6", "eligible_machines": ["xarm-lite6", "niryo-ned2"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot bags and labels part"},
            {"sequence": 50, "name": "Shipping", "operation_type": "custom", "machine_id": "niryo-conveyor", "eligible_machines": ["niryo-conveyor"], "setup_time_min": 0, "run_time_min": 3, "instructions": "Conveyor moves packaged part to shipping area"},
        ]
    },

    # CNC Milling Routing
    {
        "routing_id": "CNC-STANDARD",
        "name": "CNC Mill Standard",
        "description": "Standard routing for CNC machined metal parts",
        "process_type": ProcessType.CNC_MILL,
        "estimated_time_min": 93,
        "operations": [
            {"sequence": 10, "name": "Material Picking", "operation_type": "assembly", "machine_id": "niryo-ned2", "eligible_machines": ["niryo-ned2", "xarm-lite6"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot loads stock material into fixture"},
            {"sequence": 20, "name": "CNC Milling - Top", "operation_type": "cnc_milling", "machine_id": "bantam-explorer", "eligible_machines": ["bantam-explorer", "coastrunner-cr1", "labfab-runner"], "setup_time_min": 5, "run_time_min": 30, "instructions": "Mill top face of part"},
            {"sequence": 30, "name": "Inspection - Top", "operation_type": "inspection", "machine_id": "software", "eligible_machines": ["software"], "setup_time_min": 0, "run_time_min": 10, "instructions": "Automated dimensional inspection of top face"},
            {"sequence": 40, "name": "CNC Milling - Bottom", "operation_type": "cnc_milling", "machine_id": "bantam-explorer", "eligible_machines": ["bantam-explorer", "coastrunner-cr1", "labfab-runner"], "setup_time_min": 5, "run_time_min": 30, "instructions": "Flip and mill bottom face of part"},
            {"sequence": 50, "name": "Inspection - Bottom", "operation_type": "inspection", "machine_id": "software", "eligible_machines": ["software"], "setup_time_min": 0, "run_time_min": 10, "instructions": "Automated dimensional inspection of bottom face"},
            {"sequence": 60, "name": "Packaging", "operation_type": "packaging", "machine_id": "xarm-lite6", "eligible_machines": ["xarm-lite6", "niryo-ned2"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot wraps and labels part"},
            {"sequence": 70, "name": "Shipping", "operation_type": "custom", "machine_id": "niryo-conveyor", "eligible_machines": ["niryo-conveyor"], "setup_time_min": 0, "run_time_min": 3, "instructions": "Conveyor moves packaged part to shipping area"},
        ]
    },

    # Laser Engraving Routing
    {
        "routing_id": "LASER-ENGRAVE",
        "name": "Laser Engraving",
        "description": "Routing for laser engraved parts",
        "process_type": ProcessType.LASER,
        "estimated_time_min": 28,
        "operations": [
            {"sequence": 10, "name": "Material Picking", "operation_type": "assembly", "machine_id": "niryo-ned2", "eligible_machines": ["niryo-ned2", "xarm-lite6"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot places workpiece on laser bed"},
            {"sequence": 20, "name": "Laser Engraving", "operation_type": "custom", "machine_id": "longer-ray-laser", "eligible_machines": ["longer-ray-laser"], "setup_time_min": 3, "run_time_min": 15, "instructions": "Engrave design on part surface"},
            {"sequence": 30, "name": "Inspection", "operation_type": "inspection", "machine_id": "software", "eligible_machines": ["software"], "setup_time_min": 0, "run_time_min": 10, "instructions": "Automated vision inspection of engraving"},
            {"sequence": 40, "name": "Packaging", "operation_type": "packaging", "machine_id": "xarm-lite6", "eligible_machines": ["xarm-lite6", "niryo-ned2"], "setup_time_min": 0, "run_time_min": 5, "instructions": "Robot bags and labels part"},
            {"sequence": 50, "name": "Shipping", "operation_type": "custom", "machine_id": "niryo-conveyor", "eligible_machines": ["niryo-conveyor"], "setup_time_min": 0, "run_time_min": 3, "instructions": "Conveyor moves packaged part to shipping area"},
        ]
    },
]


def seed_parts(session):
    """Seed LEGO parts catalog."""
    print("Seeding LEGO parts...")
    count = 0
    for part_data in LEGO_PARTS:
        existing = session.query(LegoPart).filter_by(part_number=part_data["part_number"]).first()
        if not existing:
            part = LegoPart(**part_data)
            part.calculate_dimensions()
            session.add(part)
            count += 1
    session.commit()
    print(f"  Added {count} parts")


def seed_materials(session):
    """Seed materials."""
    print("Seeding materials...")
    count = 0
    for mat_data in MATERIALS:
        existing = session.query(LegoMaterial).filter_by(code=mat_data["code"]).first()
        if not existing:
            material = LegoMaterial(**mat_data)
            session.add(material)
            count += 1
    session.commit()
    print(f"  Added {count} materials")


def seed_colors(session):
    """Seed colors."""
    print("Seeding colors...")
    count = 0
    for color_data in COLORS:
        existing = session.query(LegoColor).filter_by(code=color_data["code"]).first()
        if not existing:
            color = LegoColor(**color_data)
            session.add(color)
            count += 1
    session.commit()
    print(f"  Added {count} colors")


def seed_routings(session):
    """Seed routings and operations (upsert — replaces operations if routing exists)."""
    print("Seeding routings...")
    routing_count = 0
    op_count = 0

    for routing_data in ROUTINGS:
        routing_data = dict(routing_data)  # Don't mutate the original
        operations = routing_data.pop("operations", [])

        existing = session.query(LegoRouting).filter_by(routing_id=routing_data["routing_id"]).first()
        if existing:
            # Update routing fields
            for key, value in routing_data.items():
                if key != 'routing_id':
                    setattr(existing, key, value)
            # Delete old operations and replace
            session.query(LegoRoutingOperation).filter_by(routing_id=existing.routing_id).delete()
            session.flush()
            routing = existing
        else:
            routing = LegoRouting(**routing_data)
            session.add(routing)
            session.flush()

        for op_data in operations:
            op_data = dict(op_data)  # Don't mutate the original
            op_data["routing_id"] = routing.routing_id
            operation = LegoRoutingOperation(**op_data)
            session.add(operation)
            op_count += 1

        routing_count += 1

    session.commit()
    print(f"  Upserted {routing_count} routings with {op_count} operations")


def seed_sample_products(session):
    """Seed products by generating all valid Part + Material + Color combinations."""
    print("Seeding products (all valid SKU combinations)...")

    # Get all parts, materials, and colors from database
    parts = session.query(LegoPart).filter(LegoPart.is_active == True).all()
    materials = session.query(LegoMaterial).filter(LegoMaterial.is_active == True).all()
    colors = session.query(LegoColor).filter(LegoColor.is_active == True).all()

    if not parts or not materials or not colors:
        print("  Warning: Parts, materials, or colors not yet seeded. Skipping products.")
        return

    # Build a lookup of colors by compatible materials
    color_by_material = {}
    for color in colors:
        compatible = color.compatible_materials or []
        for mat_code in compatible:
            if mat_code not in color_by_material:
                color_by_material[mat_code] = []
            color_by_material[mat_code].append(color)

    # Determine routing based on material process type
    def get_routing_for_material(material):
        if material.process_type == ProcessType.FDM:
            return "FDM-STANDARD"
        elif material.process_type == ProcessType.SLA:
            return "SLA-STANDARD"
        elif material.process_type == ProcessType.CNC_MILL:
            return "CNC-STANDARD"
        elif material.process_type == ProcessType.LASER:
            return "LASER-ENGRAVE"
        return "FDM-STANDARD"

    count = 0
    skipped = 0

    # Generate all valid combinations
    for part in parts:
        for material in materials:
            # Get compatible colors for this material
            compatible_colors = color_by_material.get(material.code, [])
            if not compatible_colors:
                continue

            # For metals, only generate for Technic parts (precision parts)
            if material.material_type == MaterialType.METAL_CNC:
                if part.category not in [PartCategory.TECHNIC, PartCategory.SPECIAL]:
                    continue  # Skip non-technic parts for metal

            for color in compatible_colors:
                sku = LegoProduct.generate_sku(part.part_number, material.code, color.code)

                # Check if already exists
                existing = session.query(LegoProduct).filter_by(sku=sku).first()
                if existing:
                    skipped += 1
                    continue

                routing_id = get_routing_for_material(material)

                product = LegoProduct(
                    sku=sku,
                    part_number=part.part_number,
                    material_code=material.code,
                    color_code=color.code,
                    routing_id=routing_id,
                )

                # Calculate weight if volume is known
                if part.volume_mm3:
                    product.weight_grams = material.calculate_weight(part.volume_mm3)

                session.add(product)
                count += 1

                # Commit in batches to avoid memory issues
                if count % 100 == 0:
                    session.flush()

    session.commit()
    print(f"  Added {count} products ({skipped} already existed)")


def seed_sample_boms(session):
    """
    Seed BOMs for all products with realistic material requirements.

    BOM includes:
    - Primary material (filament/resin/metal stock)
    - Support material (for FDM/SLA if part requires supports)
    - Packaging materials (bag, label)
    """
    print("Seeding BOMs for all products...")

    # Get all products
    products = session.query(LegoProduct).all()
    bom_count = 0
    products_processed = 0

    # Packaging constants
    SMALL_BAG_WEIGHT_G = 0.5  # Small poly bag
    LARGE_BAG_WEIGHT_G = 1.0  # Large poly bag
    LABEL_WEIGHT_G = 0.3

    # Support material factors by part category
    SUPPORT_FACTORS = {
        PartCategory.SLOPE_45: 0.15,       # Slopes need supports for overhang
        PartCategory.SLOPE_33: 0.10,
        PartCategory.SLOPE_INVERTED: 0.20,  # Inverted slopes need more support
        PartCategory.WEDGE: 0.15,
        PartCategory.SPECIAL: 0.20,         # Special parts often need supports
        PartCategory.BRICK: 0.0,            # Standard bricks print supportless
        PartCategory.PLATE: 0.0,
        PartCategory.TILE: 0.0,
        PartCategory.TECHNIC: 0.05,         # Holes may need minimal support
    }

    for product in products:
        # Check if BOM already exists
        existing = session.query(LegoProductBOM).filter_by(product_sku=product.sku).first()
        if existing:
            continue

        # Get material and part info
        material = session.query(LegoMaterial).filter_by(code=product.material_code).first()
        part = session.query(LegoPart).filter_by(part_number=product.part_number).first()

        if not material or not part:
            continue

        # Calculate weight if not already set
        if not product.weight_grams and part.volume_mm3:
            product.weight_grams = material.calculate_weight(part.volume_mm3)
            session.add(product)

        if not product.weight_grams:
            # Estimate weight based on part dimensions if volume not available
            # Rough estimate: 0.5g per stud for solid parts
            estimated_volume = part.studs_length * part.studs_width * part.height_plates * 50  # mm³ per unit
            product.weight_grams = material.density_g_cm3 * estimated_volume / 1000
            if product.weight_grams < 0.5:
                product.weight_grams = 0.5  # Minimum weight
            session.add(product)

        sequence = 10

        # 1. Primary raw material
        waste_factor = 1.10 if material.process_type in (ProcessType.FDM, ProcessType.SLA) else 1.05
        bom_primary = LegoProductBOM(
            product_sku=product.sku,
            material_sku=f"RAW-{material.code}",
            material_name=f"{material.name} (Raw)",
            quantity=round(product.weight_grams * waste_factor, 2),
            unit="grams",
            sequence=sequence,
            notes=f"Primary material with {int((waste_factor-1)*100)}% waste allowance"
        )
        session.add(bom_primary)
        bom_count += 1
        sequence += 10

        # 2. Support material (for FDM/SLA with overhang parts)
        if material.process_type in (ProcessType.FDM, ProcessType.SLA):
            support_factor = SUPPORT_FACTORS.get(part.category, 0.0)
            # Additional support for inverted or sloped parts
            if getattr(part, 'is_inverted', False):
                support_factor += 0.10
            if getattr(part, 'slope_angle', 0) and part.slope_angle > 40:
                support_factor += 0.05

            if support_factor > 0:
                support_weight = round(product.weight_grams * support_factor, 2)
                if support_weight >= 0.1:  # Only add if meaningful amount
                    support_material = "PLA" if material.code == "PLA" else material.code
                    bom_support = LegoProductBOM(
                        product_sku=product.sku,
                        material_sku=f"SUP-{support_material}",
                        material_name=f"{support_material} Support Material",
                        quantity=support_weight,
                        unit="grams",
                        sequence=sequence,
                        notes="Support material for overhangs (removed during post-processing)"
                    )
                    session.add(bom_support)
                    bom_count += 1
                    sequence += 10

        # 3. Packaging - bag size based on part size
        is_large_part = (part.studs_length * part.studs_width >= 8) or (product.weight_grams > 10)
        bag_sku = "PKG-BAG-L" if is_large_part else "PKG-BAG-S"
        bag_name = "Large Poly Bag" if is_large_part else "Small Poly Bag"
        bag_qty = LARGE_BAG_WEIGHT_G if is_large_part else SMALL_BAG_WEIGHT_G

        bom_bag = LegoProductBOM(
            product_sku=product.sku,
            material_sku=bag_sku,
            material_name=bag_name,
            quantity=1,
            unit="each",
            sequence=sequence,
            notes=f"Protective packaging ({bag_qty}g)"
        )
        session.add(bom_bag)
        bom_count += 1
        sequence += 10

        # 4. Label
        bom_label = LegoProductBOM(
            product_sku=product.sku,
            material_sku="PKG-LABEL",
            material_name="Product Label",
            quantity=1,
            unit="each",
            sequence=sequence,
            notes=f"SKU label: {product.sku}"
        )
        session.add(bom_label)
        bom_count += 1

        products_processed += 1

        # Commit in batches
        if products_processed % 100 == 0:
            session.flush()
            print(f"    Processed {products_processed} products...")

    session.commit()
    print(f"  Added {bom_count} BOM entries for {products_processed} products")


def create_tables(force_recreate=False):
    """Create LEGO catalog tables if they don't exist."""
    print("Creating LEGO catalog tables...")
    try:
        from config.database import get_engine
        from sqlalchemy import text

        engine = get_engine()

        # Create tables using raw SQL to avoid conflicts with existing tables
        with engine.connect() as conn:
            # Check if we need to recreate tables (schema mismatch)
            # Check for process_type column in lego_materials to detect old schema
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = 'lego_materials' AND column_name = 'process_type'
                )
            """))
            has_correct_schema = result.scalar()

            # Check if lego_parts table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'lego_parts'
                )
            """))
            table_exists = result.scalar()

            # If tables exist but with wrong schema, drop them
            if table_exists and not has_correct_schema:
                print("  Detected old schema, dropping tables to recreate...")
                conn.execute(text("DROP TABLE IF EXISTS lego_product_bom CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS lego_products CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS lego_routing_operations CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS lego_routings CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS lego_colors CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS lego_materials CASCADE"))
                conn.execute(text("DROP TABLE IF EXISTS lego_parts CASCADE"))
                conn.commit()
                table_exists = False

            if not table_exists:
                print("  Creating LEGO catalog tables...")

                # Create lego_parts table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_parts (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        part_number VARCHAR(20) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        category VARCHAR(20) NOT NULL,
                        subcategory VARCHAR(50),
                        studs_length INTEGER NOT NULL,
                        studs_width INTEGER NOT NULL,
                        height_plates INTEGER NOT NULL,
                        has_studs BOOLEAN DEFAULT TRUE,
                        has_holes BOOLEAN DEFAULT FALSE,
                        hole_count INTEGER DEFAULT 0,
                        slope_angle FLOAT,
                        is_inverted BOOLEAN DEFAULT FALSE,
                        side VARCHAR(10),
                        width_mm FLOAT,
                        length_mm FLOAT,
                        height_mm FLOAT,
                        volume_mm3 FLOAT,
                        reference_weight_g FLOAT,
                        fusion_design_id VARCHAR(100),
                        stl_file VARCHAR(500),
                        step_file VARCHAR(500),
                        thumbnail_url VARCHAR(500),
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))

                # Create lego_materials table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_materials (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        code VARCHAR(10) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        material_type VARCHAR(20) NOT NULL,
                        process_type VARCHAR(20) NOT NULL,
                        default_machine_id VARCHAR(50),
                        density_g_cm3 FLOAT NOT NULL,
                        cost_per_gram NUMERIC(10,4),
                        cost_per_kg NUMERIC(10,2),
                        process_params JSONB DEFAULT '{}',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))

                # Create lego_colors table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_colors (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        code VARCHAR(10) UNIQUE NOT NULL,
                        name VARCHAR(50) NOT NULL,
                        hex_code VARCHAR(7),
                        lego_id INTEGER,
                        is_metal_finish BOOLEAN DEFAULT FALSE,
                        finish_type VARCHAR(30),
                        compatible_materials JSONB DEFAULT '[]',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))

                # Create lego_products table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_products (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        sku VARCHAR(50) UNIQUE NOT NULL,
                        part_number VARCHAR(20) REFERENCES lego_parts(part_number),
                        material_code VARCHAR(10) REFERENCES lego_materials(code),
                        color_code VARCHAR(10) REFERENCES lego_colors(code),
                        routing_id VARCHAR(50),
                        description TEXT,
                        weight_grams FLOAT,
                        unit_cost NUMERIC(10,2),
                        sell_price NUMERIC(10,2),
                        lead_time_hours INTEGER DEFAULT 24,
                        min_order_qty INTEGER DEFAULT 1,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))

                # Create lego_routings table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_routings (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        routing_id VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        process_type VARCHAR(20) NOT NULL,
                        estimated_time_min INTEGER,
                        is_active BOOLEAN DEFAULT TRUE,
                        revision VARCHAR(20) DEFAULT '1.0',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))

                # Create lego_routing_operations table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_routing_operations (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        routing_id VARCHAR(50) REFERENCES lego_routings(routing_id),
                        sequence INTEGER NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        operation_type VARCHAR(50),
                        work_center_id VARCHAR(50),
                        machine_id VARCHAR(50),
                        setup_time_min INTEGER DEFAULT 0,
                        run_time_min INTEGER DEFAULT 0,
                        instructions TEXT,
                        gcode_template VARCHAR(500),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100),
                        UNIQUE(routing_id, sequence)
                    )
                """))

                # Create lego_product_bom table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS lego_product_bom (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        product_sku VARCHAR(50) REFERENCES lego_products(sku),
                        material_sku VARCHAR(50),
                        material_name VARCHAR(100),
                        quantity NUMERIC(10,4) NOT NULL,
                        unit VARCHAR(20) DEFAULT 'each',
                        sequence INTEGER DEFAULT 10,
                        notes TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(100),
                        updated_by VARCHAR(100),
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        deleted_by VARCHAR(100)
                    )
                """))

                # Create indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_lego_parts_category ON lego_parts(category)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_lego_parts_part_number ON lego_parts(part_number)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_lego_products_sku ON lego_products(sku)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_lego_routings_routing_id ON lego_routings(routing_id)"))

                conn.commit()
                print("  LEGO catalog tables created successfully!")
            else:
                print("  LEGO catalog tables already exist")

        return True

    except Exception as e:
        print(f"  Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all seed functions."""
    print("\n" + "="*60)
    print("LEGO Factory v3 - Seeding Parts Catalog")
    print("="*60 + "\n")

    # Create tables first
    if not create_tables():
        print("\nFailed to create tables. Please check database connection.")
        print("Make sure PostgreSQL is running and DATABASE_URL is set correctly.")
        return 1

    try:
        with get_db_session() as session:
            seed_parts(session)
            seed_materials(session)
            seed_colors(session)
            seed_routings(session)
            seed_sample_products(session)
            seed_sample_boms(session)

            print("\n" + "="*60)
            print("Seeding complete!")
            print("="*60 + "\n")

            # Print summary
            print("Summary:")
            print(f"  Parts:     {session.query(LegoPart).count()}")
            print(f"  Materials: {session.query(LegoMaterial).count()}")
            print(f"  Colors:    {session.query(LegoColor).count()}")
            print(f"  Routings:  {session.query(LegoRouting).count()}")
            print(f"  Products:  {session.query(LegoProduct).count()}")
            print(f"  BOM Items: {session.query(LegoProductBOM).count()}")

    except Exception as e:
        print(f"\nError seeding database: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
