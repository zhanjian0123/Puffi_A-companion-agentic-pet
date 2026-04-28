# Python Agent Service

当前 Python 后端已经收缩为最小主链，只保留两件事：

- `GET /health`：检查 SDK 和密钥是否可用
- `POST /chat`：通过 OpenAI Agents SDK 执行一次对话
- `GET /history`：读取当前 SDK session 中最近几条用户/助手消息

## Core Files

- `main.py`：Uvicorn 入口
- `app.py`：FastAPI 路由
- `service.py`：OpenAI Agents SDK 封装
- `mcp_servers.py`：外部 MCP 服务配置与接入
- `session_store.py`：SQLiteSession 封装与历史消息读取
- `schemas.py`：请求与响应模型
- `config.py`：环境变量加载

## Start

在项目根目录执行：

```bash
cd python
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8787 --log-level debug
```

## External Search MCP

服务支持通过 Streamable HTTP MCP 接入外部搜索工具。以阿里云百炼 MCP 外部调用为例，在项目根目录 `.env` 中配置：

```bash
AI_PET_MCP_ENABLED=true
AI_PET_MCP_SEARCH_ENABLED=true
AI_PET_MCP_SEARCH_NAME=websearch
AI_PET_MCP_SEARCH_URL=https://dashscope.aliyuncs.com/api/v1/mcps/YOUR_MCP_NAME/mcp
AI_PET_MCP_SEARCH_API_KEY=your_bailian_api_key
```

如果已设置 `DASHSCOPE_API_KEY`，可以省略 `AI_PET_MCP_SEARCH_API_KEY`。具体 URL 和 MCP 名称以百炼控制台“外部调用”页面展示为准。

## DeepSeek V4 Flash

DeepSeek V4 Flash 使用 OpenAI Chat Completions 兼容接口。在 `.env` 中配置：

```bash
OPENAI_API_KEY=your_deepseek_api_key
OPENAI_MODEL=deepseek-v4-flash
OPENAI_BASE_URL=https://api.deepseek.com
AI_PET_MODEL_API=chat_completions
```

如果切回当前百炼模型，可以将 `AI_PET_MODEL_API` 改回 `responses` 或删除该配置。
