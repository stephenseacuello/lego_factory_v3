# QualityRecord.msg - Quality inspection record

string inspection_id
string inspection_type               # inline, final, receiving, audit

# Result
bool passed
float32 score                        # 0.0 - 1.0 quality score

# Measurements
Measurement[] measurements

# Defects found
Defect[] defects

# Metadata
builtin_interfaces/Time inspection_time
string inspector_id
string equipment_id                  # CMM, gauge, etc.
string notes
