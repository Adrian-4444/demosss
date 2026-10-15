# MEMORY — Backend Server Project Decisions

Update this file as decisions are confirmed. Never store secrets, tokens, passwords, production credentials, or real children's location data here.

## Project
- Name: Smart Child Monitoring and Safety System.
- This repository's scope: **backend server only**.
- The system has a Parent Android App and a Child Android App that communicate with the server.
- Purpose: authenticated location/status sharing, safety checks, SOS events, safe zones, alerts, and authorized live updates.
- This is a safety-assistance system, not a guaranteed emergency service.

## Agreed technology baseline
- Python + FastAPI.
- PostgreSQL database.
- SQLAlchemy ORM and Alembic migrations.
- Firebase Cloud Messaging (FCM) for push notification/signaling.
- Authenticated WebSockets for parent near-real-time updates.
- Render hosting with managed PostgreSQL such as Neon.
- pytest for backend testing.
- Exact versions, auth provider, and final dependencies still need confirmation from repository inspection.

## Architecture decisions
- Backend and PostgreSQL are the source of truth for commands, locations, events and relationships.
- FCM is only a notification/sync signal. Commands must be persisted before FCM is attempted.
- Parent app can access only child profiles linked to its authenticated guardian account.
- Child app can submit location/status and retrieve/respond to commands only for its authenticated child identity.
- Every REST route and WebSocket subscription involving child data must enforce server-side authorization.
- On WebSocket reconnect, clients resynchronize authoritative state via REST.
- Store location capture time separately from server receipt time.
- Use UTC timestamps in storage.
- Use Alembic migrations for schema changes.

## Required safety/privacy boundaries
- No covert tracking, stealth mode, permission bypass, or unrelated collection of messages/calls/audio/video.
- Respect Android permission denial/revocation and background-location restrictions.
- Make location-sharing state transparent in the child app.
- Minimize data collection, logs, and FCM payloads.
- Support unlinking and data deletion/retention.
- Risk/anomaly scores, if later added, are uncertain signals and never proof of danger.
- Do not claim notification delivery or emergency response unless actually confirmed.

## Open decisions — ask before locking in
- Authentication provider and exact token-validation strategy.
- Location upload cadence and freshness thresholds.
- Location-history retention period.
- Pairing process and guardian verification.
- Safe-zone radius limits and cooldown behavior.
- Exact Python and dependency versions.
- Render service configuration and database connection options.
- Whether anomaly/risk scoring belongs in the initial server release or a later research phase.
- Expected load and performance targets.

## Workflow rules
- Inspect repository and Git status before editing.
- Read all six project files at the start of a task.
- Implement in small phases and preserve existing work.
- Add tests for authorization failures and edge cases.
- Run checks and report real results only.
- Update `TASKS.md` when task state changes and this file when durable decisions change.

## Session handoff
- Date/session: 2026-10-12 — Stage 1 / Phase 1 Complete
- Tasks completed: S-001 through S-004 (Phase 0), S-010 through S-015 (Phase 1)
- Files changed/created:
  - `smart-child-safety/server/` package scaffold (`app/main.py`, `app/config.py`, `app/database.py`, `app/security.py`, `app/routers/health.py`)
  - Subpackage namespaces: `app/models/`, `app/schemas/`, `app/routers/`, `app/services/`, `app/websocket/`
  - Alembic configuration: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`
  - Deployment assets: `Dockerfile`, `.dockerignore`, `render.yaml`, `.env.example`, `.gitignore`
  - Project documentation: `README.md`, `docs/architecture.md`, `docs/api-specification.md`, `docs/database-design.md`, `docs/security.md`, `docs/deployment.md`, `docs/testing.md`, `docs/implementation-status.md`
  - Automated test suite: `tests/conftest.py`, `tests/test_health.py`, `tests/test_config.py`, `tests/test_database.py`
  - Root convenience symlink: `server -> smart-child-safety/server`
- Tests run and actual results:
  - Pytest: 11 passed in 0.05s (100% pass)
  - Live local server check: `GET /health` -> 200 OK, `GET /ready` -> 200 OK (with `X-Request-ID` tracking)
- Decisions confirmed:
  - Python 3.14 on macOS Apple Silicon M4 verified compatible with all pinned packages.
  - Pydantic Settings used for typed environment loading with URL normalization (`postgres://` -> `postgresql+psycopg://`).
  - Privacy-safe logging with UUID request tracking.
  - Zero-credentials committed; mock/fallback enabled for SQLite isolated testing.
