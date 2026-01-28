# LEGO Part Numbering System

## Overview

This document describes the LEGO part numbering system used in LEGO Factory v3 for managing the product catalog, BOMs, routings, and manufacturing operations.

## Official LEGO Numbering

LEGO uses several numbering systems:

| System | Description | Example |
|--------|-------------|---------|
| **Design ID** | Unique mold/shape identifier | 3001 |
| **Element ID** | Design ID + Color | 300121 (red 2x4) |
| **Set Number** | Complete kit identifier | 10182 |

We use the **Design ID** as our base part number since it identifies the shape regardless of color or material.

---

## LEGO Unit System

### Standard Dimensions

| Unit | Metric | Imperial | Notes |
|------|--------|----------|-------|
| 1 Stud (LU) | 8.0 mm | 0.315" | Basic horizontal unit |
| 1 Plate Height | 3.2 mm | 0.126" | Basic vertical unit |
| 1 Brick Height | 9.6 mm | 0.378" | = 3 plates |
| Stud Diameter | 4.8 mm | 0.189" | Top connection |
| Stud Height | 1.8 mm | 0.071" | Above top surface |
| Wall Thickness | 1.5 mm | 0.059" | Standard wall |
| Anti-Stud ID | 4.8 mm | 0.189" | Bottom tube inner |
| Anti-Stud OD | 6.5 mm | 0.256" | Bottom tube outer |

### Dimension Formulas

```
Width (mm)  = studs_width × 8.0 - 0.2 (tolerance)
Length (mm) = studs_length × 8.0 - 0.2 (tolerance)
Height (mm) = height_plates × 3.2
Volume (mm³) ≈ Width × Length × Height × 0.3 (hollow factor)
Weight (g)  ≈ Volume × material_density
```

---

## SKU Format

### Structure

```
{LEGO_PART#}-{MATERIAL}-{COLOR}
```

### Examples

| SKU | Description |
|-----|-------------|
| `3001-ABS-RED` | 2x4 Brick, ABS Plastic, Red |
| `3001-ALU-RAW` | 2x4 Brick, Aluminum, Raw |
| `3020-PLA-BLU` | 2x4 Plate, PLA, Blue |
| `3040-PETG-YEL` | 1x2 Slope 45°, PETG, Yellow |
| `3700-ALU-RAW` | 1x2 Technic Brick, Aluminum |

---

## Part Categories

### Bricks (Standard Height = 3 plates)

| Part # | Name | L×W | Studs |
|--------|------|-----|-------|
| 3005 | Brick 1×1 | 1×1 | 1 |
| 3004 | Brick 1×2 | 1×2 | 2 |
| 3622 | Brick 1×3 | 1×3 | 3 |
| 3010 | Brick 1×4 | 1×4 | 4 |
| 3009 | Brick 1×6 | 1×6 | 6 |
| 3008 | Brick 1×8 | 1×8 | 8 |
| 3003 | Brick 2×2 | 2×2 | 4 |
| 3002 | Brick 2×3 | 2×3 | 6 |
| 3001 | Brick 2×4 | 2×4 | 8 |
| 2456 | Brick 2×6 | 2×6 | 12 |
| 3007 | Brick 2×8 | 2×8 | 16 |

### Plates (Height = 1 plate)

| Part # | Name | L×W | Studs |
|--------|------|-----|-------|
| 3024 | Plate 1×1 | 1×1 | 1 |
| 3023 | Plate 1×2 | 1×2 | 2 |
| 3623 | Plate 1×3 | 1×3 | 3 |
| 3710 | Plate 1×4 | 1×4 | 4 |
| 3666 | Plate 1×6 | 1×6 | 6 |
| 3460 | Plate 1×8 | 1×8 | 8 |
| 3022 | Plate 2×2 | 2×2 | 4 |
| 3021 | Plate 2×3 | 2×3 | 6 |
| 3020 | Plate 2×4 | 2×4 | 8 |
| 3795 | Plate 2×6 | 2×6 | 12 |
| 3034 | Plate 2×8 | 2×8 | 16 |

### Tiles (Plates without studs)

| Part # | Name | L×W |
|--------|------|-----|
| 3070 | Tile 1×1 | 1×1 |
| 3069 | Tile 1×2 | 1×2 |
| 63864 | Tile 1×3 | 1×3 |
| 2431 | Tile 1×4 | 1×4 |
| 3068 | Tile 2×2 | 2×2 |

### Slopes 45°

| Part # | Name | L×W | Run |
|--------|------|-----|-----|
| 54200 | Cheese Slope 1×1×2/3 | 1×1 | 2/3 |
| 3040 | Slope 45° 1×2 | 1×2 | 2 |
| 3039 | Slope 45° 2×2 | 2×2 | 2 |
| 3037 | Slope 45° 2×4 | 2×4 | 4 |

### Slopes 33° (Gentler)

| Part # | Name | L×W | Run |
|--------|------|-----|-----|
| 3298 | Slope 33° 2×3 | 2×3 | 3 |
| 3299 | Slope 33° 2×4 | 2×4 | 4 |

