from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from meituan_agent.domain.models import ItineraryPlan, POI, SessionState


@dataclass
class ConstraintReport:
    ok: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    satisfied: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": self.violations,
            "warnings": self.warnings,
            "satisfied": self.satisfied,
        }


def filter_candidates(state: SessionState) -> SessionState:
    """Apply deterministic hard filters before the planner combines POIs."""
    state.scratch["food_candidates"] = [p.model_dump() for p in filter_pois(state, _pois(state, "food_candidates"))]
    state.scratch["leisure_candidates"] = [p.model_dump() for p in filter_pois(state, _pois(state, "leisure_candidates"))]
    return state


def filter_pois(state: SessionState, pois: list[POI]) -> list[POI]:
    schema = state.planning_context
    if not schema and not _active_venue_constraint(state):
        return pois

    max_radius = _max_radius(state)
    filtered: list[POI] = []
    rejected: list[dict[str, Any]] = list(state.scratch.get("constraint_rejections") or [])
    for poi in pois:
        reasons = _poi_rejection_reasons(state, poi, max_radius=max_radius)
        if reasons:
            rejected.append({"poi_id": poi.id, "poi_name": poi.name, "reasons": reasons})
            continue
        filtered.append(poi)
    state.scratch["constraint_rejections"] = rejected[-30:]
    return filtered


def enrich_restaurant_availability(state: SessionState, availability_tool, *, max_queue_minutes: int) -> SessionState:
    """Query restaurant availability before planning, then remove clearly unusable options."""
    raw = state.scratch.get("food_candidates") or []
    foods = [POI.model_validate(x) for x in raw]
    availability: dict[str, dict[str, Any]] = dict(state.scratch.get("availability_by_poi") or {})
    usable: list[POI] = []
    rejected: list[dict[str, Any]] = list(state.scratch.get("availability_rejections") or [])

    for poi in foods:
        if poi.category != "餐饮":
            usable.append(poi)
            continue
        try:
            av = availability_tool.check_table_availability(poi.id, size=state.profile.party_size)
        except Exception as exc:
            av = {"ok": False, "error": str(exc), "poi_id": poi.id}
        queue = av.get("queue_minutes")
        queue_too_long = isinstance(queue, int) and queue > max_queue_minutes
        capacity_ok = av.get("capacity_ok")
        if capacity_ok is None:
            capacity_ok = True
        av = {
            "poi_id": poi.id,
            "ok": bool(av.get("ok")) and not queue_too_long and bool(capacity_ok),
            "queue_minutes": queue,
            "max_queue_minutes": max_queue_minutes,
            "queue_too_long": queue_too_long,
            "capacity_ok": bool(capacity_ok),
            "reservable_slots": av.get("reservable_slots") or [],
            "business_open": av.get("business_open", True),
            "reason": av.get("error") or av.get("reason"),
            **{
                k: v
                for k, v in av.items()
                if k
                not in {
                    "ok",
                    "queue_minutes",
                    "max_queue_minutes",
                    "queue_too_long",
                    "capacity_ok",
                    "reservable_slots",
                    "business_open",
                    "reason",
                }
            },
        }
        availability[poi.id] = av
        if av["ok"]:
            usable.append(poi)
        else:
            rejected.append({"poi_id": poi.id, "poi_name": poi.name, "availability": av})

    state.scratch["availability_by_poi"] = availability
    state.scratch["availability_rejections"] = rejected[-30:]
    state.scratch["food_candidates"] = [p.model_dump() for p in usable]
    return state


def annotate_plan(state: SessionState, plan: ItineraryPlan) -> ItineraryPlan:
    """Attach availability snapshots to items and add a validation report."""
    availability = state.scratch.get("availability_by_poi") or {}
    items = []
    for item in plan.items:
        av = availability.get(item.poi.id)
        if av:
            items.append(item.model_copy(update={"availability": av}))
        else:
            items.append(item)

    report = validate_plan(state, plan.model_copy(update={"items": items}))
    return plan.model_copy(update={"items": items, "validation": report.as_dict()})


