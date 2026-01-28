# Defect.msg - Defect record

string defect_code                   # e.g., "SCRATCH", "BURR", "DIMENSIONAL"
string defect_description

# Severity levels
uint8 SEVERITY_MINOR = 0
uint8 SEVERITY_MAJOR = 1
uint8 SEVERITY_CRITICAL = 2
uint8 severity

uint32 quantity                      # Number of defects
string location                      # Location on part

# Classification
string defect_category               # visual, dimensional, functional
string root_cause                    # If known
string corrective_action            # If taken
