from __future__ import annotations

import base64
from typing import Any

import httpx


class QwenASRClient:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def transcribe_bytes(self, audio_bytes: bytes, *, mime_type: str, language: str | None = None) -> str:
        data_b64 = base64.b64encode(audio_bytes).decode("ascii")
        data_uri = f"data:{mime_type};base64,{data_b64}"

        extra_body: dict[str, Any] = {"asr_options": {"enable_itn": False}}
        if language:
            extra_body["asr_options"]["language"] = language

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "input_audio", "input_audio": {"data": data_uri}}],
                }
            ],
            "stream": False,
            "extra_body": extra_body,
        }

        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=60) as client:
            r = client.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            resp = r.json()

        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError("asr_empty_choices")
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("asr_empty_content")
        return content.strip()

