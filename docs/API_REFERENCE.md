# API Reference

Complete API documentation for LEGO Factory v3.

## Table of Contents

- [Authentication](#authentication)
- [Common Patterns](#common-patterns)
- [ERP APIs](#erp-apis)
- [MES APIs](#mes-apis)
- [SCADA APIs](#scada-apis)
- [CMMS APIs](#cmms-apis)
- [QMS APIs](#qms-apis)
- [ML APIs](#ml-apis)
- [Error Handling](#error-handling)

---

## Authentication

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOi...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### Using the Token

```http
GET /api/v1/erp/items
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOi...
```

### Refresh Token

```http
POST /api/auth/refresh
Authorization: Bearer YOUR_REFRESH_TOKEN
```

---

## Common Patterns

### Pagination

```http
GET /api/v1/erp/items?limit=50&offset=100
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Maximum items to return |
| `offset` | int | 0 | Number of items to skip |

### Filtering

```http
GET /api/v1/erp/items?item_type=raw_material&status=active
```

### Sorting

```http
GET /api/v1/erp/items?sort=name&order=asc
```

### Date Ranges

```http
GET /api/v1/erp/sales-orders?start_date=2024-01-01&end_date=2024-12-31
```

---

## ERP APIs

Base URL: `/api/v1/erp`

### Items

#### List Items

```http
GET /api/v1/erp/items
```

**Query Parameters:**
- `item_type`: Filter by type (`raw_material`, `component`, `finished_good`)
- `search`: Search by name or ID
- `limit`, `offset`: Pagination

**Response:**
```json
[
  {
    "item_id": "BRICK-2X4-RED",
    "name": "2x4 Brick Red",
    "item_type": "finished_good",
    "base_uom": "EA",
    "standard_cost": 0.15,
    "list_price": 0.25,
    "track_inventory": true,
    "is_salable": true,
    "is_purchasable": false,
    "is_manufactured": true
  }
]
```

#### Create Item

```http
POST /api/v1/erp/items
Content-Type: application/json

{
  "name": "2x4 Brick Blue",
  "item_type": "finished_good",
  "base_uom": "EA",
  "standard_cost": 0.15,
  "list_price": 0.25,
  "is_manufactured": true
}
```

#### Get Item

```http
GET /api/v1/erp/items/{item_id}
```

#### Update Item

```http
PUT /api/v1/erp/items/{item_id}
Content-Type: application/json

{
  "list_price": 0.30
}
```

### Bill of Materials (BOM)

#### Get BOM

```http
GET /api/v1/erp/items/{item_id}/bom
```

**Response:**
```json
{
  "parent_item_id": "BRICK-2X4-RED",
  "lines": [
    {
      "component_id": "ABS-RED",
      "quantity": 5.2,
      "uom": "G",
      "scrap_factor": 2.0
    }
  ]
}
```

#### Add BOM Line

```http
POST /api/v1/erp/items/{item_id}/bom
Content-Type: application/json

{
  "component_id": "ABS-RED",
  "quantity": 5.2,
  "uom": "G",
  "scrap_factor": 2.0
}
```

#### Explode BOM

```http
GET /api/v1/erp/items/{item_id}/bom/explode?quantity=100&max_level=5
```

### Sales Orders

#### List Orders

```http
GET /api/v1/erp/sales-orders
```

**Query Parameters:**
- `customer_id`: Filter by customer
- `status`: Filter by status (`draft`, `confirmed`, `released`, `shipped`, `closed`)
- `start_date`, `end_date`: Date range filter

#### Create Order

```http
POST /api/v1/erp/sales-orders
Content-Type: application/json

{
  "customer_id": "CUST-001",
  "requested_date": "2024-02-15",
  "lines": [
    {
      "item_id": "BRICK-2X4-RED",
      "quantity": 500,
      "unit_price": 0.25
    }
  ]
}
```

#### Confirm Order

```http
POST /api/v1/erp/sales-orders/{order_number}/confirm
```

#### Release Order

```http
POST /api/v1/erp/sales-orders/{order_number}/release
```

#### Create Shipment

```http
POST /api/v1/erp/sales-orders/{order_number}/shipments
Content-Type: application/json

{
  "carrier": "UPS",
  "tracking_number": "1Z999999999",
  "lines": [
    {"line_number": 1, "quantity_shipped": 500}
  ]
}
```

### Purchase Orders

#### Create PO

```http
POST /api/v1/erp/purchase-orders
Content-Type: application/json

{
  "vendor_id": "VENDOR-001",
  "lines": [
    {
      "item_id": "ABS-RED",
      "quantity": 10000,
      "unit_price": 0.02
    }
  ]
}
```

#### Approve PO

```http
POST /api/v1/erp/purchase-orders/{po_number}/approve
```

#### Receive Goods

```http
POST /api/v1/erp/purchase-orders/{po_number}/receipts
Content-Type: application/json

{
  "lines": [
    {
      "line_number": 1,
      "quantity_received": 9500,
      "quantity_rejected": 500
    }
  ]
}
```

### MRP (Material Requirements Planning)

#### Run MRP

```http
POST /api/v1/erp/mrp/run
Content-Type: application/json

{
  "horizon_days": 90,
  "include_safety_stock": true,
  "generate_planned_orders": true
}
```

**Response:**
```json
{
  "plan_id": "MRP-2024-001",
  "plan_date": "2024-01-21",
  "horizon_days": 90,
  "requirements_count": 150,
  "planned_orders_count": 45,
  "action_messages": [
    "EXPEDITE: COMP-001 order needed by 2024-01-25"
  ]
}
```

#### Get Item Demand

```http
GET /api/v1/erp/mrp/demand/{item_id}?days=30
```

#### Get Capacity Requirements

```http
GET /api/v1/erp/mrp/capacity?days=30
```

### Inventory

#### Get Balance

```http
GET /api/v1/erp/inventory/{item_id}
```

**Response:**
```json
{
  "item_id": "BRICK-2X4-RED",
  "quantity_on_hand": 5000,
  "quantity_allocated": 1200,
  "quantity_available": 3800,
  "locations": [
    {"location_id": "WH-01", "quantity": 3000},
    {"location_id": "WH-02", "quantity": 2000}
  ]
}
```

#### Adjust Inventory

```http
POST /api/v1/erp/inventory/adjust
Content-Type: application/json

{
  "item_id": "BRICK-2X4-RED",
  "location_id": "WH-01",
  "quantity": -50,
  "reason": "scrap",
  "reference": "ADJ-001"
}
```

---

## MES APIs

Base URL: `/api/mes`

### Work Orders

#### List Work Orders

```http
GET /api/mes/work-orders
```

**Query Parameters:**
- `status`: Filter by status
- `product_id`: Filter by product
- `machine_id`: Filter by assigned machine

#### Create Work Order

```http
POST /api/mes/work-orders
Content-Type: application/json

{
  "product_id": "BRICK-2X4-RED",
  "quantity_ordered": 500,
  "priority": 3,
  "due_date": "2024-02-15",
  "work_center_id": "WC-INJECTION"
}
```

#### Release Work Order

```http
POST /api/mes/work-orders/{work_order_id}/release
```

#### Start Work Order

```http
POST /api/mes/work-orders/{work_order_id}/start
Content-Type: application/json

{
  "machine_id": "MACHINE-001",
  "operator_id": "USER-001"
}
```

#### Complete Work Order

```http
POST /api/mes/work-orders/{work_order_id}/complete
Content-Type: application/json

{
  "quantity_completed": 495,
  "quantity_rejected": 5,
  "completion_notes": "Completed with minor rejects"
}
```

### Scheduling & Optimization

#### Get Gantt Chart Data

Returns all machines, scheduled jobs, dependency chains, critical path, and maintenance windows for Gantt visualization.

```http
GET /api/mes/scheduling/gantt
```

**Response:**
```json
{
  "machines": [
    {"id": "bambu-ps1", "name": "Bambu Lab P1S", "status": "running"}
  ],
  "jobs": [
    {
      "job_id": "JOB-2026-0001",
      "machine_id": "bambu-ps1",
      "work_order_id": "WO-2026-P001",
      "start": "2026-02-16T08:00:00",
      "end": "2026-02-16T09:30:00",
      "status": "running",
      "product": "Injection - 2x4 Brick Red",
      "priority": 3,
      "eligible_machines": ["bambu-ps1", "creality-cr30"],
      "depends_on": null
    }
  ],
  "time_range": {
    "start": "2026-02-15T08:00:00",
    "end": "2026-02-18T08:00:00"
  },
  "critical_path": {
    "job_ids": ["JOB-2026-0068", "JOB-2026-0069", "JOB-2026-0070"],
    "total_duration_minutes": 252,
    "jobs_count": 3
  },
  "maintenance_windows": [
    {
      "machine_id": "creality-cr30",
      "start": "2026-02-17T10:00:00",
      "end": "2026-02-17T12:00:00",
      "type": "maintenance",
      "reason": "PM - Belt tension & calibration"
    }
  ]
}
```

#### Run Schedule Optimizer

Runs the CP-SAT constraint solver or heuristic to optimize the schedule. Supports three objectives.

```http
POST /api/mes/scheduling/reschedule
Content-Type: application/json

{
  "algorithm": "cpsat",
  "objective": "makespan",
  "apply": true
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `algorithm` | string | No | `cpsat` (default) or `heuristic` |
| `objective` | string | No | `makespan` (default), `due_date`, or `setup_time` |
| `apply` | boolean | No | Whether to persist changes (default: true) |

**Response:**
```json
{
  "makespan": 562,
  "total_setup_time": 45,
  "scheduled_count": 74,
  "unscheduled_count": 0,
  "solver_status": "OPTIMAL",
  "applied": true,
  "schedule": [
    {
      "job_id": "JOB-2026-0001",
      "machine_id": "bambu-ps1",
      "start_time": "2026-02-16T08:00:00",
      "end_time": "2026-02-16T09:30:00"
    }
  ]
}
```

#### What-If Scenario Simulation

Simulates schedule changes without modifying the actual schedule.

```http
POST /api/mes/scheduling/what-if
Content-Type: application/json

{
  "name": "Rush order test",
  "changes": [
    {
      "type": "add_job",
      "job_id": "RUSH-001",
      "work_order_id": "WO-RUSH",
      "duration_minutes": 120,
      "priority": 1,
      "setup_time": 10
    }
  ]
}
```

**Change Types:**

| Type | Fields | Description |
|------|--------|-------------|
| `add_job` | `job_id`, `duration_minutes`, `priority`, `setup_time` | Inject a new job |
| `add_maintenance` | `machine_id`, `start_time`, `end_time` | Add machine downtime |
| `change_priority` | `job_id`, `priority` | Change a job's priority |

**Response:**
```json
{
  "scenario_id": "WIF-20260217-001",
  "makespan_delta": 45,
  "jobs_affected": ["JOB-2026-0010", "JOB-2026-0015"],
  "original": {"makespan": 562, "unscheduled": 0},
  "modified": {"makespan": 607, "unscheduled": 0},
  "recommendations": [
    "Warning: Rush order increases makespan by 45 minutes",
    "Note: 2 jobs will shift to accommodate rush order"
  ]
}
```

#### Reschedule Individual Job

Move a job to a different machine or time slot.

```http
POST /api/mes/jobs/{job_id}/reschedule
Content-Type: application/json

{
  "machine_id": "bambu-ps1",
  "scheduled_start": "2026-02-16T10:00:00",
  "scheduled_end": "2026-02-16T11:30:00",
  "force": false
}
```

Returns `409 Conflict` with `conflicts` array if scheduling conflicts are detected (unless `force: true`).

### Dispatch

#### Get Dispatch Rules

```http
GET /api/mes/dispatch/rules
```

**Response:**
```json
{
  "rules": ["spt", "lpt", "edd", "fifo", "wspt", "critical_ratio", "setup_min", "slack_time"],
  "composite_rules": ["balanced", "urgent_first", "efficient"]
}
```

#### Auto-Dispatch Next Job

Automatically selects and dispatches the best job for a machine based on the selected rule.

```http
POST /api/mes/dispatch/auto/{machine_id}
Content-Type: application/json

{
  "rule": "balanced"
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "JOB-2026-0042",
  "machine_id": "bambu-ps1",
  "rule": "balanced",
  "score": 0.87
}
```

#### Get Dispatch Queue

```http
GET /api/mes/dispatch/queue?machine_id=bambu-ps1&rule=wspt
```
```

### OEE (Overall Equipment Effectiveness)

#### Calculate OEE

```http
GET /api/mes/oee?machine_id=MACHINE-001&date=2024-01-21
```

**Response:**
```json
{
  "machine_id": "MACHINE-001",
  "date": "2024-01-21",
  "oee": 78.5,
  "availability": 90.0,
  "performance": 92.0,
  "quality": 95.0,
  "scheduled_time": 480,
  "operating_time": 432,
  "total_count": 1000,
  "good_count": 950
}
```

#### Record Downtime

```http
POST /api/mes/downtime
Content-Type: application/json

{
  "machine_id": "MACHINE-001",
  "reason": "maintenance_unplanned",
  "start_time": "2024-01-21T10:00:00",
  "end_time": "2024-01-21T10:45:00",
  "notes": "Bearing replacement"
}
```

#### Get Downtime Pareto

```http
GET /api/mes/oee/pareto?machine_id=MACHINE-001&start_date=2024-01-01&end_date=2024-01-31
```

---

## SCADA APIs

Base URL: `/api/scada`

### Tags

#### List Tags

```http
GET /api/scada/tags
```

#### Read Tag Value

```http
GET /api/scada/tags/{tag_name}/value
```

**Response:**
```json
{
  "tag_name": "conveyor_speed",
  "value": 125.5,
  "quality": "good",
  "timestamp": "2024-01-21T14:30:00Z"
}
```

#### Write Tag Value

```http
PUT /api/scada/tags/{tag_name}/value
Content-Type: application/json

{
  "value": 150.0
}
```

### Alarms

#### Get Active Alarms

```http
GET /api/scada/alarms/active
```

**Response:**
```json
[
  {
    "alarm_id": "ALM-001",
    "tag_name": "motor_temp",
    "state": "active",
    "priority": "high",
    "message": "Motor temperature exceeded limit",
    "triggered_at": "2024-01-21T14:25:00Z",
    "value": 85.5,
    "setpoint": 80.0
  }
]
```

#### Acknowledge Alarm

```http
POST /api/scada/alarms/{alarm_id}/acknowledge
Content-Type: application/json

{
  "user_id": "operator1",
  "comment": "Investigating"
}
```

#### Shelve Alarm

```http
POST /api/scada/alarms/{alarm_id}/shelve
Content-Type: application/json

{
  "duration_minutes": 60,
  "reason": "Planned maintenance"
}
```

### Historian

#### Query Historical Data

```http
GET /api/scada/historian/query?tags=conveyor_speed,motor_temp&start=2024-01-21T00:00:00&end=2024-01-21T23:59:59&interval=1m
```

**Response:**
```json
{
  "tags": ["conveyor_speed", "motor_temp"],
  "start": "2024-01-21T00:00:00Z",
  "end": "2024-01-21T23:59:59Z",
  "interval": "1m",
  "data": [
    {
      "timestamp": "2024-01-21T00:00:00Z",
      "values": {"conveyor_speed": 120.5, "motor_temp": 45.2}
    }
  ]
}
```

---

## CMMS APIs

Base URL: `/api/v1/cmms`

### Assets

#### List Assets

```http
GET /api/v1/cmms/assets
```

#### Create Asset

```http
POST /api/v1/cmms/assets
Content-Type: application/json

{
  "name": "CNC Machine #1",
  "asset_class_code": "CNC",
  "status": "operational",
  "criticality": "critical",
  "serial_number": "SN-12345",
  "manufacturer": "HAAS"
}
```

#### Get Asset Hierarchy

```http
GET /api/v1/cmms/assets/{asset_id}/hierarchy
```

### Meters

#### Create Meter

```http
POST /api/v1/cmms/assets/{asset_id}/meters
Content-Type: application/json

{
  "name": "Run Hours",
  "meter_type": "continuous",
  "unit_of_measure": "hours",
  "warning_threshold": 4500,
  "critical_threshold": 5000
}
```

#### Record Reading

```http
POST /api/v1/cmms/meters/{meter_id}/readings
Content-Type: application/json

{
  "reading_value": 4550,
  "source": "manual"
}
```

### PM Schedules

#### Create PM Schedule

```http
POST /api/v1/cmms/pm-schedules
Content-Type: application/json

{
  "name": "Monthly Inspection",
  "asset_id": "AST-001",
  "trigger_type": "calendar",
  "frequency_days": 30,
  "priority": "medium",
  "estimated_hours": 2.0,
  "instructions": "Perform monthly inspection checklist"
}
```

#### Generate PM Work Orders

```http
POST /api/v1/cmms/pm-schedules/generate?days_ahead=7
```

### Maintenance Work Orders

#### Create Work Order

```http
POST /api/v1/cmms/work-orders
Content-Type: application/json

{
  "asset_id": "AST-001",
  "wo_type": "corrective",
  "priority": "high",
  "description": "Motor overheating - investigate",
  "problem_code": "OVERHEAT"
}
```

#### Start Work Order

```http
POST /api/v1/cmms/work-orders/{wo_number}/start
Content-Type: application/json

{
  "user_id": "tech_001"
}
```

#### Complete Work Order

```http
POST /api/v1/cmms/work-orders/{wo_number}/complete
Content-Type: application/json

{
  "completion_notes": "Replaced faulty bearing",
  "actual_hours": 4.0,
  "failure_code": "BEARING_FAILURE",
  "action_code": "REPLACE"
}
```

#### Record Labor

```http
POST /api/v1/cmms/work-orders/{wo_number}/labor
Content-Type: application/json

{
  "worker_id": "tech_001",
  "craft": "electrician",
  "regular_hours": 4.0,
  "hourly_rate": 50.0
}
```

#### Record Material

```http
POST /api/v1/cmms/work-orders/{wo_number}/materials
Content-Type: application/json

{
  "description": "SKF Bearing 6205",
  "quantity_used": 2,
  "unit_cost": 25.0
}
```

---

## QMS APIs

Base URL: `/api/v1/qms`

### Documents

#### List Documents

```http
GET /api/v1/qms/documents
```

#### Create Document

```http
POST /api/v1/qms/documents
Content-Type: application/json

{
  "title": "Work Instruction - Brick Inspection",
  "document_type": "work_instruction",
  "category": "quality",
  "content": "..."
}
```

#### Submit for Review

```http
POST /api/v1/qms/documents/{document_id}/submit
```

#### Approve Document (with e-signature)

```http
POST /api/v1/qms/documents/{document_id}/approve
Content-Type: application/json

{
  "password": "user_password",
  "meaning": "I have reviewed and approve this document"
}
```

### NCR (Non-Conformance Reports)

#### Create NCR

```http
POST /api/v1/qms/ncrs
Content-Type: application/json

{
  "title": "Dimensional Non-Conformance - Brick 2x4",
  "ncr_type": "product",
  "severity": "major",
  "description": "Studs height out of tolerance",
  "detected_by": "inspector_001",
  "detected_at_operation": "inspection"
}
```

#### Assign NCR

```http
POST /api/v1/qms/ncrs/{ncr_number}/assign
Content-Type: application/json

{
  "assigned_to": "engineer_001"
}
```

#### Disposition NCR

```http
POST /api/v1/qms/ncrs/{ncr_number}/disposition
Content-Type: application/json

{
  "disposition": "rework",
  "disposition_notes": "Reprocess through finishing operation"
}
```

### CAPA (Corrective/Preventive Action)

#### Create CAPA

```http
POST /api/v1/qms/capas
Content-Type: application/json

{
  "title": "Reduce Dimensional Non-Conformances",
  "capa_type": "corrective",
  "source": "ncr",
  "source_reference": "NCR-2024-001",
  "problem_statement": "Recurring stud height issues"
}
```

#### Add Root Cause Analysis

```http
POST /api/v1/qms/capas/{capa_id}/root-cause
Content-Type: application/json

{
  "analysis_method": "5_why",
  "root_cause": "Tool wear not detected in time",
  "contributing_factors": ["No tool life monitoring", "Manual inspection only"]
}
```

---

## ML APIs

Base URL: `/api/ml`

### Anomaly Detection

#### Detect Anomalies

```http
POST /api/ml/anomaly/detect
Content-Type: application/json

{
  "machine_id": "MACHINE-001",
  "sensor_data": {
    "temperature": 75.5,
    "vibration": 0.8,
    "current": 12.5
  }
}
```

**Response:**
```json
{
  "is_anomaly": false,
  "anomaly_score": 0.23,
  "threshold": 0.5,
  "confidence": 0.89,
  "contributing_features": []
}
```

### Model Status

```http
GET /api/ml/status
```

**Response:**
```json
{
  "models": {
    "anomaly_detector": {
      "status": "loaded",
      "version": "v1.2.0",
      "last_trained": "2024-01-15T10:00:00Z"
    }
  }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": "validation_error",
  "message": "Invalid input data",
  "details": {
    "field": "quantity",
    "reason": "must be positive"
  },
  "timestamp": "2024-01-21T14:30:00Z",
  "request_id": "req-12345"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Business rule violation |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error |

### Common Error Codes

| Error | Description |
|-------|-------------|
| `validation_error` | Input validation failed |
| `not_found` | Resource not found |
| `already_exists` | Duplicate resource |
| `invalid_state` | Invalid state transition |
| `insufficient_inventory` | Not enough inventory |
| `authorization_failed` | Permission denied |

---

## Rate Limiting

API requests are rate limited:

- **Anonymous**: 60 requests/minute
- **Authenticated**: 1000 requests/minute
- **Admin**: Unlimited

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1705850400
```

---

## Versioning

The API uses URL versioning:

- Current: `/api/v1/`
- Legacy: `/api/` (deprecated, use v1)

Version changes follow semantic versioning. Breaking changes increment the major version.
