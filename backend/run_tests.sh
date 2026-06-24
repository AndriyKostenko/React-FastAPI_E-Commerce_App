#!/usr/bin/env bash
# Run all service tests in Docker and report a combined exit code.
#
# Usage:
#   ./run_tests.sh [--build] [--parallel]
#
# Options:
#   --build    Rebuild images before running tests.
#   --parallel Run all service test containers concurrently (logs interleave).

set -euo pipefail

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.test.yml"
BUILD_FLAG=""
PARALLEL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      BUILD_FLAG="--build"
      shift
      ;;
    --parallel)
      PARALLEL=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--build] [--parallel]" >&2
      exit 1
      ;;
  esac
done

INFRA_SERVICES=(db redis rabbitmq)
TEST_SERVICES=(
  user-service-test
  product-service-test
  payment-service-test
  cart-service-test
  order-service-test
  notification-service-test
  api-gateway-test
)

cleanup() {
  echo ""
  echo ">>> Tearing down test infrastructure..."
  docker compose $COMPOSE_FILES --profile test down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo ">>> Starting test infrastructure (${INFRA_SERVICES[*]})..."
docker compose $COMPOSE_FILES up -d $BUILD_FLAG --wait "${INFRA_SERVICES[@]}"

FAILED_SERVICES=""
OVERALL=0

if [[ "$PARALLEL" == true ]]; then
  echo ">>> Running all service tests in parallel..."
  PIDS=()
  LOG_DIR=$(mktemp -d)

  for SERVICE in "${TEST_SERVICES[@]}"; do
    docker compose $COMPOSE_FILES --profile test run --rm $BUILD_FLAG "$SERVICE" > "$LOG_DIR/$SERVICE.log" 2>&1 &
    PIDS+=("$!:$SERVICE")
  done

  for ENTRY in "${PIDS[@]}"; do
    PID="${ENTRY%%:*}"
    SERVICE="${ENTRY##*:}"
    if ! wait "$PID"; then
      FAILED_SERVICES="$FAILED_SERVICES $SERVICE"
      OVERALL=1
    fi
  done

  echo ""
  echo ">>> Test logs are available in $LOG_DIR"
else
  echo ">>> Running service tests sequentially..."
  for SERVICE in "${TEST_SERVICES[@]}"; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ">>> Running: $SERVICE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    set +e
    docker compose $COMPOSE_FILES --profile test run --rm $BUILD_FLAG "$SERVICE"
    CODE=$?
    set -e

    if [[ $CODE -ne 0 ]]; then
      FAILED_SERVICES="$FAILED_SERVICES $SERVICE"
      OVERALL=$CODE
    fi
  done
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ">>> Test Results Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for SERVICE in "${TEST_SERVICES[@]}"; do
  if echo "$FAILED_SERVICES" | grep -qw "$SERVICE"; then
    echo "  ❌  $SERVICE"
  else
    echo "  ✅  $SERVICE"
  fi
done
echo ""

exit $OVERALL
