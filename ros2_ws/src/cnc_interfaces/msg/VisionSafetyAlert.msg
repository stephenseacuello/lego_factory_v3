# VisionSafetyAlert.msg - Safety zone violation detected by vision system
# High-priority message for immediate safety response

std_msgs/Header header

string machine_id
string camera_id

# Alert levels
uint8 LEVEL_INFO = 0            # Object detected but outside zones
uint8 LEVEL_WARNING = 1         # Object in warning zone
uint8 LEVEL_CRITICAL = 2        # Object in critical zone
uint8 LEVEL_EMERGENCY = 3       # Immediate E-stop required
uint8 alert_level

# Alert classification
string alert_type               # "hand_detected", "person_detected", "object_intrusion", "ppe_missing"
string object_class             # Detected class name

# Zone information
string zone_name                # "work_envelope", "spindle_area", "fixture_zone", "tool_change"
string zone_id

# Detection details
float32 confidence              # Detection confidence
float32 distance_mm             # Estimated distance to hazard
float32 x_position              # Normalized position in frame
float32 y_position

# Motion context (from machine state at detection time)
bool machine_in_motion
float32 machine_velocity        # mm/min
string current_operation        # "cutting", "rapid", "idle", "homing"

# Response actions
bool requires_estop             # Immediate E-stop recommended
bool requires_pause             # Feed hold recommended
bool requires_warning           # Audio/visual warning
string recommended_action       # Human-readable recommendation

# Evidence
string snapshot_path            # Path to saved image
uint32 frame_number
builtin_interfaces/Time detection_time

# Tracking (for persistent intrusions)
string tracking_id              # UUID for tracking object across frames
uint32 consecutive_frames       # Frames object has been detected
float32 time_in_zone_seconds    # Time object has been in zone
