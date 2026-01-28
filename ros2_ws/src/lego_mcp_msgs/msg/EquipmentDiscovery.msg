# EquipmentDiscovery.msg - Equipment discovery announcement
# LEGO MCP Manufacturing System v7.0
# OPC UA / MTConnect Compatible Discovery

# Header with timestamp
std_msgs/Header header

# Equipment identification
string equipment_id                 # Unique equipment identifier
string equipment_name               # Human-readable name
string serial_number                # Manufacturer serial number
string manufacturer                 # Equipment manufacturer
string model                        # Equipment model

# Equipment type
uint8 TYPE_CNC = 0                  # CNC machine
uint8 TYPE_LASER = 1                # Laser cutter/engraver
uint8 TYPE_FDM = 2                  # FDM 3D printer
uint8 TYPE_SLA = 3                  # SLA/DLP 3D printer
uint8 TYPE_ROBOT_ARM = 4            # Robot arm
uint8 TYPE_AGV = 5                  # Autonomous guided vehicle
uint8 TYPE_CONVEYOR = 6             # Conveyor system
uint8 TYPE_INSPECTION = 7           # Inspection station
uint8 TYPE_ASSEMBLY = 8             # Assembly station
uint8 TYPE_SENSOR = 9               # Sensor/IoT device
uint8 TYPE_CAMERA = 10              # Vision camera
uint8 TYPE_PLC = 11                 # PLC controller
uint8 TYPE_OTHER = 255
uint8 equipment_type

# Network information
string ip_address                   # IP address
uint16 port                         # Primary port
string mac_address                  # MAC address
string hostname                     # Network hostname

# Protocol support
string[] supported_protocols        # ["ros2", "opcua", "mtconnect", "mqtt", "modbus"]
string primary_protocol             # Primary communication protocol
string ros2_namespace               # ROS2 namespace for this equipment

# Capabilities
string[] capabilities               # List of capabilities
float32 max_payload_kg              # Max payload (if applicable)
float32[] work_envelope             # Work envelope [x, y, z] in mm
string[] supported_materials        # Supported materials

# Status
uint8 STATUS_ONLINE = 0
uint8 STATUS_OFFLINE = 1
uint8 STATUS_BUSY = 2
uint8 STATUS_ERROR = 3
uint8 STATUS_MAINTENANCE = 4
uint8 status

# ISA-95 classification
uint8 isa95_level                   # ISA-95 automation level (0-4)
string work_center_id               # Associated work center
string production_line              # Production line assignment

# Discovery metadata
builtin_interfaces/Time first_seen  # When first discovered
builtin_interfaces/Time last_seen   # Last heartbeat/announcement
uint32 announcement_count           # Number of announcements received
float32 availability_percent        # Historical availability
