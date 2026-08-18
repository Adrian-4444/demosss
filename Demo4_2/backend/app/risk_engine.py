import numpy as np
import json
import joblib
from typing import Dict, List, Tuple, Any
from app.config import settings
from app import models
from app.ml import extract_features_from_sample

def compute_similarity_percentage(
    hold_times: List[float],
    flight_times: List[float],
    latencies: List[float],
    baseline: Dict[str, Any]
) -> float:
    """
    Computes a distance-based similarity percentage (0-100%) between the typed sample
    and the user's baseline profile using Z-score normalization.
    """
    if not baseline:
        return 50.0  # Default neutral score
        
    mu_hold = np.array(baseline["mean_hold"])
    sigma_hold = np.array(baseline["std_hold"])
    mu_flight = np.array(baseline["mean_flight"])
    sigma_flight = np.array(baseline["std_flight"])
    
    # Ensure dimensions match
    h_len = min(len(hold_times), len(mu_hold))
    f_len = min(len(flight_times), len(mu_flight))
    
    if h_len == 0:
        return 0.0
        
    # Calculate Z-scores for hold times (with epsilon to prevent division by zero)
    eps = 5.0  # 5ms min deviation
    z_holds = np.abs(np.array(hold_times[:h_len]) - mu_hold[:h_len]) / (sigma_hold[:h_len] + eps)
    
    # Calculate Z-scores for flight times
    z_flights = []
    if f_len > 0:
        z_flights = np.abs(np.array(flight_times[:f_len]) - mu_flight[:f_len]) / (sigma_flight[:f_len] + eps)
        
    # Average Z-score across all timing features
    all_z = list(z_holds) + list(z_flights)
    avg_z = np.mean(all_z)
    
    # Map Z-score to a percentage. 
    # An average Z-score of 0 is 100% similarity.
    # An average Z-score of 3.0 is 0% similarity.
    similarity = 100.0 * np.exp(-0.4 * avg_z)
    return float(np.clip(similarity, 0.0, 100.0))

