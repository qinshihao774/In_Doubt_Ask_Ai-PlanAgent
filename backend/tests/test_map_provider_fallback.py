from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.container import Container
from meituan_agent.domain.models import Location, SessionState
from meituan_agent.tools.osm_tools import OpenStreetMapTools


class FakeGeoMap(OpenStreetMapTools):
    def __init__(self):
        pass

    def geocode(self, address: str, city: str = "北京") -> Location | None:
        return Location(lat=39.90, lng=116.40, label=f"{city}-{address}")

    def ip_location(self) -> Location | None:
        return Location(lat=31.23, lng=121.47, label="上海")

    def search_poi(self, *, tag: str | None, location: Location | None, radius_km: float = 3.0):
        return []

    def route(self, origin: Location, dest: Location, *, mode: str = "walk"):
        from meituan_agent.domain.models import RouteLeg

        return RouteLeg(mode=mode, minutes=10, distance_km=1.0)


def test_map_agent_supports_duck_typed_geocode_tool():
    agent = MapAgent(FakeGeoMap())
    state = SessionState(session_id="s1")

    new_state = agent.run(state, "去国贸附近吃饭")

    assert new_state.location is not None
    assert "国贸" in (new_state.location.label or "")


def test_container_falls_back_to_osm_when_no_amap_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MEITUAN_AGENT_MAP_PROVIDER", "auto")
    monkeypatch.setenv("MEITUAN_AGENT_AMAP_API_KEY", "")
    monkeypatch.setenv("MEITUAN_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MEITUAN_AGENT_SQLITE_PATH", str(tmp_path / "memory.sqlite3"))

    container = Container()

    assert isinstance(container.map_tool, OpenStreetMapTools)
    assert isinstance(container.meituan, OpenStreetMapTools)
