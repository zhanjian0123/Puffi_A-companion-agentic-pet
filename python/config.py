from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("AI_PET_AGENT_HOST", "127.0.0.1")
    port: int = int(os.getenv("AI_PET_AGENT_PORT", "8787"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4")
    knowledge_base_path: str = os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge")


settings = Settings()
