"""
FoodAgent — 餐饮搜索

从 SemanticSchema 中读取餐饮约束，按需搜索。
无硬编码标签 —— 搜索标签完全由语义分析结果驱动。
"""

from __future__ import annotations

from meituan_agent.agents.base import Agent
from meituan_agent.domain.models import POI, SemanticSchema, SessionState
from meituan_agent.tools.base import POISearchTool


class FoodAgent(Agent):
    def __init__(self, poi_search: POISearchTool) -> None:
        self._poi_search = poi_search

    def run(self, state: SessionState, _user_message: str) -> SessionState:
        schema: SemanticSchema | None = state.planning_context
        food = schema.food if schema else None

        # 从语义分析结果中提取搜索标签（全部可空，动态推理）
        search_tags: list[str] = []
        if food and food.cuisine_types:
            search_tags = list(food.cuisine_types)
        elif food and food.dietary:
            search_tags = list(food.dietary)
        else:
            search_tags = ["餐饮"]

        # 逐标签搜索
        candidates: list[POI] = []
        for tag in search_tags:
            candidates.extend(
                _search_incrementally(self._poi_search, tag=tag, location=state.location, min_results=6)
            )

        # 去重 + 仅保留餐饮类
        seen: set[str] = set()
        uniq: list[POI] = []
        for p in candidates:
            if p.id in seen:
                continue
            if "餐饮" not in p.category:
                continue
            seen.add(p.id)
            uniq.append(p)

        # 根据约束过滤
        if food:
            uniq = self._apply_constraints(uniq, food)

        if not uniq:
            cached = state.scratch.get("nearby_food") or []
            uniq = [POI.model_validate(x) for x in cached if "餐饮" in (x.get("category") or "")]
            if food:
                uniq = self._apply_constraints(uniq, food)

        state.scratch["food_candidates"] = [p.model_dump() for p in uniq]
        return state

    @staticmethod
    def _apply_constraints(pois: list[POI], food) -> list[POI]:
        """根据语义约束过滤 POI 列表"""
        result = list(pois)

        if food.avoid:
            result = [
                p for p in result
                if not any(a in (p.name + "".join(p.tags)) for a in food.avoid)
            ]

        if food.budget_per_person:
            max_price = food.budget_per_person * 1.2
            result = [
                p for p in result
                if p.price is None or p.price <= max_price
            ]

        return result or pois


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
