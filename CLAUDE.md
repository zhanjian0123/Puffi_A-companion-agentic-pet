# CLAUDE.md

## 项目概述

AI Pet 是一个跨平台桌面 AI 宠物应用，集成个人知识库、MCP 工具生态和自动化任务执行能力。

## 技术栈

- **框架**: Electron 28 + React 18 + TypeScript
- **AI**: 阿里云百炼 (DashScope) + OpenAI SDK 兼容模式
- **MCP**: @modelcontextprotocol/sdk
- **知识库**: LanceDB (本地向量数据库)
- **状态管理**: Zustand
- **构建**: Vite + electron-builder

## 项目结构

```
src/
├── main/              # Electron 主进程
│   ├── mcp/           # MCP 客户端集成
│   ├── tools/         # 原子工具注册表
│   └── main.ts        # 主进程入口
├── renderer/          # React 渲染进程
│   ├── components/    # UI 组件
│   ├── store/         # Zustand 状态管理
│   └── App.tsx        # 主界面
├── core/              # AI 核心逻辑
│   ├── agent/         # Agent 规划和决策
│   └── rag/           # RAG 知识库
└── shared/            # 共享类型定义
```

## 开发命令

```bash
npm run dev        # 启动开发环境
npm run build      # 构建生产版本
npm run package    # 打包应用
```

## 核心模块

### MCP 集成
- `src/main/mcp/server.ts` - MCP 服务器连接和管理
- 默认集成：filesystem, memory 服务器

### 工具系统
- `src/main/tools/registry.ts` - 工具注册和调用
- 支持本地工具和 MCP 工具

### Agent 核心
- `src/core/agent/core.ts` - 消息处理和任务规划
- 支持阿里云百炼 (qwen-plus 等) 和本地 Ollama

### 知识库
- `src/core/rag/knowledge.ts` - 向量数据库操作
- 支持文档添加和语义搜索

## 环境变量

复制 `.env.example` 到 `.env` 并配置：
- `DASHSCOPE_API_KEY` - 阿里云百炼 API 密钥
- `DASHSCOPE_BASE_URL` - 百炼 API 地址 (默认已配置)
- `DASHSCOPE_MODEL` - 使用的模型 (默认 qwen-plus)
- `OLLAMA_BASE_URL` - 本地 Ollama 服务地址
- `KNOWLEDGE_BASE_PATH` - 知识库存储路径
