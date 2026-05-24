"""
ManagerAgent — 决策管理

新流水线:
  SemanticAgent 深度分析 → MapAgent → FoodAgent → LeisureAgent → Planner → 执行
  一次 LLM 调用完成意图分类 + 约束提取，下游 agent 消费同一份 schema。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Generator

from meituan_agent.agents.execution_agent import ExecutionAgent
from meituan_agent.agents.food_agent import FoodAgent
from meituan_agent.agents.leisure_agent import LeisureAgent
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.agents.semantic_agent import SemanticAgent
from meituan_agent.domain.models import SemanticSchema, SessionState, SessionStatus
from meituan_agent.llm.openai_compat import OpenAICompatClient
from meituan_agent.planning.planner import Planner, PlanningInput

logger = logging.getLogger(__name__)

PIPELINE_STAGES: list[dict[str, Any]] = [
    {"id": "semantic", "label": "语义分析", "active_msg": "正在理解需求...", "done_msg": "需求理解完成", "icon": "🧠"},
    {"id": "map", "label": "地图搜索", "active_msg": "正在定位与搜索地图...", "done_msg": "位置与周边搜索完成",
     "icon": "🗺️"},
    {"id": "food", "label": "美食搜索", "active_msg": "正在为您寻找美食...", "done_msg": "美食搜索完成", "icon": "🍜"},
    {"id": "leisure", "label": "休闲探索", "active_msg": "正在搜索休闲好去处...", "done_msg": "休闲探索完成",
     "icon": "🎯"},
    {"id": "plan", "label": "方案规划", "active_msg": "正在生成行程方案...", "done_msg": "方案生成完毕", "icon": "📋"},
    {"id": "execution", "label": "执行落地", "active_msg": "正在执行方案...", "done_msg": "执行完成", "icon": "🚀"},
]


class ManagerAgent:
    def __init__(
            self,
            semantic: SemanticAgent,
            food: FoodAgent,
            leisure: LeisureAgent,
            map_agent: MapAgent,
            execution: ExecutionAgent,
            planner: Planner,
            llm: OpenAICompatClient | None = None,
    ) -> None:
        self._semantic = semantic
        self._food = food
        self._leisure = leisure
        self._map = map_agent
        self._exec = execution
        self._llm = llm
        self._planner = planner

    def step(self, state: SessionState, user_message: str, *, use_llm: bool = True) -> tuple[SessionState, str]:
        # ═══════════════════════════════════════════════════════════
        # 阶段 0: 深度语义分析 — 一次 LLM 调用完成全部理解
        # ═══════════════════════════════════════════════════════════
        if self._semantic is not None:
            loc_label = state.location.label if state.location else "未知"
            schema = self._semantic.analyze(user_message, location_label=loc_label)
        else:
            schema = SemanticSchema()
            # 补充：无 LLM 时用关键词判断确认意图
            if _is_confirmation(user_message) and state.candidate_plans:
                # SemanticSchema() 的 intent 的默认值为 "planning"，手动改为 confirmation
                schema.intent = "confirmation"
        state.planning_context = schema
        # 同步到旧 profile（兼容 planner 中仍使用 profile 的代码）
        if schema.party.size is not None:
            state.profile.party_size = schema.party.size
        if schema.party.has_child is not None:
            state.profile.has_child = schema.party.has_child
        state.profile.fat_loss = bool(schema.food.dietary)
        if schema.timing.duration_hours is not None:
            state.profile.duration_hours = schema.timing.duration_hours
        state.profile.style = _map_style(schema)
        if schema.food.budget_per_person:
            state.profile.budget_level = _budget_to_level(schema.food.budget_per_person)

        # ═══════════════════════════════════════════════════════════
        # 意图路由
        # ═══════════════════════════════════════════════════════════
        if schema.intent == "chat":
            state.status = SessionStatus.planning
            if self._llm:
                return state, self._chat_reply(user_message)
            return state, "你好呀！有什么可以帮你的吗？"

        if schema.intent == "confirmation" and state.candidate_plans:
            plan_id = _extract_plan_choice(user_message, state)
            if plan_id:
                state.selected_plan_id = plan_id
            if not state.selected_plan_id:
                state.selected_plan_id = state.candidate_plans[0].id
            state.status = SessionStatus.executing
            state = self._exec.execute_plan(state)
            if state.last_error:
                state = self._replan_after_failure(state)
                return state, _format_replan_message(state, self._llm if use_llm else None)
            state.status = SessionStatus.completed

            # 构建完整行程 + 发送邮件
            try:
                from meituan_agent.email_sender import build_itinerary_html, send_itinerary_email
                plan = next(p for p in state.candidate_plans if p.id == state.selected_plan_id)
                items = self._exec.build_itinerary(state)
                html = build_itinerary_html(plan.title, plan.rationale, items)
                to_email = os.getenv("MEITUAN_AGENT_EMAIL_SENDER")
                if to_email:
                    send_itinerary_email(
                        to_email=to_email,
                        subject=f"🍜 行程已就绪 — {plan.title}",
                        html_body=html,
                    )
            except Exception:
                pass

            return state, _format_execution_summary(state)

        # ═══════════════════════════════════════════════════════════
        # 规划流水线: Map → Food → Leisure → Plan
        # ═══════════════════════════════════════════════════════════
        state = self._map.run(state, user_message)
        state = self._food.run(state, user_message)
        state = self._leisure.run(state, user_message)
        state = self._plan(state, excluded_poi_ids=set(), last_error=None)

        # 去重：不同方案的 POI 集合不能相同（即使顺序不同）
        state = self._dedup_plans(state)

        if not state.candidate_plans:
            state.status = SessionStatus.awaiting_confirmation
            return state, _format_plan_message(state, self._llm if use_llm else None)

        state.status = SessionStatus.awaiting_confirmation
        return state, _format_plan_message(state, self._llm if use_llm else None)

    def step_stream(self, state: SessionState, user_message: str, *, use_llm: bool = True) -> Generator[
        dict[str, Any], None, tuple[SessionState, str]]:
        """流式执行 step，在流水线各阶段之间 yield pipeline_stage 事件。

        与 step() 逻辑完全一致，但每个 agent 阶段前后 yield 进度事件，
        供前端渲染点线流程可视化。
        """

        def _emit(stage_id: str, status: str, msg: str | None = None) -> dict[str, Any]:
            return {"type": "pipeline_stage", "stage_id": stage_id, "status": status, "msg": msg}

        # ═══════════════════════════════════════════════════════════
        # 阶段 0: 深度语义分析
        # ═══════════════════════════════════════════════════════════
        yield _emit("semantic", "running", "正在理解需求...")
        if self._semantic is not None:
            loc_label = state.location.label if state.location else "未知"
            schema = self._semantic.analyze(user_message, location_label=loc_label)
        else:
            schema = SemanticSchema()
            # 改动同 step() 下的一样
            if _is_confirmation(user_message) and state.candidate_plans:
                schema.intent = "confirmation"
        state.planning_context = schema
        if schema.party.size is not None:
            state.profile.party_size = schema.party.size
        if schema.party.has_child is not None:
            state.profile.has_child = schema.party.has_child
        state.profile.fat_loss = bool(schema.food.dietary)
        if schema.timing.duration_hours is not None:
            state.profile.duration_hours = schema.timing.duration_hours
        state.profile.style = _map_style(schema)
        if schema.food.budget_per_person:
            state.profile.budget_level = _budget_to_level(schema.food.budget_per_person)
        yield _emit("semantic", "done", "需求理解完成")

        # ═══════════════════════════════════════════════════════════
        # 意图路由
        # ═══════════════════════════════════════════════════════════
        if schema.intent == "chat":
            state.status = SessionStatus.planning
            if self._llm:
                return state, self._chat_reply(user_message)
            return state, "你好呀！有什么可以帮你的吗？"

        if schema.intent == "confirmation" and state.candidate_plans:
            plan_id = _extract_plan_choice(user_message, state)
            if plan_id:
                state.selected_plan_id = plan_id
            if not state.selected_plan_id:
                state.selected_plan_id = state.candidate_plans[0].id
            state.status = SessionStatus.executing

            yield _emit("execution", "running", "正在执行方案...")
            state = self._exec.execute_plan(state)
            yield _emit("execution", "done", "执行完成" if not state.last_error else "执行遇到问题")

            if state.last_error:
                yield _emit("plan", "running", "正在重新规划...")
                state = self._replan_after_failure(state)
                yield _emit("plan", "done", "重规划完成")
                return state, _format_replan_message(state, self._llm if use_llm else None)
            state.status = SessionStatus.completed

            try:
                from meituan_agent.email_sender import build_itinerary_html, send_itinerary_email
                plan = next(p for p in state.candidate_plans if p.id == state.selected_plan_id)
                items = self._exec.build_itinerary(state)
                html = build_itinerary_html(plan.title, plan.rationale, items)
                to_email = os.getenv("MEITUAN_AGENT_EMAIL_SENDER")
                if to_email:
                    send_itinerary_email(
                        to_email=to_email,
                        subject=f"🍜 行程已就绪 — {plan.title}",
                        html_body=html,
                    )
            except Exception:
                pass

            return state, _format_execution_summary(state)

        # ═══════════════════════════════════════════════════════════
        # 规划流水线: Map → Food → Leisure → Plan
        # ═══════════════════════════════════════════════════════════
        yield _emit("map", "running", "正在定位与搜索地图...")
        state = self._map.run(state, user_message)
        yield _emit("map", "done", "位置与周边搜索完成")

        yield _emit("food", "running", "正在为您寻找美食...")
        state = self._food.run(state, user_message)
        yield _emit("food", "done", "美食搜索完成")

        yield _emit("leisure", "running", "正在搜索休闲好去处...")
        state = self._leisure.run(state, user_message)
        yield _emit("leisure", "done", "休闲探索完成")

        yield _emit("plan", "running", "正在生成行程方案...")
        state = self._plan(state, excluded_poi_ids=set(), last_error=None)
        yield _emit("plan", "done", "方案生成完毕")

        state = self._dedup_plans(state)

        if not state.candidate_plans:
            state.status = SessionStatus.awaiting_confirmation
            return state, _format_plan_message(state, self._llm if use_llm else None)

        state.status = SessionStatus.awaiting_confirmation
        return state, _format_plan_message(state, self._llm if use_llm else None)

    def _dedup_plans(self, state: SessionState) -> SessionState:
        """确保方案间内容去重 —— 每个方案必须有不同的 POI 组合。

        两个方案即使只是顺序不同，也视为重复。迭代重规划直到：
          - 获得 3 个不同的方案，或
          - 达到最大重试次数（3 次）
        """
        plans = state.candidate_plans
        if len(plans) <= 1:
            return state

        def _poi_fingerprint(plan) -> frozenset:
            """提取 POI ID 指纹"""
            return frozenset(it.poi.id for it in plan.items)

        # 第一轮：过滤重复
        uniq: list = []
        seen: set[frozenset] = set()
        for plan in plans:
            fp = _poi_fingerprint(plan)
            if fp in seen:
                continue
            seen.add(fp)
            uniq.append(plan)

        # 迭代重规划，直到凑满 3 个或重试耗尽
        max_retries = 3
        retry = 0
        while len(uniq) < 3 and retry < max_retries:
            retry += 1
            # 收集全部已用 POI → 排除
            all_used = {pid for fp in seen for pid in fp}
            try:
                state = self._plan(state, excluded_poi_ids=all_used, last_error=f"dedup_retry_{retry}")
                for plan in state.candidate_plans:
                    fp = _poi_fingerprint(plan)
                    if fp not in seen:
                        seen.add(fp)
                        uniq.append(plan)
                        all_used.update(fp)
                        if len(uniq) >= 3:
                            break
            except Exception:
                break

        state.candidate_plans = uniq[:3]
        return state

    def _chat_reply(self, user_message: str) -> str:
        system = (
            "你是一个友好、温暖的 AI 助手。你具备行程规划能力，"
            "但当前用户只是在和你闲聊。请用自然的语气回复，像朋友聊天一样。"
            "保持轻松、真诚、简短。"
        )
        try:
            return self._llm.chat(system=system, user=user_message)
        except Exception:
            return "你好呀！今天有什么可以帮你的吗？"

    def _plan(self, state: SessionState, *, excluded_poi_ids: set[str], last_error: str | None) -> SessionState:
        plans = self._planner.plan(PlanningInput(state=state, excluded_poi_ids=excluded_poi_ids, last_error=last_error))
        if not plans:
            state.last_error = "insufficient_candidates"
            state.candidate_plans = []
            return state
        state.candidate_plans = plans[:3]
        if state.selected_plan_id not in {p.id for p in state.candidate_plans}:
            state.selected_plan_id = None
        state.last_error = None
        return state

    def _replan_after_failure(self, state: SessionState) -> SessionState:
        last = state.last_error or ""
        state.status = SessionStatus.planning
        bad_restaurant_id = None
        for ex in reversed(state.executions):
            if ex.step in {"check_availability", "place_order"}:
                bad_restaurant_id = ex.details.get("poi_id") or ex.details.get("restaurant_id")
        if not bad_restaurant_id and state.selected_plan_id:
            plan = next((p for p in state.candidate_plans if p.id == state.selected_plan_id), None)
            if plan:
                for it in plan.items:
                    if it.poi.category == "餐饮":
                        bad_restaurant_id = it.poi.id
                        break
        candidates_raw = state.scratch.get("food_candidates") or []
        candidates = [c for c in candidates_raw if c.get("id") != bad_restaurant_id]
        state.scratch["food_candidates"] = candidates
        excluded = {bad_restaurant_id} if bad_restaurant_id else set()
        state = self._plan(state, excluded_poi_ids=excluded, last_error=last)
        state.status = SessionStatus.awaiting_confirmation
        return state


def _map_style(schema: SemanticSchema) -> str:
    if schema.party.has_child:
        return "family"
    if schema.party.composition and "朋友" in (schema.party.composition or ""):
        return "friends"
    if schema.food.occasion == "约会":
        return "romantic"
    return "mixed"


def _budget_to_level(amount: int) -> int:
    if amount <= 80:
        return 1
    if amount <= 150:
        return 2
    return 3


def _is_confirmation(text: str) -> bool:
    t = (text or "").strip()
    return any(k in t for k in ["确认", "就这个", "选", "执行", "搞定", "开始"])


def _extract_plan_choice(text: str, state: SessionState) -> str | None:
    t = (text or "").strip()
    if "方案" in t:
        for idx, p in enumerate(state.candidate_plans, start=1):
            if f"方案{idx}" in t:
                return p.id
    if t.isdigit():
        idx = int(t)
        if 1 <= idx <= len(state.candidate_plans):
            return state.candidate_plans[idx - 1].id
    for p in state.candidate_plans:
        if p.id in t:
            return p.id
    return None


def _format_plan_message(state: SessionState, llm: OpenAICompatClient | None = None) -> str:
    if not state.candidate_plans:
        return "当前无法生成可用方案，请补充人数/偏好/地点。"
    lines = []
    if state.location:
        lines.append(f"已根据你的当前位置检索：{state.location.label or f'{state.location.lat},{state.location.lng}'}")
    lines.append("我为你生成了以下方案，请回复：确认 方案1 / 确认 方案2 开始执行。")
    for idx, plan in enumerate(state.candidate_plans, start=1):
        lines.append("")
        lines.append(f"方案{idx}：{plan.title}")
        lines.append(f"理由：{plan.rationale}")
        for it in plan.items:
            leg = it.travel_from_prev
            prefix = ""
            if leg:
                prefix = f"（{leg.mode} {leg.minutes}min/{leg.distance_km}km）"
            parts = [f"- {it.poi.name} [{it.poi.category}]"]
            if it.poi.address:
                parts.append(it.poi.address)
            if it.poi.distance_from_user is not None:
                parts.append(f"距检索中心约{it.poi.distance_from_user}km")
            if prefix:
                parts.append(prefix)
            lines.append(" ".join(parts))
    return "\n".join(lines).strip()


def _format_execution_summary(state: SessionState) -> str:
    plan = next((p for p in state.candidate_plans if p.id == state.selected_plan_id), None)
    if not plan:
        return "执行完成。"

    lines = ["✅ 方案已执行完毕！以下是完整行程：", ""]
    for i, item in enumerate(plan.items, 1):
        # 查找执行状态
        status = ""
        order_detail = ""
        for ex in state.executions:
            if ex.details.get("poi_id") == item.poi.id:
                if ex.step == "place_order" and ex.ok:
                    items_list = ex.details.get("items", [])
                    status = "已下单"
                    if items_list:
                        order_detail = f"  → 已点: {', '.join(str(x) for x in items_list)}"
                elif ex.step == "arrange_visit":
                    status = "已安排到访"

        leg = ""
        if item.travel_from_prev:
            leg = f"（{item.travel_from_prev.mode} {item.travel_from_prev.minutes}分钟/{item.travel_from_prev.distance_km}km）"

        lines.append(f"{i}. {item.poi.name} [{item.poi.category}] {leg}")
        if item.poi.address:
            lines.append(f"   📍 {item.poi.address}")
        if status:
            lines.append(f"   ✅ {status}{order_detail}")
        lines.append("")

    lines.append("---")
    to_email = os.getenv("MEITUAN_AGENT_EMAIL_SENDER")
    if to_email:
        if "@" in to_email:
            name, domain = to_email.split("@", 1)
            masked_email = f"{name[:3]}***@{domain}" if len(name) > 3 else f"***@{domain}"
        else:
            masked_email = "***"
        lines.append(f"📧 完整行程已发送至 {masked_email}，请查收邮件。")
    return "\n".join(lines)


def _format_replan_message(state: SessionState, llm: OpenAICompatClient | None = None) -> str:
    err = state.last_error or "unknown"
    return f"执行遇到问题（{err}），已触发自动重规划并给出备选方案。\n\n{_format_plan_message(state, llm)}"
