# Design & Architecture: AI-Powered Keystroke Dynamics Authentication System

This document outlines the architecture, database schemas, flowcharts, data flow diagrams (DFDs), use cases, sequence paths, and API documentation for the biometrics security system.

---

## 1. System Architecture Diagram

The application implements a decoupled, modern multi-tier architecture, utilizing a React Next.js frontend, a Python FastAPI REST API backend, and an SQLite database layer accessed through SQLAlchemy.

```mermaid
graph TD
    subgraph Frontend (React Next.js Layer)
        Client[Client Web Browser]
        Capture[JS Timing Capture Engine]
        DashUI[Admin / User Dashboard Visuals]
        Sim[Attack Simulator UI]
    end

    subgraph API Gateway / Middleware
        CORS[CORS Policy Handler]
        Rate[Rate Limiting Shield]
        SecureHeaders[Security Headers Middleware]
    end

    subgraph Backend Core (FastAPI Layer)
        API[FastAPI Controller Router]
        Auth[JWT & Bcrypt Credentials Auth]
        RiskEngine[Adaptive Biometric Risk Engine]
        ML[scikit-learn Analytics Classifier]
        Audit[Secure System Audit Logger]
    end

    subgraph Database Layer (SQLAlchemy ORM)
        DB[(SQLite File-based Database)]
    end

    Client -->|Types Keystrokes| Capture
    Capture -->|JSON Timings Payload| CORS
    CORS --> Rate
    Rate --> SecureHeaders
    SecureHeaders --> API
    API --> Auth
    API --> RiskEngine
    API --> ML
    API --> Audit
    
    Auth --> DB
    ML --> DB
    RiskEngine --> DB
    Audit --> DB
```

---

## 2. Entity-Relationship (ER) Diagram

The system stores user records, biometric timing samples, and access audit logs.

```mermaid
erDiagram
    USERS {
        int id PK "Auto-increment ID"
        string name "User Full Name"
        string email UK "Corporate Email Address"
        string password_hash "Bcrypt Hash Value"
        string role "System Role: user, admin"
        boolean is_locked "Brute force status lock"
        int failed_attempts "Consecutive failed login counter"
        datetime locked_until "Lockout expiration date"
        binary ml_model_blob "Serialized joblib classifier"
        string trained_algorithm "Active algorithm description"
        string baseline_stats "JSON: averages and std dev vectors"
        datetime created_at "Timestamp of enrollment"
    }

    KEYSTROKE_SAMPLES {
        int id PK "Auto-increment ID"
        int user_id FK "Owner reference link"
        string hold_times_json "Holds vector text"
        string flight_times_json "Flights vector text"
        string latencies_json "Latencies vector text"
        float typing_speed "Keys per second"
        int backspace_count "Number of corrections"
        float error_rate "Backspace ratio"
        datetime created_at "Enrollment date"
    }

    AUTH_LOGS {
        int id PK "Auto-increment ID"
        int user_id FK "User reference link"
        datetime timestamp "Time of login request"
        boolean status "Authentication success outcome"
        float similarity_score "Z-score similarity index"
        float confidence_score "AI prediction probability"
        float risk_score "Total assessed risk rate"
        string risk_level "Assessed level: Low, Medium, High"
        string flagged_anomalies "JSON: List of anomalies"
        string user_agent "Client Device footprint"
        string client_ip "Client Network IP Address"
        string simulation_type "Attack simulator label"
    }

    USERS ||--o{ KEYSTROKE_SAMPLES : "enrolls (10)"
    USERS ||--o{ AUTH_LOGS : "logs attempts"
```

---

## 3. Data Flow Diagram (DFD)

### DFD Level 0 (System Context)

```mermaid
graph LR
    User[Client User / Admin]
    System((Aegis Biometrics System))
    Admin[SecOps Admin]

    User -->|Credentials + Typing Dynamics| System
    System -->|Session JWT + Risk Summary| User
    System -->|Global Telemetry & Attack Graphs| Admin
```

### DFD Level 1 (Process Breakdown)

