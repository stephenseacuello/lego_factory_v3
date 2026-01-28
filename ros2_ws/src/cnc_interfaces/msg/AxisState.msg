# AxisState.msg - Individual axis state for kinematic chain

string axis_name             # X, Y, Z, A, B, C or custom name
float32 position             # Current position in axis units (mm or degrees)
float32 velocity             # Current velocity
float32 acceleration         # Current acceleration
float32 jerk                 # Current jerk
float32 load                 # Axis load (0.0 - 1.0)
float32 torque               # Axis torque (Nm)
float32 temperature          # Axis motor temperature (°C)

string state                 # stopped, moving, homing, error
bool homed                   # True if axis has been homed
bool at_positive_limit       # True if at positive limit switch
bool at_negative_limit       # True if at negative limit switch
bool servo_enabled           # True if servo is enabled
bool in_position             # True if axis is at commanded position

float32 following_error      # Difference between commanded and actual position
float32 position_error       # Position error from encoder
