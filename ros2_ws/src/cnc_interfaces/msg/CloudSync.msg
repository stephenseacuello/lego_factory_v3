# CloudSync.msg - Multi-site cloud synchronization

std_msgs/Header header

string site_id
string site_name
string region                 # Geographic region

# Sync type
uint8 SYNC_STATUS = 0
uint8 SYNC_CONFIG = 1
uint8 SYNC_PROGRAM = 2
uint8 SYNC_SCHEDULE = 3
uint8 SYNC_METRICS = 4
uint8 SYNC_ALERT = 5
uint8 sync_type

# Payload
string payload_type           # JSON schema type
string payload_json           # JSON-encoded data
uint32 payload_size           # bytes
string payload_hash           # SHA-256 for verification

# Sync metadata
string sync_id
uint32 sequence_number
builtin_interfaces/Time origin_timestamp
builtin_interfaces/Time received_timestamp

# Source/destination
string source_site
string[] destination_sites    # Empty = broadcast to all

# Conflict resolution
uint8 CONFLICT_LATEST_WINS = 0
uint8 CONFLICT_SOURCE_WINS = 1
uint8 CONFLICT_MANUAL = 2
uint8 conflict_strategy

bool has_conflict
string conflict_description
string resolution

# Delivery
bool acknowledged
bool applied
string[] failed_sites
string error_message

# Bandwidth/priority
uint8 BANDWIDTH_LOW = 0
uint8 BANDWIDTH_NORMAL = 1
uint8 BANDWIDTH_HIGH = 2
uint8 BANDWIDTH_CRITICAL = 3
uint8 bandwidth_priority

# Encryption
bool encrypted
string encryption_method