def evaluate_login_biometrics(
    keystroke_data: Any,
    user: models.User,
    user_agent: str,
    ip_address: str,
    history_logs: List[models.AuthLog]
) -> Dict[str, Any]:
    """
    Main risk engine. Compares the login timing sample against the user's ML model
    and baseline statistics, extracts anomalies, and determines the overall risk rating.
    """
    hold_times = keystroke_data.hold_times
    flight_times = keystroke_data.flight_times
    latencies = keystroke_data.latencies
    speed = keystroke_data.typing_speed
    backspaces = keystroke_data.backspace_count
    
    anomalies = []
    suspicion_points = 0
    
    # --- 1. SIGNATURE ATTACK CHECKS ---
    
    # Check for Paste Attack (Credential Stuffing / Key Injection)
    # If all flight times are 0, or typing speed is incredibly fast, it's a paste
    is_paste_attack = False
    if len(flight_times) > 0 and all(f <= 2.0 for f in flight_times):
        is_paste_attack = True
        anomalies.append("Paste Attack: Keys entered instantly (Credential Stuffing pattern)")
        suspicion_points += 100
        
    # Check for Bot Signature
    # If standard deviation of hold times is 0 or near 0, the timing is synthetic
    is_bot = False
    if len(hold_times) > 1 and np.std(hold_times) < 0.5:
        is_bot = True
        anomalies.append("Bot Signature: Perfect uniform keystroke duration detected")
        suspicion_points += 100
        
    # Check for hyper-speed bot typing (e.g., > 40 chars per second)
    if speed > 40.0:
        is_bot = True
        anomalies.append("Bot Signature: Speed exceeds human typing capabilities")
        suspicion_points += 100

    # If it is a paste or bot attack, we fail early with maximum risk
    if is_paste_attack or is_bot:
        return {
            "similarity_score": 0.0,
            "confidence_score": 0.0,
            "risk_score": 100.0,
            "risk_level": "High",
            "anomalies": anomalies,
            "decision": "REJECT"
        }

    # --- 2. BIOMETRIC EVALUATION (COMPARED TO BASELINE) ---
    
    baseline = json.loads(user.baseline_stats) if user.baseline_stats else None
    similarity_score = 50.0
    
    if baseline:
        similarity_score = compute_similarity_percentage(hold_times, flight_times, latencies, baseline)
        
        # Check if speed deviates heavily from average speed
        speed_mean = baseline["mean_speed"]
        speed_std = baseline["std_speed"]
        speed_z = abs(speed - speed_mean) / (speed_std + 0.2)
        
        if speed > speed_mean + 3 * speed_std:
            anomalies.append("Abnormally fast typing rhythm (Outlier)")
            suspicion_points += 15
        elif speed < speed_mean - 3 * speed_std:
            anomalies.append("Abnormally slow typing rhythm (Outlier)")
            suspicion_points += 15
            
        # Check hold times anomaly
        avg_hold = np.mean(hold_times)
        baseline_hold_mean = np.mean(baseline["mean_hold"])
        if abs(avg_hold - baseline_hold_mean) > 80.0: # deviation of > 80ms
            anomalies.append("Unusual key hold duration (Cadence deviation)")
            suspicion_points += 20
            
        # Rhythm Correlation: Check pattern shape
        # Let's compare hold time trends (correlation coefficient)
        h_len = min(len(hold_times), len(baseline["mean_hold"]))
        if h_len > 2:
            corr = np.corrcoef(hold_times[:h_len], baseline["mean_hold"][:h_len])[0, 1]
            if np.isnan(corr) or corr < 0.4:
                anomalies.append("Irregular rhythm sequence (Finger timing mismatch)")
                suspicion_points += 20
                
        # Check backspaces
        if backspaces > 3:
            anomalies.append(f"Excessive typing corrections ({backspaces} Backspaces)")
            suspicion_points += 10
            
        # Risk penalties based on similarity
        if similarity_score < 40.0:
            anomalies.append("Severe behavioral biometrics mismatch")
            suspicion_points += 55
        elif similarity_score < 50.0:
            anomalies.append("Moderate behavioral biometrics mismatch")
            suspicion_points += 30
    
    # --- 3. MACHINE LEARNING MODEL PREDICTION ---
    confidence_score = 50.0
    ml_prediction = 1 # Default positive
    
    if user.ml_model_blob:
        try:
            # Reconstruct the feature vector
            feat_vec = extract_features_from_sample(hold_times, flight_times, latencies, speed)
            feat_vec = feat_vec.reshape(1, -1)
            
            # Load pipeline
            import io
            buffer = io.BytesIO(user.ml_model_blob)
            model = joblib.load(buffer)
            
            # Predict
            ml_prediction = int(model.predict(feat_vec)[0])
            
            # Compute probability / confidence
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(feat_vec)[0]
                confidence_score = float(probs[1]) * 100.0
            else:
                # If model is one-class, output is 1 (normal) or -1 (anomaly)
                # Predict returns -1 or 1
                decision = model.decision_function(feat_vec)[0]
                # Normalize decision function value
                confidence_score = float(100 / (1 + np.exp(-decision)))
                if ml_prediction == -1:
                    ml_prediction = 0
            
            if ml_prediction == 0:
                anomalies.append(f"AI Model prediction: Impersonator signature ({user.trained_algorithm})")
                suspicion_points += 45
                
        except Exception as e:
            # Fallback if prediction fails
            print(f"ML evaluation failed: {e}")
            confidence_score = similarity_score
    else:
        # Fallback to similarity if no model exists
        confidence_score = similarity_score

    # --- 4. DEVICE AND CONTEXT ANALYSIS ---
    
    # Browser/Device mismatch
    if len(history_logs) > 0:
        known_agents = [log.user_agent for log in history_logs if log.status]
        if user_agent not in known_agents:
            anomalies.append("Unknown browser or device profile")
            suspicion_points += 15
            
        known_ips = [log.client_ip for log in history_logs if log.status]
        if ip_address not in known_ips:
            anomalies.append("Unusual access IP network location")
            suspicion_points += 10

    # Failed attempts risk booster
    if user.failed_attempts > 0:
        suspicion_points += user.failed_attempts * 15
        anomalies.append(f"Multiple recent failed authentication attempts ({user.failed_attempts})")

    # --- 5. RISK CATEGORY DECISION ---
    
    # Calculate final risk score (cap at 100)
    risk_score = min(max(suspicion_points, 0.0), 100.0)
    
    if risk_score <= 45.0:
        risk_level = "Low"
        decision = "ACCEPT"
    elif risk_score <= 70.0:
        risk_level = "Medium"
        decision = "MFA_CHALLENGE"  # Step-up authentication requested
    else:
        risk_level = "High"
        decision = "REJECT"

    # Always ensure a fallback for a paste attack
    if is_paste_attack:
        decision = "REJECT"

    return {
        "similarity_score": round(similarity_score, 1),
        "confidence_score": round(confidence_score, 1),
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "anomalies": anomalies,
        "decision": decision
    }
