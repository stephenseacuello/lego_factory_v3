# ChildStatus.msg - Supervised child node status
# LEGO MCP Manufacturing System v7.0
# OTP-style supervision for fault tolerance

# Child identification
string child_id                     # Unique child identifier
string node_name                    # ROS2 node name
string package_name                 # ROS2 package containing the node
string executable                   # Node executable name

# Child state
uint8 STATE_STOPPED = 0
uint8 STATE_STARTING = 1
uint8 STATE_RUNNING = 2
uint8 STATE_STOPPING = 3
uint8 STATE_FAILED = 4
uint8 STATE_RESTARTING = 5
uint8 state

# Restart configuration
uint8 RESTART_PERMANENT = 0         # Always restart
uint8 RESTART_TEMPORARY = 1         # Never restart
uint8 RESTART_TRANSIENT = 2         # Restart only on abnormal termination
uint8 restart_type

# Restart statistics
uint32 restart_count                # Number of restarts since supervisor start
uint32 restart_count_window         # Restarts within current window
builtin_interfaces/Time last_restart_time  # Time of last restart
float32 restart_window_sec          # Current restart window duration

# Health information
builtin_interfaces/Time last_heartbeat     # Last received heartbeat
float32 heartbeat_age_sec           # Seconds since last heartbeat
bool heartbeat_timeout              # True if heartbeat timed out
float32 cpu_percent                 # CPU usage
float32 memory_mb                   # Memory usage

# Lifecycle information (if lifecycle-managed)
bool is_lifecycle_managed           # Whether this is a lifecycle node
uint8 lifecycle_state               # Current lifecycle state (if applicable)
string lifecycle_state_name         # Human-readable lifecycle state

# Dependencies
string[] dependencies               # List of child_ids this node depends on
bool dependencies_satisfied         # True if all dependencies are running

# Error information
uint32 error_count                  # Total errors since start
string last_error_message           # Last error message
builtin_interfaces/Time last_error_time  # Time of last error

# Process information
int32 pid                           # Process ID (-1 if not running)
float32 uptime_sec                  # Process uptime in seconds
