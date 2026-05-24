from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from meituan_agent.domain.models import ChatMessage, SessionState
from meituan_agent.memory.base import MemoryStore


class SQLiteStore(MemoryStore):
    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_message (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts TEXT NOT NULL
                )
                """
            )

    def get_state(self, session_id: str) -> SessionState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return SessionState.model_validate_json(row["state_json"])

    def put_state(self, state: SessionState) -> None:
        payload = state.model_dump_json()
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_state(session_id, state_json, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (state.session_id, payload, now),
            )

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_message(session_id, role, content, ts) VALUES(?,?,?,?)",
                (session_id, message.role, message.content, message.ts.isoformat()),
            )

    def list_messages(self, session_id: str, limit: int = 50) -> list[ChatMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, ts
                FROM session_message
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        rows = list(reversed(rows))
        out: list[ChatMessage] = []
        for r in rows:
            out.append(
                ChatMessage(
                    role=r["role"],
                    content=r["content"],
                    ts=datetime.fromisoformat(r["ts"]),
                )
            )
        return out

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  s.session_id,
                  s.updated_at,
                  (
                    SELECT role
                    FROM session_message m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.id DESC
                    LIMIT 1
                  ) AS last_role,
                  (
                    SELECT content
                    FROM session_message m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.id DESC
                    LIMIT 1
                  ) AS last_content,
                  (
                    SELECT ts
                    FROM session_message m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.id DESC
                    LIMIT 1
                  ) AS last_ts
                FROM session_state s
                ORDER BY s.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "session_id": r["session_id"],
                    "updated_at": r["updated_at"],
                    "last_role": r["last_role"],
                    "last_content": r["last_content"],
                    "last_ts": r["last_ts"],
                }
            )
        return out

