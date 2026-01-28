# Measurement.msg - Single dimensional measurement

string feature_name                  # e.g., "Hole_1_Diameter"
string feature_id                    # CAD feature ID

float32 nominal_value
float32 measured_value
float32 upper_tolerance
float32 lower_tolerance
float32 deviation                    # measured - nominal

string unit                          # mm, inch, degree
bool passed

# Position on part (optional)
float32 location_x
float32 location_y
float32 location_z
