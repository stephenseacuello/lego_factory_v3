# DefectDetection.msg - Detected quality defect from vision system
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Detection identification
string detection_id                # Unique detection ID
string inspection_id               # Parent inspection session ID
string part_id                     # Part being inspected
string work_order_id               # Associated work order

# Defect classification
string defect_type                 # Type: layer_shift, stringing, warping, under_extrusion,
                                   #       over_extrusion, blob, gap, crack, surface_roughness,
                                   #       dimensional_error, color_mismatch, contamination
string defect_category             # Category: structural, cosmetic, dimensional, material
float32 confidence                 # Detection confidence (0.0 - 1.0)

# Location
int32[4] bbox                      # Bounding box [x, y, width, height] in pixels
geometry_msgs/Point position_3d    # 3D position in part frame (if available)
int32 layer_number                 # Print layer where defect occurred
string affected_feature            # Affected feature (e.g., "stud_3", "wall_north")

# Severity assessment
uint8 severity                     # 1=cosmetic, 2=minor, 3=major, 4=critical
float32 defect_area_mm2            # Estimated defect area in mm²
float32 defect_depth_mm            # Estimated defect depth in mm

# Image data
string image_path                  # Path to inspection image
string crop_path                   # Path to cropped defect image
string heatmap_path                # Path to attention/saliency heatmap

# Analysis
string probable_cause              # AI-inferred probable cause
string[] recommended_actions       # Recommended corrective actions
float32 rework_probability         # Probability that rework will succeed

# Model information
string model_name                  # Detection model used
string model_version               # Model version

# Timestamps
builtin_interfaces/Time detected_at
