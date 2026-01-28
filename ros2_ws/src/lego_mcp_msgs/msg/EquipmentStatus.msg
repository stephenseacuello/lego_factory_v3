# EquipmentStatus.msg - Status of manufacturing equipment
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Equipment identification
string equipment_id                # Unique equipment ID
string equipment_type              # Type: robot, printer_fdm, printer_sla, cnc, laser, conveyor
string equipment_name              # Human-readable name

# Connection status
bool connected                     # Connection to equipment established
string protocol                    # Communication protocol (ros2, grbl, http, mqtt)
string ip_address                  # IP address if networked
string serial_port                 # Serial port if USB/serial

# Operating state
uint8 state                        # 0=offline, 1=idle, 2=running, 3=paused, 4=error, 5=maintenance, 6=emergency_stop
string state_description           # Human-readable state description
string current_operation           # Description of current operation
string current_job_id              # Current job/work order ID

# Position (for CNC/robots)
geometry_msgs/Point position       # Current XYZ position
float32[] joint_positions          # Joint positions (for robots)
float32[] joint_velocities         # Joint velocities

# Machine-specific metrics
float32 spindle_speed              # Spindle RPM (CNC)
float32 feed_rate                  # Feed rate mm/min (CNC)
float32 laser_power                # Laser power percent (Laser)
float32 nozzle_temp                # Nozzle temperature (FDM)
float32 bed_temp                   # Bed temperature (FDM)
float32 chamber_temp               # Chamber temperature (SLA)
float32 resin_level                # Resin level percent (SLA)

# Health metrics
float32 uptime_hours               # Total uptime hours
float32 utilization_percent        # Current utilization (0-100)
uint32 error_count                 # Errors since last reset
uint32 cycles_completed            # Operations completed

# Safety
bool estop_active                  # Emergency stop active
bool safety_interlock              # Safety interlock engaged
bool guards_closed                 # Safety guards closed
float32[] joint_torques            # Joint torques for collision detection

# Maintenance
float32 maintenance_due_hours      # Hours until maintenance due
string[] active_alerts             # Active alert messages
builtin_interfaces/Time last_maintenance

# Performance
float32 oee_availability           # OEE availability (0-1)
float32 oee_performance            # OEE performance (0-1)
float32 oee_quality                # OEE quality (0-1)
