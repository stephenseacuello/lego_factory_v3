# FleetEvent.msg - Fleet-level events for monitoring and logging

std_msgs/Header header

# Event type constants
uint8 EVENT_MACHINE_ONLINE = 0
uint8 EVENT_MACHINE_OFFLINE = 1
uint8 EVENT_MACHINE_ALARM = 2
uint8 EVENT_MACHINE_IDLE = 3
uint8 EVENT_JOB_DISPATCHED = 4
uint8 EVENT_JOB_COMPLETED = 5
uint8 EVENT_ALLOCATION_CHANGED = 6
uint8 EVENT_CAPABILITY_CHANGED = 7

uint8 event_type
string machine_id
string job_id                     # If applicable
string message
string[] details                  # Additional key=value pairs