### Inverted Slopes

| Part # | Name | L×W |
|--------|------|-----|
| 3665 | Inverted Slope 45° 1×2 | 1×2 |
| 3660 | Inverted Slope 45° 2×2 | 2×2 |
| 3747 | Inverted Slope 45° 2×3 | 2×3 |

### Wedges

| Part # | Name | Side |
|--------|------|------|
| 43722 | Wedge 2×2 Right | Right |
| 43723 | Wedge 2×2 Left | Left |
| 41769 | Wedge 2×4 Right | Right |
| 41770 | Wedge 2×4 Left | Left |

### Technic (with holes)

| Part # | Name | Holes |
|--------|------|-------|
| 3700 | Technic Brick 1×2 | 1 |
| 3701 | Technic Brick 1×4 | 3 |
| 3702 | Technic Brick 1×8 | 7 |

---

## Materials

### Plastics (3D Printing)

| Code | Material | Process | Machine | Density | Notes |
|------|----------|---------|---------|---------|-------|
| ABS | ABS Plastic | FDM | bambu-ps1 | 1.04 g/cm³ | Closest to real LEGO |
| PLA | PLA Plastic | FDM | bambu-ps1 | 1.24 g/cm³ | Easy to print |
| PETG | PETG Plastic | FDM | bambu-ps1 | 1.27 g/cm³ | Durable |
| RES | Photopolymer Resin | SLA | - | 1.10 g/cm³ | High detail |

### Metals (CNC Machining)

| Code | Material | Process | Machine | Density | Notes |
|------|----------|---------|---------|---------|-------|
| ALU | 6061-T6 Aluminum | CNC Mill | bantam-explorer | 2.70 g/cm³ | Lightweight |
| BRS | 360 Brass | CNC Mill | bantam-explorer | 8.50 g/cm³ | Decorative |
| SST | 303 Stainless | CNC Mill | bantam-explorer | 8.00 g/cm³ | Corrosion resistant |

---

## Colors

### Standard LEGO Colors

| Code | Name | Hex | LEGO ID |
|------|------|-----|---------|
| RED | Bright Red | #C4281B | 21 |
| BLU | Bright Blue | #0055BF | 23 |
| YEL | Bright Yellow | #F2CD37 | 24 |
| GRN | Bright Green | #237841 | 28 |
| BLK | Black | #1B2A34 | 26 |
| WHT | White | #FFFFFF | 1 |
| ORG | Bright Orange | #FE8A18 | 106 |
| TAN | Tan | #E4CD9E | 5 |
| GRY | Light Bluish Gray | #A0A5A9 | 194 |
| DGY | Dark Bluish Gray | #6C6E68 | 199 |
| BRN | Reddish Brown | #582A12 | 192 |
| LBL | Light Blue | #9FC3E9 | 212 |
| PNK | Bright Pink | #E4ADC8 | 222 |
| LIM | Lime | #BBE90B | 119 |
| PRP | Medium Lavender | #AC78BA | 324 |

### Metal Finishes

| Code | Name | Notes |
|------|------|-------|
| RAW | Raw/Unfinished | Natural metal |
| ANO-RED | Anodized Red | Aluminum only |
| ANO-BLU | Anodized Blue | Aluminum only |
| ANO-BLK | Anodized Black | Aluminum only |
| POL | Polished | Mirror finish |
| BRS | Brushed | Satin finish |

---

## Routings

### 3D Print Routing (FDM)

| Seq | Operation | Machine | Setup | Run | Notes |
|-----|-----------|---------|-------|-----|-------|
| 10 | Slice Model | software | 0 | 2 min | Generate G-code |
| 20 | 3D Print | bambu-ps1 | 5 min | varies | Based on volume |
| 30 | Remove Supports | manual | 0 | 5 min | If needed |
| 40 | Quality Check | qc-station | 0 | 3 min | Visual + dimensional |
| 50 | Package | manual | 0 | 2 min | Bag + label |

**Print Time Estimation:**
```
print_time_min = (volume_mm3 / 1000) × 2.5 + layer_changes × 0.1
```

### CNC Routing (Aluminum)

| Seq | Operation | Machine | Setup | Run | Notes |
|-----|-----------|---------|-------|-----|-------|
| 10 | CAM Setup | software | 0 | 10 min | Generate toolpaths |
| 20 | Stock Prep | manual | 0 | 5 min | Cut bar stock |
| 30 | CNC Roughing | bantam-explorer | 10 min | 15 min | 0.5mm stepover |
| 40 | CNC Finishing | bantam-explorer | 2 min | 10 min | 0.1mm stepover |
| 50 | Deburr | manual | 0 | 5 min | Remove sharp edges |
| 60 | Quality Check | qc-station | 0 | 3 min | Dimensional check |
| 70 | Package | manual | 0 | 2 min | Wrap + label |

**CNC Time Estimation:**
```
roughing_time = volume_mm3 / 500  # mm³ per minute
finishing_time = surface_area_mm2 / 200  # mm² per minute
```

### Laser Engraving Routing

