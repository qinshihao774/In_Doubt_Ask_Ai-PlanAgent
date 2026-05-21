from pathlib import Path

from meituan_agent.agents.execution_agent import ExecutionAgent
from meituan_agent.agents.food_agent import FoodAgent
from meituan_agent.agents.leisure_agent import LeisureAgent
from meituan_agent.agents.manager_agent import ManagerAgent
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.domain.models import SessionStatus
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

    state2, reply2 = svc.chat(session_id=state.session_id, message="确认 方案1")
    assert state2.status in {SessionStatus.completed, SessionStatus.awaiting_confirmation}
    assert len(state2.executions) >= 1

