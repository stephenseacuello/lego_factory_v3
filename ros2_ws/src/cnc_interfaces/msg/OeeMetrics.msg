# OeeMetrics.msg - Overall Equipment Effectiveness metrics
# OEE = Availability × Performance × Quality

std_msgs/Header header

string machine_id

# OEE Components (0.0 - 1.0 scale)
float32 oee              # Overall OEE score
float32 availability     # Run Time / Planned Production Time
float32 performance      # (Ideal Cycle Time × Total Count) / Run Time
float32 quality          # Good Count / Total Count

# Time metrics (seconds)
float64 planned_time     # Planned production time
float64 run_time         # Actual running time
float64 downtime         # Total downtime
float64 idle_time        # Idle time (not producing but available)

# Count metrics
uint32 total_count       # Total parts produced
uint32 good_count        # Parts passing quality
uint32 reject_count      # Parts rejected

# Cycle time metrics (seconds)
float32 ideal_cycle_time # Target cycle time per part
float32 actual_cycle_time # Average actual cycle time

# Reliability metrics (hours)
float32 mtbf             # Mean Time Between Failures
float32 mttr             # Mean Time To Repair

# Time window
string time_window       # "shift", "day", "week", "month"
builtin_interfaces/Time window_start
builtin_interfaces/Time window_end
