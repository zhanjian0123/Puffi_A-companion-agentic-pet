from __future__ import annotations

import asyncio
from datetime import datetime
import hashlib
from pathlib import Path
import re
from time import perf_counter

from config import settings
from knowledge.converter import convert_to_markdown
from knowledge.embeddings import EmbeddingClient, EmbeddingConfig
from knowledge.graph import RuleGraphExtractor
from knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeImportResult,
    KnowledgeRelation,
    KnowledgeSearchResult,
    KnowledgeStatus,
    KnowledgeUploadResult,
)
from knowledge.store import KnowledgeStore


SUPPORTED_SUFFIXES = {".md", ".txt"}


class KnowledgeService:
    def __init__(
        self,
        *,
        enabled: bool,
        document_dir: str,
        index_db_path: str,
        chunk_max_chars: int,
        top_k: int,
        max_context_chars: int,
        auto_import_on_query: bool,
        embedding_client: EmbeddingClient,
        keyword_weight: float,
        vector_weight: float,
        graph_enabled: bool,
        graph_max_relations_per_chunk: int,
        graph_weight: float,
        graph_context_limit: int,
        upload_enabled: bool,
        upload_dir: str,
        converted_dir: str,
        upload_max_mb: int,
        upload_allowed_extensions: str,
    ) -> None:
        self._enabled = enabled
        self._document_dir = Path(document_dir).expanduser().resolve()
        self._upload_enabled = upload_enabled
        self._upload_dir = Path(upload_dir).expanduser().resolve()
        self._converted_dir = Path(converted_dir).expanduser().resolve()
        self._upload_max_bytes = max(upload_max_mb, 1) * 1024 * 1024
        self._upload_allowed_extensions = self._parse_extensions(upload_allowed_extensions)
        self._chunk_max_chars = max(chunk_max_chars, 300)
        self._top_k = max(top_k, 1)
        self._max_context_chars = max(max_context_chars, 1000)
        self._auto_import_on_query = auto_import_on_query
        self._embedding_client = embedding_client
        self._keyword_weight = max(keyword_weight, 0.0)
        self._vector_weight = max(vector_weight, 0.0)
        self._graph_enabled = graph_enabled
        self._graph_max_relations_per_chunk = max(graph_max_relations_per_chunk, 1)
        self._graph_weight = max(graph_weight, 0.0)
        self._graph_context_limit = max(graph_context_limit, 0)
        self._graph_extractor = RuleGraphExtractor()
        self._store = KnowledgeStore(
            db_path=index_db_path,
            document_dir=str(self._document_dir),
            enabled=enabled,
        )

    async def import_documents(self, path: str | None = None) -> KnowledgeImportResult:
        if not self._enabled:
            return KnowledgeImportResult(0, 0, 1, ["知识库未启用。"])

        result = await asyncio.to_thread(self._import_documents_sync, path)
        if result.imported and self._embedding_client.is_available:
            await self._ensure_embeddings()
        return result

    async def upload_document(self, *, filename: str, content: bytes) -> KnowledgeUploadResult:
        if not self._enabled:
            raise ValueError("知识库未启用。")
        if not self._upload_enabled:
            raise ValueError("知识库上传未启用。")
        if not filename:
            raise ValueError("上传文件缺少文件名。")
        if not content:
            raise ValueError("上传文件为空。")
        if len(content) > self._upload_max_bytes:
            max_mb = self._upload_max_bytes // (1024 * 1024)
            raise ValueError(f"上传文件超过大小限制：{max_mb}MB。")

        suffix = Path(filename).suffix.lower()
        if suffix not in self._upload_allowed_extensions:
            allowed = ", ".join(sorted(self._upload_allowed_extensions))
            raise ValueError(f"不支持的文件类型：{suffix or '(无扩展名)'}。允许类型：{allowed}")

        return await asyncio.to_thread(self._upload_document_sync, filename, content)

    async def query(self, query: str, *, top_k: int | None = None) -> list[KnowledgeSearchResult]:
        if not self._enabled:
            return []

        if self._auto_import_on_query:
            import_result = await self.import_documents()
            if import_result.imported or import_result.failed:
                print(
                    "[Knowledge] auto_import "
                    f"imported={import_result.imported} skipped={import_result.skipped} failed={import_result.failed}",
                    flush=True,
                )

        limit = top_k or self._top_k
        query_embedding: list[float] | None = None
        embedding_model: str | None = None
        graph_entities: list[str] = []

        if self._embedding_client.is_available:
            try:
                await self._ensure_embeddings()
                started_at = perf_counter()
                query_embedding = await self._embedding_client.embed_query(query)
                embedding_model = self._embedding_client.model
                elapsed_ms = (perf_counter() - started_at) * 1000
                print(
                    f"[Knowledge] query_embedding model={embedding_model} elapsed={elapsed_ms:.1f}ms",
                    flush=True,
                )
            except Exception as error:
                print(f"[Knowledge] embedding query error error={error}", flush=True)
                query_embedding = None
                embedding_model = None

        if self._graph_enabled:
            graph_entities = self._graph_extractor.extract_query_entities(query)
            if graph_entities:
                print(f"[Knowledge] graph_query entities={graph_entities[:8]}", flush=True)

        return await asyncio.to_thread(
            self._store.search,
            query,
            top_k=limit,
            max_context_chars=self._max_context_chars,
            query_embedding=query_embedding,
            embedding_model=embedding_model,
            keyword_weight=self._keyword_weight,
            vector_weight=self._vector_weight,
            graph_enabled=self._graph_enabled,
            graph_entities=graph_entities,
            graph_weight=self._graph_weight,
            graph_context_limit=self._graph_context_limit,
        )

    async def list_documents(self) -> list[KnowledgeDocument]:
        return await asyncio.to_thread(self._store.list_documents)

    async def list_entities(self, *, limit: int = 100) -> list[KnowledgeEntity]:
        return await asyncio.to_thread(self._store.list_entities, limit=limit)

    async def list_relations(self, *, query: str | None = None, limit: int = 100) -> list[KnowledgeRelation]:
        return await asyncio.to_thread(self._store.list_relations, query=query, limit=limit)

    async def status(self) -> KnowledgeStatus:
        return await asyncio.to_thread(self._store.status)

    def _import_documents_sync(self, path: str | None) -> KnowledgeImportResult:
        try:
            target = self._resolve_import_target(path)
        except ValueError as error:
            return KnowledgeImportResult(0, 0, 1, [str(error)])

        files = self._collect_files(target)

        imported = 0
        skipped = 0
        failed = 0
        messages: list[str] = []

        if not files:
            return KnowledgeImportResult(0, 0, 0, [f"没有找到可导入的 md/txt 文件：{target}"])

        for file_path in files:
            try:
                relative_path = self._relative_document_path(file_path)
                file_hash = self._hash_file(file_path)
                if self._store.document_is_current(
                    path=relative_path,
                    file_hash=file_hash,
                    require_graph=self._graph_enabled,
                ):
                    skipped += 1
                    messages.append(f"跳过未变化文件：{relative_path}")
                    continue

                text = file_path.read_text(encoding="utf-8")
                chunks = self._chunk_text(text)
                if not chunks:
                    skipped += 1
                    messages.append(f"跳过空文件：{relative_path}")
                    continue

                keywords = self._extract_keywords(text)
                entities = self._extract_entities(text)
                graph_chunks = self._extract_graph_chunks(chunks) if self._graph_enabled else None
                self._store.upsert_document(
                    path=relative_path,
                    title=file_path.stem,
                    file_hash=file_hash,
                    size=file_path.stat().st_size,
                    chunks=chunks,
                    keywords=keywords,
                    entities=entities,
                    graph_chunks=graph_chunks,
                )
                imported += 1
                messages.append(f"已导入：{relative_path} ({len(chunks)} chunks)")
                print(f"[Knowledge] imported path={relative_path} chunks={len(chunks)}", flush=True)
            except Exception as error:
                failed += 1
                messages.append(f"导入失败：{file_path} error={error}")
                print(f"[Knowledge] import error path={file_path} error={error}", flush=True)

        return KnowledgeImportResult(imported, skipped, failed, messages)

    def _upload_document_sync(self, filename: str, content: bytes) -> KnowledgeUploadResult:
        started_at = perf_counter()
        digest = hashlib.sha256(content).hexdigest()
        hash_suffix = digest[:8]
        source_filename = self._hashed_filename(filename, hash_suffix)
        markdown_filename = f"{Path(source_filename).stem}.md"
        source_path = self._upload_dir / source_filename
        markdown_path = self._converted_dir / markdown_filename

        print(
            f"[Knowledge] upload start filename={filename} size={len(content)} hash={hash_suffix}",
            flush=True,
        )

        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._converted_dir.mkdir(parents=True, exist_ok=True)

        source_path.write_bytes(content)
        print(f"[Knowledge] upload saved source={source_path}", flush=True)

        print(f"[Knowledge] convert start source={source_path}", flush=True)
        markdown = convert_to_markdown(source_path).strip()
        if not markdown:
            raise ValueError("转换后的 Markdown 内容为空。")

        markdown_text = self._format_uploaded_markdown(
            source_filename=source_filename,
            original_filename=filename,
            markdown=markdown,
        )
        markdown_path.write_text(markdown_text, encoding="utf-8")
        print(
            f"[Knowledge] convert success markdown={markdown_path} chars={len(markdown_text)}",
            flush=True,
        )

        import_result = self._import_documents_sync(str(markdown_path))
        elapsed_ms = (perf_counter() - started_at) * 1000
        print(
            "[Knowledge] upload_import "
            f"imported={import_result.imported} skipped={import_result.skipped} "
            f"failed={import_result.failed} elapsed={elapsed_ms:.1f}ms",
            flush=True,
        )

        return KnowledgeUploadResult(
            filename=filename,
            source_path=str(source_path),
            markdown_path=str(markdown_path),
            imported=import_result.imported,
            skipped=import_result.skipped,
            failed=import_result.failed,
            messages=import_result.messages,
        )

    async def _ensure_embeddings(self) -> None:
        if not self._embedding_client.is_available:
            return

        missing = await asyncio.to_thread(
            self._store.chunks_missing_embeddings,
            model=self._embedding_client.model,
        )
        if not missing:
            return

        started_at = perf_counter()
        print(
            f"[Knowledge] embedding start chunks={len(missing)} model={self._embedding_client.model}",
            flush=True,
        )

        try:
            texts = [content for _, content in missing]
            vectors = await self._embedding_client.embed_texts(texts)
            chunk_embeddings = [
                (chunk_id, vector)
                for (chunk_id, _), vector in zip(missing, vectors, strict=False)
                if vector
            ]
            await asyncio.to_thread(
                self._store.save_embeddings,
                model=self._embedding_client.model,
                embeddings=chunk_embeddings,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                f"[Knowledge] embedding success chunks={len(chunk_embeddings)} elapsed={elapsed_ms:.1f}ms",
                flush=True,
            )
        except Exception as error:
            print(f"[Knowledge] embedding error error={error}", flush=True)

    def _resolve_import_target(self, path: str | None) -> Path:
        if not path:
            return self._document_dir

        target = Path(path).expanduser()
        if not target.is_absolute():
            target = self._document_dir / target
        resolved = target.resolve()
        try:
            resolved.relative_to(self._document_dir)
        except ValueError as error:
            raise ValueError(f"知识库导入路径必须位于 {self._document_dir} 内。") from error
        return resolved

    def _collect_files(self, target: Path) -> list[Path]:
        if target.is_file():
            return [target] if target.suffix.lower() in SUPPORTED_SUFFIXES else []

        if not target.exists():
            return []

        return sorted(
            file_path
            for file_path in target.rglob("*")
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_SUFFIXES
        )

    def _relative_document_path(self, file_path: Path) -> str:
        try:
            return str(file_path.relative_to(self._document_dir))
        except ValueError:
            return str(file_path)

    def _hash_file(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _chunk_text(self, text: str) -> list[str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        blocks = self._split_markdown_blocks(normalized)
        chunks: list[str] = []
        current = ""

        for block in blocks:
            if not block:
                continue

            if len(block) > self._chunk_max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_long_block(block))
                continue

            candidate = f"{current}\n\n{block}".strip() if current else block
            if len(candidate) > self._chunk_max_chars and current:
                chunks.append(current.strip())
                current = block
            else:
                current = candidate

        if current:
            chunks.append(current.strip())

        return chunks

    def _split_markdown_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        current: list[str] = []

        for line in text.splitlines():
            if line.startswith("#") and current:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            if not line.strip() and current:
                blocks.append("\n".join(current).strip())
                current = []
                continue
            current.append(line)

        if current:
            blocks.append("\n".join(current).strip())

        return blocks

    def _split_long_block(self, block: str) -> list[str]:
        chunks: list[str] = []
        cursor = 0
        while cursor < len(block):
            chunks.append(block[cursor : cursor + self._chunk_max_chars].strip())
            cursor += self._chunk_max_chars
        return [chunk for chunk in chunks if chunk]

    def _extract_keywords(self, text: str) -> list[str]:
        terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", text)
        return self._dedupe_terms(terms, limit=80)

    def _extract_graph_chunks(self, chunks: list[str]):
        graph_chunks = []
        relation_count = 0
        for chunk in chunks:
            extraction = self._graph_extractor.extract_chunk(
                chunk,
                max_relations=self._graph_max_relations_per_chunk,
            )
            relation_count += len(extraction.relations)
            graph_chunks.append((extraction.entities, extraction.relations))

        if relation_count:
            print(
                f"[Knowledge] graph_extract chunks={len(chunks)} relations={relation_count}",
                flush=True,
            )

        return graph_chunks

    def _extract_entities(self, text: str) -> list[str]:
        terms = re.findall(r"[A-Z][A-Za-z0-9_]*(?:Service|Agent|Store|Tool|API|SDK|RAG)|[\u4e00-\u9fff]{2,8}", text)
        return self._dedupe_terms(terms, limit=80)

    def _dedupe_terms(self, terms: list[str], *, limit: int) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for term in terms:
            cleaned = term.strip()
            if not cleaned or cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            deduped.append(cleaned)
            if len(deduped) >= limit:
                break
        return deduped

    def _parse_extensions(self, value: str) -> set[str]:
        extensions = set()
        for item in value.split(","):
            extension = item.strip().lower()
            if not extension:
                continue
            extensions.add(extension if extension.startswith(".") else f".{extension}")
        return extensions or {".md", ".txt"}

    def _hashed_filename(self, filename: str, hash_suffix: str) -> str:
        path = Path(filename)
        suffix = path.suffix.lower()
        stem = path.stem or "document"
        safe_stem = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", stem).strip(".-")
        if not safe_stem:
            safe_stem = "document"
        return f"{safe_stem}-{hash_suffix}{suffix}"

    def _format_uploaded_markdown(self, *, source_filename: str, original_filename: str, markdown: str) -> str:
        uploaded_at = datetime.now().isoformat(timespec="seconds")
        return (
            "---\n"
            f"source_file: {source_filename}\n"
            f"original_file: {original_filename}\n"
            f"uploaded_at: {uploaded_at}\n"
            "---\n\n"
            f"{markdown}\n"
        )


_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService(
            enabled=settings.knowledge_enabled,
            document_dir=settings.knowledge_document_dir,
            index_db_path=settings.knowledge_index_db_path,
            chunk_max_chars=settings.knowledge_chunk_max_chars,
            top_k=settings.knowledge_top_k,
            max_context_chars=settings.knowledge_max_context_chars,
            auto_import_on_query=settings.knowledge_auto_import_on_query,
            embedding_client=EmbeddingClient(
                EmbeddingConfig(
                    enabled=settings.knowledge_embedding_enabled,
                    model=settings.knowledge_embedding_model,
                    api_key=settings.knowledge_embedding_api_key,
                    base_url=settings.knowledge_embedding_base_url,
                    dimensions=settings.knowledge_embedding_dimensions,
                )
            ),
            keyword_weight=settings.knowledge_keyword_weight,
            vector_weight=settings.knowledge_vector_weight,
            graph_enabled=settings.knowledge_graph_enabled,
            graph_max_relations_per_chunk=settings.knowledge_graph_max_relations_per_chunk,
            graph_weight=settings.knowledge_graph_weight,
            graph_context_limit=settings.knowledge_graph_context_limit,
            upload_enabled=settings.knowledge_upload_enabled,
            upload_dir=settings.knowledge_upload_dir,
            converted_dir=settings.knowledge_converted_dir,
            upload_max_mb=settings.knowledge_upload_max_mb,
            upload_allowed_extensions=settings.knowledge_upload_allowed_extensions,
        )
    return _knowledge_service
