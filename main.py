import os
import numpy as np
import requests
from dotenv import load_dotenv; load_dotenv(".env")
import warnings; warnings.filterwarnings("ignore")
import psycopg2
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates 
templates = Jinja2Templates(directory="templates") 

DATABASE_URL = os.getenv("DATABASE_URL")
app = FastAPI()
@app.on_event("startup")
def startup():
    create_table()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
 
def create_table():
    conn = getConnection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_session (
        id SERIAL PRIMARY KEY,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id VARCHAR(100),
        event_type VARCHAR(50),
        session_id VARCHAR(120),
        device_id VARCHAR(120)
    );
    """)
    conn.commit()
    cursor.close()
    conn.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AuthEvent(BaseModel):
    action: str
    userId: Optional[str] = None
    email: Optional[str] = None
    password: str
    session_id: str
    device_id: str
    event_ts: int

def getConnection():
    return psycopg2.connect(DATABASE_URL)

def insertRecord(userId, session_id, device_id, latitude, longitude, evt):
    conn = getConnection()
    cursor = conn.cursor()
    query = """
    INSERT INTO user_session
    (user_id, session_id, device_id, latitude, longitude, event_type, event_time)
    VALUES (%s,%s,%s,%s,%s,%s,NOW())
    """
    cursor.execute(
        query,
        (userId, session_id, device_id, latitude, longitude, evt)
    )
    conn.commit()
    cursor.close()
    conn.close()

def event_type():
    r = round(np.random.rand(), 1)
    return "LOGIN_SUCCESS" if r <= 0.5 else "LOGIN_FAILED"

@app.get("/home")
def health():
    return {"message": "API Running"}

@app.post("/event")
async def receive_event(data: AuthEvent, request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0] if forwarded else request.client.host
    base_url = os.getenv("URL")
    url = f"{base_url}{ip}"
    geo = requests.get(url).json()
    latitude = geo.get("lat")
    longitude = geo.get("lon")
    evt = event_type()
    user = data.userId if data.userId else data.email
    insertRecord(
        user,
        data.session_id,
        data.device_id,
        latitude,
        longitude,
        evt
    )
    return {
        "success": evt == "LOGIN_SUCCESS",
        "event_type": evt
    }
