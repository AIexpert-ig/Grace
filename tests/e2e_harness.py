import os
import sys
import time

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
ENABLE_RETELL_SIMULATION = os.getenv("ENABLE_RETELL_SIMULATION", "false").lower() == "true"
ENABLE_MAKE_WEBHOOKS = os.getenv("ENABLE_MAKE_WEBHOOKS", "false").lower() == "true"
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")


def _print_result(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"{status} - {label}{suffix}")
    return ok


def _print_skip(label: str, reason: str) -> None:
    print(f"SKIP - {label} ({reason})")


def _is_local_url(url: str) -> bool:
    return url.startswith("http://127.0.0.1") or url.startswith("http://localhost")


def main() -> int:
    if not ADMIN_TOKEN:
        _print_result("ADMIN_TOKEN present", False, "missing ADMIN_TOKEN env")
        return 1

    failures = 0

    with httpx.Client(timeout=5.0) as client:
        # 1) Deadletter admin ping
        res = client.get(
            f"{BASE_URL}/events/deadletter",
            headers={"X-Admin-Token": ADMIN_TOKEN},
        )
        if not _print_result("GET /events/deadletter", res.status_code == 200, f"status={res.status_code}"):
            failures += 1

        # 2) Retell simulate (flag OFF -> 404, flag ON -> 200)
        retell_body = {
            "call_id": "e2e-call-id",
            "event": "call_simulated",
            "transcript": "E2E test",
            "timestamp": int(time.time()),
        }

        if not ENABLE_RETELL_SIMULATION:
            res = client.post(f"{BASE_URL}/webhooks/retell/simulate", json=retell_body)
            if not _print_result(
                "POST /webhooks/retell/simulate (flag OFF)",
                res.status_code == 404,
                f"status={res.status_code}",
            ):
                failures += 1
        else:
            res = client.post(f"{BASE_URL}/webhooks/retell/simulate", json=retell_body)
            if not _print_result(
                "POST /webhooks/retell/simulate (flag ON)",
                res.status_code == 200,
                f"status={res.status_code}",
            ):
                failures += 1

        # 3) Make trigger
        make_envelope = {
            "version": "v1",
            "source": "e2e",
            "type": "make.trigger",
            "idempotency_key": "e2e-idem",
            "timestamp": int(time.time()),
            "correlation_id": "e2e-correlation",
            "payload": {"origin": "e2e"},
        }

        if not ENABLE_MAKE_WEBHOOKS:
            res = client.post(
                f"{BASE_URL}/integrations/make/trigger",
                json=make_envelope,
                headers={"X-Admin-Token": ADMIN_TOKEN},
            )
            if not _print_result(
                "POST /integrations/make/trigger (flag OFF)",
                res.status_code == 404,
                f"status={res.status_code}",
            ):
                failures += 1
        else:
            if not MAKE_WEBHOOK_URL:
                _print_skip("POST /integrations/make/trigger (flag ON)", "MAKE_WEBHOOK_URL not set")
            elif not _is_local_url(MAKE_WEBHOOK_URL):
                _print_skip("POST /integrations/make/trigger (flag ON)", "MAKE_WEBHOOK_URL not local")
            else:
                res = client.post(
                    f"{BASE_URL}/integrations/make/trigger",
                    json=make_envelope,
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                )
                if not _print_result(
                    "POST /integrations/make/trigger (flag ON)",
                    res.status_code == 200,
                    f"status={res.status_code}",
                ):
                    failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
