# AI Pet 个人助手

跨平台桌面 AI 宠物，集成个人知识库和 MCP 工具生态。

## 功能特性

- 🐾 可爱的桌面宠物交互
- 🧠 本地 + 云端 LLM 支持
- 📚 个人知识库 (RAG)
- 🔧 MCP 工具生态集成
- ⚡ 自动化任务执行

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 配置 API key
# DASHSCOPE_API_KEY=your_api_key  (阿里云百炼)
```

**阿里云百炼平台获取 API Key:**
1. 访问 https://dashscope.console.aliyun.com/
2. 登录/注册阿里云账号
3. 在"API-KEY 管理"中创建 API Key
4. 复制到 `.env` 文件中

### 3. 启动开发环境

```bash
npm run dev
```

如需在开发时默认打开 DevTools，可使用：

```bash
OPEN_DEVTOOLS=1 npm run dev
# 或
npm run dev:tools
```

### 4. 构建应用

```bash
npm run package
```

## 项目结构

```
ai-pet/
├── src/
│   ├── main/           # Electron 主进程
│   │   ├── mcp/        # MCP 客户端
│   │   ├── tools/      # 原子工具注册
│   │   └── main.ts     # 入口文件
│   ├── renderer/       # React 渲染进程
│   │   ├── components/ # UI 组件
│   │   ├── pet/        # 宠物动画
│   │   └── App.tsx     # 主界面
│   └── core/           # AI 核心逻辑
│       └── agent/      # Agent 规划器
├── mcp-servers/        # 自定义 MCP 服务
├── knowledge/          # 个人知识库
└── resources/          # 静态资源
```

## 技术栈

- **框架**: Electron 28 + React 18 + TypeScript
- **AI**: 阿里云百炼 (DashScope) + OpenAI SDK
- **MCP**: @modelcontextprotocol/sdk
- **知识库**: LanceDB (本地向量数据库)
- **状态管理**: Zustand
- **构建**: Vite + electron-builder

## Python Agent 规划

项目已经补充了 `python/` 服务骨架，用于承接后续的：

- Agent 编排
- RAG 检索
- 工具执行
- 模型接入

当前是迁移框架阶段，Electron 侧也增加了 Python HTTP client 骨架：

- [python/README.md](/Users/breo/Desktop/ai-pet/python/README.md)
- [PYTHON_MIGRATION.md](/Users/breo/Desktop/ai-pet/PYTHON_MIGRATION.md)
- [src/main/python/PythonAgentClient.ts](/Users/breo/Desktop/ai-pet/src/main/python/PythonAgentClient.ts)

## MCP 服务器

默认集成的 MCP 服务:
- `filesystem` - 文件系统操作
- `memory` - 长期记忆存储

可在 `.env` 中配置额外的 MCP 服务器。

## 许可证

MIT
