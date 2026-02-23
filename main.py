from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import mysql.connector
import os

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your domain in production
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

# ---------------- REQUEST MODEL ----------------
class AuthRequest(BaseModel):
    userId: str | None = None
    email: str | None = None
    password: str
    action: str


# ---------------- AUTH ENDPOINT ----------------
@app.get("/")
def health():
    return {"status": "running"}
@app.post("/auth")
def auth(data: AuthRequest):

    conn = get_db()
    cur = conn.cursor()

    # -------- REGISTER --------
    if data.action == "register":

        if not data.email:
            raise HTTPException(status_code=400, detail="Email required")

        try:
            # Insert user (id auto increment)
            cur.execute("""
                INSERT INTO WebsiteUsers (email, password, created_at, isEmailSent)
                VALUES (%s, %s, NOW(), 0)
            """, (
                data.email,
                data.password
            ))

            conn.commit()

            # Get new AUTO_INCREMENT id
            new_id = cur.lastrowid

            # Generate P-U000X format
            generated_user_id = f"P-U{new_id:04d}"

            # Update username column
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

        except Exception as e:
            cur.close()
            conn.close()
            return {"success": False}


    # -------- LOGIN --------
    elif data.action == "login":

        if not data.userId:
            raise HTTPException(status_code=400, detail="User ID required")

        cur.execute("""
            SELECT password FROM WebsiteUsers WHERE username=%s
        """, (data.userId,))

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and data.password == user[0]:
            return {"success": True}

        return {"success": False}

    else:
        cur.close()
        conn.close()

        raise HTTPException(status_code=400, detail="Invalid action")
