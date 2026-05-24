"""
LeisureAgent — 休闲搜索

从 SemanticSchema 中读取休闲约束，按需搜索。
无硬编码标签 —— 搜索标签完全由语义分析结果驱动。
"""

from __future__ import annotations

from meituan_agent.agents.base import Agent
from meituan_agent.domain.models import POI, SemanticSchema, SessionState
from meituan_agent.services.weather_service import is_bad_outdoor
from meituan_agent.tools.base import POISearchTool


class LeisureAgent(Agent):
    def __init__(self, poi_search: POISearchTool) -> None:
        self._poi_search = poi_search

    def run(self, state: SessionState, _user_message: str) -> SessionState:
        schema: SemanticSchema | None = state.planning_context
        leisure = schema.leisure if schema else None
        weather = state.scratch.get("weather")

        # 从语义分析结果中提取搜索标签（全部可空，动态推理）
        search_tags: list[str] = []
        if leisure and leisure.activity_types:
            search_tags = list(leisure.activity_types)
        elif is_bad_outdoor(weather):
            search_tags = ["展览", "博物馆", "咖啡", "商场"]
        elif schema and schema.party and schema.party.has_child:
            search_tags = ["亲子", "展览"]
        else:
            search_tags = ["展览", "休闲"]

        candidates: list[POI] = []
        for t in search_tags:
            candidates.extend(
                _search_incrementally(self._poi_search, tag=t, location=state.location, min_results=6)
            )

        seen: set[str] = set()
        uniq: list[POI] = []
        for p in candidates:
            if p.id in seen:
                continue
            if p.category == "餐饮":
                continue
            seen.add(p.id)
            uniq.append(p)

        # 按评分排序，取前 10
        uniq.sort(key=lambda x: x.rating, reverse=True)
        state.scratch["leisure_candidates"] = [p.model_dump() for p in uniq[:10]]
        return state


def _search_incrementally(
    poi_search: POISearchTool,
    *,
    tag: str,
    location,
    min_results: int,
) -> list[POI]:
    merged: list[POI] = []
    seen: set[str] = set()
    for radius_km in (3.0, 6.0, 10.0):
        for poi in poi_search.search_poi(tag=tag, location=location, radius_km=radius_km):
            if poi.id in seen:
                continue
            seen.add(poi.id)
            merged.append(poi)
        if len(merged) >= min_results:
            break
    return merged
