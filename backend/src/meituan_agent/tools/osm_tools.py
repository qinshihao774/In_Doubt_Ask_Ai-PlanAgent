from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from meituan_agent.domain.models import Location, POI, RouteLeg
from meituan_agent.tools.base import MapTool, POISearchTool

logger = logging.getLogger(__name__)


class OpenStreetMapTools(POISearchTool, MapTool):
    DEFAULT_OVERPASS_URLS = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )

    """基于 OpenStreetMap 生态的真实地点与路线实现。

    数据源：
    - Nominatim：地理编码
    - Overpass：POI 搜索
    - OSRM：路线规划

    适合无商业地图 Key 的比赛 / 个人项目场景。
    """

    def __init__(
        self,
        *,
        user_agent: str = "meituan-competition-agent/1.0",
        nominatim_url: str = "https://nominatim.openstreetmap.org",
        overpass_url: str = "https://overpass-api.de/api/interpreter",
        osrm_url: str = "https://router.project-osrm.org",
    ) -> None:
        self.user_agent = user_agent
        self.nominatim_url = nominatim_url.rstrip("/")
        self.overpass_url = overpass_url
        self.osrm_url = osrm_url.rstrip("/")
        self.overpass_urls = self._build_overpass_urls(overpass_url)

    def _client(self, *, timeout: float = 15.0) -> httpx.Client:
        return httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )

    def reverse_geocode(self, lat: float, lng: float) -> str:
        try:
            with self._client(timeout=10.0) as client:
                resp = client.get(
                    f"{self.nominatim_url}/reverse",
                    params={
                        "lat": lat,
                        "lon": lng,
                        "format": "jsonv2",
                        "accept-language": "zh-CN,zh",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                if "display_name" in data:
                    return data["display_name"]
        except Exception as exc:
            logger.warning("OSM reverse geocode failed: %s", exc)
        return f"坐标({lat:.4f}, {lng:.4f})"

    def geocode(self, address: str, city: str | None = None) -> Location | None:
        query = address.strip()
        if city and city not in query:
            query = f"{city} {query}"
        try:
            with self._client(timeout=12.0) as client:
                resp = client.get(
                    f"{self.nominatim_url}/search",
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "limit": 1,
                        "accept-language": "zh-CN,zh",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            if not data:
                return None
            item = data[0]
            return Location(
                lat=float(item["lat"]),
                lng=float(item["lon"]),
                label=item.get("display_name", address),
            )
        except Exception as exc:
            logger.warning("OSM geocode failed: %s", exc)
            return None

    def ip_location(self) -> Location | None:
        """免费 IP 定位，失败时返回 None。"""
        try:
            with self._client(timeout=8.0) as client:
                resp = client.get("https://ipwho.is/")
                resp.raise_for_status()
                data = resp.json()
            if not data.get("success"):
                return None
            lat = data.get("latitude")
            lng = data.get("longitude")
            if lat is None or lng is None:
                return None
            label_parts = [data.get("city"), data.get("region"), data.get("country")]
            label = " · ".join([x for x in label_parts if x]) or "IP 定位"
            return Location(lat=float(lat), lng=float(lng), label=label)
        except Exception as exc:
            logger.info("OSM ip location unavailable: %s", exc)
            return None

    def search_poi(self, *, tag: str | None, location: Location | None, radius_km: float = 3.0) -> list[POI]:
        if not location:
            location = Location(lat=39.908, lng=116.397, label="北京·天安门")

        query_blocks, default_category = self._build_query_blocks(tag or "")
        radius_m = max(500, int(radius_km * 1000))
        data = self._search_overpass_with_retry(query_blocks, location, radius_m)
        if not data:
            logger.warning("OSM overpass unavailable, fallback to Nominatim nearby search: tag=%s", tag or "综合")
            return self._search_nominatim_fallback(tag=tag or "", location=location, radius_km=radius_km)

        elements = data.get("elements", [])
        out: list[POI] = []
        seen: set[str] = set()
        for element in elements:
            poi = self._element_to_poi(element, location=location, default_category=default_category)
            if not poi or poi.id in seen:
                continue
            seen.add(poi.id)
            out.append(poi)

        out.sort(key=lambda x: (x.distance_from_user is None, x.distance_from_user or 999999, x.name))
        return out[:20]

    def _search_overpass_with_retry(
        self,
        query_blocks: list[tuple[str, str]],
        location: Location,
        radius_m: int,
    ) -> dict[str, Any] | None:
        # 大半径查询更容易触发公共 Overpass 的 504，先用请求规模更小的版本重试。
        radius_candidates = []
        for value in (radius_m, min(radius_m, 4000), min(radius_m, 2500)):
            if value not in radius_candidates:
                radius_candidates.append(value)

        timeout_candidates = (12, 10, 8)
        limit_candidates = (30, 20, 12)
        errors: list[str] = []

        for overpass_url in self.overpass_urls:
            for radius_candidate, timeout_seconds, result_limit in zip(
                radius_candidates,
                timeout_candidates,
                limit_candidates,
            ):
                body = self._build_overpass_query(
                    query_blocks,
                    location,
                    radius_candidate,
                    timeout_seconds=timeout_seconds,
                    result_limit=result_limit,
                )
                try:
                    with self._client(timeout=timeout_seconds + 4.0) as client:
                        resp = client.post(
                            overpass_url,
                            content=body.encode("utf-8"),
                            headers={"Content-Type": "text/plain; charset=utf-8"},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    if data.get("elements"):
                        if radius_candidate != radius_m:
                            logger.info(
                                "OSM overpass recovered with reduced radius: url=%s original=%sm fallback=%sm",
                                overpass_url,
                                radius_m,
                                radius_candidate,
                            )
                        return data
                except Exception as exc:
                    errors.append(f"{overpass_url} radius={radius_candidate} error={exc}")
                    logger.info(
                        "OSM overpass search failed: url=%s radius=%sm timeout=%ss error=%s",
                        overpass_url,
                        radius_candidate,
                        timeout_seconds,
                        exc,
                    )

        if errors:
            logger.warning("OSM overpass exhausted all retries: %s", " | ".join(errors[:6]))
        return None

    def _search_nominatim_fallback(self, *, tag: str, location: Location, radius_km: float) -> list[POI]:
        queries = self._build_nominatim_queries(tag)
        if not queries:
            return []

        out: list[POI] = []
        seen: set[str] = set()
        viewbox = self._build_viewbox(location, radius_km=max(radius_km, 2.0))
        for query in queries:
            try:
                with self._client(timeout=8.0) as client:
                    resp = client.get(
                        f"{self.nominatim_url}/search",
                        params={
                            "q": query,
                            "format": "jsonv2",
                            "limit": 8,
                            "accept-language": "zh-CN,zh",
                            "addressdetails": 1,
                            "viewbox": viewbox,
                            "bounded": 1,
                        },
                    )
                    resp.raise_for_status()
                    items = resp.json()
            except Exception as exc:
                logger.info("OSM nominatim fallback search failed: query=%s error=%s", query, exc)
                continue

            for item in items:
                poi = self._nominatim_item_to_poi(item, location=location, default_category=self._default_category_for_tag(tag))
                if not poi or poi.id in seen:
                    continue
                seen.add(poi.id)
                out.append(poi)

        out.sort(key=lambda x: (x.distance_from_user is None, x.distance_from_user or 999999, x.name))
        return out[:20]

    def route(self, origin: Location, dest: Location, *, mode: str = "walk") -> RouteLeg:
        profile = {
            "walk": "foot",
            "drive": "driving",
            "metro": "foot",
        }.get(mode, "foot")
        try:
            with self._client(timeout=12.0) as client:
                resp = client.get(
                    f"{self.osrm_url}/route/v1/{profile}/{origin.lng},{origin.lat};{dest.lng},{dest.lat}",
                    params={"overview": "false", "steps": "false"},
                )
                resp.raise_for_status()
                data = resp.json()
            routes = data.get("routes") or []
            if not routes:
                return self._fallback_route(origin, dest, mode)
            route = routes[0]
            return RouteLeg(
                mode="metro" if mode == "metro" else mode,
                minutes=max(1, int(route.get("duration", 0) // 60)),
                distance_km=round(float(route.get("distance", 0)) / 1000, 1),
            )
        except Exception as exc:
            logger.warning("OSM route failed: %s", exc)
            return self._fallback_route(origin, dest, mode)

    def _build_query_blocks(self, tag: str) -> tuple[list[tuple[str, str]], str]:
        tag = tag.strip().lower()
        if any(key in tag for key in ["吃", "餐", "美食", "轻食", "粤菜", "咖啡", "甜品", "奶茶", "火锅"]):
            return [
                ("amenity", "restaurant|cafe|fast_food|food_court|ice_cream|bar|pub"),
            ], "餐饮"
        if any(key in tag for key in ["亲子", "游乐", "儿童", "遛娃"]):
            return [
                ("tourism", "theme_park|zoo|aquarium|museum|attraction"),
                ("leisure", "playground|park|amusement_arcade"),
            ], "休闲娱乐"
        if any(key in tag for key in ["展览", "博物馆", "美术馆", "科技馆"]):
            return [
                ("tourism", "museum|gallery|attraction"),
                ("amenity", "theatre|cinema"),
            ], "休闲娱乐"
        if any(key in tag for key in ["购物", "商场", "超市", "书店"]):
            return [
                ("shop", "mall|supermarket|books|department_store|clothes|convenience"),
            ], "购物"
        if any(key in tag for key in ["休闲", "娱乐", "玩", "朋友", "citywalk", "剧本杀", "密室"]):
            return [
                ("leisure", "park|fitness_centre|sports_centre|amusement_arcade|playground"),
                ("tourism", "museum|gallery|theme_park|attraction"),
                ("amenity", "cinema|theatre|cafe|bar"),
            ], "休闲娱乐"
        return [
            ("amenity", "restaurant|cafe|fast_food|cinema|theatre"),
            ("leisure", "park|playground|fitness_centre"),
            ("tourism", "museum|gallery|attraction|theme_park"),
            ("shop", "mall|supermarket"),
        ], "综合"

    def _build_overpass_query(
        self,
        query_blocks: list[tuple[str, str]],
        location: Location,
        radius_m: int,
        *,
        timeout_seconds: int = 12,
        result_limit: int = 30,
    ) -> str:
        parts: list[str] = []
        for key, regex in query_blocks:
            for obj_type in ("node", "way", "relation"):
                parts.append(
                    f'{obj_type}(around:{radius_m},{location.lat},{location.lng})["{key}"~"{regex}",i];'
                )
        return f"[out:json][timeout:{timeout_seconds}];(" + "".join(parts) + f");out center {result_limit};"

    def _build_nominatim_queries(self, tag: str) -> list[str]:
        t = (tag or "").strip().lower()
        if any(key in t for key in ["吃", "餐", "美食", "轻食", "粤菜", "咖啡", "甜品", "奶茶", "火锅"]):
            return ["restaurant", "cafe", "fast food", "food court"]
        if any(key in t for key in ["亲子", "游乐", "儿童", "遛娃"]):
            return ["playground", "park", "museum", "attraction"]
        if any(key in t for key in ["展览", "博物馆", "美术馆", "科技馆"]):
            return ["museum", "gallery", "attraction"]
        if any(key in t for key in ["购物", "商场", "超市", "书店"]):
            return ["mall", "supermarket", "books"]
        if any(key in t for key in ["休闲", "娱乐", "玩", "朋友", "citywalk", "剧本杀", "密室"]):
            return ["park", "museum", "cinema", "cafe"]
        return ["restaurant", "park", "museum", "mall"]

    def _default_category_for_tag(self, tag: str) -> str:
        query_blocks, default_category = self._build_query_blocks(tag or "")
        _ = query_blocks
        return default_category

    def _build_viewbox(self, location: Location, *, radius_km: float) -> str:
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * max(0.3, math.cos(math.radians(location.lat))))
        left = location.lng - lng_delta
        right = location.lng + lng_delta
        top = location.lat + lat_delta
        bottom = location.lat - lat_delta
        return f"{left},{top},{right},{bottom}"

    def _build_overpass_urls(self, primary_url: str) -> list[str]:
        candidates = [primary_url, *self.DEFAULT_OVERPASS_URLS]
        urls: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            url = candidate.strip()
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
        return urls

    def _element_to_poi(
        self,
        element: dict[str, Any],
        *,
        location: Location,
        default_category: str,
    ) -> POI | None:
        tags = element.get("tags") or {}
        name = tags.get("name") or tags.get("brand") or tags.get("official_name")
        if not name:
            return None

        lat = element.get("lat")
        lng = element.get("lon")
        if lat is None or lng is None:
            center = element.get("center") or {}
            lat = center.get("lat")
            lng = center.get("lon")
        if lat is None or lng is None:
            return None

        lat = float(lat)
        lng = float(lng)
        poi_location = Location(lat=lat, lng=lng, label=name)
        category = self._infer_category(tags, default=default_category)
        distance = round(self._haversine_km(location.lat, location.lng, lat, lng), 1)

        return POI(
            id=f"osm:{element.get('type', 'node')}:{element.get('id')}",
            name=name,
            category=category,
            location=poi_location,
            lat=lat,
            lng=lng,
            tags=self._extract_tags(tags),
            rating=0.0,
            price=None,
            address=self._build_address(tags),
            open_hours=tags.get("opening_hours"),
            tel=tags.get("phone") or tags.get("contact:phone"),
            business_area=tags.get("addr:suburb") or tags.get("addr:district"),
            distance_from_user=distance,
        )

    def _nominatim_item_to_poi(
        self,
        item: dict[str, Any],
        *,
        location: Location,
        default_category: str,
    ) -> POI | None:
        name = item.get("name") or item.get("display_name")
        lat = item.get("lat")
        lng = item.get("lon")
        if not name or lat is None or lng is None:
            return None

        lat_f = float(lat)
        lng_f = float(lng)
        address = item.get("display_name")
        kind = str(item.get("type", ""))
        category = self._infer_category({"tourism": kind, "amenity": kind, "shop": kind, "leisure": kind}, default=default_category)
        distance = round(self._haversine_km(location.lat, location.lng, lat_f, lng_f), 1)
        return POI(
            id=f"nominatim:{item.get('place_id')}",
            name=str(name).split(",")[0].strip(),
            category=category,
            location=Location(lat=lat_f, lng=lng_f, label=str(name)),
            lat=lat_f,
            lng=lng_f,
            tags=[kind] if kind else [],
            rating=0.0,
            price=None,
            address=address,
            open_hours=None,
            tel=None,
            business_area=None,
            distance_from_user=distance,
        )

    def _infer_category(self, tags: dict[str, Any], *, default: str) -> str:
        amenity = str(tags.get("amenity", ""))
        leisure = str(tags.get("leisure", ""))
        tourism = str(tags.get("tourism", ""))
        shop = str(tags.get("shop", ""))
        if amenity in {"restaurant", "cafe", "fast_food", "food_court", "bar", "pub", "ice_cream"}:
            return "餐饮"
        if shop:
            return "购物"
        if leisure or tourism or amenity in {"cinema", "theatre"}:
            return "休闲娱乐"
        return default

    def _extract_tags(self, tags: dict[str, Any]) -> list[str]:
        keys = ["amenity", "leisure", "tourism", "shop", "cuisine"]
        return [str(tags[k]) for k in keys if tags.get(k)]

    def _build_address(self, tags: dict[str, Any]) -> str | None:
        if tags.get("addr:full"):
            return str(tags["addr:full"])
        parts = [
            tags.get("addr:city"),
            tags.get("addr:district"),
            tags.get("addr:suburb"),
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
        ]
        text = " ".join([str(x) for x in parts if x]).strip()
        return text or None

    def _fallback_route(self, origin: Location, dest: Location, mode: str) -> RouteLeg:
        dist_km = self._haversine_km(origin.lat, origin.lng, dest.lat, dest.lng)
        speed = 4.5 if mode == "walk" else 28.0
        minutes = max(1, int(dist_km / speed * 60))
        return RouteLeg(mode="metro" if mode == "metro" else mode, distance_km=round(dist_km, 1), minutes=minutes)

    def _haversine_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
        )
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))
