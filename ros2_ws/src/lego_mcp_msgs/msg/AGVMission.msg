# AGVMission.msg - AGV mission definition
# LEGO MCP Manufacturing System v7.0

# Mission identification
string mission_id                   # Unique mission identifier
string agv_id                       # Assigned AGV (empty for fleet assignment)
string fleet_id                     # Target fleet

# Mission type
uint8 TYPE_TRANSPORT = 0            # Point-to-point transport
uint8 TYPE_PICKUP = 1               # Pick up from station
uint8 TYPE_DELIVERY = 2             # Deliver to station
uint8 TYPE_CHARGE = 3               # Go to charging station
uint8 TYPE_PATROL = 4               # Patrol route
uint8 TYPE_RETURN_HOME = 5          # Return to home position
uint8 mission_type

# Priority
uint8 PRIORITY_LOW = 0
uint8 PRIORITY_NORMAL = 1
uint8 PRIORITY_HIGH = 2
uint8 PRIORITY_URGENT = 3
uint8 priority

# Waypoints
geometry_msgs/PoseStamped[] waypoints  # Ordered waypoints
string[] station_ids                # Station IDs to visit
float32[] dwell_times_sec           # Time to wait at each station

# Payload information
string payload_type                 # Expected payload type
string payload_id                   # Specific payload ID
float32 expected_weight_kg          # Expected payload weight

# Timing constraints
builtin_interfaces/Time requested_start  # Requested start time
builtin_interfaces/Time deadline    # Mission deadline
float32 max_duration_sec            # Maximum allowed duration

# Options
bool allow_rerouting                # Allow dynamic rerouting
bool require_confirmation           # Require pickup/delivery confirmation
bool return_to_origin               # Return to starting position after

# Associated work order
string work_order_id                # Related manufacturing work order
string job_id                       # Related job ID
