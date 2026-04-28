from __future__ import annotations

from inspect import isawaitable
from time import perf_counter
from typing import Any

from agents.mcp import MCPServer, MCPServerStreamableHttp

from config import settings


def build_mcp_servers() -> list[MCPServer]:
    if not settings.mcp_enabled:
        return []

    servers: list[MCPServer] = []

    search_server = _build_search_mcp_server()
    if search_server is not None:
        servers.append(search_server)

    return servers


def _build_search_mcp_server() -> MCPServer | None:
    if not settings.mcp_search_enabled:
        return None

    if not settings.mcp_search_url:
        print("[MCP] search disabled: AI_PET_MCP_SEARCH_URL is not configured", flush=True)
        return None

    if not settings.mcp_search_api_key:
        print(
            "[MCP] search disabled: AI_PET_MCP_SEARCH_API_KEY or DASHSCOPE_API_KEY is not configured",
            flush=True,
        )
        return None

    print(f"[MCP] search configured name={settings.mcp_search_name}", flush=True)
    return _with_mcp_logs(
        MCPServerStreamableHttp(
            {
                "url": settings.mcp_search_url,
                "headers": {
                    "Authorization": f"Bearer {settings.mcp_search_api_key}",
                },
                "timeout": settings.mcp_search_timeout,
                "sse_read_timeout": settings.mcp_search_sse_read_timeout,
            },
            cache_tools_list=settings.mcp_search_cache_tools,
            name=settings.mcp_search_name,
            max_retry_attempts=settings.mcp_search_max_retry_attempts,
        )
    )


def _shorten(value: object, limit: int = 500) -> str:
    text = str(value)
    if len(text) <= limit:
        return text

    return f"{text[:limit]}...<truncated>"


def _with_mcp_logs(server: MCPServer) -> MCPServer:
    if getattr(server, "_ai_pet_mcp_logging_wrapped", False):
        return server

    server_name = server.name
    original_list_tools = server.list_tools
    original_call_tool = server.call_tool
    last_logged_tool_names: tuple[str, ...] | None = None

    async def logged_list_tools(*args: Any, **kwargs: Any) -> Any:
        nonlocal last_logged_tool_names
        started_at = perf_counter()
        try:
            result = original_list_tools(*args, **kwargs)
            if isawaitable(result):
                result = await result
        except Exception as error:
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                f"[MCP] list_tools error server={server_name} elapsed={elapsed_ms:.1f}ms error={_shorten(error)}",
                flush=True,
            )
            raise

        elapsed_ms = (perf_counter() - started_at) * 1000
        tool_names = tuple(getattr(tool, "name", type(tool).__name__) for tool in result)
        if tool_names != last_logged_tool_names:
            print(
                f"[MCP] list_tools server={server_name} elapsed={elapsed_ms:.1f}ms tools={list(tool_names)}",
                flush=True,
            )
            last_logged_tool_names = tool_names
        return result

    async def logged_call_tool(tool_name: str, arguments: dict[str, Any] | None, *args: Any, **kwargs: Any) -> Any:
        started_at = perf_counter()
        print(
            f"[MCP] call_tool start server={server_name} tool={tool_name} args={_shorten(arguments)}",
            flush=True,
        )
        try:
            result = original_call_tool(tool_name, arguments, *args, **kwargs)
            if isawaitable(result):
                result = await result
        except Exception as error:
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                f"[MCP] call_tool error server={server_name} tool={tool_name} elapsed={elapsed_ms:.1f}ms error={_shorten(error)}",
                flush=True,
            )
            raise

        elapsed_ms = (perf_counter() - started_at) * 1000
        print(
            f"[MCP] call_tool success server={server_name} tool={tool_name} elapsed={elapsed_ms:.1f}ms result={_shorten(result)}",
            flush=True,
        )
        return result

    server.list_tools = logged_list_tools
    server.call_tool = logged_call_tool
    setattr(server, "_ai_pet_mcp_logging_wrapped", True)
    return server
