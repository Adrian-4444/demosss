import numpy as np
import pandas as pd
import json
import joblib
from typing import List, Dict, Tuple, Any
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, roc_curve
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.svm import SVC, OneClassSVM
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import HistGradientBoostingClassifier

def extract_features_from_sample(hold_times: List[float], flight_times: List[float], latencies: List[float], typing_speed: float) -> np.ndarray:
    """
    Constructs a feature vector from keystroke timings.
    Length of vector: L (holds) + (L-1) (flights) + (L-1) (latencies) + 5 summary stats
    """
    holds_arr = np.array(hold_times)
    flights_arr = np.array(flight_times)
    
    mean_hold = np.mean(holds_arr) if len(holds_arr) > 0 else 0.0
    std_hold = np.std(holds_arr) if len(holds_arr) > 1 else 0.0
    mean_flight = np.mean(flights_arr) if len(flights_arr) > 0 else 0.0
    std_flight = np.std(flights_arr) if len(flights_arr) > 1 else 0.0
    
    # Base vector: holds + flights + latencies
    base_vector = hold_times + flight_times + latencies
    
    # Append statistical summary features
    stats = [typing_speed, mean_hold, std_hold, mean_flight, std_flight]
    
    return np.array(base_vector + stats)

def prepare_dataset(user_samples: List[Any], other_samples: List[Any]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Prepares X (features) and y (labels) arrays for classification training.
    y = 1 for the target user, 0 for other users (impersonators).
    To maintain a homogeneous matrix shape, only negative samples of the same 
    password length are selected. If insufficient, synthetic negatives are generated.
    """
    X = []
    y = []
    
    if not user_samples:
        return np.empty((0, 0)), np.empty((0,))

    # 1. Process legitimate user samples
    first_holds = json.loads(user_samples[0].hold_times_json)
    target_len = len(first_holds)
    
    for sample in user_samples:
        holds = json.loads(sample.hold_times_json)
        flights = json.loads(sample.flight_times_json)
        latencies = json.loads(sample.latencies_json)
        
        # Enforce target length consistency
        if len(holds) != target_len:
            continue
            
        vec = extract_features_from_sample(holds, flights, latencies, sample.typing_speed)
        X.append(vec)
        y.append(1)
        
    # 2. Process other user samples (negatives/impersonators) that match target length
    valid_negatives_count = 0
    for sample in other_samples:
        try:
            holds = json.loads(sample.hold_times_json)
            if len(holds) != target_len:
                continue  # Skip different password lengths
                
            flights = json.loads(sample.flight_times_json)
            latencies = json.loads(sample.latencies_json)
            vec = extract_features_from_sample(holds, flights, latencies, sample.typing_speed)
            X.append(vec)
            y.append(0)
            valid_negatives_count += 1
        except Exception:
            continue

    # 3. If there are not enough negative samples of the same length, generate synthetic negatives
    if valid_negatives_count < 20:
        import random
        # Generate synthetic impostor samples by taking the user's positive samples
        # and adding significant temporal noise (representing a different user/attacker)
        needed = 25 - valid_negatives_count
        for _ in range(needed):
            source_sample = random.choice(user_samples)
            holds = json.loads(source_sample.hold_times_json)
            flights = json.loads(source_sample.flight_times_json)
            latencies = json.loads(source_sample.latencies_json)
            
            # Add heavy random noise (impostor signature)
            fake_holds = [max(10.0, h + random.normalvariate(0, 100.0)) for h in holds]
            fake_flights = [f + random.normalvariate(0, 120.0) for f in flights]
            fake_latencies = [l + random.normalvariate(0, 150.0) for l in latencies]
            fake_speed = max(0.5, source_sample.typing_speed + random.normalvariate(0, 2.5))
            
            vec = extract_features_from_sample(fake_holds, fake_flights, fake_latencies, fake_speed)
            X.append(vec)
            y.append(0)
            
    return np.array(X), np.array(y)


def calculate_eer(y_true: np.ndarray, y_probs: np.ndarray) -> Tuple[float, float]:
    """
    Calculates the Equal Error Rate (EER) and the corresponding threshold.
    EER is the point where False Acceptance Rate (FAR) matches False Rejection Rate (FRR).
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_probs)
    fnr = 1 - tpr
    
    # Find the index where FAR and FRR are closest
    idx = np.nanargmin(np.absolute(fpr - fnr))
    eer = (fpr[idx] + fnr[idx]) / 2.0
    eer_threshold = thresholds[idx]
    
    return float(eer), float(eer_threshold)

