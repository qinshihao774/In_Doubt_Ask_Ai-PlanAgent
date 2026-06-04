from __future__ import annotations

import math
import re
import time

from meituan_agent.agents.base import Agent
from meituan_agent.domain.models import ItineraryItem, Location, POI, SessionState
from meituan_agent.location_parser import extract_location_hint
from meituan_agent.services.weather_service import WeatherService
from meituan_agent.tools.base import MapTool


LOCAL_HINT_MAX_DISTANCE_KM = 80.0
LOCAL_PLACE_MAX_DISTANCE_KM = 15.0
LOCAL_PLACE_SEARCH_RADII_KM = (3.0, 8.0, 15.0)
VENUE_EVIDENCE_POLICY = "address_or_business_area_or_name"


class MapAgent(Agent):
    def __init__(self, map_tool: MapTool, weather: WeatherService | None = None) -> None:
        self._map = map_tool
        self._weather = weather

    def run(self, state: SessionState, user_message: str) -> SessionState:
        schema = state.planning_context
        loc_constraint = schema.location if schema else None

        # 1) 位置提示：语义分析结果优先
        prev_hint = state.scratch.get("location_hint")
        hint = None
        hint_source = None
        if loc_constraint and loc_constraint.area:
            hint = loc_constraint.area
            hint_source = "semantic"
        if not hint:
            extracted = extract_location_hint(user_message)
            if extracted:
                hint = extracted
                hint_source = "message"
        if not hint and prev_hint:
            hint = prev_hint
            hint_source = "memory"
        if hint:
            hint = _clean_hint_for_geocoding(hint)
            state.scratch["location_hint"] = hint
            state.scratch["location_hint_source"] = hint_source
            if hint_source in {"semantic", "message"}:
                state.scratch.pop("intended_place_poi", None)
            venue_constraint = _extract_venue_constraint(user_message, hint)
            if venue_constraint:
                state.scratch["venue_constraint"] = venue_constraint
                _add_venue_hard_constraint(state, venue_constraint["name"])
            elif hint_source in {"semantic", "message"}:
                state.scratch.pop("venue_constraint", None)

        # 2) 城市上下文：有浏览器定位时，模糊地名优先在当前城市/区域内解析。
        city = _derive_city_context(state.location.label if state.location else None)

        # 3) 位置解析
        location = state.location
        trusted_current = _has_trusted_user_location(state)
        resolved_nearby_hint = False

        should_geocode = False
        if hint and hasattr(self._map, "geocode"):
            if not location:
                should_geocode = True
            elif trusted_current:
                should_geocode = _should_geocode_with_trusted_location(
                    user_message,
                    hint=hint,
                    hint_source=hint_source,
                    previous_hint=prev_hint,
                )
            elif state.scratch.get("location_source") in {"ip", "default"}:
                should_geocode = True
            elif hint_source in {"semantic", "message"} and prev_hint != hint:
                should_geocode = True

        if (
            should_geocode
            and hint
            and location
            and trusted_current
            and _should_resolve_hint_near_current(user_message, hint)
        ):
            nearby = _resolve_nearby_place(self._map, hint=hint, current=location)
            if nearby:
                location, detail = nearby
                state.scratch["location_hint_resolution"] = detail
                if detail.get("poi"):
                    state.scratch["intended_place_poi"] = detail["poi"]
                state.scratch.pop("location_hint_rejected", None)
                should_geocode = False
                resolved_nearby_hint = True

        if should_geocode:
            try:
                geocode_city = city if trusted_current and not _is_explicit_relocation(user_message, hint) else None
                result = self._map.geocode(hint, city=geocode_city)
                if result:
                    if _should_accept_geocoded_location(
                        state,
                        user_message,
                        hint=hint,
                        current=location,
                        candidate=result,
                    ):
                        location = result
                        state.scratch.pop("location_hint_rejected", None)
                    else:
                        state.scratch["location_hint_rejected"] = {
                            "hint": hint,
                            "candidate": result.model_dump(),
                            "current": location.model_dump() if location else None,
                            "reason": "ambiguous_or_too_far_from_user_location",
                            "distance_km": _distance_km(location, result) if location else None,
                        }
            except Exception:
                pass

        used_ip_location = False
        if not location and hasattr(self._map, "ip_location"):
            try:
                location = self._map.ip_location()
                used_ip_location = bool(location)
            except Exception:
                pass

        if not location:
            location = Location(lat=39.908, lng=116.397, label="北京·天安门")

        state.location = location
        if resolved_nearby_hint and location:
            state.scratch["location_source"] = "nearby_hint"
        elif should_geocode and location:
            if state.scratch.get("location_hint_rejected"):
                state.scratch.setdefault("location_source", "bootstrap" if trusted_current else "default")
            else:
                state.scratch["location_source"] = "geocoded_hint"
        elif used_ip_location and location:
            state.scratch.setdefault("location_source", "ip")
        elif location and location.label == "北京·天安门":
            state.scratch.setdefault("location_source", "default")

        if self._weather and location:
            existing = state.scratch.get("weather")
            if self._weather.should_refresh(existing):
                snap = self._weather.fetch(lat=location.lat, lng=location.lng)
                if snap:
                    state.scratch["weather"] = snap.as_dict()
                    state.scratch["weather_location_label"] = location.label
                    state.scratch["weather_refreshed_at"] = int(time.time())

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


