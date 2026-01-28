# Alarm.msg - Machine alarm/error notification

std_msgs/Header header

string machine_id

# Severity levels
uint8 SEVERITY_INFO = 0
uint8 SEVERITY_WARNING = 1
uint8 SEVERITY_ERROR = 2
uint8 SEVERITY_CRITICAL = 3

uint8 severity

# Alarm identification
uint16 code             # GRBL alarm code (1-10) or custom code
string category         # "limit", "homing", "probe", "spindle", "gcode", etc.
string message          # Human-readable description

# GRBL standard alarm codes for reference:
# 1 = Hard limit triggered
# 2 = Soft limit alarm
# 3 = Reset while in motion
# 4 = Probe fail (didn't trigger)
# 5 = Probe fail (triggered before move)
# 6 = Homing fail (cycle failed)
# 7 = Homing fail (switch not clearing)
# 8 = Homing fail (switch not found)
# 9 = Homing fail (couldn't find second switch)
# 10 = Spindle control unavailable

# Additional context
float64 position_x      # Position when alarm occurred
float64 position_y
float64 position_z
uint32 line_number      # G-code line if applicable

# Recovery
bool recoverable        # Can be cleared without reset
string recovery_action  # Suggested action
