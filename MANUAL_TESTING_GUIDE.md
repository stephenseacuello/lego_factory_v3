# LEGO Factory v3 - Manual Testing Guide

## Prerequisites

```bash
# Activate virtual environment
cd /Users/stepheneacuello/Projects/lego_factory
source .venv/bin/activate

# Start the application (in one terminal)
python app.py

# In another terminal, run the tests below
```

---

## Phase 1: Production Control & Scheduling

### Test Dispatch Rules
```bash
# Get dispatch queue for a machine (default WSPT rule)
curl http://localhost:5000/api/mes/dispatch/queue?machine_id=bambu-ps1

# Set machine-specific dispatch rule
curl -X PUT http://localhost:5000/api/mes/machines/bambu-ps1/dispatch-rule \
  -H "Content-Type: application/json" \
  -d '{"rule": "critical_ratio"}'

# Get available dispatch rules
curl http://localhost:5000/api/mes/dispatch/rules
```

### Test Schedule Optimizer
```bash
# Get Gantt chart data (includes jobs, machines, critical path, maintenance windows)
curl http://localhost:5000/api/mes/scheduling/gantt | python3 -m json.tool

# Run CP-SAT optimizer with makespan objective
curl -X POST http://localhost:5000/api/mes/scheduling/reschedule \
  -H "Content-Type: application/json" \
  -d '{"algorithm": "cpsat", "objective": "makespan", "apply": true}'

# Run optimizer with due date objective (preview only)
curl -X POST http://localhost:5000/api/mes/scheduling/reschedule \
  -H "Content-Type: application/json" \
  -d '{"algorithm": "cpsat", "objective": "due_date", "apply": false}'

# Run optimizer with setup time minimization (heuristic)
curl -X POST http://localhost:5000/api/mes/scheduling/reschedule \
  -H "Content-Type: application/json" \
  -d '{"algorithm": "cpsat", "objective": "setup_time", "apply": true}'
```

### Test Auto-Dispatch
```bash
# Get available dispatch rules
curl http://localhost:5000/api/mes/dispatch/rules

# Auto-dispatch next job to a machine using WSPT rule
curl -X POST http://localhost:5000/api/mes/dispatch/auto/bambu-ps1 \
  -H "Content-Type: application/json" \
  -d '{"rule": "wspt"}'

# Auto-dispatch using balanced composite rule
curl -X POST http://localhost:5000/api/mes/dispatch/auto/bantam-explorer \
  -H "Content-Type: application/json" \
  -d '{"rule": "balanced"}'

# Auto-dispatch using EDD (Earliest Due Date)
curl -X POST http://localhost:5000/api/mes/dispatch/auto/rownd-lathe \
  -H "Content-Type: application/json" \
  -d '{"rule": "edd"}'
```

### Test What-If Simulation
```bash
# Simulate a rush order
curl -X POST http://localhost:5000/api/mes/scheduling/what-if \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Rush order scenario",
    "changes": [{
      "type": "add_job",
      "job_id": "RUSH-TEST",
      "work_order_id": "WO-RUSH",
      "duration_minutes": 120,
      "priority": 1,
      "setup_time": 10
    }]
  }'

# Simulate machine downtime
curl -X POST http://localhost:5000/api/mes/scheduling/what-if \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Machine down scenario",
    "changes": [{
      "type": "add_maintenance",
      "machine_id": "bambu-ps1",
      "start_time": "2026-02-17T10:00:00",
      "end_time": "2026-02-17T14:00:00"
    }]
  }'

# Simulate priority change
curl -X POST http://localhost:5000/api/mes/scheduling/what-if \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Priority bump",
    "changes": [{
      "type": "change_priority",
      "job_id": "JOB-2026-0050",
      "priority": 1
    }]
  }'
```

