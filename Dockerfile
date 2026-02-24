# Use a lightweight Python image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for PostgreSQL and pycairo
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    pkg-config \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Collect static files (Uses WhiteNoise & django-tailwind-cli)
RUN python manage.py collectstatic --noinput

# Copy the custom start script and make it executable
COPY start.sh /app/
RUN chmod +x /app/start.sh

# Expose the port Gunicorn will listen on
EXPOSE 8000

# Start the application using the script (handles migrations)
CMD ["/app/start.sh"]
