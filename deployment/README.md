# Budget Monitoring System — On-Premise Deployment Guide

> **Target audience:** System administrator deploying on a physical Ubuntu server accessible via campus LAN.  
> **Stack:** Django 4 · Gunicorn · Nginx · PostgreSQL 15 · Python 3.10

---

## Table of Contents

1. [Server Requirements](#1-server-requirements)
2. [System Dependencies](#2-system-dependencies)
3. [PostgreSQL Setup](#3-postgresql-setup)
4. [Application Setup](#4-application-setup)
5. [Environment Variables (.env)](#5-environment-variables-env)
6. [Database Migration](#6-database-migration)
7. [Collect Static Files](#7-collect-static-files)
8. [Gunicorn Service (systemd)](#8-gunicorn-service-systemd)
9. [Nginx Configuration](#9-nginx-configuration)
10. [Gmail App Password Setup](#10-gmail-app-password-setup)
11. [First-Run Admin Account](#11-first-run-admin-account)
12. [Folder Permissions & Media Volume](#12-folder-permissions--media-volume)
13. [Verification Checklist](#13-verification-checklist)
14. [Common Problems & Fixes](#14-common-problems--fixes)

---

## 1. Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| CPU | 2 vCPU / cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB | 50 GB (for media uploads) |
| Network | Campus LAN only | Campus LAN only |
| Python | 3.10 | 3.10 or 3.11 |
| PostgreSQL | 14 | 15 |

---

## 2. System Dependencies

```bash
sudo apt update && sudo apt upgrade -y

# Core tools
sudo apt install -y python3.10 python3.10-venv python3-pip git nginx

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib libpq-dev

# Required for PDF / image processing (pycairo)
sudo apt install -y pkg-config libcairo2-dev gcc

# Optional but useful
sudo apt install -y curl htop
```

---

## 3. PostgreSQL Setup

```bash
# Switch to the postgres system user
sudo -u postgres psql
```

Inside the psql prompt, run:

```sql
-- Create the application database
CREATE DATABASE budget_system_db;

-- Create a dedicated database user (use a strong password)
CREATE USER budget_user WITH PASSWORD 'CHANGE_THIS_STRONG_PASSWORD';

-- Grant privileges
ALTER ROLE budget_user SET client_encoding TO 'utf8';
ALTER ROLE budget_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE budget_user SET timezone TO 'Asia/Manila';
GRANT ALL PRIVILEGES ON DATABASE budget_system_db TO budget_user;

-- Exit psql
\q
```

> **Note:** PostgreSQL listens on `localhost:5432` by default. No changes to `pg_hba.conf` are needed for a local Django connection.

---

## 4. Application Setup

```bash
# Choose a deploy location (e.g., /srv)
sudo mkdir -p /srv/budget_system
sudo chown $USER:$USER /srv/budget_system

# Clone the repository
cd /srv/budget_system
git clone https://github.com/YOUR_ORG/YOUR_REPO.git .

# Create and activate virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Environment Variables (.env)

Create the file `/srv/budget_system/.env`:

```bash
nano /srv/budget_system/.env
```

Paste and fill in every value below:

```dotenv
# ── Django Core ───────────────────────────────────────────────────────────────
SECRET_KEY=replace-with-a-long-random-secret-key-50-chars-minimum
DEBUG=False
ALLOWED_HOSTS=192.168.1.100,budget.campus.local
CSRF_TRUSTED_ORIGINS=http://192.168.1.100,http://budget.campus.local

# ── Database (PostgreSQL) ──────────────────────────────────────────────────────
# Format: postgres://USER:PASSWORD@HOST:PORT/DBNAME
DATABASE_URL=postgres://budget_user:CHANGE_THIS_STRONG_PASSWORD@localhost:5432/budget_system_db

# Set to 'true' ONLY if your PostgreSQL is configured with SSL certificates
DATABASE_SSL=false

# ── Media Files ────────────────────────────────────────────────────────────────
# Must match the alias in nginx.conf → /path/to/app/media/
MEDIA_ROOT=/srv/budget_system/media

# ── Gmail SMTP (Email Notifications) ──────────────────────────────────────────
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-gmail-account@gmail.com
EMAIL_HOST_PASSWORD=xxxx-xxxx-xxxx-xxxx   # 16-character Gmail App Password (NOT your Gmail password)

# ── Optional: Auto-create a superuser on first boot ────────────────────────────
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@campus.edu
SUPERUSER_PASSWORD=ChangeThisAdminPassword123!
SUPERUSER_FULLNAME=System Administrator
SUPERUSER_POSITION=IT Administrator
SUPERUSER_DEPARTMENT=IT Department
```

> **Security:** Lock down the file so only the app user can read it:
> ```bash
> chmod 600 /srv/budget_system/.env
> ```

---

## 6. Database Migration

```bash
cd /srv/budget_system
source venv/bin/activate

python manage.py migrate --noinput
```

Expected output ends with lines like:
```
Running migrations:
  Applying budgets.0011_remove_cloudinary_storage... OK
  ...
```

---

## 7. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

Static files are placed in `staticfiles/` and served by Nginx directly.

---

## 8. Gunicorn Service (systemd)

Create the service file:

```bash
sudo nano /etc/systemd/system/budget_system.service
```

Paste the following (adjust paths):

```ini
[Unit]
Description=Budget Monitoring System — Gunicorn
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/budget_system
EnvironmentFile=/srv/budget_system/.env
ExecStart=/srv/budget_system/venv/bin/gunicorn \
    config.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --log-level info \
    --access-logfile /var/log/budget_system/access.log \
    --error-logfile  /var/log/budget_system/error.log

Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Set up log directory and enable the service:

```bash
# Log directory
sudo mkdir -p /var/log/budget_system
sudo chown www-data:www-data /var/log/budget_system

# Fix ownership of the app directory
sudo chown -R www-data:www-data /srv/budget_system
sudo chmod -R 750 /srv/budget_system

# Make the media folder writable
sudo chmod -R 755 /srv/budget_system/media

# Enable + start
sudo systemctl daemon-reload
sudo systemctl enable budget_system
sudo systemctl start budget_system
sudo systemctl status budget_system   # Should show "Active: active (running)"
```

> **Worker count formula:** `(2 × CPU cores) + 1`. For a 2-core server → 5 workers.

---

## 9. Nginx Configuration

```bash
# Copy the provided config
sudo cp /srv/budget_system/deployment/nginx.conf \
        /etc/nginx/sites-available/budget_system

# Edit placeholders
sudo nano /etc/nginx/sites-available/budget_system
```

Replace in the file:
| Placeholder | Your actual value |
|---|---|
| `YOUR_SERVER_IP` | e.g. `192.168.1.100` or `budget.campus.local` |
| `/path/to/app/staticfiles/` | `/srv/budget_system/staticfiles/` |
| `/path/to/app/media/` | `/srv/budget_system/media/` |

Enable the site and reload:

```bash
# Disable the default site
sudo rm -f /etc/nginx/sites-enabled/default

# Enable budget_system
sudo ln -s /etc/nginx/sites-available/budget_system \
           /etc/nginx/sites-enabled/budget_system

# Test config syntax
sudo nginx -t

# Reload (zero-downtime)
sudo systemctl reload nginx
```

---

## 10. Gmail App Password Setup

> Standard Gmail passwords **cannot** be used with SMTP. You need an **App Password**.

1. Sign in to the Gmail account that will send notifications.
2. Go to **Google Account → Security → 2-Step Verification** → turn it **ON**.
3. Go to **Google Account → Security → App passwords**.
4. Select app: **Mail**, device: **Other (custom name)** → enter `Budget System`.
5. Copy the generated **16-character password** (e.g. `abcd efgh ijkl mnop`).
6. Paste it (without spaces) into `.env` as `EMAIL_HOST_PASSWORD`.

Test from the server:

```bash
source /srv/budget_system/venv/bin/activate
python manage.py shell -c "
from django.core.mail import send_mail
send_mail('Test', 'Hello from Budget System', None, ['your@email.com'])
print('Email sent successfully!')
"
```

---

## 11. First-Run Admin Account

**Option A — Automatic (via `.env`)**  
The `start.sh` script reads `SUPERUSER_*` variables and calls `createsuperuser` automatically on first boot.

**Option B — Manual**

```bash
cd /srv/budget_system
source venv/bin/activate
python manage.py createsuperuser
```

---

## 12. Folder Permissions & Media Volume

All uploaded files (PDFs, images, Excel files) live in `MEDIA_ROOT` (`/srv/budget_system/media/`).

```bash
# Ensure www-data can write to media
sudo chown -R www-data:www-data /srv/budget_system/media
sudo chmod -R 755 /srv/budget_system/media
```

> **Backup strategy:** Back up `/srv/budget_system/media/` and the PostgreSQL database regularly.
>
> Quick database backup:
> ```bash
> sudo -u postgres pg_dump budget_system_db > backup_$(date +%Y%m%d).sql
> ```

---

## 13. Verification Checklist

Run through these after deployment:

- [ ] `sudo systemctl status budget_system` → **active (running)**
- [ ] `sudo systemctl status nginx` → **active (running)**
- [ ] Open `http://YOUR_SERVER_IP/` in a campus browser → login page loads
- [ ] Log in as admin → dashboard renders correctly
- [ ] Upload a document (PDF) on any request form → file saves to `/srv/budget_system/media/`
- [ ] Open a submitted request → PDF preview opens in-browser (no Google Docs)
- [ ] Reject a request with a reason → rejection modal works, reason shown to end-user
- [ ] Submit a new PRE/PR/AD → admin receives Gmail notification
- [ ] Approve/reject a request → end-user receives Gmail notification
- [ ] Check logs: `sudo journalctl -u budget_system -n 50`

---

## 14. Common Problems & Fixes

| Problem | Likely cause | Fix |
|---|---|---|
| `502 Bad Gateway` | Gunicorn not running | `sudo systemctl restart budget_system` |
| `Static files not loading` | `collectstatic` not run | `python manage.py collectstatic --noinput` |
| `Media files return 404` | Nginx `alias` path wrong | Check `alias` in nginx.conf matches `MEDIA_ROOT` |
| `CSRF verification failed` | `CSRF_TRUSTED_ORIGINS` missing server IP | Add `http://YOUR_IP` to `.env` |
| `OperationalError: could not connect to server` | Wrong `DATABASE_URL` | Check PostgreSQL is running: `sudo systemctl status postgresql` |
| Emails not sending | Wrong App Password or 2FA off | Re-generate App Password; ensure 2-Step Verification is ON |
| `Database SSL error` | `DATABASE_SSL=true` but no SSL cert | Set `DATABASE_SSL=false` in `.env` |
| File upload > 50 MB rejected | Nginx `client_max_body_size` | Already set to `55M` in nginx.conf |
| Permission denied writing to media | Wrong `chown` | `sudo chown -R www-data:www-data /srv/budget_system/media` |

---

## Updating the Application

```bash
cd /srv/budget_system
source venv/bin/activate

# Pull latest code
git pull origin main

# Install any new dependencies
pip install -r requirements.txt

# Apply new migrations
python manage.py migrate --noinput

# Rebuild static files if templates/CSS changed
python manage.py collectstatic --noinput

# Restart Gunicorn (zero-downtime with reload)
sudo systemctl reload budget_system
```

---

*Generated as part of the production readiness audit — Budget Monitoring System Capstone Project.*
