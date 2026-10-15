# Production Deployment & Operations Guide

## 1. Hosting Architecture
- **Web Service:** Render Python Web Service or Docker runtime container.
- **Database:** Managed PostgreSQL (Render PostgreSQL or Neon Serverless PostgreSQL with SSL required).
- **Environment Management:** Environment variables supplied through Render dashboard secrets.
- **Push Signaling:** Firebase Cloud Messaging (FCM) downstream wakeup adapter.
- **Real-Time Streaming:** Authenticated WebSockets at `/api/v1/ws`.

---

## 2. Render Blueprint (`render.yaml`)
The project includes an infrastructure-as-code `render.yaml` blueprint defining:
- `smart-child-safety-backend`: Web service configured with:
  - `buildCommand: pip install -r requirements.txt && alembic upgrade head`
  - `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - `healthCheckPath: /health`
- `smart-child-safety-db`: Managed PostgreSQL database instance automatically connected via `DATABASE_URL`.

---

## 3. Production Environment Variables Reference

| Variable | Type | Required | Description | Example / Note |
|---|---|---|---|---|
| `ENVIRONMENT` | string | Yes | Runtime mode (`production`, `development`, `testing`) | `production` |
| `DATABASE_URL` | string | Yes | Managed PostgreSQL connection string with SSL | `postgresql+psycopg://user:pass@ep-xyz.region.neon.tech/dbname?sslmode=require` |
| `API_V1_PREFIX` | string | No | Base path prefix for REST routes | `/api/v1` (default) |
| `PORT` | integer | Yes | Port allocated dynamically by Render container | Automatically provided by Render runtime |
| `HOST` | string | No | Host interface binding | `0.0.0.0` (default) |
| `LOG_LEVEL` | string | No | Structured logging verbosity | `INFO` (default) |
| `CORS_ORIGINS` | JSON list | Yes | Allowed origins for web dashboards/clients | `["https://smart-child-parent.web.app"]` |
| `FIREBASE_PROJECT_ID` | string | Yes | Firebase project ID | `smart-child-safety-prod` |
| `FIREBASE_CREDENTIALS_JSON` | string | Yes | Service account JSON secret string for FCM & Auth | Paste full JSON content in Render secret store |
| `LOCATION_RETENTION_DAYS` | integer | No | Data retention window for location history | `30` (default) |
| `LOCATION_STALE_MINUTES` | integer | No | Staleness threshold for GPS telemetry | `15` (default) |
| `PAIRING_CODE_EXPIRY_MINUTES` | integer | No | TTL for parent-child pairing invitations | `15` (default) |

---

## 4. Database Migrations & Lifecycle

### Automatic Execution on Deploy
The Render build command automatically executes migrations prior to starting the new revision:
```bash
pip install -r requirements.txt && alembic upgrade head
```

### Manual Database Operations
To inspect migration status or execute manually:
```bash
# Check current database revision against head
alembic current

# Upgrade to latest schema migration
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1
```

---

## 5. Health & Readiness Monitoring

The server exposes non-leaking health endpoints designed for container and orchestrator probes:

- **Liveness Probe:** `GET /health`
  - Used by Render health checker to verify HTTP server responsiveness.
  - Returns `{"status": "ok", "service": "smart-child-safety-backend", "version": "1.0.0"}`.
  - Never leaks database state or configuration.

- **Readiness Probe:** `GET /ready`
  - Used to verify that PostgreSQL database pool connectivity is established and responsive.
  - Returns `{"status": "ready", "database": "connected"}` with HTTP 200, or `{"status": "not_ready", "database": "disconnected"}` with HTTP 503 if unreachable.

---

## 6. Data Retention & Maintenance Routines

To adhere to privacy standards and GDPR/CCPA storage limitation principles:
- **Periodic Cleanup Endpoint:** `POST /api/v1/maintenance/retention/cleanup`
  - Can be triggered on a scheduled cron basis (e.g. daily via Render Cron Job or external scheduler).
  - Automatically prunes:
    - `LocationRecord` points older than `LOCATION_RETENTION_DAYS`.
    - `DeviceHeartbeat` telemetry older than `LOCATION_RETENTION_DAYS`.
    - Expired, unredeemed `PairingCode` records.
    - Completed or expired `DeviceCommand` records older than 30 days.
  - Returns an atomic audit summary:
    ```json
    {
      "status": "success",
      "retention_days": 30,
      "pruned_location_records": 1250,
      "pruned_heartbeats": 340,
      "pruned_pairing_codes": 12,
      "pruned_commands": 45,
      "executed_at": "2026-10-14T22:00:00+00:00"
    }
    ```

---

## 7. Security Best Practices for Production

1. **Secrets Management:**
   - Never commit `.env` or service account JSON files to source control.
   - Inject `FIREBASE_CREDENTIALS_JSON` and `DATABASE_URL` as secret environment variables in Render.
2. **TLS / HTTPS:**
   - Render automatically provisions and renews Let's Encrypt SSL/TLS certificates.
   - All REST and WebSocket traffic MUST use HTTPS (`https://`) and Secure WebSockets (`wss://`).
3. **Database SSL:**
   - Neon and Render PostgreSQL require `sslmode=require` query parameters in the connection string.
4. **Structured Logging:**
   - The server redacts tokens, credentials, and coordinates from application logs.
   - Access logs record `X-Request-ID`, HTTP method, path, status, and duration.

