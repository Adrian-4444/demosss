import pytest
import json
import numpy as np
from app import models, ml, risk_engine

def test_feature_extraction():
    # Length of password L = 8
    hold_times = [100.0] * 8
    flight_times = [150.0] * 7
    latencies = [250.0] * 7
    typing_speed = 5.0
    
    vec = ml.extract_features_from_sample(hold_times, flight_times, latencies, typing_speed)
    
    # Expected feature vector length: 8 (holds) + 7 (flights) + 7 (latencies) + 5 stats = 27
    assert len(vec) == 27
    assert vec[0] == 100.0  # Hold time
    assert vec[8] == 150.0  # Flight time
    assert vec[15] == 250.0 # Latency
    assert vec[22] == 5.0   # Typing speed
    assert vec[23] == 100.0 # Mean hold

def test_model_training():
    # Create 10 positive samples representing John Doe's password "SecureJohn99" (L=12)
    user_samples = []
    for _ in range(10):
        sample = models.KeystrokeSample(
            hold_times_json=json.dumps([100.0 + np.random.normal(0, 5) for _ in range(12)]),
            flight_times_json=json.dumps([150.0 + np.random.normal(0, 8) for _ in range(11)]),
            latencies_json=json.dumps([250.0 + np.random.normal(0, 10) for _ in range(11)]),
            typing_speed=5.2
        )
        user_samples.append(sample)
        
    # Create other samples
    other_samples = []
    for _ in range(5):
        sample = models.KeystrokeSample(
            hold_times_json=json.dumps([110.0 + np.random.normal(0, 5) for _ in range(12)]),
            flight_times_json=json.dumps([180.0 + np.random.normal(0, 8) for _ in range(11)]),
            latencies_json=json.dumps([290.0 + np.random.normal(0, 10) for _ in range(11)]),
            typing_speed=4.3
        )
        other_samples.append(sample)
        
    X, y = ml.prepare_dataset(user_samples, other_samples)
    
    # Assert dimensions are homogeneous
    assert X.shape[0] == len(user_samples) + 25  # 10 positives + 25 synthetic negatives (since valid negatives < 20)
    assert X.shape[1] == 12 + 11 + 11 + 5        # 39 features
    
    training_res = ml.train_and_compare_models(X, y)
    assert "best_model_name" in training_res
    assert "model_bytes" in training_res
    assert "metrics" in training_res
    assert len(training_res["model_bytes"]) > 0

def test_risk_engine_defense():
    class DummyKeystroke:
        def __init__(self, holds, flights, lats, speed, backspaces):
            self.hold_times = holds
            self.flight_times = flights
            self.latencies = lats
            self.typing_speed = speed
            self.backspace_count = backspaces

    # Mock user baseline stats
    user = models.User(
        name="Tester",
        email="test@banking.com",
        is_locked=False,
        failed_attempts=0,
        baseline_stats=json.dumps({
            "mean_hold": [100.0] * 8,
            "std_hold": [10.0] * 8,
            "mean_flight": [150.0] * 7,
            "std_flight": [15.0] * 7,
            "mean_latency": [250.0] * 7,
            "std_latency": [20.0] * 7,
            "mean_speed": 5.0,
            "std_speed": 0.5
        })
    )

    # 1. Test Clipboard Paste Attack (Credential Stuffing)
    paste_data = DummyKeystroke(
        holds=[1.0] * 8,
        flights=[0.0] * 7,
        lats=[1.0] * 7,
        speed=100.0,
        backspaces=0
    )
    res_paste = risk_engine.evaluate_login_biometrics(paste_data, user, "Chrome", "192.168.1.1", [])
    assert res_paste["risk_level"] == "High"
    assert res_paste["decision"] == "REJECT"
    assert any("Paste Attack" in anom for anom in res_paste["anomalies"])

    # 2. Test Bot Signature Attack (Perfect Uniform Spacing)
    bot_data = DummyKeystroke(
        holds=[50.0] * 8,
        flights=[50.0] * 7,
        lats=[100.0] * 7,
        speed=10.0,
        backspaces=0
    )
    res_bot = risk_engine.evaluate_login_biometrics(bot_data, user, "Chrome", "192.168.1.1", [])
    assert res_bot["risk_level"] == "High"
    assert res_bot["decision"] == "REJECT"
    assert any("Bot Signature" in anom for anom in res_bot["anomalies"])

    # 3. Test Normal Authorized Signature Matching (Low Risk)
    normal_data = DummyKeystroke(
        holds=[102.0, 98.0, 105.0, 95.0, 100.0, 101.0, 99.0, 100.0],
        flights=[152.0, 148.0, 155.0, 145.0, 150.0, 151.0, 149.0],
        lats=[254.0, 246.0, 260.0, 240.0, 250.0, 252.0, 248.0],
        speed=5.1,
        backspaces=0
    )
    # Mock model prediction as 1 (normal)
    user.ml_model_blob = None  # Force fallback to similarity distance evaluation
    res_normal = risk_engine.evaluate_login_biometrics(normal_data, user, "Chrome", "192.168.1.1", [])
    assert res_normal["risk_level"] == "Low"
    assert res_normal["decision"] == "ACCEPT"
    assert res_normal["similarity_score"] > 80.0
