# Knowledge Base Notes

AI Pet uses a lightweight LightRAG-like knowledge base without depending on the LightRAG package.

## Directory

Default runtime files live outside `data/`:

```text
knowledge/
  documents/
  index/
    knowledge.sqlite3
```

- `knowledge/documents/`: put local `.md` and `.txt` files here.
- `knowledge/index/knowledge.sqlite3`: generated SQLite index with documents, chunks, FTS data, and placeholder relation tables.

The root `knowledge/` directory is ignored by git because it may contain private local documents.

## Current Capabilities

- Import `.md` and `.txt` documents.
- Split documents into chunks.
- Store document manifest and chunks in SQLite.
- Search with SQLite FTS5 plus LIKE fallback.
- Automatically sync changed documents before each query when `AI_PET_KB_AUTO_IMPORT_ON_QUERY=true`.
- Automatically sync documents when the backend starts when `AI_PET_KB_IMPORT_ON_STARTUP=true`.
- Optionally use OpenAI-compatible embeddings for hybrid semantic search.
- Extract lightweight rule-based entities and relations for graph-boosted search.
- Return source file and chunk index.
- Expose a read-only `knowledge_search` Agent tool.

LLM relation extraction is intentionally not enabled yet. The graph layer is rule-based.

## API

```text
GET  /knowledge/status
GET  /knowledge/documents
POST /knowledge/import
POST /knowledge/query
GET  /knowledge/entities
GET  /knowledge/relations
```

Example import:

```bash
curl -s -X POST http://127.0.0.1:8787/knowledge/import \
  -H "Content-Type: application/json" \
  -d '{"path": null}'
```

Example query:

```bash
curl -s -X POST http://127.0.0.1:8787/knowledge/query \
  -H "Content-Type: application/json" \
  -d '{"query": "AgentService 和 MemoryService 怎么连接", "top_k": 5}'
```

## Environment

```env
AI_PET_KB_ENABLED=true
AI_PET_KB_DIR=
AI_PET_KB_DOCUMENT_DIR=
AI_PET_KB_INDEX_DB_PATH=
AI_PET_KB_TOP_K=5
AI_PET_KB_MAX_CONTEXT_CHARS=6000
AI_PET_KB_CHUNK_MAX_CHARS=1400
AI_PET_KB_AUTO_IMPORT_ON_QUERY=true
AI_PET_KB_IMPORT_ON_STARTUP=true

# Optional semantic search
AI_PET_KB_EMBEDDING_ENABLED=false
AI_PET_KB_EMBEDDING_MODEL=text-embedding-3-small
AI_PET_KB_EMBEDDING_API_KEY=
AI_PET_KB_EMBEDDING_BASE_URL=
AI_PET_KB_EMBEDDING_DIMENSIONS=
AI_PET_KB_VECTOR_WEIGHT=0.55
AI_PET_KB_KEYWORD_WEIGHT=0.45

# Optional rule-based graph search
AI_PET_KB_GRAPH_ENABLED=true
AI_PET_KB_GRAPH_MAX_RELATIONS_PER_CHUNK=8
AI_PET_KB_GRAPH_WEIGHT=0.20
AI_PET_KB_GRAPH_CONTEXT_LIMIT=2000
```

If paths are empty, defaults are under the project root `knowledge/` directory.
If embedding API key or base URL is empty, the backend reuses `OPENAI_API_KEY` and `OPENAI_BASE_URL`.

## Agent Behavior

When the user asks about local documents, project notes, or knowledge-base content, the Agent should call `knowledge_search`. If no result is found, it should say that directly instead of inventing an answer.
