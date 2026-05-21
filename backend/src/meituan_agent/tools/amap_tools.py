from __future__ import annotations

import httpx
import logging
from typing import Any

from meituan_agent.domain.models import Location, POI, RouteLeg
from meituan_agent.tools.base import MapTool, POISearchTool

logger = logging.getLogger(__name__)


class AmapTools(POISearchTool, MapTool):
    """
    基于高德地图 Web 服务 API 的真实实现。
    提供：地理编码、IP 定位、周边搜索 (POI)、步行/驾车/公交路线规划。

    不提供（高德 API 无此能力）：菜单、桌位排队、下单。
    这些功能由 Container 注入专门的 NoOp 实现，需对接美团/饿了么开放平台。
    """

    BASE_URL = "https://restapi.amap.com/v3"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        # 高德 API 分类编码映射（覆盖餐饮、休闲、亲子、购物等主要场景）
        self.category_map = {
            # ===== 餐饮 =====
            "餐饮": "050000", "美食": "050000", "中餐": "050100", "火锅": "050101",
            "烧烤": "050102", "海鲜": "050103", "西餐": "050200", "日料": "050300",
            "韩料": "050400", "东南亚菜": "050500", "小吃": "050600", "快餐": "050700",
            "咖啡": "050800", "甜品": "050900", "茶饮": "051000", "自助餐": "051100",
            "酒吧": "051200", "轻食": "050000",
            # ===== 购物 =====
            "商场": "060100", "超市": "060200", "书店": "060300", "花店": "060400",
            "购物": "060000", "商圈": "060100",
            # ===== 休闲娱乐 =====
            "休闲": "080000", "娱乐": "080000",
            "KTV": "080100", "酒吧": "080200", "咖啡厅": "080201",
            "游乐园": "080300", "水上乐园": "080301", "主题乐园": "080302",
            "展览": "080400", "博物馆": "080401", "美术馆": "080402", "科技馆": "080403",
            "电影院": "080500",
            "体育": "080600", "健身房": "080601", "游泳馆": "080602",
            "密室逃脱": "080700", "剧本杀": "080701",
            "动物园": "090100", "植物园": "090200", "水族馆": "090300",
            "公园": "110100", "城市广场": "110200",
            # ===== 亲子 =====
            "亲子": "080000", "儿童乐园": "080303", "亲子活动": "080304",
            "游乐": "080300",
            # ===== 景点/旅游 =====
            "景点": "110000", "风景名胜": "110000", "风景": "110000",
            "旅游": "110000", "观光": "110000",
        }
    
    def reverse_geocode(self, lat: float, lng: float) -> str:
        params = {
            "key": self.api_key,
            "location": f"{lng},{lat}",
        }
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{self.BASE_URL}/geocode/regeo", params=params)
                r.raise_for_status()
                data = r.json()
            if data.get("status") == "1" and data.get("regeocode"):
                return data["regeocode"].get("formatted_address", f"坐标({lat:.4f}, {lng:.4f})")
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Amap reverse geocode failed: %s", exc)
        return f"坐标({lat:.4f}, {lng:.4f})"

    def geocode(self, address: str, city: str | None = None) -> Location | None:
        """地址 → 坐标（地理编码）"""
        params = {
            "key": self.api_key,
            "address": address,
        }
        if city:
            params["city"] = city
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{self.BASE_URL}/geocode/geo", params=params)
                r.raise_for_status()
                data = r.json()
            if data.get("status") != "1" or not data.get("geocodes"):
                logger.warning(f"地理编码失败: {data}")
                return None
            loc_str = data["geocodes"][0].get("location", "")
            if "," not in loc_str:
                return None
            lng_str, lat_str = loc_str.split(",")
            return Location(
                lat=float(lat_str), lng=float(lng_str),
                label=data["geocodes"][0].get("formatted_address", address),
            )
        except Exception as e:
            logger.error(f"地理编码 API 出错: {e}")
            return None

    def ip_location(self) -> Location | None:
        """IP 粗略定位"""
        params = {"key": self.api_key}
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{self.BASE_URL}/ip", params=params)
                r.raise_for_status()
                data = r.json()
            if data.get("status") != "1":
                logger.warning(f"IP 定位失败: {data}")
                return None
            rect = data.get("rectangle") or ""
            if not rect:
                return None
            # rectangle 格式: "lng1,lat1;lng2,lat2" → 取中心点
            parts = rect.split(";")
            if len(parts) != 2:
                return None
            c1 = parts[0].split(",")
            c2 = parts[1].split(",")
            if len(c1) != 2 or len(c2) != 2:
                return None
            center_lng = (float(c1[0]) + float(c2[0])) / 2
            center_lat = (float(c1[1]) + float(c2[1])) / 2
            label = data.get("city", "") or data.get("province", "") or "IP 定位"
            return Location(lat=center_lat, lng=center_lng, label=label)
        except Exception as e:
            logger.error(f"IP 定位 API 出错: {e}")
            return None

    def search_poi(self, *, tag: str | None, location: Location | None, radius_km: float = 3.0) -> list[POI]:
        """调用高德地图周边搜索 API"""
        if not location:
            # 默认北京天安门
            location = Location(lat=39.908, lng=116.397)
            
        params = {
            "key": self.api_key,
            "location": f"{location.lng},{location.lat}",
            "radius": int(radius_km * 1000),
            "sortrule": "distance",
            "offset": 10,
            "page": 1,
            "extensions": "all"
        }
        
        # 处理搜索关键词
        tag_norm = (tag or "").strip()
        if tag_norm:
            params["keywords"] = tag_norm
            # 尝试映射到高德分类编码：精确匹配优先，再尝试包含匹配
            matched = False
            for key, code in self.category_map.items():
                if tag_norm == key or key in tag_norm:
                    params["types"] = code
                    matched = True
                    break
            if not matched:
                # 没有匹配的分类码时，不传 types，让高德用 keywords 自由搜索
                pass
        else:
            params["types"] = "050000|080000|110000"  # 默认搜餐饮、休闲、景点
            
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{self.BASE_URL}/place/around", params=params)
                r.raise_for_status()
                data = r.json()
                
            if data.get("status") != "1":
                logger.warning(f"高德 POI 搜索 API 返回错误: {data}")
                return []
            if not data.get("pois"):
                logger.info(f"高德 POI 搜索无结果 (keywords={tag_norm}, types={params.get('types','')})")
                return []
                
            out: list[POI] = []
            for item in data["pois"]:
                # 解析高德返回的数据为 POI 模型
                loc_str = item.get("location", "")
                if not loc_str or "," not in loc_str:
                    continue
                lng_str, lat_str = loc_str.split(",")
                
                # 尝试解析评分和人均消费（高德 API 的 biz_ext 字段中有时会包含）
                rating = None
                price = None
                biz_ext = item.get("biz_ext", {})
                if isinstance(biz_ext, dict):
                    if biz_ext.get("rating"):
                        try:
                            rating = float(biz_ext["rating"])
                        except (ValueError, TypeError):
                            pass
                    if biz_ext.get("cost"):
                        try:
                            price = float(biz_ext["cost"])
                        except (ValueError, TypeError):
                            pass
                
                # 从 photos 中提取图片
                photos = item.get("photos", [])
                image_url = None
                if photos and len(photos) > 0 and isinstance(photos[0], dict):
                    image_url = photos[0].get("url")
                
                loc = Location(lat=float(lat_str), lng=float(lng_str), label=item.get("name", ""))
                # 计算离搜索中心距离
                dist = None
                try:
                    dlng = loc.lng - location.lng
                    dlat = loc.lat - location.lat
                    dist = round(((dlat * 111) ** 2 + (dlng * 111 * 0.85) ** 2) ** 0.5, 1)
                except Exception:
                    pass

                poi = POI(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    category=item.get("type", "其他").split(";")[0],
                    location=loc,
                    lat=loc.lat,
                    lng=loc.lng,
                    rating=rating,
                    price=price,
                    tags=item.get("type", "").split(";"),
                    address=item.get("address", ""),
                    tel=item.get("tel") or None,
                    business_area=(item.get("biz_ext") or {}).get("business_area") or item.get("business_area"),
                    image_url=image_url,
                    distance_from_user=dist,
                )
                out.append(poi)
                
            return out
            
        except Exception as e:
            logger.error(f"调用高德地图搜索 API 出错: {e}")
            return []

    def route(self, origin: Location, dest: Location, *, mode: str = "walk") -> RouteLeg:
        """调用高德地图路径规划 API"""
        # 高德 API endpoint 映射
        endpoints = {
            "walk": "/direction/walking",
            "drive": "/direction/driving",
            "transit": "/direction/transit/integrated"
        }
        
        endpoint = endpoints.get(mode, endpoints["walk"])
        
        params = {
            "key": self.api_key,
            "origin": f"{origin.lng},{origin.lat}",
            "destination": f"{dest.lng},{dest.lat}",
        }
        
        # 公交规划需要城市参数，默认北京
        if mode == "transit":
            params["city"] = "010" 
            
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{self.BASE_URL}{endpoint}", params=params)
                r.raise_for_status()
                data = r.json()
                
            if data.get("status") != "1" or not data.get("route"):
                logger.warning(f"高德路径规划失败: {data}")
                # 失败时降级到简单计算
                return self._fallback_route(origin, dest, mode)
                
            route_data = data["route"]
            paths = route_data.get("paths", [])
            transits = route_data.get("transits", [])
            
            # 提取距离和时间
            distance_m = 0
            duration_s = 0
            
            if mode == "transit" and transits:
                distance_m = int(transits[0].get("distance", 0))
                duration_s = int(transits[0].get("duration", 0))
            elif paths:
                distance_m = int(paths[0].get("distance", 0))
                duration_s = int(paths[0].get("duration", 0))
            else:
                return self._fallback_route(origin, dest, mode)
                
            return RouteLeg(
                mode=mode,
                distance_km=round(distance_m / 1000, 1),
                minutes=max(1, duration_s // 60)
            )
            
        except Exception as e:
            logger.error(f"调用高德地图路径规划 API 出错: {e}")
            return self._fallback_route(origin, dest, mode)
            
    def _fallback_route(self, origin: Location, dest: Location, mode: str) -> RouteLeg:
        """当 API 调用失败时基于经纬度粗略估算"""
        dist_km = ((origin.lat - dest.lat) ** 2 + (origin.lng - dest.lng) ** 2) ** 0.5 * 111
        if mode == "walk":
            mins = int(dist_km / 4.0 * 60)
        else:
            mins = int(dist_km / 30.0 * 60)
        return RouteLeg(mode=mode, distance_km=round(dist_km, 1), minutes=max(1, mins))
