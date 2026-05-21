from meituan_agent.agents.manager_agent import _format_plan_message
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.domain.models import ItineraryItem, ItineraryPlan, Location, POI, RouteLeg, SessionState
from meituan_agent.location_parser import extract_location_hint


class HallucinatingLLM:
    def chat(self, *, system: str, user: str) -> str:
        return "方案1：春熙路，方案2：合肥"


def test_extract_location_hint_from_user_query():
    text = "我现在在成都新津，我只想在新津就近吃饭和娱乐，请你帮我安排计划"
    assert extract_location_hint(text) == "成都新津"


def test_format_plan_message_keeps_real_pois_even_if_llm_exists():
    state = SessionState(
        session_id="s1",
        location=Location(lat=30.41, lng=103.81, label="四川省成都市新津区"),
        candidate_plans=[
            ItineraryPlan(
                id="plan_1",
                title="就近亲子方案",
                rationale="先玩后吃，减少移动距离",
                items=[
                    ItineraryItem(
                        poi=POI(
                            id="poi_1",
                            name="新津亲子乐园",
                            category="亲子",
                            lat=30.412,
                            lng=103.815,
                            address="成都市新津区示例路 1 号",
                            distance_from_user=0.8,
                        ),
                        travel_from_prev=RouteLeg(mode="walk", minutes=12, distance_km=0.8),
                    ),
                    ItineraryItem(
                        poi=POI(
                            id="poi_2",
                            name="新津社区餐厅",
                            category="餐饮",
                            lat=30.415,
                            lng=103.819,
                            address="成都市新津区示例路 8 号",
                            distance_from_user=1.2,
                        ),
                        travel_from_prev=RouteLeg(mode="walk", minutes=6, distance_km=0.4),
                    ),
                ],
            )
        ],
    )

    text = _format_plan_message(state, HallucinatingLLM())

    assert "四川省成都市新津区" in text
    assert "新津亲子乐园" in text
    assert "新津社区餐厅" in text
    assert "春熙路" not in text
    assert "合肥" not in text


class BootstrapAwareMap:
    def ip_location(self) -> Location | None:
        return Location(lat=31.23, lng=121.47, label="上海")

    def search_poi(self, *, tag, location, radius_km=3.0):
        return []

    def route(self, origin, dest, *, mode="walk"):
        return RouteLeg(mode=mode, minutes=10, distance_km=1.0)


def test_map_agent_prefers_bootstrap_location_when_user_did_not_say_place():
    state = SessionState(
        session_id="s2",
        location=Location(lat=30.41, lng=103.81, label="四川省成都市新津区"),
    )
    new_state = MapAgent(BootstrapAwareMap()).run(state, "帮我安排下午吃饭和娱乐")
    assert new_state.location is not None
    assert new_state.location.label == "四川省成都市新津区"
