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
# Final Runtime Stage
# -------------------------
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime dependencies (smaller footprint than build stage)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1004 notificationconsumer_group \
    && adduser --system --uid 1004 --ingroup notificationconsumer_group notificationconsumer_user \
    && mkdir -p /app/logs \
    && chown -R notificationconsumer_user:notificationconsumer_group /app

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Set up PATH to include both uv and venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and set permissions
COPY --chown=notificationconsumer_user:notificationconsumer_group . .

USER notificationconsumer_user

# Expose app port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Use faststream run to start the consumer
CMD ["faststream", "run", "main:app"]