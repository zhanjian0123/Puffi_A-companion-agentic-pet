from __future__ import annotations

from inspect import isawaitable
import os
import re
from time import perf_counter
from typing import Any

from agents.mcp import MCPServer, MCPServerStreamableHttp

from config import settings


def build_mcp_servers() -> list[MCPServer]:
    if not settings.mcp_enabled:
        return []

    servers: list[MCPServer] = []
    for index, server_config in enumerate(settings.mcp_servers or []):
        server = _build_streamable_http_server(server_config, index)
        if server is not None:
            servers.append(server)

    return servers


def _build_streamable_http_server(config: dict[str, Any], index: int) -> MCPServer | None:
    if config.get("enabled", True) is False:
        return None

    server_type = str(config.get("type", "streamable_http")).strip().lower()
    if server_type not in {"streamable_http", "streamable-http"}:
        print(f"[MCP] server[{index}] disabled: unsupported type={server_type}", flush=True)
        return None

    name = str(config.get("name") or f"mcp-{index}").strip()
    url = str(config.get("url") or "").strip()
    if not url:
        print(f"[MCP] server[{index}] disabled: url is not configured", flush=True)
        return None

    headers = _resolve_headers(config)
    timeout = float(config.get("timeout", 15.0))
    sse_read_timeout = float(config.get("sse_read_timeout", 60.0))
    cache_tools = bool(config.get("cache_tools", True))
    max_retry_attempts = int(config.get("max_retry_attempts", 1))

    print(f"[MCP] configured name={name} type={server_type}", flush=True)
    return _with_mcp_logs(
        MCPServerStreamableHttp(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "sse_read_timeout": sse_read_timeout,
            },
            cache_tools_list=cache_tools,
            name=name,
            max_retry_attempts=max_retry_attempts,
        )
    )


def _resolve_headers(config: dict[str, Any]) -> dict[str, str]:
    raw_headers = config.get("headers")
    headers = {
        str(key): _resolve_env_placeholders(str(value))
        for key, value in raw_headers.items()
    } if isinstance(raw_headers, dict) else {}

    if "Authorization" not in headers:
        api_key = _resolve_api_key(config)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    return headers


def _resolve_api_key(config: dict[str, Any]) -> str | None:
    api_key = config.get("api_key")
    if isinstance(api_key, str) and api_key:
        return _resolve_env_placeholders(api_key)

    api_key_env = config.get("api_key_env")
    if isinstance(api_key_env, str) and api_key_env:
        return os.getenv(api_key_env)

    return None


def _resolve_env_placeholders(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return os.getenv(match.group(1), "")

    return re.sub(r"\$\{([A-Za-z0-9_]+)\}", replace, value)


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
