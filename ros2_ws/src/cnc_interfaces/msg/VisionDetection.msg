# VisionDetection.msg - Single YOLO/CV detection result
# Used for defects, tool wear, part presence, and safety detections

std_msgs/Header header

# Detection classification
string detection_type           # "defect", "tool_wear", "part", "safety", "ppe"
string class_name               # e.g., "scratch", "worn_edge", "hand", "person"
string class_id                 # Model class ID

# Confidence
float32 confidence              # 0.0-1.0

# Bounding box (normalized 0-1 coordinates)
float32 x_center
float32 y_center
float32 width
float32 height

# Bounding box (pixel coordinates)
uint32 x_min
uint32 y_min
uint32 x_max
uint32 y_max

# Segmentation mask (optional, for instance segmentation)
uint32 mask_width
uint32 mask_height
uint8[] mask                    # RLE or binary mask

# 3D position estimate (if depth available)
bool has_3d_position
float32 position_x              # mm from camera
float32 position_y              # mm from camera
float32 position_z              # mm (depth)
float32 distance_mm             # Euclidean distance from camera

# Model metadata
string model_id                 # Roboflow model ID (e.g., "cnc-defect-v2/1")
string model_version

# Context
string machine_id
string camera_id
uint32 frame_number
