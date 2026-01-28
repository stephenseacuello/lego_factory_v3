# BarcodeReading.msg - Barcode/QR code scanning

std_msgs/Header header

string scanner_id
string machine_id

# Barcode data
string raw_data               # Raw barcode content
string decoded_data           # Parsed/cleaned data

# Barcode type
uint8 TYPE_UNKNOWN = 0
uint8 TYPE_CODE128 = 1
uint8 TYPE_CODE39 = 2
uint8 TYPE_EAN13 = 3
uint8 TYPE_UPCA = 4
uint8 TYPE_QR = 5
uint8 TYPE_DATAMATRIX = 6
uint8 TYPE_PDF417 = 7
uint8 TYPE_AZTEC = 8
uint8 barcode_type

# Scan context
uint8 CONTEXT_PART = 0
uint8 CONTEXT_TOOL = 1
uint8 CONTEXT_MATERIAL = 2
uint8 CONTEXT_FIXTURE = 3
uint8 CONTEXT_OPERATOR = 4
uint8 CONTEXT_WORK_ORDER = 5
uint8 CONTEXT_LOT = 6
uint8 context

# Parsed fields (from GS1/structured barcodes)
string part_number
string serial_number
string lot_number
string work_order
builtin_interfaces/Time expiration_date
string vendor_id
KeyValue[] custom_fields

# Scan quality
float32 scan_confidence       # 0.0-1.0
uint32 scan_attempts
bool verified                 # Cross-checked with database

# Location
geometry_msgs/Point scan_location
string station_id

# Validation
bool valid
bool in_database
string validation_message
string[] warnings
