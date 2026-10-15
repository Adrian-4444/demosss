# TASKS — Backend Server Implementation Checklist

**Statuses:** `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`  
Only mark `DONE` after implementation and validation.

## Phase 0 — Inspect before changing
- [x] S-001 Inspect current repository, Git status, existing Python files, Android folders (if present), and dependency manager. **DONE**
- [x] S-002 Read all six Markdown documents and report conflicts/open decisions. **DONE**
- [x] S-003 Recommend the first small implementation slice and list files to change. **DONE**
- [x] S-004 Confirm authentication approach before implementing protected endpoints. **DONE**

## Phase 1 — FastAPI foundation
- [x] S-010 Create/adapt backend package and FastAPI application entry point. **DONE**
- [x] S-011 Add typed environment configuration and safe `.env.example`. **DONE**
- [x] S-012 Add `.gitignore` for `.env`, virtualenvs, caches, test artifacts and local database files. **DONE**
- [x] S-013 Add minimal `/health` endpoint. **DONE**
- [x] S-014 Add privacy-safe structured logging and request IDs. **DONE**
- [x] S-015 Add pytest/HTTPX tests for app startup and health endpoint. **DONE**

**Acceptance:** API starts locally, health test passes, no secrets are committed, and setup commands are documented. (Verified: 11 tests passed, local server tested with curl)

## Phase 2 — Database and migrations
- [x] S-020 Configure PostgreSQL URL and SQLAlchemy engine/session lifecycle. **DONE**
- [x] S-021 Configure Alembic and metadata discovery. **DONE**
- [x] S-022 Design initial models and relationships. **DONE**
- [x] S-023 Generate and review first migration. **DONE**
- [x] S-024 Test migration on a clean local/test database. **DONE**
- [x] S-025 Add database connection and rollback/error handling tests. **DONE**

**Acceptance:** Clean migration succeeds; schema changes are tracked only through migrations. (Verified: Neon PostgreSQL upgraded to head revision 4d9ae306f449, SQLite migration tested, 21 tests passed)

## Phase 3 — Authentication and authorization
- [x] S-030 Confirm provider and token-validation requirements. **DONE**
- [x] S-031 Implement verified authenticated principal dependency. **DONE**
- [x] S-032 Implement roles and active guardian-child relationship checks. **DONE**
- [x] S-033 Implement pairing code creation, hashed storage, expiry, one-time claim and revocation. **DONE**
- [x] S-034 Add rate limiting and anti-enumeration behavior. **DONE**
- [x] S-035 Test invalid tokens, expired/reused codes, revoked links and cross-guardian access. **DONE**

**Acceptance:** Identity comes from verified credentials and unlinked guardians cannot access child data. (Verified: 15 auth and pairing tests passed, 36 total tests passed)

## Phase 4 — Location and device status
- [x] S-040 Implement location point model, constraints and indexes. **DONE**
- [x] S-041 Implement child location ingestion endpoint. **DONE**
- [x] S-042 Implement latest-location endpoint. **DONE**
- [x] S-043 Implement paginated and retention-limited history endpoint. **DONE**
- [x] S-044 Implement minimal device-status endpoint. **DONE**
- [x] S-045 Handle duplicate, stale and out-of-order updates. **DONE**
- [x] S-046 Test invalid coordinates, authorization, pagination and stale states. **DONE**

**Acceptance:** Location and status endpoints are validated, tested, and relationship-scoped. (Verified: 17 location and telemetry tests passed, 53 total tests passed)

## Phase 5 — Persisted commands, FCM and WebSockets
- [x] S-050 Implement command model, allowed types, status transitions and expiry. **DONE**
- [x] S-051 Implement guardian safety-check creation and child pending-command sync. **DONE**
- [x] S-052 Implement child response endpoint and parent event updates. **DONE**
- [x] S-053 Add FCM adapter with credentials loaded from environment/secret storage. **DONE**
- [x] S-054 Persist commands before sending FCM and handle send failures. **DONE**
- [x] S-055 Implement authenticated WebSocket manager and per-child subscription authorization. **DONE**
- [x] S-056 Test reconnect/resync, FCM failure, expiry and unauthorized subscriptions. **DONE**

**Acceptance:** Commands remain in PostgreSQL and can be fetched even when FCM fails. (Verified: 17 command and WebSocket tests passed, 70 total tests passed)

## Phase 6 — SOS, safe zones and events
- [x] S-060 Implement SOS persistence and notification attempt. **DONE**
- [x] S-061 Implement safe-zone CRUD with coordinate/radius validation. **DONE**
- [x] S-062 Implement entry/exit evaluation and duplicate suppression. **DONE**
- [x] S-063 Implement authorized event listing and acknowledgement. **DONE**
- [x] S-064 Test duplicate SOS, boundary cases, delayed location and unauthorized access. **DONE**

**Acceptance:** Events are auditable, geofencing is deterministic, and false alert storms are mitigated. (Verified: 13 safety, geofencing, and SOS tests passed, 83 total tests passed in 3.12s)

## Phase 7 — Privacy, security and deployment
- [x] S-070 Implement retention and deletion/unlinking behavior. **DONE**
- [x] S-071 Review all REST routes and WebSocket authorization. **DONE**
- [x] S-072 Review logs, FCM payloads, CORS if relevant, rate limits and secret handling. **DONE**
- [x] S-073 Run tests, formatter, linter/type checks and dependency review. **DONE**
- [x] S-074 Configure Render service and managed PostgreSQL connection. **DONE**
- [x] S-075 Document migrations, environment variables, health check, startup command and deployment. **DONE**
- [x] S-076 Record actual test/deployment outcomes and known limitations. **DONE**

**Acceptance:** Deployment configuration, right-to-be-forgotten deletion workflows, retention pruning, privacy logs, security authorization, and automated test suite are fully completed, tested, and documented. (Verified: 91 total tests passing in 10.83s, 100% pass rate)

## Status Summary
All phases (Phase 0 through Phase 7) are fully implemented, tested, and verified. The backend server for the Smart Child Monitoring and Safety System is complete and ready for production deployment.


