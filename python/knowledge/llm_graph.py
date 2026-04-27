from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from knowledge.graph import ExtractedEntity, ExtractedRelation, GraphExtraction, RuleGraphExtractor

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None


@dataclass(slots=True)
class LLMGraphConfig:
    enabled: bool
    model: str
    api_key: str | None
    base_url: str | None
    max_entities_per_chunk: int
    max_relations_per_chunk: int
    min_confidence: float
    max_chars: int


class LLMGraphExtractor:
    def __init__(self, config: LLMGraphConfig) -> None:
        self._config = config
        self._client = self._build_client()
        self._validator = RuleGraphExtractor()

    @property
    def is_available(self) -> bool:
        return self._config.enabled and self._client is not None and bool(self._config.api_key)

    @property
    def model(self) -> str:
        return self._config.model

    def extract_chunk(self, content: str, *, max_relations: int) -> GraphExtraction:
        if not self.is_available or self._client is None:
            raise RuntimeError("LLM graph extractor is not available.")

        text = content.strip()[: max(self._config.max_chars, 500)]
        if not text:
            return GraphExtraction(entities=[], relations=[])

        response = self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是严格的知识图谱抽取器。只抽取文本中明确陈述的确定事实。"
                        "不要抽取疑问句、测试题、假设、反问、未给出答案的问题。"
                        "不要把否定、禁忌或“是否/是不是/能否”误抽成正向“是”关系。"
                        "每条关系必须包含能在原文中找到的 evidence。"
                        "只输出 JSON，不要输出 Markdown。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        text,
                        max_entities=self._config.max_entities_per_chunk,
                        max_relations=min(max_relations, self._config.max_relations_per_chunk),
                    ),
                },
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        payload = self._parse_json(raw)
        return self._to_graph_extraction(payload)

    def _build_client(self):
        if not self._config.enabled or OpenAI is None or not self._config.api_key:
            return None

        options = {"api_key": self._config.api_key}
        if self._config.base_url:
            options["base_url"] = self._config.base_url
        return OpenAI(**options)

    def _build_prompt(self, text: str, *, max_entities: int, max_relations: int) -> str:
        return (
            "请从下面文本抽取知识图谱。\n"
            f"最多抽取 {max_entities} 个实体和 {max_relations} 条关系。\n"
            "输出格式必须是：\n"
            "{\n"
            '  "entities": [\n'
            '    {"name": "实体名", "type": "概念/组件/人物/药材/症状/文件/API/技术/其他", "description": "简短说明"}\n'
            "  ],\n"
            '  "relations": [\n'
            '    {"source": "源实体", "relation": "关系", "target": "目标实体", '
            '"description": "关系说明", "evidence": "原文证据", "confidence": 0.0}\n'
            "  ]\n"
            "}\n"
            "过滤规则：\n"
            "- 不抽取包含“是否/是不是/能否/可否/？/?”的疑问关系。\n"
            "- 如果原文是测试题或问题，只能抽取文本中明确给出的答案/结论。\n"
            "- source、relation、target 必须简洁，不能是整句。\n\n"
            f"文本：\n{text}"
        )

    def _parse_json(self, raw: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.S)
            if not match:
                raise
            parsed = json.loads(match.group(0))

        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _to_graph_extraction(self, payload: dict[str, Any]) -> GraphExtraction:
        entities = self._parse_entities(payload.get("entities"))
        relations = self._parse_relations(payload.get("relations"))
        return GraphExtraction(entities=entities, relations=relations)

    def _parse_entities(self, value: Any) -> list[ExtractedEntity]:
        if not isinstance(value, list):
            return []

        entities: list[ExtractedEntity] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            name = self._clean(item.get("name"), limit=80)
            entity_type = self._clean(item.get("type"), limit=30) or "term"
            description = self._clean(item.get("description"), limit=240) or None
            normalized = self._validator.normalize(name)
            if not normalized or normalized in seen or not self._validator._is_entity_candidate(name):
                continue
            seen.add(normalized)
            entities.append(
                ExtractedEntity(
                    name=name,
                    type=entity_type,
                    description=description,
                    extractor="llm",
                    model=self._config.model,
                )
            )
            if len(entities) >= self._config.max_entities_per_chunk:
                break

        return entities

    def _parse_relations(self, value: Any) -> list[ExtractedRelation]:
        if not isinstance(value, list):
            return []

        relations: list[ExtractedRelation] = []
        seen: set[tuple[str, str, str]] = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            source = self._clean(item.get("source"), limit=80)
            relation = self._clean(item.get("relation"), limit=24)
            target = self._clean(item.get("target"), limit=120)
            description = self._clean(item.get("description"), limit=280) or None
            evidence = self._clean(item.get("evidence"), limit=360) or None
            confidence = self._float(item.get("confidence"), default=0.0)
            key = (
                self._validator.normalize(source),
                self._validator.normalize(relation),
                self._validator.normalize(target),
            )

            if not source or not relation or not target or not evidence:
                continue
            if key in seen or key[0] == key[2]:
                continue
            if confidence < self._config.min_confidence:
                continue
            if not self._validator._is_relation_candidate(source, target):
                continue
            if self._validator._is_question_like(relation) or self._validator._is_question_like(evidence):
                continue

            seen.add(key)
            relations.append(
                ExtractedRelation(
                    source=source,
                    relation=relation,
                    target=target,
                    confidence=confidence,
                    description=description,
                    evidence=evidence,
                    extractor="llm",
                    model=self._config.model,
                )
            )
            if len(relations) >= self._config.max_relations_per_chunk:
                break

        return relations

    def _clean(self, value: Any, *, limit: int) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split()).strip()[:limit]

    def _float(self, value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
