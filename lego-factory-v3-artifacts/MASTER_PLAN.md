# LEGO Factory - Master Integration Plan

## Three Repositories → One Unified System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOURCE REPOSITORIES                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │    flask_cnc_app     │  │ lego-mcp-fusion360   │  │gcode_fingerprinting│ │
│  ├──────────────────────┤  ├──────────────────────┤  ├───────────────────┤  │
│  │ • 80+ Services       │  │ • 50+ Services       │  │ • 2 ML Models     │  │
│  │ • 41 Dashboards      │  │ • 16+ Dashboards     │  │ • 19 Notebooks    │  │
│  │ • Unity Digital Twin │  │ • MCP Server         │  │ • Training Scripts│  │
│  │ • TinyG/GRBL Control │  │ • ISA-95 MES/ERP     │  │ • Inference API   │  │
│  │ • MCC/Arduino DAQ    │  │ • LEGO Brick Design  │  │ • 668-Token Vocab │  │
│  │ • Data Alignment     │  │ • Slicer Service     │  │ • Pretrained Wts  │  │
│  │ • Robot Arms         │  │ • Scheduling (RL)    │  │ • Ablation Studies│  │
│  │ • Vision Inspection  │  │ • Quality SPC/FMEA   │  │                   │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │
│           │                         │                         │              │
│           └─────────────────────────┼─────────────────────────┘              │
│                                     │                                        │
│                                     ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         LEGO FACTORY                                  │   │
│  │                    (Unified Repository)                               │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                       │   │
│  │  Total: 130+ Services | 57+ Dashboards | 30+ MCP Tools | 2 ML Models │   │
│  │                                                                       │   │
│  │  Complete ISA-95 Stack: ERP → MES → SCADA → Control → Sensors → ML   │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LEGO FACTORY - COMPLETE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER INTERFACES                                                             │
│  ═══════════════                                                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐     │
│  │  Claude   │ │   Flask   │ │   Unity   │ │  Grafana  │ │  Fusion   │     │
│  │  Desktop  │ │  Portal   │ │  3D Twin  │ │  Metrics  │ │   360     │     │
│  │  (MCP)    │ │ (57+ UIs) │ │           │ │           │ │  Add-in   │     │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘     │
│        └─────────────┴─────────────┴─────────────┴─────────────┘            │
│                                     │                                        │
│                                     ▼                                        │
│  API LAYER (Flask + FastAPI)                                                │
│  ═══════════════════════════                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ /api/lego/*      Brick design, catalog, dimensions, slicing          │   │
│  │ /api/scada/*     Machine control, sensors, jobs, alignment           │   │
│  │ /api/mes/*       Work orders, scheduling, routing, BOM               │   │
│  │ /api/erp/*       Orders, costing, inventory, ATP/CTP, financials     │   │
│  │ /api/quality/*   SPC, FMEA, QFD, inspection, zero-defect             │   │
│  │ /api/ml/*        Fingerprinting, inference, training, anomaly        │   │
│  │ /api/unity/*     Digital twin state, commands, playback              │   │
│  │ /api/ai/*        Copilot, agents, causal AI, predictions             │   │
│  │ /api/robot/*     Niryo Ned2, xArm Lite 6 control                     │   │
│  │ /api/supply/*    Supplier portal, traceability, compliance           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  ═══════════════════════════════════╪════════════════════════════════════   │
│                              ISA-95 LEVELS                                   │
│  ═══════════════════════════════════╪════════════════════════════════════   │
│                                     │                                        │
│  LEVEL 4: ERP (lego-mcp-fusion360)  │                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Customer Orders │ ATP/CTP │ Demand Forecast │ Costing │ Financials   │   │
│  │ AR/AP/GL │ Inventory │ MRP │ Supply Chain │ Supplier Portal          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 3: MES (lego-mcp-fusion360)  │                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Work Orders │ Routing │ BOM │ CP-SAT Scheduler │ NSGA-II │ RL Dispatch│   │
│  │ Quality SPC (EWMA/CUSUM/T²) │ FMEA │ QFD │ Digital Thread │ OEE      │   │
│  │ Zero-Defect │ Vision AI (YOLO11) │ Traceability │ Compliance          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 2: SCADA (flask_cnc_app) ◀═══╪════════════════════════════ CRITICAL │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │   │
│  │  │ Zero/Home  │  │  Sensor    │  │    Job     │  │ Data Alignment │  │   │
│  │  │ Machines   │  │ Collection │  │ Execution  │  │ (G-code=Truth) │  │   │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └───────┬────────┘  │   │
│  │        │               │               │                 │           │   │
│  │        └───────────────┴───────────────┴─────────────────┘           │   │
│  │                                │                                      │   │
│  │                                ▼                                      │   │
│  │  ┌──────────────────────────────────────────────────────────────┐    │   │
│  │  │           G-CODE FINGERPRINTING (gcode_fingerprinting)        │    │   │
│  │  │                                                               │    │   │
│  │  │  Aligned   ┌─────────────┐   ┌─────────────────────────────┐ │    │   │
│  │  │  Data  ──▶ │ MM-DTAE-LSTM│──▶│ SensorMultiHead Decoder     │ │    │   │
│  │  │  (NPZ)     │  (Encoder)  │   │ Type│Cmd│Param│Digits       │ │    │   │
│  │  │            │  FROZEN     │   │ (Trainable)                 │ │    │   │
│  │  │            └─────────────┘   └─────────────────────────────┘ │    │   │
│  │  │                 │                        │                    │    │   │
│  │  │                 ▼                        ▼                    │    │   │
│  │  │         Operation: 100%          Token: 90.23%               │    │   │
│  │  │                                                               │    │   │
│  │  │  OUTPUTS: Anomaly Detection │ Process Fingerprint │ Alerts   │    │   │
│  │  └──────────────────────────────────────────────────────────────┘    │   │
│  │                                                                       │   │
│  │  Factory Cell Orchestrator │ Material Flow │ Historical Playback     │   │
│  │  Unity Digital Twin Sync │ 41 SCADA Dashboards                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 1: CONTROL (flask_cnc_app)   │                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ TinyG │ GRBL │ Marlin │ Bambu MQTT │ Prusa Serial │ Niryo │ xArm     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  LEVEL 0: SENSORS (flask_cnc_app + gcode_fingerprinting)                    │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ MCC USB-1608G │ Arduino (155 channels) │ Cameras │ Proximity         │   │
│  │ Temperature │ Vibration │ Current │ Load │ Pressure │ Accelerometer  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Component Inventory

### From flask_cnc_app (SCADA Layer)

| Category | Components | Count |
|----------|------------|-------|
| **Controllers** | TinyG, GRBL, Sensor, Robot | 4 |
| **Services** | Factory cell, material flow, vision, playback, bantam, predictive, etc. | 80+ |
| **API Routes** | /tinyg, /sensors, /mcc, /gcode, /bantam, /factory, /robot, /unity, /playback | 41 modules |
| **Dashboards** | Portal pages for all SCADA functions | 41 pages |
| **Unity** | Digital twin project, scripts, scenes | Full project |
| **Data Acquisition** | MCC helper, MCC recorder, G-code interpolation/alignment | 3 core |
| **Docker** | ROS2, Grafana, Prometheus, Mosquitto, PostgreSQL | 10+ services |

**Key Files to Port:**
- `gcode_interpolate_align.py` - **Critical** data alignment engine
- `mcc_helper.py`, `mcc_recorder.py` - DAQ integration
- `core/controllers/` - Machine drivers
- `services/factory_cell_orchestrator.py` - Robot coordination
- `services/pick_place_workflow.py` - Automated workflows
- `unity-project/` - Complete Unity digital twin

---

### From lego-mcp-fusion360 (MES/ERP Layer)

| Category | Components | Count |
|----------|------------|-------|
| **MES Services** | Work orders, routing, scheduling, OEE | 15+ |
| **ERP Services** | Orders, ATP/CTP, costing, inventory, financials | 10+ |
| **Quality Services** | SPC (EWMA/CUSUM/T²), FMEA, QFD, zero-defect | 10+ |
| **Scheduling** | CP-SAT, NSGA-II, RL dispatcher | 3 engines |
| **AI Services** | Claude copilot, multi-agent, causal AI | 5+ |
| **LEGO Services** | Brick design, dimensions, catalog | 5+ |
| **MCP Tools** | Create brick, slice, work order, etc. | 20+ |
| **Dashboards** | MES, quality, scheduling, analytics | 16+ pages |
| **Database Models** | Manufacturing, quality, orders, routing, BOM, FMEA, QFD | 25+ |

**Key Files to Port:**
- `dashboard/services/manufacturing/` - MES core
- `dashboard/services/scheduling/` - CP-SAT, NSGA-II, RL
- `dashboard/services/quality/` - SPC, FMEA, zero-defect
- `dashboard/services/ai/` - Copilot, agents
- `mcp-server/src/` - MCP tools
- `slicer-service/` - Docker slicer
- `fusion360-addin/` - Fusion 360 integration

---

### From gcode_fingerprinting (ML Layer)

| Category | Components | Count |
|----------|------------|-------|
| **Models** | MM-DTAE-LSTM encoder, SensorMultiHeadDecoder | 2 |
| **Training Scripts** | train_mm_dtae_lstm, train_sensor_multihead, create_splits, evaluate | 5 |
| **Notebooks** | Getting started through ablation studies | 19 |
| **Data Processing** | Dataset classes, preprocessing, tokenization | 5+ |
| **Inference** | FastAPI server, ONNX export | 2 |
| **Vocabulary** | 668-token hybrid vocabulary | 1 |
| **Pretrained Weights** | Encoder (45MB), Decoder (32MB) | 2 |
| **Configs** | Training configs, hyperparameters | 5+ |
| **Docker** | Training container, inference container | 2 |

**Key Files to Port:**
- `src/miracle/model/mm_dtae_lstm.py` - Encoder architecture
- `src/miracle/model/sensor_multihead_decoder.py` - Decoder architecture
- `src/miracle/dataset/` - Data loading
- `src/miracle/training/` - Losses, metrics
- `scripts/` - Training pipeline
- `data/vocabulary_4digit_hybrid.json` - Tokenization
- `outputs/*/best_model.pt` - Pretrained weights

---

## Data Flow: End-to-End

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COMPLETE DATA FLOW - NO LOSS OF FUNCTION                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. DESIGN (lego-mcp-fusion360)                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Claude MCP: "Create 2x4 brick"                                         │ │
│  │      │                                                                 │ │
│  │      ▼                                                                 │ │
│  │ Fusion 360 ──▶ Parametric Model ──▶ STL/STEP ──▶ Slicer ──▶ G-code   │ │
│  │ (Add-in)       (Brick specs)        (Export)     (Docker)   (NC file) │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  2. SCHEDULE (lego-mcp-fusion360)                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Customer Order ──▶ MRP ──▶ Work Order ──▶ Scheduler ──▶ Dispatch      │ │
│  │                           │              │                             │ │
│  │                           │    ┌─────────┴─────────┐                   │ │
│  │                           │    │ CP-SAT (optimal)  │                   │ │
│  │                           │    │ NSGA-II (Pareto)  │                   │ │
│  │                           │    │ RL (adaptive)     │                   │ │
│  │                           │    └───────────────────┘                   │ │
│  │                           │                                            │ │
│  │                  Quality Plan (FMEA, control limits)                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  3. EXECUTE (flask_cnc_app - SCADA)                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Step A: ZERO/HOME                                                     │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Machine Controller (TinyG/GRBL) ──▶ G28 ──▶ Reference established │ │ │
│  │  │ Unity Digital Twin ──▶ Sync position ──▶ Visual confirmation      │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │  Step B: START SENSORS                                                 │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ MCC USB-1608G ──▶ 100 Hz sampling ──▶ temp, vib, current, load   │ │ │
│  │  │ Arduino Mega ──▶ 50 Hz ──▶ proximity, pressure, accel (155 ch)  │ │ │
│  │  │ Machine Status ──▶ 60 Hz ──▶ position, velocity, state          │ │ │
│  │  │ Vision Cameras ──▶ 30 FPS ──▶ process monitoring                │ │ │
│  │  │                                                                  │ │ │
│  │  │ All streams ──▶ Timestamped queue ──▶ Async collection          │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │  Step C: STREAM G-CODE                                                 │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ For each line in G-code file:                                    │ │ │
│  │  │   • timestamp_start = now()                                      │ │ │
│  │  │   • Send line to machine controller                              │ │ │
│  │  │   • Wait for 'ok' or queue space                                 │ │ │
│  │  │   • timestamp_end = now()                                        │ │ │
│  │  │   • Record: {line#, cmd, X, Y, Z, F, S, start, end, duration}   │ │ │
│  │  │   • Update Unity twin position                                   │ │ │
│  │  │   • Check real-time anomaly detection                            │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │  Step D: STOP & ALIGN (gcode_interpolate_align.py)                     │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                                                                  │ │ │
│  │  │  G-code Timeline (Ground Truth):                                 │ │ │
│  │  │  ═════╤═════╤═════╤═════╤═════╤═════╤═════╤═════▶ time          │ │ │
│  │  │       L1    L2    L3    L4    L5    L6    L7                     │ │ │
│  │  │                                                                  │ │ │
│  │  │  Sensor Streams (Async, different rates):                        │ │ │
│  │  │  ──●──●──●──●──●──●──●──●──●──●──●──●──●──●──▶ (100 Hz)         │ │ │
│  │  │  ────○────○────○────○────○────○────○────▶ (50 Hz)               │ │ │
│  │  │  ──────□──────□──────□──────□──────▶ (60 Hz)                    │ │ │
│  │  │                                                                  │ │ │
│  │  │  INTERPOLATE (linear/cubic/nearest):                             │ │ │
│  │  │  ═════╤═════╤═════╤═════╤═════╤═════╤═════╤═════▶               │ │ │
│  │  │       │     │     │     │     │     │     │                      │ │ │
│  │  │       ▼     ▼     ▼     ▼     ▼     ▼     ▼                      │ │ │
│  │  │      S1    S2    S3    S4    S5    S6    S7  (aligned values)   │ │ │
│  │  │                                                                  │ │ │
│  │  │  QUALITY SCORE: How close was nearest actual reading?            │ │ │
│  │  │                                                                  │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  4. ALIGNED DATASET                                                          │
│  ━━━━━━━━━━━━━━━━━━                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  CSV/Parquet Format (for analysis, export, storage):                   │ │
│  │  ┌───────┬─────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────┐ │ │
│  │  │ Line# │ Cmd │  X   │  Y   │  Z   │ Temp │ Vib  │ Curr │ Quality │ │ │
│  │  ├───────┼─────┼──────┼──────┼──────┼──────┼──────┼──────┼─────────┤ │ │
│  │  │   1   │ G28 │  0.0 │  0.0 │  0.0 │ 22.1 │ 0.01 │  0.5 │   1.0   │ │ │
│  │  │   2   │ G1  │ 10.0 │  0.0 │ -2.0 │ 23.4 │ 0.12 │  2.3 │   0.98  │ │ │
│  │  │   3   │ G1  │ 20.0 │  0.0 │ -2.0 │ 28.7 │ 0.45 │  3.1 │   0.95  │ │ │
│  │  │  ...  │ ... │  ... │  ... │  ... │  ... │  ... │  ... │   ...   │ │ │
│  │  └───────┴─────┴──────┴──────┴──────┴──────┴──────┴──────┴─────────┘ │ │
│  │                                                                        │ │
│  │                              │                                         │ │
│  │                    CONVERT TO NPZ                                      │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │  NPZ Format (for fingerprinting ML):                                   │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ continuous:    [N, 64, 155] float32  (sensor windows)            │ │ │
│  │  │ categorical:   [N, 64, 4]   int64    (categorical features)      │ │ │
│  │  │ tokens:        [N, 7]       int64    (tokenized G-code)          │ │ │
│  │  │ operation_type:[N]          int64    (operation labels)          │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  5. FINGERPRINTING (gcode_fingerprinting)                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │              MM-DTAE-LSTM ENCODER (Frozen)                       │  │ │
│  │  │                                                                  │  │ │
│  │  │  continuous [B, 64, 155] ──▶ Linear ──▶ LayerNorm ──┐           │  │ │
│  │  │                                                      ├──▶ Fusion │  │ │
│  │  │  categorical [B, 64, 4] ──▶ Embed ──▶ Linear ───────┘           │  │ │
│  │  │                                                                  │  │ │
│  │  │                           Fusion ──▶ BiLSTM (2 layers, 128 dim) │  │ │
│  │  │                                            │                     │  │ │
│  │  │                                            ▼                     │  │ │
│  │  │                    Memory [B, 64, 128] + Operation logits [B, 9]│  │ │
│  │  │                                                                  │  │ │
│  │  │                    ★ Operation Classification: 100% accuracy ★   │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                      │                                 │ │
│  │                                      ▼                                 │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │            SENSOR MULTIHEAD DECODER (Trainable)                  │  │ │
│  │  │                                                                  │  │ │
│  │  │  Memory [B, 64, 128] + Token Embedding (668 vocab)              │  │ │
│  │  │                              │                                   │  │ │
│  │  │                              ▼                                   │  │ │
│  │  │              Transformer Decoder (4 layers, 8 heads)            │  │ │
│  │  │                              │                                   │  │ │
│  │  │                              ▼                                   │  │ │
│  │  │  ┌──────────┬───────────┬─────────────┬─────────────────────┐  │  │ │
│  │  │  │ Type [4] │ Command[6]│ ParamType[10]│ Digits [4×10]      │  │  │ │
│  │  │  │ (99.8%)  │ (99.9%)   │   (96.2%)    │ (4-digit values)   │  │  │ │
│  │  │  └──────────┴───────────┴─────────────┴─────────────────────┘  │  │ │
│  │  │                                                                  │  │ │
│  │  │                    ★ Token Accuracy: 90.23% ★                    │  │ │
│  │  │                    (600x improvement over random)                │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                      │                                 │ │
│  │                                      ▼                                 │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│  │  │                       OUTPUTS                                    │  │ │
│  │  │                                                                  │  │ │
│  │  │  • Predicted operation type                                      │  │ │
│  │  │  • Predicted G-code sequence                                     │  │ │
│  │  │  • Anomaly score (deviation from expected)                       │  │ │
│  │  │  • Process fingerprint (unique signature)                        │  │ │
│  │  │  • Confidence scores per prediction                              │  │ │
│  │  └─────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  6. REAL-TIME ACTIONS                                                        │
│  ━━━━━━━━━━━━━━━━━━━━                                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌────────────┐ │ │
│  │  │  Anomaly    │   │   Unity     │   │    MES      │   │  Quality   │ │ │
│  │  │  Alert      │   │   Twin      │   │   Update    │   │   Record   │ │ │
│  │  │  (WebSocket)│   │  (Overlay)  │   │  (Status)   │   │  (DB)      │ │ │
│  │  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬─────┘ │ │
│  │         │                 │                 │                 │        │ │
│  │         ▼                 ▼                 ▼                 ▼        │ │
│  │  Dashboard         3D Visual          Work Order        Traceability  │ │
│  │  Notification      Indicator          Completion        Digital Thread│ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases (10 Weeks)

### Phase 1: Foundation (Week 1)
**Goal**: Unified repository, basic SCADA

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Create unified repo structure | New | monorepo layout |
| Port machine controllers | flask_cnc_app | `core/controllers/` |
| Port sensor acquisition | flask_cnc_app | `mcc_helper.py`, `mcc_recorder.py` |
| Port data alignment | flask_cnc_app | `gcode_interpolate_align.py` |
| Port SCADA API routes | flask_cnc_app | `api/routes/` (41 modules) |
| Create main Flask app | New | `app.py` |
| Merge requirements.txt | All | dependencies |

**Deliverable**: Connect machine, collect sensors, align data

---

### Phase 2: Fingerprinting Integration (Week 2)
**Goal**: ML pipeline working with aligned data

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port model architectures | gcode_fingerprinting | `src/miracle/model/` |
| Port dataset classes | gcode_fingerprinting | `src/miracle/dataset/` |
| Port training utilities | gcode_fingerprinting | `src/miracle/training/` |
| Port vocabulary | gcode_fingerprinting | `data/vocabulary_4digit_hybrid.json` |
| Port pretrained weights | gcode_fingerprinting | `outputs/*/best_model.pt` |
| Create alignment → NPZ converter | New | conversion pipeline |
| Create inference service | New | real-time prediction |
| Create ML API routes | New | `/api/ml/*` |

**Deliverable**: Real-time fingerprinting during job execution

---

### Phase 3: LEGO Services (Week 3)
**Goal**: Brick design to G-code

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port brick dimension specs | lego-mcp-fusion360 | `shared/` |
| Port brick service | lego-mcp-fusion360 | `mcp-server/src/` |
| Port slicer service | lego-mcp-fusion360 | `slicer-service/` (Docker) |
| Port Fusion 360 add-in | lego-mcp-fusion360 | `fusion360-addin/` |
| Create LEGO API routes | New | `/api/lego/*` |
| Connect slicer → SCADA | New | G-code handoff |

**Deliverable**: Design brick → Generate G-code → Execute on machine

---

### Phase 4: MES Layer (Week 4)
**Goal**: Work orders and scheduling

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port MES models | lego-mcp-fusion360 | `dashboard/models/manufacturing.py` |
| Port work order service | lego-mcp-fusion360 | `dashboard/services/manufacturing/` |
| Port CP-SAT scheduler | lego-mcp-fusion360 | `dashboard/services/scheduling/cp_scheduler.py` |
| Port NSGA-II scheduler | lego-mcp-fusion360 | `dashboard/services/scheduling/nsga2_scheduler.py` |
| Port RL dispatcher | lego-mcp-fusion360 | `dashboard/services/scheduling/rl_dispatcher.py` |
| Create MES API routes | New | `/api/mes/*` |
| Connect MES → SCADA dispatch | New | work order → job |

**Deliverable**: Schedule work orders, dispatch to machines

---

### Phase 5: ERP Layer (Week 5)
**Goal**: Customer orders to shop floor

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port ERP models | lego-mcp-fusion360 | `dashboard/models/customer_order.py` |
| Port order service | lego-mcp-fusion360 | `dashboard/services/erp/order_service.py` |
| Port ATP/CTP service | lego-mcp-fusion360 | `dashboard/services/erp/atp_service.py` |
| Port costing service | lego-mcp-fusion360 | `dashboard/services/erp/` |
| Port inventory service | lego-mcp-fusion360 | `dashboard/services/erp/` |
| Create ERP API routes | New | `/api/erp/*` |

**Deliverable**: End-to-end order fulfillment

---

### Phase 6: Quality System (Week 6)
**Goal**: SPC, FMEA, Zero-Defect

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port SPC services | lego-mcp-fusion360 | `dashboard/services/quality/advanced_spc.py` |
| Port FMEA service | lego-mcp-fusion360 | `dashboard/services/quality/fmea_service.py` |
| Port QFD service | lego-mcp-fusion360 | `dashboard/services/quality/qfd_service.py` |
| Port zero-defect | lego-mcp-fusion360 | `dashboard/services/quality/zero_defect/` |
| Port vision inspection | flask_cnc_app | `services/vision_inspection_service.py` |
| Create quality API routes | New | `/api/quality/*` |
| Connect fingerprint → quality | New | anomaly → alert |

**Deliverable**: Complete quality management

---

### Phase 7: Digital Twin (Week 7)
**Goal**: Unity visualization

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port Unity project | flask_cnc_app | `unity-project/`, `unity/` |
| Port Unity state service | flask_cnc_app | `services/` |
| Port historical playback | flask_cnc_app | `services/historical_playback_service.py` |
| Add LEGO brick models | New | 3D assets |
| Add fingerprint overlay | New | anomaly visualization |
| Create Unity API routes | New | `/api/unity/*` |

**Deliverable**: Real-time 3D visualization with ML overlay

---

### Phase 8: Robot Integration (Week 8)
**Goal**: Automated material handling

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port factory cell orchestrator | flask_cnc_app | `services/factory_cell_orchestrator.py` |
| Port pick-place workflow | flask_cnc_app | `services/pick_place_workflow.py` |
| Port material flow | flask_cnc_app | `services/material_flow_service.py` |
| Port robot drivers | flask_cnc_app | Niryo, xArm |
| Create robot API routes | New | `/api/robot/*` |

**Deliverable**: Automated load/unload with robots

---

### Phase 9: Dashboards & MCP (Week 9)
**Goal**: Unified UI and Claude integration

| Task | Source Repo | Files/Modules |
|------|-------------|---------------|
| Port SCADA dashboards | flask_cnc_app | 41 pages |
| Port MES/ERP dashboards | lego-mcp-fusion360 | 16+ pages |
| Port fingerprint dashboard | gcode_fingerprinting | `flask_dashboard.py` |
| Create unified portal | New | navigation, theming |
| Port MCP server | lego-mcp-fusion360 | `mcp-server/` |
| Add SCADA MCP tools | flask_cnc_app | machine control |
| Add ML MCP tools | New | fingerprint, anomaly |

**Deliverable**: 57+ dashboards, 30+ MCP tools

---

### Phase 10: Testing & Documentation (Week 10)
**Goal**: Production ready

| Task | Description |
|------|-------------|
| Integration tests | End-to-end workflow tests |
| Performance tests | Latency, throughput validation |
| Port all notebooks | gcode_fingerprinting 19 notebooks |
| Write unified docs | Setup, API, training guides |
| Docker compose | Single deployment file |
| CI/CD pipeline | GitHub Actions |

**Deliverable**: Production-ready unified system

---

## Total Deliverables

| Category | Count |
|----------|-------|
| **Services** | 130+ |
| **API Routes** | 70+ |
| **Dashboard Pages** | 57+ |
| **MCP Tools** | 30+ |
| **ML Models** | 2 (encoder + decoder) |
| **Training Notebooks** | 19 |
| **Database Models** | 30+ |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Machine control | Zero, home, jog, run on all equipment |
| Data alignment | >95% coverage (sensors → G-code) |
| Fingerprint accuracy | 90%+ token prediction |
| Anomaly detection | <100ms real-time inference |
| End-to-end latency | Design → Execute < 5 minutes |
| Dashboard load | <2s page load |
| MCP response | <500ms tool execution |

---

## Ready to Begin

All three repositories documented. Complete scope mapped. No loss of function.

**When you're ready, we start Phase 1: Foundation**
- Machine controllers
- Sensor acquisition  
- Data alignment engine
- Core SCADA services

Let me know! 🏭
