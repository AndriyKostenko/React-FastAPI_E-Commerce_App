#!/usr/bin/env bash
# Run all service tests in Docker and report a combined exit code.
# Usage: ./run_tests.sh [--build]

set -euo pipefail

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.test.yml"
BUILD_FLAG=""
[[ "${1:-}" == "--build" ]] && BUILD_FLAG="--build"

TEST_SERVICES=(
  user-service-test
  product-service-test
  payment-service-test
  order-service-test
  notification-service-test
  api-gateway-test
)

cleanup() {
  echo ""
  echo ">>> Tearing down all containers..."
  docker compose $COMPOSE_FILES --profile test down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo ">>> Starting infrastructure (db, redis, rabbitmq, services)..."
docker compose $COMPOSE_FILES --profile test up -d $BUILD_FLAG \
  --scale user-service-test=0 \
  --scale product-service-test=0 \
  --scale payment-service-test=0 \
  --scale order-service-test=0 \
  --scale notification-service-test=0 \
  --scale api-gateway-test=0

echo ">>> Waiting for services to become healthy..."
sleep 5

declare -A EXIT_CODES
OVERALL=0

for SERVICE in "${TEST_SERVICES[@]}"; do
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ">>> Running: $SERVICE"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  set +e
  docker compose $COMPOSE_FILES --profile test run --rm "$SERVICE"
  CODE=$?
  set -e

  EXIT_CODES[$SERVICE]=$CODE
  [[ $CODE -ne 0 ]] && OVERALL=$CODE
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ">>> Test Results Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for SERVICE in "${TEST_SERVICES[@]}"; do
  CODE=${EXIT_CODES[$SERVICE]}
  if [[ $CODE -eq 0 ]]; then
    echo "  ✅  $SERVICE"
  else
    echo "  ❌  $SERVICE (exit code $CODE)"
  fi
done
echo ""

exit $OVERALL
