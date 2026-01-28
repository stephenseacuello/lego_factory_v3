# LEGO Factory v3 API Reference

## Base URL

```
http://localhost:5000/api
```

## Authentication

Currently uses session-based authentication. Login via `/api/auth/login`.

---

## SCADA API (`/api/scada`)

### Machines

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/machines` | List all machines |
| GET | `/machines/{id}` | Get machine details |
| POST | `/machines/{id}/connect` | Connect to machine |
| POST | `/machines/{id}/disconnect` | Disconnect from machine |
| GET | `/machines/{id}/status` | Get machine status |
| POST | `/machines/{id}/gcode` | Send G-code command |
| POST | `/machines/{id}/job/start` | Start a print job |
| POST | `/machines/{id}/job/pause` | Pause current job |
| POST | `/machines/{id}/job/resume` | Resume paused job |
| POST | `/machines/{id}/job/cancel` | Cancel current job |

### Tags

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tags` | List all tags |
| GET | `/tags/{id}` | Get tag value |
| PUT | `/tags/{id}` | Set tag value |

### Alarms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/alarms` | List alarms (filter: state, priority) |
| POST | `/alarms/{id}/acknowledge` | Acknowledge alarm |
| POST | `/alarms/{id}/shelve` | Shelve alarm |
| POST | `/alarms/{id}/unshelve` | Unshelve alarm |

### Historian

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/historian/query` | Query historical data |
| GET | `/historian/tags` | List historian tags |

---

## MES API (`/api/mes`)

### Work Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/work-orders` | List work orders |
| POST | `/work-orders` | Create work order |
| GET | `/work-orders/{id}` | Get work order details |
| PUT | `/work-orders/{id}` | Update work order |
| POST | `/work-orders/{id}/release` | Release work order |
| POST | `/work-orders/{id}/complete` | Complete work order |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List jobs |
| GET | `/jobs/{id}` | Get job details |
| POST | `/jobs/{id}/start` | Start job |
| POST | `/jobs/{id}/complete` | Complete job |

### OEE

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/oee` | Get OEE metrics |
| GET | `/oee/summary` | Get OEE summary |
| POST | `/downtime` | Report downtime |
| POST | `/production` | Report production |

### Recipes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/recipes` | List recipes |
| GET | `/recipes/{id}` | Get recipe details |
| POST | `/recipes/{id}/download` | Download to machine |

### Labor

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workers` | List workers |
| POST | `/time-entries` | Record time entry |
| POST | `/clock-in` | Clock in worker |
| POST | `/clock-out` | Clock out worker |

---

## ERP API (`/api/erp`)

### Sales

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sales-orders` | List sales orders |
| POST | `/sales-orders` | Create sales order |
| GET | `/sales-orders/{id}` | Get sales order |
| GET | `/customers` | List customers |
| GET | `/customers/{id}` | Get customer details |

### Purchasing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/purchase-orders` | List POs |
| POST | `/purchase-orders` | Create PO |
| GET | `/vendors` | List vendors |
| POST | `/receipts` | Record receipt |

### Inventory

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/inventory` | Get inventory balances |
| GET | `/items` | List items |
| GET | `/items/{id}` | Get item details |
| GET | `/bom/{item_id}` | Get bill of materials |
| POST | `/transfers` | Create inventory transfer |

### Planning

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/mrp/run` | Run MRP planning |
| GET | `/mrp/planned-orders` | Get planned orders |
| GET | `/forecasts` | Get demand forecasts |

---

## QMS API (`/api/qms`)

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/documents` | List documents |
| POST | `/documents` | Create document |
| GET | `/documents/{id}` | Get document |
| POST | `/documents/{id}/approve` | Approve document |
| POST | `/documents/{id}/release` | Release document |

### NCR/CAPA

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ncrs` | List NCRs |
| POST | `/ncrs` | Create NCR |
| GET | `/ncrs/{id}` | Get NCR details |
| PUT | `/ncrs/{id}` | Update NCR |
| GET | `/capas` | List CAPAs |
| POST | `/capas` | Create CAPA |

### Training

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/training/courses` | List courses |
| GET | `/training/records` | Get training records |
| POST | `/training/records` | Record training |

### Calibration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/calibration/equipment` | List calibrated equipment |
| POST | `/calibration/records` | Record calibration |
| GET | `/calibration/due` | Get calibrations due |

