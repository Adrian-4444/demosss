# Database Design & Entity Architecture

## 1. Engine & Driver Selection
- **ORM:** SQLAlchemy 2.x Declarative Mapping (`Mapped`, `mapped_column`)
- **Database:** PostgreSQL (Production target: Neon Serverless PostgreSQL / Render)
- **Driver:** `psycopg[binary]>=3.2`
- **Testing Engine:** SQLite (with SQLite foreign-keys pragma enforced)
- **Migrations:** Alembic (Revision: `4d9ae306f449`)

## 2. Core Entities (13 Domain Entities + Pairing)

### 1. `user_profiles` (`UserProfile`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `firebase_uid`: `VARCHAR(128)` Unique, Indexed. Source-of-truth identity claim from Firebase.
- `email`: `VARCHAR(255)` Unique, Indexed.
- `display_name`: `VARCHAR(120)` Nullable.
- `phone_number`: `VARCHAR(32)` Nullable.
- `role`: `VARCHAR(32)` Default `'guardian'` (`guardian` | `operator`).
- `is_active`: `BOOLEAN` Default `TRUE`.
- `created_at`, `updated_at`: `TIMESTAMPTZ` UTC.
- `disabled_at`: `TIMESTAMPTZ` Nullable.

### 2. `families` (`Family`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `name`: `VARCHAR(120)` e.g., "Doe Family".
- `created_by_user_id`: `VARCHAR(36)` FK to `user_profiles.id` (`RESTRICT`).
- `created_at`, `updated_at`: `TIMESTAMPTZ` UTC.

### 3. `family_memberships` (`FamilyMembership`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `family_id`: `VARCHAR(36)` FK to `families.id` (`CASCADE`), Indexed.
- `user_id`: `VARCHAR(36)` FK to `user_profiles.id` (`CASCADE`), Indexed.
- `role`: `VARCHAR(32)` Default `'guardian'` (`owner` | `guardian` | `viewer`).
- `created_at`: `TIMESTAMPTZ` UTC.
- **Constraints:** `UniqueConstraint(family_id, user_id)` preventing duplicate memberships.

### 4. `child_profiles` (`ChildProfile`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `family_id`: `VARCHAR(36)` FK to `families.id` (`CASCADE`), Indexed.
- `first_name`, `display_name`: `VARCHAR`
- `last_name`, `gender`: `VARCHAR` Nullable.
- `date_of_birth`: `DATE` Nullable.
- `sharing_enabled`: `BOOLEAN` Default `TRUE`.
- `location_interval_moving`: `INTEGER` Default `30` seconds.
- `location_interval_stationary`: `INTEGER` Default `120` seconds.
- `created_at`, `updated_at`: `TIMESTAMPTZ` UTC.
- `deleted_at`: `TIMESTAMPTZ` Nullable (supports soft-deletion).

### 5. `registered_devices` (`RegisteredDevice`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Indexed.
- `device_identifier`: `VARCHAR(128)` Unique, Indexed. Hardware UUID / Android ID hash.
- `device_model`, `os_version`, `app_version`: `VARCHAR` Nullable.
- `fcm_token`: `TEXT` Nullable. Protected device push token.
- `battery_percent`: `INTEGER` Nullable (0-100).
- `is_charging`: `BOOLEAN` Nullable.
- `location_permission_state`: `VARCHAR(64)` Default `'granted_always'`.
- `is_active`: `BOOLEAN` Default `TRUE`.
- `last_seen_at`: `TIMESTAMPTZ` Nullable.
- `created_at`, `updated_at`: `TIMESTAMPTZ` UTC.

### 6. `latest_locations` (`LatestLocation`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Unique, Indexed (1:1 with `ChildProfile`).
- `device_id`: `VARCHAR(36)` FK to `registered_devices.id` (`SET NULL`), Nullable.
- `latitude`, `longitude`: `FLOAT` Double precision coordinates.
- `accuracy_m`, `speed_mps`, `bearing_deg`, `altitude_m`: `FLOAT` Nullable.
- `captured_at`: `TIMESTAMPTZ` Indexed. Actual GPS fix time on device.
- `received_at`: `TIMESTAMPTZ` Server arrival timestamp.
- `freshness_status`: `VARCHAR(32)` (`LIVE`, `FRESH`, `STALE`, `NOT_REPORTING`).

### 7. `location_records` (`LocationRecord`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Indexed.
- `device_id`: `VARCHAR(36)` FK to `registered_devices.id` (`SET NULL`), Nullable.
- `latitude`, `longitude`, `accuracy_m`, `speed_mps`, `bearing_deg`, `altitude_m`: Coordinates & telemetry.
- `captured_at`, `received_at`: `TIMESTAMPTZ`.
- **Index:** `ix_location_child_captured_desc` on `(child_profile_id, captured_at DESC)` for O(log N) paginated history.

### 8. `safety_zones` (`SafetyZone`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `family_id`: `VARCHAR(36)` FK to `families.id` (`CASCADE`), Indexed.
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Nullable (if null, applies to whole family).
- `name`: `VARCHAR(120)` e.g. "School", "Home", "Restricted Lake".
- `zone_type`: `VARCHAR(32)` (`SAFE`, `RESTRICTED`, `DANGER`).
- `center_latitude`, `center_longitude`: `FLOAT`.
- `radius_meters`: `FLOAT`.
- `is_active`: `BOOLEAN` Default `TRUE`.
- `created_at`, `updated_at`: `TIMESTAMPTZ` UTC.

