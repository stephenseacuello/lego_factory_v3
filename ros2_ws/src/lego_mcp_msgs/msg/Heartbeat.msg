# Heartbeat.msg - Node heartbeat status for OTP-style supervision
# LEGO MCP Manufacturing System v7.0
# Industry 4.0/5.0 Architecture - ISA-95 Compliant

# Header with timestamp
std_msgs/Header header

# Node identification
string node_name                    # ROS2 node name
string node_namespace               # ROS2 namespace
string node_id                      # Unique node identifier (UUID)

# Heartbeat sequence (for ordering/loss detection)
uint64 sequence_number              # Monotonically increasing sequence
uint64 missed_count                 # Number of missed heartbeats detected

# Node state
uint8 STATE_UNKNOWN = 0
uint8 STATE_STARTING = 1
uint8 STATE_RUNNING = 2
uint8 STATE_STOPPING = 3
uint8 STATE_STOPPED = 4
uint8 STATE_ERROR = 5
uint8 STATE_UNCONFIGURED = 10       # Lifecycle: unconfigured
uint8 STATE_INACTIVE = 11           # Lifecycle: inactive
uint8 STATE_ACTIVE = 12             # Lifecycle: active
uint8 STATE_FINALIZED = 13          # Lifecycle: finalized
uint8 state

# Health metrics
float32 cpu_percent                 # CPU usage percentage (0-100)
float32 memory_mb                   # Memory usage in MB
uint32 error_count                  # Cumulative error count
uint32 warning_count                # Cumulative warning count

# Timing information
builtin_interfaces/Time last_activity  # Last meaningful activity timestamp
float32 uptime_seconds              # Node uptime in seconds
float32 loop_rate_hz                # Actual main loop rate

# Diagnostic information
string[] active_topics              # Topics this node is publishing/subscribing
string[] active_services            # Services this node provides
bool has_pending_work               # Whether node has queued work
string status_message               # Human-readable status message

# ISA-95 layer information
uint8 ISA95_LEVEL_0 = 0             # Field devices
uint8 ISA95_LEVEL_1 = 1             # Control
uint8 ISA95_LEVEL_2 = 2             # Supervisory
uint8 ISA95_LEVEL_3 = 3             # MES/MOM
uint8 ISA95_LEVEL_4 = 4             # ERP
uint8 isa95_level