- Known blockers: None for Stage 1. Real Firebase service-account JSON will be needed in Stage 3 for end-to-end token verification.
- Next task: Phase 2 — Database and migrations (SQLAlchemy models and Alembic migration scripts).

- Date/session: 2026-10-14 — Stage 2 / Phase 2 Complete
- Tasks completed: S-020 through S-025 (Phase 2)
- Files changed/created:
  - `app/models/user.py`: `UserProfile`, `Family`, `FamilyMembership`
  - `app/models/child.py`: `ChildProfile`, `RegisteredDevice`, `PairingCode`
  - `app/models/location.py`: `LatestLocation`, `LocationRecord`
  - `app/models/safety.py`: `SafetyZone`, `SafetyPolicy`, `SafetyEvent`
  - `app/models/command.py`: `DeviceCommand`, `CommandAcknowledgement`, `DeviceHeartbeat`
  - `app/models/__init__.py`: Registered and exported all 13 core entities + `Base`
  - `alembic/env.py`: Integrated model discovery and batch mode for SQLite
  - `alembic/versions/20261014_0509_4d9ae306f449_initial_schema_13_core_entities.py`: Initial schema migration
  - `tests/test_models.py`: 10 comprehensive tests for all entities, cascades, foreign keys, and rollbacks
  - `tests/conftest.py`: Added `db_session` fixture and SQLite foreign keys pragma enforcement
  - `docs/database-design.md`, `docs/testing.md`, `docs/implementation-status.md`: Documentation updated
- Tests run and actual results:
  - Alembic migration generated and applied to Neon cloud PostgreSQL (`alembic upgrade head`) -> head revision `4d9ae306f449`
  - Alembic migration and downgrade verified on clean SQLite (`upgrade head` and `downgrade base`)
  - Pytest: 21 passed in 0.22s (100% pass)
- Decisions confirmed:
  - UUID4 strings (`VARCHAR(36)`) used for cross-database primary keys without engine-specific extensions.
  - JSON columns use `JSON().with_variant(JSONB, 'postgresql')` for portable JSON support.
  - Cascading deletes configured on ChildProfile to guarantee clean deletion of device telemetry, locations, and events.
  - SQLite foreign key pragma enabled during tests to ensure identical constraint enforcement.
- Known blockers: None. Real Firebase credentials are now placed in `.env` (gitignored), ready for Stage 3 token verification.
- Next task: Phase 3 — Authentication and authorization (Firebase ID token verification, profile endpoints, and secure pairing).

- Date/session: 2026-10-14 — Stage 3 / Phase 3 Complete
- Tasks completed: S-030 through S-035 (Phase 3)
- Files changed/created:
  - `app/services/firebase_auth.py`: Firebase Admin SDK certificate/JSON loading and ID token verification.
  - `app/services/rate_limiter.py`: Thread-safe in-memory sliding-window rate limiter for sensitive endpoints.
  - `app/security.py`: `get_current_principal` dependency, auto-provisioning, active status check, and relationship-based access verifiers (`verify_guardian_family_access`, `verify_guardian_child_access`).
  - `app/schemas/user.py`: Request and response schemas for user profiles and family groups.
  - `app/schemas/pairing.py`: Request and response schemas for single-use pairing generation, redemption, status, and revocation.
  - `app/routers/user.py`: `/api/v1/me`, `/api/v1/families`, `/api/v1/families/{family_id}/children`.
  - `app/routers/pairing.py`: `/api/v1/pairing/create`, `/api/v1/pairing/claim`, `/api/v1/pairing/status/{child_id}`, `/api/v1/pairing/revoke/...`.
  - `app/routers/__init__.py` & `app/main.py`: Mounted user, family, and pairing routers under `/api/v1`.
  - `requirements.txt`: Added `firebase-admin>=6.5.0,<8.0.0`.
  - `tests/test_auth.py` & `tests/test_pairing.py`: Added 15 comprehensive automated test cases.
  - `docs/api-specification.md`, `docs/security.md`, `docs/testing.md`, `docs/implementation-status.md`: Updated.
- Tests run and actual results:
  - Full pytest suite: 36 passed in 0.50s (100% pass rate).
  - Live server check: `GET /api/v1/me` -> 401 Unauthorized, `POST /api/v1/pairing/claim` with invalid code -> 400 Bad Request.
