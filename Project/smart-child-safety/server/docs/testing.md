# Testing & Verification Strategy

## 1. Testing Framework
- **Test Runner:** Pytest 9.x
- **HTTP Client:** HTTPX / Starlette TestClient
- **Database Engine for Tests:** Isolated SQLite / in-memory instance, ensuring zero side-effects on production or local development databases. Foreign key enforcement is explicitly activated via SQLite PRAGMA.

## 2. Test Execution
Execute the full test suite with verbose reporting:
```bash
pytest -v
```

## 3. Verification History

### Phase 7 Verification Results (Data Retention, Privacy & Deployment Hardening)
Date of execution: October 14, 2026
Test outcome: **91 passed in 10.83s** (100% pass rate)

#### Data Retention, Deletion & Right to be Forgotten (`tests/test_retention.py` - 8 tests)
- `test_retention_prune_expired_location_records`: Prunes historical location points older than retention limit (30 days) while preserving modern points.
- `test_retention_prune_expired_heartbeats`: Prunes telemetry heartbeats older than retention limit (30 days).
- `test_retention_prune_expired_pairing_codes`: Prunes expired unredeemed pairing codes while preserving valid codes.
- `test_retention_maintenance_endpoint`: Tests `POST /api/v1/maintenance/retention/cleanup` execution and metrics payload.
- `test_child_profile_deletion_cascades_all_tracking_history`: Full right-to-be-forgotten verification: deleting a child profile permanently removes all GPS history, latest location, paired devices, commands, and safety events.
- `test_child_profile_settings_update`: Tests partial updates (`PATCH /families/{family_id}/children/{child_id}`) for child settings (display name, sharing enabled toggle).
- `test_account_deactivation_right_to_be_forgotten`: Tests self-service account deactivation (`DELETE /me`) and subsequent 403 Forbidden enforcement on disabled accounts.
- `test_device_revocation_clears_fcm_token_and_blocks_uploads`: Tests device unpairing (`DELETE /pairing/revoke/...`): deactivates device, clears FCM token, and blocks further telemetry uploads.

---

### Phase 6 Verification Results (Safe Zones, Geofencing, SOS & Safety Events)
Date of execution: October 14, 2026
Test outcome: **83 passed in 3.12s** (100% pass rate)


#### Safe Zones, Geofencing & Safety Events (`tests/test_safety.py` - 13 tests)
- `test_haversine_distance_calculations`: Validates geodesic Haversine distance accuracy between known coordinates and zero-distance identical points.
- `test_create_safe_zone_authorized_guardian`: Guardian creates circular safe zone with coordinate validation (SAFE, RESTRICTED, DANGER).
- `test_safe_zone_coordinate_and_radius_bounds_validation`: Enforces coordinate boundaries (lat -90 to 90, lon -180 to 180), radius limits (10m to 50,000m), and valid zone types with HTTP 422.
- `test_list_and_get_and_update_and_delete_safe_zones`: Comprehensive CRUD operations: list active/inactive zones, get zone by ID, partial update (PATCH), and cascade-safe deletion (DELETE) preserving safety event history.
- `test_cross_guardian_safe_zone_access_denied`: Unlinked guardians are forbidden from creating, retrieving, updating, or deleting another family's safe zones.
- `test_trigger_emergency_sos_device_and_guardian`: SOS event persisted with `severity="CRITICAL"`, notification attempted via FCM, and honest `notification_status="attempted"` returned.
- `test_emergency_sos_duplicate_suppression_within_cooldown`: Rapid SOS button presses within the 60-second cooldown window are suppressed with `status="duplicate_suppressed"` to prevent alert storms.
- `test_sos_unauthorized_access_denied`: Unauthenticated callers and unregistered hardware IDs are rejected with HTTP 401.
- `test_geofence_entry_exit_and_duplicate_suppression_on_location_ingestion`: Ingested GPS points evaluate circular boundaries, generate `ZONE_ENTRY` and `ZONE_EXIT` events, and suppress duplicate transitions for continuous inside/outside fixes.
- `test_geofence_delayed_location_point_suppression`: Delayed historical locations are saved to history without triggering false real-time boundary flap alerts.
- `test_list_child_safety_events_and_filtering`: Paginated event query with filtering by `event_type`, `severity`, and acknowledgement status.
- `test_acknowledge_safety_event_and_cross_guardian_denial`: Guardian marks safety event acknowledged; cross-family guardians are rejected with HTTP 403.
- `test_websocket_broadcast_on_sos_and_zone_transition`: Verified real-time WebSocket notifications are broadcast for `sos_alert`, `zone_transition`, and `location_update`.

---

### Phase 5 Verification Results (Persisted Commands, FCM & WebSockets)
Date of execution: October 14, 2026
Test outcome: **70 passed in 2.98s** (100% pass rate)


