from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Protocol

from meituan_agent.domain.models import ItineraryItem, ItineraryPlan, Location, POI, SessionState
from meituan_agent.planning.schema import PlanningOutput
from meituan_agent.services.weather_service import is_bad_outdoor
from meituan_agent.tools.base import MapTool, POISearchTool


class LLM(Protocol):
    def chat(self, *, system: str, user: str) -> str: ...


@dataclass(frozen=True)
class PlanningInput:
    state: SessionState
    excluded_poi_ids: set[str]
    last_error: str | None


class Planner(Protocol):
    def plan(self, inp: PlanningInput) -> list[ItineraryPlan]: ...


class FallbackPlanner:
    def __init__(self, primary: Planner, fallback: Planner) -> None:
        self._primary = primary
        self._fallback = fallback

    def plan(self, inp: PlanningInput) -> list[ItineraryPlan]:
        try:
            plans = self._primary.plan(inp)
        except Exception:
            plans = []
        if plans:
            return plans
        return self._fallback.plan(inp)


class HeuristicPlanner:
    def __init__(self, map_tool: MapTool) -> None:
        self._map = map_tool

    def plan(self, inp: PlanningInput) -> list[ItineraryPlan]:
        state = inp.state
        food = _pois_from_scratch(state, "food_candidates", excluded=inp.excluded_poi_ids)
        leisure = _pois_from_scratch(state, "leisure_candidates", excluded=inp.excluded_poi_ids)
        if not food or len(leisure) < 2:
            return []

        plans: list[ItineraryPlan] = []
        have_child = state.profile.has_child
        style = state.profile.style

        # 使用不同餐厅 + 不同休闲组合，确保方案间内容去重
        r1 = food[0]
        r2 = food[1] if len(food) > 1 else food[0]
        l1, l2 = leisure[0], leisure[1]
        l3 = leisure[2] if len(leisure) > 2 else leisure[0]

        if have_child:
            plans.append(self._build_plan(state.location, "亲子优先方案A", "低体力消耗与亲子友好", [l1, r1, l2]))
            plans.append(self._build_plan(state.location, "亲子优先方案B", "低体力消耗与亲子友好", [r2, l2, l3]))
        elif style == "friends":
            plans.append(self._build_plan(state.location, "社交聚会方案A", "增强社交属性与氛围感", [l1, r1, l2]))
            plans.append(self._build_plan(state.location, "社交聚会方案B", "就近组合，减少路程", [l3, r2, l1]))
        else:
            plans.append(self._build_plan(state.location, "推荐方案A", "综合推荐", [l1, r1, l2]))
            plans.append(self._build_plan(state.location, "推荐方案B", "综合推荐", [r2, l3, l1]))

        # 第三方案（如果数据充足）
        if len(food) >= 2 and len(leisure) >= 3:
            plans.append(self._build_plan(state.location, "推荐方案C", "备选推荐", [l2, r2, l3]))

        return plans[:3]

    def _build_plan(self, origin: Location | None, title: str, rationale: str, pois: list[POI]) -> ItineraryPlan:
        items = [ItineraryItem(poi=p) for p in pois]
        if origin:
            items = _enrich_routes(self._map, origin, items)
        return ItineraryPlan(id=f"plan_{uuid.uuid4().hex[:8]}", title=title, items=items, rationale=rationale)


class LLMPlanner:
    def __init__(self, *, llm: LLM, poi_search: POISearchTool, map_tool: MapTool) -> None:
        self._llm = llm
        self._poi_search = poi_search
        self._map = map_tool

    def plan(self, inp: PlanningInput) -> list[ItineraryPlan]:
        state = inp.state
        food = _pois_from_scratch(state, "food_candidates", excluded=inp.excluded_poi_ids)
        leisure = _pois_from_scratch(state, "leisure_candidates", excluded=inp.excluded_poi_ids)
        weather = state.scratch.get("weather")

        if not food:
            food = [
                p
                for p in self._poi_search.search_poi(tag="轻食" if state.profile.fat_loss else "餐饮", location=state.location)
                if p.category == "餐饮"
            ]
        if not leisure:
            if is_bad_outdoor(weather):
                tags = ["博物馆", "展览", "咖啡", "商场", "剧本杀"]
            else:
                tags = ["亲子", "展览", "Citywalk", "剧本杀"]
            out: list[POI] = []
            for t in tags:
                out.extend(self._poi_search.search_poi(tag=t, location=state.location))
            leisure = [p for p in out if p.category != "餐饮"]

        food = [p for p in food if p.id not in inp.excluded_poi_ids][:8]
        leisure = [p for p in leisure if p.id not in inp.excluded_poi_ids][:12]

        if not food:
            food = [p for p in self._poi_search.search_poi(tag="餐饮", location=state.location) if p.category == "餐饮"]
            food = [p for p in food if p.id not in inp.excluded_poi_ids][:8]

        candidates = food + leisure
        if not candidates:
            return []

        system, user = _build_prompt(state, candidates, inp.excluded_poi_ids, inp.last_error)
        raw = self._llm.chat(system=system, user=user)

        parsed = _parse_planning_output(raw)
        plans: list[ItineraryPlan] = []
        poi_index = {p.id: p for p in candidates}
        for pc in parsed.plans:
            items: list[ItineraryItem] = []
            ok = True
            for ref in pc.items:
                poi = poi_index.get(ref.poi_id)
                if not poi:
                    ok = False
                    break
                items.append(ItineraryItem(poi=poi, notes=ref.notes))
            if not ok or len(items) < 2:
                continue
            if state.location:
                items = _enrich_routes(self._map, state.location, items)
            plans.append(ItineraryPlan(id=f"plan_{uuid.uuid4().hex[:8]}", title=pc.title, items=items, rationale=pc.rationale))
        return plans[:3]


