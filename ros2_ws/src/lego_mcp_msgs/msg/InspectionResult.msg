# InspectionResult.msg - Quality inspection result
# LEGO MCP Manufacturing System v7.0
# ISO 9001 / IATF 16949 Compliant

# Header with timestamp
std_msgs/Header header

# Inspection identification
string inspection_id                # Unique inspection identifier
string part_id                      # Inspected part ID
string serial_number                # Part serial number
string work_order_id                # Associated work order
string operation_id                 # Manufacturing operation inspected

# Inspection type
uint8 TYPE_VISUAL = 0               # Visual inspection
uint8 TYPE_DIMENSIONAL = 1          # Dimensional measurement
uint8 TYPE_FUNCTIONAL = 2           # Functional test
uint8 TYPE_SURFACE = 3              # Surface quality
uint8 TYPE_ASSEMBLY = 4             # Assembly verification
uint8 TYPE_FINAL = 5                # Final inspection
uint8 inspection_type

# Overall result
uint8 RESULT_PASS = 0
uint8 RESULT_FAIL = 1
uint8 RESULT_CONDITIONAL = 2        # Pass with conditions
uint8 RESULT_REWORK = 3             # Requires rework
uint8 RESULT_SCRAP = 4              # Must be scrapped
uint8 result

# Confidence and method
float32 confidence_score            # AI confidence (0-1)
bool automated                      # Automated vs manual inspection
string inspector_id                 # Inspector ID (human or system)
string inspection_station           # Station where inspection occurred

# Measurements (if dimensional)
lego_mcp_msgs/Measurement[] measurements

# Defects found
lego_mcp_msgs/DefectDetection[] defects

# Quality metrics
float32 quality_score               # Overall quality score (0-100)
uint32 defect_count                 # Number of defects found
string[] failed_criteria            # List of failed criteria

# SPC data
float32 cpk_contribution            # Contribution to Cpk calculation
bool out_of_control                 # SPC out-of-control signal
string control_chart_id             # Associated control chart

# Disposition
string disposition                  # Final disposition decision
string disposition_reason           # Reason for disposition
string rework_instructions          # Instructions if rework needed

# Traceability
string[] image_urls                 # Inspection images
string report_url                   # Detailed report URL
builtin_interfaces/Time inspection_duration  # How long inspection took
