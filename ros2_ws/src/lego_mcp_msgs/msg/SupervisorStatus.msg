# SupervisorStatus.msg - OTP-style supervisor status
# LEGO MCP Manufacturing System v7.0
# Industry 4.0/5.0 Architecture - ISA-95 Compliant

# Header with timestamp
std_msgs/Header header

# Supervisor identification
string supervisor_id                # Unique supervisor identifier
string supervisor_name              # Human-readable name
string parent_supervisor_id         # Parent supervisor ID (empty if root)

# Restart strategy
uint8 STRATEGY_ONE_FOR_ONE = 0      # Restart only failed child
uint8 STRATEGY_ONE_FOR_ALL = 1      # Restart all children on any failure
uint8 STRATEGY_REST_FOR_ONE = 2     # Restart failed + all started after
uint8 strategy

# Supervisor state
uint8 STATE_STOPPED = 0
uint8 STATE_STARTING = 1
uint8 STATE_RUNNING = 2
uint8 STATE_STOPPING = 3
uint8 STATE_DEGRADED = 4            # Running but with failed children
uint8 STATE_FAILED = 5
uint8 state

# Configuration
uint32 max_restarts                 # Max restarts before escalation
float32 restart_window_sec          # Time window for restart counting
float32 heartbeat_timeout_ms        # Heartbeat timeout in milliseconds

# Statistics
uint32 total_restarts               # Total restarts since supervisor start
uint32 restarts_in_window           # Restarts in current window
uint32 escalation_count             # Number of escalations to parent
builtin_interfaces/Time last_restart_time  # Time of last child restart
builtin_interfaces/Time start_time  # Supervisor start time
float32 uptime_sec                  # Supervisor uptime

# Children summary
uint32 total_children               # Total number of child specs
uint32 running_children             # Number of running children
uint32 stopped_children             # Number of stopped children
uint32 failed_children              # Number of failed children
uint32 restarting_children          # Number of children being restarted

# Child status array (detailed status per child)
lego_mcp_msgs/ChildStatus[] children

# Health metrics
float32 health_score                # Overall health score (0.0 - 1.0)
string[] active_alerts              # Active alert messages
string[] recent_events              # Recent supervision events

# ISA-95 layer
uint8 isa95_level                   # ISA-95 automation level
string isa95_layer_name             # Layer name (Field, Control, Supervisory, etc.)

# Checkpoint information
bool checkpoint_enabled             # Whether checkpointing is enabled
string last_checkpoint_id           # ID of last checkpoint
builtin_interfaces/Time last_checkpoint_time  # Time of last checkpoint
