# ============================================================================
# 1. BASE IMAGE & SYSTEM DEPENDENCIES
# ============================================================================
FROM python:3.11-slim as builder

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for compilation if any wheels are missing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ============================================================================
# 2. FINAL RUNTIME IMAGE
# ============================================================================
FROM python:3.11-slim as runner

# Setup production environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5000

WORKDIR /app

# Copy isolated virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application codebase
COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Create a non-privileged system user for runtime security
RUN useradd -u 8888 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Run Flask app with production-ready Gunicorn WSGI server
# 4 workers are recommended for basic multi-threaded handling in container platforms
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "--timeout", "120", "app:app"]
