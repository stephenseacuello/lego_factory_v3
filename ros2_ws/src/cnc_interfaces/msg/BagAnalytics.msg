# BagAnalytics.msg - ROS bag analysis results

std_msgs/Header header

string bag_path
string analysis_id

# Bag metadata
builtin_interfaces/Time start_time
builtin_interfaces/Time end_time
float64 duration              # seconds
uint64 message_count
uint64 bag_size               # bytes

# Topics analyzed
string[] topics
uint64[] message_counts       # Per topic
float32[] message_rates       # Hz per topic

# Analysis type
uint8 ANALYSIS_SUMMARY = 0
uint8 ANALYSIS_ANOMALY = 1
uint8 ANALYSIS_CORRELATION = 2
uint8 ANALYSIS_PREDICTION = 3
uint8 ANALYSIS_QUALITY = 4
uint8 analysis_type

# Statistical results
float32[] means
float32[] std_devs
float32[] mins
float32[] maxs
string[] stat_labels

# Anomalies detected
uint32 anomaly_count
builtin_interfaces/Time[] anomaly_timestamps
string[] anomaly_descriptions
float32[] anomaly_scores

# Correlations
string[] correlated_topics
float32[] correlation_coefficients

# Machine learning insights
string model_used
float32 model_confidence
string[] predictions
string[] recommendations

# Time series data (sampled)
builtin_interfaces/Time[] sample_times
float32[] sample_values
string sample_metric

# Report
string report_format          # "json", "html", "pdf"
string report_path
