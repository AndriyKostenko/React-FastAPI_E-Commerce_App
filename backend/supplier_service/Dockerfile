# -------------------------
# Build Stage
# -------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:${PATH}"

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

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

# -------------------------
# Test Build Stage
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
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc/supplier-service

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1017 suppliergroup \
    && adduser --system --uid 1017 --ingroup suppliergroup supplieruser \
    && mkdir -p /app/logs \
    && mkdir -p /tmp/prometheus_multiproc/supplier-service \
    && chown -R supplieruser:suppliergroup /app \
    && chown -R supplieruser:suppliergroup /tmp/prometheus_multiproc

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=supplieruser:suppliergroup . .

USER supplieruser

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

CMD ["sh", "-c", "mkdir -p ${PROMETHEUS_MULTIPROC_DIR} && rm -rf ${PROMETHEUS_MULTIPROC_DIR}/* && gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8010 --workers ${GUNICORN_WORKERS:-1} --timeout 120 --graceful-timeout 30 --access-logfile -"]

# -------------------------
# Test Runtime Stage
# -------------------------
FROM python:3.12-slim AS test

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc/supplier-service

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1017 suppliergroup \
    && adduser --system --uid 1017 --ingroup suppliergroup supplieruser \
    && mkdir -p /app/logs \
    && mkdir -p /tmp/prometheus_multiproc/supplier-service \
    && chown -R supplieruser:suppliergroup /app \
    && chown -R supplieruser:suppliergroup /tmp/prometheus_multiproc

COPY --from=test-builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=supplieruser:suppliergroup . .

USER supplieruser

CMD ["python", "-m", "pytest", "tests/", "-v"]
