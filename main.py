from fastapi import FastAPI, Request
import requests
import os
from dotenv import load_dotenv; load_dotenv(".env")
import psycopg2 

app = FastAPI()
DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/health")
def heath():
    return {"status":"OK"}

@app.get("/")
async def get_location(request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0] if forwarded else request.client.host
    base_url = os.getenv("URL")
    url = f"{base_url}{ip}"
    response = requests.get(url).json()
    ip=ip
    city=response.get("city")
    country=response.get("country")
    latitude=response.get("lat")
    longitude=response.get("lon")
    insert_location(ip, latitude, longitude, city, country)
    return {"status":"OK"}

def getConnection():
    return psycopg2.connect(DATABASE_URL)

def insert_location(ip_address, latitude, longitude, city, country):
    conn = getConnection()
    cursor = conn.cursor()
    query = """
    INSERT INTO ip_locations
    (ip_address, latitude, longitude, city, country)
    VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (ip_address, latitude, longitude, city, country))
    conn.commit()
    cursor.close()
    conn.close()
    print("Location inserted successfully")