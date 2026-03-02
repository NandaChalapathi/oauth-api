from flask import Flask, request, jsonify
import numpy as np
import pandas as pd
import joblib as jb

app = Flask(__name__)

# ==============================
# Load Models and Files (Once)
# ==============================

threshold = np.load("threshold.npy")
iForest_Score_Train = np.load("iForest_Score_Train.npy")
LOF_Score_Train = np.load("LOF_Score_Train.npy")

iForest = jb.load("Final Copy/Model/IsolationForest_v1.pkl")
LOF = jb.load("Final Copy/Model/LocalOutlierFactor_v1.pkl")
RobuScaler = jb.load("Final Copy/Model/RobustScaler_LOF.pkl")

# ==============================
# Core Functions
# ==============================

def scale_data(data):
    return RobuScaler.transform(data)

def decision_function(raw_data, scaled_data):
    iForest_score = -iForest.decision_function(raw_data)[0]
    LOF_score = -LOF.decision_function(scaled_data)[0]
    return iForest_score, LOF_score

def normalize_scores(iForest_score, LOF_score):
    iForest_per = (iForest_Score_Train < iForest_score).mean()
    LOF_per = (LOF_Score_Train < LOF_score).mean()
    return iForest_per, LOF_per

def ensemble_score(iForest_per, LOF_per):
    return (0.6 * iForest_per + 0.4 * LOF_per)

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

        # Step 1: Scale
        scaled = scale_data(df)

        # Step 2: Decision Scores
        iForest_score, LOF_score = decision_function(df, scaled)

        # Step 3: Normalize
        iForest_per, LOF_per = normalize_scores(iForest_score, LOF_score)

        # Step 4: Ensemble
        score = ensemble_score(iForest_per, LOF_per)

        # Step 5: Label + Risk
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
    app.run(debug=True)
