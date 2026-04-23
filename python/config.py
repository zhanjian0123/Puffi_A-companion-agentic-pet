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


def _default_session_db_path() -> str:
    return str(Path.home() / ".ai-pet" / "agent_sessions.sqlite3")


def _default_tool_data_dir() -> str:
    return str((Path(__file__).resolve().parent / "data" / "tools").resolve())


def _default_memory_dir() -> str:
    project_root = Path(__file__).resolve().parent.parent
    return str((project_root / "data" / "memory").resolve())


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("AI_PET_AGENT_HOST", "127.0.0.1")
    port: int = int(os.getenv("AI_PET_AGENT_PORT", "8787"))
    openai_api_key: str | None = _optional_env("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "qwen3.6-plus")
    openai_base_url: str | None = _optional_env("OPENAI_BASE_URL")
    openai_websocket_base_url: str | None = _optional_env("OPENAI_WEBSOCKET_BASE_URL")
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


settings = Settings()
