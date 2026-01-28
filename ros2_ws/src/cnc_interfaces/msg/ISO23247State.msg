# ISO23247State.msg - ISO 23247-3 compliant Digital Representation
# For Unity Digital Twin and standards-compliant data exchange

std_msgs/Header header

# Observable Manufacturing Element (OME) identification
string ome_id
string ome_type              # equipment, material, process, personnel, facility
string semantic_id           # ISO 23247 semantic identifier

# Operational State (per MTConnect/ISO 23247 mapping)
string execution_state       # ACTIVE, READY, STOPPED, INTERRUPTED, FEED_HOLD
string machine_mode          # AUTOMATIC, MANUAL, MDI, SETUP
string active_program
int32 line_number
float32 feed_override        # 0.0 - 2.0 (200%)
float32 spindle_override     # 0.0 - 2.0 (200%)

# 3D Position (high-frequency update)
geometry_msgs/Point position
geometry_msgs/Point velocity
float64 position_timestamp

# Kinematics State
cnc_interfaces/AxisState[] axes
cnc_interfaces/ToolStateMsg tool
cnc_interfaces/SpindleStateMsg spindle
float64 kinematics_timestamp

# Data Quality (ISO 23247-3 requirement)
float32 quality_score        # 0.0 - 1.0
float64 data_freshness       # seconds since last update
string data_source           # controller, sensor, interpolated
bool interpolated            # true if position is interpolated

# AAS Reference (IEC 63278)
string aas_shell_ref         # URI to AAS shell
string geometry_ref          # URI to STEP/glTF geometry

# Sensor Overlay Data
cnc_interfaces/SensorOverlayMsg[] sensors
