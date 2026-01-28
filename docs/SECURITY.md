# LEGO Factory v3 - Security Documentation

## Table of Contents
- [Authentication](#authentication)
- [Authorization](#authorization)
- [Hardware Security Module (HSM/TPM)](#hardware-security-module-hsmtpm)
- [API Security](#api-security)
- [Configuration Security](#configuration-security)

---

## Authentication

### JWT Token-Based Authentication

The system uses JWT (JSON Web Tokens) for API authentication:

```
Authorization: Bearer <access_token>
```

**Token Configuration:**
- Access tokens expire after 15 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRES_MINUTES`)
- Refresh tokens expire after 30 days (configurable via `JWT_REFRESH_TOKEN_EXPIRES_DAYS`)
- Algorithm: HS256 (configurable via `JWT_ALGORITHM`)

### Demo Credentials

For development and testing only:
- Username: `admin`
- Password: `admin`

**WARNING:** Change default credentials in production!

---

## Authorization

### Role-Based Access Control (RBAC)

| Role | Permissions |
|------|-------------|
| `admin` | Full system access |
| `supervisor` | Manage work orders, view all data |
| `operator` | Start/stop machines, view assigned data |
| `viewer` | Read-only access |

---

## Hardware Security Module (HSM/TPM)

### Overview

The system includes TPM 2.0 integration for hardware-backed security:
- Platform attestation
- Sealed storage (secrets tied to platform state)
- Hardware random number generation

### Simulation Mode

**IMPORTANT:** By default, TPM operates in SIMULATION MODE.

In simulation mode:
- All cryptographic operations use software implementation
- Suitable for development, testing, and cloud deployments
- Does NOT provide hardware security guarantees

#### Enabling Hardware TPM

To use real TPM hardware:

```bash
# Disable simulation mode
export TPM_SIMULATION_MODE=false

# Specify TPM device (optional)
export TPM_DEVICE_PATH=/dev/tpmrm0
```

#### Requirements for Hardware TPM

1. **Hardware:** TPM 2.0 chip or firmware TPM
2. **Device Access:** `/dev/tpm0` or `/dev/tpmrm0` must exist
3. **Permissions:** Application must have read/write access to TPM device
4. **Library:** `tpm2-pytss` Python library for hardware access

#### TPM Operations

| Operation | Simulation | Hardware |
|-----------|------------|----------|
| PCR Read | Software hash | TPM hardware |
| PCR Extend | Software hash | TPM hardware |
| Seal Data | AES encryption | TPM sealing |
| Unseal Data | AES decryption | TPM unsealing |
| Attestation Quote | Simulated signature | TPM quote |
| Random Generation | `secrets` module | TPM RNG |

#### Security Considerations

| Mode | Use Case | Security Level |
|------|----------|----------------|
| Simulation | Development, Testing | Software-only |
| Hardware TPM | Production with TPM | Hardware-backed |
| vTPM (Cloud) | Cloud deployments | Cloud provider dependent |

---

## API Security

### Protected Endpoints

All API endpoints require JWT authentication except:
- `GET /health` - Health check
- `POST /api/auth/login` - Login
- `POST /api/auth/register` - Registration

### Rate Limiting

| Endpoint Type | Limit |
|---------------|-------|
| Standard API | 100 requests/minute |
| Admin endpoints | 10 requests/minute |
| G-code commands | 30 requests/minute |

### G-Code Command Auditing

All G-code commands sent to machines are:
1. Validated for safety
2. Logged with user identity
3. Rate limited
4. Auditable via `gcode_audit` logger

---

## Configuration Security

### Required Environment Variables (Production)

```bash
# MUST be set to secure random values
SECRET_KEY=<32+ character random string>
JWT_SECRET_KEY=<32+ character random string>

# Database credentials
DATABASE_URL=postgresql://user:password@host:5432/database

# Production mode
FLASK_ENV=production
FLASK_DEBUG=0
```

### Security Validation

The configuration system validates:
- Secret key length (minimum 32 characters)
- Secret key entropy (rejects obvious patterns)
- Debug mode disabled in production
- Localhost usage warnings in production

### Generating Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database password
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

---

## Security Checklist

### Development
- [ ] Use simulation mode for TPM
- [ ] Use development credentials
- [ ] Debug mode enabled for troubleshooting

### Staging
- [ ] Use unique secrets (not production)
- [ ] Test authentication flows
- [ ] Verify rate limiting works

### Production
- [ ] SECRET_KEY set to secure random value
- [ ] JWT_SECRET_KEY set to secure random value
- [ ] FLASK_DEBUG=0
- [ ] FLASK_ENV=production
- [ ] HTTPS enabled
- [ ] Database using strong password
- [ ] Rate limiting configured
- [ ] Audit logging enabled
- [ ] TPM hardware enabled (if available)

---

*Last updated: 2026-01-21*
