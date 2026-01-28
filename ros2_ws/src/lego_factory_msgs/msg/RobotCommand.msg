# Robot command message
string robot_id
string command_type   # move_joints, move_pose, gripper, home, stop
float64[] target_joints    # For joint moves
geometry_msgs/Pose target_pose  # For cartesian moves
float64 velocity_scaling   # 0.0 - 1.0
float64 gripper_position   # For gripper commands
bool wait_for_completion
