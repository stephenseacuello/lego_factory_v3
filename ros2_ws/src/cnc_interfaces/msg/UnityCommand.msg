# UnityCommand.msg - Commands from Unity Digital Twin to Flask/ROS2

std_msgs/Header header

string machine_id
string command_type          # jog, home, gcode, stop, pause, resume, tool_change

# Jog command data
string jog_axis              # X, Y, Z, A, B, C
float32 jog_distance         # Distance in mm or degrees
float32 jog_feed_rate        # Feed rate mm/min

# Home command data
string[] home_axes           # Which axes to home

# G-code command data
string gcode_line            # Single G-code line
string gcode_file            # Path to G-code file

# Tool change data
int32 tool_number            # Tool to change to

# Simulation control
bool simulate_only           # True = don't execute on real machine
float32 simulation_speed     # Playback speed multiplier

# Visualization requests
bool request_toolpath        # Request toolpath visualization
bool request_geometry        # Request machine geometry
bool request_sensors         # Request sensor overlay data

# Source information
string source_application    # "unity", "rviz2", "web_ui"
string user_id               # User who issued command
float64 timestamp            # Command timestamp
