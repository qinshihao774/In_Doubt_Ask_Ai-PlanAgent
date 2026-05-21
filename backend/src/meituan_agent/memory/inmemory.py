from __future__ import annotations

from collections import defaultdict, deque

from meituan_agent.domain.models import ChatMessage, SessionState
from meituan_agent.memory.base import MemoryStore


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._states: dict[str, SessionState] = {}
        self._messages: dict[str, deque[ChatMessage]] = defaultdict(lambda: deque(maxlen=500))

    def get_state(self, session_id: str) -> SessionState | None:
        return self._states.get(session_id)

    def put_state(self, state: SessionState) -> None:
        self._states[state.session_id] = state

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        self._messages[session_id].append(message)

    def list_messages(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        msgs = list(self._messages.get(session_id, deque()))
        return msgs[-limit:]

