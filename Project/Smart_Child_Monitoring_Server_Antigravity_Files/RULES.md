# RULES — Antigravity Backend Development Rules

These instructions are mandatory for server changes.

## 1. Before coding
1. Inspect the current repository and Git status.
2. Read all six project documents.
3. Identify existing conventions and dependencies before proposing changes.
4. State the scope, files to change, and acceptance criteria for each substantial phase.
5. Do not overwrite or delete user work without explicit approval.
6. Ask before making a decision that materially affects security, privacy, authentication, data retention, or deployment.

## 2. Source of truth
- `PRD.md`: requirements and scope.
- `ARCHITECTURE.md`: backend boundaries, components, data model and API outline.
- `RULES.md`: coding and security rules.
- `DESIGN.md`: API interaction/error-state and service contract behavior.
- `TASKS.md`: implementation order and completion state.
- `MEMORY.md`: durable decisions, discoveries, and unresolved questions.
If these documents conflict, stop and report the conflict instead of silently guessing.

## 3. Stack and code quality
- Use Python + FastAPI, Pydantic, PostgreSQL, SQLAlchemy and Alembic unless the repository has an explicitly approved alternative.
- Use type hints and clear modules. Keep route handlers thin and business logic in services.
- Use dependency injection for database sessions and authenticated identity.
- Use UTC timestamps. Keep capture time and server receipt time distinct.
- Use database migrations for schema changes; do not treat `create_all()` as production migration management.
- Use transactions for multi-step writes that must be consistent.
- Add foreign keys, constraints, and indexes where justified.
- Validate request and response schemas.
- Use consistent HTTP status codes and error responses without leaking internals.
- Keep dependencies minimal and document any new dependency.

## 4. Security and privacy rules
- Every client value is untrusted.
- Never use a client-provided user/guardian/child ID alone to authorize access.
- Check active guardian-child link on every relevant route and WebSocket subscription.
- Never expose child location to unauthenticated users or unlinked guardians.
- Never commit `.env`, credentials, tokens, private keys, FCM service-account files, or real personal data.
- Keep secrets in environment variables or hosting secret storage.
- Never log passwords, bearer tokens, refresh tokens, raw pairing codes, full FCM tokens, or unnecessary precise coordinates.
- Hash pairing secrets before storing them; enforce expiry, one-time use, and rate limiting.
- Verify auth tokens using the selected provider's official validation method; do not implement cryptography yourself.
- Persist events/commands before attempting notifications.
- Treat FCM as a best-effort signal, not a durable queue or proof of delivery.
- Authenticate WebSockets and scope each event to authorized sessions.
- Do not implement covert tracking, stealth, permission bypass, or unrelated surveillance.
- Respect data retention, unlinking and deletion requirements.
- Treat anomaly/risk signals as uncertain and explainable, never proof of danger.

## 5. API rules
- Use `/api/v1` for versioned endpoints unless existing conventions are already established.
- Publish request/response models in OpenAPI.
- Add pagination and bounded time windows to history queries.
- Validate coordinate bounds, timestamp plausibility, battery range, radius limits and command allowlists.
- Handle duplicate requests, stale/out-of-order location points and expired commands.
- Use rate limiting for authentication, pairing, SOS and commands.
- Avoid exposing stack traces in production responses.
- Do not add a route without authorization tests where the route accesses child-specific data.

## 6. Tests and verification
- Use pytest and the existing project test tooling.
- Test happy paths and negative cases.
- Include tests for cross-guardian access, revoked links, expired/reused pairing codes, invalid coordinates, stale locations, command expiry, FCM failure, and WebSocket authorization.
- Use synthetic test data only.
- Run relevant tests, lint/type checks and app startup/build checks after changes.
- Do not claim a command passed unless it was actually run and passed.
- If a check cannot run, state why and what remains unverified.

## 7. Repository safety
- Preserve unrelated user changes.
- Do not run destructive shell commands or rewrite Git history without explicit approval.
- Do not commit automatically unless asked.
- Review `git diff` before finishing.
- Keep generated caches, virtual environments, secrets and local database files out of Git.

## 8. Completion report
For each phase, report:
- Summary of behavior implemented.
- Files created/changed.
- Tests/checks actually run and results.
- Security/authorization considerations addressed.
- Known gaps or blockers.
- Next task.
Update `TASKS.md` and `MEMORY.md` when state or durable decisions change. A task is not done merely because code was generated.
