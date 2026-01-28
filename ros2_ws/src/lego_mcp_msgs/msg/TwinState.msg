# TwinState.msg - Digital twin state for entire factory cell
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Twin identification
string twin_id                     # Digital twin instance ID
string factory_cell_id             # Physical factory cell ID
uint32 sequence_number             # State sequence for ordering

# Synchronization
builtin_interfaces/Time physical_timestamp    # Timestamp from physical world
builtin_interfaces/Time twin_timestamp        # Twin processing timestamp
float32 sync_latency_ms            # Sync latency in milliseconds
bool synchronized                  # Twin is synchronized with physical

# Equipment states (embedded)
lego_mcp_msgs/EquipmentStatus[] equipment_states  # All equipment status

# Active work
string[] active_work_orders        # Currently active work orders
string[] active_jobs               # Currently executing jobs
uint32 queue_depth                 # Jobs waiting in queue

# Production metrics
uint32 parts_produced_today        # Parts produced today
uint32 parts_target_today          # Production target
float32 production_rate            # Current parts per hour
float32 defect_rate                # Current defect rate (0-1)

# Overall equipment effectiveness
float32 oee_overall                # Overall OEE (0-1)
float32 oee_availability           # Availability component
float32 oee_performance            # Performance component
float32 oee_quality                # Quality component

# Resource status
float32[] material_levels          # Material levels by type (0-100)
string[] material_types            # Material type names
float32 energy_consumption_kw      # Current energy consumption

# Spatial information (for AR)
geometry_msgs/Pose[] equipment_poses     # Equipment positions in world frame
string[] equipment_frame_ids             # TF frame IDs for each equipment

# Assembly state
string current_model_id            # Model being assembled
uint32 assembly_step_current       # Current assembly step
uint32 assembly_step_total         # Total assembly steps
geometry_msgs/Pose[] placed_bricks # Positions of placed bricks

# Alerts and events
string[] active_alerts             # Active alert messages
uint8[] alert_severities           # Alert severity levels
uint32 unacknowledged_events       # Count of unacknowledged events

# PINN predictions (if available)
float32 predicted_quality_score    # PINN predicted quality (0-1)
float32 prediction_confidence      # Prediction confidence
float32 predicted_completion_min   # Predicted time to completion

# Health summary
uint8 overall_health               # 0=critical, 1=degraded, 2=warning, 3=healthy
string health_summary              # Human-readable health summary
