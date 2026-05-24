from __future__ import annotations

import uuid
from typing import Any

from meituan_agent.domain.models import ChatMessage, Location, SessionState, SessionStatus
from meituan_agent.memory.base import MemoryStore
from meituan_agent.agents.manager_agent import ManagerAgent


class SessionService:
    def __init__(self, memory: MemoryStore, manager: ManagerAgent) -> None:
        self._memory = memory
        self._manager = manager

    def ensure_session(self, session_id: str | None) -> SessionState:
        sid = session_id or f"sess_{uuid.uuid4().hex[:10]}"
        existing = self._memory.get_state(sid)
        if existing:
            return existing
        state = SessionState(session_id=sid, status=SessionStatus.planning)
        self._memory.put_state(state)
        return state

    def set_bootstrap_location(self, session_id: str, location: Location | None) -> SessionState:
        state = self.ensure_session(session_id)
        if location and not state.scratch.get("location_hint"):
            state.location = location
            state.scratch["bootstrap_location"] = location.model_dump()
            self._memory.put_state(state)
        return state

    def chat(self, *, session_id: str | None, message: str, bootstrap_location: Location | None = None) -> tuple[SessionState, str]:
        state = self.ensure_session(session_id)
        if bootstrap_location and not state.scratch.get("location_hint"):
            state.location = bootstrap_location
            state.scratch["bootstrap_location"] = bootstrap_location.model_dump()
        self._memory.append_message(state.session_id, ChatMessage(role="user", content=message))

        state, reply = self._manager.step(state, message)

        self._memory.put_state(state)
        self._memory.append_message(state.session_id, ChatMessage(role="assistant", content=reply))
        return state, reply

    def chat_raw(self, *, session_id: str | None, message: str, bootstrap_location: Location | None = None) -> tuple[SessionState, str]:
        state = self.ensure_session(session_id)
        if bootstrap_location and not state.scratch.get("location_hint"):
            state.location = bootstrap_location
            state.scratch["bootstrap_location"] = bootstrap_location.model_dump()
        self._memory.append_message(state.session_id, ChatMessage(role="user", content=message))

        state, reply = self._manager.step(state, message, use_llm=False)

        self._memory.put_state(state)
        return state, reply

    def append_assistant(self, session_id: str, reply: str) -> None:
        self._memory.append_message(session_id, ChatMessage(role="assistant", content=reply))

    def get_state(self, session_id: str) -> SessionState | None:
        return self._memory.get_state(session_id)

    def get_messages(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        return self._memory.list_messages(session_id, limit=limit)

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self._memory.list_sessions(limit=limit, offset=offset)

