# TwinSync.msg - Digital twin synchronization message
# LEGO MCP Manufacturing System v7.0
# ISO 23247 Digital Twin Compliant

# Header with timestamp
std_msgs/Header header

# Sync identification
string sync_id                      # Unique sync transaction ID
string twin_id                      # Digital twin instance ID
string physical_asset_id            # Physical asset being synchronized

# Sync type
uint8 SYNC_FULL = 0                 # Full state synchronization
uint8 SYNC_INCREMENTAL = 1          # Incremental update
uint8 SYNC_EVENT = 2                # Event-triggered sync
uint8 SYNC_HEARTBEAT = 3            # Periodic heartbeat sync
uint8 sync_type

# Direction
uint8 DIRECTION_P2D = 0             # Physical to Digital
uint8 DIRECTION_D2P = 1             # Digital to Physical (command)
uint8 DIRECTION_BIDIRECTIONAL = 2   # Both directions
uint8 direction

# Sync scope
string[] synced_properties          # Properties being synchronized
string[] excluded_properties        # Properties excluded from sync

# State data (JSON encoded for flexibility)
string state_json                   # Current state as JSON
string previous_state_hash          # Hash of previous state
string current_state_hash           # Hash of current state

# Transform (physical to digital mapping)
geometry_msgs/Transform world_transform  # Transform in world frame
float32 scale_factor                # Scale factor (physical to digital)

# Quality metrics
float32 sync_latency_ms             # Synchronization latency
float32 data_quality_score          # Data quality (0-1)
uint32 sequence_number              # Sync sequence number
uint32 missed_syncs                 # Number of missed sync cycles

# Timestamps
builtin_interfaces/Time physical_timestamp   # Physical world timestamp
builtin_interfaces/Time digital_timestamp    # Digital twin timestamp
float32 time_drift_ms               # Time drift between systems

# Conflict resolution
bool has_conflict                   # Conflict detected
string conflict_resolution          # Resolution strategy used
string[] conflicting_properties     # Properties with conflicts