### Test Machine Feedback
```bash
# Simulate machine job completion signal
curl -X POST http://localhost:5000/api/mes/machine-feedback \
  -H "Content-Type: application/json" \
  -d '{
    "machine_id": "bambu-ps1",
    "event_type": "job_complete",
    "job_id": "test-job-001",
    "good_count": 95,
    "scrap_count": 5,
    "cycle_time_seconds": 120
  }'
```

---

## Phase 2: SCADA & Machine Monitoring

### Test Predictive Alarms
```bash
# Process sensor reading with dynamic threshold calculation
curl -X POST http://localhost:5000/api/scada/sensor-reading \
  -H "Content-Type: application/json" \
  -d '{
    "tag_id": "TEMP-001",
    "tag_name": "Extruder Temperature",
    "value": 215.5,
    "alarm_thresholds": {"high": 250, "low": 180}
  }'

# Get tag statistics
curl http://localhost:5000/api/scada/tags/TEMP-001/statistics

# Get active trend alerts
curl http://localhost:5000/api/scada/alarms/trend-alerts
```

### Test Anomaly Detection
```bash
# Feed multiple readings to train the model (run 50+ times with slight variations)
for i in {1..50}; do
  curl -s -X POST http://localhost:5000/api/scada/anomaly/analyze \
    -H "Content-Type: application/json" \
    -d "{\"tag_id\": \"PRES-001\", \"tag_name\": \"Pressure Sensor\", \"value\": $((100 + RANDOM % 5))}"
done

# Now inject an anomaly
curl -X POST http://localhost:5000/api/scada/anomaly/analyze \
  -H "Content-Type: application/json" \
  -d '{"tag_id": "PRES-001", "tag_name": "Pressure Sensor", "value": 200}'

# Check active anomalies
curl http://localhost:5000/api/scada/anomaly/active
```

### Test Recipe Tracking
```bash
# Create a new recipe
curl -X POST http://localhost:5000/api/mes/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PLA Standard Print",
    "product_id": "BRICK-2x4-RED",
    "machine_type": "fdm",
    "description": "Standard PLA printing parameters",
    "parameters": [
      {"name": "nozzle_temp", "value": 215, "unit": "C", "is_critical": true},
      {"name": "bed_temp", "value": 60, "unit": "C"},
      {"name": "print_speed", "value": 50, "unit": "mm/s"},
      {"name": "layer_height", "value": 0.2, "unit": "mm"}
    ],
    "created_by": "engineer_01"
  }'

# List all recipes
curl http://localhost:5000/api/mes/recipes

# Get recipe version history (replace RCP-XXXXXXXX with actual ID)
curl http://localhost:5000/api/mes/recipes/RCP-XXXXXXXX/history

# Submit for approval
curl -X POST http://localhost:5000/api/mes/recipes/RCP-XXXXXXXX/versions/1/submit \
  -H "Content-Type: application/json" \
  -d '{"submitted_by": "engineer_01"}'

# Approve recipe (replace APR-XXXXXXXX with request ID)
curl -X POST http://localhost:5000/api/mes/recipes/approvals/APR-XXXXXXXX/approve \
  -H "Content-Type: application/json" \
  -d '{"approver": "quality_manager", "comments": "Looks good"}'
```

---

## Phase 3: CMMS & Maintenance

### Test Reliability Analysis (Weibull)
```bash
# Perform Weibull analysis with failure data
curl -X POST http://localhost:5000/api/cmms/reliability/weibull \
  -H "Content-Type: application/json" \
  -d '{
    "machine_id": "cnc-1",
    "failure_times_hours": [150, 280, 350, 420, 510, 630, 720, 850, 920, 1050]
  }'

# Get reliability metrics
curl http://localhost:5000/api/cmms/machines/cnc-1/reliability
```

### Test FMEA
```bash
# Create FMEA item
curl -X POST http://localhost:5000/api/cmms/fmea \
  -H "Content-Type: application/json" \
  -d '{
    "machine_id": "cnc-1",
    "component": "Spindle Motor",
    "failure_mode": "Bearing wear",
    "failure_effect": "Spindle vibration, poor surface finish",
    "severity": 8,
    "occurrence": 5,
    "detection": 6,
    "current_controls": "Monthly vibration check"
  }'

# Get FMEA analysis for machine
curl http://localhost:5000/api/cmms/machines/cnc-1/fmea
```

