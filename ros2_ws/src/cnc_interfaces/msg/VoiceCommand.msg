# VoiceCommand.msg - Voice control commands

std_msgs/Header header

string session_id
string user_id

# Raw input
string raw_transcript      # Original speech-to-text output
float32 transcription_confidence

# Parsed command
uint8 COMMAND_UNKNOWN = 0
uint8 COMMAND_JOG = 1
uint8 COMMAND_HOME = 2
uint8 COMMAND_STOP = 3
uint8 COMMAND_EMERGENCY_STOP = 4
uint8 COMMAND_START = 5
uint8 COMMAND_PAUSE = 6
uint8 COMMAND_RESUME = 7
uint8 COMMAND_SPINDLE_ON = 8
uint8 COMMAND_SPINDLE_OFF = 9
uint8 COMMAND_COOLANT_ON = 10
uint8 COMMAND_COOLANT_OFF = 11
uint8 COMMAND_ZERO_AXIS = 12
uint8 COMMAND_GO_TO = 13
uint8 COMMAND_SET_FEED = 14
uint8 COMMAND_SET_SPEED = 15
uint8 COMMAND_LOAD_PROGRAM = 16
uint8 COMMAND_STATUS = 17
uint8 command_type

# Command parameters
string target_machine_id   # "tinyg_001", "all", "nearest"
string axis                # "x", "y", "z", "a", "b", "c"
float32 distance           # mm or inches
float32 speed              # mm/min or RPM
string direction           # "positive", "negative", "plus", "minus"
string program_name        # For LOAD_PROGRAM
geometry_msgs/Point target_position  # For GO_TO

# Intent parsing
string intent              # NLU intent label
float32 intent_confidence
KeyValue[] entities        # Extracted entities

# Execution
bool executed
bool success
string response_text       # Text to speak back
string error_message

# Safety
bool requires_confirmation
bool confirmed
uint8 safety_level         # 0=safe, 1=caution, 2=dangerous
