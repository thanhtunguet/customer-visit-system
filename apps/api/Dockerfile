# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for API service

# Build stage
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app

# Copy application code
COPY apps/api/ ./apps/api/
COPY packages/python/ ./packages/python/
COPY contracts/ ./contracts/

# Create non-root user and fix permissions
RUN useradd -m -u 1000 apiuser \
    && chown -R apiuser:apiuser /app \
    && cp -r /root/.local /home/apiuser/ \
    && chown -R apiuser:apiuser /home/apiuser/.local

USER apiuser
ENV PATH=/home/apiuser/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/v1/health || exit 1

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]

