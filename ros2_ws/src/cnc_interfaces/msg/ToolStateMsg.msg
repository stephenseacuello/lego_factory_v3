# ToolStateMsg.msg - Tool state for CNC/Robot operations

int32 tool_number            # Current tool number (T1, T2, etc.)
string tool_id               # Unique tool identifier
string tool_type             # end_mill, ball_mill, drill, tap, probe, etc.
string tool_material         # HSS, carbide, ceramic, diamond, etc.

float32 length_offset        # Tool length offset (mm)
float32 diameter             # Tool diameter (mm)
float32 corner_radius        # Corner/nose radius (mm)
float32 flute_length         # Cutting flute length (mm)
int32 number_of_flutes       # Number of cutting flutes

# Tool condition
float32 wear_level           # 0.0 - 1.0 (1.0 = needs replacement)
int32 remaining_life         # Estimated remaining cuts/time
float32 cutting_time         # Total cutting time (hours)
int32 cut_count              # Number of cuts made

# Tool position
geometry_msgs/Point tip_position   # Tool tip position
geometry_msgs/Quaternion orientation  # Tool orientation

# Tool holder
string holder_type           # BT40, CAT40, HSK, ER, etc.
int32 pocket_number          # Tool carousel pocket number
