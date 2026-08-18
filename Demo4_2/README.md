# Key Dynamics: AI-Powered Keystroke Dynamics Authentication System

A production-quality demonstration web application that integrates **Machine Learning** and **Behavioral Biometrics** to protect corporate login systems against credential theft, automated bots, and credential stuffing attacks.

Instead of asking users for standard fingerprints or physical keys, Key Dynamics introduces an **invisible second authentication layer** that analyzes *how* the user types their password. The keystroke rhythm forms a behavioral signature, and a personalized scikit-learn classifier checks if the person typing is the legitimate account owner.

---

## 🛡️ Core Cybersecurity Protections

*   **Behavioral Biometrics**: Extracts timing patterns (Key Hold Duration, Key Flight intervals, and Digraph/Trigraph latencies) unique to human muscle memory.
*   **Credential Stuffing Block (Paste Detection)**: Clipboard injections are flagged instantly by detecting zero flight times ($FT = 0.0$ms) between inputs.
*   **Automated Bot Block**: Robotic typing scripts are rejected by measuring uniform key intervals (timing standard deviation = 0.0).
*   **Brute Force Protections**: Locks accounts for 15 minutes after 5 consecutive incorrect attempts to block dictionary attacks.
*   **Adaptive MFA (Step-Up)**: Triggers a secondary 6-digit OTP challenge only if the user types with minor variation (Medium Risk, 35-70% score), preventing friction for normal logins.
*   **OWASP Compliance**: Secure bcrypt password hashing, input validations using Pydantic, Helmet-equivalent CORS/security headers, JWT session verification, and timing attack protections on queries.

---

## 📂 Project Structure

```text
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI REST API & Middlewares
│   │   ├── auth.py            # Bcrypt, JWT, Lockout policies
│   │   ├── ml.py              # Keystroke parsing, training & evaluation
│   │   ├── risk_engine.py     # Anomaly scoring & Risk assessment
│   │   ├── database.py        # SQLAlchemy session initialization
│   │   ├── models.py          # SQLAlchemy tables schema (User, KeystrokeSample, AuthLog)
│   │   ├── schemas.py         # Input/Output Pydantic structures
│   │   ├── config.py          # JWT, Database, & Risk thresholds settings
│   │   └── seed_data.py       # Seed script for mock users & historical analytics
│   ├── tests/
│   │   └── test_ml.py         # Automated pytest test suite
│   ├── Dockerfile             # Python container configuration
│   └── requirements.txt       # Backend dependencies list
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx     # Next.js Server layout
│   │   │   ├── globals.css    # Custom dark cyber-defense CSS layout
│   │   │   ├── client-layout.tsx # Client-side auth navigation header
│   │   │   ├── page.tsx       # Landing page (conceptual overview)
│   │   │   ├── register/      # 10-trial biometrics enrollment wizard
│   │   │   ├── login/         # Secure biometrics login portal + OTP modal
│   │   │   └── simulations/   # Interactive Cyberattack Simulator
│   │   ├── hooks/
│   │   │   └── useKeystrokeCapture.ts # Backspace-filtering timing stack capture hook
│   ├── Dockerfile             # Node.js Alpine container configuration
│   └── package.json           # Frontend packages list
│
├── docs/
│   ├── design_and_architecture.md    # DFDs, Flowcharts, ER, Sequence & API Docs
│   └── installation_and_testing.md  # Step-by-step setup guides & verification paths
│
└── docker-compose.yml         # Container orchestrator stack
```

---

## ⚡ Quick Start

### Option A: Running Locally (Recommended)

#### 1. Start the Backend API
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
python app/seed_data.py          # Seeds SQLite DB with default profiles & audit history
uvicorn app.main:app --reload --port 8080
```
*API documentation will be running at [http://localhost:8080/docs](http://localhost:8080/docs).*

#### 2. Start the Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```
*The web portal will be running at [http://localhost:3000](http://localhost:3000).*

### Option B: Running with Docker Compose
Ensure you have Docker and Docker Compose installed, then execute:
```bash
docker-compose up --build
```

---

## 🔑 Default Seeded Accounts

The database seeding command creates three pre-configured accounts with extensive login logs:

1.  **Administrator Portal**:
    *   **Email**: `admin@banking.com`
    *   **Password**: `AdminPassword123`
    *   **Role**: `admin`
2.  **Standard User 1**:
    *   **Email**: `john@banking.com`
    *   **Password**: `SecureJohn99`
    *   **Role**: `user`
3.  **Standard User 2**:
    *   **Email**: `jane@banking.com`
    *   **Password**: `JaneP@ssword`
    *   **Role**: `user`

---

## 📈 Machine Learning Framework

Aegis Dynamics trains and compares **7 different classification models** dynamically in a cross-validation loop to identify the most accurate timing signature for each user:

1.  **Supervised Algorithms** (Binary classifiers evaluating user vs reference pool):
    *   *Random Forest Classifier*
    *   *Support Vector Machine (SVC with RBF kernel)*
    *   *K-Nearest Neighbors (KNN)*
    *   *Multi-Layer Perceptron (MLP Neural Network)*
    *   *Gradient Boosting (HistGradientBoostingClassifier)*
2.  **Unsupervised Algorithms** (One-class anomaly models trained only on user baseline):
    *   *One-Class SVM*
    *   *Isolation Forest*

Admins can inspect accuracy comparisons, False Acceptance Rates (FAR), False Rejection Rates (FRR), and interactive Confusion Matrices for these models on the **Admin Operations Dashboard**.

---

## 📚 Detailed Documentation

*   For architectural specs, DFDs, ER, Flowcharts, Use Cases, Sequence diagrams, and REST APIs, see **[design_and_architecture.md](file:///Users/adrianphilipdsouza/Developer/Demo4/docs/design_and_architecture.md)**.
*   For developer setup guides, automated test scripts, and verification instructions, see **[installation_and_testing.md](file:///Users/adrianphilipdsouza/Developer/Demo4/docs/installation_and_testing.md)**.