### Test Spare Parts Optimization
```bash
# Calculate optimal inventory for a part
curl -X POST http://localhost:5000/api/cmms/spare-parts/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "part_id": "BEARING-6205",
    "annual_usage": 24,
    "unit_cost": 45.00,
    "lead_time_days": 14,
    "service_level": 0.95
  }'

# Get ABC classification
curl http://localhost:5000/api/cmms/spare-parts/abc-analysis

# Check for obsolete parts
curl http://localhost:5000/api/cmms/spare-parts/obsolescence
```

### Test PM Calendar
```bash
# Get PM schedule with production integration
curl "http://localhost:5000/api/cmms/pm/calendar?start_date=2026-02-01&end_date=2026-02-28"

# Cluster PM tasks to minimize disruption
curl -X POST http://localhost:5000/api/cmms/pm/cluster \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-02-15", "max_tasks_per_day": 3}'

# Get compliance status
curl http://localhost:5000/api/cmms/pm/compliance
```

---

## Phase 4: Quality Management

### Test SPC
```bash
# Record SPC measurements
curl -X POST http://localhost:5000/api/qms/spc/measurements \
  -H "Content-Type: application/json" \
  -d '{
    "characteristic_id": "DIM-LENGTH-001",
    "values": [10.02, 10.01, 9.99, 10.03, 10.00],
    "machine_id": "cnc-1",
    "operator_id": "OP-001"
  }'

# Set specification limits
curl -X POST http://localhost:5000/api/qms/spc/specifications \
  -H "Content-Type: application/json" \
  -d '{
    "characteristic_id": "DIM-LENGTH-001",
    "usl": 10.10,
    "target": 10.00,
    "lsl": 9.90
  }'

# Record more measurements (repeat 25+ times for control limits)
for i in {1..25}; do
  curl -s -X POST http://localhost:5000/api/qms/spc/measurements \
    -H "Content-Type: application/json" \
    -d "{\"characteristic_id\": \"DIM-LENGTH-001\", \"values\": [$(echo "scale=2; 10 + ($RANDOM % 10 - 5) / 100" | bc)], \"machine_id\": \"cnc-1\"}"
done

# Get control chart data
curl http://localhost:5000/api/qms/spc/control-chart/DIM-LENGTH-001

# Calculate capability
curl http://localhost:5000/api/qms/spc/capability/DIM-LENGTH-001
```

### Test First Article Inspection
```bash
# Create FAI
curl -X POST http://localhost:5000/api/qms/fai \
  -H "Content-Type: application/json" \
  -d '{
    "part_number": "BRICK-2x4-RED",
    "part_name": "2x4 LEGO Brick Red",
    "revision": "A",
    "work_order_id": "WO-001",
    "created_by": "inspector_01"
  }'

# Add characteristic to FAI (replace FAI-XXXXXXXX)
curl -X POST http://localhost:5000/api/qms/fai/FAI-XXXXXXXX/characteristics \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Overall Length",
    "nominal": 31.8,
    "upper_limit": 32.0,
    "lower_limit": 31.6,
    "unit": "mm"
  }'

# Record measurement
curl -X POST http://localhost:5000/api/qms/fai/FAI-XXXXXXXX/measurements \
  -H "Content-Type: application/json" \
  -d '{
    "char_id": "FAI-XXXXXXXX-001",
    "measured_value": 31.85,
    "measured_by": "inspector_01"
  }'

# Submit for review
curl -X POST http://localhost:5000/api/qms/fai/FAI-XXXXXXXX/submit \
  -H "Content-Type: application/json" \
  -d '{"submitted_by": "inspector_01"}'
```

---