| Seq | Operation | Machine | Setup | Run | Notes |
|-----|-----------|---------|-------|-----|-------|
| 10 | Design Setup | software | 0 | 5 min | Prepare artwork |
| 20 | Laser Engrave | longer-ray-laser | 3 min | varies | Based on area |
| 30 | Clean | manual | 0 | 2 min | Remove residue |
| 40 | Quality Check | qc-station | 0 | 2 min | Visual inspection |

---

## Database Schema

### lego_parts (Master Catalog)

```sql
CREATE TABLE lego_parts (
    part_number VARCHAR(10) PRIMARY KEY,  -- "3001"
    name VARCHAR(100) NOT NULL,            -- "Brick 2x4"
    category VARCHAR(20) NOT NULL,         -- brick, plate, tile, slope, etc.
    subcategory VARCHAR(30),               -- slope_45, slope_33, inverted, etc.
    studs_length INT NOT NULL,             -- 4
    studs_width INT NOT NULL,              -- 2
    height_plates INT NOT NULL,            -- 3 (= 1 brick)
    has_studs BOOLEAN DEFAULT TRUE,
    has_holes BOOLEAN DEFAULT FALSE,
    hole_count INT DEFAULT 0,
    slope_angle DECIMAL(4,1),              -- 45.0, 33.0, etc.
    weight_grams DECIMAL(6,2),             -- Reference ABS weight
    volume_mm3 DECIMAL(10,2),
    fusion_design_id VARCHAR(100),         -- Link to Fusion 360
    thumbnail_url VARCHAR(500),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### products (Manufactured Variants)

```sql
CREATE TABLE products (
    sku VARCHAR(30) PRIMARY KEY,           -- "3001-ABS-RED"
    part_number VARCHAR(10) REFERENCES lego_parts(part_number),
    material VARCHAR(10) NOT NULL,         -- ABS, PLA, ALU, etc.
    color VARCHAR(10) NOT NULL,            -- RED, BLU, RAW, etc.
    routing_id INT REFERENCES routings(id),
    unit_cost DECIMAL(10,2),
    lead_time_days INT,
    min_order_qty INT DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    gcode_file VARCHAR(500),               -- Path to G-code
    stl_file VARCHAR(500),                 -- Path to STL
    step_file VARCHAR(500),                -- Path to STEP
    created_at TIMESTAMP DEFAULT NOW()
);
```

### bom_items (Bill of Materials)

```sql
CREATE TABLE bom_items (
    id SERIAL PRIMARY KEY,
    product_sku VARCHAR(30) REFERENCES products(sku),
    material_id VARCHAR(50) NOT NULL,      -- Raw material SKU
    quantity DECIMAL(10,4) NOT NULL,
    unit VARCHAR(20) NOT NULL,             -- grams, mm, ml, each
    notes TEXT
);
```

### routings (Process Templates)

```sql
CREATE TABLE routings (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,            -- "3D Print FDM Standard"
    process_type VARCHAR(20) NOT NULL,     -- fdm, cnc, sla, laser
    description TEXT,
    estimated_time_min INT,
    active BOOLEAN DEFAULT TRUE
);
```

### routing_operations (Steps in Routing)

```sql
CREATE TABLE routing_operations (
    id SERIAL PRIMARY KEY,
    routing_id INT REFERENCES routings(id),
    sequence INT NOT NULL,                 -- 10, 20, 30...
    operation_name VARCHAR(100) NOT NULL,
    operation_type VARCHAR(30),            -- setup, machining, manual, qc
    machine_id VARCHAR(50),                -- NULL for manual ops
    work_center_id VARCHAR(50),
    setup_time_min INT DEFAULT 0,
    run_time_min INT DEFAULT 0,
    instructions TEXT,
    gcode_template VARCHAR(500),
    UNIQUE(routing_id, sequence)
);
```

---

## Fusion 360 Integration

### MCP Tools Available

| Tool | Description |
|------|-------------|
| `create_brick` | Create parametric LEGO brick in Fusion 360 |
| `export_stl` | Export STL for 3D printing |
| `export_step` | Export STEP for CNC |
| `generate_cam` | Generate CAM toolpaths |
| `export_gcode` | Export G-code for machine |
| `get_thumbnail` | Get preview image |

### Workflow

1. **Design** - Create/modify brick in Fusion 360
2. **Export** - Generate STL (print) or STEP (CNC)
3. **Link** - Associate files with product SKU
4. **CAM** - Generate toolpaths (CNC only)
5. **G-code** - Export machine-ready code
6. **Manufacture** - Create work order, schedule jobs

---

## References

- [BrickLink Part Catalog](https://www.bricklink.com/catalogTree.asp?itemType=P)
- [LEGO Element IDs](https://rebrickable.com/parts/)
- [LEGO Dimensions Reference](https://www.mecabricks.com/en/help/measurements)
- [LEGO Color Reference](https://www.bricklink.com/catalogColors.asp)

---

*Document Version: 1.0*
*Last Updated: 2025-01-23*
*LEGO Factory v3*
