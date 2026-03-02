from flask import Flask, request, jsonify
import numpy as np
import pandas as pd
import joblib as jb
import os
app = Flask(__name__)

# ==============================
# Load Model + Files
# ==============================

threshold = np.load("threshold.npy")
iForest_Score_Train = np.load("iForest_Score_Train.npy")

iForest = jb.load("IsolationForest_v1.pkl")


# ==============================
# Core Functions
# ==============================

def decision_function(raw_data):
    # Negative because anomaly → higher score
    return -iForest.decision_function(raw_data)[0]


def normalize_score(iForest_score):
    # Percentile normalization
    return (iForest_Score_Train < iForest_score).mean()


def label_and_risk(score):
    label = -1 if score >= threshold else 1

    if score >= 0.80:
        risk = "High"
    elif score >= 0.60:
        risk = "Medium"
    else:
        risk = "Low"

    return label, risk


# ==============================
# Prediction API
# ==============================

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json

        df = pd.DataFrame({
            "devices_count": [data["devices_count"]],
            "avg_session_duration": [data["avg_session_duration"]],
            "api_rate": [data["api_rate"]],
            "geo_jump_km": [data["geo_jump_km"]],
            "activations_24h": [data["activations_24h"]],
            "failed_login_ratio": [data["failed_login_ratio"]],
            "api_std_7d": [data["api_std_7d"]],
            "session_trend": [data["session_trend"]],
        })

        # Step 1: Get raw anomaly score
        iForest_score = decision_function(df)

        # Step 2: Normalize (0–1)
        score = normalize_score(iForest_score)

        # Step 3: Label + Risk
        label, risk = label_and_risk(score)

        return jsonify({
            "score": round(float(score), 4),
            "label": int(label),
            "risk_level": risk
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# Run Server
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
