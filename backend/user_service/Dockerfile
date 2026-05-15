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
        nano \
        vim \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files only
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev tools in the runtime image)
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
    PYTHONUNBUFFERED=1

# Install runtime dependencies (smaller footprint than build stage)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        nano \
        vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 usergroup \
    && adduser --system --uid 1001 --ingroup usergroup user \
    && mkdir -p /app/logs \
    && chown -R user:usergroup /app

# Copy production venv from builder
COPY --from=builder /app/.venv /app/.venv

# Set up PATH to include both uv and venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and set permissions
COPY --chown=user:usergroup . .

USER user

# Expose app port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8001", "--workers", "1", "--timeout", "60", "--access-logfile", "-"]






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
    && addgroup --system --gid 1001 usergroup \
    && adduser --system --uid 1001 --ingroup usergroup user \
    && mkdir -p /app/logs \
    && chown -R user:usergroup /app

# Copy venv with dev deps (pytest, httpx, etc.) from test-builder
COPY --from=test-builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=user:usergroup . .

USER user

CMD ["python", "-m", "pytest", "tests/", "-v"]