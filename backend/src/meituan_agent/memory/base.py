from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from meituan_agent.domain.models import ChatMessage, SessionState


class MemoryStore(ABC):
    @abstractmethod
    def get_state(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    def put_state(self, state: SessionState) -> None: ...

    @abstractmethod
    def append_message(self, session_id: str, message: ChatMessage) -> None: ...

    @abstractmethod
    def list_messages(self, session_id: str, limit: int = 50) -> list[ChatMessage]: ...

    @abstractmethod
    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]: ...