def _has_trusted_user_location(state: SessionState) -> bool:
    if not state.location:
        return False
    source = state.scratch.get("location_source")
    if source == "bootstrap":
        return True
    if state.scratch.get("bootstrap_location"):
        return True
    # A non-default location from earlier geocoding is also safer than a new ambiguous hint.
    return source in {"geocoded_hint", "nearby_hint"}


def _should_geocode_with_trusted_location(
    text: str,
    *,
    hint: str,
    hint_source: str | None,
    previous_hint: str | None,
) -> bool:
    if hint_source == "memory":
        return False
    if previous_hint == hint:
        return False
    if _is_explicit_relocation(text, hint):
        return True
    # Short local hints such as "国贸附近" can be useful, but they must pass the
    # distance guard after geocoding. The current city is passed to geocode first.
    return _is_local_place_hint(hint)


def _should_accept_geocoded_location(
    state: SessionState,
    text: str,
    *,
    hint: str,
    current: Location | None,
    candidate: Location,
) -> bool:
    if not current:
        return True
    if _is_explicit_relocation(text, hint):
        return True
    distance = _distance_km(current, candidate)
    if (
        distance is not None
        and distance > LOCAL_PLACE_MAX_DISTANCE_KM
        and _should_resolve_hint_near_current(text, hint)
        and _has_nearby_intent(text)
    ):
        return False
    if distance <= LOCAL_HINT_MAX_DISTANCE_KM:
        return True
    return False


def _is_explicit_relocation(text: str, hint: str) -> bool:
    source = text or ""
    explicit_current = re.search(r"(?:我现在在|现在在|我目前在|目前在|人在|位于|住在)\s*" + re.escape(hint), source)
    if explicit_current:
        return True
    explicit_go = re.search(r"(?:去|到|前往)\s*" + re.escape(hint), source)
    if explicit_go and _is_administrative_specific(hint):
        return True
    return _is_administrative_specific(hint) and any(k in source for k in ["跨城", "外地", "出差", "旅游", "前往"])


def _is_administrative_specific(hint: str) -> bool:
    return any(k in (hint or "") for k in ["省", "市", "区", "县", "自治州", "州", "镇", "乡", "街道"])


def _is_local_place_hint(hint: str) -> bool:
    text = hint or ""
    if len(text) <= 12:
        return True
    return any(k in text for k in ["商场", "广场", "公园", "地铁站", "火车站", "机场", "路", "街", "社区"])


def _should_resolve_hint_near_current(text: str, hint: str) -> bool:
    if _is_explicit_relocation(text, hint):
        return False
    if _is_administrative_specific(hint):
        return False
    return _is_local_place_hint(hint)


