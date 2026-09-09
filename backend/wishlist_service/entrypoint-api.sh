#!/usr/bin/env sh
# Bring the schema up to date, then serve.
#
# This service no longer bootstraps its own tables: create_all cannot alter an
# existing table, so a database that predated a model change came up missing
# columns while the service reported a clean startup. Alembic is the only
# schema authority now, and running it here is what keeps migrations from
# being a step someone has to remember by hand.
set -e

echo "Running wishlist_service database migrations..."
alembic upgrade head

mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
rm -rf "${PROMETHEUS_MULTIPROC_DIR:?}"/*

exec gunicorn -k uvicorn.workers.UvicornWorker main:app \
    --bind 0.0.0.0:8009 \
    --workers "${GUNICORN_WORKERS:-1}" \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile -
