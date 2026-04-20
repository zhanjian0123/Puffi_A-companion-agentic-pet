from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("AI_PET_AGENT_HOST", "127.0.0.1")
    port: int = int(os.getenv("AI_PET_AGENT_PORT", "8787"))
    dashscope_api_key: str | None = os.getenv("DASHSCOPE_API_KEY")
    dashscope_base_url: str = os.getenv(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    dashscope_model: str = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
    knowledge_base_path: str = os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge")


settings = Settings()
