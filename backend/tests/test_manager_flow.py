from pathlib import Path

from meituan_agent.agents.execution_agent import ExecutionAgent
from meituan_agent.agents.food_agent import FoodAgent
from meituan_agent.agents.leisure_agent import LeisureAgent
from meituan_agent.agents.manager_agent import ManagerAgent
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.domain.models import Location, SessionStatus
from meituan_agent.memory.inmemory import InMemoryStore
from meituan_agent.planning.planner import HeuristicPlanner
from meituan_agent.services.session_service import SessionService
from meituan_agent.tools.mock_map import MockMapTool
from meituan_agent.tools.mock_meituan import MockMeituanTools
from meituan_agent.tools.mock_rpa import MockRPAExecutor


def _build_service(tmp_path):
    meituan = MockMeituanTools(str(tmp_path))
    map_tool = MockMapTool()
    rpa = MockRPAExecutor()
    planner = HeuristicPlanner(map_tool)
    manager = ManagerAgent(
        semantic=None,
        food=FoodAgent(meituan),
        leisure=LeisureAgent(meituan),
        map_agent=MapAgent(map_tool),
        execution=ExecutionAgent(availability=meituan, menu=meituan, order=meituan, rpa=rpa, max_queue_minutes=120),
        planner=planner,
    )
    memory = InMemoryStore()
    return SessionService(memory, manager)

# 测试期望：发送"确认 方案1"后进入执行流程，产生 executions 记录。
def test_plan_and_execute(tmp_path):
    data_dir = tmp_path
    (data_dir / "mock_pois.json").write_text(
        (Path(__file__).resolve().parents[1] / "data" / "mock_pois.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    svc = _build_service(data_dir)

    state, reply = svc.chat(session_id=None, message="下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时")
    assert "方案" in reply
    assert state.status == SessionStatus.awaiting_confirmation
    assert len(state.candidate_plans) >= 1
    plan = state.candidate_plans[0]
    assert plan.total_minutes is not None
    assert 240 <= plan.total_minutes <= 360
    assert plan.actions
    assert any(action.type == "place_food_order" for action in plan.actions)
    assert any(item.start and item.end for item in plan.items)
    restaurant = next(item for item in plan.items if item.poi.category == "餐饮")
    assert restaurant.availability is not None
    assert restaurant.availability["ok"] is True

    state2, reply2 = svc.chat(session_id=state.session_id, message="确认 方案1")
    assert state2.status in {SessionStatus.completed, SessionStatus.awaiting_confirmation}
    assert len(state2.executions) >= 1
    steps = {ex.step for ex in state2.executions}
    assert "reserve_restaurant" in steps
    assert "place_order" in steps
    assert "book_activity" in steps or "arrange_visit" in steps


class SlowQueueMeituan(MockMeituanTools):
    def check_table_availability(self, poi_id: str, *, size: int) -> dict:
        data = super().check_table_availability(poi_id, size=size)
        if poi_id == "poi_light_food_001":
            data["queue_minutes"] = 180
        return data


def test_planning_filters_restaurants_with_too_long_queue(tmp_path):
    data_dir = tmp_path
    (data_dir / "mock_pois.json").write_text(
        (Path(__file__).resolve().parents[1] / "data" / "mock_pois.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    meituan = SlowQueueMeituan(str(data_dir))
    map_tool = MockMapTool()
    manager = ManagerAgent(
        semantic=None,
        food=FoodAgent(meituan),
        leisure=LeisureAgent(meituan),
        map_agent=MapAgent(map_tool),
        execution=ExecutionAgent(availability=meituan, menu=meituan, order=meituan, rpa=MockRPAExecutor(), max_queue_minutes=60),
        planner=HeuristicPlanner(map_tool),
    )
    svc = SessionService(InMemoryStore(), manager)

    state, _reply = svc.chat(session_id=None, message="下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时")

    assert state.candidate_plans
    used_restaurant_ids = {item.poi.id for plan in state.candidate_plans for item in plan.items if item.poi.category == "餐饮"}
    assert "poi_light_food_001" not in used_restaurant_ids
    assert "poi_cantonese_001" in used_restaurant_ids


def test_bootstrap_location_is_kept_even_when_message_contains_location_hint(tmp_path):
    data_dir = tmp_path
    (data_dir / "mock_pois.json").write_text(
        (Path(__file__).resolve().parents[1] / "data" / "mock_pois.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    svc = _build_service(data_dir)
    browser_location = Location(lat=30.414, lng=103.812, label="四川省成都市新津区")

    state, _reply = svc.chat(
        session_id=None,
        message="下午想在武汉附近吃饭和玩，别太远",
        bootstrap_location=browser_location,
    )

    assert state.location is not None
    assert state.location.label == "四川省成都市新津区"
    assert state.scratch["location_source"] == "bootstrap"
    assert state.scratch["bootstrap_location"]["label"] == "四川省成都市新津区"

