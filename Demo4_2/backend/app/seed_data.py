import sys
import os
import json
import random
from datetime import datetime, timedelta

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine
from app import models, auth, ml

def generate_keystroke_vectors(password: str, profile_type: str = "normal") -> dict:
    """
    Generates mock keystroke timing vectors (hold times, flight times, latencies)
    based on the password text and a simulated typing style.
    """
    L = len(password)
    holds = []
    flights = []
    latencies = []
    
    # Establish typing speed signature (keys per second)
    if profile_type == "normal":
        speed = random.uniform(4.0, 7.0)
        base_hold = random.uniform(80.0, 120.0)
        base_flight = random.uniform(100.0, 200.0)
        noise_level = 15.0
    elif profile_type == "slow":
        speed = random.uniform(1.5, 3.0)
        base_hold = random.uniform(140.0, 220.0)
        base_flight = random.uniform(250.0, 450.0)
        noise_level = 35.0
    elif profile_type == "fast":
        speed = random.uniform(8.0, 12.0)
        base_hold = random.uniform(45.0, 70.0)
        base_flight = random.uniform(40.0, 90.0)
        noise_level = 8.0
    elif profile_type == "bot":
        # Robotic timing: exactly identical intervals
        speed = 10.0
        holds = [50.0] * L
        flights = [50.0] * (L - 1)
        latencies = [100.0] * (L - 1)
        return {"holds": holds, "flights": flights, "latencies": latencies, "speed": speed}
    elif profile_type == "paste":
        # Paste timing: everything is zero
        speed = 100.0
        holds = [1.0] * L
        flights = [0.0] * (L - 1)
        latencies = [1.0] * (L - 1)
        return {"holds": holds, "flights": flights, "latencies": latencies, "speed": speed}
        
    # Generate human timing lists
    current_time = 0.0
    press_times = []
    release_times = []
    
    for i in range(L):
        # Hold duration
        hold = max(20.0, base_hold + random.normalvariate(0, noise_level))
        holds.append(hold)
        
        # Press timestamp
        press_times.append(current_time)
        release_times.append(current_time + hold)
        
        if i < L - 1:
            # Flight interval to next key
            flight = base_flight + random.normalvariate(0, noise_level)
            flights.append(flight)
            # Next key down occurs after flight time
            current_time = release_times[-1] + flight
            
    # Calculate Latencies (press-to-press)
    for i in range(L - 1):
        latencies.append(press_times[i+1] - press_times[i])
        
    return {
        "holds": [round(h, 1) for h in holds],
        "flights": [round(f, 1) for f in flights],
        "latencies": [round(l, 1) for l in latencies],
        "speed": round(speed, 2)
    }

