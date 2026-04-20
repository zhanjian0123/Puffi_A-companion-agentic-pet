import json
from typing import Any
import httpx

from config import settings


class DashScopeChatModel:
    @property
    def is_configured(self) -> bool:
        return bool(settings.dashscope_api_key)

    async def chat(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
    ) -> str:
        payload = {
            "model": settings.dashscope_model,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "tools": tools or None,
        }
        headers = {
            "Authorization": f"Bearer {settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.dashscope_base_url}/chat/completions",
                headers=headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
