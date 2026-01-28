# SpindleStateMsg.msg - Spindle state for CNC machines

float32 commanded_speed      # Commanded spindle speed (RPM)
float32 actual_speed         # Actual spindle speed (RPM)
float32 load                 # Spindle load (0.0 - 1.0)
float32 torque               # Spindle torque (Nm)
float32 power                # Spindle power (kW)
float32 temperature          # Spindle bearing temperature (°C)

string state                 # stopped, clockwise, counterclockwise, braking
bool at_speed                # True if spindle is at commanded speed
bool oriented                # True if spindle is oriented (for tool change)
bool in_tolerance            # True if speed is within tolerance

float32 vibration_x          # Vibration amplitude X (mm/s)
float32 vibration_y          # Vibration amplitude Y (mm/s)
float32 vibration_z          # Vibration amplitude Z (mm/s)

# Spindle bearing monitoring
float32 bearing_wear         # 0.0 - 1.0
int32 bearing_hours          # Total bearing hours
float32 bearing_temperature  # Bearing temperature (°C)
