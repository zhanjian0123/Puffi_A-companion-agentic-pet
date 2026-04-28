# AI Pet

一个最小可运行的桌面宠物助手骨架，当前只保留三条核心链路：

- Electron 主进程：创建宠物窗和聊天悬浮窗
- React 渲染层：宠物交互和聊天面板
- Python 服务：通过 OpenAI Agents SDK 执行聊天

## Current Structure

```text
src/
  main/        Electron 窗口、IPC、Python 服务桥接
  renderer/    宠物 UI 和聊天 UI
  shared/      preload 类型定义
python/
  main.py      Uvicorn 入口
  app.py       FastAPI 路由
  service.py   OpenAI Agents SDK 封装
  schemas.py   接口模型
  config.py    环境变量加载
```

## Development

前端桌面端：

```bash
npm run dev:desktop
```

Python 后端：

```bash
npm run dev:python
```

如果开发时希望自动打开 Electron DevTools，可以直接把
`src/main/app/devFlags.ts` 里的 `OPEN_DEVTOOLS` 改成 `true`。

## Environment

复制 `.env.example` 到 `.env`，至少填写：

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `AI_PET_MODEL_API`：默认 `responses`；DeepSeek 等只支持 Chat Completions 的服务填 `chat_completions`
- `OPENAI_BASE_URL`：接其他兼容平台时再填
- `OPENAI_WEBSOCKET_BASE_URL`：只有供应商要求 WebSocket 地址时再填

外部搜索 MCP 可选配置：

- `AI_PET_MCP_ENABLED=true`
- `AI_PET_MCP_SEARCH_ENABLED=true`
- `AI_PET_MCP_SEARCH_NAME=websearch`
- `AI_PET_MCP_SEARCH_URL`：百炼 MCP 外部调用里的 Streamable HTTP 地址
- `AI_PET_MCP_SEARCH_API_KEY`：百炼 API Key；已配置 `DASHSCOPE_API_KEY` 时可省略

DeepSeek V4 Flash 示例：

```bash
OPENAI_API_KEY=your_deepseek_api_key
OPENAI_MODEL=deepseek-v4-flash
OPENAI_BASE_URL=https://api.deepseek.com
AI_PET_MODEL_API=chat_completions
```
