# Architecture and System Data Flow

## 1. Overview
The backend server is the central authority for the Smart Child Monitoring and Safety System. It coordinates data and commands between two distinct native Android applications:
1. **Parent Application (Guardian):** Monitors child locations, sets geofences/policies, reviews safety events, and issues remote commands.
2. **Child Application (Monitored Device):** Periodically captures and uploads GPS coordinates, reports battery/connectivity telemetry, syncs pending commands, and submits SOS alerts.

## 2. Component Flow Diagram
```
+--------------------------+       HTTPS / REST        +-----------------------------------+
|  Parent Android App      | <=======================> |                                   |
|  (Guardian)              |       Authorized WSS      |                                   |
|                          | <------------------------ |       FastAPI Backend Server      |
+--------------------------+                           |                                   |
                                                       |   - AuthN/AuthZ Engine            |
+--------------------------+       HTTPS / REST        |   - Geofencing & Risk Engine      |
|  Child Android App       | <=======================> |   - Command Manager               |
|  (Monitored Device)      |                           |   - WebSocket Hub                 |
+--------------------------+                           |                                   |
             ^                                         +-----------------------------------+
             |                                              |                  |
             |  FCM Notification Signal                     |                  |
             |  (Wakeup / Sync Command)                     v                  v
     [Firebase Cloud Messaging] <---------------------+  [PostgreSQL]    [Firebase Auth]
```

## 3. Core Principles
- **PostgreSQL is Source of Truth:** All commands, locations, zones, and events are stored durably in PostgreSQL before any notification or live push is attempted.
- **FCM is a Signal Only:** FCM delivers a lightweight nudge ("sync pending commands"). The child device pulls the persisted command and verifies its authenticity.
- **Explainable Decisions:** Safety events and risk scores are transparently calculated using verifiable geographical formulas (Haversine formula, velocity estimation, GPS accuracy boundaries).
