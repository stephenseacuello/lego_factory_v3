# VisionStatus.msg - Vision system status and health

std_msgs/Header header

string machine_id

# Camera state
bool camera_connected
string camera_device            # /dev/video0
string camera_model
uint32 frame_width
uint32 frame_height
float32 fps_target
float32 fps_actual
float32 exposure_ms
bool auto_exposure

# Inference state
bool inference_running
bool inference_server_connected
string inference_server_url
string active_model             # Primary model ID
string[] loaded_models          # All loaded models

# Performance metrics
float32 avg_inference_time_ms
float32 max_inference_time_ms
float32 min_inference_time_ms
uint32 frames_processed
uint32 frames_dropped
float32 gpu_utilization         # 0-100 if available
float32 memory_usage_mb

# Detection summary (session)
uint32 total_detections
uint32 defect_detections
uint32 safety_detections
uint32 tool_wear_detections
uint32 part_detections

# Last detection info
builtin_interfaces/Time last_detection_time
string last_detection_class
float32 last_detection_confidence

# Health
uint8 HEALTH_OK = 0
uint8 HEALTH_DEGRADED = 1
uint8 HEALTH_CRITICAL = 2
uint8 HEALTH_OFFLINE = 3
uint8 health_status
string health_message
string[] active_warnings
