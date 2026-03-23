#!/bin/bash

# AEGIS C4ISR Quick Start Script
# This script helps you get the AEGIS C4ISR platform running quickly

set -e  # Exit on error

echo "════════════════════════════════════════════════════════"
echo "  AEGIS C4ISR - Unified Command Platform"
echo "  Quick Start Setup"
echo "════════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${CYAN}[1/6] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"
echo ""

# Generate environment file
echo -e "${CYAN}[2/6] Generating environment configuration...${NC}"

if [ -f .env ]; then
    echo -e "${YELLOW}⚠ .env file already exists. Backing up to .env.backup${NC}"
    cp .env .env.backup
fi

# Generate strong secrets
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
INFLUX_TOKEN=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
AES_KEY=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-32)

# Create .env file
cat > .env <<EOF
# AEGIS C4ISR Environment Configuration
# Generated: $(date)

# Application
DEBUG=False
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000,https://localhost

# PostgreSQL Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aegis_c4isr
POSTGRES_USER=aegis_admin
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# InfluxDB
INFLUX_URL=http://influxdb:8086
INFLUX_TOKEN=${INFLUX_TOKEN}
INFLUX_ORG=aegis_command
INFLUX_BUCKET_GPS=gps_telemetry
INFLUX_BUCKET_SENSOR=sensor_data
INFLUX_BUCKET_THREAT=threat_events
INFLUX_BUCKET_CYBER=cyber_events
INFLUX_PASSWORD=${POSTGRES_PASSWORD}

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_TTL_GPS=30
REDIS_TTL_THREAT=300
REDIS_TTL_DRONE=10

# JWT Authentication
JWT_SECRET_KEY=${JWT_SECRET_KEY}
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=7

# AES Encryption
AES_KEY=${AES_KEY}

# MFA
MFA_REQUIRED=True
MFA_ISSUER=AEGIS_C4ISR

# MAVLink
MAVLINK_HOST=0.0.0.0
MAVLINK_PORT=14550
DRONE_TELEMETRY_RATE=10
MAX_DRONES=32
GEOFENCE_DEFAULT_RADIUS=5000

# AI
YOLO_MODEL_PATH=/app/models/yolov8n.pt
AI_CONFIDENCE_THRESHOLD=0.65
AI_DEVICE=cpu

# Kafka
KAFKA_BOOTSTRAP=kafka:9092
KAFKA_TOPIC_GPS=gps.telemetry
KAFKA_TOPIC_THREATS=threat.detected
KAFKA_TOPIC_AUDIT=audit.log
KAFKA_TOPIC_CYBER=cyber.events

# Rate Limiting
RATE_LIMIT_PER_MINUTE=300
RATE_LIMIT_AUTH_PER_MINUTE=10
RATE_LIMIT_API_PER_MINUTE=100

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/aegis/app.log
EOF

echo -e "${GREEN}✓ Environment configuration generated${NC}"
echo -e "${YELLOW}⚠ IMPORTANT: Your secrets have been saved to .env${NC}"
echo ""

# Generate SSL certificates
echo -e "${CYAN}[3/6] Generating SSL certificates...${NC}"

mkdir -p certs

if [ -f certs/nginx.crt ] && [ -f certs/nginx.key ]; then
    echo -e "${YELLOW}⚠ SSL certificates already exist. Skipping...${NC}"
else
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout certs/nginx.key -out certs/nginx.crt \
        -subj "/C=US/ST=VA/L=DC/O=AEGIS/CN=localhost" 2>/dev/null

    echo -e "${GREEN}✓ SSL certificates generated${NC}"
fi
echo ""

# Create required directories
echo -e "${CYAN}[4/6] Creating required directories...${NC}"
mkdir -p models logs
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Build and start services
echo -e "${CYAN}[5/6] Building and starting services...${NC}"
echo -e "${YELLOW}This may take several minutes on first run...${NC}"

docker-compose up --build -d

echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Wait for services to be ready
echo -e "${CYAN}[6/6] Waiting for services to be ready...${NC}"

echo -n "Waiting for API to be healthy..."
for i in {1..30}; do
    if curl -k -s https://localhost/api/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Display summary
echo ""
echo "════════════════════════════════════════════════════════"
echo -e "${GREEN}  AEGIS C4ISR Platform is now running!${NC}"
echo "════════════════════════════════════════════════════════"
echo ""
echo -e "${CYAN}Access Points:${NC}"
echo "  • Frontend UI:      https://localhost"
echo "  • API Docs:         https://localhost/docs"
echo "  • Health Check:     https://localhost/api/health"
echo ""
echo -e "${CYAN}Default Credentials:${NC}"
echo "  • Username:         CDR.ADMIN"
echo "  • Password:         AEGIS@Command2026!"
echo ""
echo -e "${RED}⚠ CRITICAL SECURITY WARNING:${NC}"
echo "  1. Change the default password immediately!"
echo "  2. Enable MFA for all accounts"
echo "  3. Review the security checklist in README.md"
echo ""
echo -e "${CYAN}Useful Commands:${NC}"
echo "  • View logs:        docker-compose logs -f aegis-api"
echo "  • Stop services:    docker-compose down"
echo "  • Restart:          docker-compose restart"
echo "  • Check status:     docker-compose ps"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo "  • README.md         - Complete documentation"
echo "  • DEPLOYMENT.md     - Production deployment guide"
echo "  • PROJECT_SUMMARY.md - Project overview"
echo ""
echo -e "${GREEN}Setup complete! Access the platform at https://localhost${NC}"
echo ""
