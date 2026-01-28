# Measurement.msg - Dimensional measurement
# LEGO MCP Manufacturing System v7.0
# ISO 10012 Metrology Compliant

# Measurement identification
string measurement_id               # Unique measurement ID
string characteristic_name          # What is being measured (e.g., "length", "diameter")
string feature_id                   # CAD feature ID

# Measurement type
uint8 TYPE_LINEAR = 0               # Linear dimension
uint8 TYPE_ANGULAR = 1              # Angular dimension
uint8 TYPE_RADIUS = 2               # Radius/diameter
uint8 TYPE_POSITION = 3             # Position (X,Y,Z)
uint8 TYPE_FLATNESS = 4             # Flatness GD&T
uint8 TYPE_PERPENDICULARITY = 5     # Perpendicularity GD&T
uint8 TYPE_PARALLELISM = 6          # Parallelism GD&T
uint8 TYPE_CONCENTRICITY = 7        # Concentricity GD&T
uint8 TYPE_RUNOUT = 8               # Runout GD&T
uint8 TYPE_SURFACE_FINISH = 9       # Surface roughness
uint8 measurement_type

# Values
float64 nominal_value               # Nominal/target value
float64 measured_value              # Actual measured value
float64 deviation                   # Deviation from nominal
float64 upper_tolerance             # Upper tolerance limit
float64 lower_tolerance             # Lower tolerance limit

# Units
string unit                         # Measurement unit (mm, deg, um, etc.)

# Result
bool in_tolerance                   # Within tolerance?
float32 percent_of_tolerance        # Position within tolerance band (%)

# Uncertainty
float64 measurement_uncertainty     # Measurement uncertainty (k=2)
float64 repeatability               # Measurement repeatability

# Equipment
string gauge_id                     # Measuring instrument ID
string gauge_type                   # Type of gauge/instrument
builtin_interfaces/Time calibration_due  # Gauge calibration due date

# GD&T reference (if applicable)
string datum_reference              # Datum reference frame
string material_condition           # MMC, LMC, RFS

# Timestamp
builtin_interfaces/Time timestamp
