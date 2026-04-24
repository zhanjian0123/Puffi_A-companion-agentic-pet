from __future__ import annotations

from dataclasses import dataclass

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - optional dependency
    AsyncOpenAI = None


@dataclass(slots=True)
class EmbeddingConfig:
    enabled: bool
    model: str
    api_key: str | None
    base_url: str | None
    dimensions: int | None = None


class EmbeddingClient:
    def __init__(self, config: EmbeddingConfig) -> None:
        self._config = config
        self._client = self._build_client()

    @property
    def is_available(self) -> bool:
        return self._config.enabled and self._client is not None and bool(self._config.api_key)

    @property
    def model(self) -> str:
        return self._config.model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.is_available or self._client is None:
            raise RuntimeError("Embedding client is not available.")

        request: dict[str, object] = {
            "model": self._config.model,
            "input": texts,
        }
        if self._config.dimensions:
            request["dimensions"] = self._config.dimensions

        response = await self._client.embeddings.create(**request)
        return [list(item.embedding) for item in response.data]

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self.embed_texts([query])
        return embeddings[0] if embeddings else []

    def _build_client(self):
        if not self._config.enabled or AsyncOpenAI is None or not self._config.api_key:
            return None

        options = {"api_key": self._config.api_key}
        if self._config.base_url:
            options["base_url"] = self._config.base_url

        return AsyncOpenAI(**options)
