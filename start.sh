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
        --email "$SUPERUSER_EMAIL" \``
        --position "${SUPERUSER_POSITION:-System Admin}" \
        --fullname "${SUPERUSER_FULLNAME:-Super Admin}" \
        --department "${SUPERUSER_DEPARTMENT:-IT Department}" || true
    # The '|| true' ensures the script doesn't crash if the user already exists
fi

echo "Starting Gunicorn Server..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
