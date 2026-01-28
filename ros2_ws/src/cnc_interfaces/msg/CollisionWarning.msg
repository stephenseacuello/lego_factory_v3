# CollisionWarning.msg - Collision detection and path safety

std_msgs/Header header

string machine_id

# Collision type
uint8 COLLISION_NONE = 0
uint8 COLLISION_TOOL_WORKPIECE = 1
uint8 COLLISION_TOOL_FIXTURE = 2
uint8 COLLISION_TOOL_TABLE = 3
uint8 COLLISION_AXIS_LIMIT = 4
uint8 COLLISION_TOOL_HOLDER = 5
uint8 COLLISION_SPINDLE = 6
uint8 collision_type

# Severity
uint8 SEVERITY_SAFE = 0
uint8 SEVERITY_WARNING = 1      # Within warning distance
uint8 SEVERITY_CRITICAL = 2     # Imminent collision
uint8 SEVERITY_COLLISION = 3    # Collision detected
uint8 severity

# Position information
geometry_msgs/Point collision_point
geometry_msgs/Point current_position
geometry_msgs/Point target_position

# Distance metrics
float32 min_distance      # mm to nearest obstacle
float32 warning_distance  # Configured warning threshold
float32 stop_distance     # Configured stop threshold

# Object information
string obstacle_type      # "workpiece", "fixture", "clamp", "table"
string obstacle_id

# Path segment
uint32 gcode_line
string gcode_command
float32 path_progress     # 0.0-1.0

# Recommended action
uint8 ACTION_CONTINUE = 0
uint8 ACTION_REDUCE_SPEED = 1
uint8 ACTION_STOP = 2
uint8 ACTION_RETRACT = 3
uint8 ACTION_EMERGENCY_STOP = 4
uint8 recommended_action

string action_message
geometry_msgs/Point safe_retract_position
