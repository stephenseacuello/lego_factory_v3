# LEGO Factory v3 - Production Deployment Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Security Checklist](#security-checklist)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Docker 24.0+ and Docker Compose 2.0+
- PostgreSQL 15+ with TimescaleDB extension
- Redis 7.0+
- Node.js 20+ (for frontend build)
- Python 3.11+

### Hardware Requirements (Minimum)
| Component | CPU | RAM | Storage |
|-----------|-----|-----|---------|
| Application | 2 cores | 4GB | 20GB |
| Database | 4 cores | 8GB | 100GB SSD |
| Redis | 1 core | 2GB | 5GB |

---

## Environment Configuration

### 1. Generate Secure Secrets

Use the provided script to generate all required secrets:

```bash
# Generate all secrets and save to file
python scripts/generate_secrets.py --output .env.secrets

# Or display secrets in terminal
python scripts/generate_secrets.py --format env

# Or generate as JSON for automation
python scripts/generate_secrets.py --format json
```

Individual generation (if needed):
```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate Database Password
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for complete documentation of all configuration options.

### 2. Create Production Environment File

Copy `.env.example` to `.env.production` and configure:

```bash
# Required Security Settings
SECRET_KEY=<your-generated-secret-key>
JWT_SECRET_KEY=<your-generated-jwt-secret>
FLASK_ENV=production
FLASK_DEBUG=0

# Database (use strong password)
DATABASE_URL=postgresql://lego_factory:YOUR_SECURE_PASSWORD@db:5432/lego_factory
POSTGRES_USER=lego_factory
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD
POSTGRES_DB=lego_factory

# Redis
REDIS_URL=redis://:YOUR_REDIS_PASSWORD@redis:6379/0

# CORS (specify your domain)
CORS_ALLOWED_ORIGINS=https://factory.yourdomain.com
```

### 3. Critical Configuration Items

| Setting | Development | Production |
|---------|-------------|------------|
| `FLASK_DEBUG` | 1 | **0** |
| `FLASK_ENV` | development | **production** |
| `SECRET_KEY` | default | **secure random** |
| `DEMO_MODE` | true | **false** |
| `CORS_ALLOWED_ORIGINS` | * | **specific domains** |

---

## Database Setup

### 1. Initialize PostgreSQL with TimescaleDB

```bash
# Create database
createdb lego_factory

# Enable extensions (connect to database first)
psql -d lego_factory -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
psql -d lego_factory -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
```

### 2. Run Migrations

```bash
# Set DATABASE_URL
export DATABASE_URL=postgresql://user:pass@localhost:5432/lego_factory

# Check current status
python scripts/db_migrate.py status

# Create backup before migration
python scripts/db_migrate.py backup

# Run migrations
python scripts/db_migrate.py upgrade
```

### 3. Seed Initial Data (Optional)

```bash
# Only for initial setup, NOT for production data
export DATABASE_URL=postgresql://user:pass@localhost:5432/lego_factory
python database/seeds/seed_all.py
```

---

## Docker Deployment

### 1. Build Images

```bash
# Build production image
docker build -t lego-factory:latest .

# Build frontend
cd frontend && npm ci && npm run build
```

### 2. Deploy with Docker Compose

```bash
# Production deployment
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker compose ps

# View logs
docker compose logs -f app
```

### 3. Health Check Verification

```bash
# Check application health
curl http://localhost:5000/health

# Expected response:
# {"status": "healthy", "version": "3.0.0", ...}
```

---

## Kubernetes Deployment

### 1. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace lego-factory

# Create secrets (use your generated values)
kubectl create secret generic lego-factory-secrets \
  --namespace lego-factory \
  --from-literal=SECRET_KEY='your-secret-key' \
  --from-literal=JWT_SECRET_KEY='your-jwt-secret' \
  --from-literal=DATABASE_PASSWORD='your-db-password' \
  --from-literal=REDIS_PASSWORD='your-redis-password'
```

### 2. Deploy Application

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment status
kubectl get pods -n lego-factory
kubectl get services -n lego-factory
```

### 3. Configure Ingress

Update `k8s/ingress.yaml` with your domain and TLS settings.

---

## Security Checklist

### Pre-Deployment

- [ ] All `CHANGE_ME` placeholders replaced with secure values
- [ ] `FLASK_DEBUG=0` in production config
- [ ] `FLASK_ENV=production` set
- [ ] `SECRET_KEY` is unique, random, 32+ characters
- [ ] `JWT_SECRET_KEY` is unique, random, 32+ characters
- [ ] Database password is strong (24+ characters)
- [ ] `.env` file NOT committed to git
- [ ] CORS origins explicitly specified
- [ ] HTTPS enabled (TLS certificates configured)

### Post-Deployment

- [ ] Health endpoints responding correctly
- [ ] Authentication required for all API endpoints
- [ ] Logs not exposing sensitive data
- [ ] Database connections using SSL
- [ ] Firewall rules configured (only ports 80/443 exposed)

---

## Monitoring & Health Checks

### Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Overall application health |
| `/api/health/dependencies` | External service connectivity |
| `/api/health/circuits` | Circuit breaker status |

### Prometheus Metrics (if enabled)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'lego-factory'
    static_configs:
      - targets: ['lego-factory:5000']
    metrics_path: '/metrics'
```

### Recommended Alerts

```yaml
# Critical
- Application health status != "healthy"
- Database connection failures > 5 in 1 minute
- API response time > 5 seconds

# Warning
- Active alarms > 10
- Memory usage > 80%
- Error rate > 1%
```

---

## Backup & Recovery

### Database Backup

```bash
# Manual backup
python scripts/db_migrate.py backup

# Automated backup (add to cron)
0 2 * * * /path/to/scripts/db_migrate.py backup >> /var/log/lego-backup.log 2>&1
```

### Restore from Backup

```bash
# Restore (WARNING: overwrites current database)
python scripts/db_migrate.py restore backups/lego_factory_20260121_020000.sql
```

### Migration Rollback

```bash
# Rollback one migration
python scripts/db_migrate.py downgrade

# Rollback to specific revision
python scripts/db_migrate.py downgrade 001_initial
```

---

## Troubleshooting

### Common Issues

#### Application won't start

```bash
# Check logs
docker compose logs app

# Common causes:
# - DATABASE_URL not set or incorrect
# - Database not accessible
# - Missing required environment variables
```

#### Database connection errors

```bash
# Test connectivity
psql $DATABASE_URL -c "SELECT 1"

# Check if TimescaleDB is enabled
psql $DATABASE_URL -c "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';"
```

#### Migration failures

```bash
# Check current state
python scripts/db_migrate.py status

# View history
python scripts/db_migrate.py history

# Manual fix (if needed)
alembic stamp head  # Mark as current without running migrations
```

#### Frontend not loading

```bash
# Check if build exists
ls frontend/dist/

# Rebuild if needed
cd frontend && npm run build

# Check CORS settings if API calls fail
```

### Log Locations

| Component | Location |
|-----------|----------|
| Application | `/var/log/lego-factory/app.log` or `docker logs` |
| Database | PostgreSQL logs |
| Nginx | `/var/log/nginx/` |

---

## Contact & Support

For issues and feature requests, create an issue at:
https://github.com/your-org/lego-factory/issues

---

*Last updated: 2026-01-21*
