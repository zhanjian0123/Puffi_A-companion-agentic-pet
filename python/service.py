from __future__ import annotations

from collections.abc import AsyncIterator
import json
import re

from config import settings
from memory import MemoryService
from schemas import ChatRequest, ChatResponse, ChatStreamEvent, HealthResponse, HistoryResponse
from session_store import AgentSessionStore
from tool_registry import build_agent_tools

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
保持回复简洁、自然、友好，优先直接帮用户完成事情，对话可以适当添加一些 emoji。

工具使用规则：
1. 遇到时间、日期、待办查询这类需要准确信息的问题，优先调用可用工具，不要凭空猜测。
2. 普通陪聊、安慰、解释类问题，如果不需要工具就直接自然回答，不要为了用工具而用工具。
3. 如果工具执行失败、找不到目标或返回空结果，要明确告诉用户真实情况，绝对不要编造工具结果。

写入边界规则：
1. 你只能通过待办相关工具修改受控的本地待办数据。
2. 你不能假装自己能写任意文件，也不能承诺修改待办工具以外的本地内容。
3. 当用户想新增、完成或删除待办时，优先使用对应工具完成操作。

记忆系统规则：
1. SDK session 已负责短期上下文，你不需要向用户解释内部 session 细节。
2. 长期核心记忆适用于所有模式，模式记忆只适用于当前模式。
3. 当系统提供了记忆上下文时，把它当作用户长期偏好和当前模式状态参考，但不要逐字复述。
4. 如果用户明确要求“记住”或“忘记”，自然确认结果；不要声称保存了未被系统确认的记忆。
5. 只有当本轮上下文里出现“本轮记忆操作结果”时，你才可以说“我记住了/记下来啦”；否则不要假装已经保存记忆。
6. 如果本轮记忆操作是后台自动捕获，请自然融入回复，不要输出系统化的记忆摘要。