### 9. `safety_policies` (`SafetyPolicy`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `family_id`: `VARCHAR(36)` FK to `families.id` (`CASCADE`), Indexed.
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Nullable.
- `policy_type`: `VARCHAR(64)` (`GEOFENCE_SCHEDULE`, `APP_USAGE_LIMIT`, `CURFEW`, `SPEED_LIMIT`).
- `name`: `VARCHAR(120)`.
- `configuration`: `JSONB` on PostgreSQL, `JSON` on SQLite.
- `is_active`: `BOOLEAN` Default `TRUE`.

### 10. `safety_events` (`SafetyEvent`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `family_id`: `VARCHAR(36)` FK to `families.id` (`CASCADE`), Indexed.
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Indexed.
- `zone_id`: `VARCHAR(36)` FK to `safety_zones.id` (`SET NULL`), Nullable.
- `policy_id`: `VARCHAR(36)` FK to `safety_policies.id` (`SET NULL`), Nullable.
- `event_type`: `VARCHAR(64)` (`SOS`, `ZONE_ENTRY`, `ZONE_EXIT`, `ZONE_VIOLATION`, `BATTERY_LOW`, `DEVICE_OFFLINE`).
- `severity`: `VARCHAR(32)` (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- `risk_score`: `FLOAT` Nullable (0.0 - 100.0).
- `reason`: `TEXT` Human-readable explanation.
- `metadata_json`: `JSONB` on PostgreSQL, `JSON` on SQLite.
- `is_acknowledged`: `BOOLEAN` Default `FALSE`.
- `acknowledged_by_user_id`: `VARCHAR(36)` FK to `user_profiles.id` (`SET NULL`), Nullable.
- `acknowledged_at`: `TIMESTAMPTZ` Nullable.
- `created_at`: `TIMESTAMPTZ` Indexed.

### 11. `device_commands` (`DeviceCommand`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Indexed.
- `target_device_id`: `VARCHAR(36)` FK to `registered_devices.id` (`SET NULL`), Nullable.
- `issued_by_user_id`: `VARCHAR(36)` FK to `user_profiles.id` (`CASCADE`), Indexed.
- `command_type`: `VARCHAR(64)` (`REQUEST_LOCATION_REFRESH`, `SYNC_POLICIES`, `DEVICE_STATUS_CHECK`, `ENABLE_APP_SAFETY_MODE`, `RELEASE_APP_SAFETY_MODE`).
- `payload`: `JSONB` / `JSON`.
- `status`: `VARCHAR(32)` (`PENDING`, `SIGNAL_SENT`, `ACKNOWLEDGED`, `EXECUTED`, `FAILED`, `EXPIRED`).
- `fcm_message_id`: `VARCHAR(128)` Nullable.
- `signal_sent_at`: `TIMESTAMPTZ` Nullable.
- `expires_at`: `TIMESTAMPTZ` Indexed.
- `created_at`, `updated_at`: `TIMESTAMPTZ` UTC.

### 12. `command_acknowledgements` (`CommandAcknowledgement`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `command_id`: `VARCHAR(36)` FK to `device_commands.id` (`CASCADE`), Unique, Indexed (1:1 with `DeviceCommand`).
- `device_id`: `VARCHAR(36)` FK to `registered_devices.id` (`CASCADE`), Indexed.
- `status`: `VARCHAR(32)` (`ACKNOWLEDGED`, `EXECUTED`, `FAILED`).
- `execution_result`, `error_message`: `TEXT` Nullable.
- `acknowledged_at`, `received_at`: `TIMESTAMPTZ`.

### 13. `device_heartbeats` (`DeviceHeartbeat`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `device_id`: `VARCHAR(36)` FK to `registered_devices.id` (`CASCADE`), Indexed.
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Indexed.
- `battery_percent`: `INTEGER` Nullable.
- `is_charging`: `BOOLEAN` Default `FALSE`.
- `network_type`: `VARCHAR(32)` (`WIFI`, `CELLULAR`, `OFFLINE`).
- `storage_free_mb`: `INTEGER` Nullable.
- `is_gps_enabled`: `BOOLEAN` Default `TRUE`.
- `observed_at`, `received_at`: `TIMESTAMPTZ`.

### 14. `pairing_codes` (`PairingCode`)
- `id`: `VARCHAR(36)` Primary Key (UUID4)
- `family_id`: `VARCHAR(36)` FK to `families.id` (`CASCADE`), Indexed.
- `child_profile_id`: `VARCHAR(36)` FK to `child_profiles.id` (`CASCADE`), Indexed.
- `created_by_user_id`: `VARCHAR(36)` FK to `user_profiles.id` (`CASCADE`), Indexed.
- `code_hash`: `VARCHAR(128)` Indexed (HMAC-SHA256).
- `attempts_count`: `INTEGER` Default `0`.
- `is_claimed`: `BOOLEAN` Default `FALSE`.
- `claimed_by_device_id`: `VARCHAR(36)` FK to `registered_devices.id` (`SET NULL`), Nullable.
- `expires_at`: `TIMESTAMPTZ` Indexed.
- `created_at`, `claimed_at`: `TIMESTAMPTZ`.

---

## 3. Data Integrity & Migration Strategy
- Primary keys use standard 36-character UUID strings, preventing enumeration attacks and providing universal compatibility across PostgreSQL, Neon, and SQLite.
- Foreign key cascading is enforced: deleting a `ChildProfile` automatically cascades to remove its devices, locations, safety events, commands, heartbeats, and pairing codes.
- Migrations are managed strictly via Alembic revisions. The active head revision is `4d9ae306f449`.
