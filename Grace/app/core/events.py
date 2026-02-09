import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings


logger = logging.getLogger("GRACE_BUS")


@dataclass(frozen=True)
class EventEnvelope:
    version: str
    source: str
    type: str
    idempotency_key: str
    timestamp: int
    correlation_id: str
    payload: Dict[str, Any]

    def __post_init__(self) -> None:
        if self.version != "v1":
            raise ValueError("Unsupported envelope version")
        if not self.source or not self.type:
            raise ValueError("Envelope requires source and type")
        if not self.idempotency_key:
            raise ValueError("Envelope requires idempotency_key")
        if not self.correlation_id:
            raise ValueError("Envelope requires correlation_id")


@dataclass
class PublishResult:
    status: str
    correlation_id: str
    envelope: EventEnvelope


@dataclass(frozen=True)
class _HandlerRegistration:
    source: Optional[str]
    event_type: Optional[str]
    handler: Callable[[EventEnvelope], Any]

    def matches(self, envelope: EventEnvelope) -> bool:
        if self.source and self.source != envelope.source:
            return False
        if self.event_type and self.event_type != envelope.type:
            return False
        return True


class EventBus:
    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self._handlers: List[_HandlerRegistration] = []
        self._idempotency: Dict[str, float] = {}
        self._deadletters: List[Dict[str, Any]] = []
        self._ttl_seconds = ttl_seconds or settings.IDEMPOTENCY_TTL_SECONDS
        self._max_deadletters = 200

    def register_handler(
        self,
        *,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        handler: Callable[[EventEnvelope], Any],
    ) -> None:
        self._handlers.append(_HandlerRegistration(source, event_type, handler))

    def subscribe(self, event_type: str, handler: Callable[[EventEnvelope], Any]) -> None:
        self.register_handler(event_type=event_type, handler=handler)

    async def publish(self, envelope: Any, payload: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None) -> PublishResult:
        if not isinstance(envelope, EventEnvelope):
            event_type = envelope
            if payload is None:
                raise ValueError("Legacy publish requires payload")
            corr_id = correlation_id or str(uuid.uuid4())
            envelope = EventEnvelope(
                version="v1",
                source="legacy",
                type=event_type,
                idempotency_key=corr_id,
                timestamp=int(time.time()),
                correlation_id=corr_id,
                payload=payload,
            )

        self._purge_expired()

        if self._is_duplicate(envelope.idempotency_key):
            return PublishResult(status="duplicate", correlation_id=envelope.correlation_id, envelope=envelope)

        self._mark_processed(envelope.idempotency_key)

        failures = []
        for registration in self._handlers:
            if registration.matches(envelope):
                success, error = await self._dispatch_with_retry(registration.handler, envelope)
                if not success:
                    failures.append(error)
                    self._record_deadletter(envelope, registration.handler, error)

        status = "failed" if failures else "processed"
        return PublishResult(status=status, correlation_id=envelope.correlation_id, envelope=envelope)

    def get_deadletters(self) -> List[Dict[str, Any]]:
        return list(self._deadletters)

    def _purge_expired(self) -> None:
        now = time.time()
        expired_keys = [key for key, exp in self._idempotency.items() if exp <= now]
        for key in expired_keys:
            self._idempotency.pop(key, None)

    def _is_duplicate(self, key: str) -> bool:
        exp = self._idempotency.get(key)
        return exp is not None and exp > time.time()

    def _mark_processed(self, key: str) -> None:
        self._idempotency[key] = time.time() + self._ttl_seconds

    async def _dispatch_with_retry(self, handler: Callable[[EventEnvelope], Any], envelope: EventEnvelope) -> tuple[bool, Optional[Exception]]:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(envelope)
                else:
                    handler(envelope)
                return True, None
            except Exception as exc:  # pragma: no cover - defensive
                if attempt >= max_attempts:
                    return False, exc
                await asyncio.sleep(0.1 * (2 ** (attempt - 1)))
        return False, None

    def _record_deadletter(self, envelope: EventEnvelope, handler: Callable[[EventEnvelope], Any], error: Exception) -> None:
        entry = {
            "envelope": envelope,
            "handler": getattr(handler, "__name__", "handler"),
            "error": str(error),
            "timestamp": int(time.time()),
        }
        self._deadletters.append(entry)
        if len(self._deadletters) > self._max_deadletters:
            self._deadletters = self._deadletters[-self._max_deadletters :]


bus = EventBus()
