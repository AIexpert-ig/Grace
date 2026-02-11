#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
TELEGRAM_WEBHOOK_SECRET="${TELEGRAM_WEBHOOK_SECRET:-}"

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

check_with_body() {
  local name="$1"
  local url="$2"
  local body="$3"
  local expected="$4"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$body" "$url")
  if [ "$status" = "$expected" ]; then
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

check_with_body "POST /webhook (missing headers)" "$BASE_URL/webhook" '{"event":"ping"}' "401"

if [ -n "$TELEGRAM_WEBHOOK_SECRET" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "X-Telegram-Bot-Api-Secret-Token: wrong" \
    -d '{"update_id":1,"message":{"message_id":1,"text":"hi","chat":{"id":1,"type":"private"}}}' \
    "$BASE_URL/telegram-webhook")
  if [ "$status" = "401" ]; then
    pass "POST /telegram-webhook (wrong secret)" "$status"
  else
    fail "POST /telegram-webhook (wrong secret)" "$status"
  fi

  status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET" \
    -d '{"update_id":1,"message":{"message_id":1,"text":"hi","chat":{"id":1,"type":"private"}}}' \
    "$BASE_URL/telegram-webhook")
  if [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
    pass "POST /telegram-webhook (correct secret)" "$status"
  else
    fail "POST /telegram-webhook (correct secret)" "$status"
  fi
else
  echo "SKIP - /telegram-webhook secret checks (TELEGRAM_WEBHOOK_SECRET not set)"
fi