def _resolve_nearby_place(map_tool: MapTool, *, hint: str, current: Location) -> tuple[Location, dict] | None:
    if not hasattr(map_tool, "search_poi"):
        return None
    best: tuple[tuple[int, float], POI] | None = None
    seen: set[str] = set()
    for radius_km in LOCAL_PLACE_SEARCH_RADII_KM:
        try:
            pois = map_tool.search_poi(tag=hint, location=current, radius_km=radius_km)
        except Exception:
            continue
        for poi in pois:
            if poi.id in seen:
                continue
            seen.add(poi.id)
            if not _category_matches_place_hint(poi, hint):
                continue
            score = _place_hint_match_score(poi, hint, current)
            if not score:
                continue
            if score[1] > radius_km:
                continue
            if best is None or score < best[0]:
                best = (score, poi)
        if best:
            break
    if not best:
        return None

    score, poi = best
    loc = poi.location or Location(lat=poi.lat, lng=poi.lng, label=poi.name)
    label = poi.name or loc.label or hint
    resolved = Location(lat=loc.lat, lng=loc.lng, label=label)
    detail = {
        "hint": hint,
        "method": "nearby_poi",
        "poi_id": poi.id,
        "poi_name": poi.name,
        "address": poi.address,
        "business_area": poi.business_area,
        "distance_km": score[1],
        "search_radii_km": list(LOCAL_PLACE_SEARCH_RADII_KM),
        "poi": poi.model_dump(),
    }
    return resolved, detail


def _place_hint_match_score(poi: POI, hint: str, current: Location) -> tuple[int, float] | None:
    hint_key = _compact_place_text(_strip_place_action_words(hint))
    if len(hint_key) < 2:
        return None
    name_key = _compact_place_text(poi.name)
    address_key = _compact_place_text(poi.address or "")
    area_key = _compact_place_text(poi.business_area or "")
    tag_key = _compact_place_text(" ".join(poi.tags or []))
    fields = [name_key, address_key, area_key, tag_key]

    aliases = _place_aliases(hint_key)
    rank: int | None = None
    if name_key == hint_key:
        rank = 0
    elif hint_key in name_key or name_key in hint_key:
        rank = 1
    elif any(alias in name_key for alias in aliases):
        rank = 2
    elif any(alias in field for alias in aliases for field in fields[1:]):
        rank = 3
    if rank is None:
        return None

    poi_location = poi.location or Location(lat=poi.lat, lng=poi.lng, label=poi.name)
    distance = poi.distance_from_user
    if distance is None:
        distance = _distance_km(current, poi_location)
    if distance is None:
        return None
    return rank, float(distance)


def _place_aliases(hint_key: str) -> list[str]:
    aliases = [hint_key]
    for suffix in ["湿地公园", "森林公园", "生态公园", "主题公园", "公园", "景区", "广场", "商场", "购物中心", "中心"]:
        if hint_key.endswith(suffix) and len(hint_key) > len(suffix) + 1:
            aliases.append(hint_key[: -len(suffix)])
    out: list[str] = []
    for item in aliases:
        if len(item) >= 2 and item not in out:
            out.append(item)
    return out


def _category_matches_place_hint(poi: POI, hint: str) -> bool:
    text = f"{poi.name} {poi.category} {' '.join(poi.tags or [])}"
    if any(key in hint for key in ["公园", "湿地", "景区", "绿道", "森林"]):
        return not any(key in text for key in ["餐饮", "餐厅", "饭店", "烧烤", "火锅", "小吃", "咖啡", "茶饮"])
    return True


def _strip_place_action_words(value: str) -> str:
    text = (value or "").strip()
    for suffix in ["散步之前", "散步", "徒步", "跑步", "溜达", "遛弯", "逛逛", "逛", "游玩", "玩"]:
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            text = text[: -len(suffix)].strip()
    return text


def _compact_place_text(value: str) -> str:
    return re.sub(r"[\s·\-_/()（）【】\[\],，.。:：;；]+", "", value or "").lower()


def _has_nearby_intent(text: str) -> bool:
    source = text or ""
    return any(
        key in source
        for key in [
            "就近",
            "附近",
            "周边",
            "旁边",
            "不远",
            "不太远",
            "别太远",
            "太远",
            "步行",
            "散步",
            "饭前",
            "饭后",
        ]
    )


