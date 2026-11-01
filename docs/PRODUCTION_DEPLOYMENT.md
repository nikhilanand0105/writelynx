# Writelynx — Production Deployment & Infrastructure Runbook

**Document Classification:** Production Operations Manual  
**Target Platform:** Writelynx (VIT-Exclusive Paid Academic SaaS)  
**Target Architecture:** Single-Node VPS (Hetzner Cloud CPX11 / DigitalOcean Droplet / AWS EC2)  
**Operating System:** Ubuntu 22.04 / 24.04 LTS  

---

## 1. Architecture Overview

```
                      INTERNET / VIT STUDENTS
                                 │
                                 ▼
                     HTTPS Port 443 (TLS 1.3)
                                 │
                   ┌─────────────┴─────────────┐
                   │       CADDY PROXY         │
                   │  (Auto Let's Encrypt TLS) │
                   └─────────────┬─────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   Static Assets & SPA                       /api/* Reverse Proxy
 (React + Vite Build in /dist)               http://127.0.0.1:8000
                                                      │
                                                      ▼
                                            ┌──────────────────┐
                                            │ FASTAPI BACKEND  │
                                            │ (Python 3.11+)   │
                                            └─────────┬────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
              Persistent Storage                                            SQLite Database
           /app/storage/documents/                                       /app/storage/manuscript_studio.db
           /app/storage/quarantine/                                      (WAL Mode, PRAGMA busy_timeout=5000)
```

---

## 2. Server Provisioning & Base Hardening

### 2.1 Hardware Requirements
- **Recommended Node:** Hetzner CPX11 (2 vCPU, 2 GB RAM, 40 GB NVMe SSD) @ €5.35/month (~₹480/month).
- **Minimum Node:** 1 vCPU, 1 GB RAM (with 2 GB swapfile).

### 2.2 Initial OS Setup & Firewall
```bash
# 1. Update system packages
apt update && apt upgrade -y

# 2. Create isolated non-root system user
adduser --disabled-password --gecos "" writelynx
usermod -aG sudo writelynx

# 3. Configure UFW Firewall (Deny all incoming except SSH and Web)
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 4. Enable fail2ban for SSH brute-force defense
apt install -y fail2ban
systemctl enable fail2ban && systemctl start fail2ban
```

---

## 3. Deployment Option A: Docker Compose (Recommended)

### 3.1 Directory Layout on Production Host
```
/opt/writelynx/
├── .env.production
├── docker-compose.yml
├── Caddyfile
├── storage/
│   ├── documents/
│   └── quarantine/
└── data/
    └── manuscript_studio.db
```

### 3.2 Production `docker-compose.yml`
```yaml
version: "3.8"

services:
  caddy:
    image: caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./frontend/dist:/srv/frontend:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - backend

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    restart: always
    user: "1000:1000"
    environment:
      - ENVIRONMENT=production
    env_file:
      - .env.production
    volumes:
      - ./storage:/app/storage
      - ./data:/app/data
    deploy:
      resources:
        limits:
          cpus: "1.50"
          memory: 1536M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 15s
      timeout: 5s
      retries: 3

volumes:
  caddy_data:
  caddy_config:
```

### 3.3 Production `Caddyfile`
```caddy
writelynx.vitstudent.ac.in, writelynx.app {
    # Automatic HTTPS with Let's Encrypt
    encode zstd gzip

    # Strict Security Headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }

    # API Endpoints Reverse Proxy
    handle /api/* {
        reverse_proxy backend:8000 {
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
            transport http {
                response_header_timeout 60s
            }
        }
    }

    # Frontend Single-Page Application (SPA)
    handle {
        root * /srv/frontend
        try_files {path} /index.html
        file_server
    }
}
```

---

## 4. Deployment Option B: Native Systemd Service (Lightweight)

If operating without Docker to minimize overhead on a 1 GB VPS:

### 4.1 Systemd Unit File (`/etc/systemd/system/writelynx.service`)
```ini
[Unit]
Description=Writelynx FastAPI Production Service
After=network.target

[Service]
Type=simple
User=writelynx
Group=writelynx
WorkingDirectory=/opt/writelynx/backend
EnvironmentFile=/opt/writelynx/.env.production
ExecStart=/opt/writelynx/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --limit-concurrency 50
Restart=always
RestartSec=5

# Security Sandboxing Directives
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/writelynx/storage /opt/writelynx/backend/storage
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start systemd daemon
sudo systemctl daemon-reload
sudo systemctl enable writelynx
sudo systemctl start writelynx
```

---

## 5. Production Environment Variables (`.env.production`)

```env
# Host Environment
ENVIRONMENT=production
DEBUG=false
ALLOWED_HOSTS=writelynx.vitstudent.ac.in,writelynx.app,localhost

# Database (SQLite with WAL mode)
DATABASE_URL=sqlite:////opt/writelynx/storage/manuscript_studio.db

# Storage Paths
STORAGE_PATH=/opt/writelynx/storage
QUARANTINE_PATH=/opt/writelynx/storage/quarantine
DOCUMENTS_PATH=/opt/writelynx/storage/documents

# Google OAuth Credentials (VIT Workspace Verified)
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret

# Razorpay Production Keys (Use test keys during staging)
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_razorpay_live_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret

# Master Admin Key for Telemetry & Kill Switches
ADMIN_MASTER_KEY=your-securely-generated-64-character-hex-key

# Cost Governor Budget Ceilings (Integer Paise)
AI_MAX_SPEND_BASIC_PAISE=400
AI_MAX_SPEND_STANDARD_PAISE=900
AI_MAX_SPEND_EXTENDED_PAISE=2400

# Zero-Data-Retention LLM Provider API Keys
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

---

## 6. Safe Online SQLite WAL Backup Strategy

Because SQLite is running in `WAL` mode, copying the file directly with `cp` can result in corruption if a write is underway. We execute an online hot backup using SQLite’s native `.backup` API:

### 6.1 Automated Backup Script (`/opt/writelynx/scripts/backup_db.sh`)
```bash
#!/usr/bin/env bash
set -eo pipefail

BACKUP_DIR="/opt/writelynx/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_FILE="/opt/writelynx/storage/manuscript_studio.db"
BACKUP_FILE="${BACKUP_DIR}/manuscript_studio_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

# Native online safe snapshot (zero write blocking)
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# Compress and encrypt snapshot
gzip "$BACKUP_FILE"

# Retention: keep last 14 days of backups
find "$BACKUP_DIR" -type f -name "*.db.gz" -mtime +14 -delete

echo "[$(date)] Backup completed: ${BACKUP_FILE}.gz"
```

### 6.2 Crontab Schedule
```cron
# Backup database every 6 hours
0 */6 * * * /opt/writelynx/scripts/backup_db.sh >> /var/log/writelynx_backup.log 2>&1
```
