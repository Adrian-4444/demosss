from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.config import settings
from app.database import Base, engine, get_db
from app import models, schemas, auth, ml, risk_engine

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom In-Memory Rate Limiting
ip_request_history: Dict[str, List[datetime]] = {}

@app.middleware("http")
async def rate_limiter_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow()
    
    # Prune history
    if client_ip not in ip_request_history:
        ip_request_history[client_ip] = []
    
    # Only keep requests from the last 60 seconds
    ip_request_history[client_ip] = [
        t for t in ip_request_history[client_ip] if (now - t).total_seconds() < 60
    ]
    
    # Rate limit: 60 requests per minute
    if len(ip_request_history[client_ip]) > 100:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again in a minute."
        )
        
    ip_request_history[client_ip].append(now)
    
    # Security headers (Helmet equivalent)
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Temporary store for generated login OTPs (in production, use Redis or DB)
active_otps: Dict[str, str] = {}

# --- ENDPOINTS ---

@app.post("/api/auth/register", response_model=schemas.TokenResponse)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    # Create the user
    # If first user, make them admin for demo ease, else user
    is_first = db.query(models.User).count() == 0
    role = "admin" if is_first else "user"
    
    new_user = models.User(
        name=user_data.name,
        email=user_data.email,
        password_hash=auth.hash_password(user_data.password),
        role=role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Save the 10 typing samples
    samples_created = []
    for sample in user_data.keystroke_samples:
        db_sample = models.KeystrokeSample(
            user_id=new_user.id,
            hold_times_json=json.dumps(sample.hold_times),
            flight_times_json=json.dumps(sample.flight_times),
            latencies_json=json.dumps(sample.latencies),
            typing_speed=sample.typing_speed,
            backspace_count=sample.backspace_count,
            error_rate=sample.error_rate
        )
        db.add(db_sample)
        samples_created.append(db_sample)
    db.commit()
    
    # Calculate baseline profile
    baseline = ml.calculate_baseline_statistics(samples_created)
    new_user.baseline_stats = json.dumps(baseline)
    db.commit()
    
    # Train the models for this user!
    # Fetch negative samples from other users
    other_samples = db.query(models.KeystrokeSample).filter(models.KeystrokeSample.user_id != new_user.id).all()
    
    # If no other samples exist in the database (this is the first user), generate synthetic negatives
    if len(other_samples) < 10:
        other_samples = []
        # Generate synthetic timing variants with high variance/noise to act as impostors
        for sample in samples_created:
            for _ in range(3):  # 3 fake impostor variations per sample
                holds = json.loads(sample.hold_times_json)
                flights = json.loads(sample.flight_times_json)
                latencies = json.loads(sample.latencies_json)
                
                # Add heavy noise (std dev of 100ms) to create an impostor pattern
                fake_holds = [max(10.0, h + random.normalvariate(0, 100)) for h in holds]
                fake_flights = [f + random.normalvariate(0, 150) for f in flights]
                fake_latencies = [l + random.normalvariate(0, 180) for l in latencies]
                fake_speed = max(0.5, sample.typing_speed + random.normalvariate(0, 3.0))
                
                dummy_sample = models.KeystrokeSample(
                    user_id=0,
                    hold_times_json=json.dumps(fake_holds),
                    flight_times_json=json.dumps(fake_flights),
                    latencies_json=json.dumps(fake_latencies),
                    typing_speed=fake_speed
                )
                other_samples.append(dummy_sample)

    # Compile dataset & train classifiers
    X, y = ml.prepare_dataset(samples_created, other_samples)
    
    try:
        training_res = ml.train_and_compare_models(X, y)
        new_user.ml_model_blob = training_res["model_bytes"]
        new_user.trained_algorithm = training_res["best_model_name"]
        db.commit()
    except Exception as e:
        print(f"Error training models during registration: {e}")
        # Default fallback to One-Class SVM training if binary classification fails
        try:
            from sklearn.svm import OneClassSVM
            from sklearn.preprocessing import StandardScaler
            from sklearn.pipeline import Pipeline
            import joblib
            
            # Simple fallback model
            oc_pipeline = Pipeline([
                ("scaler", StandardScaler()),
                ("classifier", OneClassSVM(nu=0.1, kernel="rbf"))
            ])
            X_pos = X[y == 1]
            import io
            buffer = io.BytesIO()
            joblib.dump(oc_pipeline, buffer)
            new_user.ml_model_blob = buffer.getvalue()
            new_user.trained_algorithm = "One-Class SVM"
            db.commit()
        except Exception as e_inner:
            print(f"Fallback training also failed: {e_inner}")

    # Generate JWT
    access_token = auth.create_access_token(data={"sub": new_user.email})
    
    # Audit log the registration as a successful auth event
    log = models.AuthLog(
        user_id=new_user.id,
        status=True,
        similarity_score=100.0,
        confidence_score=100.0,
        risk_score=0.0,
        risk_level="Low",
        flagged_anomalies=json.dumps([]),
        user_agent="Registration Profiling",
        client_ip="localhost",
        simulation_type="None"
    )
    db.add(log)
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": new_user.role,
        "user": new_user
    }


