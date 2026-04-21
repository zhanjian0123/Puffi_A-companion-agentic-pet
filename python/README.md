# Python Agent Service

当前 Python 后端已经收缩为最小主链，只保留两件事：

- `GET /health`：检查 SDK 和密钥是否可用
- `POST /chat`：通过 OpenAI Agents SDK 执行一次对话

## Core Files

- `main.py`：Uvicorn 入口
- `app.py`：FastAPI 路由
- `service.py`：OpenAI Agents SDK 封装
- `schemas.py`：请求与响应模型
- `config.py`：环境变量加载

## Start

在项目根目录执行：

```bash
cd python
../.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8787 --log-level debug
```
