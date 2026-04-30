from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
import json
import re

from config import settings
from interaction_state import InteractionStateStore
from memory import MemoryService
from mcp_servers import build_mcp_servers
from schemas import ChatRequest, ChatResponse, ChatStreamEvent, HealthResponse, HistoryResponse
from session_store import AgentSessionStore
from tool_registry import build_agent_tools

try:
    from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, RunConfig, Runner, set_default_openai_client
    from agents.mcp import MCPServerManager
    from openai import AsyncOpenAI
    from openai.types.responses import ResponseTextDeltaEvent
except ImportError:  # pragma: no cover - optional dependency
    Agent = None
    ModelSettings = None
    OpenAIChatCompletionsModel = None
    RunConfig = None
    Runner = None
    set_default_openai_client = None
    MCPServerManager = None
    AsyncOpenAI = None
    ResponseTextDeltaEvent = None


SYSTEM_PROMPT = """你是 AI Pet 的桌面宠物助手。
保持回复简洁、自然、友好，优先直接帮用户完成事情，对话可以适当添加一些 emoji，emoji要可爱。

工具使用规则：
1. 遇到时间、日期、待办、提醒查询这类需要准确信息的问题，优先调用可用工具，不要凭空猜测。
2. 普通陪聊、安慰、解释类问题，如果不需要工具就直接自然回答，不要为了用工具而用工具。
3. 如果工具执行失败、找不到目标或返回空结果，要明确告诉用户真实情况，绝对不要编造工具结果。
4. 当用户询问事实、定义、资料、项目文档、笔记或“某个东西是什么/怎么样/为什么”时，先调用 knowledge_search 检查本地知识库；不要等用户明确说“用本地知识库”才检索。
5. 当用户询问“知识库里有哪些 / 列出知识库 / 有哪些文档 / 当前收录了什么资料 / 知识库文件清单”时，调用 list_knowledge_documents。
6. 如果知识库有结果，优先基于知识库回答，并尽量给出来源文件；如果知识库没有结果，直接用通用模型知识自然回答，不要主动提“本地知识库没有找到”，除非用户明确询问知识库是否收录。
7. 当用户询问新闻、价格、政策、近期变化、当前版本、实时资料或明显需要外部网页验证的信息时，调用可用的外部搜索 MCP 工具获取最新信息；不要只依赖模型记忆。
8. 如果本地知识库结果可能已经过期，或用户明确要求“联网/外部搜索/查一下最新”，在 knowledge_search 之后再调用外部搜索 MCP 交叉验证。
9. 使用外部搜索结果回答时，尽量说明来源、网页标题或发布时间；如果外部搜索工具不可用或失败，要如实说明，不能编造搜索结果。
10. 搜索“今天/今日/最新新闻”时，必须先确认当前日期，并在搜索关键词中包含完整日期和年份，例如“YYYY年M月D日 今日要闻/新闻摘要”，避免只搜索“今日新闻”这类泛词。

写入边界规则：
1. 你只能通过待办相关工具修改受控的本地待办数据。
2. 你可以通过 write_knowledge_note 将用户明确要求沉淀的资料写入本地知识库；除此之外不能假装自己能写任意文件。
3. 当用户想新增、完成或删除待办/提醒时，优先使用对应工具完成操作。
4. 设置一次性提醒时必须把“明天/半小时后/下午三点”等相对时间换算成明确时间，再调用 add_reminder；remind_at 使用 YYYY-MM-DD HH:mm 或 YYYY-MM-DDTHH:mm:ss。
5. 当用户想取消、删除或去除某个提醒时，先用 list_reminders 确认提醒；如果能明确匹配，再调用 remove_reminder。
6. 当用户要求“每天/每日/定期/自动推送/自动执行”这类重复任务时，使用 add_scheduled_task，而不是 add_reminder；prompt 必须写清楚到点后要执行的完整动作。
7. 当用户想删除或停用自动任务时，先用 list_scheduled_tasks 确认任务；如果能明确匹配，再调用 remove_scheduled_task 或 pause_scheduled_task。
8. 只有当用户明确说“加入知识库 / 存到知识库 / 保存成资料 / 以后检索这个内容”等意图时，才调用 write_knowledge_note；不要把普通聊天、临时偏好、寒暄自动写入知识库。
9. 写入知识库前要先整理成简洁 Markdown：保留可复用事实、流程、结论和来源语境，避免保存冗余对话原文。
10. 当用户明确要求按路径删除知识库资料时，调用 delete_knowledge_document；必须使用用户提供的具体相对路径，不要根据标题、关键词或猜测路径删除知识库文件。
11. 如果用户想删除知识库资料但没有提供具体路径，先要求用户提供来源路径，不要直接调用删除工具。

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


@dataclass(slots=True)
class RuntimeState:
    mode: str
    runtime_context: str
    acknowledgement: str
    short_circuit: bool
    should_track_user_chat: bool
    started_at: datetime


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
        self._interaction_state = InteractionStateStore()
        self._tools = build_agent_tools()
        self._mcp_servers = build_mcp_servers()
        self._mcp_connected = False
        self._client = None
        self._mcp_manager = (
            MCPServerManager(
                self._mcp_servers,
                connect_timeout_seconds=settings.mcp_connect_timeout,
                cleanup_timeout_seconds=settings.mcp_cleanup_timeout,
                drop_failed_servers=True,
                strict=False,
                connect_in_parallel=True,
            )
            if self._mcp_servers and MCPServerManager is not None
            else None
        )
        self._configure_client()
        self._agent = self._build_agent() if self.is_available else None

    @property
    def sdk_installed(self) -> bool:
        return (
            Agent is not None
            and OpenAIChatCompletionsModel is not None
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
            model_api=settings.model_api,
            base_url=settings.openai_base_url,
            mcp_enabled=settings.mcp_enabled,
            mcp_servers=[server.name for server in self._active_mcp_servers()],
        )

    async def startup(self) -> None:
        if self._mcp_manager is None:
            return

        active_servers = await self._mcp_manager.connect_all()
        self._mcp_connected = True
        print(
            f"[MCP] connected servers={[server.name for server in active_servers]}",
            flush=True,
        )

        if self._mcp_manager.failed_servers:
            print(
                f"[MCP] failed servers={[server.name for server in self._mcp_manager.failed_servers]}",
                flush=True,
            )

        if self.is_available:
            self._agent = self._build_agent()

    async def shutdown(self) -> None:
        if self._mcp_manager is None:
            return

        await self._mcp_manager.cleanup_all()
        self._mcp_connected = False

    async def history(self, limit: int) -> HistoryResponse:
        messages = await self._session_store.get_recent_messages(limit)
        return HistoryResponse(messages=messages)

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        runtime_state = await self._prepare_runtime_state(request)
        if runtime_state.short_circuit:
            yield ChatStreamEvent(type="state", pet_state="tooling")
            yield ChatStreamEvent(type="delta", delta=runtime_state.acknowledgement or "已处理记忆请求。")
            yield ChatStreamEvent(type="done", pet_state="success")
            await self._mark_user_chat_completed(runtime_state)
            return

        if not self.sdk_installed:
            yield ChatStreamEvent(
                type="error",
                message=(
                    "当前 Python 环境没有可用的 OpenAI Agents SDK。"
                    "请确认你是在项目的 .venv 中安装了 `openai-agents`。"
                ),
                pet_state="error",
            )
            return

        if not self.api_key_configured:
            yield ChatStreamEvent(
                type="error",
                message="还没有检测到 OPENAI_API_KEY，请先在 .env 中补齐后再试。",
                pet_state="error",
            )
            return

        if self._agent is None or Runner is None:
            yield ChatStreamEvent(
                type="error",
                message="Agent 初始化失败，请检查模型和 base URL 配置。",
                pet_state="error",
            )
            return

        agent = self._build_agent_for_runtime_context(runtime_state.runtime_context)

        result = Runner.run_streamed(
            agent,
            request.message,
            run_config=self._build_run_config(),
            session=self._session_store.session,
        )

        emitted_text = False
        current_pet_state = "thinking"

        try:
            yield ChatStreamEvent(type="state", pet_state=current_pet_state)

            if runtime_state.acknowledgement:
                emitted_text = True
                yield ChatStreamEvent(type="delta", delta=f"{runtime_state.acknowledgement}\n\n")

            async for event in result.stream_events():
                next_pet_state = self._extract_pet_state_from_stream_event(event)
                if next_pet_state and next_pet_state != current_pet_state:
                    current_pet_state = next_pet_state
                    yield ChatStreamEvent(type="state", pet_state=current_pet_state)

                delta = self._extract_stream_delta(event)
                if delta:
                    emitted_text = True
                    yield ChatStreamEvent(type="delta", delta=delta)

            if result.run_loop_exception:
                if not (emitted_text and self._is_missing_final_response_error(result.run_loop_exception)):
                    raise result.run_loop_exception

            if not emitted_text:
                fallback_text = self._stringify_output(getattr(result, "final_output", ""))
                if not fallback_text.strip():
                    fallback_text = self._fallback_text_from_run_result(result, request.message)
                if fallback_text:
                    yield ChatStreamEvent(type="delta", delta=fallback_text)
                elif runtime_state.acknowledgement:
                    yield ChatStreamEvent(type="delta", delta=runtime_state.acknowledgement)
                elif self._is_missing_final_response_error(result.run_loop_exception):
                    yield ChatStreamEvent(
                        type="delta",
                        delta="模型这次没有返回可用文本，请再发一次或换个完整问题试试。",
                    )
            else:
                final_text = self._stringify_output(getattr(result, "final_output", ""))
                if not final_text.strip():
                    fallback_text = self._fallback_text_from_run_result(result, request.message)
                    if fallback_text:
                        yield ChatStreamEvent(type="delta", delta=f"\n\n{fallback_text}")

            yield ChatStreamEvent(type="done", pet_state="success")
            await self._mark_user_chat_completed(runtime_state)
        except Exception as error:
            yield ChatStreamEvent(type="error", message=f"模型调用失败：{error}", pet_state="error")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        runtime_state = await self._prepare_runtime_state(request)
        if runtime_state.short_circuit:
            await self._mark_user_chat_completed(runtime_state)
            return ChatResponse(response=runtime_state.acknowledgement or "已处理记忆请求。")

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

        agent = self._build_agent_for_runtime_context(runtime_state.runtime_context)

        try:
            result = await Runner.run(
                agent,
                request.message,
                run_config=self._build_run_config(),
                session=self._session_store.session,
            )
            response_text = self._stringify_output(getattr(result, "final_output", ""))
            if not response_text.strip():
                response_text = self._fallback_text_from_run_result(result, request.message)
        except Exception as error:
            if not self._is_missing_final_response_error(error):
                raise
            response_text = "模型这次没有返回可用文本，请再发一次或换个完整问题试试。"

        await self._mark_user_chat_completed(runtime_state)
        return ChatResponse(response=self._combine_memory_response(runtime_state.acknowledgement, response_text))

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

        self._client = AsyncOpenAI(**client_options)
        set_default_openai_client(self._client)

    def _build_agent(self, instructions: str | None = None) -> Agent:
        if Agent is None:
            raise RuntimeError("OpenAI Agents SDK is not installed.")

        agent_options = {
            "name": "AI Pet Assistant",
            "instructions": instructions or SYSTEM_PROMPT,
            "model": self._build_model(),
            "tools": self._tools,
            "mcp_servers": self._active_mcp_servers(),
        }
        model_settings = self._build_model_settings()
        if model_settings is not None:
            agent_options["model_settings"] = model_settings

        return Agent(**agent_options)

    def _build_model_settings(self) -> object | None:
        if ModelSettings is None or settings.model_extra_body is None:
            return None

        return ModelSettings(extra_body=settings.model_extra_body)

    def _build_run_config(self) -> object | None:
        if RunConfig is None or settings.model_api != "chat_completions":
            return None

        if settings.chat_completions_history_mode != "text_only":
            return None

        return RunConfig(session_input_callback=self._chat_completions_session_input)

    def _chat_completions_session_input(
        self,
        history_items: list[dict[str, Any]],
        new_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        cleaned_history = [
            item
            for item in (self._clean_chat_completions_history_item(item) for item in history_items)
            if item is not None
        ]
        return cleaned_history + new_items

    def _clean_chat_completions_history_item(self, item: object) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None

        role = item.get("role")
        if role not in {"user", "assistant"}:
            return None

        content = self._extract_chat_message_text(item.get("content"))
        if not content:
            return None

        return {
            "role": role,
            "content": content,
        }

    def _extract_chat_message_text(self, value: object) -> str:
        if isinstance(value, str):
            return value.strip()

        if isinstance(value, list):
            parts = [self._extract_chat_message_text(item) for item in value]
            return "\n".join(part for part in parts if part).strip()

        if isinstance(value, dict):
            for key in ("text", "content", "value"):
                text = self._extract_chat_message_text(value.get(key))
                if text:
                    return text

        return ""

    def _build_model(self) -> object:
        if settings.model_api == "chat_completions":
            if OpenAIChatCompletionsModel is None or self._client is None:
                raise RuntimeError("Chat Completions model is not available.")

            return OpenAIChatCompletionsModel(
                model=settings.openai_model,
                openai_client=self._client,
            )

        return settings.openai_model

    def _active_mcp_servers(self) -> list[object]:
        if self._mcp_manager is None or not self._mcp_connected:
            return []

        return self._mcp_manager.active_servers

    async def _prepare_runtime_state(self, request: ChatRequest) -> RuntimeState:
        mode = self._normalize_mode(request.mode)
        now = datetime.now().astimezone()
        should_track_user_chat = mode == "chat"
        temporal_context = ""
        if should_track_user_chat:
            interaction_state = await self._interaction_state.load()
            temporal_context = self._format_temporal_context(
                now=now,
                last_user_chat_at=interaction_state.last_user_chat_at,
            )

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
            now=now,
            temporal_context=temporal_context,
            memory_context=memory_context,
            command_messages=self._memory_service.format_runtime_notes(command_results),
        )
        acknowledgement = self._memory_service.format_acknowledgement(command_results)
        short_circuit = self._memory_service.should_short_circuit_response(
            message=request.message,
            command_results=command_results,
        )
        return RuntimeState(
            mode=mode,
            runtime_context=runtime_context,
            acknowledgement=acknowledgement,
            short_circuit=short_circuit,
            should_track_user_chat=should_track_user_chat,
            started_at=now,
        )

    def _build_agent_for_runtime_context(self, runtime_context: str) -> Agent:
        if not runtime_context:
            return self._agent or self._build_agent()

        return self._build_agent(f"{SYSTEM_PROMPT}\n\n{runtime_context}")

    def _format_runtime_context(
        self,
        *,
        mode: str,
        now: datetime,
        temporal_context: str,
        memory_context: str,
        command_messages: list[str],
    ) -> str:
        sections = [f"当前模式：{mode}"]
        sections.append(f"当前日期：{now.strftime('%Y-%m-%d')}")

        if temporal_context:
            sections.append(temporal_context)

        if command_messages:
            sections.append("本轮记忆操作结果：\n" + "\n".join(f"- {message}" for message in command_messages))

        if memory_context:
            sections.append(memory_context)

        return "\n\n".join(sections)

    def _format_temporal_context(self, *, now: datetime, last_user_chat_at: datetime | None) -> str:
        weekday = self._format_weekday(now)
        lines = [
            "时间感知上下文：",
            f"- 当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}，{weekday}。",
        ]

        if last_user_chat_at is None:
            lines.extend(
                [
                    "- 上次用户对话时间：暂无记录，可能是首次对话或本地状态刚初始化。",
                    "- 这是当前记录中的首次用户对话。",
                ]
            )
        else:
            last_local = last_user_chat_at.astimezone(now.tzinfo)
            day_delta = (now.date() - last_local.date()).days
            elapsed = max(now - last_local, timedelta())
            lines.extend(
                [
                    f"- 上次用户对话时间：{last_local.strftime('%Y-%m-%d %H:%M:%S')}，{self._format_weekday(last_local)}。",
                    f"- 距离上次用户对话已经过去：{self._format_elapsed(elapsed)}。",
                    f"- 是否跨自然日：{'是' if day_delta > 0 else '否'}。",
                    f"- 是否今天首次用户对话：{'是' if day_delta > 0 else '否'}。",
                ]
            )

            if day_delta >= 1:
                lines.append(f"- 距离上次用户对话已经过了 {day_delta} 个自然日。")

        lines.extend(
            [
                "- 使用方式：你可以自然感知时间流逝，尤其是跨天、隔了多天、早晚问候或用户继续上次话题时。",
                "- 不要机械复述这些时间字段；只有在对话自然需要时，轻轻体现“过了一段时间/又是新的一天”。",
            ]
        )
        return "\n".join(lines)

    def _format_weekday(self, value: datetime) -> str:
        names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return names[value.weekday()]

    def _format_elapsed(self, elapsed: timedelta) -> str:
        total_seconds = max(int(elapsed.total_seconds()), 0)
        days, remainder = divmod(total_seconds, 24 * 60 * 60)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, seconds = divmod(remainder, 60)

        parts: list[str] = []
        if days:
            parts.append(f"{days}天")
        if hours:
            parts.append(f"{hours}小时")
        if minutes:
            parts.append(f"{minutes}分钟")
        if not parts:
            parts.append(f"{seconds}秒")
        return "".join(parts)

    async def _mark_user_chat_completed(self, runtime_state: RuntimeState) -> None:
        if not runtime_state.should_track_user_chat:
            return

        await self._interaction_state.update_last_user_chat_at(runtime_state.started_at)

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

    def _extract_pet_state_from_stream_event(self, event: object) -> str | None:
        if getattr(event, "type", None) != "run_item_stream_event":
            return None

        item = getattr(event, "item", None)
        item_type = type(item).__name__.lower()
        event_name = str(getattr(event, "name", "")).lower()

        if "tool" not in item_type and "tool" not in event_name:
            return None

        tool_name = self._extract_tool_name(item) or self._extract_tool_name(event)
        if not tool_name:
            return "tooling"

        return self._pet_state_for_tool_name(tool_name)

    def _pet_state_for_tool_name(self, tool_name: str) -> str:
        normalized = tool_name.lower()
        if "search" in normalized or "bailian_web_search" in normalized:
            return "searching"

        return "tooling"

    def _extract_tool_name(self, value: object, depth: int = 0) -> str | None:
        if value is None or depth > 4:
            return None

        if isinstance(value, dict):
            for key in ("name", "tool_name", "server_label"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate

            for key in ("raw_item", "item", "function", "tool", "tool_call"):
                candidate = self._extract_tool_name(value.get(key), depth + 1)
                if candidate:
                    return candidate

            return None

        for attr in ("name", "tool_name", "server_label"):
            candidate = getattr(value, attr, None)
            if isinstance(candidate, str) and candidate.strip():
                return candidate

        for attr in ("raw_item", "item", "function", "tool", "tool_call"):
            candidate = self._extract_tool_name(getattr(value, attr, None), depth + 1)
            if candidate:
                return candidate

        return None

    def _is_missing_final_response_error(self, error: object) -> bool:
        return "did not produce a final response" in str(error).lower()

    def _stringify_output(self, output: object) -> str:
        if isinstance(output, str):
            return output

        if output is None:
            return ""

        return json.dumps(output, ensure_ascii=False)

    def _fallback_text_from_run_result(self, result: object, user_message: str = "") -> str:
        for text in reversed(self._extract_tool_output_texts(result)):
            formatted = self._format_search_tool_output(text, user_message)
            if formatted:
                return formatted

        return ""

    def _extract_tool_output_texts(self, result: object) -> list[str]:
        texts: list[str] = []
        for item in getattr(result, "new_items", []) or []:
            if type(item).__name__ != "ToolCallOutputItem":
                continue

            texts.extend(self._extract_text_from_tool_output(getattr(item, "output", None)))

            raw_item = getattr(item, "raw_item", None)
            if isinstance(raw_item, dict):
                texts.extend(self._extract_text_from_tool_output(raw_item.get("output")))

        return texts

    def _extract_text_from_tool_output(self, output: object) -> list[str]:
        if output is None:
            return []

        if isinstance(output, str):
            return [output]

        if isinstance(output, dict):
            text = output.get("text")
            if isinstance(text, str):
                return [text]

            nested_output = output.get("output")
            if nested_output is not None:
                return self._extract_text_from_tool_output(nested_output)

            return []

        if isinstance(output, list):
            texts: list[str] = []
            for item in output:
                texts.extend(self._extract_text_from_tool_output(item))
            return texts

        return []

    def _format_search_tool_output(self, text: str, user_message: str = "") -> str:
        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError:
            return text.strip()

        if not isinstance(payload, dict):
            return ""

        pages = payload.get("pages")
        if not isinstance(pages, list):
            return ""

        pages_to_format = self._prioritize_current_year_pages(pages, user_message)
        formatted_pages: list[str] = []
        for page in pages_to_format[:5]:
            if not isinstance(page, dict):
                continue

            title = str(page.get("title") or "搜索结果").strip()
            hostname = str(page.get("hostname") or "").strip()
            url = str(page.get("url") or "").strip()
            snippet = re.sub(r"\s+", " ", str(page.get("snippet") or "")).strip()
            if len(snippet) > 220:
                snippet = f"{snippet[:220]}..."

            source = hostname or url
            source_line = f"\n来源：{source}" if source else ""
            url_line = f"\n链接：{url}" if url else ""
            formatted_pages.append(
                f"{len(formatted_pages) + 1}. {title}\n{snippet}{source_line}{url_line}"
            )

        if not formatted_pages:
            return "外部搜索完成了，但没有拿到可用的搜索结果。"

        return "我查到这些最新结果：\n\n" + "\n\n".join(formatted_pages)

    def _prioritize_current_year_pages(self, pages: list[object], user_message: str) -> list[object]:
        message = user_message.strip()
        is_time_sensitive = any(keyword in message for keyword in ["今天", "今日", "最新", "新闻", "2026"])
        if not is_time_sensitive:
            return pages

        current_year = datetime.now().strftime("%Y")

        def page_text(page: object) -> str:
            if not isinstance(page, dict):
                return ""
            return f"{page.get('title', '')} {page.get('snippet', '')} {page.get('url', '')}"

        current_year_pages = [page for page in pages if current_year in page_text(page)]
        other_pages = [page for page in pages if current_year not in page_text(page)]
        return [*current_year_pages, *other_pages]
