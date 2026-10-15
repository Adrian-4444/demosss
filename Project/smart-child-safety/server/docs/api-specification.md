# API Specification

## Base URLs
- Local Development: `http://localhost:8000`
- API Prefix: `/api/v1`
- OpenAPI Documentation: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

---

## 1. System Health Probes

### Service Liveness Probe
- **Endpoint:** `GET /health` (also `GET /api/v1/health`)
- **Authentication:** None
- **Response `200 OK`:**
```json
{
  "status": "ok",
  "service": "Smart Child Monitoring and Safety System",
  "version": "0.1.0",
  "timestamp": "2026-10-14T05:27:50.000000+00:00"
}
```

### Service Readiness Probe
- **Endpoint:** `GET /ready` (also `GET /api/v1/ready`)
- **Authentication:** None
- **Response `200 OK`:**
```json
{
  "status": "ready",
  "database": "connected",
  "timestamp": "2026-10-14T05:27:50.000000+00:00"
}
```

---

## 2. Authentication & User Profile (`/api/v1/me`)

### Get Current User Profile
- **Endpoint:** `GET /api/v1/me`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `200 OK`:**
```json
{
  "profile": {
    "id": "7f8b9e6a-3c12-4f81-8d99-873b2210a442",
    "firebase_uid": "WvO9ZgM2KjX98aBCDefGhIjKlMn1",
    "email": "guardian@example.com",
    "display_name": "Jane Doe",
    "phone_number": "+1234567890",
    "role": "guardian",
    "is_active": true,
    "created_at": "2026-10-14T05:20:00.000000+00:00"
  },
  "families": [
    {
      "family_id": "b182d3e4-f567-4a89-9cde-f1234567890a",
      "family_name": "Doe Family",
      "role": "owner",
      "created_at": "2026-10-14T05:21:00.000000+00:00"
    }
  ],
  "children": [
    {
      "id": "c293e4f5-a678-4b90-adef-12345678901b",
      "family_id": "b182d3e4-f567-4a89-9cde-f1234567890a",
      "first_name": "Tommy",
      "last_name": "Doe",
      "display_name": "Tommy Doe",
      "gender": "male",
      "sharing_enabled": true,
      "created_at": "2026-10-14T05:22:00.000000+00:00"
    }
  ]
}
```

### Update User Profile
- **Endpoint:** `PATCH /api/v1/me`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Request Body:**
```json
{
  "display_name": "Jane A. Doe",
  "phone_number": "+1987654321"
}
```
- **Response `200 OK`:** Returns updated `UserProfileResponse`.

### Deactivate User Account (Right to be Forgotten)
- **Endpoint:** `DELETE /api/v1/me`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `204 No Content`:** Deactivates user account and invalidates active sessions.

---

## 3. Family & Child Management (`/api/v1/families`)

### Create Family Group
- **Endpoint:** `POST /api/v1/families`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Request Body:**
```json
{
  "name": "Doe Family"
}
```
- **Response `201 Created`:**
```json
{
  "family_id": "b182d3e4-f567-4a89-9cde-f1234567890a",
  "family_name": "Doe Family",
  "role": "owner",
  "created_at": "2026-10-14T05:21:00.000000+00:00"
}
```

### Create Child Profile in Family
- **Endpoint:** `POST /api/v1/families/{family_id}/children`
- **Authentication:** `Bearer <Firebase_ID_Token>` (Caller must be `owner` or `guardian` of `{family_id}`)
- **Request Body:**
```json
{
  "first_name": "Tommy",
  "last_name": "Doe",
  "display_name": "Tommy Doe",
  "gender": "male",
  "sharing_enabled": true
}
```
- **Response `201 Created`:** Returns `ChildSummaryItem`.