def seed_db():
    print("Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Define our seed users
    users_to_seed = [
        {"name": "Administrator", "email": "admin@banking.com", "password": "AdminPassword123", "role": "admin", "style": "fast"},
        {"name": "John Doe", "email": "john@banking.com", "password": "SecureJohn99", "role": "user", "style": "normal"},
        {"name": "Jane Smith", "email": "jane@banking.com", "password": "JaneP@ssword", "role": "user", "style": "slow"}
    ]
    
    seeded_users = []
    all_seeded_samples = []
    
    print("\nSeeding users and baseline keystroke profiles...")
    for user_info in users_to_seed:
        # Create User
        db_user = models.User(
            name=user_info["name"],
            email=user_info["email"],
            password_hash=auth.hash_password(user_info["password"]),
            role=user_info["role"]
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        seeded_users.append((db_user, user_info))
        
        # Create 10 registration typing samples
        user_samples = []
        for _ in range(10):
            timings = generate_keystroke_vectors(user_info["password"], user_info["style"])
            sample = models.KeystrokeSample(
                user_id=db_user.id,
                hold_times_json=json.dumps(timings["holds"]),
                flight_times_json=json.dumps(timings["flights"]),
                latencies_json=json.dumps(timings["latencies"]),
                typing_speed=timings["speed"],
                backspace_count=0,
                error_rate=0.0
            )
            db.add(sample)
            user_samples.append(sample)
            all_seeded_samples.append(sample)
            
        db.commit()
        
        # Calculate baseline statistics
        baseline = ml.calculate_baseline_statistics(user_samples)
        db_user.baseline_stats = json.dumps(baseline)
        db.commit()
        print(f"-> Seeded {db_user.name} ({db_user.email}) with 10 typing samples.")
        
    print("\nTraining biometrics classifier models for each user...")
    # Train models
    for db_user, user_info in seeded_users:
        user_samples = db.query(models.KeystrokeSample).filter(models.KeystrokeSample.user_id == db_user.id).all()
        other_samples = db.query(models.KeystrokeSample).filter(models.KeystrokeSample.user_id != db_user.id).all()
        
        X, y = ml.prepare_dataset(user_samples, other_samples)
        
        training_res = ml.train_and_compare_models(X, y)
        db_user.ml_model_blob = training_res["model_bytes"]
        db_user.trained_algorithm = training_res["best_model_name"]
        db.commit()
        print(f"-> Successfully trained model for {db_user.name}. Active model: {db_user.trained_algorithm}")

    # Seed authentication logs history for the past 14 days
    print("\nGenerating simulated historical authentication attempts & security logs...")
    
    start_date = datetime.utcnow() - timedelta(days=14)
    devices = [
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36Chrome/120.0.0.0 Safari/537.36", "192.168.1.45"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1", "172.56.21.9"),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0", "73.14.92.108")
    ]
    
    # Generate logs
    for day in range(15):
        log_date = start_date + timedelta(days=day)
        
        # Create between 3 and 10 logs per day
        num_logs = random.randint(5, 12)
        
        for _ in range(num_logs):
            # Select random user
            user_pair = random.choice(seeded_users)
            db_user, user_info = user_pair
            
            # Select random log type: Successful, MFA challenged, Blocked, or Attack simulation
            log_type = random.choices(
                ["success", "failed_password", "mismatch_biometrics", "mfa_success", "bot_attack", "paste_attack"],
                weights=[60, 10, 12, 10, 4, 4],
                k=1
            )[0]
            
            # Timestamp scattered throughout the day
            timestamp = log_date.replace(
                hour=random.randint(0, 23),
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            )
            
            device = random.choice(devices)
            uagent, ip = device
            
            sim_type = "None"
            status = False
            sim_score = None
            conf_score = None
            risk_score = None
            risk_lvl = None
            anomalies = []
            
            if log_type == "success":
                status = True
                sim_score = random.uniform(82.0, 96.0)
                conf_score = random.uniform(85.0, 99.0)
                risk_score = random.uniform(5.0, 25.0)
                risk_lvl = "Low"
                
            elif log_type == "failed_password":
                status = False
                risk_score = 100.0
                risk_lvl = "High"
                anomalies = ["Incorrect password credentials"]
                
            elif log_type == "mismatch_biometrics":
                status = False
                sim_score = random.uniform(40.0, 65.0)
                conf_score = random.uniform(30.0, 58.0)
                risk_score = random.uniform(72.0, 90.0)
                risk_lvl = "High"
                anomalies = ["Moderate behavioral biometrics mismatch", "AI Model prediction: Impersonator signature"]
                sim_type = "Impersonation"
                
            elif log_type == "mfa_success":
                status = True
                sim_score = random.uniform(66.0, 74.0)
                conf_score = random.uniform(62.0, 71.0)
                risk_score = random.uniform(40.0, 60.0)
                risk_lvl = "Medium"
                anomalies = ["Moderate behavioral biometrics mismatch", "MFA OTP Step-up Verified"]
                
            elif log_type == "bot_attack":
                status = False
                sim_score = 10.0
                conf_score = 15.0
                risk_score = 100.0
                risk_lvl = "High"
                anomalies = ["Bot Signature: Perfect uniform keystroke duration detected", "Bot Signature: Speed exceeds human typing capabilities"]
                sim_type = "Bot"
                uagent = "Python-requests/2.31.0"
                ip = "45.227.254.12"
                
            elif log_type == "paste_attack":
                status = False
                sim_score = 5.0
                conf_score = 5.0
                risk_score = 100.0
                risk_lvl = "High"
                anomalies = ["Paste Attack: Keys entered instantly (Credential Stuffing pattern)"]
                sim_type = "CredentialStuffing"
                ip = "185.220.101.5" # Tor Exit Node
            
            auth_log = models.AuthLog(
                user_id=db_user.id,
                timestamp=timestamp,
                status=status,
                similarity_score=sim_score,
                confidence_score=conf_score,
                risk_score=risk_score,
                risk_level=risk_lvl,
                flagged_anomalies=json.dumps(anomalies),
                user_agent=uagent,
                client_ip=ip,
                simulation_type=sim_type
            )
            db.add(auth_log)
            
    db.commit()
    db.close()
    print("\nDatabase seeding completed successfully! The application is ready to run.")

if __name__ == "__main__":
    seed_db()
