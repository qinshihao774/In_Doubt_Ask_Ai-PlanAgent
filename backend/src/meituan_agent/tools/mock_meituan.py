from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from meituan_agent.domain.models import Location, POI
from meituan_agent.tools.base import AvailabilityTool, MenuInfoTool, OrderTool, POISearchTool


DEFAULT_POIS: list[dict[str, Any]] = [
    {
        "id": "poi_light_food_001",
        "name": "Green Bowl 轻食",
        "category": "餐饮",
        "lat": 39.9098,
        "lng": 116.3995,
        "address": "北京东城区示例路 1 号",
        "rating": 4.7,
        "price": 58,
        "price_level": 2,
        "tags": ["轻食", "沙拉", "减脂"],
        "duration_minutes": 70,
        "open_hours": "10:00-21:00",
        "menu": [
            {"name": "鸡胸肉能量碗", "price": 39, "tags": ["低脂", "高蛋白"]},
            {"name": "牛油果藜麦沙拉", "price": 36, "tags": ["低卡", "减脂"]},
            {"name": "低糖酸奶杯", "price": 18, "tags": ["低糖"]},
        ],
    },
    {
        "id": "poi_cantonese_001",
        "name": "粤满庭",
        "category": "餐饮",
        "lat": 39.9071,
        "lng": 116.4012,
        "address": "北京东城区示例路 8 号",
        "rating": 4.5,
        "price": 92,
        "price_level": 3,
        "tags": ["粤菜", "家庭聚餐"],
        "duration_minutes": 90,
        "open_hours": "11:00-22:00",
        "menu": [
            {"name": "虾饺皇", "price": 36},
            {"name": "烧味双拼", "price": 68},
            {"name": "例汤", "price": 22},
        ],
    },
    {
        "id": "poi_kids_park_001",
        "name": "童趣探索乐园",
        "category": "亲子",
        "lat": 39.9112,
        "lng": 116.3958,
        "address": "北京东城区亲子街 6 号",
        "rating": 4.8,
        "price": 88,
        "price_level": 2,
        "tags": ["亲子", "游乐", "儿童"],
        "duration_minutes": 120,
        "open_hours": "09:30-20:30",
    },
    {
        "id": "poi_book_001",
        "name": "种子绘本馆",
        "category": "亲子",
        "lat": 39.9062,
        "lng": 116.3941,
        "address": "北京东城区阅读路 3 号",
        "rating": 4.6,
        "price": 35,
        "price_level": 1,
        "tags": ["亲子", "绘本", "阅读"],
        "duration_minutes": 80,
        "open_hours": "10:00-19:00",
    },
    {
        "id": "poi_exhibit_001",
        "name": "城市艺术展",
        "category": "休闲娱乐",
        "lat": 39.913,
        "lng": 116.402,
        "address": "北京朝阳区艺术路 10 号",
        "rating": 4.4,
        "price": 68,
        "price_level": 2,
        "tags": ["展览", "艺术", "朋友"],
        "duration_minutes": 100,
        "open_hours": "10:00-21:00",
    },
]


