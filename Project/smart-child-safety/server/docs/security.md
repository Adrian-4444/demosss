# Security, Authentication, and Privacy

## 1. Threat Model & Boundaries
- **Untrusted Mobile Clients:** Mobile apps (Android Parent and Child) are treated as untrusted clients. All claims, parameters, and associations are verified server-side.
- **Privacy-Preserving Architecture:** No covert tracking, stealth recording, or interception of messages, calls, camera, or microphone is implemented.
- **Zero Client Trust:** The backend derives caller identity strictly from verified cryptographic tokens (Firebase ID tokens). Request body user IDs are never trusted as identity proof.

## 2. Authentication Contract
- **Identity Provider:** Firebase Authentication.
- **Token Verification:** Every protected route uses `HTTPBearer` and verifies the ID token using `firebase_admin.auth.verify_id_token`.
- **Identity Derivation:** The user's UID is derived strictly from the cryptographically verified token claims (`decoded_token["uid"]`).
- **Profile Auto-Provisioning:** On first successful authentication, the system provisions an active `UserProfile` linked to the verified Firebase UID.
- **Account State Validation:** Deactivated or disabled accounts (`is_active=False` or `disabled_at IS NOT NULL`) are immediately denied with HTTP 403 Forbidden.

## 3. Relationship-Based Authorization (ABAC / ReBAC)
- **Family Scoping:** Every resource (child profile, safe zone, safety policy, device command) belongs to a `Family`.
- **Relationship Verification:** `verify_guardian_child_access(child_id)` enforces that the authenticated caller has an active `FamilyMembership` within the family that owns the child.
- **Cross-Guardian Isolation:** An unlinked guardian cannot read or mutate another family's children, pairing codes, devices, or locations. Attempts are rejected with HTTP 403 Forbidden.

## 4. Parent-Child Pairing Security
- **Short-Lived Codes:** Pairing invitation codes expire after a configurable duration (default: 15 minutes).
- **Single-Use & Atomic Claims:** Atomic transactions ensure a code can only be redeemed once. Re-submission returns HTTP 409 Conflict.
- **Hashed Storage:** Raw 6-character pairing codes are returned exclusively to the generating guardian once and are never persisted to disk or database. Only HMAC-SHA256 hashes are stored.
- **Maximum Attempt Lockout:** Codes track failed verification attempts. Exceeding 5 attempts locks the code to prevent brute-force attacks.

## 5. Rate Limiting & Anti-Enumeration
- **Sliding-Window Protection:** An in-memory thread-safe rate limiter guards `/api/v1/pairing/claim` (10 req/min) and `/api/v1/pairing/create` (20 req/min) per client IP.
- **Uniform Error Messages:** Generic "Invalid pairing code" messages prevent attackers from discovering valid vs. non-existent pairing codes.

## 6. Privacy & Log Sanitization
- Logs record request metadata (`method`, `path`, `status`, `duration_ms`, `request_id`).
- Authorization headers (`Bearer ...`), credentials, tokens, passwords, and precise GPS coordinates are strictly excluded from structured logs.
- `.env`, private keys, and Firebase service account JSON files are excluded by `.gitignore` and `.dockerignore`.
