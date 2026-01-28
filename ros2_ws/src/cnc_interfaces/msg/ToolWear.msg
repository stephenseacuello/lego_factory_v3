# ToolWear.msg - Tool wear monitoring and prediction

std_msgs/Header header

string machine_id
string tool_id
string tool_type  # "end_mill", "drill", "tap", "face_mill", "engraver"

# Tool identification
uint32 tool_number        # T1, T2, etc.
float32 tool_diameter     # mm
float32 tool_length       # mm
string material           # "HSS", "Carbide", "Ceramic", "CBN"

# Wear metrics
float32 flank_wear        # mm - VB
float32 crater_wear       # mm - KT
float32 nose_wear         # mm
float32 edge_chipping     # percentage

# Usage tracking
float32 cutting_time      # Total cutting time in hours
float32 cutting_distance  # Total distance cut in meters
uint32 cycle_count        # Number of machining cycles
float32 material_removed  # cm³

# Wear prediction
float32 wear_rate         # mm/hour
float32 remaining_life    # Percentage 0-100
float32 estimated_remaining_time  # Hours

# Condition
uint8 CONDITION_NEW = 0
uint8 CONDITION_GOOD = 1
uint8 CONDITION_FAIR = 2
uint8 CONDITION_WORN = 3
uint8 CONDITION_REPLACE = 4
uint8 CONDITION_FAILED = 5
uint8 condition

# Replacement recommendation
bool replace_recommended
string replacement_reason
builtin_interfaces/Time recommended_replacement_time
