from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from meituan_agent.agents.execution_agent import ExecutionAgent
from meituan_agent.agents.food_agent import FoodAgent
from meituan_agent.agents.semantic_agent import SemanticAgent
from meituan_agent.agents.leisure_agent import LeisureAgent
from meituan_agent.agents.manager_agent import ManagerAgent
from meituan_agent.agents.map_agent import MapAgent
from meituan_agent.config import load_settings
from meituan_agent.llm.openai_compat import OpenAICompatClient
from meituan_agent.memory.factory import build_memory_store
from meituan_agent.planning.planner import FallbackPlanner, HeuristicPlanner, LLMPlanner
from meituan_agent.services.weather_service import WeatherService
from meituan_agent.tools.amap_tools import AmapTools
from meituan_agent.tools.base import RPAExecutor, AvailabilityTool, MenuInfoTool, OrderTool
from meituan_agent.tools.mock_map import MockMapTool
from meituan_agent.tools.mock_meituan import MockMeituanTools
from meituan_agent.tools.osm_tools import OpenStreetMapTools


class SimRPA(RPAExecutor):
    """模拟 RPA 执行 — 返回成功信号"""

    def execute(self, *, action: str, payload: dict) -> dict:
        return {"ok": True, "action": action, "message": f"RPA 操作已完成：{action}"}


class SimMenu(MenuInfoTool):
    """模拟菜单查询 — 返回示例菜单数据"""

    def get_menu_info(self, poi_id: str, *, fat_content: bool = False) -> dict:
        items = [
            {"name": "招牌推荐菜", "price": 68},
            {"name": "时令蔬菜", "price": 32},
            {"name": "特色饮品", "price": 22},
        ]
        if fat_content:
            items = [{"name": "轻食沙拉", "price": 42}, {"name": "低卡鸡胸", "price": 38}]
        return {"ok": True, "menu": items, "poi_id": poi_id}


class SimAvailability(AvailabilityTool):
    """模拟排队检查 — 返回可订状态"""

    def check_table_availability(self, poi_id: str, *, size: int) -> dict:
        return {"ok": True, "queue_minutes": 5, "table_available": True, "party_size": size}


class SimOrder(OrderTool):
    """模拟下单 — 返回已订信号"""

    def place_order(self, poi_id: str, *, items: list[dict], user_notes: str | None = None) -> dict:
        return {
            "ok": True,
            "order_id": f"ord_{poi_id[:8]}_{hash(str(items)) % 10000:04d}",
            "status": "已下单",
            "items": items,
            "message": "订单已提交，餐厅已确认",
        }




class Container:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[3]
        dotenv_path = root / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=True)
        else:
            load_dotenv(override=True)
        self.settings = load_settings()
        data_dir = Path(self.settings.data_dir)
        if not data_dir.is_absolute():
            data_dir = root / data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        sqlite_path = Path(self.settings.sqlite_path)
        if not sqlite_path.is_absolute():
            sqlite_path = root / sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.data_dir = str(data_dir)
        self.settings.sqlite_path = str(sqlite_path)

        self.memory = build_memory_store(self.settings)

        # ===== 地图与 POI 数据源：高德 -> OSM -> Mock =====
        provider = (self.settings.map_provider or "auto").strip().lower()
        amap_key = (self.settings.amap_api_key or "").strip()
        if provider == "amap":
            if not amap_key:
                raise RuntimeError("map_provider=amap 时必须配置 MEITUAN_AGENT_AMAP_API_KEY")
            tools = AmapTools(api_key=amap_key)
            self.meituan = tools
            self.map_tool = tools
        elif provider == "mock":
            self.meituan = MockMeituanTools(self.settings.data_dir)
            self.map_tool = MockMapTool()
        elif provider == "osm" or (provider == "auto" and not amap_key):
            tools = OpenStreetMapTools(
                user_agent=self.settings.osm_user_agent,
                nominatim_url=self.settings.osm_nominatim_url,
                overpass_url=self.settings.osm_overpass_url,
                osrm_url=self.settings.osm_osrm_url,
            )
            self.meituan = tools
            self.map_tool = tools
        else:
            tools = AmapTools(api_key=amap_key)
            self.meituan = tools
            self.map_tool = tools

        # ===== RPA / 菜单 / 排队 / 下单：无真实 API 时模拟成功 =====
        self.rpa = SimRPA()
        self.menu_tool = SimMenu()
        self.availability_tool = SimAvailability()
        self.order_tool = SimOrder()

        # ===== LLM =====
        llm = None
        if (self.settings.llm_provider or "none").lower() != "none" and (self.settings.openai_api_key or "").strip():
            llm = OpenAICompatClient(
                base_url=self.settings.openai_base_url,
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
            )
        self.llm = llm

        self.weather_service = WeatherService()

        # ===== Agent 初始化 =====
        dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "")
        dashscope_app_id = (self.settings.dashscope_app_id or "").strip()
        if dashscope_key and dashscope_app_id:
            self.semantic_agent = SemanticAgent(dashscope_api_key=dashscope_key, dashscope_app_id=dashscope_app_id)
        elif llm:
            self.semantic_agent = SemanticAgent(llm)
        else:
            self.semantic_agent = None
        self.food_agent = FoodAgent(self.meituan)
        self.leisure_agent = LeisureAgent(self.meituan)
        self.map_agent = MapAgent(self.map_tool, weather=self.weather_service)
        self.execution_agent = ExecutionAgent(
            availability=self.availability_tool,
            menu=self.menu_tool,
            order=self.order_tool,
            rpa=self.rpa,
            max_queue_minutes=self.settings.max_queue_minutes,
        )

        # ===== Planner =====
        heuristic = HeuristicPlanner(self.map_tool)
        planner = heuristic
        if llm:
            planner = FallbackPlanner(LLMPlanner(llm=llm, poi_search=self.meituan, map_tool=self.map_tool), heuristic)

        self.manager = ManagerAgent(
            semantic=self.semantic_agent,
            food=self.food_agent,
            leisure=self.leisure_agent,
            map_agent=self.map_agent,
            execution=self.execution_agent,
            planner=planner,
            llm=llm,
        )

        # ===== 计时切面织入 =====
        from meituan_agent.timing_aspect import install_timing_aspect
        install_timing_aspect(self)
