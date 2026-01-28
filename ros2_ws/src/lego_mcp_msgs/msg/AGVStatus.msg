# AGVStatus.msg - Autonomous Guided Vehicle status
# LEGO MCP Manufacturing System v7.0
# Industry 4.0/5.0 Architecture - ISA-95 Compliant

# Header with timestamp
std_msgs/Header header

# AGV identification
string agv_id                       # Unique AGV identifier
string fleet_id                     # Fleet this AGV belongs to
string model                        # AGV model (e.g., "Alvik", "MiR100")

# Navigation state
uint8 NAV_STATE_IDLE = 0
uint8 NAV_STATE_NAVIGATING = 1
uint8 NAV_STATE_DOCKING = 2
uint8 NAV_STATE_CHARGING = 3
uint8 NAV_STATE_WAITING = 4
uint8 NAV_STATE_ERROR = 5
uint8 NAV_STATE_MANUAL = 6
uint8 NAV_STATE_EMERGENCY_STOP = 7
uint8 navigation_state

# Position (in map frame)
geometry_msgs/PoseStamped pose      # Current pose
geometry_msgs/Twist velocity        # Current velocity
float32 localization_score          # Localization confidence (0-1)

# Battery status
float32 battery_percent             # Battery level (0-100)
float32 battery_voltage             # Battery voltage
bool is_charging                    # Currently charging
float32 estimated_runtime_min       # Estimated remaining runtime

# Current mission
string current_mission_id           # Active mission ID (empty if none)
string current_task                 # Current task description
float32 mission_progress            # Mission progress (0-100)
string destination_station          # Target station name

# Safety
bool emergency_stop_active          # E-stop engaged
bool obstacle_detected              # Obstacle in path
float32 closest_obstacle_distance   # Distance to closest obstacle (m)
string[] active_safety_zones        # Active safety zone names

# Payload
bool has_payload                    # Currently carrying payload
string payload_type                 # Type of payload
float32 payload_weight_kg           # Payload weight

# Health metrics
float32 odometry_distance_m         # Total distance traveled
uint32 mission_count                # Total missions completed
uint32 error_count                  # Total errors
string last_error                   # Last error message
builtin_interfaces/Time last_error_time

# Connectivity
int32 wifi_rssi                     # WiFi signal strength (dBm)
float32 latency_ms                  # Communication latency
