# Getting Started with LEGO Factory v3

This guide will help you get LEGO Factory v3 up and running quickly.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (5 minutes)](#quick-start-5-minutes)
- [Detailed Setup](#detailed-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Verifying the Installation](#verifying-the-installation)
- [Next Steps](#next-steps)

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Runtime environment |
| PostgreSQL | 15+ | Primary database |
| Redis | 7+ | Cache and pub/sub |
| Docker | 24+ | Container runtime (optional but recommended) |

### Optional Software

| Software | Version | Purpose |
|----------|---------|---------|
| TimescaleDB | 2.x | Time-series data (historian) |
| Mosquitto | 2.x | MQTT broker |
| ROS2 | Jazzy | Robot control |

---

## Quick Start (5 minutes)

### Option A: Docker (Recommended)

```bash
# 1. Clone the repository
cd lego_factory

# 2. Copy environment file
cp .env.example .env

# 3. Start all services
docker-compose up -d

# 4. Open in browser
open http://localhost:5000
```

### Option B: Demo Mode (No Database Required)

```bash
# 1. Clone and setup
cd lego_factory
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run in demo mode
DEMO_MODE=true python run.py
```

Demo mode uses in-memory SQLite and default credentials for quick testing.

---

## Detailed Setup

### Step 1: Clone and Create Virtual Environment

```bash
# Clone repository
cd lego_factory

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Verify Python version
python --version  # Should be 3.11+
```

### Step 2: Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# For development (includes test tools)
pip install -r requirements-dev.txt
# Or using make:
make dev-install
```

### Step 3: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# For production, generate secure secrets:
python scripts/generate_secrets.py --output .env.secrets
```

#### Minimum Configuration (.env)

```bash
# Application
FLASK_ENV=development
FLASK_DEBUG=true
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://lego:lego@localhost:5432/lego_factory

# Redis (optional for development)
REDIS_URL=redis://localhost:6379/0

# Demo Mode (set true to skip external dependencies)
DEMO_MODE=false
```

### Step 4: Setup Database

#### Option A: Using Docker (Recommended)

```bash
# Start PostgreSQL + TimescaleDB
docker-compose up -d postgres

# Wait for database to be ready
docker-compose logs -f postgres
# Look for "database system is ready to accept connections"
```

#### Option B: Local PostgreSQL

```bash
# Create database
createdb lego_factory

# Create user (if needed)
psql -c "CREATE USER lego WITH PASSWORD 'lego';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE lego_factory TO lego;"

# Install TimescaleDB extension (optional)
psql -d lego_factory -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Step 5: Run Database Migrations

```bash
# Initialize migrations (if not already done)
flask db upgrade

# Or using alembic directly
alembic upgrade head
```

### Step 6: Seed Initial Data (Optional)

```bash
# Seed demo data (basic)
python scripts/seed_demo_data.py

# Seed rich demo data for Gantt chart presentation (39 WOs, 118 jobs, maintenance windows)
docker compose exec app python -m database.seeds.seed_demo_presentation

# Or use the API
curl -X POST http://localhost:5000/api/admin/seed
```

---

## Configuration

### Environment Variables

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for complete documentation.

#### Key Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes* | - | Flask secret key |
| `DATABASE_URL` | Yes* | - | PostgreSQL connection URL |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `DEMO_MODE` | No | `false` | Enable demo mode |
| `FLASK_ENV` | No | `production` | Environment mode |

*Not required when `DEMO_MODE=true`

### Generate Production Secrets

```bash
# Generate all secrets to file
python scripts/generate_secrets.py --output .env.secrets

# Generate and display (don't save)
python scripts/generate_secrets.py --format env

# Generate as JSON
python scripts/generate_secrets.py --format json
```

---

## Running the Application

### Development Server

```bash
# Using Flask development server
python run.py

# Or with flask command
FLASK_APP=app.main:create_app flask run --port 5000

# With debug mode
FLASK_DEBUG=true python run.py
```

### Production Server

```bash
# Using Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app.main:create_app()"

# With Gevent workers (for WebSocket support)
gunicorn -w 4 -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
  -b 0.0.0.0:5000 "app.main:create_app()"
```

### Docker

```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d postgres redis web

# View logs
docker-compose logs -f web

# Stop all services
docker-compose down
```

---

## Verifying the Installation

### 1. Health Check

```bash
# Check overall health
curl http://localhost:5000/health
# Expected: {"status": "healthy", ...}

# Check detailed health
curl http://localhost:5000/health/ready
# Expected: {"database": "ok", "redis": "ok", ...}

# Check liveness (is app running?)
curl http://localhost:5000/health/live
# Expected: {"status": "alive"}
```

### 2. API Access

```bash
# Get API info
curl http://localhost:5000/api/v1/

# List items (ERP)
curl http://localhost:5000/api/v1/erp/items

# Get active alarms (SCADA)
curl http://localhost:5000/api/scada/alarms/active
```

### 3. Authentication

```bash
# Login (default demo credentials)
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Response includes access_token
# Use token for authenticated requests:
curl http://localhost:5000/api/v1/erp/items \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Run Tests

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run with coverage
make coverage

# Quick syntax check
python -m py_compile app/main.py
```

---

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| Flask App | 5000 | http://localhost:5000 |
| PostgreSQL | 5432 | `postgresql://localhost:5432/lego_factory` |
| Redis | 6379 | `redis://localhost:6379` |
| MQTT Broker | 1883 | `mqtt://localhost:1883` |
| Grafana | 3000 | http://localhost:3000 |
| ROS2 Bridge | 9090 | `ws://localhost:9090` |
| noVNC | 6080 | http://localhost:6080 |

---

## Next Steps

### Explore the Platform

1. **Web Dashboard**: Open http://localhost:5000 in your browser
2. **API Documentation**: See [API_REFERENCE.md](API_REFERENCE.md)
3. **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)

### Common Tasks

- **View Gantt Chart**: Open http://localhost:5000/mes/scheduling
- **Run Schedule Optimizer**: POST `/api/mes/scheduling/reschedule` with `{"objective": "makespan"}`
- **Auto-Dispatch Jobs**: POST `/api/mes/dispatch/auto/{machine_id}` with `{"rule": "balanced"}`
- **What-If Simulation**: POST `/api/mes/scheduling/what-if` with scenario changes
- **Create a Work Order**: POST `/api/mes/work-orders`
- **Run MRP**: POST `/api/erp/mrp/run`
- **View OEE**: GET `/api/mes/oee?machine_id=MACHINE_ID`
- **Check Alarms**: GET `/api/scada/alarms/active`

### Development

- **Test Strategy**: See [TEST_STRATEGY.md](TEST_STRATEGY.md)
- **Contributing**: See [DEVELOPMENT.md](DEVELOPMENT.md)
- **Troubleshooting**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### Deployment

- **Production Deployment**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Kubernetes**: See `k8s/` directory

---

## Troubleshooting

### Common Issues

#### "SECRET_KEY environment variable is required"

```bash
# Option 1: Enable demo mode
export DEMO_MODE=true

# Option 2: Generate secrets
python scripts/generate_secrets.py --format shell | source /dev/stdin
```

#### Database Connection Refused

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Or for local PostgreSQL
pg_isready -h localhost -p 5432
```

#### Redis Connection Error

```bash
# Redis is optional in development
# Either start Redis:
docker-compose up -d redis

# Or disable Redis features:
export REDIS_ENABLED=false
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

## Support

- **Issues**: https://github.com/anthropics/claude-code/issues
- **Documentation**: `/docs` directory
- **API Reference**: http://localhost:5000/api/docs (when running)
