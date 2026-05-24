from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

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

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for sid, st in self._states.items():
            msgs = list(self._messages.get(sid, deque()))
            last = msgs[-1] if msgs else None
            items.append(
                {
                    "session_id": sid,
                    "updated_at": (last.ts.isoformat() if last else None),
                    "last_role": (last.role if last else None),
                    "last_content": (last.content if last else None),
                    "last_ts": (last.ts.isoformat() if last else None),
                }
            )
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items[offset : offset + limit]