### Inspections

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/inspection/plans` | List inspection plans |
| POST | `/inspection/records` | Record inspection |

---

## CMMS API (`/api/cmms`)

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/assets` | List assets |
| GET | `/assets/{id}` | Get asset details |
| GET | `/assets/{id}/history` | Get maintenance history |

### Maintenance Work Orders

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/work-orders` | List MWOs |
| POST | `/work-orders` | Create MWO |
| GET | `/work-orders/{id}` | Get MWO details |
| PUT | `/work-orders/{id}` | Update MWO |
| POST | `/work-orders/{id}/complete` | Complete MWO |

### PM Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pm-schedules` | List PM schedules |
| POST | `/pm-schedules` | Create PM schedule |
| GET | `/pm-schedules/due` | Get PMs due |

### Spares

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/spares` | List spares |
| GET | `/spares/reorder` | Get reorder report |

---

## LEGO API (`/api/lego`)

### Catalog

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/catalog` | Browse brick catalog |
| GET | `/catalog/{part_number}` | Get brick template |
| GET | `/colors` | List LEGO colors |

### Designs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/designs` | List designs |
| POST | `/designs` | Create design |
| GET | `/designs/{id}` | Get design details |
| PUT | `/designs/{id}` | Update design |
| DELETE | `/designs/{id}` | Delete design |
| POST | `/designs/{id}/export` | Export design |
| GET | `/designs/{id}/stl` | Download STL |

### Export Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/export-jobs` | List export jobs |
| GET | `/export-jobs/{id}` | Get job status |
| GET | `/export-jobs/{id}/download` | Download output |

### Print Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profiles` | List print profiles |
| POST | `/profiles` | Create profile |

---

## ML API (`/api/ml`)

### Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Get ML service status |
| GET | `/models` | List loaded models |

### Inference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inference` | Run inference |
| POST | `/fingerprint` | Get G-code fingerprint |
| POST | `/predict/tool-wear` | Predict tool wear |

### Anomalies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/anomalies` | List detected anomalies |
| GET | `/anomalies/realtime` | Real-time anomaly stream |

---

## Unity API (`/api/unity`)

### State Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/state` | Get factory state |
| POST | `/command` | Send command from Unity |
| GET | `/events` | Get event stream (SSE) |

### Playback

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/playback/sessions` | List playback sessions |
| POST | `/playback/start` | Start playback |
| POST | `/playback/stop` | Stop playback |

---

## ROS2 API (`/api/ros2`)

### Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Get ROS2 bridge status |
| GET | `/nodes` | List active nodes |
| GET | `/topics` | List active topics |

### Robots

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/robots` | List robots |
| GET | `/robots/{id}` | Get robot status |
| POST | `/robots/{id}/move` | Move to position |
| POST | `/robots/{id}/pick` | Pick operation |
| POST | `/robots/{id}/place` | Place operation |
| POST | `/robots/{id}/home` | Home robot |
| POST | `/robots/{id}/stop` | Emergency stop |

### Cell Orchestration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cell/status` | Get cell status |
| POST | `/cell/run-cycle` | Run production cycle |

---

## MCP API (`/api/mcp`)

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tools` | List available MCP tools |
| POST | `/execute` | Execute MCP tool |

---

## PLC API (`/api/plc`)

### Connection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Get PLC connection status |
| POST | `/connect` | Connect to PLC |
| POST | `/disconnect` | Disconnect from PLC |

### Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/read` | Read PLC tags |
| POST | `/write` | Write PLC tags |

---

## Response Formats

### Success Response

```json
{
  "success": true,
  "data": { ... }
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error message",
  "code": "ERROR_CODE"
}
```

### Pagination

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

---

## WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:5000/ws/scada` | Real-time SCADA data |
| `ws://localhost:5000/ws/alarms` | Real-time alarm events |
| `ws://localhost:9090` | rosbridge WebSocket |

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Alarm response | < 500ms |
| Historian write | > 100,000 pts/sec |
| ML inference | < 100ms |
| MRP run (90 days) | < 30 seconds |
| Dashboard load | < 2 seconds |

---

## OpenAPI Specification

Full OpenAPI 3.1 specification available at:
- `/docs/api/openapi.yaml`
- Swagger UI: `/api/docs` (when enabled)
