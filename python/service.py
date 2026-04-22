from __future__ import annotations

from collections.abc import AsyncIterator
import json

from config import settings
from schemas import ChatRequest, ChatResponse, ChatStreamEvent, HealthResponse, HistoryResponse
from session_store import AgentSessionStore

try:
    from agents import Agent, Runner, set_default_openai_client
    from openai import AsyncOpenAI
    from openai.types.responses import ResponseTextDeltaEvent
except ImportError:  # pragma: no cover - optional dependency
    Agent = None
    Runner = None
    set_default_openai_client = None
    AsyncOpenAI = None
    ResponseTextDeltaEvent = None


SYSTEM_PROMPT = """你是 AI Pet 的桌面宠物助手。
保持回复简洁、自然、友好，优先直接帮用户完成事情，对话可以适当添加一些emoji。"""


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

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        if not self.sdk_installed:
            yield ChatStreamEvent(
                type="error",
                message=(
                    "当前 Python 环境没有可用的 OpenAI Agents SDK。"
                    "请确认你是在项目的 .venv 中安装了 `openai-agents`。"
                ),
            )
            return

        if not self.api_key_configured:
            yield ChatStreamEvent(
                type="error",
                message="还没有检测到 OPENAI_API_KEY，请先在 .env 中补齐后再试。",
            )
            return

        if self._agent is None or Runner is None:
            yield ChatStreamEvent(type="error", message="Agent 初始化失败，请检查模型和 base URL 配置。")
            return

        result = Runner.run_streamed(
            self._agent,
            request.message,
            session=self._session_store.session,
        )

        emitted_text = False

        try:
          async for event in result.stream_events():
              if (
                  event.type == "raw_response_event"
                  and ResponseTextDeltaEvent is not None
                  and isinstance(event.data, ResponseTextDeltaEvent)
                  and event.data.delta
              ):
                  emitted_text = True
                  yield ChatStreamEvent(type="delta", delta=event.data.delta)

          if result.run_loop_exception:
              raise result.run_loop_exception

          if not emitted_text:
              fallback_text = self._stringify_output(getattr(result, "final_output", ""))
              if fallback_text:
                  yield ChatStreamEvent(type="delta", delta=fallback_text)

          yield ChatStreamEvent(type="done")
        except Exception as error:
            yield ChatStreamEvent(type="error", message=f"模型调用失败：{error}")

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
        return ChatResponse(response=self._stringify_output(getattr(result, "final_output", "")))

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

    def _stringify_output(self, output: object) -> str:
        if isinstance(output, str):
            return output

        if output is None:
            return ""

        return json.dumps(output, ensure_ascii=False)