```mermaid
graph TD
    User[Client Browser]
    
    subgraph Processes
        P1[1.0 Validate Password & Lockout]
        P2[2.0 Extract Keystroke Timings]
        P3[3.5 Run AI Prediction]
        P4[4.0 Assess Combined Risk Level]
        P5[5.0 Log Audit Security Trail]
    end

    subgraph Data Stores
        D1[(User Credentials Database)]
        D2[(ML Profiles / Baselines)]
        D3[(Audit Logs Store)]
      end

    User -->|Password credentials| P1
    P1 -->|Query password hash| D1
    
    User -->|Hold/Flight timings| P2
    P2 -->|Query baseline profile| D2
    
    P2 -->|Processed Feature Vector| P3
    P3 -->|Load saved classifier| D2
    
    P3 -->|AI probability prediction| P4
    P2 -->|Z-score similarity rate| P4
    
    P4 -->|Combined score & anomalies| P5
    P5 -->|Insert log record| D3
    
    P4 -->|Auth Status / OTP challenge| User
```

---

## 4. System Flowchart (Biometric Authentication Loop)

```mermaid
flowchart TD
    Start([1. User Submits Email & Password]) --> PasswordCheck{Bcrypt Hash Valid?}
    PasswordCheck -- No --> FailLog[Log Failure + Increment Fail Counters] --> LockoutCheck{Fail Count >= 5?}
    LockoutCheck -- Yes --> LockAccount[Lock Account for 15 mins] --> BlockAccess[Reject Access: Invalid Credentials]
    LockoutCheck -- No --> BlockAccess
    
    PasswordCheck -- Yes --> LoadModel[Retrieve AI Model & Timing Baselines]
    LoadModel --> CheckFingerprint{Check Paste or Bot Signatures?}
    
    CheckFingerprint -- Yes (Paste/Bot) --> FlagHighRisk[Assign Risk = 100%, Set Level = High] --> LogBlock[Log Threat Block + Lockout] --> DenyAccess([Reject Access: Biometrics Blocked])
    
    CheckFingerprint -- No --> ComputeScore[Calculate Z-Score Similarity & Run ML Predict]
    ComputeScore --> CombinedRisk{Assess Risk Level}
    
    CombinedRisk -- Risk <= 35% (Low) --> GrantAccess[Reset Lockout Counters + Issue Session JWT] --> Success([Login Success])
    
    CombinedRisk -- 35% < Risk <= 70% (Medium) --> TriggerOTP[Trigger Step-Up OTP Challenge] --> CheckOTP{OTP Code Correct?}
    CheckOTP -- No --> IncrementFail[Log Failure + Increment Lockout Counters] --> DenyAccess
    CheckOTP -- Yes --> GrantAccess
    
    CombinedRisk -- Risk > 70% (High) --> FlagHighRisk
```

---

## 5. Use Case Diagram

```mermaid
left_to_right_direction
actor User
actor Admin as "SecOps Admin"

rectangle Aegis_Authentication_System {
    User --> (Register Credentials & Type 10 Samples)
    User --> (Secure Biometric Login)
    User --> (Perform Adaptive OTP Step-Up)
    User --> (Inspect Typing Timeline & Speed Heatmap)
    User --> (Simulate Cyberattacks: Paste, Bot, Brute Force)
    
    (Secure Biometric Login) ..> (Evaluate Anomaly & Risk Score) : include
    
    Admin --> (Authenticate Admin Operations Session)
    Admin --> (View Global Real-time Security Log)
    Admin --> (Monitor ML Algorithm Accuracy Comparisons)
}
```

---

## 6. Sequence Diagram (Authentication and Adaptive MFA)

```mermaid
sequenceDiagram
    autonumber
    actor User as Client User
    participant JS as JS Capture Engine
    participant API as FastAPI Gateway
    participant Risk as Biometrics Risk Engine
    participant DB as SQLite DB

    User->>JS: Types email, password & hits login
    JS->>JS: Reconstructs timing stack (removes backspaces)
    JS->>API: HTTP POST /api/auth/login (timings + credentials)
    API->>DB: Query User profile by Email
    DB-->>API: User details, password hash, ML model & baseline
    API->>API: Verify password using bcrypt
    
    alt Password Mismatch
        API->>DB: Log authentication failure
        API-->>User: HTTP 401 Unauthorized (Access Denied)
    else Password Match
        API->>Risk: evaluate_login_biometrics(timings, baseline)
        Risk->>Risk: Check for Paste/Bot signatures
        Risk->>Risk: Run ML Classifier & Z-score similarity calculations
        Risk-->>API: Risk Score = 52.0%, Level = Medium, OTP Code = 123456
        API->>DB: Log AuthLog (MFA Challenge triggered)
        API-->>User: HTTP 200 (MFA_REQUIRED + Temp token + OTP debug code)
        
        User->>User: Renders OTP verification prompt
        User->>API: HTTP POST /api/auth/verify-otp (Code: 123456)
        API->>API: Validate code matches
        API->>DB: Log success, reset failed attempts
        API-->>User: HTTP 200 Success (JWT Session Token)
    end
```

