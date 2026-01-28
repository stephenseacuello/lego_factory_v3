# MachineStatus.msg - Complete CNC machine status
# Compatible with TinyG, GRBL, and grblHAL controllers

# Header with timestamp
std_msgs/Header header

# Machine identification
string machine_id
string controller_type  # "tinyg", "grbl", "grblhal", "linuxcnc"
string firmware_version

# Machine state constants
uint8 STATE_UNKNOWN = 0
uint8 STATE_IDLE = 1
uint8 STATE_RUN = 2
uint8 STATE_HOLD = 3
uint8 STATE_JOG = 4
uint8 STATE_ALARM = 5
uint8 STATE_DOOR = 6
uint8 STATE_CHECK = 7
uint8 STATE_HOME = 8
uint8 STATE_SLEEP = 9

# Current state
uint8 state
string state_text  # Human-readable state

# Position (machine coordinates)
float64 mpos_x
float64 mpos_y
float64 mpos_z
float64 mpos_a  # 4th axis (optional)
float64 mpos_b  # 5th axis (optional)
float64 mpos_c  # 6th axis (optional)

# Position (work coordinates)
float64 wpos_x
float64 wpos_y
float64 wpos_z
float64 wpos_a
float64 wpos_b
float64 wpos_c

# Work coordinate offset (G54-G59)
string coord_system  # "G54", "G55", etc.
float64 wco_x
float64 wco_y
float64 wco_z

# Motion
float64 feed_rate       # Current feed rate (mm/min or in/min)
float64 feed_override   # Feed override percentage (0.0-2.0)
float64 rapid_override  # Rapid override percentage
float64 velocity        # Actual velocity

# Spindle
float64 spindle_speed   # RPM
float64 spindle_override
bool spindle_cw         # Clockwise rotation
bool spindle_ccw        # Counter-clockwise

# Coolant
bool coolant_flood
bool coolant_mist

# Program execution
uint32 line_number      # Current G-code line
float32 progress        # Job progress 0.0-1.0

# Buffer status
uint16 planner_buffer   # Available planner buffer entries
uint16 rx_buffer        # Available RX buffer bytes

# Units
bool metric             # true = mm, false = inches