- Decisions confirmed:
  - Caller identity is derived exclusively from verified Firebase ID token claims (`uid`).
  - Single-use pairing codes are stored exclusively as HMAC-SHA256 hashes with expiry and attempt counting.
  - Rate limiting protects `/api/v1/pairing/claim` (10 req/min) and `/api/v1/pairing/create` (20 req/min).
  - Cross-guardian access is blocked at the database query layer via family membership checks.
- Known blockers: None.
- Next task: Phase 4 — Location and device status (Location point model/constraints, ingestion endpoint, latest-location retrieval, paginated history, device telemetry, and freshness tracking).

- Date/session: 2026-10-14 — Stage 4 / Phase 4 Complete
- Tasks completed: S-040 through S-046 (Phase 4)
- Files changed/created:
  - `app/schemas/location.py`: Validated Pydantic models for location upload/query, freshness status, paginated history, and device telemetry.
  - `app/schemas/__init__.py`: Exported location schemas.
  - `app/models/user.py`: Added `ensure_utc` helper for timezone-safe cross-database comparisons.
  - `app/services/rate_limiter.py`: Added `location_upload_limiter` (120 req/min) and dependency.
  - `app/security.py`: Added `verify_child_ingestion_auth` supporting both paired device hardware (`X-Device-Identifier`) and authorized guardians via Bearer tokens.
  - `app/routers/location.py`: Implemented `/api/v1/children/{child_id}/locations`, `/location/latest`, `/locations` (paginated history), and `/status` (telemetry upload and query).
  - `app/routers/__init__.py` & `app/main.py`: Mounted `location_router` under `/api/v1`.
  - `tests/test_location.py`: 17 comprehensive automated tests covering coordinates validation, future/retention limits, duplicate idempotency, out-of-order handling, dynamic freshness, sharing toggle, pagination, telemetry, rate limiting, and cross-guardian security denials.
  - `docs/api-specification.md`, `docs/testing.md`, `docs/implementation-status.md`, `TASKS.md`: Documentation and task lists updated.
- Tests run and actual results:
  - Full pytest suite: **53 passed in 1.18s** (100% pass rate).
- Decisions confirmed:
  - Coordinate bounds strictly validated: latitude `[-90, 90]`, longitude `[-180, 180]`, accuracy `>= 0`, speed `>= 0`, bearing `[0, 360]`.
  - Clock drift tolerated up to 5 minutes into the future; older than 30 days retention rejected.
  - S-045 Duplicate handling: Exact child + timestamp retransmissions return `status="duplicate"` and existing ID without creating duplicate rows.
  - S-045 Out-of-order handling: Delayed historical points are appended to `LocationRecord` history, but `LatestLocation` snapshot is never regressed by older points.
  - Dynamic freshness evaluation: `LIVE` (<= 60s), `FRESH` (<= 15 min `settings.location_stale_minutes`), `STALE` (> 15 min), and `NOT_REPORTING` (no points or sharing disabled).
  - Telemetry: Collects minimal hardware status (`battery_percent`, `is_charging`, `network_type`, `location_permission_state`, `is_gps_enabled`, `storage_free_mb`) without collecting contacts/SMS/media surveillance data.
- Known blockers: None.
- Next task: Phase 5 — Persisted commands, FCM signaling and WebSockets (Command model & lifecycle, guardian remote commands, child pending-command sync, FCM signaling, and authenticated WebSockets with per-child authorization).

- Date/session: 2026-10-14 — Stage 5 / Phase 5 Complete
- Tasks completed: S-050 through S-056 (Phase 5)
- Files changed/created:
  - `app/services/fcm.py`: FCM adapter sending data-only signals (`action="SYNC_PENDING_COMMANDS"`) and high-priority notifications with resilient failure handling.
  - `app/websocket/manager.py`: Thread-safe `WebSocketConnectionManager` managing active connections, per-child subscriptions, and broadcast distribution.
  - `app/websocket/__init__.py`: Exported `ws_manager` and `WebSocketConnectionManager`.
  - `app/schemas/command.py`: Pydantic models for command creation, responses, acknowledgements, pending sync, and history.
  - `app/schemas/__init__.py`: Exported command schemas.
  - `app/routers/command.py`: Endpoints for guardian command creation, child pending-command sync, execution acknowledgement/response, and history.
  - `app/routers/websocket.py`: Authenticated WebSocket router (`/api/v1/ws`) supporting query param and message handshake auth, per-child subscription authorization, keepalive ping/pong, and clean unsubscription.
  - `app/routers/__init__.py` & `app/main.py`: Mounted `command_router` and `websocket_router` under `/api/v1`.
  - `tests/test_commands.py`: 10 automated tests covering creation, type validation, FCM fallback durability, pending command sync, auto-expiry, execution acknowledgement, 410 on expired execution, and authorization denials.
  - `tests/test_websocket.py`: 7 automated tests covering query param auth, message handshake auth, invalid credentials rejection (1008), authorized child subscription, unauthorized subscription denial, ping/pong, and real-time broadcast delivery on command acknowledgement.
  - `docs/api-specification.md`, `docs/testing.md`, `docs/implementation-status.md`, `TASKS.md`: Documentation and task lists updated.
