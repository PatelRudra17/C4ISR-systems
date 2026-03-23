# AEGIS C4ISR Deployment Guide

## Production Deployment Checklist

### 1. Infrastructure Preparation

#### Hardware Requirements
- **Minimum**: 4 CPU cores, 16GB RAM, 200GB SSD
- **Recommended**: 8+ CPU cores, 32GB RAM, 500GB NVMe SSD
- **Network**: Gigabit Ethernet, static IP address
- **Redundancy**: Consider active-passive failover setup

#### Operating System
- Ubuntu 22.04 LTS Server (recommended)
- RHEL 8+, CentOS 8+, or Debian 11+ also supported
- Kernel 5.15+ for optimal Docker performance

### 2. Pre-Deployment Setup

#### Install Docker
```bash
# Remove old versions
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg lsb-release

# Add Docker GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable Docker at boot
sudo systemctl enable docker
sudo systemctl start docker
```

#### Configure Firewall
```bash
# Allow only HTTPS traffic
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH (restrict to specific IPs in production)
sudo ufw enable
```

### 3. Security Hardening

#### Generate Strong Secrets
```bash
# PostgreSQL password
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Redis password
REDIS_PASSWORD=$(openssl rand -base64 32)

# InfluxDB token
INFLUX_TOKEN=$(openssl rand -hex 32)

# JWT secret
JWT_SECRET_KEY=$(openssl rand -hex 32)

# AES key (exactly 32 characters)
AES_KEY=$(openssl rand -base64 24)

# Print for .env file
echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
echo "REDIS_PASSWORD=${REDIS_PASSWORD}"
echo "INFLUX_TOKEN=${INFLUX_TOKEN}"
echo "JWT_SECRET_KEY=${JWT_SECRET_KEY}"
echo "AES_KEY=${AES_KEY}"
```

#### Generate Production SSL Certificate
```bash
# Self-signed (for internal use)
openssl req -x509 -nodes -days 365 -newkey rsa:4096 \
  -keyout certs/nginx.key -out certs/nginx.crt \
  -subj "/C=US/ST=Virginia/L=DC/O=AEGIS/CN=aegis.yourdomain.mil"

# OR use Let's Encrypt (for public domains)
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d aegis.yourdomain.mil
sudo ln -s /etc/letsencrypt/live/aegis.yourdomain.mil/fullchain.pem certs/nginx.crt
sudo ln -s /etc/letsencrypt/live/aegis.yourdomain.mil/privkey.pem certs/nginx.key
```

### 4. Deploy Application

#### Clone Repository
```bash
cd /opt
sudo git clone https://github.com/your-org/aegis-c4isr.git
cd aegis-c4isr
```

#### Configure Environment
```bash
cp .env.example .env
nano .env  # Edit with generated secrets

# Set production values
DEBUG=False
ENVIRONMENT=production
ALLOWED_ORIGINS=https://aegis.yourdomain.mil
```

#### Launch Services
```bash
# Build and start all services
sudo docker-compose up --build -d

# Check status
sudo docker-compose ps

# View logs
sudo docker-compose logs -f aegis-api
```

### 5. Post-Deployment Verification

#### Health Checks
```bash
# API health
curl -k https://localhost/api/health

# PostgreSQL
sudo docker exec -it aegis-postgres pg_isready -U aegis_admin

# Redis
sudo docker exec -it aegis-redis redis-cli -a ${REDIS_PASSWORD} ping

# InfluxDB
curl -k http://localhost:8086/health
```

#### Create First Admin User
```bash
# Connect to API container
sudo docker exec -it aegis-api bash

# Inside container, use Python
python3 -c "
from app.core.security import hash_password, generate_totp_secret, get_totp_uri
pwd = hash_password('YourSecurePassword123!')
secret = generate_totp_secret()
uri = get_totp_uri(secret, 'ADMIN')
print(f'Password Hash: {pwd}')
print(f'TOTP Secret: {secret}')
print(f'TOTP URI: {uri}')
"
```

Update `scripts/init.sql` with the new hash, then restart PostgreSQL.

### 6. Monitoring Setup

#### Install Prometheus & Grafana
```bash
# Create monitoring directory
mkdir -p /opt/monitoring
cd /opt/monitoring

# Create docker-compose.yml for monitoring
cat > docker-compose.yml <<EOF
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  prometheus-data:
  grafana-data:
EOF

# Create Prometheus config
cat > prometheus.yml <<EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'aegis-api'
    static_configs:
      - targets: ['localhost:8000']
EOF

# Start monitoring
sudo docker-compose up -d
```

#### Configure Alerts
Set up alerts for:
- High CPU/Memory usage
- Database connection failures
- Failed authentication attempts
- Cyber security events

### 7. Backup Strategy