Skill 规则：
1. 只有当用户明确要求“保存为 skill / 沉淀成技能 / 下次复用这个流程”时，才调用 create_or_update_skill。
2. Skill 内容要提炼成可复用流程，避免包含临时对话碎片。
"""


class AgentService:
    def __init__(self) -> None:
        self._session_store = AgentSessionStore(
            session_id=settings.session_id,
            db_path=settings.session_db_path,
            context_limit=settings.session_context_limit,
        )
        self._memory_service = MemoryService(
            memory_dir=settings.memory_dir,
            core_char_limit=settings.memory_core_char_limit,
            mode_char_limit=settings.memory_mode_char_limit,
            skill_index_char_limit=settings.skill_index_char_limit,
            skill_file_char_limit=settings.skill_file_char_limit,
            max_skills_per_request=settings.max_skills_per_request,
            core_file_char_limit=settings.memory_core_file_max_chars,
            mode_file_char_limit=settings.memory_mode_file_max_chars,
            skill_file_max_chars=settings.skill_file_max_chars,
            skill_index_file_max_chars=settings.skill_index_file_max_chars,
            auto_capture=settings.memory_auto_capture,
            enabled=settings.memory_enabled,
        )
        self._tools = build_agent_tools()
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
        runtime_context, acknowledgement, short_circuit = await self._prepare_memory_state(request)
        if short_circuit:
            yield ChatStreamEvent(type="delta", delta=acknowledgement or "已处理记忆请求。")
            yield ChatStreamEvent(type="done")
            return

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

        agent = self._build_agent_for_runtime_context(runtime_context)

        result = Runner.run_streamed(
            agent,
            request.message,
            session=self._session_store.session,
        )

        emitted_text = False

        try:
            if acknowledgement:
                emitted_text = True
                yield ChatStreamEvent(type="delta", delta=f"{acknowledgement}\n\n")

            async for event in result.stream_events():
                delta = self._extract_stream_delta(event)
                if delta:
                    emitted_text = True
                    yield ChatStreamEvent(type="delta", delta=delta)

            if result.run_loop_exception:
                if not (emitted_text and self._is_missing_final_response_error(result.run_loop_exception)):
                    raise result.run_loop_exception

            if not emitted_text:
                fallback_text = self._stringify_output(getattr(result, "final_output", ""))
                if fallback_text:
                    yield ChatStreamEvent(type="delta", delta=fallback_text)
                elif acknowledgement:
                    yield ChatStreamEvent(type="delta", delta=acknowledgement)
                elif self._is_missing_final_response_error(result.run_loop_exception):
                    yield ChatStreamEvent(
                        type="delta",
                        delta="模型这次没有返回可用文本，请再发一次或换个完整问题试试。",
                    )

            yield ChatStreamEvent(type="done")
        except Exception as error:
            yield ChatStreamEvent(type="error", message=f"模型调用失败：{error}")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        runtime_context, acknowledgement, short_circuit = await self._prepare_memory_state(request)
        if short_circuit:
            return ChatResponse(response=acknowledgement or "已处理记忆请求。")

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

        agent = self._build_agent_for_runtime_context(runtime_context)

        try:
            result = await Runner.run(
                agent,
                request.message,
                session=self._session_store.session,
            )
            response_text = self._stringify_output(getattr(result, "final_output", ""))
        except Exception as error:
            if not self._is_missing_final_response_error(error):
                raise
            response_text = "模型这次没有返回可用文本，请再发一次或换个完整问题试试。"

        return ChatResponse(response=self._combine_memory_response(acknowledgement, response_text))

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

    def _build_agent(self, instructions: str | None = None) -> Agent:
        if Agent is None:
            raise RuntimeError("OpenAI Agents SDK is not installed.")

        return Agent(
            name="AI Pet Assistant",
            instructions=instructions or SYSTEM_PROMPT,
            model=settings.openai_model,
            tools=self._tools,
        )

    async def _prepare_memory_state(self, request: ChatRequest) -> tuple[str, str, bool]:
        mode = self._normalize_mode(request.mode)
        command_results = await self._memory_service.apply_explicit_commands(
            message=request.message,
            mode=mode,
        )
        memory_context = await self._memory_service.build_context(
            message=request.message,
            mode=mode,
        )
        runtime_context = self._format_runtime_context(
            mode=mode,
            memory_context=memory_context,
            command_messages=self._memory_service.format_runtime_notes(command_results),
        )
        acknowledgement = self._memory_service.format_acknowledgement(command_results)
        short_circuit = self._memory_service.should_short_circuit_response(
            message=request.message,
            command_results=command_results,
        )
        return runtime_context, acknowledgement, short_circuit

    def _build_agent_for_runtime_context(self, runtime_context: str) -> Agent:
        if not runtime_context:
            return self._agent or self._build_agent()

        return self._build_agent(f"{SYSTEM_PROMPT}\n\n{runtime_context}")

    def _format_runtime_context(
        self,
        *,
        mode: str,
        memory_context: str,
        command_messages: list[str],
    ) -> str:
        sections = [f"当前模式：{mode}"]

        if command_messages:
            sections.append("本轮记忆操作结果：\n" + "\n".join(f"- {message}" for message in command_messages))

        if memory_context:
            sections.append(memory_context)

        return "\n\n".join(sections)

    def _normalize_mode(self, mode: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_-]", "-", mode.strip().lower())
        return normalized or "chat"

    def _combine_memory_response(self, acknowledgement: str, response_text: str) -> str:
        ack = acknowledgement.strip()
        reply = response_text.strip()

        if ack and reply:
            return f"{ack}\n\n{reply}"
        if ack:
            return ack
        return reply

    def _extract_stream_delta(self, event: object) -> str:
        if getattr(event, "type", None) != "raw_response_event":
            return ""

        data = getattr(event, "data", None)
        if data is None:
            return ""

        if (
            ResponseTextDeltaEvent is not None
            and isinstance(data, ResponseTextDeltaEvent)
            and getattr(data, "delta", None)
        ):
            return str(data.delta)

        data_type = str(getattr(data, "type", ""))
        delta = getattr(data, "delta", None)
        if isinstance(delta, str) and delta and "text" in data_type and "reasoning" not in data_type:
            return delta

        return ""

    def _is_missing_final_response_error(self, error: object) -> bool:
        return "did not produce a final response" in str(error).lower()

    def _stringify_output(self, output: object) -> str:
        if isinstance(output, str):
            return output

        if output is None:
            return ""

        return json.dumps(output, ensure_ascii=False)
