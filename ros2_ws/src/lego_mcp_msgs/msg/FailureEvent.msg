# FailureEvent.msg - Equipment or process failure event
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Failure identification
string failure_id                  # Unique failure ID
string equipment_id                # Equipment that failed
string equipment_type              # Equipment type

# Failure classification
uint8 failure_type                 # 0=robot_fault, 1=print_failed, 2=quality_reject,
                                   #  3=equipment_offline, 4=material_stockout, 5=collision,
                                   #  6=communication_lost, 7=safety_violation, 8=thermal_fault
string failure_type_name           # Human-readable failure type
string failure_code                # Equipment-specific error code
string failure_message             # Detailed failure message

# Severity
uint8 severity                     # 1=minor, 2=moderate, 3=major, 4=critical, 5=emergency
bool production_stopped            # Did this stop production?
bool safety_concern                # Is there a safety concern?

# Context
string work_order_id               # Affected work order
string operation_id                # Affected operation
string job_id                      # Affected job

# State at failure
geometry_msgs/Pose equipment_pose  # Equipment position at failure
float32[] joint_positions          # Joint positions (robots)
string[] active_alarms             # Active alarms at time of failure
float32 operation_progress         # Progress when failed (0-100)

# Impact assessment
string[] affected_work_orders      # All affected work orders
uint32 parts_affected              # Number of parts affected
float32 estimated_downtime_min     # Estimated downtime in minutes
float32 estimated_cost             # Estimated cost impact

# Recovery information
uint8 recovery_status              # 0=pending, 1=in_progress, 2=recovered, 3=escalated, 4=manual_required
string recovery_action             # Current/completed recovery action
uint8 retry_count                  # Recovery attempts made
uint8 max_retries                  # Maximum retries allowed
string escalation_contact          # Who to contact if unrecoverable

# Root cause (if determined)
string probable_cause              # AI-determined probable cause
string[] contributing_factors      # Contributing factors
string prevention_recommendation   # How to prevent recurrence

# Timestamps
builtin_interfaces/Time failure_time
builtin_interfaces/Time detection_time
builtin_interfaces/Time recovery_start_time
builtin_interfaces/Time recovery_end_time
