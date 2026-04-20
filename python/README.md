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

This scaffold is intentionally lightweight and not yet wired into the Electron runtime.
It exists to support a staged migration from the current TypeScript-side agent into a
dedicated Python service.
