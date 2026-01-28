# AssemblyStep.msg - Single step in LEGO assembly sequence
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Step identification
string step_id                     # Unique step ID
string assembly_id                 # Parent assembly/model ID
uint32 sequence_number             # Order in assembly sequence
string description                 # Human-readable description

# Brick to place
string brick_id                    # Brick being placed
string brick_type                  # Brick type for verification

# Source location (where to pick from)
geometry_msgs/Pose pick_pose       # Pose to pick brick from
string pick_zone                   # Zone name (e.g., "feeder_1", "conveyor")

# Target location (where to place)
geometry_msgs/Pose place_pose      # Final brick placement pose
string place_frame                 # Reference frame for placement

# Connection information
string[] connects_to               # IDs of bricks this connects to
string connection_type             # Type: stud, technic_pin, axle, clip

# Robot assignment
string assigned_robot              # Robot to perform step (ned2, xarm)
string gripper_type                # Required gripper type

# Motion constraints
float32 approach_distance          # Approach distance in mm
float32 press_force                # Force to apply when placing (N)
float32 max_velocity               # Maximum velocity constraint

# Status
uint8 status                       # 0=pending, 1=in_progress, 2=completed, 3=failed, 4=skipped
string error_message               # Error if failed

# Timing
float32 estimated_duration_sec     # Estimated duration
float32 actual_duration_sec        # Actual duration if completed

# AR/VR visualization
string visualization_mesh          # Path to visualization mesh
float32[4] highlight_color         # RGBA color for AR highlighting
