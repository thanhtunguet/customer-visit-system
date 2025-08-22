# Multi-stage Dockerfile for Worker service
FROM python:3.11-slim AS base

# Install system dependencies for OpenCV and face recognition
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgstreamer1.0-0 \
    libgtk-3-0 \
    libgl1 \
    libglu1-mesa \
    gcc \
    g++ \
    curl \
    ca-certificates \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching  
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory
RUN mkdir -p app/models

# Create non-root user
RUN useradd -m -u 1000 workeruser && chown -R workeruser:workeruser /app
USER workeruser

# Default environment for container
ENV PYTHONPATH=/app
ENV MOCK_MODE=true
ENV DETECTOR_TYPE=mock
ENV EMBEDDER_TYPE=mock

CMD ["python", "-m", "app.main"]

