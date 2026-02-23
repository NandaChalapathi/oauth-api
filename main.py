from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
import os
import uuid
import time
import math

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT"))
    )

# ---------------- HEALTH ROUTE ----------------
@app.get("/")
def health():
    return {"status": "running"}

# ---------------- REQUEST MODEL ----------------
class AuthRequest(BaseModel):
    userId: str | None = None
    email: str | None = None
    password: str
    action: str
    session_id: str | None = None
    device_id: str | None = None


# =====================================================
# ================= FEATURE FUNCTIONS =================
# =====================================================

def insert_login_event(cur, conn, user_id, session_id, device_id):
    now_ts = int(time.time() * 1000)
    cur.execute("""
        INSERT INTO user_session_events (
            user_id, session_id, device_id,
            event_type, event_ts
        ) VALUES (%s,%s,%s,%s,%s)
    """, (
        user_id,
        session_id,
        device_id,
        "login_success",
        now_ts
    ))
    conn.commit()


def get_device_count(cur, user_id):
    cur.execute("""
        SELECT COUNT(DISTINCT device_id)
        FROM user_session_events
        WHERE user_id=%s
    """, (user_id,))
    return cur.fetchone()[0] or 0


def get_session_duration(cur, session_id):
    cur.execute("""
        SELECT (MAX(event_ts) - MIN(event_ts))/1000
        FROM user_session_events
        WHERE session_id=%s
    """, (session_id,))
    result = cur.fetchone()[0]
    return result or 0


def get_avg_session_duration(cur):
    cur.execute("""
        SELECT AVG(duration) FROM (
            SELECT (MAX(event_ts) - MIN(event_ts))/1000 AS duration
            FROM user_session_events
            GROUP BY session_id
        ) t
    """)
    result = cur.fetchone()[0]
    return result or 0


def get_last_24h_logins(cur, user_id):
    cur.execute("""
        SELECT COUNT(*)
        FROM user_session_events
        WHERE user_id=%s
          AND event_type IN ('login_success','login_failed')
          AND received_at > NOW() - INTERVAL 24 HOUR
    """, (user_id,))
    return cur.fetchone()[0] or 0


def get_failed_login_ratio(cur, user_id):
    cur.execute("""
        SELECT
          SUM(event_type='login_failed') / NULLIF(COUNT(*),0)
        FROM user_session_events
        WHERE user_id=%s
          AND event_type IN ('login_success','login_failed')
          AND received_at > NOW() - INTERVAL 1 HOUR
    """, (user_id,))
    result = cur.fetchone()[0]
    return float(result) if result else 0


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) ** 2
    )
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def get_geo_jump(cur, user_id):
    cur.execute("""
        SELECT latitude, longitude
        FROM user_session_events
        WHERE user_id=%s AND latitude IS NOT NULL
        ORDER BY received_at DESC
        LIMIT 2
    """, (user_id,))
    rows = cur.fetchall()
    if len(rows) == 2:
        return haversine(
            rows[0][0], rows[0][1],
            rows[1][0], rows[1][1]
        )
    return 0.0


def get_api_rate_1min(cur, user_id):
    cur.execute("""
        SELECT COUNT(*)
        FROM user_session_events
        WHERE user_id=%s
          AND event_type='api_call'
          AND received_at > NOW() - INTERVAL 1 MINUTE
    """, (user_id,))
    return cur.fetchone()[0] or 0


def get_api_rate_7d(cur, user_id):
    cur.execute("""
        SELECT COUNT(*) / 7
        FROM user_session_events
        WHERE user_id=%s
          AND event_type='api_call'
          AND received_at > NOW() - INTERVAL 7 DAY
    """, (user_id,))
    result = cur.fetchone()[0]
    return result or 0


# ---------------- INSERT INTO RISK TABLE ----------------
def insert_risk_features(cur, conn, user_id, features):
    cur.execute("""
        INSERT INTO user_risk_features (
            user_id,
            device_count,
            avg_session_duration_sec,
            session_duration_perId_sec,
            last_24hrs_logins,
            failed_login_ratio,
            geo_jump_km,
            api_rate,
            api_rate_7d,
            calculated_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
    """, (
        user_id,
        features["device_count"],
        features["avg_session_duration"],
        features["session_duration"],
        features["last_24h_logins"],
        features["failed_login_ratio"],
        features["geo_jump_km"],
        features["api_rate_1min"],
        features["api_rate_7d_avg"]
    ))
    conn.commit()


# =====================================================
# ================= AUTH ENDPOINT =====================
# =====================================================

@app.post("/auth")
def auth(data: AuthRequest):

    conn = get_db()
    cur = conn.cursor()

    # ---------------- REGISTER ----------------
    if data.action == "register":

        if not data.email:
            raise HTTPException(status_code=400, detail="Email required")

        try:
            cur.execute("""
                INSERT INTO WebsiteUsers (email, password, created_at, isEmailSent)
                VALUES (%s, %s, NOW(), 0)
            """, (
                data.email,
                data.password
            ))

            conn.commit()

            new_id = cur.lastrowid
            generated_user_id = f"P-U{new_id:04d}"

            cur.execute("""
                UPDATE WebsiteUsers
                SET username = %s
                WHERE id = %s
            """, (
                generated_user_id,
                new_id
            ))

            conn.commit()

            cur.close()
            conn.close()

            return {
                "success": True,
                "user_id": generated_user_id
            }

        except Exception:
            cur.close()
            conn.close()
            return {"success": False}

    # ---------------- LOGIN ----------------
    elif data.action == "login":

        if not data.userId:
            raise HTTPException(status_code=400, detail="User ID required")

        cur.execute("""
            SELECT password FROM WebsiteUsers WHERE username=%s
        """, (data.userId,))

        user = cur.fetchone()

        if user and data.password == user[0]:

            session_id = data.session_id or str(uuid.uuid4())
            device_id = data.device_id or "web_device"

            insert_login_event(cur, conn, data.userId, session_id, device_id)

            features = {
                "device_count": get_device_count(cur, data.userId),
                "session_duration": get_session_duration(cur, session_id),
                "avg_session_duration": get_avg_session_duration(cur),
                "last_24h_logins": get_last_24h_logins(cur, data.userId),
                "failed_login_ratio": get_failed_login_ratio(cur, data.userId),
                "geo_jump_km": get_geo_jump(cur, data.userId),
                "api_rate_1min": get_api_rate_1min(cur, data.userId),
                "api_rate_7d_avg": get_api_rate_7d(cur, data.userId),
            }

            insert_risk_features(cur, conn, data.userId, features)

            cur.close()
            conn.close()

            return {
                "success": True,
                "features": features
            }

        cur.close()
        conn.close()
        return {"success": False}

    else:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid action")
