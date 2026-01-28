# SafetyState.msg - Safety system state

std_msgs/Header header

string machine_id

# Overall safety status
uint8 SAFETY_OK = 0
uint8 SAFETY_WARNING = 1
uint8 SAFETY_CRITICAL = 2
uint8 SAFETY_EMERGENCY = 3
uint8 safety_level

# E-stop state
bool estop_hardware       # Physical E-stop button pressed
bool estop_software       # Software E-stop activated
bool estop_remote         # Remote/network E-stop
string estop_source       # Which E-stop was triggered

# Interlock states
bool door_interlock       # Door closed and locked
bool guard_interlock      # Safety guard in place
bool chuck_interlock      # Chuck clamped (lathe)
bool fixture_interlock    # Fixture clamped
bool tool_interlock       # Tool properly seated
bool[] custom_interlocks
string[] interlock_names

# Light curtain / safety scanner
bool light_curtain_clear
uint8 light_curtain_zone  # 0=clear, 1=warning, 2=stop
float32 nearest_intrusion_distance  # mm

# Limit switches
bool x_limit_min
bool x_limit_max
bool y_limit_min
bool y_limit_max
bool z_limit_min
bool z_limit_max
bool[] axis_limits        # All axis limits as array

# Probe state
bool probe_triggered
float32 probe_deflection

# Thermal safety
float32 spindle_temperature   # °C
float32 motor_temperature_x
float32 motor_temperature_y
float32 motor_temperature_z
bool thermal_warning
bool thermal_shutdown

# Electrical
float32 spindle_current       # Amps
float32 total_current
bool overcurrent_warning
bool ground_fault

# Motion safety
float32 actual_velocity
float32 max_safe_velocity
bool overspped_warning

# Safety functions
bool safe_torque_off          # STO active
bool safe_stop_1              # SS1 active
bool safe_stop_2              # SS2 active
bool safe_limited_speed       # SLS active
bool safe_direction           # SDI active

# Reset requirements
bool reset_required
string[] reset_conditions     # What needs to happen before reset
