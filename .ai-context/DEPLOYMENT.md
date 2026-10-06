# DEPLOYMENT

---

## Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB | 50 GB (for media uploads) |
| Network | Campus LAN (private IP) | Campus LAN |
| Python | 3.10 | 3.10 or 3.11 |
| PostgreSQL | 14 | 15 |
| LibreOffice | Latest stable | Latest stable |
| Nginx | Latest stable | Latest stable |

> **Note:** The deployment README (`deployment/README.md`) targets Ubuntu. The development environment is Windows. LibreOffice path differs between environments.

---

## Complete Environment Variables

Every `os.getenv()` call found in `config/settings.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | `'django-insecure-dev-key-change-in-production'` | Django secret key |
| `DEBUG` | `'False'` | Debug mode — **must be `False` in production** |
| `ALLOWED_HOSTS` | `'localhost,127.0.0.1'` | Comma-separated allowed hosts |
| `CSRF_TRUSTED_ORIGINS` | `'http://localhost:8000'` | Comma-separated trusted origins |
| `RENDER_EXTERNAL_HOSTNAME` | (none) | Render.com hostname (legacy, can be ignored) |
| `DATABASE_URL` | `sqlite:///BASE_DIR/db.sqlite3` | Database connection string (via `dj-database-url`) |
| `DATABASE_SSL` | `'false'` | Set `'true'` only if PostgreSQL has SSL certificates |
| `LIBREOFFICE_PATH` | `r'C:\Program Files\LibreOffice\program\soffice.exe'` | Path to `soffice` executable |
| `EMAIL_BACKEND` | `'django.core.mail.backends.smtp.EmailBackend'` | Email backend |
| `EMAIL_HOST` | `'smtp.gmail.com'` | SMTP host |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_USE_TLS` | `True` | Use TLS |
| `EMAIL_HOST_USER` | (none — required) | Gmail address |
| `EMAIL_HOST_PASSWORD` | (none — required) | Gmail App Password (16 chars) |

### Sample `.env` for production

```dotenv
SECRET_KEY=replace-with-a-long-random-secret-key-50-chars-minimum
DEBUG=False
ALLOWED_HOSTS=192.168.1.100,budget.campus.local
CSRF_TRUSTED_ORIGINS=http://192.168.1.100,http://budget.campus.local
DATABASE_URL=postgres://budget_user:STRONG_PASSWORD@localhost:5432/budget_system_db
DATABASE_SSL=false
LIBREOFFICE_PATH=/usr/bin/soffice
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

---

## System Dependencies (Ubuntu)

```bash
sudo apt update && sudo apt upgrade -y

# Core tools
sudo apt install -y python3.10 python3.10-venv python3-pip git nginx

# PostgreSQL
sudo apt install -y postgresql postgresql-contrib libpq-dev

# LibreOffice (for DOCX/XLSX → PDF conversion)
sudo apt install -y libreoffice-calc libreoffice-writer

# Required for pycairo (PDF rendering)
sudo apt install -y pkg-config libcairo2-dev gcc

# Optional
sudo apt install -y curl htop
```

---

## PostgreSQL Setup

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE budget_system_db;
CREATE USER budget_user WITH PASSWORD 'CHANGE_THIS_STRONG_PASSWORD';
ALTER ROLE budget_user SET client_encoding TO 'utf8';
ALTER ROLE budget_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE budget_user SET timezone TO 'Asia/Manila';
GRANT ALL PRIVILEGES ON DATABASE budget_system_db TO budget_user;
\q
```

---

## Application Setup

```bash
sudo mkdir -p /srv/budget_system
cd /srv/budget_system
git clone <repository-url> .

python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Database Migration

```bash
python manage.py migrate --noinput
```

---

## Static Files

```bash
python manage.py collectstatic --noinput
```

Static files are placed in `staticfiles/` and served directly by Nginx.

---

## Gunicorn Service (systemd)

File: `/etc/systemd/system/budget_system.service`

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

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/log/budget_system
sudo chown www-data:www-data /var/log/budget_system
sudo chown -R www-data:www-data /srv/budget_system
sudo chmod -R 750 /srv/budget_system
sudo chmod -R 755 /srv/budget_system/media
sudo systemctl daemon-reload
sudo systemctl enable budget_system
sudo systemctl start budget_system
```

---

## Nginx Configuration

File: `deployment/nginx.conf` (copy to `/etc/nginx/sites-available/budget_system`)

Key settings:
- `client_max_body_size 55M` — must be ≥ Django's 50 MB upload limit
- `X-Frame-Options: SAMEORIGIN` — required for iframe document previews
- Static: `alias /srv/budget_system/staticfiles/` with 30d cache
- Media: `alias /srv/budget_system/media/` with 7d cache
- Proxy: `proxy_pass http://127.0.0.1:8000` with 120s timeout

```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/budget_system
# Edit placeholders: YOUR_SERVER_IP, /path/to/app
sudo ln -s /etc/nginx/sites-available/budget_system /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

---

## LibreOffice Installation

### Ubuntu (Production)
```bash
sudo apt install -y libreoffice-calc libreoffice-writer
# soffice will be available at /usr/bin/soffice
# Set LIBREOFFICE_PATH=/usr/bin/soffice in .env
```

### Windows (Development)
- Install LibreOffice from https://www.libreoffice.org/download/
- Default path: `C:\Program Files\LibreOffice\program\soffice.exe`
- `LIBREOFFICE_PATH` env var or `settings.LIBREOFFICE_PATH` setting

### Verify installation
```bash
soffice --headless --version
```

---

## Media Directory

```bash
sudo mkdir -p /srv/budget_system/media
sudo chown -R www-data:www-data /srv/budget_system/media
sudo chmod -R 755 /srv/budget_system/media
```

All uploaded files (PDFs, images, Excel, DOCX) are stored here. **Back up regularly.**

---

## ALLOWED_HOSTS Configuration

For campus LAN:
```dotenv
ALLOWED_HOSTS=192.168.1.100,budget.campus.local
CSRF_TRUSTED_ORIGINS=http://192.168.1.100,http://budget.campus.local
```

Replace with actual server IP and optional hostname.

---

## First Admin Account

```bash
python manage.py createsuperuser
```

Or use `.env` variables for automatic creation:
```dotenv
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@campus.edu
SUPERUSER_PASSWORD=ChangeThisAdminPassword123!
SUPERUSER_FULLNAME=System Administrator
SUPERUSER_POSITION=IT Administrator
SUPERUSER_DEPARTMENT=IT Department
```

---

## Verification Checklist

- [ ] `sudo systemctl status budget_system` → active (running)
- [ ] `sudo systemctl status nginx` → active (running)
- [ ] Browser: `http://SERVER_IP/` → login page loads
- [ ] Admin login → dashboard renders
- [ ] Upload a document → file saves to `media/`
- [ ] Preview a document → PDF preview works in iframe
- [ ] Reject a request → modal works, reason saved and displayed
- [ ] Submit PRE/PR/AD → admin receives email notification
- [ ] Approve/reject → end user receives email notification
- [ ] Check logs: `sudo journalctl -u budget_system -n 50`
