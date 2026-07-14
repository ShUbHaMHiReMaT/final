# AVIRA Backend – Docker Configuration
# Used for local development and alternative deployment options.

FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Environment defaults (override in docker-compose or environment)
ENV APP_ENV=production
ENV PORT=5000
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Run with gunicorn
CMD ["sh", "-c", "gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -"]