def _extract_venue_constraint(text: str, hint: str) -> dict[str, str | bool] | None:
    venue_name = _clean_venue_name(hint)
    if len(venue_name) < 2:
        return None
    if not _mentions_inside_venue(text, raw_hint=hint, venue_name=venue_name):
        return None
    return {
        "name": venue_name,
        "raw_hint": hint,
        "require_inside": True,
        "evidence_policy": VENUE_EVIDENCE_POLICY,
    }


def _clean_hint_for_geocoding(hint: str) -> str:
    text = (hint or "").strip()
    if not text:
        return text
    return _clean_venue_name(_strip_place_action_words(text))


def _clean_venue_name(value: str) -> str:
    name = (value or "").strip()
    name = re.split(r"[，。,.！!？?\n\r]", name, maxsplit=1)[0].strip()
    for suffix in ["里面的", "内部的", "商场内的", "商场里的", "楼内的", "楼里的", "馆内的", "内的", "里的"]:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            name = name[: -len(suffix)].strip()
    for suffix in ["里面", "内部", "商场内", "商场里", "楼内", "楼里", "馆内", "附近", "周边", "旁边", "一带"]:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            name = name[: -len(suffix)].strip()
    if name.endswith("内") and len(name) >= 3:
        name = name[:-1].strip()
    if name.endswith("里") and _is_venue_like(name[:-1]) and len(name) >= 3:
        name = name[:-1].strip()
    return name.strip(" ,，。;；:")


def _mentions_inside_venue(text: str, *, raw_hint: str, venue_name: str) -> bool:
    source = re.sub(r"\s+", "", text or "")
    raw = re.sub(r"\s+", "", raw_hint or "")
    venue = re.sub(r"\s+", "", venue_name or "")
    if not source or not venue:
        return False
    if _mentions_nearby_only(source, venue):
        return False
    inside_words = ["内", "里面", "里", "内部", "商场内", "商场里", "楼内", "楼里", "馆内"]
    if raw != venue and any(word in raw for word in inside_words):
        return True
    inside_pattern = re.escape(venue) + r"(?:的)?(?:内|里面|里|内部|商场内|商场里|楼内|楼里|馆内)"
    if re.search(inside_pattern, source):
        return True
    if _is_venue_like(venue) and re.search(r"(?:在|到|去)" + re.escape(venue) + r"(?:吃饭|用餐|就餐|玩|逛|活动|安排)", source):
        return True
    return False


def _mentions_nearby_only(text: str, venue_name: str) -> bool:
    pattern = re.escape(venue_name) + r"(?:附近|周边|旁边|一带|周围)"
    return bool(re.search(pattern, text))


def _is_venue_like(name: str) -> bool:
    text = name or ""
    return any(
        key in text
        for key in [
            "商场",
            "广场",
            "购物",
            "中心",
            "mall",
            "Mall",
            "MALL",
            "plaza",
            "Plaza",
            "城",
            "天地",
            "天街",
            "万象",
            "万达",
            "银泰",
            "大悦",
            "吾悦",
            "龙湖",
            "奥莱",
        ]
    )


def _add_venue_hard_constraint(state: SessionState, venue_name: str) -> None:
    schema = state.planning_context
    if not schema:
        return
    msg = f"必须确认商家或活动位于{venue_name}内，缺少地址/商圈/店名证据不得按场馆内推荐"
    if msg not in schema.hard_constraints:
        schema.hard_constraints.append(msg)


def _derive_city_context(label: str | None) -> str | None:
    text = label or ""
    if not text:
        return None
    municipality = re.search(r"(北京|上海|天津|重庆)", text)
    if municipality:
        return municipality.group(1)
    city = re.search(r"([一-龥]{2,12}市)", text)
    if city:
        return city.group(1)
    district = re.search(r"([一-龥]{2,12}(?:区|县))", text)
    if district:
        return district.group(1)
    return None


def _distance_km(a: Location | None, b: Location | None) -> float | None:
    if not a or not b:
        return None
    r = 6371.0
    d_lat = math.radians(b.lat - a.lat)
    d_lng = math.radians(b.lng - a.lng)
    v = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(a.lat)) * math.cos(math.radians(b.lat)) * math.sin(d_lng / 2) ** 2
    )
    return round(2 * r * math.atan2(math.sqrt(v), math.sqrt(1 - v)), 1)
