"""VLM clients and routing for chart analysis."""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VLMClient:
    """Single backend VLM client using OpenAI-compatible API."""

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
            except ImportError as exc:
                raise ImportError("openai package required for VLM client") from exc
        return self._client

    @property
    def usage_summary(self) -> Dict[str, Any]:
        return {
            "model": self.model,
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
        agent_name: Optional[str] = None,
        task: Optional[str] = None,
    ) -> Dict[str, Any]:
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(None, self._analyze_sync, image_path, system_prompt, user_prompt)

    def _analyze_sync(self, image_path: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not Path(image_path).exists():
            return {"error": f"Image not found: {image_path}", "raw": ""}

        image_b64 = self._encode_image(image_path)
        try:
            client = self._get_client()
        except Exception as exc:
            self._failed_calls += 1
            return {"error": str(exc), "raw": ""}

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "high"}},
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
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_base_delay * (2 ** (attempt - 1)))

        self._failed_calls += 1
        return {"error": str(last_err), "raw": ""}

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _parse_response(raw: str) -> Dict[str, Any]:
        text = raw.strip()
        import re
        # Extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1).strip()
        else:
            brace_start = text.find('{')
            brace_end = text.rfind('}')
            if brace_start != -1 and brace_end != -1:
                text = text[brace_start:brace_end + 1]
        # Remove // comments that VLMs sometimes add
        text = re.sub(r'//[^\n]*', '', text)
        # Remove trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": raw, "parse_error": True}


class VLMRouter:
    """Route chart analysis requests across multiple VLM backends/models."""

    def __init__(self, config: Dict[str, Any] | None = None):
        config = config or {}
        self.default_client = VLMClient(config)
        self.routes = config.get("routes", []) or []
        self._clients: List[Dict[str, Any]] = []
        for route in self.routes:
            client_cfg = dict(config)
            client_cfg.update(route)
            self._clients.append(
                {
                    "name": route.get("name", route.get("model", "route")),
                    "agent_names": set(route.get("agent_names", [])),
                    "tasks": set(route.get("tasks", [])),
                    "client": VLMClient(client_cfg),
                }
            )

    def _select_client(self, agent_name: Optional[str], task: Optional[str]) -> VLMClient:
        for route in self._clients:
            if agent_name and agent_name in route["agent_names"]:
                return route["client"]
            if task and task in route["tasks"]:
                return route["client"]
        return self.default_client

    async def analyze_chart(
        self,
        image_path: str,
        system_prompt: str,
        user_prompt: str,
        agent_name: Optional[str] = None,
        task: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = self._select_client(agent_name=agent_name, task=task)
        return await client.analyze_chart(
            image_path=image_path,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            agent_name=agent_name,
            task=task,
        )

    @property
    def usage_summary(self) -> Dict[str, Any]:
        data = {"default": self.default_client.usage_summary, "routes": {}}
        for route in self._clients:
            data["routes"][route["name"]] = route["client"].usage_summary
        return data
