FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, Java for PySpark)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Java home for PySpark
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Matplotlib: use non-interactive backend (no display server in container)
ENV MPLBACKEND=Agg

# Copy requirements first for Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p sessions uploads

# Default port (Render overrides with $PORT env var)
ENV PORT=8080
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/spark/status || exit 1

# Run with uvicorn — shell form to expand $PORT
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
