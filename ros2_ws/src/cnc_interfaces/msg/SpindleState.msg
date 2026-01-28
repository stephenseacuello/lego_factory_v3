# SpindleState.msg - Spindle/laser state

std_msgs/Header header

string machine_id

# Mode
uint8 MODE_OFF = 0
uint8 MODE_CW = 1       # M3 - Clockwise
uint8 MODE_CCW = 2      # M4 - Counter-clockwise
uint8 MODE_LASER = 3    # Laser mode

uint8 mode

# Speed
float64 commanded_rpm   # Requested speed
float64 actual_rpm      # Measured speed (if available)
float64 override        # Override percentage (0.0-2.0)

# Laser-specific (when mode == MODE_LASER)
float64 power           # 0.0-1.0 (S-value / S-max)
bool dynamic_power      # M4 laser mode (power scales with speed)

# Limits
float64 min_rpm
float64 max_rpm

# Status
bool at_speed           # Spindle has reached commanded speed
bool fault
string fault_message