- Tests run and actual results:
  - Full pytest suite: **70 passed in 2.98s** (100% pass rate).
- Decisions confirmed:
  - FCM is strictly a wake-up signal containing minimal data fields (`action`, `child_id`, `command_id`, `command_type`); sensitive command details are never sent in push payloads.
  - Command durability: Commands are committed to PostgreSQL *before* any FCM push attempt. If FCM fails, the command remains safely stored with status `PENDING` for child sync.
  - Command allowlist strictly enforced: `SAFETY_CHECK`, `REQUEST_LOCATION_REFRESH`, `SYNC_POLICIES`, `DEVICE_STATUS_CHECK`, `ENABLE_APP_SAFETY_MODE`, `RELEASE_APP_SAFETY_MODE`.
  - Expired commands (`expires_at < now`) automatically transition to `EXPIRED` during sync and return HTTP 410 Gone if execution is attempted.
  - WebSockets enforce per-child relationship authorization at subscription time via database membership checks.
- Known blockers: None.
- Next task: Phase 6 — SOS, safe zones and events (SOS persistence, notification attempts, circular safe-zone CRUD, entry/exit transition evaluation with duplicate suppression, authorized event listing and acknowledgement).

- Date/session: 2026-10-14 — Stage 6 / Phase 6 Complete
- Tasks completed: S-060 through S-064 (Phase 6)
- Files changed/created:
  - `app/services/geofence.py`: Geofencing service using great-circle Haversine formula, dynamic severity mapping (`SAFE` -> `LOW`/`MEDIUM`, `RESTRICTED` -> `HIGH`/`LOW`, `DANGER` -> `CRITICAL`/`MEDIUM`), duplicate transition suppression / hysteresis, and delayed location point alert suppression.
  - `app/schemas/safety.py`: Pydantic models for circular safe zone creation, update, responses, emergency SOS triggers, auditable safety event listings, and event acknowledgement.
  - `app/schemas/__init__.py`: Exported safety schemas.
  - `app/routers/safety.py`: REST endpoints for safe zone CRUD (`/children/{child_id}/safe-zones`, `/safe-zones/{zone_id}`), emergency SOS activation (`/children/{child_id}/sos`), auditable safety event listing (`/children/{child_id}/events`), and event acknowledgement (`/events/{event_id}/ack`).
  - `app/routers/location.py`: Hooked real-time geofence evaluation into `POST /api/v1/children/{child_id}/locations` and added live WebSocket broadcasting for `zone_transition` and `location_update`.
  - `app/routers/__init__.py` & `app/main.py`: Mounted `safety_router` under `/api/v1`.
  - `tests/test_safety.py`: 13 automated tests covering Haversine distance calculations, coordinate and radius boundary validation (10m to 50km), safe zone CRUD lifecycle, cross-guardian access denials, SOS persistence and FCM tracking, 60s duplicate SOS suppression, geofence entry and exit state transitions with duplicate suppression, delayed location point processing, paginated event queries with filters, event acknowledgement, and real-time WebSocket broadcast integration.
  - `docs/api-specification.md`, `docs/testing.md`, `docs/implementation-status.md`, `TASKS.md`: Documentation and task lists updated.
- Tests run and actual results:
  - Full pytest suite: **83 passed in 3.12s** (100% pass rate).
