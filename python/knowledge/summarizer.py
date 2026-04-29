from __future__ import annotations

from dataclasses import dataclass
import re

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None


@dataclass(slots=True)
class SummaryConfig:
    enabled: bool
    llm_enabled: bool
    model: str
    api_key: str | None
    base_url: str | None
    max_chars: int


@dataclass(slots=True)
class DocumentSummary:
    summary: str
    keywords: list[str]
    topics: list[str]
    model: str | None
    extractor: str


class DocumentSummarizer:
    def __init__(self, config: SummaryConfig) -> None:
        self._config = config
        self._client = self._build_client()

    @property
    def is_enabled(self) -> bool:
        return self._config.enabled

    @property
    def model(self) -> str | None:
        if self._config.llm_enabled and self._client is not None:
            return self._config.model
        return None

    def summarize(self, *, title: str, text: str) -> DocumentSummary:
        if not self._config.enabled:
            return DocumentSummary(summary="", keywords=[], topics=[], model=None, extractor="none")

        clipped = text.strip()[: max(self._config.max_chars, 800)]
        if self._config.llm_enabled and self._client is not None and self._config.api_key:
            try:
                return self._summarize_with_llm(title=title, text=clipped)
            except Exception as error:
                print(f"[Knowledge] summary_llm error error={error}", flush=True)

        return self._summarize_with_rules(title=title, text=clipped)

    def summarize_preview(self, *, title: str, text: str) -> DocumentSummary:
        summary = self.summarize(title=title, text=text)
        if summary.summary.strip():
            return summary

        clipped = text.strip()[: max(self._config.max_chars, 800)]
        return self._summarize_with_rules(title=title, text=clipped)

    def _build_client(self):
        if not self._config.llm_enabled or OpenAI is None or not self._config.api_key:
            return None
        options = {"api_key": self._config.api_key}
        if self._config.base_url:
            options["base_url"] = self._config.base_url
        return OpenAI(**options)

    def _summarize_with_llm(self, *, title: str, text: str) -> DocumentSummary:
        if self._client is None:
            raise RuntimeError("Summary LLM client is not available.")

        response = self._client.chat.completions.create(
            model=self._config.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "你是文档摘要器。请输出简洁、可检索的中文摘要，不要编造原文没有的信息。",
                },
                {
                    "role": "user",
                    "content": (
                        f"标题：{title}\n\n"
                        "请生成 120-240 字摘要，并列出 3-8 个主题关键词。"
                        "格式：摘要：...\n关键词：a, b, c\n\n"
                        f"正文：\n{text}"
                    ),
                },
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        summary, keywords = self._parse_llm_summary(content)
        if not summary:
            return self._summarize_with_rules(title=title, text=text)
        return DocumentSummary(
            summary=summary,
            keywords=keywords,
            topics=keywords[:5],
            model=self._config.model,
            extractor="llm",
        )

    def _summarize_with_rules(self, *, title: str, text: str) -> DocumentSummary:
        normalized = re.sub(r"\s+", " ", text).strip()
        summary = normalized[:360]
        keywords = self._keywords(f"{title} {text}")
        return DocumentSummary(
            summary=summary,
            keywords=keywords,
            topics=keywords[:5],
            model=None,
            extractor="rule",
        )

    def _parse_llm_summary(self, content: str) -> tuple[str, list[str]]:
        summary = content
        keywords: list[str] = []
        summary_match = re.search(r"摘要[:：]\s*(.+?)(?:\n|关键词[:：]|$)", content, re.S)
        if summary_match:
            summary = summary_match.group(1).strip()
        keyword_match = re.search(r"关键词[:：]\s*(.+)$", content, re.S)
        if keyword_match:
            keywords = [
                item.strip(" ，,;；")
                for item in re.split(r"[,，;；\n]", keyword_match.group(1))
                if item.strip(" ，,;；")
            ][:8]
        if not keywords:
            keywords = self._keywords(content)
        return summary[:500], keywords

    def _keywords(self, text: str) -> list[str]:
        terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,8}", text)
        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(term)
            if len(deduped) >= 8:
                break
        return deduped
