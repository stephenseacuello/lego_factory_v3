# PrintJob.msg - 3D print job status and specification
# LEGO MCP Manufacturing System v7.0

std_msgs/Header header

# Job identification
string job_id                      # Unique job ID
string work_order_id               # Parent work order
string brick_id                    # Brick being printed

# Printer information
string printer_id                  # Printer executing job
string printer_type                # Type: fdm, sla, dlp

# File paths
string source_file                 # Original CAD file path
string sliced_file                 # Sliced file path (.gcode, .form, etc.)

# Print parameters
float32 layer_height               # Layer height in mm
float32 infill_percent             # Infill percentage (0-100)
float32 print_speed                # Print speed in mm/s
float32 nozzle_temp                # Nozzle temperature (FDM) in Celsius
float32 bed_temp                   # Bed temperature (FDM) in Celsius
float32 resin_temp                 # Resin temperature (SLA) in Celsius
float32 exposure_time              # Layer exposure time (SLA) in seconds

# Progress tracking
uint8 status                       # 0=queued, 1=preparing, 2=printing, 3=post_processing, 4=complete, 5=failed, 6=cancelled
float32 progress_percent           # 0.0 to 100.0
uint32 current_layer               # Current layer number
uint32 total_layers                # Total layers to print
float32 elapsed_time_sec           # Elapsed time in seconds
float32 estimated_remaining_sec    # Estimated remaining time

# Quality metrics
float32 estimated_material_grams   # Material usage estimate
float32 actual_material_grams      # Actual material used

# Timestamps
builtin_interfaces/Time created_at
builtin_interfaces/Time started_at
builtin_interfaces/Time completed_at

# Error handling
string error_message               # Error message if failed
uint8 retry_count                  # Number of retries attempted
