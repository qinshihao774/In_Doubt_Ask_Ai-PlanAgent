from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

from meituan_agent.agents.manager_agent import PIPELINE_STAGES
from meituan_agent.asr.qwen_asr import QwenASRClient
from meituan_agent.container import Container
from meituan_agent.domain.models import ChatMessage, Location, SessionState
from meituan_agent.services.session_service import SessionService


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    user_location: Location | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    state: dict[str, Any]


class PlaceOrderRequest(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    user_notes: str | None = None


class InitRequest(BaseModel):
    session_id: str | None = None


class InitResponse(BaseModel):
    session_id: str
    state: dict[str, Any]


def create_app() -> FastAPI:
    container = Container()
    svc = SessionService(container.memory, container.manager)
    app = FastAPI(title="Meituan Competition Agent", version="0.1.0")

    dist_dir = Path(__file__).resolve().parents[4] / "webui" / "dist"
    assets_dir = dist_dir / "assets"
    if dist_dir.exists() and assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        app.mount("/ui/assets", StaticFiles(directory=str(assets_dir)), name="ui-assets")

        favicon = dist_dir / "favicon.svg"
        if favicon.exists():
            @app.get("/favicon.svg", include_in_schema=False)
            def favicon_svg():
                return FileResponse(str(favicon))

        @app.get("/ui", include_in_schema=False)
        @app.get("/ui/{path:path}", include_in_schema=False)
        def ui(path: str = ""):
            target = (dist_dir / path).resolve()
            if path and target.exists() and target.is_file() and str(target).startswith(str(dist_dir.resolve())):
                return FileResponse(str(target))
            return FileResponse(str(dist_dir / "index.html"))

    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "ok": True,
            "message": "Backend is running. Use /health, /docs, /init, /chat, /chat/stream.",
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    @app.post("/init", response_model=InitResponse)
    def init(req: InitRequest) -> InitResponse:
        state = svc.ensure_session(req.session_id)
        return InitResponse(session_id=state.session_id, state=state.model_dump())

    @app.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        state, reply = svc.chat(
            session_id=req.session_id,
            message=req.message,
            bootstrap_location=req.user_location,
        )
        return ChatResponse(session_id=state.session_id, reply=reply, state=state.model_dump())

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest):
        state = svc.ensure_session(req.session_id)
        if req.user_location and not state.scratch.get("location_hint"):
            state.location = req.user_location
            state.scratch["bootstrap_location"] = req.user_location.model_dump()
        svc._memory.append_message(state.session_id, ChatMessage(role="user", content=req.message))

        async def event_gen():
            nonlocal_state = state
            yield _sse({"type": "session", "session_id": nonlocal_state.session_id})
            yield _sse({"type": "pipeline_config", "stages": PIPELINE_STAGES})

            gen = container.manager.step_stream(nonlocal_state, req.message, use_llm=True)
            base_reply = ""

            while True:
                try:
                    event = next(gen)
                except StopIteration as e:
                    nonlocal_state, base_reply = e.value
                    break

                if isinstance(event, dict) and event.get("type") == "pipeline_stage":
                    yield _sse(event)
                    await asyncio.sleep(0)

            svc._memory.put_state(nonlocal_state)

            final_parts: list[str] = []
            for chunk in _chunk_text(base_reply, 24):
                final_parts.append(chunk)
                yield _sse({"type": "delta", "content": chunk})
                await asyncio.sleep(0)

            final = "".join(final_parts).strip() or base_reply
            svc.append_assistant(nonlocal_state.session_id, final)
            yield _sse({"type": "done"})

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    @app.get("/state/{session_id}", response_model=dict[str, Any])
    def get_state(session_id: str) -> dict[str, Any]:
        state = svc.get_state(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="session_not_found")
        return state.model_dump()

    @app.get("/messages/{session_id}", response_model=list[ChatMessage])
    def get_messages(session_id: str, limit: int = 50) -> list[ChatMessage]:
        return svc.get_messages(session_id, limit=limit)

    @app.post("/asr/transcribe", response_model=dict[str, Any])
    async def asr_transcribe(file: UploadFile = File(...), language: str | None = None) -> dict[str, Any]:
        if (container.settings.asr_provider or "none").lower() != "qwen":
            raise HTTPException(status_code=400, detail="asr_provider_disabled")
        api_key = os.getenv("DASHSCOPE_API_KEY") or ""
        if not api_key:
            raise HTTPException(status_code=400, detail="missing_dashscope_api_key")
        if not (file.content_type or "").startswith("audio/"):
            raise HTTPException(status_code=400, detail="unsupported_content_type")
        audio_bytes = await file.read()
        if len(audio_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="audio_too_large")

        client = QwenASRClient(base_url=container.settings.asr_base_url, api_key=api_key, model=container.settings.asr_model)
        try:
            text = client.transcribe_bytes(audio_bytes, mime_type=file.content_type or "audio/wav", language=language)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        return {"text": text}

    return app


app = create_app()

def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int) -> list[str]:
    out: list[str] = []
    s = text or ""
    for i in range(0, len(s), size):
        out.append(s[i : i + size])
    return out