#### Automated Backups
```bash
# Create backup script
sudo nano /opt/scripts/backup-aegis.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/aegis"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec aegis-postgres pg_dump -U aegis_admin aegis_c4isr | \
  gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Backup InfluxDB
docker exec aegis-influxdb influx backup -t $INFLUX_TOKEN /tmp/influx_backup
docker cp aegis-influxdb:/tmp/influx_backup $BACKUP_DIR/influx_$DATE

# Backup Redis
docker exec aegis-redis redis-cli -a $REDIS_PASSWORD SAVE
docker cp aegis-redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Remove backups older than 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable
sudo chmod +x /opt/scripts/backup-aegis.sh

# Add cron job (daily at 2 AM)
sudo crontab -e
# Add: 0 2 * * * /opt/scripts/backup-aegis.sh >> /var/log/aegis-backup.log 2>&1
```

### 8. High Availability Setup

#### Database Replication
```yaml
# docker-compose.yml additions for PostgreSQL replication
postgres-replica:
  image: postgres:16-alpine
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    PGDATA: /var/lib/postgresql/data/pgdata
  volumes:
    - postgres-replica-data:/var/lib/postgresql/data
  command: >
    -c wal_level=replica
    -c hot_standby=on
    -c max_wal_senders=10
    -c max_replication_slots=10
```

#### Load Balancing
```nginx
# nginx.conf upstream configuration
upstream aegis_api {
    least_conn;
    server aegis-api-1:8000 max_fails=3 fail_timeout=30s;
    server aegis-api-2:8000 max_fails=3 fail_timeout=30s;
    server aegis-api-3:8000 max_fails=3 fail_timeout=30s;
}
```

### 9. Performance Optimization

#### PostgreSQL Tuning
```sql
-- Connect to PostgreSQL
docker exec -it aegis-postgres psql -U aegis_admin -d aegis_c4isr

-- Apply optimizations
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '10MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET max_worker_processes = 8;
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;
ALTER SYSTEM SET max_parallel_maintenance_workers = 4;

-- Restart PostgreSQL
\q
docker restart aegis-postgres
```

#### Redis Optimization
```bash
# Connect to Redis
docker exec -it aegis-redis redis-cli -a ${REDIS_PASSWORD}

# Apply settings
CONFIG SET maxmemory 4gb
CONFIG SET maxmemory-policy allkeys-lru
CONFIG SET save "900 1 300 10 60 10000"
CONFIG REWRITE
```

### 10. Disaster Recovery

#### Recovery Procedures

**PostgreSQL Recovery:**
```bash
# Stop services
sudo docker-compose down

# Restore from backup
gunzip -c /opt/backups/aegis/postgres_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i aegis-postgres psql -U aegis_admin aegis_c4isr

# Restart
sudo docker-compose up -d
```

**InfluxDB Recovery:**
```bash
# Copy backup to container
docker cp /opt/backups/aegis/influx_YYYYMMDD_HHMMSS aegis-influxdb:/tmp/

# Restore
docker exec aegis-influxdb influx restore -t $INFLUX_TOKEN /tmp/influx_YYYYMMDD_HHMMSS
```

**Full System Recovery:**
```bash
# 1. Fresh installation on new server
# 2. Restore all backups
# 3. Update DNS/IP addresses
# 4. Test all endpoints
# 5. Verify data integrity
```

### 11. Compliance & Auditing

#### Enable Audit Logging
```python
# In app/main.py, ensure audit middleware is enabled
app.add_middleware(AuditLoggerMiddleware)
```

#### Log Retention
```bash
# Configure log rotation
sudo nano /etc/logrotate.d/aegis

# Add:
/var/log/aegis/*.log {
    daily
    rotate 365
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        docker kill -s USR1 aegis-api
    endscript
}
```

### 12. Maintenance

#### Regular Tasks
- **Daily**: Check logs, review security alerts
- **Weekly**: Review performance metrics, check disk space
- **Monthly**: Update dependencies, security patches
- **Quarterly**: Review access controls, audit user accounts
- **Annually**: Security audit, penetration testing

#### Update Procedure
```bash
# Pull latest code
cd /opt/aegis-c4isr
sudo git pull

# Backup current state
/opt/scripts/backup-aegis.sh

# Rebuild and deploy
sudo docker-compose down
sudo docker-compose up --build -d

# Verify health
curl -k https://localhost/api/health
```

---

## Troubleshooting

### Common Issues

**Service Won't Start:**
```bash
# Check logs
sudo docker-compose logs aegis-api

# Check ports
sudo netstat -tlnp | grep -E '8000|5432|6379|8086'

# Check disk space
df -h
```

**High Memory Usage:**
```bash
# Check container stats
sudo docker stats

# Restart specific service
sudo docker-compose restart aegis-api
```

**Database Connection Timeout:**
```bash
# Increase connection pool
# In .env:
POSTGRES_MAX_CONNECTIONS=200

# Restart
sudo docker-compose restart postgres aegis-api
```

---

## Support Contacts

- **Technical Support**: support@aegis.mil
- **Security Team**: security@aegis.mil
- **Emergency Hotline**: +1-XXX-XXX-XXXX

---

**Classification**: TOP SECRET//NOFORN
**Document Version**: 1.0.0
**Last Updated**: 2026-03-17
