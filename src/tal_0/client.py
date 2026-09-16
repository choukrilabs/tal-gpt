"""Zero-dependency Gemini HTTP client with explicit local fallback."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Optional


class GeminiClientError(RuntimeError):
    """Raised when the Gemini API request cannot be completed."""


class GeminiLLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3-flash-preview",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self.model = model
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            return "TAL-0 deterministic fallback: no Gemini API call was made."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return self._extract_text(payload)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in (408, 429, 500, 502, 503, 504) or attempt >= self.max_retries:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, GeminiClientError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
            time.sleep(min(0.5 * (2 ** attempt), 8.0))

        raise GeminiClientError(f"Gemini request failed after retries: {last_error}")

    @staticmethod
    def _extract_text(payload: dict) -> str:
        candidates = payload.get("candidates") or []
        if not candidates:
            raise GeminiClientError("Gemini response contains no candidates")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text:
            raise GeminiClientError("Gemini response contains no text part")
        return text
