# Python Migration Plan

## Goal

Move AI orchestration, knowledge search, and tool execution out of Electron main process and into a dedicated Python service.

## Current State

- Electron keeps window control and native desktop behavior.
- Python is now the target runtime for chat, knowledge search, and tool invocation.
- Electron-side bridge now calls the Python HTTP client under `src/main/python/`.

## Next Migration Steps

1. Add a `PythonServiceManager` in Electron main to start and health-check the Python backend.
2. Move knowledge persistence from Python memory mode into a real local store.
3. Move tool implementations into Python and keep Electron-only system actions as explicit bridge calls.
4. Add streaming chat support between Electron and Python.
5. Package the Python service for macOS and Windows distribution.

## Suggested Runtime Split

- Electron:
  - transparent pet window
  - panel window
  - tray, startup, drag/focus behavior
  - explicit native desktop capabilities
- Python:
  - LLM provider access
  - tool planning/execution
  - RAG pipeline
  - long-running memory and task logic
