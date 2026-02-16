# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app.py .

# Create directory for database
RUN mkdir -p /app/data

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
#EXPOSE 5000

# Health check
#HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
   # CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"

# Run with gunicorn (production WSGI server)
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60 --access-logfile - --error-logfile - app:app

