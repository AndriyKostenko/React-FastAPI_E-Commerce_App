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
    && addgroup --system --gid 1005 ordergroup \
    && adduser --system --uid 1005 --ingroup ordergroup orderuser \
    && mkdir -p /app/logs \
    && mkdir -p /media/images \
    && mkdir -p /media/icons \
    && chown -R orderuser:ordergroup /app \
    && chown -R orderuser:ordergroup /media

# Copy dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Set up PATH to include both uv and venv
ENV PATH="/app/.venv/bin:$PATH"

# Create a non-root user and set permissions
COPY --chown=orderuser:ordergroup . .

# Ensure the app runs as a non-root user
USER orderuser

# Port configuration
EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

# Use Gunicorn for multi-worker production server (without Kubernetes!...if with Kubernetes, use uvicorn with other settings instead !)
# workers = (2 × CPU cores) + 1 - recommended baseline from Gunicorn’s official documentation. (4-5  are optimum )
# Each Gunicorn worker is a separate process.
# If you're using uvicorn.workers.UvicornWorker, then each worker runs a full async FastAPI app.

# ( automatically detects the number of CPU cores and sets the number of workers accordingly )
# CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8002 --workers $(nproc) --timeout 60 --access-logfile -"]

#CMD ["uv", "run", "gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8002", "--workers", "1", "--timeout", "60", "--access-logfile"]

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8005", "--workers", "1", "--timeout", "60", "--access-logfile", "-"]
