from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEITUAN_AGENT_", extra="ignore")

    env: str = "dev"
    data_dir: str = "backend/data"

    memory_backend: str = "sqlite"
    sqlite_path: str = "backend/data/memory.sqlite3"

    llm_provider: str = "none"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    asr_provider: str = "none"
    asr_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    asr_model: str = "qwen3-asr-flash"

    map_provider: str = "auto"
    amap_api_key: str = ""
    osm_user_agent: str = "meituan-competition-agent/1.0"
    osm_nominatim_url: str = "https://nominatim.openstreetmap.org"
    osm_overpass_url: str = "https://overpass-api.de/api/interpreter"
    osm_osrm_url: str = "https://router.project-osrm.org"

    dashscope_app_id: str = ""

    max_queue_minutes: int = 60


def load_settings() -> Settings:
    s = Settings()
    root = Path(__file__).resolve().parents[3]
    data_dir = Path(s.data_dir)
    sqlite_path = Path(s.sqlite_path)
    if not data_dir.is_absolute():
        s.data_dir = str((root / data_dir).resolve())
    if not sqlite_path.is_absolute():
        s.sqlite_path = str((root / sqlite_path).resolve())
    return s

