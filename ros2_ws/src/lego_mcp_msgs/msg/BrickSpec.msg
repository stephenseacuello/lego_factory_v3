# BrickSpec.msg - LEGO brick specification for manufacturing
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Brick identification
string brick_id                    # Unique brick ID (e.g., "brick-2x4-red")
string brick_type                  # Type classification (e.g., "basic", "technic", "plate")
string part_number                 # Official part number if applicable

# Dimensions (in mm, LEGO standard units)
float32 length                     # Length in studs (e.g., 4 for 2x4)
float32 width                      # Width in studs (e.g., 2 for 2x4)
float32 height                     # Height in plates (1 plate = 3.2mm, 1 brick = 3 plates)

# Physical properties
string color                       # Color name (e.g., "bright_red", "dark_bluish_gray")
string material                    # Material type (e.g., "ABS", "PLA", "resin")
float32 mass_grams                 # Expected mass in grams

# Manufacturing specifications
float32 stud_diameter              # Stud diameter in mm (nominal 4.8mm)
float32 stud_height                # Stud height in mm (nominal 1.8mm)
float32 wall_thickness             # Wall thickness in mm
float32 clutch_force_target        # Target clutch force in Newtons

# Tolerances
float32 dimensional_tolerance      # General dimensional tolerance in mm
float32 stud_tolerance             # Stud diameter tolerance in mm

# Metadata
string[] tags                      # Classification tags
string notes                       # Additional notes
