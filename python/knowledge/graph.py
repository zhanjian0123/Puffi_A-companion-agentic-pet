from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class ExtractedEntity:
    name: str
    type: str
    description: str | None = None
    extractor: str = "rule"
    model: str | None = None


@dataclass(slots=True)
class ExtractedRelation:
    source: str
    relation: str
    target: str
    confidence: float
    description: str | None = None
    evidence: str | None = None
    extractor: str = "rule"
    model: str | None = None


@dataclass(slots=True)
class GraphExtraction:
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]


class RuleGraphExtractor:
    _relation_words = ("调用", "读取", "写入", "使用", "依赖", "存储到", "连接", "管理", "检索", "返回", "属于", "是")
    _question_markers = (
        "？",
        "?",
        "是否",
        "是不是",
        "能否",
        "可否",
        "需不需要",
        "要不要",
        "是否正确",
        "是否违反",
    )

    def extract_chunk(self, content: str, *, max_relations: int) -> GraphExtraction:
        entities = self.extract_entities(content)
        relations = self.extract_relations(content, entities=entities, max_relations=max_relations)
        return GraphExtraction(entities=entities, relations=relations)

    def extract_query_entities(self, query: str) -> list[str]:
        names = [entity.name for entity in self.extract_entities(query)]
        for part in re.findall(r"[\u4e00-\u9fff]+", query):
            if len(part) >= 2:
                names.extend(part[index : index + 2] for index in range(len(part) - 1))
            if len(part) >= 3:
                names.extend(part[index : index + 3] for index in range(len(part) - 2))

        deduped: list[str] = []
        seen: set[str] = set()
        for name in names:
            normalized = self.normalize(name)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(name)
            if len(deduped) >= 40:
                break
        return deduped

    def extract_entities(self, text: str) -> list[ExtractedEntity]:
        found: dict[str, ExtractedEntity] = {}

        patterns = [
            (r"\b[A-Z][A-Za-z0-9_]*(?:Service|Agent|Store|Tool|Client|API|SDK|RAG)\b", "component"),
            (r"\b[a-z][a-z0-9_]*(?:_search|_tool|_service|_store|_client)\b", "function"),
            (r"\b[A-Z0-9_]{3,}\b", "constant"),
            (r"\b[\w.-]+\.(?:md|txt|py|ts|tsx|json|sqlite3)\b", "file"),
            (r"/[A-Za-z0-9_./{}-]+", "api"),
            (r"[\u4e00-\u9fff]{2,10}", "term"),
        ]

        for pattern, entity_type in patterns:
            for match in re.findall(pattern, text):
                name = str(match).strip()
                if not self._is_entity_candidate(name):
                    continue
                found.setdefault(self.normalize(name), ExtractedEntity(name=name, type=entity_type))

        return list(found.values())[:80]

    def extract_relations(
        self,
        text: str,
        *,
        entities: list[ExtractedEntity],
        max_relations: int,
    ) -> list[ExtractedRelation]:
        relations: list[ExtractedRelation] = []
        factual_segments = self._factual_segments(text)

        for segment in factual_segments:
            for match in re.finditer(r"([\u4e00-\u9fffA-Za-z0-9_.-]{2,20})(?<!不)是(?!否)([^，。；;\n]{1,24})", segment):
                source = match.group(1).strip()
                target = match.group(2).strip(" 的")
                if (
                    source
                    and target
                    and self.normalize(source) != self.normalize(target)
                    and self._is_relation_candidate(source, target)
                ):
                    relations.append(
                        ExtractedRelation(
                            source=source,
                            relation="是",
                            target=target,
                            confidence=0.7,
                        )
                    )
                    if len(relations) >= max_relations:
                        return relations

        names = [entity.name for entity in entities if len(entity.name) >= 2]
        if len(names) < 2:
            return relations

        escaped_names = sorted((re.escape(name) for name in names), key=len, reverse=True)
        name_pattern = "|".join(escaped_names[:80])
        relation_pattern = "|".join(
            re.escape(word) if word != "是" else r"(?<!不)是(?!否)"
            for word in self._relation_words
        )

        for segment in factual_segments:
            for match in re.finditer(
                rf"({name_pattern}).{{0,24}}?({relation_pattern}).{{0,24}}?({name_pattern})",
                segment,
            ):
                source, relation, target = match.group(1), match.group(2), match.group(3)
                if self.normalize(source) == self.normalize(target):
                    continue
                if not self._is_relation_candidate(source, target):
                    continue
                relations.append(
                    ExtractedRelation(
                        source=source,
                        relation=relation,
                        target=target,
                        confidence=0.75,
                    )
                )
                if len(relations) >= max_relations:
                    return relations

        return relations

    def normalize(self, name: str) -> str:
        return re.sub(r"\s+", "", name.strip().lower())

    def _is_entity_candidate(self, name: str) -> bool:
        if len(name) < 2:
            return False
        if name.isdigit():
            return False
        if name in {"这个", "那个", "什么", "怎么", "为什么", "一般来说", "本地知识库"}:
            return False
        return True

    def _factual_segments(self, text: str) -> list[str]:
        segments = re.split(r"[\n。；;！!]+", text)
        return [
            segment.strip()
            for segment in segments
            if segment.strip() and not self._is_question_like(segment)
        ]

    def _is_question_like(self, text: str) -> bool:
        return any(marker in text for marker in self._question_markers)

    def _is_relation_candidate(self, source: str, target: str) -> bool:
        if self._is_question_like(source) or self._is_question_like(target):
            return False
        if target.startswith(("否", "不", "没", "未")):
            return False
        if source.endswith(("是否", "能否", "可否")):
            return False
        return True
