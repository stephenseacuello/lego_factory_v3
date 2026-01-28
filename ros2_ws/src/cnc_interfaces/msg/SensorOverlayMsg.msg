# SensorOverlayMsg.msg - Sensor data for Unity visualization overlay

string sensor_id             # Unique sensor identifier
string sensor_type           # temperature, vibration, current, force, etc.
string sensor_name           # Human-readable name

float32 value                # Current sensor value
string unit                  # Measurement unit (°C, mm/s, A, N, etc.)

float32 min_value            # Minimum normal range
float32 max_value            # Maximum normal range
float32 warning_threshold    # Warning threshold
float32 critical_threshold   # Critical threshold

string status                # normal, warning, critical, offline
float32 confidence           # Data confidence (0.0 - 1.0)

# Position for 3D overlay
geometry_msgs/Point position # Sensor position in machine frame
geometry_msgs/Quaternion orientation  # Sensor orientation

# Visualization hints
string color_map             # heatmap, gradient, discrete
float32 normalized_value     # 0.0 - 1.0 for visualization
bool show_in_hud             # Show in heads-up display
bool show_as_marker          # Show as 3D marker
