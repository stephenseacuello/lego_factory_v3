# MachinePosition.msg - Lightweight position-only message for high-frequency updates

std_msgs/Header header

string machine_id

# Machine position (absolute)
float64 x
float64 y
float64 z
float64 a
float64 b
float64 c

# Work position (with offsets applied)
float64 wx
float64 wy
float64 wz

# Velocity vector
float64 vx
float64 vy
float64 vz

# Current feed rate
float64 feed_rate
