# DigitalTwinState.msg - Complete machine state for digital twin visualization

std_msgs/Header header

string machine_id
string machine_type   # "3axis_mill", "5axis_mill", "lathe", "router", "laser"
string machine_model  # "Tormach 440", "Haas VF-2", etc.

# Kinematic state
geometry_msgs/Pose tool_pose        # Tool tip position and orientation
geometry_msgs/Pose spindle_pose     # Spindle position
geometry_msgs/Pose table_pose       # Table/workpiece position
float32[] joint_positions           # Joint angles/positions
float32[] joint_velocities          # Joint velocities
float32[] joint_torques             # Joint torques/forces

# Tool information
uint32 current_tool_number
float32 tool_length
float32 tool_diameter
string tool_type
geometry_msgs/Point tool_tip_offset

# Workpiece state
geometry_msgs/Pose workpiece_pose
float32[] workpiece_dimensions      # [length, width, height]
string workpiece_material
float32 material_removed_volume     # cm³

# Spindle state
float32 spindle_speed               # RPM
float32 spindle_load                # Percentage
float32 spindle_temperature         # °C
bool spindle_running

# Axis states
float32[] axis_positions            # [X, Y, Z, A, B, C]
float32[] axis_velocities
float32[] axis_loads
bool[] axis_homed
bool[] axis_at_limit

# Coolant visualization
bool coolant_flood_active
bool coolant_mist_active
geometry_msgs/Point coolant_nozzle_position
geometry_msgs/Vector3 coolant_direction

# Chip/debris simulation
geometry_msgs/Point[] chip_positions
float32 chip_accumulation           # Percentage of chip tray

# Enclosure state
bool door_open
bool guard_engaged
bool[] interlock_states

# Visual settings
string color_scheme                 # "default", "thermal", "stress", "velocity"
float32 animation_speed             # Playback speed multiplier
bool show_toolpath
bool show_work_envelope
bool show_collision_zones
