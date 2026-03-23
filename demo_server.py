
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import random
import copy

app = FastAPI(title="AEGIS C4ISR API - Demo Mode")

# Module-level poll counter to drive score mutation
_poll_count = 0

# Seed EnrichedThreat objects with varied severity and ai_confidence
_SEED_THREATS = [
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
        "detected_at": "2026-03-17T13:00:00Z",
        "pattern_id": "PAT-001",
        "confidence_breakdown": {
            "radar_classification": {"score": 0.96, "sensor": "RADAR-A"},
            "visual_recognition":   {"score": 0.91, "sensor": "CAM-3"},
            "behavioral_analysis":  {"score": 0.88, "sensor": "ANALYTICS"},
            "signal_intelligence":  {"score": None,  "sensor": "SIGINT-1"}
        }
    },
    {
        "threat_id": "THR-002",
        "threat_type": "PERSONNEL",
        "severity": "HIGH",
        "lat": 34.0560,
        "lng": -118.2680,
        "sector": "3A",
        "ai_confidence": 0.76,
        "sensor_source": "CAM-3",
        "status": "ACTIVE",
        "detected_at": "2026-03-17T13:02:00Z",
        "pattern_id": "PAT-001",
        "confidence_breakdown": {
            "radar_classification": {"score": 0.72, "sensor": "RADAR-A"},
            "visual_recognition":   {"score": 0.81, "sensor": "CAM-3"},
            "behavioral_analysis":  {"score": 0.74, "sensor": "ANALYTICS"},
            "signal_intelligence":  {"score": 0.70, "sensor": "SIGINT-1"}
        }
    },
    {
        "threat_id": "THR-003",
        "threat_type": "AIRCRAFT",
        "severity": "CRITICAL",
        "lat": 34.0610,
        "lng": -118.2750,
        "sector": "4B",
        "ai_confidence": 0.89,
        "sensor_source": "RADAR-B",
        "status": "ACTIVE",
        "detected_at": "2026-03-17T13:05:00Z",
        "pattern_id": "PAT-002",
        "confidence_breakdown": {
            "radar_classification": {"score": 0.93, "sensor": "RADAR-B"},
            "visual_recognition":   {"score": 0.85, "sensor": "CAM-7"},
            "behavioral_analysis":  {"score": 0.88, "sensor": "ANALYTICS"},
            "signal_intelligence":  {"score": 0.82, "sensor": "SIGINT-2"}
        }
    },
    {
        "threat_id": "THR-004",
        "threat_type": "VESSEL",
        "severity": "MEDIUM",
        "lat": 34.0490,
        "lng": -118.2600,
        "sector": "2C",
        "ai_confidence": 0.55,
        "sensor_source": "SIGINT-1",
        "status": "ACTIVE",
        "detected_at": "2026-03-17T13:08:00Z",
        "pattern_id": "PAT-002",
        "confidence_breakdown": {
            "radar_classification": {"score": 0.50, "sensor": "RADAR-A"},
            "visual_recognition":   {"score": None,  "sensor": "CAM-1"},
            "behavioral_analysis":  {"score": 0.60, "sensor": "ANALYTICS"},
            "signal_intelligence":  {"score": 0.58, "sensor": "SIGINT-1"}
        }
    },
    {
        "threat_id": "THR-005",
        "threat_type": "UNKNOWN",
        "severity": "LOW",
        "lat": 34.0450,
        "lng": -118.2550,
        "sector": "1D",
        "ai_confidence": 0.32,
        "sensor_source": "CAM-2",
        "status": "ACTIVE",
        "detected_at": "2026-03-17T13:10:00Z",
        "pattern_id": "PAT-002",
        "confidence_breakdown": {
            "radar_classification": {"score": 0.28, "sensor": "RADAR-A"},
            "visual_recognition":   {"score": 0.35, "sensor": "CAM-2"},
            "behavioral_analysis":  {"score": None,  "sensor": "ANALYTICS"},
            "signal_intelligence":  {"score": None,  "sensor": "SIGINT-1"}
        }
    }
]

# Mutable working copy of threats (scores mutate on each poll)
_active_threats = copy.deepcopy(_SEED_THREATS)

_THREAT_PATTERNS = [
    {
        "pattern_id": "PAT-001",
        "pattern_name": "COORDINATED ARMOR ADVANCE",
        "threat_ids": ["THR-001", "THR-002"],
        "aggregate_confidence": 0.85,
        "contains_critical": True,
        "centroid_lat": 34.0574,
        "centroid_lng": -118.2691
    },
    {
        "pattern_id": "PAT-002",
        "pattern_name": "MULTI-DOMAIN INCURSION",
        "threat_ids": ["THR-003", "THR-004", "THR-005"],
        "aggregate_confidence": 0.59,
        "contains_critical": True,
        "centroid_lat": 34.0517,
        "centroid_lng": -118.2633
    }
]

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

@app.get("/api/v1/threats/active")
async def get_active_threats():
    global _poll_count, _active_threats
    _poll_count += 1
    for threat in _active_threats:
        delta = random.uniform(-0.05, 0.05)
        threat["ai_confidence"] = max(0.0, min(1.0, threat["ai_confidence"] + delta))
    return _active_threats

@app.get("/api/v1/threats/patterns")
async def get_threat_patterns():
    return _THREAT_PATTERNS

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
