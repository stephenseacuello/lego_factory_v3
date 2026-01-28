# GrblStatus.msg - GRBL v1.1 specific status (from ? query)
# Format: <State|MPos:x,y,z|FS:feed,spindle|Ov:f,r,s|A:SFM|Pn:XYZPDHRS>

std_msgs/Header header

string machine_id

# State (Idle, Run, Hold, Jog, Alarm, Door, Check, Home, Sleep)
string state
uint8 state_code

# Position (depends on $10 setting)
bool report_machine_pos  # true = MPos, false = WPos
float64 pos_x
float64 pos_y
float64 pos_z

# Feed and Speed (FS)
float64 feed_rate
float64 spindle_speed

# Overrides (Ov) - percentages
uint8 feed_override
uint8 rapid_override
uint8 spindle_override

# Accessory state (A) - parsed from SFM flags
bool spindle_cw
bool spindle_ccw
bool flood_coolant
bool mist_coolant

# Input pin state (Pn)
bool pin_x_limit
bool pin_y_limit
bool pin_z_limit
bool pin_probe
bool pin_door
bool pin_hold
bool pin_soft_reset
bool pin_cycle_start

# Buffer state (Bf)
uint16 planner_blocks_available
uint16 rx_chars_available

# Line number being executed (Ln)
uint32 line_number

# Work Coordinate Offset (WCO) - sent periodically
float64 wco_x
float64 wco_y
float64 wco_z
