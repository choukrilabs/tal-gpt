"""Gemini transport adapter with retry/backoff and deterministic TAL-1 fallback."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional


class GeminiLLMClient:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3-flash-preview", max_retries: int = 3, base_delay: float = 0.5) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.max_retries = max(0, max_retries)
        self.base_delay = max(0.0, base_delay)

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            return "TAL-1 fallback: deterministic response for prompt={}".format(prompt[:80])
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key}, method="POST")
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return payload["candidates"][0]["content"]["parts"][0]["text"]
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
                if attempt >= self.max_retries:
                    return f"TAL-1 fallback after transport failure: {exc}"
                time.sleep(self.base_delay * (2 ** attempt))
        raise RuntimeError("unreachable")
