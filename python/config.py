from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def _load_env_files() -> None:
    if load_dotenv is None:
        return

    python_dir = Path(__file__).resolve().parent
    project_root = python_dir.parent

    load_dotenv(project_root / ".env", override=False)
    load_dotenv(python_dir / ".env", override=False)


_load_env_files()


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value or None


def _optional_int_env(name: str) -> int | None:
    value = _optional_env(name)
    if value is None:
        return None

    return int(value)


def _optional_float_env(name: str, default: float) -> float:
    value = _optional_env(name)
    if value is None:
        return default

    return float(value)


def _bool_env(name: str, default: bool) -> bool:
    value = _optional_env(name)
    if value is None:
        return default

    return value.lower() == "true"


def _default_session_db_path() -> str:
    return str(Path.home() / ".ai-pet" / "agent_sessions.sqlite3")


def _default_tool_data_dir() -> str:
    return str((Path(__file__).resolve().parent / "data" / "tools").resolve())


def _default_memory_dir() -> str:
    project_root = Path(__file__).resolve().parent.parent
    return str((project_root / "data" / "memory").resolve())


def _default_knowledge_dir() -> str:
    project_root = Path(__file__).resolve().parent.parent
    return str((project_root / "knowledge").resolve())


def _default_knowledge_upload_dir() -> str:
    return str((Path(_optional_env("AI_PET_KB_DIR") or _default_knowledge_dir()) / "uploads").resolve())


