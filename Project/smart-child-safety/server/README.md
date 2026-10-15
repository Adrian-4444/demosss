# Smart Child Monitoring and Safety System — Backend Server

Backend server for the MCA Major Project: **Smart Child Monitoring and Safety System Using Context-Aware Geofencing and Remote Device Enforcement**.

Built with **FastAPI**, **PostgreSQL** (Neon managed PostgreSQL target), **SQLAlchemy 2.x**, **Alembic**, **Firebase Cloud Messaging (FCM)**, and **WebSockets**.

---

## 1. System Overview

This repository contains **only the backend server**. The server acts as the trusted authority and source of truth for:
- Guardian authentication and account management (via Firebase Authentication ID tokens).
- Expiring, single-use parent-child pairing invitations with hashed storage.
- Child GPS location ingestion, staleness tracking, and paginated history.
- Context-aware geofencing (safe and restricted zones) and explainable safety event generation.
- Durable remote device commands (e.g., location refresh, safety mode) signaled via FCM.
- Authenticated, scoped WebSocket live updates to connected parent applications.

---

## 2. Technology Stack

- **Runtime:** Python 3.12+ (tested on Python 3.14 on macOS Apple Silicon M4)
- **Framework:** FastAPI
- **Data Validation & Settings:** Pydantic v2 & Pydantic Settings
- **Database & ORM:** PostgreSQL / SQLite (for tests) with SQLAlchemy 2.x
- **Database Migrations:** Alembic
- **PostgreSQL Driver:** `psycopg[binary]>=3.2`
- **Testing:** Pytest & HTTPX / Starlette TestClient
- **Containerization:** Docker (multi-platform slim build)
- **Deployment Target:** Render Web Service + Neon PostgreSQL

---

## 3. Directory Layout

```text
smart-child-safety/
└── server/
    ├── app/
    │   ├── main.py            # FastAPI entry point, CORS, logging & middlewares
    │   ├── config.py          # Pydantic Settings & typed environment config
    │   ├── database.py        # SQLAlchemy engine, session lifecycle & readiness check
    │   ├── security.py        # Principal models, token verification & pairing hasher
    │   ├── models/            # SQLAlchemy declarative models
    │   ├── schemas/           # Pydantic request & response schemas
    │   ├── routers/           # API endpoints (health, auth, location, commands, etc.)
    │   ├── services/          # Business logic, geofencing & risk engine
    │   └── websocket/         # Authorized WebSocket connection manager
    ├── tests/                 # Automated test suite (Pytest & HTTPX)
    ├── alembic/               # Alembic migration scripts and env.py
    ├── alembic.ini            # Alembic configuration
    ├── requirements.txt       # Version-constrained dependencies
    ├── Dockerfile             # Production multi-stage / non-root Dockerfile
    ├── .dockerignore          # Docker build exclusions
    ├── .gitignore             # Git exclusions for secrets, venvs, and caches
    ├── .env.example           # Environment template with placeholder values
    ├── render.yaml            # Render Blueprint for automated deployment
    └── README.md              # Project documentation and guide
```

---

## 4. Local Setup & Installation

### Prerequisites
- Python 3.12 or compatible Python 3.14 installation.
- Git.

### 1. Create and Activate Virtual Environment
```bash
cd smart-child-safety/server
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure your local or test database connection. By default, local testing falls back to SQLite (`sqlite:///./test.db`).

---

## 5. Running the Server Locally

Start the local development server with auto-reload:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Once started:
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Liveness Probe:** `GET http://127.0.0.1:8000/health`
- **Readiness Probe:** `GET http://127.0.0.1:8000/ready`

---

## 6. Running Automated Tests

Run the complete test suite with Pytest:
```bash
pytest -v
```

All tests execute against isolated in-memory or temporary databases. Production databases are never touched during test execution.

---

## 7. Database Migrations (Alembic)

To run pending migrations:
```bash
alembic upgrade head
```

To generate a new migration after model changes:
```bash
alembic revision --autogenerate -m "describe_change"
```

To rollback the last migration:
```bash
alembic downgrade -1
```

---

## 8. Deployment to Render

The repository includes a ready-to-use `render.yaml` blueprint.

### Deployment Steps:
1. Push the repository to GitHub.
2. In the Render Dashboard, create a **New Blueprint Instance** and connect the repository.
3. Render will provision:
   - A managed PostgreSQL database (`smart-child-safety-db`).
   - A web service running the FastAPI application (`smart-child-safety-backend`).
4. Set required secret environment variables in the Render dashboard:
   - `FIREBASE_PROJECT_ID`: Your Firebase project ID.
   - `FIREBASE_CREDENTIALS_JSON`: The JSON content of your Firebase service account key.
   - `CORS_ORIGINS`: Allowed parent/child app web origins.
5. Render runs the health check at `/health`.

---

## 9. Security & Privacy Rules

- **Zero Client Trust:** Identity is derived exclusively from verified Firebase ID tokens; client-provided UIDs are never trusted.
- **Pairing Protection:** Pairing codes are hashed using SHA-256 HMAC before persistence, single-use, and rate-limited.
- **Privacy-Safe Logs:** Authorization headers, bearer tokens, passwords, and raw coordinates are never written to server logs.
- **No Committed Secrets:** Private keys, Firebase credentials, and `.env` files are excluded via `.gitignore` and `.dockerignore`.
