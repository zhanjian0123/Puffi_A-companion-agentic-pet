# AI Pet Architecture

## Direction

This project is evolving from a runnable Electron prototype into a desktop agent with:

- a dedicated desktop shell
- a visual pet presentation layer
- an agent orchestration core
- pluggable local and MCP tools
- a real local knowledge pipeline
- swappable LLM providers

## Target Structure

```text
src/
├── main/
│   ├── app/
│   ├── ipc/
│   ├── preload/
│   └── bootstrap.ts
├── renderer/
│   ├── app/
│   ├── chat/
│   ├── knowledge/
│   ├── pet/
│   ├── settings/
│   └── store/
├── agent/
│   ├── core/
│   ├── memory/
│   ├── planning/
│   └── prompts/
├── llm/
│   ├── providers/
│   ├── schemas/
│   └── client.ts
├── tools/
│   ├── local/
│   ├── mcp/
│   ├── permissions/
│   └── registry/
└── knowledge/
    ├── embed/
    ├── ingest/
    ├── retrieve/
    └── store/
```

## Layer Responsibilities

### main

Electron lifecycle, window creation, preload registration, IPC setup, and dependency wiring.

### renderer

The user-facing interface for chat, pet rendering, settings, and knowledge management.

### agent

The orchestration layer that combines prompt building, retrieval, tool decisions, tool execution, and response generation.

### llm

Provider-agnostic model access for DashScope, OpenAI-compatible APIs, and local models like Ollama.

### tools

Local tool definitions, MCP tool discovery, schema normalization, execution, and permissions.

### knowledge

Document ingest, chunking, embedding, local storage, retrieval, and citation assembly.

## First Milestones

1. Stabilize Electron shell and IPC boundaries.
2. Move agent orchestration into its own top-level module.
3. Replace in-memory knowledge search with a persistent local store.
4. Upgrade tool calling from placeholders to a full request-execute-observe loop.
5. Promote Pixi-based pet rendering into a first-class UI module.
