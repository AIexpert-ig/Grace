import hashlib
import hmac
import time

import pytest

from app.core.security import (
    SignatureExpiredError,
    SignatureInvalidError,
    SignatureMissingError,
    verify_hmac_signature,
)


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode() + b"." + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def test_verify_hmac_signature_valid(monkeypatch):
    secret = "test-secret"
    body = b'{"hello": "world"}'
    timestamp = "1700000000"
    signature = _sign(secret, timestamp, body)

    monkeypatch.setattr(time, "time", lambda: 1700000001)

    verify_hmac_signature(
        raw_body=body,
        timestamp=timestamp,
        signature=signature,
        secret=secret,
        tolerance_seconds=300,
    )


def test_verify_hmac_signature_invalid(monkeypatch):
    secret = "test-secret"
    body = b"{}"
    timestamp = "1700000000"

    monkeypatch.setattr(time, "time", lambda: 1700000001)

    with pytest.raises(SignatureInvalidError):
        verify_hmac_signature(
            raw_body=body,
            timestamp=timestamp,
            signature="deadbeef",
            secret=secret,
            tolerance_seconds=300,
        )


def test_verify_hmac_signature_missing_timestamp_or_signature():
    secret = "test-secret"
    body = b"{}"

    with pytest.raises(SignatureMissingError):
        verify_hmac_signature(
            raw_body=body,
            timestamp=None,
            signature="abcd",
            secret=secret,
            tolerance_seconds=300,
        )

    with pytest.raises(SignatureMissingError):
        verify_hmac_signature(
            raw_body=body,
            timestamp="1700000000",
            signature=None,
            secret=secret,
            tolerance_seconds=300,
        )


def test_verify_hmac_signature_expired(monkeypatch):
    secret = "test-secret"
    body = b"{}"
    timestamp = "1700000000"
    signature = _sign(secret, timestamp, body)

    monkeypatch.setattr(time, "time", lambda: 1700000401)

    with pytest.raises(SignatureExpiredError):
        verify_hmac_signature(
            raw_body=body,
            timestamp=timestamp,
            signature=signature,
            secret=secret,
            tolerance_seconds=300,
        )


def test_verify_hmac_signature_uses_raw_bytes(monkeypatch):
    secret = "test-secret"
    raw_body = b'{"hello": "world"}'
    timestamp = "1700000000"
    signature = _sign(secret, timestamp, raw_body)

    monkeypatch.setattr(time, "time", lambda: 1700000001)

    verify_hmac_signature(
        raw_body=raw_body,
        timestamp=timestamp,
        signature=signature,
        secret=secret,
        tolerance_seconds=300,
    )

    altered_body = b'{"hello":"world"}'
    with pytest.raises(SignatureInvalidError):
        verify_hmac_signature(
            raw_body=altered_body,
            timestamp=timestamp,
            signature=signature,
            secret=secret,
            tolerance_seconds=300,
        )
