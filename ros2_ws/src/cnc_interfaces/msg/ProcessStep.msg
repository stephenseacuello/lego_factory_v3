# ProcessStep.msg - Single manufacturing operation record

string operation_id
uint32 operation_number              # Sequence number (10, 20, 30...)
string operation_name

# Machine and program
string machine_id
string program_id                    # G-code program used
string tool_id                       # Tool used

# Timing
builtin_interfaces/Time start_time
builtin_interfaces/Time end_time
float32 cycle_time                   # Actual cycle time (seconds)
float32 setup_time                   # Setup time (seconds)

# Parameters recorded during operation
KeyValue[] parameters                # Feeds, speeds, etc.

# Traceability
string operator_id
string rosbag_path                   # Rosbag recording for this step
string[] sensor_data_refs            # References to sensor data

# Quality
bool passed_inline_check
string inline_check_notes