## Phase 5: Production Performance

### Test Takt Time Monitoring
```bash
# Calculate takt time
curl "http://localhost:5000/api/mes/takt/calculate?demand_qty=480&available_hours=8"

# Record cycle times
for i in {1..20}; do
  curl -s -X POST http://localhost:5000/api/mes/takt/cycle \
    -H "Content-Type: application/json" \
    -d "{\"work_center_id\": \"WC-ASSEMBLY\", \"cycle_seconds\": $((58 + RANDOM % 8)), \"takt_target_seconds\": 60}"
done

# Get real-time takt status
curl "http://localhost:5000/api/mes/takt/status/WC-ASSEMBLY?takt_target=60"

# Get takt alerts
curl http://localhost:5000/api/mes/takt/alerts

# Line balance analysis
curl -X POST http://localhost:5000/api/mes/takt/line-balance \
  -H "Content-Type: application/json" \
  -d '{
    "takt_seconds": 60,
    "operations": [
      {"name": "Injection", "cycle_seconds": 45},
      {"name": "Cooling", "cycle_seconds": 55},
      {"name": "Ejection", "cycle_seconds": 35},
      {"name": "QC Check", "cycle_seconds": 62}
    ]
  }'
```

### Test Setup/SMED Tracking
```bash
# Start a setup
curl -X POST http://localhost:5000/api/mes/setup/start \
  -H "Content-Type: application/json" \
  -d '{
    "machine_id": "bambu-ps1",
    "job_id": "JOB-002",
    "from_product": "BRICK-2x4-RED",
    "to_product": "BRICK-2x4-BLUE",
    "operator_id": "OP-001"
  }'

# Complete setup (replace SETUP-XXXXXXXX)
curl -X POST http://localhost:5000/api/mes/setup/SETUP-XXXXXXXX/complete \
  -H "Content-Type: application/json" \
  -d '{"notes": "Smooth changeover"}'

# Get setup trends
curl "http://localhost:5000/api/mes/setup/trends?machine_id=bambu-ps1"

# Get setup benchmarks
curl http://localhost:5000/api/mes/setup/benchmarks

# Create SMED project
curl -X POST http://localhost:5000/api/mes/setup/smed-project \
  -H "Content-Type: application/json" \
  -d '{
    "machine_id": "bambu-ps1",
    "from_product": "BRICK-2x4-RED",
    "to_product": "BRICK-2x4-BLUE",
    "target_minutes": 10
  }'
```

### Test WIP & Kanban
```bash
# Get WIP levels
curl http://localhost:5000/api/mes/wip/levels

# Get kanban board
curl http://localhost:5000/api/mes/wip/kanban-board

# Get WIP aging analysis
curl http://localhost:5000/api/mes/wip/aging

# Get kanban signals
curl http://localhost:5000/api/mes/wip/kanban-signals

# Get constraint analysis
curl http://localhost:5000/api/mes/wip/constraints

# Create kanban card
curl -X POST http://localhost:5000/api/mes/wip/kanban-card \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "BRICK-2x4-RED",
    "work_center_id": "WC-ASSEMBLY",
    "target_qty": 100,
    "reorder_point": 30
  }'
```

### Test OEE
```bash
# Get real-time OEE
curl "http://localhost:5000/api/mes/oee/realtime/bambu-ps1"

# Get OEE waterfall breakdown
curl "http://localhost:5000/api/mes/oee/waterfall/bambu-ps1?date=2026-02-05"

# Get Six Big Losses analysis
curl "http://localhost:5000/api/mes/oee/six-big-losses/bambu-ps1"

# Compare OEE by shift
curl http://localhost:5000/api/mes/oee/compare/shift

# Compare OEE by machine
curl http://localhost:5000/api/mes/oee/compare/machine
```

---

## Phase 6: Production Integration

