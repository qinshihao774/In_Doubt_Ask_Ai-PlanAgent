from __future__ import annotations

from meituan_agent.config import Settings
from meituan_agent.memory.base import MemoryStore
from meituan_agent.memory.inmemory import InMemoryStore
from meituan_agent.memory.sqlite_store import SQLiteStore


def build_memory_store(settings: Settings) -> MemoryStore:
    backend = (settings.memory_backend or "sqlite").lower()
    if backend == "memory":
        return InMemoryStore()
    return SQLiteStore(settings.sqlite_path)

