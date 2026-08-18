# Installation & Testing Manual

This document details how to install, configure, test, and run the **AI-Powered Keystroke Dynamics Authentication System** web application.

---

## 1. Local Environment Installation

### 1.1. Backend Setup (Python FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create the Python virtual environment (if not already done):
   ```bash
   python3 -m venv .venv
   ```
3. Activate the virtual environment:
   - On macOS/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - On Windows (Command Prompt):
     ```cmd
     .venv\Scripts\activate.bat
     ```
4. Install all Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Pre-seed the database with mock records, user metrics, and ML models:
   ```bash
   python app/seed_data.py
   ```
6. Start the backend development server using Uvicorn:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```
   The backend API will now be listening at `http://localhost:8080` with interactive Swagger docs accessible at `http://localhost:8080/docs`.

### 1.2. Frontend Setup (Next.js & React)

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the Next.js dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The frontend application will now be running at `http://localhost:3000`.

---

## 2. Automated Test Suite

We will configure automated tests in `backend/tests/test_ml.py` to verify our biometrics model training pipeline and risk evaluations.

To run the automated tests:
1. Ensure your backend virtual environment is active.
2. Execute the test command:
   ```bash
   pytest backend/tests/
   ```

---

## 3. Manual Biometrics Verification Guide

Follow these steps to manually experience the keystroke biometrics:

### 3.1. Enrollment (Creating Your Typing Signature)
1. Navigate to `http://localhost:3000/register` in your browser.
2. Fill out Step 1 with a name, email, and password. Let's use password: `SecurePassword123`
3. Click **Proceed to Biometrics**.
4. Type your password exactly **10 times** in the input field. Pay attention to typing it in your normal, continuous, muscle-memory speed.
5. After the 10th sample, the system automatically registers the account and trains a personalized classifier (Random Forest/SVM) on your timings.
6. You will be redirected to your User Dashboard showing your baseline statistics.

### 3.2. Success Login Case (Legitimate Owner)
1. Go to `http://localhost:3000/login` (logout if logged in).
2. Enter your registered email and type the password (`SecurePassword123`) using your normal typing speed and rhythm.
3. The system will recognize your biometrics, show a low risk score, and log you in.

### 3.3. Blocked Login Case (Stolen Password / Impersonator Mismatch)
1. Go to the login page.
2. Enter your email and type the correct password (`SecurePassword123`), but type it extremely slowly (e.g., lingering on each key for a second) or type it with unnatural pauses.
3. The system will detect the rhythm deviation (mismatching hold times, slow speed Z-scores, and ML classifier rejection), identify it as an Impersonator attempt, flag it as High Risk, and block your access.

### 3.4. Simulated Attacks (Attack Center)
1. Open `http://localhost:3000/simulations`.
2. Try the **Credential Stuffing (Paste) Attack**: The system catches the 0ms flight times and blocks the attack.
3. Try the **Robotic Bot Attack**: The system identifies the perfectly uniform timing spacing (0ms standard deviation) and blocks it.
4. Try the **Brute Force Lockout**: The system locks out the account after 5 consecutive guesses, showing credential dictionary protections.

---

## 4. Production Container Deployment (Docker Support)

The repository includes a multi-container Docker Compose setup for production building.

### 4.1. Root Docker Compose config
To build and spin up the complete frontend, backend, and DB stack in production mode:
```bash
docker-compose up --build
```
This builds:
- **`backend` container**: Runs FastAPI on port 8000.
- **`frontend` container**: Runs production Next.js node server on port 3000.
- **`database` file**: Stored locally in a shared volume.
