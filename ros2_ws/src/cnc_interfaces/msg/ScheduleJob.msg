# ScheduleJob.msg - Scheduled job definition

std_msgs/Header header

string job_id
string work_order_id
string part_number
string part_name
string customer_id

# Scheduling
uint8 PRIORITY_LOW = 0
uint8 PRIORITY_NORMAL = 1
uint8 PRIORITY_HIGH = 2
uint8 PRIORITY_URGENT = 3
uint8 PRIORITY_EMERGENCY = 4
uint8 priority

builtin_interfaces/Time scheduled_start
builtin_interfaces/Time scheduled_end
builtin_interfaces/Time actual_start
builtin_interfaces/Time actual_end
builtin_interfaces/Time due_date

# Machine assignment
string assigned_machine_id
string[] capable_machines     # Machines that can run this job
string[] required_capabilities

# Program
string program_path
string program_name
uint32 estimated_runtime      # seconds
uint32 actual_runtime

# Quantity
uint32 quantity_required
uint32 quantity_completed
uint32 quantity_rejected

# Materials and tooling
string material_type
string[] required_tools
string[] required_fixtures

# Status
uint8 STATUS_PENDING = 0
uint8 STATUS_SCHEDULED = 1
uint8 STATUS_QUEUED = 2
uint8 STATUS_SETUP = 3
uint8 STATUS_RUNNING = 4
uint8 STATUS_PAUSED = 5
uint8 STATUS_COMPLETED = 6
uint8 STATUS_CANCELLED = 7
uint8 STATUS_FAILED = 8
uint8 status

float32 progress              # 0.0-1.0

# Dependencies
string[] prerequisite_jobs    # Jobs that must complete first
string[] blocking_jobs        # Jobs waiting on this one

# Notes
string setup_notes
string operator_notes
string quality_notes
