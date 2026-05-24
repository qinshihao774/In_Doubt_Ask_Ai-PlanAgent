"""
ExecutionAgent — 方案落地执行

执行流程:
  1. 逐个 POI 检查排队/可订状态
  2. 查询菜单信息
  3. 模拟下单（返回"已订"信号）
  4. 生成路线导航信息
  5. 汇总完整执行行程
"""

from __future__ import annotations

from typing import Any

from meituan_agent.agents.base import Agent
from meituan_agent.domain.models import ExecutionResult, Location, RouteLeg, SessionState
from meituan_agent.tools.base import AvailabilityTool, MapTool, MenuInfoTool, OrderTool, RPAExecutor


class ExecutionAgent(Agent):
    def __init__(
        self,
        availability: AvailabilityTool,
        menu: MenuInfoTool,
        order: OrderTool,
        rpa: RPAExecutor,
        *,
        max_queue_minutes: int = 60,
    ) -> None:
        self._availability = availability
        self._menu = menu
        self._order = order
        self._rpa = rpa
        self._max_queue = max_queue_minutes

    def run(self, state: SessionState, user_message: str) -> SessionState:
        return state

    def execute_plan(self, state: SessionState) -> SessionState:
        plan = next((p for p in state.candidate_plans if p.id == state.selected_plan_id), None)
        if not plan:
            state.last_error = "selected_plan_not_found"
            return state

        state.executions.clear()
        all_ok = True

        for item in plan.items:
            if item.poi.category != "餐饮":
                # 非餐饮：标记为已安排
                state.executions.append(ExecutionResult(
                    ok=True, step="arrange_visit",
                    details={"poi_id": item.poi.id, "poi_name": item.poi.name, "status": "已安排到访"},
                ))
                continue

            # === 餐饮 POI 执行流程 ===
            poi_id = item.poi.id
            poi_name = item.poi.name

            # 1) 排队检查
            av = self._availability.check_table_availability(poi_id, size=state.profile.party_size)
            queue_minutes = av.get("queue_minutes")
            too_long = queue_minutes is not None and int(queue_minutes) > self._max_queue
            av_ok = bool(av.get("ok")) and not too_long
            state.executions.append(ExecutionResult(
                ok=av_ok, step="check_availability",
                details={
                    "poi_id": poi_id,
                    "poi_name": poi_name,
                    "max_queue_minutes": self._max_queue,
                    "queue_too_long": bool(too_long),
                    **av,
                },
            ))
            if not av_ok:
                state.last_error = f"排队检查失败: {poi_name}"
                return state

            # 只检查了 ok，没有检查 queue_minutes
            # 虽然 ExecutionAgent 构造时接受了 max_queue_minutes，但此阈值未被使用
            if av.get("queue_minutes",0) > self._max_queue:
                state.last_error = f"排队超时: {poi_name} 需等待{av['queue_minutes']} 分钟"
                return state

            # 2) 菜单查询
            menu = self._menu.get_menu_info(poi_id, fat_content=state.profile.fat_loss)
            state.executions.append(ExecutionResult(
                ok=bool(menu.get("ok")), step="get_menu_info",
                details={"poi_id": poi_id, "poi_name": poi_name, "menu_count": len(menu.get("menu") or [])},
            ))
            if not menu.get("ok"):
                state.last_error = f"菜单查询失败: {poi_name}"
                return state

            # 3) 选菜
            picked = _pick_order_items(menu.get("menu") or [], party_size=state.profile.party_size)

            # 4) 模拟下单 → 返回"已订"信号
            order = self._order.place_order(poi_id, items=picked, user_notes="auto")
            state.executions.append(ExecutionResult(
                ok=bool(order.get("ok")), step="place_order",
                details={
                    "poi_id": poi_id, "poi_name": poi_name,
                    "order_id": order.get("order_id", ""),
                    "items": [i.get("name") for i in picked],
                    "status": "已下单，餐厅已确认" if order.get("ok") else order.get("error"),
                },
            ))
            if not order.get("ok"):
                state.last_error = f"下单失败: {poi_name}"
                all_ok = False

        if all_ok:
            state.last_error = None
        return state

    def build_itinerary(self, state: SessionState, map_tool: MapTool | None = None) -> list[dict]:
        """构建完整行程数据（含路线），供邮件和展示使用"""
        plan = next((p for p in state.candidate_plans if p.id == state.selected_plan_id), None)
        if not plan:
            return []

        items: list[dict] = []
        prev_loc = state.location
        for it in plan.items:
            entry: dict[str, Any] = {
                "poi": it.poi.name,
                "category": it.poi.category,
                "address": it.poi.address or "",
                "rating": it.poi.rating,
                "status": "",
                "leg": "",
            }

            # 路线
            if prev_loc and map_tool and it.poi.location:
                try:
                    leg: RouteLeg = map_tool.route(prev_loc, it.poi.location, mode="walk")
                    entry["leg"] = f"{leg.mode} {leg.minutes}分钟 / {leg.distance_km}km"
                except Exception:
                    entry["leg"] = "步行 约15分钟"

            # 执行状态
            for ex in state.executions:
                if ex.details.get("poi_id") == it.poi.id:
                    if ex.step == "place_order":
                        entry["status"] = ex.details.get("status", "已下单")
                    elif ex.step == "arrange_visit":
                        entry["status"] = "已安排到访"
                    elif ex.step == "check_availability":
                        entry["status"] = "已确认有位"

            if not entry["status"]:
                entry["status"] = "已安排"

            items.append(entry)
            if it.poi.location:
                prev_loc = it.poi.location

        return items


def _pick_order_items(menu: list[dict[str, Any]], *, party_size: int) -> list[dict[str, Any]]:
    if not menu:
        return [{"name": "推荐套餐", "qty": max(1, party_size // 2)}]
    picks = []
    for i, item in enumerate(menu[:min(3, len(menu))]):
        qty = 2 if i == 0 else 1
        picks.append({"name": item.get("name", f"菜品{i+1}"), "qty": qty})
    return picks
