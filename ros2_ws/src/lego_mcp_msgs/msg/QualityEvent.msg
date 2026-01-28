# QualityEvent.msg - Quality system event for manufacturing control
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Event identification
string event_id                    # Unique event ID
string event_type                  # Type: defect_detected, spc_violation, inspection_complete,
                                   #       calibration_drift, measurement_recorded, audit_finding

# Context
string work_order_id               # Associated work order
string operation_id                # Associated operation
string part_id                     # Associated part
string equipment_id                # Equipment that produced/inspected

# Severity and action
uint8 severity                     # 1=info, 2=warning, 3=minor, 4=major, 5=critical
uint8 action                       # 0=MONITOR, 1=LOG, 2=ALERT, 3=INSPECT, 4=ADJUST, 5=STOP, 6=REWORK, 7=SCRAP
string action_name                 # Human-readable action name
string description                 # Event description

# SPC-specific fields
string parameter_name              # Measured parameter (e.g., "stud_diameter")
float32 measured_value             # Measured value
float32 target_value               # Target/nominal value
float32 ucl                        # Upper control limit
float32 lcl                        # Lower control limit
float32 usl                        # Upper specification limit
float32 lsl                        # Lower specification limit
string violation_type              # Type: out_of_control, out_of_spec, trend, run, zone

# Defect reference (if defect-related)
string defect_id                   # Reference to DefectDetection
string defect_type                 # Defect type
float32 defect_confidence          # Detection confidence

# Response tracking
bool acknowledged                  # Event acknowledged by operator
string acknowledged_by             # Who acknowledged
builtin_interfaces/Time acknowledged_at
bool resolved                      # Event resolved
string resolution_notes            # Resolution description
string corrective_action_id        # Link to corrective action record

# Audit trail
string triggered_by                # What triggered this event (vision, spc, manual)
string[] related_events            # Related event IDs
