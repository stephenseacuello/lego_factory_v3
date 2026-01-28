# PredictiveMaintenance.msg - ML-based maintenance predictions

std_msgs/Header header

string machine_id
string component_id  # "spindle", "x_axis", "y_axis", "z_axis", "tool_holder"

# Prediction type
uint8 PREDICTION_TOOL_WEAR = 0
uint8 PREDICTION_BEARING_DEGRADATION = 1
uint8 PREDICTION_BACKLASH = 2
uint8 PREDICTION_VIBRATION_ANOMALY = 3
uint8 PREDICTION_THERMAL_DRIFT = 4
uint8 PREDICTION_LUBRICATION = 5
uint8 prediction_type

# Health metrics
float32 health_score          # 0.0-1.0 (1.0 = perfect health)
float32 remaining_useful_life # Hours until predicted failure
float32 confidence            # 0.0-1.0 prediction confidence

# Severity levels
uint8 SEVERITY_INFO = 0
uint8 SEVERITY_WARNING = 1
uint8 SEVERITY_CRITICAL = 2
uint8 SEVERITY_FAILURE = 3
uint8 severity

# Trend analysis
float32 degradation_rate      # Rate of health decline per hour
float32[] historical_health   # Recent health scores
builtin_interfaces/Time[] historical_timestamps

# Recommendations
string[] recommended_actions  # ["Replace tool", "Schedule bearing inspection"]
string maintenance_notes

# Model info
string model_id
string model_version
float32 model_accuracy
