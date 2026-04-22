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


settings = Settings()