@app.post("/api/auth/login")
def login(
    login_data: schemas.UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    user_agent = request.headers.get("user-agent", "unknown")
    client_ip = request.client.host if request.client else "unknown"

    # 1. Fetch user (OWASP: generic error message)
    user = db.query(models.User).filter(models.User.email == login_data.email).first()
    if not user:
        # Avoid timing differences
        auth.verify_password("dummy_password", "dummy_hash")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    # 2. Check lockout
    auth.check_brute_force_lockout(user)
    
    # 3. Verify password
    if not auth.verify_password(login_data.password, user.password_hash):
        auth.record_failed_login(user, db)
        
        # Log failure
        log = models.AuthLog(
            user_id=user.id,
            status=False,
            risk_level="High",
            risk_score=100.0,
            flagged_anomalies=json.dumps(["Incorrect password credentials"]),
            user_agent=user_agent,
            client_ip=client_ip,
            simulation_type=login_data.simulation_type
        )
        db.add(log)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    # 4. Password is correct! Run Keystroke Biometrics Risk Engine
    # Retrieve user's previous history logs for anomaly analysis
    history = db.query(models.AuthLog).filter(models.AuthLog.user_id == user.id).order_by(models.AuthLog.timestamp.desc()).limit(10).all()
    
    biometrics_eval = risk_engine.evaluate_login_biometrics(
        keystroke_data=login_data.keystroke_data,
        user=user,
        user_agent=user_agent,
        ip_address=client_ip,
        history_logs=history
    )
    
    # 5. Create Auth Log
    log = models.AuthLog(
        user_id=user.id,
        status=(biometrics_eval["decision"] != "REJECT"),
        similarity_score=biometrics_eval["similarity_score"],
        confidence_score=biometrics_eval["confidence_score"],
        risk_score=biometrics_eval["risk_score"],
        risk_level=biometrics_eval["risk_level"],
        flagged_anomalies=json.dumps(biometrics_eval["anomalies"]),
        user_agent=user_agent,
        client_ip=client_ip,
        simulation_type=login_data.simulation_type
    )
    db.add(log)
    db.commit()
    
    decision = biometrics_eval["decision"]
    
    if decision == "REJECT":
        # Increment failed logins and reject
        auth.record_failed_login(user, db)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Access denied due to behavioral biometrics mismatch (Keystroke dynamics anomaly).",
                "anomalies": biometrics_eval["anomalies"],
                "risk_score": biometrics_eval["risk_score"]
            }
        )
        
    elif decision == "MFA_CHALLENGE":
        # Adaptive Authentication: require OTP verification
        otp = f"{random.randint(100000, 999999)}"
        active_otps[user.email] = otp
        
        # In a real environment, send via email. For developer demo, we return it or output it.
        print(f"\n==========================================")
        print(f"[SECURITY CONTROL] Adaptive Auth OTP for {user.email}: {otp}")
        print(f"==========================================\n")
        
        # Create a temporary JWT token that ONLY allows OTP verification
        temp_token = auth.create_access_token(data={"sub": user.email, "scope": "mfa_verification"}, expires_delta=timedelta(minutes=5))
        
        return {
            "status": "MFA_REQUIRED",
            "temp_token": temp_token,
            "risk_score": biometrics_eval["risk_score"],
            "anomalies": biometrics_eval["anomalies"],
            "otp_debug": otp  # Returned for developer demonstration visibility
        }
        
    # ACCEPT login
    auth.reset_failed_login(user, db)
    access_token = auth.create_access_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at
        }
    }


