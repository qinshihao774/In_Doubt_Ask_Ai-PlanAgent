import json
from pathlib import Path

from meituan_agent.agents.execution_agent import ExecutionAgent
from meituan_agent.agents.food_agent import FoodAgent
from meituan_agent.agents.leisure_agent import LeisureAgent
from meituan_agent.agents.manager_agent import ManagerAgent
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.memory.inmemory import InMemoryStore
from meituan_agent.planning.planner import FallbackPlanner, HeuristicPlanner, LLMPlanner
from meituan_agent.services.session_service import SessionService
from meituan_agent.tools.mock_map import MockMapTool
from meituan_agent.tools.mock_meituan import MockMeituanTools
from meituan_agent.tools.mock_rpa import MockRPAExecutor


class StubLLM:
    def chat(self, *, system: str, user: str) -> str:
        payload = json.loads(user)
        excluded = set(payload["constraints"]["excluded_poi_ids"])
        if "poi_light_food_001" in excluded:
            restaurant = "poi_cantonese_001"
        else:
            restaurant = "poi_light_food_001"
        out = {
            "plans": [
                {
                    "title": "LLM方案",
                    "rationale": "结构化输出",
                    "items": [
                        {"poi_id": "poi_kids_park_001", "category": "亲子"},
                        {"poi_id": restaurant, "category": "餐饮"},
                        {"poi_id": "poi_book_001", "category": "亲子"},
                    ],
                }
            ]
        }
        return json.dumps(out, ensure_ascii=False)


def _build_service(tmp_path):
    data_dir = tmp_path
    (data_dir / "mock_pois.json").write_text(
        (Path(__file__).resolve().parents[1] / "data" / "mock_pois.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    meituan = MockMeituanTools(str(data_dir))
    map_tool = MockMapTool()
    rpa = MockRPAExecutor()

    heuristic = HeuristicPlanner(map_tool)
    llm_planner = LLMPlanner(llm=StubLLM(), poi_search=meituan, map_tool=map_tool)
    planner = FallbackPlanner(llm_planner, heuristic)

    manager = ManagerAgent(
        semantic=None,
        food=FoodAgent(meituan),
        leisure=LeisureAgent(meituan),
        map_agent=MapAgent(map_tool),
        execution=ExecutionAgent(availability=meituan, menu=meituan, order=meituan, rpa=rpa, max_queue_minutes=0),
        planner=planner,
        llm=None,
    )
    memory = InMemoryStore()
    return SessionService(memory, manager)


def test_llm_structured_planning_and_replan(tmp_path):
    svc = _build_service(tmp_path)
    state, reply = svc.chat(session_id=None, message="下午2点出发，带5岁娃，老婆减脂，帮我规划4-6小时")
    assert "LLM方案" in reply
    assert any(it.poi.id == "poi_light_food_001" for it in state.candidate_plans[0].items)

    state2, reply2 = svc.chat(session_id=state.session_id, message="确认 方案1")
    assert "已触发自动重规划" in reply2
    assert any(it.poi.id == "poi_cantonese_001" for it in state2.candidate_plans[0].items)
