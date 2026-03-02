from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pandas as pd
import joblib as jb
import os

app = Flask(__name__)
CORS(app)   # ✅ Enable CORS

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
    return -iForest.decision_function(raw_data)[0]

def normalize_score(iForest_score):
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
# Health Check Endpoint ✅
# ==============================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "API is running",
        "model": "IsolationForest",
        "version": "1.0"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


# ==============================
# Prediction Endpoint
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

        iForest_score = decision_function(df)
        score = normalize_score(iForest_score)
        label, risk = label_and_risk(score)

        return jsonify({
            "score": round(float(score), 4),
            "label": int(label),
            "risk_level": risk
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# Render Production Config
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