---

## 7. REST API Documentation

### 7.1. User Registration & Enrollment
* **Endpoint**: `POST /api/auth/register`
* **Request Body**:
```json
{
  "name": "John Doe",
  "email": "john@banking.com",
  "password": "SecurePassword123",
  "keystroke_samples": [
    {
      "hold_times": [112.5, 95.0, 120.0, 105.0],
      "flight_times": [140.0, 180.0, 160.0],
      "latencies": [252.5, 275.0, 280.0],
      "typing_speed": 4.8,
      "backspace_count": 0,
      "error_rate": 0.0
    }
    // ... requires exactly 10 timing objects
  ]
}
```
* **Response (HTTP 200)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "role": "user",
  "user": {
    "id": 2,
    "name": "John Doe",
    "email": "john@banking.com",
    "role": "user",
    "created_at": "2026-07-01T20:00:00.000"
  }
}
```

### 7.2. Biometric Login Request
* **Endpoint**: `POST /api/auth/login`
* **Request Body**:
```json
{
  "email": "john@banking.com",
  "password": "SecurePassword123",
  "keystroke_data": {
    "hold_times": [110.0, 92.0, 122.0, 101.0],
    "flight_times": [145.0, 175.0, 165.0],
    "latencies": [255.0, 267.0, 287.0],
    "typing_speed": 4.9,
    "backspace_count": 0,
    "error_rate": 0.0
  },
  "simulation_type": "None"
}
```
* **Response (HTTP 200 - Access Accepted)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "role": "user",
  "user": {
    "id": 2,
    "name": "John Doe",
    "email": "john@banking.com",
    "role": "user"
  }
}
```
* **Response (HTTP 200 - Step-Up MFA Challenge)**:
```json
{
  "status": "MFA_REQUIRED",
  "temp_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "risk_score": 52.0,
  "anomalies": ["Moderate behavioral biometrics mismatch"],
  "otp_debug": "495810"
}
```

### 7.3. Verify Step-Up OTP
* **Endpoint**: `POST /api/auth/verify-otp`
* **Request Body**:
```json
{
  "email": "john@banking.com",
  "otp": "495810"
}
```
* **Response (HTTP 200)**: Same as Access Accepted JWT response.

### 7.4. User Dashboard Timeline Statistics
* **Endpoint**: `GET /api/dashboard/user-stats`
* **Headers**: `Authorization: Bearer <token>`
* **Response (HTTP 200)**:
```json
{
  "total_logins": 42,
  "failed_logins": 2,
  "avg_speed": 4.8,
  "avg_hold": 108.2,
  "avg_similarity": 89.4,
  "history": [
    {
      "id": 104,
      "timestamp": "2026-07-01T20:00:00Z",
      "status": true,
      "similarity_score": 92.5,
      "confidence_score": 96.0,
      "risk_score": 12.0,
      "risk_level": "Low",
      "flagged_anomalies": "[]",
      "simulation_type": "None"
    }
  ]
}
```

### 7.5. Admin Dashboard Global Telemetry
* **Endpoint**: `GET /api/dashboard/admin-stats`
* **Headers**: `Authorization: Bearer <token>`
* **Response (HTTP 200)**:
```json
{
  "total_users": 3,
  "total_attempts": 182,
  "failed_attempts": 32,
  "compromised_prevented": 14,
  "daily_logins": [
    { "date": "2026-06-30", "success": 12, "failed": 2 }
  ],
  "anomalies_distribution": [
    { "name": "Bot Signature", "value": 8 }
  ],
  "recent_attempts": []
}
```
