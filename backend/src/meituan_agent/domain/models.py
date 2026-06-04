from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    planning = "planning"
    awaiting_confirmation = "awaiting_confirmation"
    executing = "executing"
    completed = "completed"


class UserProfile(BaseModel):
    party_size: int = 2
    has_child: bool = False
    fat_loss: bool = False
    budget_level: int | None = None
    start_time: str | None = None
    duration_hours: int = 5
    style: Literal["family", "friends", "romantic", "mixed"] = "mixed"


class Location(BaseModel):
    lat: float
    lng: float
    label: str | None = None


class POI(BaseModel):
    id: str
    name: str
    category: str
    location: Location | None = None  # 完整坐标对象
    lat: float = 0.0  # 冗余纬度，方便直接访问
    lng: float = 0.0  # 冗余经度
    tags: list[str] = Field(default_factory=list)
    rating: float = 0.0
    price: float | None = None  # 人均消费
    price_level: int | None = None
    address: str | None = None
    open_hours: str | None = None
    duration_minutes: int | None = None
    menu: list[dict[str, Any]] | None = None
    image_url: str | None = None
    tel: str | None = None
    business_area: str | None = None
    distance_from_user: float | None = None


class RouteLeg(BaseModel):
    mode: Literal["walk", "drive", "metro"] = "walk"
    minutes: int
    distance_km: float


class ItineraryItem(BaseModel):
    poi: POI
    start: str | None = None
    end: str | None = None
    travel_from_prev: RouteLeg | None = None
    notes: str | None = None
    availability: dict[str, Any] | None = None


class PlanAction(BaseModel):
    """A concrete operation that can be executed after the user confirms a plan."""

    type: Literal[
        "check_availability",
        "reserve_restaurant",
        "place_food_order",
        "book_activity",
        "arrange_visit",
        "notify_user",
    ]
    poi_id: str
    scheduled_time: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    required: bool = True


class ItineraryPlan(BaseModel):
    id: str
    title: str
    items: list[ItineraryItem]
    rationale: str
    total_minutes: int | None = None
    actions: list[PlanAction] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)


class LocationConstraint(BaseModel):
    """位置约束 — 所有字段可空，LLM 动态推理填充"""
    type: Literal["current_gps", "named_area", "none"] = "current_gps"
    area: str | None = None
    radius_km: float | None = None
    must_not_exceed: bool | None = None


class FoodConstraint(BaseModel):
    """餐饮约束 — 所有字段可空，LLM 动态推理填充"""
    required: bool | None = None
    cuisine_types: list[str] | None = None
    avoid: list[str] | None = None
    taste_profile: str | None = None
    dietary: list[str] | None = None
    budget_per_person: int | None = None
    occasion: str | None = None


class LeisureConstraint(BaseModel):
    """休闲约束 — 所有字段可空，LLM 动态推理填充"""
    required: bool | None = None
    activity_types: list[str] | None = None
    vibe: str | None = None
    indoor_outdoor: Literal["indoor", "outdoor", "any"] | None = None
    duration_per_activity_minutes: int | None = None


class PartyConstraint(BaseModel):
    """同行人员约束 — 所有字段可空，LLM 动态推理填充"""
    size: int | None = None
    has_child: bool | None = None
    child_age: int | None = None
    composition: str | None = None


class TimingConstraint(BaseModel):
    """时间约束 — 所有字段可空，LLM 动态推理填充"""
    start: str | None = None
    duration_hours: int | None = None
    date: str | None = None


class SemanticSchema(BaseModel):
    """LLM 深度语义分析输出的完整结构化需求"""
    intent: Literal["planning", "chat", "confirmation"] = "planning"
    location: LocationConstraint = Field(default_factory=LocationConstraint)
    food: FoodConstraint = Field(default_factory=FoodConstraint)
    leisure: LeisureConstraint = Field(default_factory=LeisureConstraint)
    party: PartyConstraint = Field(default_factory=PartyConstraint)
    timing: TimingConstraint = Field(default_factory=TimingConstraint)
    hard_constraints: list[str] = Field(default_factory=list)   # 必须遵守的硬约束
    free_text_summary: str = ""       # 一句话总结用户需求


# 保留兼容别名
PlanningContext = SemanticSchema


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    ts: datetime = Field(default_factory=datetime.utcnow)


class ExecutionResult(BaseModel):
    ok: bool
    step: str
    details: dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    session_id: str
    status: SessionStatus = SessionStatus.planning
    profile: UserProfile = Field(default_factory=UserProfile)
    location: Location | None = None
    planning_context: PlanningContext | None = None
    candidate_plans: list[ItineraryPlan] = Field(default_factory=list)
    selected_plan_id: str | None = None
    executions: list[ExecutionResult] = Field(default_factory=list)
    last_error: str | None = None
    scratch: dict[str, Any] = Field(default_factory=dict)

