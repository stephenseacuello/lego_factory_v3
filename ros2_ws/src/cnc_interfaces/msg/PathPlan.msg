# PathPlan.msg - Motion path planning result

std_msgs/Header header

string machine_id
string plan_id

# Planning request info
geometry_msgs/Pose start_pose
geometry_msgs/Pose goal_pose
string planning_algorithm  # "RRT", "PRM", "linear", "spline"

# Path waypoints
geometry_msgs/PoseStamped[] waypoints
float32[] velocities       # Velocity at each waypoint
float32[] accelerations    # Acceleration at each waypoint

# Path metrics
float32 total_distance     # mm
float32 estimated_time     # seconds
float32 max_velocity       # mm/min
float32 max_acceleration   # mm/s²

# Safety analysis
bool collision_free
float32 min_clearance      # mm to nearest obstacle
CollisionWarning[] potential_collisions

# Path quality
float32 smoothness_score   # 0.0-1.0
float32 efficiency_score   # 0.0-1.0 (direct path = 1.0)
uint32 waypoint_count

# Optimization
bool optimized
string optimization_method  # "time", "distance", "smoothness", "energy"
float32 optimization_improvement  # Percentage improvement

# Status
uint8 STATUS_PENDING = 0
uint8 STATUS_PLANNING = 1
uint8 STATUS_SUCCESS = 2
uint8 STATUS_FAILED = 3
uint8 STATUS_COLLISION = 4
uint8 status
string status_message
