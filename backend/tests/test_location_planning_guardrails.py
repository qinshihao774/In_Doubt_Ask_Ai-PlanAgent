from meituan_agent.agents.manager_agent import _format_plan_message
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.domain.models import ItineraryItem, ItineraryPlan, Location, POI, RouteLeg, SemanticSchema, SessionState
from meituan_agent.location_parser import extract_location_hint
from meituan_agent.planning.constraints import filter_candidates


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

    def geocode(self, hint: str, city: str | None = None) -> Location | None:
        if "北京" in hint:
            return Location(lat=39.92, lng=116.46, label="北京·朝阳")
        return None

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


def test_map_agent_prefers_user_message_location_over_bootstrap_location():
    state = SessionState(
        session_id="s3",
        location=Location(lat=31.23, lng=121.47, label="上海"),
        scratch={
            "bootstrap_location": Location(lat=31.23, lng=121.47, label="上海").model_dump(),
            "location_source": "bootstrap",
        },
    )
    new_state = MapAgent(BootstrapAwareMap()).run(state, "我现在在北京朝阳，帮我安排下午吃饭和娱乐")
    assert new_state.location is not None
    assert new_state.location.label == "北京·朝阳"


class AmbiguousFarawayMap:
    def geocode(self, hint: str, city: str | None = None) -> Location | None:
        if "武汉" in hint:
            return Location(lat=30.5928, lng=114.3055, label="湖北省武汉市")
        if "国贸" in hint:
            return Location(lat=30.66, lng=104.08, label=f"{city or '成都'}·国贸")
        return None

    def search_poi(self, *, tag, location, radius_km=3.0):
        return []

    def route(self, origin, dest, *, mode="walk"):
        return RouteLeg(mode=mode, minutes=10, distance_km=1.0)


def test_map_agent_rejects_ambiguous_faraway_place_when_browser_location_exists():
    state = SessionState(
        session_id="s4",
        location=Location(lat=30.67, lng=104.06, label="四川省成都市武侯区"),
        scratch={
            "bootstrap_location": Location(lat=30.67, lng=104.06, label="四川省成都市武侯区").model_dump(),
            "location_source": "bootstrap",
        },
    )

    new_state = MapAgent(AmbiguousFarawayMap()).run(state, "下午想在武汉附近吃饭和玩，别太远")

    assert new_state.location is not None
    assert new_state.location.label == "四川省成都市武侯区"
    assert new_state.scratch["location_hint_rejected"]["reason"] == "ambiguous_or_too_far_from_user_location"


def test_map_agent_accepts_explicit_faraway_administrative_destination():
    state = SessionState(
        session_id="s5",
        location=Location(lat=30.67, lng=104.06, label="四川省成都市武侯区"),
        scratch={
            "bootstrap_location": Location(lat=30.67, lng=104.06, label="四川省成都市武侯区").model_dump(),
            "location_source": "bootstrap",
        },
    )

    new_state = MapAgent(AmbiguousFarawayMap()).run(state, "明天去武汉市旅游，帮我安排下午吃饭和娱乐")

    assert new_state.location is not None
    assert new_state.location.label == "湖北省武汉市"


def test_map_agent_accepts_nearby_local_hint_with_browser_location():
    state = SessionState(
        session_id="s6",
        location=Location(lat=30.67, lng=104.06, label="四川省成都市武侯区"),
        scratch={
            "bootstrap_location": Location(lat=30.67, lng=104.06, label="四川省成都市武侯区").model_dump(),
            "location_source": "bootstrap",
        },
    )

    new_state = MapAgent(AmbiguousFarawayMap()).run(state, "去国贸附近吃饭和娱乐")

    assert new_state.location is not None
    assert "国贸" in (new_state.location.label or "")


class VenueMap:
    def geocode(self, hint: str, city: str | None = None) -> Location | None:
        if "碧乐城" in hint:
            return Location(lat=30.414, lng=103.812, label=f"{city or '成都'}·碧乐城")
        return None

    def search_poi(self, *, tag, location, radius_km=3.0):
        return []

    def route(self, origin, dest, *, mode="walk"):
        return RouteLeg(mode=mode, minutes=5, distance_km=0.3)


