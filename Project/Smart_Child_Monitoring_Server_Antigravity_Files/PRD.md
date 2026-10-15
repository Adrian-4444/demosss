# PRD — Smart Child Monitoring System Backend Server

## 1. Purpose
Build a secure backend server that connects the Parent Android App and Child Android App. The server is the source of truth for user access, parent-child links, location history, device status, safe zones, safety events, and remote safety-check commands.

## 2. Product boundaries
This repository is for the **backend server only**. Do not build Android screens or frontend UI here. Mobile apps consume the documented REST API and authenticated WebSocket endpoint.

## 3. Approved baseline
- Language/runtime: Python
- API framework: FastAPI
- Validation/settings: Pydantic and typed environment settings
- Database: PostgreSQL
- ORM: SQLAlchemy
- Schema migrations: Alembic
- Push notifications: Firebase Cloud Messaging (FCM)
- Parent live updates: authenticated WebSockets
- Hosting: Render
- Managed database target: Neon PostgreSQL or equivalent
- Tests: pytest and HTTPX/FastAPI test client
- Python version and dependency versions must be selected, pinned/limited, and documented during setup.

## 4. Main goals
1. Authenticate requests and enforce authorization on every protected resource.
2. Securely pair a guardian account with a child profile/device.
3. Receive and store child location updates and minimal device status.
4. Provide authorized latest-location and paginated history queries.
5. Store safety-check commands durably, notify the child through FCM, and accept responses.
6. Persist SOS and safe-zone events and notify authorized guardians.
7. Publish authorized near-real-time events to parent WebSocket sessions.
8. Support revocation, data retention/deletion, observability, tests, and Render deployment.

## 5. User roles
- **Guardian:** can access only child profiles linked to their authenticated account.
- **Child/device:** can submit data only for its authenticated child identity and fetch/respond to its own eligible commands.
- **Operator:** deployment/operations access only; no routine access to child location content.

## 6. Functional requirements
- **FR-01 Authentication:** use a documented, secure authentication strategy. Prefer a trusted identity provider if already selected by the mobile apps. Validate issuer, audience, signature, expiry, and relevant claims. Never trust a client-supplied user ID as proof of identity.
- **FR-02 Authorization:** verify the active guardian-child relationship on every relevant REST route and WebSocket subscription.
- **FR-03 Pairing:** use expiring, single-use pairing secrets; store only a secure hash; rate-limit attempts; support unlinking/revocation.
- **FR-04 Location ingestion:** validate latitude/longitude, capture timestamp, accuracy, and authenticated child identity. Store capture time separately from server receipt time.
- **FR-05 Latest location/history:** return the newest valid point and paginated, retention-limited history only to authorized guardians. Include freshness/accuracy metadata.
- **FR-06 Device status:** accept minimal status such as battery percentage, connectivity, location permission, sharing state, and last-seen when available.
- **FR-07 Safety checks:** guardian creates an allowed safety-check command; server persists it before attempting FCM; child fetches pending commands through an authenticated API and posts a response.
- **FR-08 SOS:** persist the event first, then attempt notification to linked guardians. Return an honest status; do not promise delivery or emergency response.
- **FR-09 Safe zones:** create/list/update/disable/delete circular zones and generate entry/exit events from eligible location updates with duplicate suppression.
- **FR-10 Notifications:** FCM is a signal only, not the database or source of truth. Minimize sensitive data in push payloads.
- **FR-11 WebSockets:** authenticate connections, authorize each subscription, send only allowed events, and resynchronize from persisted state after reconnect.
- **FR-12 Auditing:** record security-relevant actions without logging secrets or unnecessary precise location details.
- **FR-13 Data lifecycle:** implement documented retention, unlinking, account deletion, and related token revocation.
- **FR-14 Health:** expose a minimal health/readiness endpoint that does not leak secrets or configuration.

## 7. Non-functional requirements
- HTTPS/TLS in deployed environments.
- Strict server-side access checks and least privilege.
- No committed secrets; use environment variables/hosting secrets.
- Consistent error responses and privacy-safe structured logs.
- Database constraints, foreign keys, indexes, and migrations.
- Idempotency or duplicate handling for retried submissions where appropriate.
- Bounded/paginated queries and request validation.
- Automated tests for both success and unauthorized/invalid cases.
- Maintainable modules with type hints and clear service boundaries.
- No claim that location is live if stale, unavailable, or device-offline.
- Follow Android permissions and OS background-location limitations; the server cannot bypass them.

## 8. Out of scope
- Parent/child Android UI implementation.
- Covert tracking or permission bypass.
- Capturing messages, calls, microphone, camera, or unrelated personal data.
- Remote lock/wipe or punitive autonomous actions.
- Treating an anomaly score as proof that a child is in danger.
- Guaranteed delivery of notifications or guaranteed emergency response.

## 9. Acceptance criteria
- A guardian cannot retrieve data for an unlinked child, including by changing IDs.
- Expired, invalid, and reused pairing secrets are rejected.
- Location values are validated; stale timestamps are handled safely.
- Commands remain retrievable if FCM fails or is delayed.
- WebSocket connections and subscriptions enforce authentication and authorization.
- Critical flows have automated tests.
- Migrations work on a clean database.
- `.env.example`, setup instructions, test instructions, and Render deployment instructions are present.
- The final report lists tests actually run and their real outcomes.

## 10. Suggested build phases
1. Inspect repository and establish server skeleton.
2. Configuration, health endpoint, PostgreSQL connection, SQLAlchemy, Alembic, tests.
3. Authentication, roles, pairing and authorization.
4. Location ingestion, latest/history queries, device status.
5. Persisted commands, FCM signaling, WebSockets and child responses.
6. SOS, safe zones, alert queries and duplicate suppression.
7. Retention/deletion, security review, test hardening and deployment.

Do not implement every phase in one large change. Finish and validate each phase before continuing.
