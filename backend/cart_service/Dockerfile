# -------------------------
# Build Stage
# -------------------------
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
        nano \
        vim \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files only
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync instead of uv pip install
RUN uv sync --frozen --no-dev




# -------------------------
# Test Build Stage
# (same as builder but includes dev dependencies: pytest, httpx, etc.)
# -------------------------
FROM builder AS test-builder

RUN uv sync --frozen




# -------------------------
# Final Runtime Stage
# -------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc/cart-service

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1007 cartgroup \
    && adduser --system --uid 1007 --ingroup cartgroup cartuser \
    && mkdir -p /app/logs \
    && mkdir -p /app/logs /tmp/prometheus_multiproc/cart-service \
    && chown -R cartuser:cartgroup /app \
    && chown -R cartuser:cartgroup /app /tmp/prometheus_multiproc

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Set up PATH to include both uv and venv
ENV PATH="/app/.venv/bin:$PATH"

# Create a non-root user and set permissions
COPY --chown=cartuser:cartgroup . .

# Ensure the app runs as a non-root user
USER cartuser

# Port configuration
EXPOSE 8007

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8007/health || exit 1

# Use Gunicorn for multi-worker production server (without Kubernetes!...if with Kubernetes, use uvicorn with other settings instead !)
# workers = (2 × CPU cores) + 1 - recommended baseline from Gunicorn’s official documentation. (4-5  are optimum )
# Each Gunicorn worker is a separate process.
# If you're using uvicorn.workers.UvicornWorker, then each worker runs a full async FastAPI app.

# ( automatically detects the number of CPU cores and sets the number of workers accordingly )

#CMD ["sh", "-c", "rm -rf /tmp/prometheus_multiproc/* && gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8007 --workers $((2 * $(nproc) + 1)) --timeout 120 --graceful-timeout 30 --access-logfile -"]
CMD ["sh", "-c", "mkdir -p ${PROMETHEUS_MULTIPROC_DIR} && rm -rf ${PROMETHEUS_MULTIPROC_DIR}/* && gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8007 --workers ${GUNICORN_WORKERS:-1} --timeout 120 --graceful-timeout 30 --access-logfile -"]




# -------------------------
# Test Runtime Stage
# -------------------------
FROM python:3.12-slim AS test

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc/cart-service

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1007 cartgroup \
    && adduser --system --uid 1007 --ingroup cartgroup cartuser \
    && mkdir -p /app/logs \
    && mkdir -p /tmp/prometheus_multiproc/cart-service \
    && chown -R cartuser:cartgroup /app \
    && chown -R cartuser:cartgroup /tmp/prometheus_multiproc

# Copy venv with dev deps (pytest, httpx, etc.) from test-builder
COPY --from=test-builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=cartuser:cartgroup . .

USER cartuser

CMD ["python", "-m", "pytest", "tests/", "-v"]
