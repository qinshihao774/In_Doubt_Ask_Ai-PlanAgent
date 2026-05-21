from __future__ import annotations

import math

from meituan_agent.domain.models import Location, POI, RouteLeg
from meituan_agent.tools.base import MapTool, POISearchTool


class MockMapTool(POISearchTool, MapTool):
    """Minimal offline map tool used only by tests and explicit mock mode."""

    def geocode(self, address: str, city: str = "北京") -> Location | None:
        label = address if city in address else f"{city}-{address}"
        return Location(lat=39.908, lng=116.397, label=label)

    def ip_location(self) -> Location | None:
        return Location(lat=39.908, lng=116.397, label="北京·天安门")

    def search_poi(self, *, tag: str | None, location: Location | None, radius_km: float = 3.0) -> list[POI]:
        return []

    def reverse_geocode(self, lat: float, lng: float) -> str:
        return "模拟位置"

    def route(self, origin: Location, dest: Location, *, mode: str = "walk") -> RouteLeg:
        dist_km = self._haversine_km(origin.lat, origin.lng, dest.lat, dest.lng)
        speed = 4.5 if mode == "walk" else 28.0
        minutes = max(1, int(dist_km / speed * 60))
        return RouteLeg(mode="metro" if mode == "metro" else mode, minutes=minutes, distance_km=round(dist_km, 1))

    def _haversine_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
        )
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))
