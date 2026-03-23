#!/usr/bin/env python3
"""
AEGIS C4ISR - Local Backend Runner
Runs the FastAPI backend locally without Docker for development/testing
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]}")

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import redis
        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e.name}")
        print("\n📦 Install dependencies with:")
        print("   pip install fastapi uvicorn sqlalchemy redis pydantic pydantic-settings")
        return False

def setup_minimal_env():
    """Setup minimal environment variables for local testing"""
    env = {
        # Disable optional services for local dev
        "DEBUG": "True",
        "ENVIRONMENT": "development",
        "ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,file://",

        # Use SQLite instead of PostgreSQL for local dev
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "aegis_local",
        "POSTGRES_USER": "aegis",
        "POSTGRES_PASSWORD": "local_dev",

        # Dummy InfluxDB config (will fail gracefully if not available)
        "INFLUX_URL": "http://localhost:8086",
        "INFLUX_TOKEN": "dev_token",
        "INFLUX_ORG": "aegis_dev",
        "INFLUX_BUCKET_GPS": "gps",
        "INFLUX_BUCKET_SENSOR": "sensor",
        "INFLUX_BUCKET_THREAT": "threat",
        "INFLUX_BUCKET_CYBER": "cyber",

        # Local Redis (optional)
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "",
        "REDIS_TTL_GPS": "30",
        "REDIS_TTL_THREAT": "300",
        "REDIS_TTL_DRONE": "10",

        # Security (dev keys)
        "JWT_SECRET_KEY": "dev_secret_key_change_in_production",
        "JWT_ALGORITHM": "HS256",
        "JWT_ACCESS_EXPIRE_MINUTES": "60",
        "AES_KEY": "dev_aes_key_32_characters_long!",

        # MFA
        "MFA_REQUIRED": "False",

        # MAVLink
        "MAVLINK_HOST": "0.0.0.0",
        "MAVLINK_PORT": "14550",

        # AI
        "AI_CONFIDENCE_THRESHOLD": "0.65",

        # Kafka (optional)
        "KAFKA_BOOTSTRAP": "localhost:9092",

        # Rate limiting
        "RATE_LIMIT_PER_MINUTE": "1000",
        "RATE_LIMIT_AUTH_PER_MINUTE": "100",

        # Logging
        "LOG_LEVEL": "DEBUG",
    }

    for key, value in env.items():
        os.environ[key] = value

    print("✅ Environment configured for local development")

def create_demo_mode_app():
    """Create a simplified app.py that runs without databases"""
    demo_app = """
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="AEGIS C4ISR API - Demo Mode")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "name": "AEGIS C4ISR",
        "version": "1.0.0",
        "mode": "DEMO",
        "status": "OPERATIONAL"
    }

@app.get("/api/health")
async def health():
    return {"status": "healthy", "mode": "demo"}

# Demo auth endpoint
@app.post("/api/v1/auth/login")
async def login(credentials: dict):
    return {
        "access_token": "demo_token_12345",
        "refresh_token": "demo_refresh",
        "token_type": "bearer",
        "callsign": credentials.get("callsign", "DEMO"),
        "role": "COMMANDER",
        "clearance": "TOP SECRET",
        "permissions": ["admin:*"]
    }

@app.get("/api/v1/auth/me")
async def get_me():
    return {
        "id": "demo-user-id",
        "callsign": "DEMO.USER",
        "role": "COMMANDER",
        "clearance": "TOP SECRET",
        "permissions": ["admin:*"]
    }

# Demo data endpoints
@app.get("/api/v1/units/")
async def get_units():
    return [
        {
            "unit_id": "ALPHA-1",
            "callsign": "ALPHA-1",
            "unit_type": "INFANTRY",
            "sector": "1A",
            "status": "ACTIVE",
            "lat": 34.0522,
            "lng": -118.2437,
            "altitude_m": 120,
            "heading_deg": 45,
            "speed_kmh": 25,
            "battery_pct": 87,
            "last_seen": "2026-03-17T13:00:00Z"
        }
    ]

@app.get("/api/v1/threats/")
async def get_threats():
    return [
        {
            "threat_id": "THR-001",
            "threat_type": "VEHICLE",
            "severity": "CRITICAL",
            "lat": 34.0588,
            "lng": -118.2701,
            "sector": "3A",
            "ai_confidence": 0.94,
            "sensor_source": "RADAR-A",
            "status": "ACTIVE",
            "detected_at": "2026-03-17T13:00:00Z"
        }
    ]

@app.get("/api/v1/drones/")
async def get_drones():
    return [
        {
            "drone_id": "UAV-01",
            "name": "Reaper-1",
            "model": "MQ-9",
            "status": "AIRBORNE",
            "lat": 34.0522,
            "lng": -118.2437,
            "altitude_m": 120,
            "speed_ms": 45,
            "heading_deg": 45,
            "battery_pct": 87,
            "flight_mode": "AUTO",
            "is_armed": False
        }
    ]

@app.get("/api/v1/analytics/system/health")
async def system_health():
    import random
    return {
        "cpu_percent": random.uniform(20, 50),
        "memory_percent": random.uniform(60, 80),
        "disk_percent": 58.0,
        "network_sent_mb": 1247.5,
        "network_recv_mb": 3421.8
    }

if __name__ == "__main__":
    print("=" * 60)
    print("  AEGIS C4ISR - Demo Mode API Server")
    print("=" * 60)
    print("  Backend running without databases")
    print("  Access: http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
"""

    with open("demo_server.py", "w") as f:
        f.write(demo_app)

    print("✅ Created demo_server.py")

def main():
    print("=" * 60)
    print("  AEGIS C4ISR - Local Backend Setup")
    print("=" * 60)
    print()

    # Check Python version
    check_python_version()

    # Check if dependencies are installed
    if not check_dependencies():
        print("\n💡 Quick install:")
        print("   pip install fastapi uvicorn[standard] pydantic")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  Starting DEMO Mode Server")
    print("=" * 60)
    print("  This runs a simplified API without databases")
    print("  Perfect for testing the frontend integration!")
    print("=" * 60)
    print()

    # Create and run demo server
    create_demo_mode_app()

    print("🚀 Starting server...")
    print("   Open frontend: file:///C:/Users/Rudra/OneDrive/Desktop/c4isr/frontend/index.html")
    print()

    try:
        subprocess.run([sys.executable, "demo_server.py"])
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")

if __name__ == "__main__":
    main()
