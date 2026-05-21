from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlanItemRef(BaseModel):
    poi_id: str
    category: str
    notes: str | None = None
    travel_mode_from_prev: Literal["walk", "drive", "metro"] | None = None


class PlanCandidate(BaseModel):
    title: str
    rationale: str
    items: list[PlanItemRef] = Field(min_length=2, max_length=6)


class PlanningOutput(BaseModel):
    plans: list[PlanCandidate] = Field(min_length=1, max_length=3)