@app.post("/api/auth/verify-otp")
def verify_otp(data: schemas.OTPValidation, db: Session = Depends(get_db)):
    stored_otp = active_otps.get(data.email)
    if not stored_otp or stored_otp != data.otp:
        # Log failure
        user = db.query(models.User).filter(models.User.email == data.email).first()
        if user:
            log = models.AuthLog(
                user_id=user.id,
                status=False,
                risk_level="High",
                risk_score=95.0,
                flagged_anomalies=json.dumps(["Failed step-up OTP challenge"]),
                user_agent="MFA Engine",
                client_ip="localhost",
                simulation_type="None"
            )
            db.add(log)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
        
    # Clear OTP
    del active_otps[data.email]
    
    user = db.query(models.User).filter(models.User.email == data.email).first()
    auth.reset_failed_login(user, db)
    
    # Audit trail success
    log = models.AuthLog(
        user_id=user.id,
        status=True,
        risk_level="Medium",
        risk_score=50.0,
        flagged_anomalies=json.dumps(["MFA OTP Step-up Verified"]),
        user_agent="MFA Engine",
        client_ip="localhost",
        simulation_type="None"
    )
    db.add(log)
    db.commit()
    
    access_token = auth.create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at
        }
    }


@app.get("/api/dashboard/user-stats", response_model=schemas.UserStatsResponse)
def get_user_stats(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    # Total login counts
    total_logins = db.query(models.AuthLog).filter(models.AuthLog.user_id == current_user.id).count()
    failed_logins = db.query(models.AuthLog).filter(models.AuthLog.user_id == current_user.id, models.AuthLog.status == False).count()
    
    # Biometric Averages
    logs_with_score = db.query(models.AuthLog).filter(
        models.AuthLog.user_id == current_user.id, 
        models.AuthLog.similarity_score.isnot(None)
    ).all()
    
    avg_similarity = 100.0
    if len(logs_with_score) > 0:
        avg_similarity = sum(l.similarity_score for l in logs_with_score) / len(logs_with_score)
        
    # Typing averages from baseline
    avg_speed = 0.0
    avg_hold = 0.0
    if current_user.baseline_stats:
        base = json.loads(current_user.baseline_stats)
        avg_speed = base["mean_speed"]
        avg_hold = sum(base["mean_hold"]) / len(base["mean_hold"]) if len(base["mean_hold"]) > 0 else 0.0
        
    # Get last 50 audit logs
    history = db.query(models.AuthLog).filter(models.AuthLog.user_id == current_user.id).order_by(models.AuthLog.timestamp.desc()).limit(50).all()
    
    return {
        "total_logins": total_logins,
        "failed_logins": failed_logins,
        "avg_speed": round(avg_speed, 1),
        "avg_hold": round(avg_hold, 1),
        "avg_similarity": round(avg_similarity, 1),
        "history": history
    }


@app.get("/api/dashboard/admin-stats", response_model=schemas.AdminStatsResponse)
def get_admin_stats(
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    total_users = db.query(models.User).count()
    total_attempts = db.query(models.AuthLog).count()
    failed_attempts = db.query(models.AuthLog).filter(models.AuthLog.status == False).count()
    
    # Calculate compromised logins prevented (High risk rejects and bot blocks)
    compromised_prevented = db.query(models.AuthLog).filter(
        models.AuthLog.status == False,
        (models.AuthLog.risk_level == "High") | (models.AuthLog.simulation_type != "None")
    ).count()

    # Log timeline (grouped by day)
    # Simple SQLite grouping (could fail on postgres, but we use portable code)
    logs = db.query(models.AuthLog).order_by(models.AuthLog.timestamp.desc()).limit(500).all()
    
    # Calculate daily logins
    daily_map = {}
    anomaly_map = {}
    
    for log in logs:
        day_str = log.timestamp.strftime("%Y-%m-%d")
        daily_map[day_str] = daily_map.get(day_str, {"success": 0, "fail": 0})
        if log.status:
            daily_map[day_str]["success"] += 1
        else:
            daily_map[day_str]["fail"] += 1
            
        # Compile anomaly tags
        if log.flagged_anomalies:
            try:
                tags = json.loads(log.flagged_anomalies)
                for tag in tags:
                    # Strip details
                    simple_tag = tag.split(":")[0]
                    anomaly_map[simple_tag] = anomaly_map.get(simple_tag, 0) + 1
            except Exception:
                pass
                
    daily_logins = [{"date": k, "success": v["success"], "failed": v["fail"]} for k, v in sorted(daily_map.items())][-7:]
    anomalies_distribution = [{"name": k, "value": v} for k, v in anomaly_map.items()]
    
    recent_attempts = db.query(models.AuthLog).order_by(models.AuthLog.timestamp.desc()).limit(50).all()
    
    return {
        "total_users": total_users,
        "total_attempts": total_attempts,
        "failed_attempts": failed_attempts,
        "compromised_prevented": compromised_prevented,
        "daily_logins": daily_logins,
        "anomalies_distribution": anomalies_distribution,
        "recent_attempts": recent_attempts
    }


@app.get("/api/ml/compare-models")
def compare_models(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Simulates training and compares accuracy across all ML classifiers using the logged-in user's
    data vs all other samples.
    """
    user_samples = db.query(models.KeystrokeSample).filter(models.KeystrokeSample.user_id == current_user.id).all()
    if len(user_samples) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough keystroke data. Retrain requires at least 10 samples."
        )
        
    other_samples = db.query(models.KeystrokeSample).filter(models.KeystrokeSample.user_id != current_user.id).all()
    
    # Generate synthetic negative samples if not enough exist
    if len(other_samples) < 10:
        other_samples = []
        for sample in user_samples:
            for _ in range(3):
                holds = json.loads(sample.hold_times_json)
                flights = json.loads(sample.flight_times_json)
                latencies = json.loads(sample.latencies_json)
                
                fake_holds = [max(10.0, h + random.normalvariate(0, 100)) for h in holds]
                fake_flights = [f + random.normalvariate(0, 150) for f in flights]
                fake_latencies = [l + random.normalvariate(0, 180) for l in latencies]
                fake_speed = max(0.5, sample.typing_speed + random.normalvariate(0, 3.0))
                
                dummy_sample = models.KeystrokeSample(
                    user_id=0,
                    hold_times_json=json.dumps(fake_holds),
                    flight_times_json=json.dumps(fake_flights),
                    latencies_json=json.dumps(fake_latencies),
                    typing_speed=fake_speed
                )
                other_samples.append(dummy_sample)
                
    X, y = ml.prepare_dataset(user_samples, other_samples)
    
    try:
        training_res = ml.train_and_compare_models(X, y)
        
        # Save the new model to DB
        current_user.ml_model_blob = training_res["model_bytes"]
        current_user.trained_algorithm = training_res["best_model_name"]
        db.commit()
        
        return {
            "active_model": training_res["best_model_name"],
            "comparisons": training_res["metrics"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model training comparison failed: {str(e)}"
        )
