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
# Final Runtime Stage
# -------------------------
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
    && addgroup --system --gid 1007 paymentgroup \
    && adduser --system --uid 1007 --ingroup paymentgroup paymentuser \
    && mkdir -p /app/logs \
    && chown -R paymentuser:paymentgroup /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=paymentuser:paymentgroup . .

USER paymentuser

EXPOSE 8006

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8006/health || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8006", "--workers", "1", "--timeout", "60", "--access-logfile", "-"]
