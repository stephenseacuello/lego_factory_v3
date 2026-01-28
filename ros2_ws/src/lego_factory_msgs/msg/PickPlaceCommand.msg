# Pick and place command
string command_id
string robot_id

# Pick location
geometry_msgs/Pose pick_pose
string pick_frame_id       # coordinate frame

# Place location
geometry_msgs/Pose place_pose
string place_frame_id

# Part info
string part_type           # 'lego_brick', 'filament_spool', etc.
string part_id

# Motion parameters
float64 approach_height    # approach offset (m)
float64 retract_height     # retract offset (m)
float64 velocity_scale     # 0-1
float64 acceleration_scale # 0-1

# Gripper parameters
float64 grip_force         # 0-100%
float64 grip_position      # 0-100%

# Options
bool use_vision            # use vision for fine positioning
bool check_collision       # enable collision checking
int32 retry_count          # number of retries on failure
