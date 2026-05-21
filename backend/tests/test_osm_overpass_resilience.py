from meituan_agent.domain.models import Location
from meituan_agent.tools.osm_tools import OpenStreetMapTools


class RetryingOSM(OpenStreetMapTools):
    def __init__(self):
        super().__init__(overpass_url="https://primary.example/api/interpreter")
        self.calls: list[tuple[str, int]] = []

    def _client(self, *, timeout: float = 15.0):
        raise AssertionError("test should not use real http client")

    def _search_overpass_with_retry(self, query_blocks, location, radius_m):
        return super()._search_overpass_with_retry(query_blocks, location, radius_m)

    def _build_overpass_query(self, query_blocks, location, radius_m, *, timeout_seconds=12, result_limit=30):
        return super()._build_overpass_query(
            query_blocks,
            location,
            radius_m,
            timeout_seconds=timeout_seconds,
            result_limit=result_limit,
        )


def test_build_overpass_urls_keeps_primary_and_deduplicates():
    tools = OpenStreetMapTools(overpass_url="https://overpass-api.de/api/interpreter")
    urls = tools.overpass_urls
    assert urls[0] == "https://overpass-api.de/api/interpreter"
    assert len(urls) == len(set(urls))


def test_build_overpass_query_uses_custom_timeout_and_limit():
    tools = OpenStreetMapTools()
    query = tools._build_overpass_query(
        [("amenity", "restaurant|cafe")],
        Location(lat=30.4, lng=103.8, label="成都新津"),
        3000,
        timeout_seconds=9,
        result_limit=18,
    )
    assert "[timeout:9]" in query
    assert "out center 18;" in query


class FallbackOSM(OpenStreetMapTools):
    def _search_overpass_with_retry(self, query_blocks, location, radius_m):
        return None

    def _search_nominatim_fallback(self, *, tag: str, location: Location, radius_km: float):
        return ["fallback-poi"]


def test_search_poi_falls_back_to_nominatim_when_overpass_unavailable():
    tools = FallbackOSM()
    result = tools.search_poi(tag="美食", location=Location(lat=30.4, lng=103.8, label="成都新津"), radius_km=3.0)
    assert result == ["fallback-poi"]
