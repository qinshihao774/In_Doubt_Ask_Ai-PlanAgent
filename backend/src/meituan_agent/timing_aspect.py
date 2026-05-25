"""
计时切面 — AOP 实现

通过运行时装饰器自动拦截 Agent.run() 方法，透明地记录每个阶段的耗时。
业务代码（Agent / ManagerAgent）无需任何改动。

用法:
    在 Container 初始化后调用 install_timing_aspect(container) 即可。
    之后通过 TimerRegistry 读取计时数据。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TimerRegistry:
    """全局计时注册表 — 收集所有被切面拦截的方法耗时。"""

    _records: list[dict[str, Any]] = []

    @classmethod
    def reset(cls) -> None:
        cls._records.clear()

    @classmethod
    def add(cls, name: str, elapsed_ms: float) -> None:
        cls._records.append({"name": name, "elapsed_ms": elapsed_ms})

    @classmethod
    def get_records(cls) -> list[dict[str, Any]]:
        return list(cls._records)

    @classmethod
    def total_ms(cls) -> float:
        return sum(r["elapsed_ms"] for r in cls._records)

    @classmethod
    def summary(cls) -> str:
        """输出全流程计时摘要，格式化为表格。"""
        if not cls._records:
            return "[timer] 无计时记录"
        lines = ["", "┌─ 流水线计时摘要 ─────────────────────────────┐"]
        total = 0.0
        for r in cls._records:
            ms = r["elapsed_ms"]
            total += ms
            if ms >= 1000:
                lines.append(f"│  {r['name']:<20s}  {ms / 1000:>7.1f}s  │")
            else:
                lines.append(f"│  {r['name']:<20s}  {ms:>7.0f}ms  │")
        lines.append("├───────────────────────────────────────────────┤")
        if total >= 1000:
            lines.append(f"│  {'TOTAL':<20s}  {total / 1000:>7.1f}s  │")
        else:
            lines.append(f"│  {'TOTAL':<20s}  {total:>7.0f}ms  │")
        lines.append("└───────────────────────────────────────────────┘")
        return "\n".join(lines)


def timed(name: str | None = None) -> Callable:
    """装饰器切面 — 拦截函数调用，记录耗时到 TimerRegistry。

    Args:
        name: 计时记录的名称，默认使用函数的 qualname。
    """

    def decorator(fn: Callable) -> Callable:
        label = name or getattr(fn, "__qualname__", fn.__name__)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                TimerRegistry.add(label, elapsed_ms)

        wrapper.__name__ = fn.__name__
        wrapper.__qualname__ = fn.__qualname__
        return wrapper

    return decorator


def install_timing_aspect(container: Any, *, stage_map: dict[str, str] | None = None) -> None:
    """将计时切面织入 Container 中的 Agent 实例。

    自动拦截以下方法:
      - semantic_agent.analyze()  → SemanticAgent
      - map_agent.run()           → MapAgent
      - food_agent.run()          → FoodAgent
      - leisure_agent.run()       → LeisureAgent
      - execution_agent.execute_plan() → ExecutionAgent

    Args:
        container: Container 实例
        stage_map: 可选的方法 → 阶段名映射，默认使用 agent 类名
    """
    default_map = {
        "semantic_agent": ("analyze", "SemanticAgent"),
        "map_agent": ("run", "MapAgent"),
        "food_agent": ("run", "FoodAgent"),
        "leisure_agent": ("run", "LeisureAgent"),
        "execution_agent": ("execute_plan", "ExecutionAgent"),
    }

    for attr_name, (method_name, label) in default_map.items():
        agent = getattr(container, attr_name, None)
        if agent is None:
            continue
        original = getattr(agent, method_name, None)
        if original is None:
            continue
        setattr(agent, method_name, timed(label)(original))
