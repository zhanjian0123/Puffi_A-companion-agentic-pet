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


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("AI_PET_AGENT_HOST", "127.0.0.1")
    port: int = int(os.getenv("AI_PET_AGENT_PORT", "8787"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    openai_websocket_base_url: str | None = os.getenv("OPENAI_WEBSOCKET_BASE_URL")


settings = Settings()
