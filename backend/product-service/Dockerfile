# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app
# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}"

# Install system build dependencies and uv
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev \
        curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Final runtime stage
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1002 productgroup \
    && adduser --system --uid 1002 --ingroup productgroup productuser \
    && mkdir -p /app/logs \
    && mkdir -p /media/images \
    $$ mkdir -p /media/icons \
    && chown -R productuser:productgroup /app \ 
    && chown -R productuser:productgroup /media

# Copy only the necessary files from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create a non-root user and set permissions
COPY --chown=productuser:productgroup . .

# Ensure the app runs as a non-root user
USER productuser

# Port configuration
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Use Gunicorn for multi-worker production server (without Kubernetes!...if with Kubernetes, use uvicorn with other settings instead !)
# workers = (2 × CPU cores) + 1 - recommended baseline from Gunicorn’s official documentation. (4-5  are optimum )
# Each Gunicorn worker is a separate process.
# If you're using uvicorn.workers.UvicornWorker, then each worker runs a full async FastAPI app.
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8001", "--workers", "1", "--timeout", "60", "--access-logfile", "-"]