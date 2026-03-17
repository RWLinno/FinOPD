"""
VLM (Vision-Language Model) client for chart analysis.
Sends rendered chart images to a VLM and parses structured responses.
Includes retry logic, cost tracking, and graceful degradation.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VLMClient:
    """
    Client for querying VLMs (GPT-4o, Qwen-VL, etc.) with chart images.
    Uses OpenAI-compatible API format with retry and cost tracking.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        config = config or {}
        self.backend = config.get("backend", "openai")
        self.model = config.get("model", "gpt-4o")
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 2048)
        self.timeout = config.get("timeout", 60)
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
        self.max_retries = config.get("max_retries", 3)
        self.retry_base_delay = config.get("retry_base_delay", 2.0)

        self._client = None
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0
        self._failed_calls = 0

    def _get_client(self):
        if self._client is None:
            try:
                import openai
                kwargs: Dict[str, Any] = {"timeout": self.timeout}
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = openai.OpenAI(**kwargs)
            except ImportError:
                raise ImportError("openai package required for VLM client")
        return self._client

    @property
    def usage_summary(self) -> Dict[str, Any]:
        return {
            "total_calls": self._total_calls,
            "failed_calls": self._failed_calls,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
        }

    async def analyze_chart(
        self,
        image_path: str,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Send a chart image to the VLM for analysis."""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._analyze_sync, image_path, system_prompt, user_prompt
        )

    def _analyze_sync(
        self, image_path: str, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        if not Path(image_path).exists():
            logger.error(f"Chart image not found: {image_path}")
            return {"error": f"Image not found: {image_path}", "raw": ""}

        image_b64 = self._encode_image(image_path)

        try:
            client = self._get_client()
        except (ImportError, Exception) as e:
            logger.error(f"Cannot initialise VLM client: {e}")
            self._failed_calls += 1
            return {"error": str(e), "raw": ""}

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._total_calls += 1
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                if response.usage:
                    self._total_prompt_tokens += response.usage.prompt_tokens
                    self._total_completion_tokens += response.usage.completion_tokens

                raw = response.choices[0].message.content or ""
                return self._parse_response(raw)

            except Exception as e:
                last_err = e
                delay = self.retry_base_delay * (2 ** (attempt - 1))
                logger.warning(
                    f"VLM call attempt {attempt}/{self.max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                if attempt < self.max_retries:
                    time.sleep(delay)

        self._failed_calls += 1
        logger.error(f"VLM call failed after {self.max_retries} attempts: {last_err}")
        return {"error": str(last_err), "raw": ""}

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _parse_response(raw: str) -> Dict[str, Any]:
        """Attempt to parse JSON from VLM response, handling markdown fences."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": raw, "parse_error": True}