### Test Material Shortage Resolution
```bash
# Check material availability
curl -X POST http://localhost:5000/api/mes/materials/check \
  -H "Content-Type: application/json" \
  -d '{
    "material_id": "PLA",
    "quantity_required": 100,
    "job_id": "JOB-003",
    "work_order_id": "WO-002"
  }'

# Get material alternatives
curl "http://localhost:5000/api/mes/materials/alternatives?material_id=PLA&quantity=50"

# Get active shortages
curl http://localhost:5000/api/mes/materials/shortages
```

### Test Labor & Skill Management
```bash
# Register a worker
curl -X POST http://localhost:5000/api/mes/workers \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "W001",
    "name": "John Smith",
    "department": "Production",
    "hire_date": "2023-01-15",
    "hourly_rate": 28.50,
    "primary_machines": ["bambu-ps1", "bambu-ps2"]
  }'

# Add skill to worker
curl -X POST http://localhost:5000/api/mes/workers/W001/skills \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "FDM_OPERATION",
    "skill_name": "FDM Printer Operation",
    "level": 4,
    "required_for_machines": ["bambu-ps1", "bambu-ps2"]
  }'

# Add certification
curl -X POST http://localhost:5000/api/mes/workers/W001/certifications \
  -H "Content-Type: application/json" \
  -d '{
    "certification_type": "safety",
    "certification_name": "Machine Safety",
    "issued_date": "2025-01-01",
    "expiry_date": "2027-01-01",
    "issuing_authority": "Internal"
  }'

# Clock in
curl -X POST http://localhost:5000/api/mes/timeclock/clock-in \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "W001",
    "machine_id": "bambu-ps1",
    "job_id": "JOB-001"
  }'

# Clock out
curl -X POST http://localhost:5000/api/mes/timeclock/clock-out \
  -H "Content-Type: application/json" \
  -d '{"worker_id": "W001"}'

# Get skill matrix
curl http://localhost:5000/api/mes/skills/matrix

# Get expiring certifications
curl http://localhost:5000/api/mes/certifications/expiring

# Get cross-training recommendations
curl http://localhost:5000/api/mes/skills/cross-training
```

### Test Genealogy & Traceability
```bash
# Create product record (requires database session - use via app)
curl -X POST http://localhost:5000/api/mes/genealogy/products \
  -H "Content-Type: application/json" \
  -d '{
    "work_order_id": "WO-001",
    "product_id": "BRICK-2x4-RED",
    "product_name": "2x4 LEGO Brick Red",
    "batch_number": "BATCH-2026-02-001"
  }'

# Record process step (replace serial number)
curl -X POST http://localhost:5000/api/mes/genealogy/SN-XXXXXXXX/steps \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "OP-INJECT",
    "operation_name": "Injection Molding",
    "sequence": 1,
    "machine_id": "inj-01",
    "parameters": {"temp": 220, "pressure": 85},
    "quality_result": "passed"
  }'

# Backward trace (what went into this product?)
curl http://localhost:5000/api/mes/genealogy/trace/backward/SN-XXXXXXXX

# Forward trace (what products used this lot?)
curl http://localhost:5000/api/mes/genealogy/trace/forward/LOT-001

# Recall impact analysis
curl -X POST http://localhost:5000/api/mes/genealogy/recall-analysis \
  -H "Content-Type: application/json" \
  -d '{
    "lot_number": "LOT-001",
    "date_range_start": "2026-02-01T00:00:00",
    "date_range_end": "2026-02-05T23:59:59"
  }'

# Generate compliance report
curl "http://localhost:5000/api/mes/genealogy/SN-XXXXXXXX/compliance-report?standard=AS9100"

# Export FDA Device History Record
curl "http://localhost:5000/api/mes/genealogy/SN-XXXXXXXX/dhr"
```

---

## Dashboard Verification Guide

### 1. Production Dashboard (http://localhost:5000/dashboard)
- [ ] View real-time machine status
- [ ] Check OEE gauges for each machine
- [ ] Verify job queue display
- [ ] Test WebSocket updates (should auto-refresh)

