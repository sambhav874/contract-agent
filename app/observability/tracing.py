"""Observability tracing."""

import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator

from app.observability.logger import get_logger

logger = get_logger(__name__)


class Trace:
    def __init__(self, name: str, trace_id: str | None = None) -> None:
        self.name = name
        self.trace_id = trace_id or str(uuid.uuid4())
        self.spans: list[dict[str, Any]] = []
        self._current_span: dict[str, Any] | None = None

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self._current_span = {
            "span_id": str(uuid.uuid4()),
            "name": name,
            "start_time": time.time(),
            "attributes": attributes or {},
        }

    def end_span(self, error: Exception | None = None) -> None:
        if self._current_span is None:
            return
        self._current_span["end_time"] = time.time()
        self._current_span["duration_ms"] = round(
            (self._current_span["end_time"] - self._current_span["start_time"]) * 1000, 2
        )
        if error:
            self._current_span["error"] = str(error)
        self.spans.append(self._current_span)
        self._current_span = None

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        if self._current_span is not None:
            self._current_span.setdefault("events", []).append(
                {"name": name, "timestamp": time.time(), "attributes": attributes or {}}
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "spans": self.spans,
        }


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Generator[Trace, None, None]:
    t = Trace(name)
    t.start_span(name, attributes)
    try:
        yield t
        t.end_span()
    except Exception as e:
        t.end_span(error=e)
        raise
