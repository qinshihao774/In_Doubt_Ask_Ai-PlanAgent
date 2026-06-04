from __future__ import annotations

import re
from datetime import datetime, timedelta

from meituan_agent.domain.models import ItineraryItem, ItineraryPlan, PlanAction, SessionState


DEFAULT_START = "14:00"


def schedule_plans(state: SessionState, plans: list[ItineraryPlan]) -> list[ItineraryPlan]:
    """Attach start/end times, total duration, and executable actions to plans."""
    return [schedule_plan(state, plan) for plan in plans]


def schedule_plan(state: SessionState, plan: ItineraryPlan) -> ItineraryPlan:
    start_text = state.profile.start_time or DEFAULT_START
    start_dt = _parse_start_time(start_text)
    current = start_dt
    scheduled: list[ItineraryItem] = []

    for item in plan.items:
        leg = item.travel_from_prev
        if leg:
            current += timedelta(minutes=max(0, int(leg.minutes)))
        item_start = current
        duration = _duration_minutes(item, state)
        item_end = item_start + timedelta(minutes=duration)
        scheduled.append(
            item.model_copy(
                update={
                    "start": _fmt(item_start),
                    "end": _fmt(item_end),
                    "notes": _merge_note(item.notes, _availability_note(item)),
                }
            )
        )
        current = item_end

    total_minutes = max(0, int((current - start_dt).total_seconds() // 60))
    target_minutes = max(60, int(state.profile.duration_hours or 5) * 60)
    min_minutes = max(180, target_minutes - 60)
    max_minutes = target_minutes + 60

    if scheduled and total_minutes < min_minutes:
        missing = min_minutes - total_minutes
        last_idx = _last_extendable_item_index(scheduled)
        last = scheduled[last_idx]
        last_end = _parse_hhmm(last.end or _fmt(current)) + timedelta(minutes=missing)
        updated_note = _merge_note(last.notes, f"含{missing}分钟休息/机动时间")
        scheduled[last_idx] = last.model_copy(update={"end": _fmt(last_end), "notes": updated_note})
        total_minutes += missing

    actions = _build_actions(scheduled, state)
    validation = dict(plan.validation or {})
    validation.setdefault("time_window", {"target_minutes": target_minutes, "min_minutes": min_minutes, "max_minutes": max_minutes})

    return plan.model_copy(
        update={
            "items": scheduled,
            "total_minutes": total_minutes,
            "actions": actions,
            "validation": validation,
        }
    )


def _duration_minutes(item: ItineraryItem, state: SessionState) -> int:
    if item.poi.duration_minutes:
        return max(20, int(item.poi.duration_minutes))
    category = item.poi.category or ""
    tags = " ".join(item.poi.tags or [])
    text = f"{category} {tags} {item.poi.name}"
    if "餐饮" in category:
        return 90 if state.profile.party_size >= 3 else 75
    if any(key in text for key in ["咖啡", "奶茶", "饮品", "甜品"]):
        return 45
    if any(key in text for key in ["亲子", "游乐", "儿童"]):
        return 110
    if any(key in text for key in ["展览", "博物馆", "美术馆", "科技馆"]):
        return 100
    if any(key in text for key in ["商场", "购物", "citywalk", "公园"]):
        return 90
    return 80


def _build_actions(items: list[ItineraryItem], state: SessionState) -> list[PlanAction]:
    actions: list[PlanAction] = []
    for item in items:
        poi_id = item.poi.id
        payload = {
            "poi_name": item.poi.name,
            "party_size": state.profile.party_size,
            "start": item.start,
            "end": item.end,
        }
        if item.poi.category == "餐饮":
            actions.append(PlanAction(type="check_availability", poi_id=poi_id, scheduled_time=item.start, payload=payload))
            actions.append(PlanAction(type="reserve_restaurant", poi_id=poi_id, scheduled_time=item.start, payload=payload))
            actions.append(PlanAction(type="place_food_order", poi_id=poi_id, scheduled_time=item.start, payload=payload))
        else:
            action_type = "book_activity" if _should_book_activity(item) else "arrange_visit"
            actions.append(PlanAction(type=action_type, poi_id=poi_id, scheduled_time=item.start, payload=payload, required=False))
    return actions


def _should_book_activity(item: ItineraryItem) -> bool:
    text = f"{item.poi.category} {' '.join(item.poi.tags or [])} {item.poi.name}"
    return any(key in text for key in ["展览", "博物馆", "游乐", "亲子", "剧本", "密室", "电影", "预约"])


def _availability_note(item: ItineraryItem) -> str | None:
    av = item.availability or {}
    if not av:
        return None
    if item.poi.category != "餐饮":
        return None
    queue = av.get("queue_minutes")
    if isinstance(queue, int):
        return f"预计排队{queue}分钟"
    return None


def _last_extendable_item_index(items: list[ItineraryItem]) -> int:
    for idx in range(len(items) - 1, -1, -1):
        if items[idx].poi.category != "餐饮":
            return idx
    return len(items) - 1


def _parse_start_time(text: str) -> datetime:
    now = datetime.now().replace(second=0, microsecond=0)
    hhmm = _extract_hhmm(text or "") or DEFAULT_START
    hour, minute = [int(x) for x in hhmm.split(":", 1)]
    return now.replace(hour=hour, minute=minute)


def _extract_hhmm(text: str) -> str | None:
    s = (text or "").strip()
    m = re.search(r"(\d{1,2})[:：](\d{1,2})", s)
    if m:
        return _normalize_hhmm(int(m.group(1)), int(m.group(2)), s)
    m = re.search(r"(\d{1,2})\s*点(?:半|(\d{1,2})分?)?", s)
    if m:
        minute = 30 if "半" in m.group(0) else int(m.group(2) or 0)
        return _normalize_hhmm(int(m.group(1)), minute, s)
    m = re.search(r"^\d{1,2}$", s)
    if m:
        return _normalize_hhmm(int(s), 0, s)
    return None


def _normalize_hhmm(hour: int, minute: int, source: str) -> str:
    if ("下午" in source or "晚上" in source) and hour < 12:
        hour += 12
    if "中午" in source and hour < 11:
        hour += 12
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return f"{hour:02d}:{minute:02d}"


def _parse_hhmm(text: str) -> datetime:
    now = datetime.now().replace(second=0, microsecond=0)
    hour, minute = [int(x) for x in (text or DEFAULT_START).split(":", 1)]
    return now.replace(hour=hour, minute=minute)


def _fmt(value: datetime) -> str:
    return value.strftime("%H:%M")


def _merge_note(existing: str | None, addition: str | None) -> str | None:
    parts = [p.strip() for p in [existing, addition] if p and p.strip()]
    if not parts:
        return None
    out: list[str] = []
    for part in parts:
        if part not in out:
            out.append(part)
    return "；".join(out)
