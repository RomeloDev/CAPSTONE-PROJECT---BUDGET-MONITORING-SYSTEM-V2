#!/bin/bash
set -e

echo "Running Database Migrations..."
python manage.py migrate --noinput

echo "Checking for Superuser creation..."
# If superuser details are provided in environment variables, create one automatically
if [ -n "$SUPERUSER_USERNAME" ] && [ -n "$SUPERUSER_EMAIL" ] && [ -n "$SUPERUSER_PASSWORD" ]; then
    export DJANGO_SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD"
    python manage.py createsuperuser --noinput \
        --username "$SUPERUSER_USERNAME" \
        --email "$SUPERUSER_EMAIL" \
        --position "${SUPERUSER_POSITION:-System Admin}" \
        --fullname "${SUPERUSER_FULLNAME:-Super Admin}" \
        --department "${SUPERUSER_DEPARTMENT:-IT Department}" || true
    # The '|| true' ensures the script doesn't crash if the user already exists
fi

echo "Starting Gunicorn Server..."

# Render-friendly Gunicorn defaults (override via environment variables if needed)
PORT="${PORT:-8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-1}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-500}"
GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-50}"

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --max-requests "${GUNICORN_MAX_REQUESTS}" \
    --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER}"
