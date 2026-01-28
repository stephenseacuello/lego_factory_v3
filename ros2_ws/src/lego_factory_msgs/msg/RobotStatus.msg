# Robot arm status message
string robot_id
string state          # idle, moving, gripping, error
float64[] joint_positions   # 6 joint angles in radians
float64[] joint_velocities
float64[] joint_efforts
geometry_msgs/Pose end_effector_pose
bool gripper_open
float64 gripper_position    # 0.0 = closed, 1.0 = open
string error_code
string error_message