def _pois_from_scratch(state: SessionState, key: str, *, excluded: set[str]) -> list[POI]:
    raw = state.scratch.get(key) or []
    pois = [POI.model_validate(x) for x in raw]
    return [p for p in pois if p.id not in excluded]


def _enrich_routes(map_tool: MapTool, origin: Location, items: list[ItineraryItem]) -> list[ItineraryItem]:
    prev = origin
    out: list[ItineraryItem] = []
    for it in items:
        dest = Location(lat=it.poi.lat, lng=it.poi.lng, label=it.poi.name)
        leg = map_tool.route(prev, dest, mode="walk")
        out.append(it.model_copy(update={"travel_from_prev": leg}))
        prev = dest
    return out


def _build_prompt(state: SessionState, candidates: list[POI], excluded: set[str], last_error: str | None) -> tuple[str, str]:
    profile = state.profile.model_dump()
    loc = state.location.model_dump() if state.location else None
    weather = state.scratch.get("weather")

    # 语义分析结果
    semantic = None
    if state.planning_context:
        semantic = state.planning_context.model_dump()

    cand_compact = []
    for p in candidates:
        cand_compact.append(
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "tags": p.tags,
                "rating": p.rating,
                "price": p.price,
                "price_level": p.price_level,
                "address": p.address,
                "business_area": p.business_area,
                "open_hours": p.open_hours,
                "distance_from_user": p.distance_from_user,
            }
        )

    schema = {
        "plans": [
            {
                "title": "string",
                "rationale": "string",
                "items": [
                    {
                        "poi_id": "string",
                        "category": "string",
                        "notes": "string|null",
                        "travel_mode_from_prev": "walk|drive|metro|null",
                    }
                ],
            }
        ]
    }

    system = (
        "你是美团场景的私人规划执行助理，负责输出可落地的行程规划。"
        "你必须严格输出JSON，且只输出JSON，不要输出任何解释文字。"
        "严格遵守用户的所有约束，尤其是hard_constraints中的硬性限制。"
        "【关键】每个方案的 POI 组合必须完全不同。不同方案不能只是顺序不同，"
        "必须选择不同的餐饮/休闲场所，确保用户有真正不同的选择。"
        "如果 candidates 足够多，每个方案应使用不同的餐厅。"
    )

    user = json.dumps(
        {
            "task": "generate_itinerary_plans",
            "constraints": {
                "profile": profile,
                "location": loc,
                "weather": weather,
                "semantic_analysis": semantic,
                "duration_hours": state.profile.duration_hours,
                "must_include": ["餐饮"],
                "excluded_poi_ids": sorted(list(excluded)),
                "last_error": last_error,
            },
            "candidates": cand_compact,
            "output_schema": schema,
            "rules": [
                "输出2-3个plans，每个plan包含2-4个items",
                "items必须只引用candidates里的poi_id",
                "至少包含一个category为餐饮的item",
                "【最重要】不同plan之间POI组合必须完全不同，不能只是顺序调整",
                "每个plan应选择不同的餐厅（除非candidates中只有一家餐厅）",
                "严格遵守semantic_analysis.hard_constraints中的每一条硬性限制",
                "根据semantic_analysis.food选择餐饮（菜系、口味、预算、避讳）",
                "根据semantic_analysis.leisure选择休闲活动（类型、氛围、室内外）",
                "根据semantic_analysis.location约束选点（区域、半径、是否可超出）",
                "根据semantic_analysis.party优化方案（人数、小孩、聚会性质）",
                "根据semantic_analysis.timing安排时间顺序",
                "如果last_error提示dedup或失败，必须选择与之前完全不同的poi_id",
            ],
        },
        ensure_ascii=False,
    )
    return system, user


def _parse_planning_output(raw: str) -> PlanningOutput:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("invalid_json")
    obj = json.loads(text[start : end + 1])
    return PlanningOutput.model_validate(obj)