def _default_knowledge_converted_dir() -> str:
    return str((Path(_optional_env("AI_PET_KB_DOCUMENT_DIR") or Path(_optional_env("AI_PET_KB_DIR") or _default_knowledge_dir()) / "documents") / "uploads").resolve())


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("AI_PET_AGENT_HOST", "127.0.0.1")
    port: int = int(os.getenv("AI_PET_AGENT_PORT", "8787"))
    openai_api_key: str | None = _optional_env("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "qwen3.6-plus")
    model_api: str = os.getenv("AI_PET_MODEL_API", "responses").lower()
    openai_base_url: str | None = _optional_env("OPENAI_BASE_URL")
    openai_websocket_base_url: str | None = _optional_env("OPENAI_WEBSOCKET_BASE_URL")
    mcp_enabled: bool = _bool_env("AI_PET_MCP_ENABLED", True)
    mcp_search_enabled: bool = _bool_env("AI_PET_MCP_SEARCH_ENABLED", False)
    mcp_search_name: str = os.getenv("AI_PET_MCP_SEARCH_NAME", "websearch")
    mcp_search_url: str | None = _optional_env("AI_PET_MCP_SEARCH_URL")
    mcp_search_api_key: str | None = _optional_env("AI_PET_MCP_SEARCH_API_KEY") or _optional_env(
        "DASHSCOPE_API_KEY"
    )
    mcp_search_timeout: float = _optional_float_env("AI_PET_MCP_SEARCH_TIMEOUT", 15.0)
    mcp_search_sse_read_timeout: float = _optional_float_env("AI_PET_MCP_SEARCH_SSE_READ_TIMEOUT", 60.0)
    mcp_search_cache_tools: bool = _bool_env("AI_PET_MCP_SEARCH_CACHE_TOOLS", True)
    mcp_search_max_retry_attempts: int = int(os.getenv("AI_PET_MCP_SEARCH_MAX_RETRY_ATTEMPTS", "1"))
    session_id: str = os.getenv("AI_PET_SESSION_ID", "desktop-active")
    session_db_path: str = os.getenv("AI_PET_SESSION_DB_PATH", _default_session_db_path())
    session_context_limit: int | None = _optional_int_env("AI_PET_SESSION_CONTEXT_LIMIT")
    tool_data_dir: str = os.getenv("AI_PET_TOOL_DATA_DIR", _default_tool_data_dir())
    memory_enabled: bool = os.getenv("AI_PET_MEMORY_ENABLED", "true").lower() == "true"
    memory_auto_capture: bool = os.getenv("AI_PET_MEMORY_AUTO_CAPTURE", "true").lower() == "true"
    memory_dir: str = _optional_env("AI_PET_MEMORY_DIR") or _default_memory_dir()
    # Injection limits: max chars loaded into one model request.
    memory_core_char_limit: int = int(os.getenv("AI_PET_MEMORY_CORE_CHAR_LIMIT", "3000"))
    memory_mode_char_limit: int = int(os.getenv("AI_PET_MEMORY_MODE_CHAR_LIMIT", "2500"))
    skill_index_char_limit: int = int(os.getenv("AI_PET_SKILL_INDEX_CHAR_LIMIT", "2000"))
    skill_file_char_limit: int = int(os.getenv("AI_PET_SKILL_FILE_CHAR_LIMIT", "5000"))
    max_skills_per_request: int = int(os.getenv("AI_PET_MAX_SKILLS_PER_REQUEST", "2"))
    # Storage limits: max chars kept on disk per markdown file.
    memory_core_file_max_chars: int = int(os.getenv("AI_PET_MEMORY_CORE_FILE_MAX_CHARS", "12000"))
    memory_mode_file_max_chars: int = int(os.getenv("AI_PET_MEMORY_MODE_FILE_MAX_CHARS", "10000"))
    skill_file_max_chars: int = int(os.getenv("AI_PET_SKILL_FILE_MAX_CHARS", "14000"))
    skill_index_file_max_chars: int = int(os.getenv("AI_PET_SKILL_INDEX_FILE_MAX_CHARS", "12000"))
    knowledge_enabled: bool = os.getenv("AI_PET_KB_ENABLED", "true").lower() == "true"
    knowledge_dir: str = _optional_env("AI_PET_KB_DIR") or _default_knowledge_dir()
    knowledge_document_dir: str = (
        _optional_env("AI_PET_KB_DOCUMENT_DIR")
        or str((Path(_optional_env("AI_PET_KB_DIR") or _default_knowledge_dir()) / "documents").resolve())
    )
    knowledge_index_db_path: str = (
        _optional_env("AI_PET_KB_INDEX_DB_PATH")
        or str((Path(_optional_env("AI_PET_KB_DIR") or _default_knowledge_dir()) / "index" / "knowledge.sqlite3").resolve())
    )
    knowledge_top_k: int = int(os.getenv("AI_PET_KB_TOP_K", "5"))
    knowledge_max_context_chars: int = int(os.getenv("AI_PET_KB_MAX_CONTEXT_CHARS", "6000"))
    knowledge_chunk_max_chars: int = int(os.getenv("AI_PET_KB_CHUNK_MAX_CHARS", "1400"))
    knowledge_auto_import_on_query: bool = os.getenv("AI_PET_KB_AUTO_IMPORT_ON_QUERY", "true").lower() == "true"
    knowledge_import_on_startup: bool = os.getenv("AI_PET_KB_IMPORT_ON_STARTUP", "true").lower() == "true"
    knowledge_embedding_enabled: bool = os.getenv("AI_PET_KB_EMBEDDING_ENABLED", "false").lower() == "true"
    knowledge_embedding_model: str = os.getenv("AI_PET_KB_EMBEDDING_MODEL", "text-embedding-3-small")
    knowledge_embedding_api_key: str | None = _optional_env("AI_PET_KB_EMBEDDING_API_KEY") or openai_api_key
    knowledge_embedding_base_url: str | None = _optional_env("AI_PET_KB_EMBEDDING_BASE_URL") or openai_base_url
    knowledge_embedding_dimensions: int | None = _optional_int_env("AI_PET_KB_EMBEDDING_DIMENSIONS")
    knowledge_vector_weight: float = float(os.getenv("AI_PET_KB_VECTOR_WEIGHT", "0.55"))
    knowledge_keyword_weight: float = float(os.getenv("AI_PET_KB_KEYWORD_WEIGHT", "0.45"))
    knowledge_graph_enabled: bool = os.getenv("AI_PET_KB_GRAPH_ENABLED", "true").lower() == "true"
    knowledge_graph_max_relations_per_chunk: int = int(os.getenv("AI_PET_KB_GRAPH_MAX_RELATIONS_PER_CHUNK", "8"))
    knowledge_graph_weight: float = float(os.getenv("AI_PET_KB_GRAPH_WEIGHT", "0.20"))
    knowledge_graph_context_limit: int = int(os.getenv("AI_PET_KB_GRAPH_CONTEXT_LIMIT", "2000"))
    knowledge_graph_llm_enabled: bool = os.getenv("AI_PET_KB_GRAPH_LLM_ENABLED", "false").lower() == "true"
    knowledge_graph_extractor: str = os.getenv("AI_PET_KB_GRAPH_EXTRACTOR", "hybrid")
    knowledge_graph_llm_model: str = _optional_env("AI_PET_KB_GRAPH_LLM_MODEL") or openai_model
    knowledge_graph_llm_api_key: str | None = _optional_env("AI_PET_KB_GRAPH_LLM_API_KEY") or openai_api_key
    knowledge_graph_llm_base_url: str | None = _optional_env("AI_PET_KB_GRAPH_LLM_BASE_URL") or openai_base_url
    knowledge_graph_llm_max_entities_per_chunk: int = int(os.getenv("AI_PET_KB_GRAPH_LLM_MAX_ENTITIES_PER_CHUNK", "30"))
    knowledge_graph_llm_max_relations_per_chunk: int = int(os.getenv("AI_PET_KB_GRAPH_LLM_MAX_RELATIONS_PER_CHUNK", "20"))
    knowledge_graph_llm_min_confidence: float = _optional_float_env("AI_PET_KB_GRAPH_LLM_MIN_CONFIDENCE", 0.65)
    knowledge_graph_llm_max_chars: int = int(os.getenv("AI_PET_KB_GRAPH_LLM_MAX_CHARS", "3000"))
    knowledge_graph_llm_fallback_to_rule: bool = (
        os.getenv("AI_PET_KB_GRAPH_LLM_FALLBACK_TO_RULE", "true").lower() == "true"
    )
    knowledge_summary_enabled: bool = os.getenv("AI_PET_KB_SUMMARY_ENABLED", "true").lower() == "true"
    knowledge_summary_model: str = _optional_env("AI_PET_KB_SUMMARY_MODEL") or openai_model
    knowledge_summary_api_key: str | None = _optional_env("AI_PET_KB_SUMMARY_API_KEY") or openai_api_key
    knowledge_summary_base_url: str | None = _optional_env("AI_PET_KB_SUMMARY_BASE_URL") or openai_base_url
    knowledge_summary_max_chars: int = int(os.getenv("AI_PET_KB_SUMMARY_MAX_CHARS", "6000"))
    knowledge_summary_on_import: bool = os.getenv("AI_PET_KB_SUMMARY_ON_IMPORT", "true").lower() == "true"
    knowledge_summary_llm_enabled: bool = os.getenv("AI_PET_KB_SUMMARY_LLM_ENABLED", "false").lower() == "true"
    knowledge_summary_embedding_enabled: bool = (
        os.getenv("AI_PET_KB_SUMMARY_EMBEDDING_ENABLED", "true").lower() == "true"
    )
    knowledge_upload_enabled: bool = os.getenv("AI_PET_KB_UPLOAD_ENABLED", "true").lower() == "true"
    knowledge_upload_dir: str = _optional_env("AI_PET_KB_UPLOAD_DIR") or _default_knowledge_upload_dir()
    knowledge_converted_dir: str = _optional_env("AI_PET_KB_CONVERTED_DIR") or _default_knowledge_converted_dir()
    knowledge_upload_max_mb: int = int(os.getenv("AI_PET_KB_UPLOAD_MAX_MB", "25"))
    knowledge_upload_allowed_extensions: str = os.getenv(
        "AI_PET_KB_UPLOAD_ALLOWED_EXTENSIONS",
        ".md,.txt,.pdf,.docx,.pptx,.xlsx,.html,.htm,.csv,.json",
    )


settings = Settings()