#### Remote Commands & FCM Push Signaling (`tests/test_commands.py` - 10 tests)
- `test_create_command_authorized_guardian`: Guardian creates allowlisted command; durably persisted in database with status `SIGNAL_SENT` upon successful FCM signal.
- `test_create_command_invalid_type_rejected`: Command types outside the allowlist are rejected with HTTP 422.
- `test_command_persists_when_fcm_fails`: FCM delivery failure or network error leaves command safely stored in PostgreSQL with status `PENDING` (S-054).
- `test_child_device_sync_pending_commands`: Paired child device fetches active pending commands via `X-Device-Identifier`.
- `test_pending_commands_auto_expire`: Expired commands (`expires_at < now`) are automatically transitioned to `EXPIRED` status and excluded from active sync (S-050).
- `test_acknowledge_command_success`: Child device executes command, updates status to `EXECUTED`, and stores immutable `CommandAcknowledgement`.
- `test_acknowledge_expired_command_returns_410`: Child device attempting to execute an expired command receives HTTP 410 Gone.
- `test_command_history_pagination`: Guardian queries paginated command history with status filtering.
- `test_cross_guardian_cannot_issue_commands`: Unlinked guardian is forbidden from issuing commands to another family's child (HTTP 403).
- `test_mismatched_device_cannot_ack_command`: Device paired to Child B cannot acknowledge commands issued to Child A (HTTP 403).

#### Authenticated Real-Time WebSockets (`tests/test_websocket.py` - 7 tests)
- `test_websocket_connect_with_query_token_success`: Authentication verified via URL query parameter `?token=<firebase_id_token>`.
- `test_websocket_connect_with_message_handshake_success`: Connection accepted and authenticated via first message handshake `{"action": "authenticate"}`.
- `test_websocket_unauthenticated_connection_rejected`: Invalid token triggers error message and connection closure with policy violation code 1008.
- `test_websocket_subscribe_authorized_child`: Authorized guardian subscribes to child event stream (`{"action": "subscribe"}`) and receives confirmation.
- `test_websocket_subscribe_unauthorized_child_denied`: Subscription to unlinked child profile is blocked with unauthorized error event (S-055).
- `test_websocket_ping_pong_and_unsubscribe`: Keep-alive ping/pong and clean unsubscription.
- `test_websocket_broadcast_on_command_ack`: End-to-end integration: when child device acknowledges command via REST, subscribed guardian receives real-time `command_status_changed` WebSocket broadcast!

---

### Phase 4 Verification Results (Location & Device Status)
Date of execution: October 14, 2026
Test outcome: **53 passed in 1.18s** (100% pass rate)

#### Location Tracking & Device Telemetry (`tests/test_location.py` - 17 tests)
- `test_ingest_location_success_as_child_device`: Paired child device uploads GPS position via `X-Device-Identifier`, updates `LatestLocation` snapshot, appends to `LocationRecord`, and updates `last_seen_at`.
- `test_ingest_location_success_as_guardian`: Authorized guardian can upload location via Bearer token.
- `test_ingest_location_coordinate_bounds_validation`: WGS84 coordinate bounds strictly enforced (-90/90 lat, -180/180 lon, accuracy >= 0, speed >= 0, bearing 0–360) with HTTP 422.
- `test_ingest_location_future_timestamp_rejected`: Captures exceeding 5-minute future clock drift are rejected with HTTP 422.
- `test_ingest_location_retention_window_exceeded_rejected`: Captures older than the 30-day retention window are rejected with HTTP 422.
- `test_ingest_duplicate_location_handling`: Retransmitted duplicate points return `status="duplicate"` and existing ID without creating duplicate database rows (S-045).
- `test_ingest_out_of_order_location_updates`: Delayed historical points are appended to time-series history, but `LatestLocation` snapshot is never regressed by older points (S-045).
- `test_get_latest_location_not_reporting_initially`: Child profile with no location returns `freshness_status="NOT_REPORTING"` with `location=null`.
- `test_get_latest_location_dynamic_freshness_states`: Dynamic calculation accurately evaluates `LIVE` (<= 60s), `FRESH` (<= 15 min), and `STALE` (> 15 min).
- `test_location_sharing_disabled_behavior`: When sharing is disabled, uploads are rejected with HTTP 403 and latest queries return `NOT_REPORTING`.
- `test_get_location_history_pagination`: Paginated descending query with `limit`, `offset`, and strict 30-day retention cutoff enforcement.
- `test_device_status_upload_and_retrieval`: Child device uploads battery/charging/network/permission telemetry; guardian queries online status.
- `test_unauthenticated_requests_denied`: Calls lacking device identifier or Bearer token are rejected with HTTP 401.
- `test_invalid_or_deactivated_device_identifier_denied`: Unregistered or deactivated hardware identifiers are rejected with HTTP 401.
- `test_mismatched_device_child_denied`: Device paired to Child A attempting to upload for Child B is blocked with HTTP 403.
- `test_cross_guardian_cannot_access_child_location_or_status`: Unlinked guardian is forbidden from accessing child location or status (HTTP 403).
- `test_location_rate_limiter_blocks_excessive_uploads`: Exceeding 120 location uploads per minute returns HTTP 429 Too Many Requests.

---

### Phase 3 Verification Results (Authentication & Pairing)
Date of execution: October 14, 2026
Test outcome: **36 passed in 0.50s** (100% pass rate)
- 7 tests in `tests/test_auth.py`
- 8 tests in `tests/test_pairing.py`
- 10 tests in `tests/test_models.py`
- 11 tests in `tests/test_config.py`, `tests/test_database.py`, `tests/test_health.py`

## 4. Alembic Migration Verification
- Current revision on Neon cloud PostgreSQL: `4d9ae306f449 (head)`.
- Verified clean upgrade and downgrade on SQLite.
