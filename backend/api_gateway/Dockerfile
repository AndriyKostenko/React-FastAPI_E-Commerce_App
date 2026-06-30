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
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev \
        curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files only
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync instead of uv pip install
RUN uv sync --frozen --no-dev

# -------------------------
# Test Builder Stage
# -------------------------
FROM builder AS test-builder

RUN uv sync --frozen

# -------------------------
# Test Runtime Stage
# -------------------------
FROM python:3.12-slim AS test

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1010 apigatewaygroup-test \
    && adduser --system --uid 1010 --ingroup apigatewaygroup-test apigatewayuser-test \
    && mkdir -p /app/logs \
    && chown -R apigatewayuser-test:apigatewaygroup-test /app

COPY --from=test-builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=apigatewayuser-test:apigatewaygroup-test . .

USER apigatewayuser-test

CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]

# -------------------------
# Final Runtime Stage
# -------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Prometheus multiprocess mode: each Gunicorn worker writes metrics to shared files
    # so the /metrics endpoint can aggregate across all workers.
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc/api-gateway

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1000 apigatewaygroup \
    && adduser --system --uid 1000 --ingroup apigatewaygroup apigatewayuser \
    && mkdir -p /app/logs /tmp/prometheus_multiproc/api-gateway \
    && chown -R apigatewayuser:apigatewaygroup /app /tmp/prometheus_multiproc

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Set up PATH to include both uv and venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and set permissions
COPY --chown=apigatewayuser:apigatewaygroup . .

# Ensure the app runs as a non-root user
USER apigatewayuser

# Expose app port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use Gunicorn for multi-worker production server (without Kubernetes!...if with Kubernetes, use uvicorn with other settings instead!)
# workers = (2 × CPU cores) + 1 - recommended baseline from Gunicorn’s official documentation. (4-5  are optimum )
# Each Gunicorn worker is a separate process.
# If you're using uvicorn.workers.UvicornWorker, then each worker runs a full async FastAPI app.

# adding the clean up for prometheus metrics
# CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000 --workers $((2 * $(nproc) + 1)) --timeout 120 --graceful-timeout 30 --access-logfile -"]
CMD ["sh", "-c", \
"mkdir -p ${PROMETHEUS_MULTIPROC_DIR} && \
 rm -rf ${PROMETHEUS_MULTIPROC_DIR}/* && \
 gunicorn \
 -k uvicorn.workers.UvicornWorker \
 main:app \
 --bind 0.0.0.0:8000 \
 --workers ${GUNICORN_WORKERS:-1} \
 --timeout 120 \
 --graceful-timeout 30 \
 --access-logfile -"]
