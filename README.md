# AEGIS C4ISR Unified Command Platform

**Military-Grade Command, Control, Communications, Computers, Intelligence, Surveillance & Reconnaissance Platform**

[![Classification](https://img.shields.io/badge/CLASSIFICATION-TOP%20SECRET-red?style=for-the-badge)](.)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](.)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?style=for-the-badge&logo=fastapi)](.)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=for-the-badge&logo=postgresql)](.)
[![InfluxDB](https://img.shields.io/badge/InfluxDB-2.7-blue?style=for-the-badge)](.)
[![Redis](https://img.shields.io/badge/Redis-7-red?style=for-the-badge&logo=redis)](.)

---

## 🛡️ Overview

AEGIS C4ISR is a production-grade, military-specification unified command and control platform designed for modern warfare operations. It integrates real-time GPS tracking, AI-powered threat detection, secure encrypted communications, autonomous drone control, comprehensive analytics, and advanced cyber security monitoring into a single cohesive system.

### Key Capabilities

- **🗺️ Real-Time Tactical Mapping** — SVG-based tactical map with live GPS tracking, unit positioning, and threat visualization
- **⚠️ AI Threat Detection** — YOLOv8-powered threat classification with confidence scoring and automated alerts
- **🔒 Secure Communications** — AES-256-GCM encrypted messaging with TOTP/MFA authentication
- **🚁 Autonomous Drone Control** — MAVLink integration for real-time drone telemetry and mission planning
- **📊 Advanced Analytics** — Time-series analysis with InfluxDB for operational intelligence
- **🛡️ Cyber Security** — Real-time intrusion detection, threat blocking, and security event monitoring

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX REVERSE PROXY                     │
│              (TLS 1.3, Rate Limiting, Load Balancing)           │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│  Frontend (HTML) │            │   FastAPI API    │
│   Dark Tactical  │◄───────────┤   (4 Workers)    │
│   UI Interface   │  WebSocket │   uvloop/httptools│
└──────────────────┘            └────────┬─────────┘
                                         │
                 ┌───────────────────────┼───────────────────────┐
                 │                       │                       │
                 ▼                       ▼                       ▼
        ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
        │   PostgreSQL   │    │    InfluxDB    │    │     Redis      │
        │  (Relational)  │    │ (Time-Series)  │    │ (Cache/PubSub) │
        │                │    │                │    │                │
        │ • Users        │    │ • GPS Track    │    │ • Sessions     │
        │ • Units        │    │ • Sensor Data  │    │ • Live GPS     │
        │ • Threats      │    │ • Threat Events│    │ • Rate Limits  │
        │ • Drones       │    │ • Cyber Events │    │ • PubSub       │
        │ • Messages     │    │                │    │                │
        │ • Audit Logs   │    │                │    │                │
        └────────────────┘    └────────────────┘    └────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    External Integrations                       │
├────────────────────────────────────────────────────────────────┤
│  Kafka (Event Streaming)  │  MAVLink (Drones)  │  YOLOv8 (AI) │
└────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
aegis-c4isr/
├── app/
│   ├── core/
│   │   ├── config.py              # Environment configuration
│   │   ├── database.py            # PostgreSQL async engine
│   │   ├── redis_client.py        # Redis operations
│   │   └── security.py            # JWT, AES, TOTP, RBAC
│   ├── models/
│   │   └── models.py              # SQLAlchemy ORM models (11 tables)
│   ├── routers/
│   │   ├── auth.py                # Authentication & MFA
│   │   ├── units.py               # Unit tracking & GPS
│   │   ├── threats.py             # Threat detection & management
│   │   ├── drones.py              # Drone control & telemetry
│   │   ├── comms.py               # Encrypted communications
│   │   ├── analytics.py           # Metrics & time-series data
│   │   ├── cyber.py               # Cyber security events
│   │   └── sensors.py             # Sensor data ingestion
│   ├── services/
│   │   └── mavlink_service.py     # MAVLink drone manager
│   ├── middleware/
│   │   ├── auth_middleware.py     # JWT validation
│   │   └── audit_logger.py        # Tamper-evident logging
│   └── main.py                    # FastAPI application
├── docker/
│   ├── Dockerfile                 # Multi-stage production build
│   └── nginx.conf                 # Nginx reverse proxy config
├── frontend/
│   └── index.html                 # Single-page tactical UI
├── scripts/
│   └── init.sql                   # Database initialization
├── docker-compose.yml             # Full stack orchestration
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

---

## 🚀 Quick Start

### Prerequisites

- Docker 24+ and Docker Compose 2.20+
- Python 3.11+ (for local development)
- OpenSSL (for certificate generation)
- 8GB RAM minimum, 16GB recommended

### 1. Clone Repository

```bash
git clone https://github.com/your-org/aegis-c4isr.git
cd aegis-c4isr
```

### 2. Generate Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` and configure:
- `POSTGRES_PASSWORD` — Strong database password
- `INFLUX_TOKEN` — Generate with: `openssl rand -hex 32`
- `REDIS_PASSWORD` — Strong Redis password
- `JWT_SECRET_KEY` — Generate with: `openssl rand -hex 32`
- `AES_KEY` — Exactly 32 characters for AES-256

### 3. Generate SSL Certificates

```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/nginx.key -out certs/nginx.crt \
  -subj "/C=US/ST=VA/L=DC/O=AEGIS/CN=localhost"
```

### 4. Launch Full Stack

```bash
docker-compose up --build -d
```

This will start:
- PostgreSQL on port 5432 (internal)
- InfluxDB on port 8086 (internal)
- Redis on port 6379 (internal)
- FastAPI on port 8000
- Nginx on ports 80/443

### 5. Access Platform

- **Frontend UI**: https://localhost
- **API Documentation**: https://localhost/docs
- **Health Check**: https://localhost/api/health

### 6. Default Credentials

```
Username: CDR.ADMIN
Password: AEGIS@Command2026!
```

**⚠️ CRITICAL: Change this password immediately in production!**

---

## 🔐 Role-Based Access Control (RBAC)

| Role | Clearance | Access |
|------|-----------|--------|
| **COMMANDER** | TOP SECRET | Full admin access, user management, all operations |
| **OPERATOR** | SECRET | Map tracking, threat response, comms, drone control |
| **ANALYST** | CONFIDENTIAL | Threat analysis, intel reports, read-only access |
| **VIEWER** | UNCLASSIFIED | Basic map viewing, analytics dashboard |

### Permission Matrix

| Permission | Commander | Operator | Analyst | Viewer |
|------------|-----------|----------|---------|--------|
| `admin:*` | ✅ | ❌ | ❌ | ❌ |
| `users:*` | ✅ | ❌ | ❌ | ❌ |
| `map:rw` | ✅ | ✅ | ❌ | ❌ |
| `map:r` | ✅ | ✅ | ✅ | ✅ |
| `threats:rw` | ✅ | ✅ | ❌ | ❌ |
| `threats:r` | ✅ | ✅ | ✅ | ❌ |
| `comms:rw` | ✅ | ✅ | ❌ | ❌ |
| `comms:r` | ✅ | ✅ | ✅ | ❌ |
| `drones:rw` | ✅ | ✅ | ❌ | ❌ |
| `analytics:rw` | ✅ | ❌ | ❌ | ❌ |
| `analytics:r` | ✅ | ✅ | ✅ | ✅ |
| `cyber:rw` | ✅ | ❌ | ❌ | ❌ |
| `cyber:r` | ✅ | ✅ | ✅ | ❌ |

---

## 📡 API Reference

### Authentication

#### `POST /api/v1/auth/login`
Authenticate with callsign, password, and optional TOTP.

**Request:**
```json
{
  "callsign": "CDR.ADMIN",
  "password": "AEGIS@Command2026!",
  "totp_code": "123456"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "callsign": "CDR.ADMIN",
  "role": "COMMANDER",
  "clearance": "TOP SECRET",
  "permissions": ["admin:*", "users:*", ...]
}
```

#### `POST /api/v1/auth/refresh`
Generate new access token from refresh token.

#### `POST /api/v1/auth/logout`
Invalidate current session.

#### `GET /api/v1/auth/me`
Get current user profile.

#### `POST /api/v1/auth/register` (COMMANDER only)
Register new user account.

#### `POST /api/v1/auth/mfa/enable`
Enable multi-factor authentication.

---

### Unit Tracking

#### `POST /api/v1/units/{unit_id}/position`
Update unit GPS position (writes to Redis, InfluxDB, PostgreSQL).

**Request:**
```json
{
  "lat": 34.0522,
  "lng": -118.2437,
  "altitude_m": 120.5,
  "heading_deg": 45.0,
  "speed_kmh": 25.0,
  "battery_pct": 87.0
}
```

#### `GET /api/v1/units/{unit_id}/track?hours=24`
Get historical GPS track from InfluxDB.

#### `GET /api/v1/units/`
List all active units.

#### `WebSocket /api/v1/units/stream/live`
Real-time GPS position updates via Redis PubSub.

---

### Threat Detection

#### `POST /api/v1/threats/`
Create new threat detection.

**Request:**
```json
{
  "threat_type": "VEHICLE",
  "severity": "CRITICAL",
  "lat": 34.0588,
  "lng": -118.2701,
  "sector": "3A",
  "ai_confidence": 0.94,
  "ai_model": "YOLOv8",
  "sensor_source": "RADAR-A",
  "description": "Hostile vehicle convoy detected"
}
```

#### `GET /api/v1/threats/?severity=CRITICAL&status=ACTIVE&limit=100`
List threats with filters.

#### `GET /api/v1/threats/active`
Get active threats from Redis cache.

#### `PATCH /api/v1/threats/{threat_id}/resolve`
Mark threat as resolved/neutralized.

---

### Drone Control

#### `GET /api/v1/drones/`
List all drones with status.

#### `POST /api/v1/drones/{drone_id}/command`
Send command to drone (ARM, DISARM, TAKEOFF, LAND, RTH, GOTO, MODE, SPEED).

**Request:**
```json
{
  "command": "GOTO",
  "lat": 34.0522,
  "lng": -118.2437,
  "altitude": 100.0
}
```

#### `POST /api/v1/drones/mission`
Create and upload drone mission with waypoints.

**Request:**
```json
{
  "drone_id": "UAV-01",
  "name": "RECON-Alpha-1",
  "mission_type": "RECON",
  "waypoints": [
    {"lat": 34.0522, "lng": -118.2437, "alt": 100},
    {"lat": 34.0588, "lng": -118.2567, "alt": 120}
  ]
}
```

#### `WebSocket /api/v1/drones/{drone_id}/stream`
Real-time drone telemetry stream.

---

### Secure Communications

#### `GET /api/v1/comms/channels`
List all communication channels.

#### `POST /api/v1/comms/send`
Send AES-256 encrypted message.

**Request:**
```json
{
  "channel_id": "uuid",
  "plaintext": "All units maintain radio silence",
  "classification": "SECRET"
}
```

#### `GET /api/v1/comms/{channel_id}/messages?limit=50`
Get decrypted messages from channel.

---

### Analytics

#### `GET /api/v1/analytics/gps/history?unit_id=ALPHA-1&hours=24`
Get GPS history from InfluxDB.

#### `GET /api/v1/analytics/threats/stats`
Get threat statistics by severity.

#### `GET /api/v1/analytics/system/health`
Get real-time system metrics (CPU, Memory, Disk, Network).

#### `GET /api/v1/analytics/missions/summary`
Get mission statistics summary.

---

### Cyber Security

#### `POST /api/v1/cyber/event`
Log cyber security event.

#### `GET /api/v1/cyber/events?severity=CRITICAL&limit=100`
List recent cyber events.

#### `POST /api/v1/cyber/block-ip`
Block IP address with optional expiration.

**Request:**
```json
{
  "ip_address": "185.220.101.45",
  "reason": "SQL injection attempt detected",
  "expires_hours": 24
}
```

#### `GET /api/v1/cyber/blocked-ips`
List all blocked IP addresses.

#### `DELETE /api/v1/cyber/unblock-ip/{ip_address}`
Remove IP from block list.

#### `GET /api/v1/cyber/stats`
Get cyber security statistics.

---

### Sensors

#### `POST /api/v1/sensors/reading`
Log single sensor reading to InfluxDB.

#### `POST /api/v1/sensors/reading/batch`
Log multiple sensor readings (max 1000).

#### `POST /api/v1/sensors/radar/contact`
Log radar contact detection.

#### `GET /api/v1/sensors/history/{sensor_id}?hours=24`
Get sensor history from InfluxDB.

---

## 🚁 Drone Integration (MAVLink)

### SITL Simulator Setup

```bash
# Install ArduPilot SITL
git clone https://github.com/ArduPilot/ardupilot.git
cd ardupilot
./Tools/environment_install/install-prereqs-ubuntu.sh -y

# Launch copter simulator
cd ArduCopter
sim_vehicle.py -v ArduCopter --console --map
```

### Python Client Example

```python
import requests
import websockets
import asyncio

API_URL = "https://localhost/api/v1"
TOKEN = "your_access_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

# Send drone command
response = requests.post(
    f"{API_URL}/drones/UAV-01/command",
    json={"command": "TAKEOFF", "altitude": 50.0},
    headers=headers,
    verify=False
)
print(response.json())

# Stream drone telemetry
async def stream_telemetry():
    uri = "wss://localhost/api/v1/drones/UAV-01/stream"
    async with websockets.connect(uri, extra_headers=headers) as ws:
        async for message in ws:
            print(message)

asyncio.run(stream_telemetry())
```

---

## 📊 InfluxDB Flux Query Examples

### GPS Track Query

```flux
from(bucket: "gps_telemetry")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "gps_telemetry")
  |> filter(fn: (r) => r["unit_id"] == "ALPHA-1")
  |> filter(fn: (r) => r["_field"] == "lat" or r["_field"] == "lng")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
```

### Threat Events Query

```flux
from(bucket: "threat_events")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "threat_events")
  |> filter(fn: (r) => r["severity"] == "CRITICAL")
  |> group(columns: ["threat_type"])
  |> count()
```

### Sensor Aggregation Query

```flux
from(bucket: "sensor_data")
  |> range(start: -1h)
  |> filter(fn: (r) => r["sensor_type"] == "RADAR")
  |> aggregateWindow(every: 5m, fn: mean)
```

---

## 🔒 Security Pre-Deployment Checklist

- [ ] **Change all default passwords** (PostgreSQL, Redis, InfluxDB, default user)
- [ ] **Rotate JWT_SECRET_KEY** using `openssl rand -hex 32`
- [ ] **Rotate AES_KEY** (exactly 32 characters)
- [ ] **Generate production SSL certificates** (not self-signed)
- [ ] **Enable MFA for all COMMANDER accounts**
- [ ] **Configure firewall rules** (block all except 80/443)
- [ ] **Enable audit logging** to secure syslog server
- [ ] **Configure backup strategy** (PostgreSQL, InfluxDB)
- [ ] **Enable PostgreSQL row-level security** (RLS)
- [ ] **Review and restrict ALLOWED_ORIGINS** in .env
- [ ] **Enable rate limiting** on Nginx
- [ ] **Configure Kafka authentication** (SASL/SSL)
- [ ] **Scan container images** for vulnerabilities
- [ ] **Enable WAF** (Web Application Firewall)
- [ ] **Configure IDS/IPS** integration
- [ ] **Document incident response procedures**

---

## 🧪 Development

### Local Setup (Without Docker)

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start databases (Docker Compose for just databases)
docker-compose up postgres influxdb redis kafka -d

# Run application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Tests

```bash
pytest tests/ -v --cov=app --cov-report=html
```

### Code Quality

```bash
# Linting
flake8 app/
black app/ --check

# Type checking
mypy app/
```

---

## 📈 Performance Tuning

### PostgreSQL

```sql
-- Increase shared_buffers
ALTER SYSTEM SET shared_buffers = '4GB';

-- Enable parallel queries
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;

-- Optimize for SSD
ALTER SYSTEM SET random_page_cost = 1.1;
```

### InfluxDB

```bash
# Increase cache size
influx config set --host http://localhost:8086 \
  --token YOUR_TOKEN \
  --org aegis_command \
  cache-max-memory-size 1GB
```

### Redis

```bash
# Increase max memory
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## 🐛 Troubleshooting

### Database Connection Errors

```bash
# Check PostgreSQL logs
docker logs aegis-postgres

# Test connection
docker exec -it aegis-postgres psql -U aegis_admin -d aegis_c4isr
```

### InfluxDB Token Issues

```bash
# Create new token
docker exec -it aegis-influxdb \
  influx auth create --org aegis_command --all-access
```

### Redis Connection Failed

```bash
# Test Redis connectivity
docker exec -it aegis-redis redis-cli -a YOUR_PASSWORD ping
```

### MAVLink Connection Timeout

```bash
# Check firewall
sudo ufw allow 14550/udp

# Test MAVLink SITL
sim_vehicle.py -v ArduCopter -L YourLocation --console --map
```

---

## 📝 License

**CLASSIFIED - GOVERNMENT USE ONLY**

This software is classified TOP SECRET and is restricted to authorized personnel only. Unauthorized access, use, or distribution is strictly prohibited and may result in severe criminal and civil penalties.

---

## 🤝 Support

For technical support, operational issues, or security incidents:

- **Emergency**: Contact SOC (Security Operations Center) immediately
- **Technical Support**: support@aegis.mil (Unclassified systems only)
- **Security Incidents**: security@aegis.mil + Report via secure channel

---

## 🏆 Credits

Developed with **Claude Opus 4.6** — Anthropic's most capable AI model
Built for operational excellence in modern C4ISR environments

**Classification**: TOP SECRET//NOFORN
**Version**: 1.0.0
**Last Updated**: 2026-03-17

---

**⚠️ WARNING: This system contains classified information. Unauthorized access is prohibited. All activity is monitored and logged.**