- Decisions confirmed:
  - SOS honest status: Durably persisted as `SafetyEvent(event_type="SOS", severity="CRITICAL")` *before* push notification attempt; returns `notification_status="attempted"` without false claims of emergency dispatch.
  - SOS duplicate suppression: Cooldown window of 60 seconds suppresses rapid repeated button presses and returns `status="duplicate_suppressed"` to prevent alert storms.
  - Safe zone limits: Radius strictly bounded between `10.0m` (minimum viable GPS resolution) and `50,000.0m` (50km max); coordinates validated to WGS84 bounds.
  - Geofence duplicate suppression: Jitter around boundary edges does not flap state. A transition event (`ZONE_ENTRY` or `ZONE_EXIT`) is only generated when the child crosses from outside to inside or inside to outside. Continuous inside or continuous outside points are silently ignored.
  - Delayed historical points (`is_latest=False`) are saved to history without triggering false real-time boundary flap alerts.
  - Deleting a safe zone cascades safely: preserves historical `SafetyEvent` records with `zone_id` set to `NULL` (via `ondelete="SET NULL"`).
  - Acknowledgement: Guardians acknowledge events via `POST /api/v1/events/{event_id}/ack`, updating `is_acknowledged=True`, `acknowledged_by_user_id`, and `acknowledged_at`, with live broadcast to connected WebSocket subscribers.
- Known blockers: None.
- Next task: Phase 7 — Privacy, security and deployment (Data retention policies, deletion/unlinking workflows, security audit of routes and WebSockets, log redaction check, secrets check, linting/formatting, Render configuration, and final deployment documentation).

- Date/session: 2026-10-14 — Stage 7 / Phase 7 Complete (All Phases Complete)
- Tasks completed: S-070 through S-076 (Phase 7)
- Files changed/created:
  - `app/services/retention.py`: Data retention service for pruning expired location records (> 30 days), telemetry heartbeats (> 30 days), expired unredeemed pairing codes, and stale completed commands.
  - `app/routers/maintenance.py`: REST endpoint `POST /api/v1/maintenance/retention/cleanup` for scheduled and manual retention pruning.
  - `app/schemas/user.py`: Added `ChildUpdate` and `RetentionCleanupResponse` models.
  - `app/schemas/__init__.py`: Exported new schemas.
  - `app/routers/user.py`: Implemented `DELETE /api/v1/me` (self-service account deactivation), `PATCH /api/v1/families/{family_id}/children/{child_id}` (child profile settings update), and `DELETE /api/v1/families/{family_id}/children/{child_id}` (cascading child deletion right-to-be-forgotten).
  - `app/routers/pairing.py`: Enhanced device unpairing (`DELETE /api/v1/pairing/revoke/...`) to deactivate device, clear `fcm_token`, and update timestamps.
  - `app/routers/__init__.py` & `app/main.py`: Mounted `maintenance_router` under `/api/v1`.
  - `requirements.txt`: Explicitly declared `websockets>=13.0.0,<18.0.0`.
  - `render.yaml`: Hardened build command with automatic migration execution (`pip install -r requirements.txt && alembic upgrade head`).
  - `docs/deployment.md`: Enriched production deployment runbook, environment variable reference, migration instructions, and health probe documentation.
  - `docs/api-specification.md`, `docs/testing.md`, `docs/implementation-status.md`, `TASKS.md`: Documentation and task lists updated.
  - `tests/test_retention.py`: 8 automated tests covering location pruning, heartbeat pruning, pairing code pruning, maintenance endpoint, cascading child profile deletion, child settings update, account deactivation, and revoked device upload prevention.
- Tests run and actual results:
  - Full pytest suite: **91 passed in 10.83s** (100% pass rate).
  - Python compiler: `python -m compileall app tests` completed with zero syntax errors.
- Decisions confirmed:
  - Right to be forgotten: Deleting a child profile (`DELETE /families/{family_id}/children/{child_id}`) triggers cascading removal across all linked tables (`LocationRecord`, `LatestLocation`, `RegisteredDevice`, `DeviceCommand`, `CommandAcknowledgement`, `SafetyEvent`, `PairingCode`, `DeviceHeartbeat`).
  - Account deactivation: `DELETE /me` sets `is_active=False` and `disabled_at=now`. Subsequent calls with tokens belonging to disabled accounts are blocked with HTTP 403 Forbidden.
  - Revoked devices: When unlinked, `is_active` is set to False and `fcm_token` is cleared to `NULL` to prevent unwanted push notifications; subsequent location or status uploads from deactivated hardware identifiers return HTTP 401 Unauthorized.
  - Retention cleanup: Scheduled pruning safely deletes rows exceeding `settings.location_retention_days` (default 30 days) and expired unredeemed pairing codes in an atomic transaction.
- Status: Project implementation complete. All phases in `TASKS.md` (Phases 0 through 7) are completed, tested, and verified.


