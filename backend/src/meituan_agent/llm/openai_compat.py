from __future__ import annotations

import httpx


class OpenAICompatClient:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def chat(self, *, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=60) as client:
            r = client.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            resp = r.json()
        choices = resp.get("choices") or []
        if not choices:
            raise RuntimeError("llm_empty_choices")
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("llm_empty_content")
        return content.strip()

    def chat_stream(self, *, system: str, user: str):
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", f"{self._base_url}/chat/completions", json=payload, headers=headers) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        obj = httpx.Response(200, content=data).json()
                    except Exception:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if isinstance(delta, str) and delta:
                        yield delta
