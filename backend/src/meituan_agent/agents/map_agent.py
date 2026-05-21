from __future__ import annotations

from meituan_agent.agents.base import Agent
from meituan_agent.domain.models import ItineraryItem, Location, POI, SessionState
from meituan_agent.location_parser import extract_location_hint
from meituan_agent.tools.base import MapTool


class MapAgent(Agent):
    def __init__(self, map_tool: MapTool) -> None:
        self._map = map_tool

    def run(self, state: SessionState, user_message: str) -> SessionState:
        schema = state.planning_context
        loc_constraint = schema.location if schema else None

        # 1) 位置提示：语义分析结果优先
        hint = None
        if loc_constraint and loc_constraint.area:
            hint = loc_constraint.area
        if not hint:
            hint = state.scratch.get("location_hint") or extract_location_hint(user_message)
        if hint:
            state.scratch["location_hint"] = hint

        # 2) 城市上下文
        city = None
        if state.location and state.location.label:
            label = state.location.label
            for suffix in ["市", "省", "自治区", "县"]:
                label = label.replace(suffix, "")
            city = label

        # 3) 位置解析
        location = state.location

        if not location and hint and hasattr(self._map, "geocode"):
            try:
                result = self._map.geocode(hint, city=city)
                if result:
                    location = result
            except Exception:
                pass

        if not location and hasattr(self._map, "ip_location"):
            try:
                location = self._map.ip_location()
            except Exception:
                pass

        if not location:
            location = Location(lat=39.908, lng=116.397, label="北京·天安门")

        state.location = location

        # 4) 搜索半径：优先用语义分析结果，未指定默认 3km
        radius = (loc_constraint.radius_km if loc_constraint and loc_constraint.radius_km is not None else 3.0)
        state.scratch["search_radius_km"] = float(radius)

        # 5) 周边 POI 预搜索
        if hasattr(self._map, "search_poi"):
            try:
                food_pois = self._map.search_poi(tag="美食", location=location, radius_km=float(radius))
                state.scratch["nearby_food"] = [p.model_dump() for p in food_pois[:15]]
            except Exception:
                state.scratch["nearby_food"] = []

            try:
                leisure_pois = self._map.search_poi(tag="休闲", location=location, radius_km=float(radius))
                state.scratch["nearby_leisure"] = [p.model_dump() for p in leisure_pois[:15]]
            except Exception:
                state.scratch["nearby_leisure"] = []

            state.scratch["nearby_location_label"] = location.label

        return state

    def enrich_routes(self, origin: Location, items: list[ItineraryItem], *, mode: str = "walk") -> list[ItineraryItem]:
        prev = origin
        out: list[ItineraryItem] = []
        for it in items:
            dest = it.poi.location or Location(lat=it.poi.lat, lng=it.poi.lng, label=it.poi.name)
            leg = self._map.route(prev, dest, mode=mode)
            out.append(it.model_copy(update={"travel_from_prev": leg}))
            prev = dest
        return out
