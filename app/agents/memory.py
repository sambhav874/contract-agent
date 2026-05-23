"""Working memory for agent session management."""

import time
from typing import Any, Optional
from app.llm.gemini_client import call_gemini
from app.config import settings


class WorkingMemory:
    def __init__(self, history_limit: int = 20, summarize_threshold: int = 10):
        self.history_limit = history_limit
        self.summarize_threshold = summarize_threshold
        self.messages: list = []
        self.summaries: list = []
        self.token_estimates: list[int] = []
        self._estimated_total = 0

    def append(self, message) -> None:
        self.messages.append(message)
        self._maybe_summarize()
        self._maybe_evict()

    def get_messages(self) -> list:
        return self.summaries + self.messages

    def _maybe_summarize(self) -> None:
        if len(self.messages) >= self.summarize_threshold:
            # Summarize oldest messages
            to_summarize = self.messages[: self.summarize_threshold]
            summary = self._summarize_messages(to_summarize)
            self.summaries.append(summary)
            self.messages = self.messages[self.summarize_threshold :]

    def _summarize_messages(self, messages: list) -> Any:
        text = "\n".join(str(m) for m in messages)
        return {"role": "system", "content": f"[Summary of prior conversation]: {text[:500]}..."}

    def _maybe_evict(self) -> None:
        if len(self.messages) + len(self.summaries) > self.history_limit:
            if self.summaries:
                self.summaries.pop(0)
            else:
                self.messages = self.messages[-self.history_limit:]

    @property
    def size(self) -> int:
        return len(self.messages) + len(self.summaries)