def test_map_agent_records_inside_venue_constraint():
    state = SessionState(
        session_id="s7",
        location=Location(lat=30.414, lng=103.812, label="四川省成都市新津区"),
        planning_context=SemanticSchema(),
        scratch={
            "bootstrap_location": Location(lat=30.414, lng=103.812, label="四川省成都市新津区").model_dump(),
            "location_source": "bootstrap",
        },
    )

    new_state = MapAgent(VenueMap()).run(state, "下午想在碧乐城内吃饭和玩，别太远")

    assert new_state.scratch["venue_constraint"]["name"] == "碧乐城"
    assert new_state.scratch["venue_constraint"]["require_inside"] is True
    assert any("碧乐城内" in item for item in new_state.planning_context.hard_constraints)


def test_inside_venue_constraint_filters_nearby_restaurants_without_evidence():
    state = SessionState(
        session_id="s8",
        planning_context=SemanticSchema(),
        scratch={
            "venue_constraint": {
                "name": "碧乐城",
                "require_inside": True,
                "evidence_policy": "address_or_business_area_or_name",
            },
            "food_candidates": [
                POI(
                    id="ayuan",
                    name="阿元路边烧烤",
                    category="餐饮",
                    lat=30.415,
                    lng=103.813,
                    address="成都市新津区五津街道瑞通路 88 号",
                    distance_from_user=0.2,
                ).model_dump(),
                POI(
                    id="inside",
                    name="碧乐城轻食厨房",
                    category="餐饮",
                    lat=30.414,
                    lng=103.812,
                    address="成都市新津区碧乐城 B1 层",
                    business_area="碧乐城",
                    distance_from_user=0.1,
                ).model_dump(),
            ],
            "leisure_candidates": [],
        },
    )

    new_state = filter_candidates(state)

    kept_ids = {poi["id"] for poi in new_state.scratch["food_candidates"]}
    assert kept_ids == {"inside"}
    rejection = next(item for item in new_state.scratch["constraint_rejections"] if item["poi_id"] == "ayuan")
    assert "缺少位于碧乐城内的明确证据" in rejection["reasons"]


class DuplicateHongshiMap:
    def geocode(self, hint: str, city: str | None = None) -> Location | None:
        if "红石" in hint:
            return Location(lat=30.56, lng=103.93, label="四川省成都市双流区红石")
        return None

    def search_poi(self, *, tag, location, radius_km=3.0):
        if "红石" not in (tag or ""):
            return []
        return [
            POI(
                id="hongshi_wujin",
                name="红石湿地公园",
                category="公园景区",
                lat=30.4145,
                lng=103.8125,
                address="成都市新津区五津街道红石湿地公园",
                tags=["湿地", "公园", "散步"],
                distance_from_user=0.6,
            ),
            POI(
                id="hongshi_shuangliu",
                name="红石公园",
                category="公园景区",
                lat=30.56,
                lng=103.93,
                address="成都市双流区红石社区",
                tags=["公园"],
                distance_from_user=28.0,
            ),
        ]

    def route(self, origin, dest, *, mode="walk"):
        return RouteLeg(mode=mode, minutes=5, distance_km=0.6)


def test_map_agent_resolves_duplicate_place_name_near_browser_location_first():
    state = SessionState(
        session_id="s9",
        location=Location(lat=30.414, lng=103.812, label="兴园3路，五津街道，新津区，成都市"),
        scratch={
            "bootstrap_location": Location(lat=30.414, lng=103.812, label="兴园3路，五津街道，新津区，成都市").model_dump(),
            "location_source": "bootstrap",
        },
    )

    new_state = MapAgent(DuplicateHongshiMap()).run(
        state,
        "我已经订在红石湿地公园散步，但是散步之前需要吃饭，我女朋友喜欢喝奶茶，所以吃饭的地方需要就近有奶茶店",
    )

    assert new_state.location is not None
    assert new_state.location.label == "红石湿地公园"
    assert new_state.scratch["location_source"] == "nearby_hint"
    assert new_state.scratch["location_hint_resolution"]["poi_id"] == "hongshi_wujin"
    assert new_state.scratch["intended_place_poi"]["id"] == "hongshi_wujin"
    assert "双流" not in (new_state.location.label or "")
