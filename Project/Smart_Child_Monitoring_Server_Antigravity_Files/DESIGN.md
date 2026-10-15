# DESIGN — Backend API and Service Contracts

This is the design document for the **server API and backend behavior**, not the Android visual design.

## 1. Contract principles
- JSON REST API under `/api/v1`; WebSocket endpoint under `/api/v1/ws`.
- Authentication is required for all protected routes.
- Authorization is relationship-based and checked server-side.
- Use consistent response schemas, UTC ISO-8601 timestamps, clear error codes, and request IDs where practical.
- Do not expose secrets or unnecessary precise location data in logs, push messages, or error responses.
- Exact schemas should be implemented in Pydantic and documented by FastAPI OpenAPI.

## 2. Authentication contract
Choose and document the auth provider before implementation. If using an identity provider, verify signed tokens using its supported SDK/JWKS flow, issuer, audience, expiry, and required claims. Derive the actor from verified credentials; never accept a request body user ID as identity proof.

Suggested error semantics:
- `401 Unauthorized`: missing or invalid credentials.
- `403 Forbidden`: authenticated but not permitted.
- `404 Not Found`: resource absent; consider using a consistent non-enumerating policy for sensitive resources.
- `409 Conflict`: duplicate/incompatible state transition.
- `422 Unprocessable Entity`: schema or validation failure.
- `429 Too Many Requests`: rate limit reached.

## 3. Pairing contract
- Pairing code is short-lived, single-use, random, rate-limited and stored as a hash.
- Claiming must be atomic so two requests cannot redeem the same code.
- Successful claim creates an active guardian-child link.
- Unlinking revokes access and prevents new commands from the former guardian.
- Never log or return a pairing secret after the initial authorized display.

## 4. Location contract
Suggested location submission fields:
- `latitude`: number from -90 through 90.
- `longitude`: number from -180 through 180.
- `accuracy_m`: non-negative number when supplied.
- `captured_at`: ISO-8601 timestamp with timezone.
- Optional minimal source metadata if justified.

Server adds `received_at`. Return latest point with captured/received timestamps, accuracy if known, and a derived freshness state. The freshness threshold should be configurable and documented, not hidden in UI assumptions. History responses should be paginated and bounded by retention policy.

## 5. Device-status contract
Only collect fields needed for the feature:
- battery percentage (0–100, optional)
- connectivity state (coarse)
- location permission state
- sharing enabled/disabled
- observed timestamp

Do not collect contacts, SMS, call logs, microphone, camera, or unrelated app data.

## 6. Command contract
- Allowlist command types; first release includes `SAFETY_CHECK`.
- Command includes ID, type, created time, expiry, and status.
- Persist command before triggering FCM.
- Child fetches its own pending commands through an authenticated endpoint.
- Child response includes an allowed response/status and timestamp.
- Commands must expire and must not execute after expiry or link revocation.
- Repeated requests should not create duplicate actions where an idempotency key is used.
- FCM payload should be a minimal signal (for example, “sync pending command”) rather than sensitive command details.

## 7. SOS and event contract
- SOS is an explicit child-initiated event.
- Persist the event before notification attempts.
- Distinguish event persistence from notification attempt/delivery status.
- Safe-zone events should record zone, event type, and timestamps with minimized details.
- Apply duplicate suppression/cooldowns to noisy boundary crossings.
- An inferred anomaly must be labeled as an inference, with a reason and uncertainty.

## 8. WebSocket contract
- Require valid authentication during connection setup.
- Client requests a subscription only to child IDs it is authorized to access.
- Server validates every subscription and sends only scoped event types.
- Define heartbeat, disconnect behavior, reconnect guidance, and payload versioning.
- On reconnect, client fetches authoritative state through REST; WebSocket events are not a durable event log.
- Do not put bearer tokens in URLs if avoidable; use a secure supported authentication handshake.

## 9. Notification behavior
- FCM send happens after database commit.
- Transient failures may be retried with bounded backoff.
- Invalid tokens should be marked/revoked.
- Notification status must reflect only evidence the server actually has.
- Do not claim that a push was seen by a person based only on a successful send request.

## 10. Observability
- Structured logs with request ID, route, status, duration, and safe error category.
- Redact authorization headers and secrets.
- Avoid logging raw request bodies for location, pairing, authentication, or commands.
- Health endpoint reveals only minimal service status.
- Track operational failures without collecting unnecessary personal data.

## 11. Contract acceptance checklist
- [ ] OpenAPI reflects actual routes and schemas.
- [ ] Protected routes return appropriate auth errors.
- [ ] Cross-guardian data access is denied.
- [ ] Timestamps are timezone-aware and consistently UTC in storage.
- [ ] FCM payloads are minimized.
- [ ] WebSocket events are scoped and reconnect is recoverable.
- [ ] Errors and logs do not reveal secrets or sensitive data.