def validate_plan(state: SessionState, plan: ItineraryPlan) -> ConstraintReport:
    report = ConstraintReport()
    schema = state.planning_context
    max_radius = _max_radius(state)

    if not any(item.poi.category == "餐饮" for item in plan.items):
        report.ok = False
        report.violations.append("方案缺少餐饮安排")
    else:
        report.satisfied.append("已包含餐饮安排")

    if schema and schema.party.has_child:
        child_ok = any(_is_child_friendly(item.poi) for item in plan.items)
        if child_ok:
            report.satisfied.append("已包含亲子友好活动")
        else:
            report.warnings.append("未明显包含亲子友好活动")

    if schema and schema.food.dietary:
        diet_ok = any(_diet_friendly(item.poi, schema.food.dietary or []) for item in plan.items if item.poi.category == "餐饮")
        if diet_ok:
            report.satisfied.append("餐饮已考虑减脂/低卡偏好")
        else:
            report.warnings.append("餐饮未明显命中减脂/低卡偏好")

    for item in plan.items:
        for reason in _poi_rejection_reasons(state, item.poi, max_radius=max_radius):
            report.ok = False
            report.violations.append(f"{item.poi.name}: {reason}")
        av = item.availability or {}
        if item.poi.category == "餐饮" and av:
            if av.get("ok"):
                queue = av.get("queue_minutes")
                if isinstance(queue, int):
                    report.satisfied.append(f"{item.poi.name} 预计排队{queue}分钟")
                else:
                    report.satisfied.append(f"{item.poi.name} 可接待{state.profile.party_size}人")
            else:
                report.ok = False
                report.violations.append(f"{item.poi.name}: 餐厅当前不可用或排队过久")

    if plan.total_minutes is not None:
        target = int(state.profile.duration_hours or 5) * 60
        if target - 60 <= plan.total_minutes <= target + 60:
            report.satisfied.append(f"总时长约{round(plan.total_minutes / 60, 1)}小时，符合时间预算")
        else:
            report.warnings.append(f"总时长约{round(plan.total_minutes / 60, 1)}小时，可能偏离目标")

    venue = _active_venue_constraint(state)
    if venue and not any("缺少位于" in v for v in report.violations):
        report.satisfied.append(f"已校验点位归属：{venue['name']}内")

    if not report.violations:
        report.ok = True
    return report


def _pois(state: SessionState, key: str) -> list[POI]:
    return [POI.model_validate(x) for x in (state.scratch.get(key) or [])]


def _max_radius(state: SessionState) -> float | None:
    schema = state.planning_context
    if not schema:
        return None
    if schema.location.radius_km is not None:
        return float(schema.location.radius_km)
    if schema.location.must_not_exceed:
        return float(state.scratch.get("search_radius_km") or 3.0)
    return None


def _poi_rejection_reasons(state: SessionState, poi: POI, *, max_radius: float | None) -> list[str]:
    schema = state.planning_context
    reasons: list[str] = []
    venue = _active_venue_constraint(state)
    if venue and not _poi_has_venue_evidence(poi, str(venue["name"])):
        reasons.append(f"缺少位于{venue['name']}内的明确证据")
    if max_radius is not None and poi.distance_from_user is not None and poi.distance_from_user > max_radius:
        reasons.append(f"距离{poi.distance_from_user}km超过{max_radius}km范围")
    if schema and schema.food.avoid and poi.category == "餐饮":
        haystack = f"{poi.name} {' '.join(poi.tags or [])}"
        for avoid in schema.food.avoid:
            if avoid and avoid in haystack:
                reasons.append(f"命中忌口/避讳：{avoid}")
    if schema and schema.food.budget_per_person and poi.category == "餐饮" and poi.price:
        if poi.price > schema.food.budget_per_person * 1.2:
            reasons.append(f"人均{poi.price:g}元超过预算")
    if schema and schema.leisure.indoor_outdoor == "indoor" and poi.category != "餐饮":
        text = f"{poi.name} {' '.join(poi.tags or [])}"
        if any(key in text for key in ["公园", "户外", "citywalk", "徒步", "广场"]):
            reasons.append("天气/用户要求下不适合户外")
    return reasons


def _active_venue_constraint(state: SessionState) -> dict[str, Any] | None:
    raw = state.scratch.get("venue_constraint")
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    if not name or not raw.get("require_inside"):
        return None
    return {**raw, "name": name}


def _poi_has_venue_evidence(poi: POI, venue_name: str) -> bool:
    venue_keys = _venue_keys(venue_name)
    if not venue_keys:
        return True

    fields = [
        poi.name,
        poi.address,
        poi.business_area,
        poi.category,
        poi.location.label if poi.location else None,
        " ".join(poi.tags or []),
    ]
    compact_fields = [_compact_text(str(field)) for field in fields if field]
    if not compact_fields:
        return False
    for key in venue_keys:
        if any(key and key in field for field in compact_fields):
            return True
    return False


def _venue_keys(venue_name: str) -> list[str]:
    compact = _compact_text(venue_name)
    if not compact:
        return []
    keys = [compact]
    for suffix in ["购物中心", "购物广场", "商业中心", "商场", "广场", "中心", "mall", "plaza"]:
        if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
            keys.append(compact[: -len(suffix)])
    out: list[str] = []
    for key in keys:
        if key and key not in out:
            out.append(key)
    return out


def _compact_text(value: str) -> str:
    return re.sub(r"[\s·\-_/()（）【】\[\],，.。:：;；]+", "", value or "").lower()


def _is_child_friendly(poi: POI) -> bool:
    text = f"{poi.name} {poi.category} {' '.join(poi.tags or [])}"
    return any(key in text for key in ["亲子", "儿童", "绘本", "乐园", "游乐", "家庭"])


def _diet_friendly(poi: POI, dietary: list[str]) -> bool:
    text = f"{poi.name} {' '.join(poi.tags or [])} {poi.category}"
    diet_text = " ".join(dietary)
    if any(key in text for key in ["轻食", "沙拉", "低卡", "减脂", "健康"]):
        return True
    if any(key in diet_text for key in ["减脂", "低卡", "轻食"]):
        return any(key in text for key in ["粤菜", "日料", "咖啡", "茶", "健康"])
    return True
