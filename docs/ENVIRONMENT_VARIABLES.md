# Environment Variables Reference

LEGO Factory v3 uses environment variables for configuration. This document provides a comprehensive reference for all available settings.

## Quick Start

```bash
# Generate production secrets
python scripts/generate_secrets.py --output .env.production

# Run in demo mode (allows insecure defaults)
DEMO_MODE=true python -m flask run

# Run in production
FLASK_ENV=production python -m flask run
```

## Table of Contents

- [Core Settings](#core-settings)
- [Security Settings](#security-settings)
- [Database Configuration](#database-configuration)
- [Redis Configuration](#redis-configuration)
- [Historian Configuration](#historian-configuration)
- [Alarm Configuration](#alarm-configuration)
- [Machine Control Configuration](#machine-control-configuration)
- [ROS2 Configuration](#ros2-configuration)
- [ML Configuration](#ml-configuration)
- [LEGO Design Services](#lego-design-services)
- [Unity Digital Twin](#unity-digital-twin)
- [MCP Server](#mcp-server)
- [JWT Authentication](#jwt-authentication)
- [Circuit Breaker Configuration](#circuit-breaker-configuration)
- [Logging Configuration](#logging-configuration)

---

## Core Settings

| Variable | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `FLASK_ENV` | string | `development` | No | Environment mode: `development`, `testing`, or `production` |
| `FLASK_DEBUG` | bool | `false` | No | Enable Flask debug mode. **Never enable in production.** |
| `FLASK_HOST` | string | `0.0.0.0` | No | Host to bind the Flask server |
| `FLASK_PORT` | int | `5000` | No | Port to bind the Flask server |
| `DEMO_MODE` | bool | `false` | No | Allow insecure defaults for demonstration. See [Demo Mode](#demo-mode). |

### Demo Mode

When `DEMO_MODE=true`:
- Placeholder secrets are allowed with warnings
- Insecure defaults are used for development/demonstration
- Warnings are logged about security implications

When `DEMO_MODE=false` (default) in production:
- Application fails fast if secrets contain placeholders
- All security requirements are enforced
- Production-safe configuration is required

**Example:**
```bash
# Development with demo mode
DEMO_MODE=true FLASK_ENV=development python -m flask run

# Production (fails without proper secrets)
FLASK_ENV=production python -m flask run
```

---

## Security Settings

| Variable | Type | Default | Required (Prod) | Description |
|----------|------|---------|-----------------|-------------|
| `SECRET_KEY` | string | *insecure default* | **Yes** | Flask secret key for sessions. Min 32 chars. |
| `JWT_SECRET_KEY` | string | *insecure default* | **Yes** | JWT signing key. Min 32 chars. |

### Generating Secure Keys

```bash
# Using the provided script
python scripts/generate_secrets.py

# Manual generation
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Security Considerations:**
- Never commit secrets to version control
- Use different secrets for each environment
- Rotate secrets periodically
- Store in a secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.)

---

## Database Configuration

| Variable | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `DATABASE_URL` | string | - | Recommended | Full PostgreSQL connection URL |
| `DB_HOST` | string | `localhost` | No* | Database hostname |
| `DB_PORT` | int | `5432` | No | Database port |
| `DB_NAME` | string | `lego_factory` | No | Database name |
| `DB_USER` | string | `postgres` | No | Database username |
| `DB_PASSWORD` | string | - | **Yes*** | Database password |
| `DB_POOL_SIZE` | int | `10` | No | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | int | `20` | No | Max connections above pool size |

*Either `DATABASE_URL` or individual `DB_*` variables are required.

### Connection URL Format

```bash
# Using DATABASE_URL (recommended for Docker/K8s)
DATABASE_URL=postgresql://user:password@host:5432/lego_factory

# Using individual variables
DB_HOST=localhost
DB_PORT=5432
DB_NAME=lego_factory
DB_USER=postgres
DB_PASSWORD=your_secure_password
```

**Production Recommendations:**
- Use SSL connections: `?sslmode=require`
- Configure appropriate pool sizes based on workload
- Use connection pooling (PgBouncer) for high-load scenarios

---

## Redis Configuration

| Variable | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `REDIS_URL` | string | - | No | Full Redis connection URL |
| `REDIS_HOST` | string | `localhost` | No | Redis hostname |
| `REDIS_PORT` | int | `6379` | No | Redis port |
| `REDIS_DB` | int | `0` | No | Redis database number |
| `REDIS_PASSWORD` | string | - | Recommended | Redis password |

### Connection URL Format

```bash
# Using REDIS_URL
REDIS_URL=redis://:password@localhost:6379/0

# Using individual variables
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_secure_password
```

---

## Historian Configuration

TimescaleDB historian settings for time-series data storage.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HISTORIAN_BUFFER_SIZE` | int | `1000` | Number of points to buffer before flush |
| `HISTORIAN_FLUSH_INTERVAL` | float | `1.0` | Flush interval in seconds |
| `HISTORIAN_COMPRESSION_DEVIATION` | float | `0.01` | Swinging door compression deviation |
| `HISTORIAN_COMPRESSION_MAX_TIME` | float | `60.0` | Max seconds before forced write |
| `HISTORIAN_RETENTION_RAW_DAYS` | int | `7` | Days to retain raw data |
| `HISTORIAN_RETENTION_1MIN_DAYS` | int | `30` | Days to retain 1-minute aggregates |
| `HISTORIAN_RETENTION_1HOUR_DAYS` | int | `365` | Days to retain 1-hour aggregates |
| `HISTORIAN_CHUNK_INTERVAL` | string | `1 day` | TimescaleDB chunk time interval |

**Production Recommendations:**
- Adjust retention based on storage capacity
- Monitor chunk sizes for query performance
- Consider compression policies for older data

---

## Alarm Configuration

ISA-18.2 compliant alarm management settings.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ALARM_MAX_UNACKED` | int | `1000` | Maximum unacknowledged alarms |
| `ALARM_SHELVE_MAX_HOURS` | int | `24` | Maximum shelve duration in hours |
| `ALARM_RATE_LIMIT` | int | `100` | Alarm rate limit per minute |
| `ALARM_DEADBAND_PERCENT` | float | `1.0` | Default alarm deadband percentage |

---

## Machine Control Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MACHINE_BAUD_RATE` | int | `115200` | Default serial baud rate |
| `MACHINE_CONN_TIMEOUT` | float | `10.0` | Connection timeout in seconds |
| `MACHINE_CMD_TIMEOUT` | float | `5.0` | Command timeout in seconds |
| `MACHINE_POLL_INTERVAL` | float | `0.1` | Status polling interval in seconds |

---

## ROS2 Configuration

ROS2 Jazzy integration settings.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ROS2_ENABLED` | bool | `true` | Enable ROS2 integration |
| `ROS2_MQTT_HOST` | string | `localhost` | MQTT broker for ROS2 bridge |
| `ROS2_MQTT_PORT` | int | `1883` | MQTT broker port |
| `ROS2_MQTT_PREFIX` | string | `ros2_bridge` | MQTT topic prefix |
| `ROS2_SERVICE_TIMEOUT` | float | `10.0` | ROS2 service call timeout |
| `ROS2_ACTION_TIMEOUT` | float | `60.0` | ROS2 action timeout |
| `ROSBRIDGE_PORT` | int | `9090` | ROSBridge WebSocket port |

---

## ML Configuration

Machine learning fingerprinting and anomaly detection.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ML_MODEL_PATH` | string | `services/ml/checkpoints` | Path to ML model checkpoints |
| `ML_VOCAB_PATH` | string | `services/ml/dataset/vocabulary.json` | Path to vocabulary file |
| `ML_BATCH_SIZE` | int | `32` | Inference batch size |
| `ML_DEVICE` | string | `cpu` | Inference device: `cpu` or `cuda` |
| `ML_ANOMALY_THRESHOLD` | float | `0.8` | Anomaly detection threshold |

---

## LEGO Design Services

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SLICER_HOST` | string | `localhost` | Slicer service hostname |
| `SLICER_PORT` | int | `8766` | Slicer service port |
| `FUSION360_HOST` | string | `localhost` | Fusion 360 service hostname |
| `FUSION360_PORT` | int | `8767` | Fusion 360 service port |
| `BRICK_CATALOG_PATH` | string | `services/lego/brick_catalog.json` | Path to brick catalog |

---

## Unity Digital Twin

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `UNITY_WS_PORT` | int | `8765` | Unity WebSocket port |
| `UNITY_UPDATE_RATE` | float | `30.0` | State update rate in Hz |

---

## MCP Server

Model Context Protocol server settings.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MCP_SERVER_NAME` | string | `lego-factory-v3` | MCP server name |
| `MCP_SERVER_VERSION` | string | `3.0.0` | MCP server version |

---

## JWT Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_SECRET_KEY` | string | *insecure default* | JWT signing secret (see [Security](#security-settings)) |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | int | `15` | Access token expiration in minutes |
| `JWT_REFRESH_TOKEN_EXPIRES_DAYS` | int | `30` | Refresh token expiration in days |
| `JWT_ALGORITHM` | string | `HS256` | JWT signing algorithm |

---

## Circuit Breaker Configuration

Resilience settings for external service calls.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CB_REDIS_FAIL_MAX` | int | `5` | Max failures before Redis circuit opens |
| `CB_REDIS_RESET_TIMEOUT` | int | `30` | Seconds before Redis circuit resets |
| `CB_REDIS_EXCLUDE` | string | `KeyError` | Comma-separated exceptions to exclude |
| `CB_MQTT_FAIL_MAX` | int | `3` | Max failures before MQTT circuit opens |
| `CB_MQTT_RESET_TIMEOUT` | int | `60` | Seconds before MQTT circuit resets |
| `CB_DATABASE_FAIL_MAX` | int | `5` | Max failures before database circuit opens |
| `CB_DATABASE_RESET_TIMEOUT` | int | `30` | Seconds before database circuit resets |
| `CB_EXTERNAL_API_FAIL_MAX` | int | `3` | Max failures before external API circuit opens |
| `CB_EXTERNAL_API_RESET_TIMEOUT` | int | `45` | Seconds before external API circuit resets |
| `CB_ROS2_FAIL_MAX` | int | `3` | Max failures before ROS2 circuit opens |
| `CB_ROS2_RESET_TIMEOUT` | int | `30` | Seconds before ROS2 circuit resets |
| `CB_LOCAL_CACHE_MAX_SIZE` | int | `1000` | Max items in local fallback cache |
| `CB_LOCAL_CACHE_TTL` | int | `300` | Default TTL for local cache (seconds) |
| `CB_RETRY_QUEUE_MAX_SIZE` | int | `1000` | Max messages in retry queues |

---

## Logging Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | string | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | string | *see below* | Log message format |

Default log format:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

---

## TPM/HSM Configuration

Trusted Platform Module settings for hardware security.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `TPM_SIMULATION_MODE` | bool | `true` | Use TPM simulation (software cryptography) |

When `TPM_SIMULATION_MODE=false`:
- Requires `/dev/tpm0` hardware device
- Requires `python-tpm2-pytss` library
- Enables hardware-backed cryptographic operations

---

## Environment File Examples

### Development (.env.development)

```bash
FLASK_ENV=development
FLASK_DEBUG=true
DEMO_MODE=true
LOG_LEVEL=DEBUG

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lego_factory_dev
REDIS_URL=redis://localhost:6379/0
```

### Testing (.env.testing)

```bash
FLASK_ENV=testing
DATABASE_URL=sqlite:///:memory:
REDIS_URL=redis://localhost:6379/1
LOG_LEVEL=WARNING
```

### Production (.env.production)

```bash
FLASK_ENV=production
FLASK_DEBUG=false
DEMO_MODE=false

# Generate with: python scripts/generate_secrets.py
SECRET_KEY=your-generated-secret-key
JWT_SECRET_KEY=your-generated-jwt-key

DATABASE_URL=postgresql://lego_user:strong_password@db.example.com:5432/lego_factory?sslmode=require
REDIS_URL=redis://:redis_password@redis.example.com:6379/0

DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

LOG_LEVEL=INFO
```

---

## Docker Compose Example

```yaml
services:
  app:
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/lego_factory
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
```

---

## Kubernetes ConfigMap Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: lego-factory-config
data:
  FLASK_ENV: "production"
  DB_HOST: "postgres-service"
  DB_PORT: "5432"
  DB_NAME: "lego_factory"
  REDIS_HOST: "redis-service"
  LOG_LEVEL: "INFO"
```

Secrets should be stored separately in a Kubernetes Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: lego-factory-secrets
type: Opaque
data:
  SECRET_KEY: <base64-encoded-value>
  JWT_SECRET_KEY: <base64-encoded-value>
  DB_PASSWORD: <base64-encoded-value>
```
