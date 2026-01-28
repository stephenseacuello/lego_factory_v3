# SensorReading.msg - Generic sensor data from Arduino/ESP32 via micro-ROS

std_msgs/Header header

string sensor_id
string sensor_type  # "temperature", "vibration", "current", "proximity", etc.

# Primary value
float64 value
string unit  # "C", "g", "A", "mm", etc.

# Optional multi-axis data (for accelerometers, etc.)
float64[] values
string[] labels  # ["ax", "ay", "az"] for accelerometer

# Quality indicators
float32 confidence  # 0.0-1.0
bool valid
uint32 sample_count  # For averaged readings

# Calibration
bool calibrated
float64 offset
float64 scale