### Update Child Profile Settings
- **Endpoint:** `PATCH /api/v1/families/{family_id}/children/{child_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Request Body:**
```json
{
  "display_name": "Tommy D.",
  "sharing_enabled": true,
  "location_interval_moving": 30,
  "location_interval_stationary": 120
}
```
- **Response `200 OK`:** Returns updated `ChildSummaryItem`.

### Delete Child Profile (Right to be Forgotten)
- **Endpoint:** `DELETE /api/v1/families/{family_id}/children/{child_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>` (Caller must be `owner` or `guardian` of `{family_id}`)
- **Response `204 No Content`:** Permanently purges child profile and cascades deletion to all GPS history, latest location, paired devices, commands, and safety events.

---


## 4. Device Pairing (`/api/v1/pairing`)

### Generate Single-Use Pairing Code (Guardian)
- **Endpoint:** `POST /api/v1/pairing/create`
- **Authentication:** `Bearer <Firebase_ID_Token>` (Guardian must own child's family)
- **Rate Limit:** 20 requests / minute
- **Request Body:**
```json
{
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b"
}
```
- **Response `201 Created`:**
```json
{
  "pairing_code": "K7M9P2",
  "expires_at": "2026-10-14T05:35:00.000000+00:00",
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b"
}
```
*Note: The raw code is returned only once in this response and is stored exclusively as an HMAC-SHA256 hash.*

### Redeem Pairing Code (Child Device)
- **Endpoint:** `POST /api/v1/pairing/claim`
- **Authentication:** None (Device onboarding step)
- **Rate Limit:** 10 requests / minute
- **Request Body:**
```json
{
  "pairing_code": "K7M9P2",
  "device_identifier": "android-hw-uuid-882371",
  "device_model": "Pixel 8",
  "os_version": "Android 14",
  "app_version": "1.0.0",
  "fcm_token": "fcm_token_device_abc123"
}
```
- **Response `200 OK`:**
```json
{
  "status": "paired",
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "family_id": "b182d3e4-f567-4a89-9cde-f1234567890a",
  "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
  "paired_at": "2026-10-14T05:25:00.000000+00:00"
}
```

### Get Pairing Status (Guardian)
- **Endpoint:** `GET /api/v1/pairing/status/{child_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `200 OK`:**
```json
{
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "has_active_device": true,
  "devices": [
    {
      "id": "d394f5a6-b789-4c01-bdef-23456789012c",
      "device_identifier": "android-hw-uuid-882371",
      "device_model": "Pixel 8",
      "os_version": "Android 14",
      "battery_percent": null,
      "location_permission_state": "granted_always",
      "is_active": true,
      "last_seen_at": "2026-10-14T05:25:00.000000+00:00",
      "created_at": "2026-10-14T05:25:00.000000+00:00"
    }
  ]
}
```

### Revoke Device Association (Guardian)
- **Endpoint:** `DELETE /api/v1/pairing/revoke/{child_id}/devices/{device_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `204 No Content`**

---

## 5. Location Tracking (`/api/v1/children`)

### Ingest Child Location Point
- **Endpoint:** `POST /api/v1/children/{child_id}/locations`
- **Authentication:** `X-Device-Identifier: <device_hardware_uuid>` OR `Bearer <Firebase_ID_Token>`
- **Rate Limit:** 120 requests / minute
- **Request Body:**
```json
{
  "latitude": 12.9716,
  "longitude": 77.5946,
  "accuracy_m": 8.5,
  "speed_mps": 1.2,
  "bearing_deg": 180.0,
  "altitude_m": 920.0,
  "captured_at": "2026-10-14T05:30:00.000000+00:00"
}
```
- **Validation Rules:**
  - `latitude`: `[-90.0, 90.0]`
  - `longitude`: `[-180.0, 180.0]`
  - `accuracy_m`: `>= 0.0`
  - `speed_mps`: `>= 0.0`
  - `bearing_deg`: `[0.0, 360.0]`
  - `captured_at`: Must not exceed 5 minutes in the future; must not exceed 30-day retention window.
  - S-045 Duplicate handling: Duplicate points (same child + timestamp) return `status="duplicate"` and existing record without database bloat.
  - S-045 Out-of-order handling: Older historical points are appended to `LocationRecord` history, but `LatestLocation` snapshot is never regressed.
- **Response `201 Created`:**
```json
{
  "status": "success",
  "record_id": "e405a6b7-c890-4d12-bdef-34567890123d",
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
  "captured_at": "2026-10-14T05:30:00.000000+00:00",
  "received_at": "2026-10-14T05:30:01.200000+00:00",
  "freshness_status": "LIVE",
  "is_latest": true
}
```

### Get Child Latest Location (Guardian)
- **Endpoint:** `GET /api/v1/children/{child_id}/location/latest`
- **Authentication:** `Bearer <Firebase_ID_Token>` (Guardian must belong to child's family)
- **Response `200 OK` (Live/Fresh/Stale):**
```json
{
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "freshness_status": "LIVE",
  "sharing_enabled": true,
  "location": {
    "id": "f516b7c8-d901-4e23-cdef-45678901234e",
    "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
    "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "accuracy_m": 8.5,
    "speed_mps": 1.2,
    "bearing_deg": 180.0,
    "altitude_m": 920.0,
    "captured_at": "2026-10-14T05:30:00.000000+00:00",
    "received_at": "2026-10-14T05:30:01.200000+00:00",
    "freshness_status": "LIVE",
    "age_seconds": 12.4
  },
  "retrieved_at": "2026-10-14T05:30:12.400000+00:00"
}
```
- **Freshness States:**
  - `LIVE`: Captured within the last 60 seconds.
  - `FRESH`: Captured within `location_stale_minutes` (default 15 minutes).
  - `STALE`: Captured more than 15 minutes ago.
  - `NOT_REPORTING`: No location point exists, or `sharing_enabled` is false.

### Get Paginated Location History (Guardian)
- **Endpoint:** `GET /api/v1/children/{child_id}/locations`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Query Parameters:**
  - `limit`: `int` (1–200, default 50)
  - `offset`: `int` (default 0)
  - `start_time`: `ISO-8601 UTC datetime` (Bounded by 30-day retention cutoff)
  - `end_time`: `ISO-8601 UTC datetime`
- **Response `200 OK`:**
```json
{
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "total": 1420,
  "limit": 50,
  "offset": 0,
  "retention_days": 30,
  "retention_cutoff": "2026-09-14T05:30:00.000000+00:00",
  "items": [
    {
      "id": "e405a6b7-c890-4d12-bdef-34567890123d",
      "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
      "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
      "latitude": 12.9716,
      "longitude": 77.5946,
      "accuracy_m": 8.5,
      "speed_mps": 1.2,
      "bearing_deg": 180.0,
      "altitude_m": 920.0,
      "captured_at": "2026-10-14T05:30:00.000000+00:00",
      "received_at": "2026-10-14T05:30:01.200000+00:00",
      "freshness_status": null,
      "age_seconds": 12.4
    }
  ]
}
```

---

## 6. Device Status & Telemetry (`/api/v1/children/{child_id}/status`)

### Submit Device Telemetry / Heartbeat
- **Endpoint:** `POST /api/v1/children/{child_id}/status`
- **Authentication:** `X-Device-Identifier: <device_hardware_uuid>` OR `Bearer <Firebase_ID_Token>`
- **Rate Limit:** 120 requests / minute
- **Request Body:**
```json
{
  "battery_percent": 88,
  "is_charging": true,
  "network_type": "WIFI",
  "location_permission_state": "granted_always",
  "storage_free_mb": 12400,
  "is_gps_enabled": true,
  "observed_at": "2026-10-14T05:29:45.000000+00:00"
}
```
- **Response `201 Created`:**
```json
{
  "status": "recorded",
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
  "received_at": "2026-10-14T05:29:46.100000+00:00"
}
```

### Get Child Device Status (Guardian)
- **Endpoint:** `GET /api/v1/children/{child_id}/status`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `200 OK`:**
```json
{
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "sharing_enabled": true,
  "devices": [
    {
      "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
      "device_identifier": "android-hw-uuid-882371",
      "device_model": "Pixel 8",
      "battery_percent": 88,
      "is_charging": true,
      "network_type": "WIFI",
      "location_permission_state": "granted_always",
      "is_gps_enabled": true,
      "is_online": true,
      "last_seen_at": "2026-10-14T05:29:46.100000+00:00"
    }
  ],
  "retrieved_at": "2026-10-14T05:30:00.000000+00:00"
}
```

---

## 7. Remote Commands (`/api/v1/children/{child_id}/commands`, `/api/v1/commands`)

### Issue Remote Command (Guardian)
- **Endpoint:** `POST /api/v1/children/{child_id}/commands`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Allowed Command Types:**
  - `SAFETY_CHECK`
  - `REQUEST_LOCATION_REFRESH`
  - `SYNC_POLICIES`
  - `DEVICE_STATUS_CHECK`
  - `ENABLE_APP_SAFETY_MODE`
  - `RELEASE_APP_SAFETY_MODE`
- **Request Body:**
```json
{
  "command_type": "SAFETY_CHECK",
  "payload": {
    "reason": "Routine evening check"
  },
  "expiry_seconds": 300
}
```
- **Lifecycle & Durability:**
  - Command is committed to PostgreSQL **before** triggering any FCM push signal.
  - If FCM push succeeds, status transitions to `SIGNAL_SENT`.
  - If FCM fails or device is offline, status remains `PENDING` without rolling back the command.
  - Real-time `command_created` event is broadcast to connected WebSocket subscribers.
- **Response `201 Created`:**
```json
{
  "id": "a1b2c3d4-e5f6-7a89-b012-34567890123a",
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "target_device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
  "issued_by_user_id": "7f8b9e6a-3c12-4f81-8d99-873b2210a442",
  "command_type": "SAFETY_CHECK",
  "payload": {
    "reason": "Routine evening check"
  },
  "status": "SIGNAL_SENT",
  "fcm_message_id": "projects/smart-child-safty-firebase/messages/0:1728900000",
  "signal_sent_at": "2026-10-14T05:31:00.000000+00:00",
  "expires_at": "2026-10-14T05:36:00.000000+00:00",
  "created_at": "2026-10-14T05:31:00.000000+00:00",
  "updated_at": "2026-10-14T05:31:00.000000+00:00"
}
```

### Sync Pending Commands (Child Device)
- **Endpoint:** `GET /api/v1/children/{child_id}/commands/pending`
- **Authentication:** `X-Device-Identifier: <device_hardware_uuid>` OR `Bearer <Firebase_ID_Token>`
- **Behavior:** Reconciles expired commands (`expires_at < now`) to `EXPIRED` status automatically. Returns only active `PENDING` and `SIGNAL_SENT` commands.
- **Response `200 OK`:**
```json
{
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "count": 1,
  "commands": [
    {
      "id": "a1b2c3d4-e5f6-7a89-b012-34567890123a",
      "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
      "target_device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
      "issued_by_user_id": "7f8b9e6a-3c12-4f81-8d99-873b2210a442",
      "command_type": "SAFETY_CHECK",
      "payload": {
        "reason": "Routine evening check"
      },
      "status": "SIGNAL_SENT",
      "expires_at": "2026-10-14T05:36:00.000000+00:00",
      "created_at": "2026-10-14T05:31:00.000000+00:00",
      "updated_at": "2026-10-14T05:31:00.000000+00:00"
    }
  ]
}
```

### Acknowledge Command Execution (Child Device)
- **Endpoint:** `POST /api/v1/commands/{command_id}/ack` (alias: `POST /api/v1/commands/{command_id}/response`)
- **Authentication:** `X-Device-Identifier: <device_hardware_uuid>` OR `Bearer <Firebase_ID_Token>`
- **Request Body:**
```json
{
  "status": "EXECUTED",
  "execution_result": "Child confirmed safety check prompt",
  "error_message": null,
  "acknowledged_at": "2026-10-14T05:32:00.000000+00:00"
}
```
- **Response `200 OK`:**
```json
{
  "status": "recorded",
  "command_id": "a1b2c3d4-e5f6-7a89-b012-34567890123a",
  "device_id": "d394f5a6-b789-4c01-bdef-23456789012c",
  "command_status": "EXECUTED",
  "acknowledged_at": "2026-10-14T05:32:00.000000+00:00",
  "received_at": "2026-10-14T05:32:01.000000+00:00"
}
```

### Get Command History (Guardian)
- **Endpoint:** `GET /api/v1/children/{child_id}/commands`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Query Parameters:** `limit` (default 50), `offset` (default 0), `status` (optional filter)
- **Response `200 OK`:** Returns `CommandHistoryResponse`.

---

## 8. Real-Time WebSockets (`/api/v1/ws`)

### Guardian Real-Time Stream
- **Endpoint:** `WS /api/v1/ws?token=<Firebase_ID_Token>`
- **Handshake Protocol:**
  - Token can be passed as query parameter `?token=<token>` or sent as first message `{"action": "authenticate", "token": "<token>"}`.
  - Invalid credentials immediately terminate connection with close code `1008` (Policy Violation).
- **Client Actions:**
  - **Subscribe to Child:**
    ```json
    {"action": "subscribe", "child_id": "c293e4f5-a678-4b90-adef-12345678901b"}
    ```
    - Server verifies active guardian-child relationship in database.
    - Response on success: `{"event": "subscribed", "child_id": "...", "status": "ok"}`.
    - Response on failure: `{"event": "error", "child_id": "...", "detail": "Unauthorized subscription: access denied"}`.
  - **Unsubscribe:**
    ```json
    {"action": "unsubscribe", "child_id": "c293e4f5-a678-4b90-adef-12345678901b"}
    ```
  - **Keep-Alive Ping:**
    ```json
    {"action": "ping"}
    ```
    Response: `{"event": "pong"}`.
- **Server Broadcast Events:**
  - `command_created`: Sent when an authorized guardian creates a remote command.
  - `command_status_changed`: Sent when a child device acknowledges or completes command execution.
  - `location_update`: Sent when a new GPS point is ingested for a subscribed child.
  - `zone_transition`: Sent when a child crosses a circular safe/danger/restricted zone boundary (`ZONE_ENTRY` / `ZONE_EXIT`).
  - `sos_alert`: High-priority alert sent immediately when an emergency SOS button is activated.
  - `event_acknowledged`: Sent when a guardian marks an auditable event or SOS alert as acknowledged.

---

## 9. Safe Zones (`/api/v1/children/{child_id}/safe-zones` & `/api/v1/safe-zones`)

### Create Safe Zone (Guardian)
- **Endpoint:** `POST /api/v1/children/{child_id}/safe-zones`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Request Body:**
```json
{
  "name": "Home Safe Zone",
  "zone_type": "SAFE",
  "center_latitude": 37.7749,
  "center_longitude": -122.4194,
  "radius_meters": 250.0,
  "is_active": true
}
```
- **Validation Rules:**
  - `center_latitude`: `[-90.0, 90.0]`
  - `center_longitude`: `[-180.0, 180.0]`
  - `radius_meters`: `[10.0, 50000.0]` (10m minimum to 50km maximum)
  - `zone_type`: `SAFE`, `RESTRICTED`, or `DANGER`
- **Response `201 Created`:** Returns `SafeZoneResponse`.

### List Safe Zones for Child (Guardian)
- **Endpoint:** `GET /api/v1/children/{child_id}/safe-zones`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Query Parameters:** `include_inactive` (boolean, default false)
- **Response `200 OK`:** Returns array of `SafeZoneResponse` (includes child-specific and family-wide active zones).

### Get Safe Zone by ID (Guardian)
- **Endpoint:** `GET /api/v1/safe-zones/{zone_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `200 OK`:** Returns `SafeZoneResponse`.

### Update Safe Zone (Guardian)
- **Endpoint:** `PATCH /api/v1/safe-zones/{zone_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Request Body:** Partial update fields (`name`, `zone_type`, `center_latitude`, `center_longitude`, `radius_meters`, `is_active`).
- **Response `200 OK`:** Returns updated `SafeZoneResponse`.

### Delete Safe Zone (Guardian)
- **Endpoint:** `DELETE /api/v1/safe-zones/{zone_id}`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Response `204 No Content`:** Deletes safe zone; historical `SafetyEvent` records preserve history with `zone_id` set to `NULL`.

---

## 10. Emergency SOS & Auditable Safety Events

### Trigger Emergency SOS (Child Device or Guardian)
- **Endpoint:** `POST /api/v1/children/{child_id}/sos`
- **Authentication:** `X-Device-Identifier: <device_hardware_uuid>` OR `Bearer <Firebase_ID_Token>`
- **Request Body:**
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194,
  "accuracy_m": 8.5,
  "message": "Emergency SOS triggered from lock screen widget",
  "triggered_at": "2026-10-14T05:35:00.000000+00:00"
}
```
- **Behavior:**
  - Persists `SafetyEvent` with `event_type="SOS"` and `severity="CRITICAL"` durably before notification attempts.
  - S-060 Duplicate Suppression: Rapid repeated SOS presses within a 60-second cooldown window are suppressed and return `status="duplicate_suppressed"` to prevent alert storms.
  - Notification Delivery: Attempts push notification via FCM and broadcasts real-time `sos_alert` over authenticated WebSockets.
  - Honest Status Tracking: Returns `notification_status="attempted"`.
- **Response `201 Created`:**
```json
{
  "status": "persisted",
  "event_id": "b1c2d3e4-f5a6-7b89-c012-45678901234b",
  "child_profile_id": "c293e4f5-a678-4b90-adef-12345678901b",
  "family_id": "f1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c",
  "severity": "CRITICAL",
  "notification_status": "attempted",
  "triggered_at": "2026-10-14T05:35:00.000000+00:00",
  "received_at": "2026-10-14T05:35:00.500000+00:00"
}
```

### List Safety Events for Child (Guardian)
- **Endpoint:** `GET /api/v1/children/{child_id}/events`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Query Parameters:**
  - `limit`: Page limit (1-100, default 50)
  - `offset`: Page offset (default 0)
  - `event_type`: Optional filter (`SOS`, `ZONE_ENTRY`, `ZONE_EXIT`)
  - `severity`: Optional filter (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
  - `is_acknowledged`: Optional filter (`true`, `false`)
- **Response `200 OK`:** Returns `SafetyEventListResponse`.

### Acknowledge Safety Event (Guardian)
- **Endpoint:** `POST /api/v1/events/{event_id}/ack`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Behavior:** Marks event `is_acknowledged=true`, sets `acknowledged_by_user_id` and `acknowledged_at`, and broadcasts `event_acknowledged` over WebSockets.
- **Response `200 OK`:**
```json
{
  "status": "acknowledged",
  "event_id": "b1c2d3e4-f5a6-7b89-c012-45678901234b",
  "acknowledged_by_user_id": "u182c3d4-e5f6-7a89-0b1c-def123456789",
  "acknowledged_at": "2026-10-14T05:36:10.000000+00:00"
}
```

---

## 11. Maintenance & Data Retention (`/api/v1/maintenance`)

### Execute Data Retention Cleanup
- **Endpoint:** `POST /api/v1/maintenance/retention/cleanup`
- **Authentication:** `Bearer <Firebase_ID_Token>`
- **Query Parameters:** `retention_days` (integer, optional override 1-365)
- **Behavior:**
  - Prunes location records older than retention threshold (default 30 days).
  - Prunes device heartbeats older than retention threshold.
  - Prunes expired unredeemed pairing codes.
  - Prunes expired/completed device commands older than 30 days.
  - Returns audit metrics summary.
- **Response `200 OK`:**
```json
{
  "status": "success",
  "retention_days": 30,
  "pruned_location_records": 1250,
  "pruned_heartbeats": 340,
  "pruned_pairing_codes": 12,
  "pruned_commands": 45,
  "executed_at": "2026-10-14T05:40:00.000000+00:00"
}
```


