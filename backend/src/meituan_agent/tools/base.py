from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from meituan_agent.domain.models import Location, POI, RouteLeg


class POISearchTool(ABC):
    @abstractmethod
    def search_poi(self, *, tag: str | None, location: Location | None, radius_km: float = 3.0) -> list[POI]: ...


class MenuInfoTool(ABC):
    @abstractmethod
    def get_menu_info(self, poi_id: str, *, fat_content: bool = False) -> dict[str, Any]: ...


class AvailabilityTool(ABC):
    @abstractmethod
    def check_table_availability(self, poi_id: str, *, size: int) -> dict[str, Any]: ...


class OrderTool(ABC):
    @abstractmethod
    def place_order(self, poi_id: str, *, items: list[dict[str, Any]], user_notes: str | None = None) -> dict[str, Any]: ...


class MapTool(ABC):
    @abstractmethod
    def route(self, origin: Location, dest: Location, *, mode: str = "walk") -> RouteLeg: ...

    @abstractmethod
    def reverse_geocode(self, lat: float, lng: float) -> str: ...


class RPAExecutor(ABC):
    @abstractmethod
    def execute(self, *, action: str, payload: dict[str, Any]) -> dict[str, Any]: ...

