# VisionDetectionArray.msg - Array of detections from a single frame
# Published by YOLO inference node

std_msgs/Header header

# Frame metadata
string frame_id                 # Camera frame ID
uint32 image_width
uint32 image_height
string image_encoding           # "rgb8", "bgr8", "mono8"

# Detections
VisionDetection[] detections

# Inference metadata
string model_id                 # Primary model used
string[] models_used            # All models if multi-model inference
float32 inference_time_ms       # Total inference time
float32 preprocessing_time_ms
float32 postprocessing_time_ms

# Camera metadata
string camera_id
string machine_id
uint32 frame_number

# Summary statistics
uint32 total_detections
uint32 defect_count
uint32 safety_count
uint32 part_count
float32 max_confidence
float32 avg_confidence
