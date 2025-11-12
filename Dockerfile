# ==============================================
# Multi-stage Dockerfile for SSQE Orchestrator
# ==============================================
 
# Stage 1: Builder
FROM python:3.11-slim as builder
 
# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
 
# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
&& rm -rf /var/lib/apt/lists/*
 
# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
 
# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt
 
# Stage 2: Runtime
FROM python:3.11-slim
 
# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
 
# Create non-root user
RUN groupadd -r qeagent && useradd -r -g qeagent qeagent
 
# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
&& rm -rf /var/lib/apt/lists/*
 
# Set working directory
WORKDIR /app
 
# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
 
# Copy application code
COPY --chown=qeagent:qeagent . /app
 
# Create necessary directories
RUN mkdir -p /app/logs && \
    chown -R qeagent:qeagent /app
 
# Switch to non-root user
USER qeagent
 
# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
 
# Expose port
EXPOSE 8080
 
# Default command (webhook mode)
CMD ["python", "main.py", "--mode", "webhook"]