### 2. SCADA Dashboard (http://localhost:5000/scada)
- [ ] View sensor readings with trend graphs
- [ ] Check alarm panel for active/historical alarms
- [ ] Verify predictive alerts show trend direction
- [ ] Test anomaly detection indicators

### 3. Quality Dashboard (http://localhost:5000/qms)
- [ ] View SPC control charts
- [ ] Check capability indices (Cp, Cpk)
- [ ] Review FAI status board
- [ ] Verify NCR tracking

### 4. Maintenance Dashboard (http://localhost:5000/cmms)
- [ ] View PM calendar
- [ ] Check reliability metrics (MTBF, MTTR)
- [ ] Review spare parts inventory status
- [ ] Verify work order queue

### 5. Scheduling Gantt Chart (http://localhost:5000/mes/scheduling)
- [ ] View Gantt chart with jobs across all machines
- [ ] Verify per-machine utilization badges show percentages
- [ ] Verify bottleneck machine row is highlighted (red accent)
- [ ] Verify critical path jobs have orange glow
- [ ] Verify dependency arrows render (orange curved, red bold for critical path)
- [ ] Verify maintenance window blocks appear (hatched overlay with wrench icon)
- [ ] Hover a job to see tooltip (product, WO, duration, priority, machine util%)
- [ ] Click a job to open detail modal (duration, priority badge, eligible machines)
- [ ] Drag a job between eligible machines (green highlight on valid targets)
- [ ] Click "Run Optimizer" → select objective → click Run → verify before/after table
- [ ] Toggle "Auto-Dispatch" → verify button turns green
- [ ] Click play button on a machine row → verify dispatch toast appears
- [ ] Click "What-If" → select Rush Order tab → click Simulate → verify impact analysis
- [ ] Use search bar to filter by product name → verify matching jobs glow yellow, others dim
- [ ] Click "Overdue" quick filter → verify only overdue jobs highlighted
- [ ] Click "Critical Path" quick filter → verify only critical path jobs highlighted
- [ ] Switch views: Day / Week / Month
- [ ] Verify 6-metric stats bar: Scheduled, Makespan, Utilization, On-Time%, Bottleneck, Overdue
- [ ] Verify legend shows: statuses, priority levels, dependency, critical path, maintenance

### 6. Kanban Board (http://localhost:5000/mes/kanban)
- [ ] View visual kanban cards
- [ ] Check WIP limits per machine
- [ ] Verify kanban signals (replenish/stop)
- [ ] Test drag-and-drop job movement

### 6. Reports (http://localhost:5000/reports)
- [ ] Generate OEE report by date range
- [ ] Export production genealogy report
- [ ] View setup time trends
- [ ] Check labor utilization report

---

## Quick Health Check Script

```bash
#!/bin/bash
# Save as test_health.sh and run: bash test_health.sh

BASE_URL="http://localhost:5000"

echo "=== LEGO Factory v3 Health Check ==="

# Check main endpoints
endpoints=(
  "/api/health"
  "/api/mes/scheduling/gantt"
  "/api/mes/dispatch/rules"
  "/api/mes/oee/realtime/bambu-ps1"
  "/api/mes/wip/levels"
  "/api/cmms/pm/compliance"
  "/api/qms/spc/charts"
)

for endpoint in "${endpoints[@]}"; do
  response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
  if [ "$response" == "200" ]; then
    echo "✓ $endpoint"
  else
    echo "✗ $endpoint (HTTP $response)"
  fi
done

echo "=== Health Check Complete ==="
```

---

## Troubleshooting

### If API returns 404:
- Check if the route is registered in `api/routes/`
- Verify the app blueprint is loaded

### If database errors occur:
```bash
# Reset and migrate database
flask db upgrade
```

### If WebSocket doesn't connect:
```bash
# Verify Flask-SocketIO is running
# Check browser console for connection errors
```

### View logs:
```bash
tail -f logs/app.log
```
