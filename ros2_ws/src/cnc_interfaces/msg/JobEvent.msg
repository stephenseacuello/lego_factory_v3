# JobEvent.msg - Production job lifecycle events
# Used for tracking job start/stop for OEE calculation

std_msgs/Header header

string job_id
string work_order_id
string machine_id
string part_number
string operation_id

# Event type constants
uint8 EVENT_START = 0
uint8 EVENT_COMPLETE = 1
uint8 EVENT_PAUSE = 2
uint8 EVENT_RESUME = 3
uint8 EVENT_ABORT = 4
uint8 EVENT_REJECT = 5
uint8 EVENT_REWORK = 6

uint8 event_type

# Timing
builtin_interfaces/Time event_time
float32 cycle_time       # Actual cycle time (seconds)
float32 planned_time     # Planned/ideal cycle time (seconds)

# Quality
bool passed_inspection
string reject_reason     # If rejected
uint8 quality_grade      # 0-100

# Operator info
string operator_id
string shift_id

# Additional context
string notes