class MockMeituanTools(POISearchTool, MenuInfoTool, AvailabilityTool, OrderTool):
    """Offline dataset used by tests and explicit mock mode only."""

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)
        self._pois = self._load_pois()
        self._poi_index = {poi.id: poi for poi in self._pois}

    def search_poi(self, *, tag: str | None, location: Location | None, radius_km: float = 3.0) -> list[POI]:
        tag_text = (tag or "").strip().lower()
        ranked = [poi for poi in self._pois if self._matches_tag(poi, tag_text)]
        if not ranked and tag_text:
            ranked = [poi for poi in self._pois if tag_text in poi.name.lower()]
        if location:
            ranked = [self._attach_distance(poi, location) for poi in ranked]
            ranked.sort(key=lambda x: (x.distance_from_user is None, x.distance_from_user or 999999, -x.rating))
        else:
            ranked.sort(key=lambda x: (-x.rating, x.name))
        return ranked[:20]

    def get_menu_info(self, poi_id: str, *, fat_content: bool = False) -> dict[str, Any]:
        poi = self._poi_index.get(poi_id)
        if not poi or poi.category != "餐饮":
            return {"ok": False, "error": "menu_not_found", "poi_id": poi_id}
        menu = list(poi.menu or [])
        if fat_content:
            menu = [item for item in menu if not any(word in str(item.get("name", "")) for word in ["炸", "奶油", "肥牛"])] or menu
        return {"ok": True, "poi_id": poi_id, "menu": menu}

    def check_table_availability(self, poi_id: str, *, size: int) -> dict[str, Any]:
        poi = self._poi_index.get(poi_id)
        if not poi or poi.category != "餐饮":
            return {"ok": False, "error": "restaurant_not_found", "poi_id": poi_id}
        queue_minutes = 15 if poi_id == "poi_light_food_001" else 0
        return {
            "ok": True,
            "poi_id": poi_id,
            "queue_minutes": queue_minutes,
            "party_size": size,
            "capacity_ok": size <= 6,
            "business_open": True,
            "reservable_slots": ["14:30", "16:00", "17:30", "18:30"],
            "table_available": size <= 6,
        }

    def place_order(self, poi_id: str, *, items: list[dict[str, Any]], user_notes: str | None = None) -> dict[str, Any]:
        poi = self._poi_index.get(poi_id)
        if not poi or poi.category != "餐饮":
            return {"ok": False, "error": "restaurant_not_found", "poi_id": poi_id}
        return {
            "ok": True,
            "poi_id": poi_id,
            "items": items,
            "user_notes": user_notes,
            "order_id": f"mock-order-{poi_id}",
        }

    def _load_pois(self) -> list[POI]:
        file_path = self._data_dir / "mock_pois.json"
        raw: list[dict[str, Any]]
        if file_path.exists():
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            raw = DEFAULT_POIS
        return [self._to_poi(item) for item in raw]

    def _to_poi(self, item: dict[str, Any]) -> POI:
        lat = float(item.get("lat", 0.0))
        lng = float(item.get("lng", 0.0))
        location = Location(lat=lat, lng=lng, label=item.get("name"))
        return POI(
            id=str(item["id"]),
            name=str(item["name"]),
            category=str(item.get("category", "其他")),
            location=location,
            lat=lat,
            lng=lng,
            tags=[str(tag) for tag in item.get("tags", [])],
            rating=float(item.get("rating", 0.0)),
            price=float(item["price"]) if item.get("price") is not None else None,
            price_level=int(item["price_level"]) if item.get("price_level") is not None else None,
            address=item.get("address"),
            open_hours=item.get("open_hours"),
            duration_minutes=int(item["duration_minutes"]) if item.get("duration_minutes") is not None else None,
            menu=item.get("menu"),
            image_url=item.get("image_url"),
            tel=item.get("tel"),
            business_area=item.get("business_area"),
        )

    def _matches_tag(self, poi: POI, tag_text: str) -> bool:
        if not tag_text:
            return True
        haystacks = [
            poi.name.lower(),
            poi.category.lower(),
            " ".join(tag.lower() for tag in poi.tags),
        ]
        joined = " ".join(haystacks)
        keyword_groups = [
            ({"餐饮", "美食", "吃", "轻食", "粤菜", "咖啡"}, {"餐饮"}),
            ({"亲子", "儿童", "绘本", "遛娃"}, {"亲子"}),
            ({"展览", "剧本杀", "citywalk", "朋友", "休闲", "娱乐"}, {"休闲娱乐", "亲子"}),
        ]
        for words, categories in keyword_groups:
            if any(word in tag_text for word in words):
                return poi.category in categories or any(word in joined for word in words)
        return tag_text in joined

    def _attach_distance(self, poi: POI, location: Location) -> POI:
        distance = round(self._distance_km(location, poi.location or Location(lat=poi.lat, lng=poi.lng)), 1)
        return poi.model_copy(update={"distance_from_user": distance})

    def _distance_km(self, origin: Location, dest: Location) -> float:
        dx = (origin.lng - dest.lng) * 111 * 0.85
        dy = (origin.lat - dest.lat) * 111
        return (dx * dx + dy * dy) ** 0.5