def train_and_compare_models(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """
    Trains multiple ML algorithms, evaluates them using cross-validation / test splits,
    compares their results, and returns metrics along with the best model's serialized bytes.
    """
    # 80-20 split for validation
    # If the user has 10 samples and other users have 50 samples, we have 60 samples.
    # A standard train_test_split is appropriate.
    # To handle cases where we have very few samples, we use stratify if possible.
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )
    except ValueError:
        # Fallback if stratify fails due to too few samples
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42
        )

    # Dictionary of classifiers to evaluate
    classifiers = {
        "Random Forest": RandomForestClassifier(n_estimators=50, random_state=42),
        "Support Vector Machine": SVC(probability=True, kernel="rbf", random_state=42),
        "K-Nearest Neighbors": KNeighborsClassifier(n_neighbors=min(3, len(X_train))),
        "Neural Network": MLPClassifier(hidden_layer_sizes=(16, 8), max_iter=1000, random_state=42),
        "Gradient Boosting": HistGradientBoostingClassifier(max_iter=50, random_state=42)
    }

    comparison_results = {}
    best_f1 = -1.0
    best_model_name = None
    best_pipeline = None

    for name, clf in classifiers.items():
        # Build scaling pipeline
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", clf)
        ])
        
        # Train model
        pipeline.fit(X_train, y_train)
        
        # Predict labels and probabilities
        y_pred = pipeline.predict(X_test)
        if hasattr(pipeline, "predict_proba"):
            y_probs = pipeline.predict_proba(X_test)[:, 1]
        else:
            y_probs = pipeline.decision_function(X_test)
            # Normalize to 0-1
            y_probs = (y_probs - y_probs.min()) / (y_probs.max() - y_probs.min() + 1e-6)
            
        # Compute metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        
        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
        
        # Rates
        far = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        frr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        
        # Calculate EER
        try:
            eer, _ = calculate_eer(y_test, y_probs)
        except Exception:
            eer = (far + frr) / 2.0
            
        # Get ROC Curve details for frontend plotting
        fpr_pts, tpr_pts, _ = roc_curve(y_test, y_probs)
        
        comparison_results[name] = {
            "accuracy": float(acc * 100),
            "precision": float(prec * 100),
            "recall": float(rec * 100),
            "f1_score": float(f1 * 100),
            "far": float(far * 100),
            "frr": float(frr * 100),
            "eer": float(eer * 100),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "roc_curve": {"fpr": fpr_pts.tolist(), "tpr": tpr_pts.tolist()}
        }
        
        # Select best model based on F1 score and EER
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_pipeline = pipeline

    # Now let's train unsupervised models (One-Class SVM, Isolation Forest) using only positive samples (y=1)
    X_pos_train = X[y == 1]
    X_pos_test = X_test  # Evaluate on same test set to compare
    
    # One-Class SVM
    oc_svm_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", OneClassSVM(nu=0.1, kernel="rbf"))
    ])
    oc_svm_pipeline.fit(X_pos_train)
    # Predict: 1 = normal, -1 = anomaly
    y_pred_oc = oc_svm_pipeline.predict(X_pos_test)
    y_pred_oc_binary = np.where(y_pred_oc == 1, 1, 0)
    
    # Isolation Forest
    if_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", IsolationForest(contamination=0.1, random_state=42))
    ])
    if_pipeline.fit(X_pos_train)
    y_pred_if = if_pipeline.predict(X_pos_test)
    y_pred_if_binary = np.where(y_pred_if == 1, 1, 0)
    
    for name, pipe, pred_binary in [("One-Class SVM", oc_svm_pipeline, y_pred_oc_binary), ("Isolation Forest", if_pipeline, y_pred_if_binary)]:
        acc = accuracy_score(y_test, pred_binary)
        prec = precision_score(y_test, pred_binary, zero_division=0)
        rec = recall_score(y_test, pred_binary, zero_division=0)
        f1 = f1_score(y_test, pred_binary, zero_division=0)
        
        tn, fp, fn, tp = confusion_matrix(y_test, pred_binary, labels=[0, 1]).ravel()
        far = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        frr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        
        comparison_results[name] = {
            "accuracy": float(acc * 100),
            "precision": float(prec * 100),
            "recall": float(rec * 100),
            "f1_score": float(f1 * 100),
            "far": float(far * 100),
            "frr": float(frr * 100),
            "eer": float((far + frr) / 2.0 * 100),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "roc_curve": {"fpr": [0.0, float(far), 1.0], "tpr": [0.0, float(rec), 1.0]}
        }

    # If supervised model is chosen as best, we retrain it on all data and serialize it
    # We retrain the best pipeline on the entire dataset
    best_pipeline.fit(X, y)
    
    # Save the pipeline to bytes
    import io
    buffer = io.BytesIO()
    joblib.dump(best_pipeline, buffer)
    model_bytes = buffer.getvalue()

    return {
        "best_model_name": best_model_name,
        "model_bytes": model_bytes,
        "metrics": comparison_results
    }

def calculate_baseline_statistics(user_samples: List[Any]) -> Dict[str, Any]:
    """
    Computes the baseline profile (mean and std dev vectors) for a user based on their 10 samples.
    Used for simple distance-based similarity calculations.
    """
    holds_list = []
    flights_list = []
    latencies_list = []
    speeds = []
    
    for sample in user_samples:
        holds_list.append(json.loads(sample.hold_times_json))
        flights_list.append(json.loads(sample.flight_times_json))
        latencies_list.append(json.loads(sample.latencies_json))
        speeds.append(sample.typing_speed)
        
    return {
        "mean_hold": np.mean(holds_list, axis=0).tolist(),
        "std_hold": np.std(holds_list, axis=0).tolist(),
        "mean_flight": np.mean(flights_list, axis=0).tolist(),
        "std_flight": np.std(flights_list, axis=0).tolist(),
        "mean_latency": np.mean(latencies_list, axis=0).tolist(),
        "std_latency": np.std(latencies_list, axis=0).tolist(),
        "mean_speed": float(np.mean(speeds)),
        "std_speed": float(np.std(speeds))
    }
