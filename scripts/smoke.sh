#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"

pass() { printf 'PASS - %s (status=%s)\n' "$1" "$2"; }
fail() { printf 'FAIL - %s (status=%s)\n' "$1" "$2"; }

if [ -z "$ADMIN_TOKEN" ]; then
  echo "ADMIN_TOKEN is required"
  exit 1
fi

check() {
  local name="$1"
  local method="$2"
  local url="$3"
  local status
  if [ "$method" = "GET" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" -H "X-Admin-Token: $ADMIN_TOKEN" "$url")
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "X-Admin-Token: $ADMIN_TOKEN" "$url")
  fi

  if [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
    pass "$name" "$status"
  else
    fail "$name" "$status"
  fi
}

check "GET /health" "GET" "$BASE_URL/health"
check "GET /__build" "GET" "$BASE_URL/__build"
check "GET /events/deadletter" "GET" "$BASE_URL/events/deadletter"
check "GET /integrations/test/telegram" "GET" "$BASE_URL/integrations/test/telegram"
check "GET /integrations/test/make" "GET" "$BASE_URL/integrations/test/make"
