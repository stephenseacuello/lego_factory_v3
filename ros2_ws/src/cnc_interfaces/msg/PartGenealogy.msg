# PartGenealogy.msg - Complete part traceability record

string part_serial                    # Unique part identifier
string work_order_id
string part_number
string material_lot_id                # Source material lot

# Process history
ProcessStep[] process_steps           # All operations performed
QualityRecord[] inspections          # All quality checks

# Timestamps
builtin_interfaces/Time created_at
builtin_interfaces/Time completed_at

# Status
uint8 STATUS_IN_PROGRESS = 0
uint8 STATUS_COMPLETE = 1
uint8 STATUS_SCRAPPED = 2
uint8 STATUS_REWORK = 3
uint8 STATUS_ON_HOLD = 4
uint8 status

# Linked data
string[] linked_rosbags              # Rosbag recordings for this part
string[] linked_documents            # Certificates, drawings, etc.

# Metadata
string operator_id
string notes
