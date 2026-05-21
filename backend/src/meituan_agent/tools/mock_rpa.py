from __future__ import annotations

from typing import Any

from meituan_agent.tools.base import RPAExecutor


class MockRPAExecutor(RPAExecutor):
    """Offline RPA stub for tests."""

    def execute(self, *, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "action": action,
            "payload": payload,
            "message": "mock_rpa_executed",
        }
