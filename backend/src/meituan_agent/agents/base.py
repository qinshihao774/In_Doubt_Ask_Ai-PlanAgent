from __future__ import annotations

from abc import ABC, abstractmethod

from meituan_agent.domain.models import SessionState


class Agent(ABC):
    @abstractmethod
    def run(self, state: SessionState, user_message: str) -> SessionState: ...

