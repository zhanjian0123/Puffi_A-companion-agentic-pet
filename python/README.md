# Python Agent Service

This directory contains the next-stage backend architecture for AI Pet.

The intended responsibility split is:

- Electron/React: windows, tray, pet interaction, local desktop UX
- Python service: agent orchestration, RAG, tool execution, model access

## Planned API

- `GET /health`
- `POST /chat`
- `POST /knowledge/search`
- `POST /tools/invoke`

## Current Status

This backend is now centered on the OpenAI Agents SDK runtime and is intended to be the
main agent orchestration layer for AI Pet.

## OpenAI Agents SDK

The backend now uses the OpenAI Agents SDK as its primary agent runtime.

- Install dependency: `pip install openai-agents`
- Set `OPENAI_API_KEY`
- Optional: set `OPENAI_MODEL` (default: `gpt-5.4`)

The `/chat` route runs through `Agent + Runner` from the SDK and uses function tools for:

- knowledge search
- todo management
- notifications
- screenshot requests
