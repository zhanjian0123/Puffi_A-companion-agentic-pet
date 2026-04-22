from __future__ import annotations

import json

from config import settings
from schemas import ChatRequest, ChatResponse, HealthResponse, HistoryResponse
from session_store import AgentSessionStore

try:
    from agents import Agent, Runner, set_default_openai_client
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - optional dependency
    Agent = None
    Runner = None
    set_default_openai_client = None
    AsyncOpenAI = None


SYSTEM_PROMPT = """你是 AI Pet 的桌面宠物助手。
保持回复简洁、自然、友好，优先直接帮用户完成事情。"""


class AgentService:
    def __init__(self) -> None:
        self._session_store = AgentSessionStore(
            session_id=settings.session_id,
            db_path=settings.session_db_path,
            context_limit=settings.session_context_limit,
        )
        self._configure_client()
        self._agent = self._build_agent() if self.is_available else None

    @property
    def sdk_installed(self) -> bool:
        return (
            Agent is not None
            and Runner is not None
            and set_default_openai_client is not None
            and AsyncOpenAI is not None
        )

    @property
    def api_key_configured(self) -> bool:
        return bool(settings.openai_api_key)

    @property
    def is_available(self) -> bool:
        return self.sdk_installed and self.api_key_configured

    def health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            runtime="openai-agents-sdk",
            configured=self.is_available,
            sdk_installed=self.sdk_installed,
            api_key_configured=self.api_key_configured,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    async def history(self, limit: int) -> HistoryResponse:
        messages = await self._session_store.get_recent_messages(limit)
        return HistoryResponse(messages=messages)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not self.sdk_installed:
            return ChatResponse(
                response=(
                    "当前 Python 环境没有可用的 OpenAI Agents SDK。"
                    "请确认你是在项目的 .venv 中安装了 `openai-agents`。"
                )
            )

        if not self.api_key_configured:
            return ChatResponse(response="还没有检测到 OPENAI_API_KEY，请先在 .env 中补齐后再试。")

        if self._agent is None or Runner is None:
            return ChatResponse(response="Agent 初始化失败，请检查模型和 base URL 配置。")

        result = await Runner.run(
            self._agent,
            request.message,
            session=self._session_store.session,
        )
        final_output = getattr(result, "final_output", "")

        if isinstance(final_output, str):
            return ChatResponse(response=final_output)

        if final_output is None:
            return ChatResponse(response="")

        return ChatResponse(response=json.dumps(final_output, ensure_ascii=False))

    def _configure_client(self) -> None:
        if (
            not self.api_key_configured
            or AsyncOpenAI is None
            or set_default_openai_client is None
        ):
            return

        client_options = {"api_key": settings.openai_api_key}

        if settings.openai_base_url:
            client_options["base_url"] = settings.openai_base_url

        if settings.openai_websocket_base_url:
            client_options["websocket_base_url"] = settings.openai_websocket_base_url

        client = AsyncOpenAI(**client_options)
        set_default_openai_client(client)

    def _build_agent(self) -> Agent:
        if Agent is None:
            raise RuntimeError("OpenAI Agents SDK is not installed.")

        return Agent(
            name="AI Pet Assistant",
            instructions=SYSTEM_PROMPT,
            model=settings.openai_model,
        )
