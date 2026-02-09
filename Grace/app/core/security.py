import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request

from app.core.config import settings


@dataclass
class SignatureError(Exception):
    code: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class SignatureMissingError(SignatureError):
    def __init__(self, message: str = "Missing signature or timestamp") -> None:
        super().__init__(code="missing_signature", message=message)


class SignatureInvalidError(SignatureError):
    def __init__(self, message: str = "Invalid signature") -> None:
        super().__init__(code="invalid_signature", message=message)


class SignatureExpiredError(SignatureError):
    def __init__(self, message: str = "Signature timestamp expired") -> None:
        super().__init__(code="expired_signature", message=message)


def verify_hmac_signature(
    *,
    raw_body: bytes,
    timestamp: Optional[str | int],
    signature: Optional[str],
    secret: str,
    tolerance_seconds: int,
) -> None:
    if not timestamp or not signature:
        raise SignatureMissingError()

    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        raise SignatureInvalidError("Invalid timestamp")

    now = int(time.time())
    if abs(now - timestamp_int) > tolerance_seconds:
        raise SignatureExpiredError()

    timestamp_str = str(timestamp)
    message = timestamp_str.encode() + b"." + raw_body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise SignatureInvalidError()


async def verify_retell_signature(request: Request) -> None:
    if not settings.RETELL_SIGNING_SECRET:
        return

    signature = request.headers.get("X-Retell-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    body = await request.body()
    expected = hmac.new(
        settings.RETELL_SIGNING_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")
