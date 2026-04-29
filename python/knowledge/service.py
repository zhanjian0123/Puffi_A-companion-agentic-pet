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
from knowledge.graph import GraphExtraction, RuleGraphExtractor
from knowledge.llm_graph import LLMGraphConfig, LLMGraphExtractor
from knowledge.models import (
    KnowledgeDeleteResult,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeIndexingState,
    KnowledgeIndexStartResult,
    KnowledgeImportResult,
    KnowledgeRelation,
    KnowledgeSearchResult,
    KnowledgeStatus,
    KnowledgeUploadResult,
)
from knowledge.summarizer import DocumentSummarizer, SummaryConfig
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
        graph_llm_extractor: LLMGraphExtractor,
        graph_extractor_mode: str,
        graph_llm_fallback_to_rule: bool,
        summarizer: DocumentSummarizer,
        summary_on_import: bool,
        summary_embedding_enabled: bool,
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
        self._graph_llm_extractor = graph_llm_extractor
        self._graph_extractor_mode = self._normalize_graph_extractor_mode(graph_extractor_mode)
        self._graph_llm_fallback_to_rule = graph_llm_fallback_to_rule
        self._last_graph_extractor_name: str | None = None
        self._last_graph_model: str | None = None
        self._graph_had_llm_error = False
        self._summarizer = summarizer
        self._summary_on_import = summary_on_import
        self._summary_embedding_enabled = summary_embedding_enabled
        self._indexing_state = KnowledgeIndexingState(messages=[])
        self._indexing_task: asyncio.Task[None] | None = None
        self._indexing_lock = asyncio.Lock()
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
            await self._ensure_graph_embeddings()
            await self._ensure_summary_embeddings()
        return result

    async def start_background_import(
        self,
        *,
        path: str | None = None,
        reason: str,
    ) -> KnowledgeIndexStartResult:
        if not self._enabled:
            state = self.indexing_state()
            return KnowledgeIndexStartResult(started=False, state=state, message="知识库未启用。")

        async with self._indexing_lock:
            if self._indexing_task and not self._indexing_task.done():
                return KnowledgeIndexStartResult(
                    started=False,
                    state=self.indexing_state(),
                    message="知识库索引任务已在运行。",
                )

            self._indexing_state = KnowledgeIndexingState(
                status="running",
                reason=reason,
                started_at=datetime.now().isoformat(timespec="seconds"),
                finished_at=None,
                imported=0,
                skipped=0,
                failed=0,
                messages=[],
                last_error=None,
            )
            self._indexing_task = asyncio.create_task(self._run_background_import(path=path, reason=reason))
            return KnowledgeIndexStartResult(
                started=True,
                state=self.indexing_state(),
                message="知识库索引已在后台启动。",
            )

    def indexing_state(self) -> KnowledgeIndexingState:
        messages = self._indexing_state.messages or []
        return KnowledgeIndexingState(
            status=self._indexing_state.status,
            reason=self._indexing_state.reason,
            started_at=self._indexing_state.started_at,
            finished_at=self._indexing_state.finished_at,
            imported=self._indexing_state.imported,
            skipped=self._indexing_state.skipped,
            failed=self._indexing_state.failed,
            messages=list(messages),
            last_error=self._indexing_state.last_error,
        )

    async def _run_background_import(self, *, path: str | None, reason: str) -> None:
        try:
            result = await self.import_documents(path)
            self._indexing_state = KnowledgeIndexingState(
                status="failed" if result.failed else "done",
                reason=reason,
                started_at=self._indexing_state.started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                imported=result.imported,
                skipped=result.skipped,
                failed=result.failed,
                messages=result.messages,
                last_error=None if not result.failed else "; ".join(result.messages[-3:]),
            )
            print(
                "[Knowledge] background_import "
                f"reason={reason} imported={result.imported} skipped={result.skipped} failed={result.failed}",
                flush=True,
            )
        except Exception as error:
            self._indexing_state = KnowledgeIndexingState(
                status="failed",
                reason=reason,
                started_at=self._indexing_state.started_at,
                finished_at=datetime.now().isoformat(timespec="seconds"),
                imported=0,
                skipped=0,
                failed=1,
                messages=[],
                last_error=str(error),
            )
            print(f"[Knowledge] background_import error reason={reason} error={error}", flush=True)

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

    async def delete_document(self, path: str) -> KnowledgeDeleteResult:
        if not self._enabled:
            return KnowledgeDeleteResult(
                deleted=False,
                path=path,
                chunks_deleted=0,
                relations_deleted=0,
                summaries_deleted=0,
                orphan_entities_deleted=0,
                message="知识库未启用。",
            )

        return await asyncio.to_thread(self._delete_document_sync, path)

    async def query(
        self,
        query: str,
        *,
        top_k: int | None = None,
        debug: bool = False,
    ) -> list[KnowledgeSearchResult]:
        if not self._enabled:
            return []

        if self._auto_import_on_query and self._indexing_state.status in {"idle", "failed"}:
            await self.start_background_import(reason="query_auto_import")

        limit = top_k or self._top_k
        query_embedding: list[float] | None = None
        embedding_model: str | None = None
        graph_entities: list[str] = []

        if self._embedding_client.is_available:
            try:
                await self._ensure_embeddings()
                await self._ensure_graph_embeddings()
                await self._ensure_summary_embeddings()
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
            include_debug_context=debug,
            global_query=self._is_global_query(query),
        )

    async def list_documents(self) -> list[KnowledgeDocument]:
        return await asyncio.to_thread(self._store.list_documents)

    async def list_entities(self, *, limit: int = 100) -> list[KnowledgeEntity]:
        return await asyncio.to_thread(self._store.list_entities, limit=limit)

    async def list_relations(self, *, query: str | None = None, limit: int = 100) -> list[KnowledgeRelation]:
        return await asyncio.to_thread(self._store.list_relations, query=query, limit=limit)

    async def status(self) -> KnowledgeStatus:
        status = await asyncio.to_thread(self._store.status)
        status.indexing = self.indexing_state()
        return status

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
                    graph_extractor=self._current_graph_extractor_name(),
                    graph_model=self._current_graph_model(),
                    require_summary=self._summary_required(),
                    summary_extractor=self._current_summary_extractor_name(),
                    summary_model=self._current_summary_model(),
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
                    graph_extractor=self._last_graph_extractor_name or self._current_graph_extractor_name(),
                    graph_model=self._last_graph_model,
                )
                if self._summary_required():
                    summary = self._summarizer.summarize(title=file_path.stem, text=text)
                    self._store.upsert_document_summary(
                        path=relative_path,
                        summary=summary.summary,
                        keywords=summary.keywords,
                        topics=summary.topics,
                        extractor=summary.extractor,
                        model=summary.model,
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
        upload_summary = self._summarize_uploaded_markdown(
            title=Path(filename).stem,
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
            summary=upload_summary.summary,
            keywords=upload_summary.keywords,
        )

    def _delete_document_sync(self, path: str) -> KnowledgeDeleteResult:
        try:
            target = self._resolve_document_file(path)
        except ValueError as error:
            return KnowledgeDeleteResult(
                deleted=False,
                path=path,
                chunks_deleted=0,
                relations_deleted=0,
                summaries_deleted=0,
                orphan_entities_deleted=0,
                message=str(error),
            )

        relative_path = str(target.relative_to(self._document_dir))
        try:
            target.unlink()
        except OSError as error:
            return KnowledgeDeleteResult(
                deleted=False,
                path=relative_path,
                chunks_deleted=0,
                relations_deleted=0,
                summaries_deleted=0,
                orphan_entities_deleted=0,
                message=f"删除文件失败：{error}",
            )

        result = self._store.delete_document(relative_path)
        if not result.deleted:
            return KnowledgeDeleteResult(
                deleted=True,
                path=relative_path,
                chunks_deleted=0,
                relations_deleted=0,
                summaries_deleted=0,
                orphan_entities_deleted=0,
                message="已删除知识库文件，但索引中没有找到该文档。",
            )

        print(
            "[Knowledge] delete_document "
            f"path={relative_path} chunks={result.chunks_deleted} "
            f"relations={result.relations_deleted} summaries={result.summaries_deleted} "
            f"orphan_entities={result.orphan_entities_deleted}",
            flush=True,
        )
        return result

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

    async def _ensure_graph_embeddings(self) -> None:
        if not self._graph_enabled or not self._embedding_client.is_available:
            return

        missing = await asyncio.to_thread(
            self._store.graph_items_missing_embeddings,
            model=self._embedding_client.model,
        )
        if not missing:
            return

        started_at = perf_counter()
        print(
            f"[Knowledge] graph_embedding start items={len(missing)} model={self._embedding_client.model}",
            flush=True,
        )

        try:
            texts = [text for _, _, text in missing]
            vectors = await self._embedding_client.embed_texts(texts)
            graph_embeddings = [
                (kind, item_id, vector)
                for (kind, item_id, _), vector in zip(missing, vectors, strict=False)
                if vector
            ]
            await asyncio.to_thread(
                self._store.save_graph_embeddings,
                model=self._embedding_client.model,
                embeddings=graph_embeddings,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                f"[Knowledge] graph_embedding success items={len(graph_embeddings)} elapsed={elapsed_ms:.1f}ms",
                flush=True,
            )
        except Exception as error:
            print(f"[Knowledge] graph_embedding error error={error}", flush=True)

    async def _ensure_summary_embeddings(self) -> None:
        if (
            not self._summary_embedding_enabled
            or not self._summarizer.is_enabled
            or not self._embedding_client.is_available
        ):
            return

        missing = await asyncio.to_thread(
            self._store.document_summaries_missing_embeddings,
            model=self._embedding_client.model,
        )
        if not missing:
            return

        started_at = perf_counter()
        print(
            f"[Knowledge] summary_embedding start documents={len(missing)} model={self._embedding_client.model}",
            flush=True,
        )

        try:
            texts = [text for _, text in missing]
            vectors = await self._embedding_client.embed_texts(texts)
            summary_embeddings = [
                (document_id, vector)
                for (document_id, _), vector in zip(missing, vectors, strict=False)
                if vector
            ]
            await asyncio.to_thread(
                self._store.save_document_summary_embeddings,
                model=self._embedding_client.model,
                embeddings=summary_embeddings,
            )
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(
                f"[Knowledge] summary_embedding success documents={len(summary_embeddings)} elapsed={elapsed_ms:.1f}ms",
                flush=True,
            )
        except Exception as error:
            print(f"[Knowledge] summary_embedding error error={error}", flush=True)

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

    def _resolve_document_file(self, path: str) -> Path:
        cleaned = path.strip()
        if not cleaned:
            raise ValueError("删除失败：路径不能为空。")

        requested = Path(cleaned).expanduser()
        if requested.is_absolute():
            raise ValueError("删除失败：请提供知识库文档目录内的相对路径。")

        target = (self._document_dir / requested).resolve()
        try:
            target.relative_to(self._document_dir)
        except ValueError as error:
            raise ValueError("删除失败：路径不能超出知识库文档目录。") from error

        if target.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError("删除失败：只允许删除 .md 或 .txt 知识库文档。")
        if not target.exists():
            raise ValueError(f"删除失败：知识库文件不存在：{cleaned}")
        if not target.is_file():
            raise ValueError("删除失败：只能删除具体文件，不能删除目录。")

        return target

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
        llm_relation_count = 0
        rule_relation_count = 0
        llm_entity_count = 0
        rule_entity_count = 0
        self._graph_had_llm_error = False
        for chunk in chunks:
            extraction = self._extract_graph_chunk(chunk)
            relation_count += len(extraction.relations)
            llm_entity_count += sum(1 for entity in extraction.entities if entity.extractor == "llm")
            rule_entity_count += sum(1 for entity in extraction.entities if entity.extractor != "llm")
            if extraction.relations and any(relation.extractor == "llm" for relation in extraction.relations):
                llm_relation_count += len(extraction.relations)
            else:
                rule_relation_count += len(extraction.relations)
            graph_chunks.append((extraction.entities, extraction.relations))

        if llm_relation_count or llm_entity_count:
            self._last_graph_extractor_name = self._graph_extractor_mode
            self._last_graph_model = self._current_graph_model()
        elif rule_relation_count or rule_entity_count:
            self._last_graph_extractor_name = "rule"
            self._last_graph_model = None
        elif self._graph_had_llm_error:
            self._last_graph_extractor_name = "rule"
            self._last_graph_model = None
        else:
            self._last_graph_extractor_name = self._current_graph_extractor_name()
            self._last_graph_model = self._current_graph_model()

        if relation_count:
            print(
                "[Knowledge] graph_extract "
                f"extractor={self._current_graph_extractor_name()} model={self._current_graph_model() or '-'} "
                f"chunks={len(chunks)} relations={relation_count} "
                f"llm_relations={llm_relation_count} rule_relations={rule_relation_count}",
                flush=True,
            )

        return graph_chunks

    def _extract_graph_chunk(self, chunk: str):
        if self._should_use_llm_graph():
            try:
                extraction = self._graph_llm_extractor.extract_chunk(
                    chunk,
                    max_relations=self._graph_max_relations_per_chunk,
                )
                if extraction.entities or extraction.relations:
                    return extraction
                if self._graph_extractor_mode == "llm":
                    return extraction
            except Exception as error:
                print(f"[Knowledge] graph_llm error error={error}", flush=True)
                self._graph_had_llm_error = True
                if self._graph_extractor_mode == "llm" or not self._graph_llm_fallback_to_rule:
                    return GraphExtraction(entities=[], relations=[])

        return self._graph_extractor.extract_chunk(
            chunk,
            max_relations=self._graph_max_relations_per_chunk,
        )

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

    def _normalize_graph_extractor_mode(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"rule", "llm", "hybrid"}:
            return normalized
        return "hybrid"

    def _should_use_llm_graph(self) -> bool:
        if self._graph_extractor_mode == "rule":
            return False
        return self._graph_llm_extractor.is_available

    def _current_graph_extractor_name(self) -> str | None:
        if not self._graph_enabled:
            return None
        if self._should_use_llm_graph():
            return self._graph_extractor_mode
        return "rule"

    def _current_graph_model(self) -> str | None:
        if self._should_use_llm_graph():
            return self._graph_llm_extractor.model
        return None

    def _summary_required(self) -> bool:
        return self._summarizer.is_enabled and self._summary_on_import

    def _current_summary_extractor_name(self) -> str | None:
        if not self._summary_required():
            return None
        return "llm" if self._summarizer.model else "rule"

    def _current_summary_model(self) -> str | None:
        if not self._summary_required():
            return None
        return self._summarizer.model

    def _is_global_query(self, query: str) -> bool:
        return any(
            keyword in query
            for keyword in (
                "整体",
                "全部",
                "总结",
                "梳理",
                "核心",
                "体系",
                "架构",
                "流程",
                "有哪些",
                "对比",
                "优缺点",
                "怎么设计",
            )
        )

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

    def _summarize_uploaded_markdown(self, *, title: str, markdown: str):
        normalized = re.sub(r"\s+", " ", markdown).strip()
        return self._summarizer.summarize_preview(title=title, text=normalized)


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
            graph_llm_extractor=LLMGraphExtractor(
                LLMGraphConfig(
                    enabled=settings.knowledge_graph_llm_enabled,
                    model=settings.knowledge_graph_llm_model,
                    api_key=settings.knowledge_graph_llm_api_key,
                    base_url=settings.knowledge_graph_llm_base_url,
                    max_entities_per_chunk=settings.knowledge_graph_llm_max_entities_per_chunk,
                    max_relations_per_chunk=settings.knowledge_graph_llm_max_relations_per_chunk,
                    min_confidence=settings.knowledge_graph_llm_min_confidence,
                    max_chars=settings.knowledge_graph_llm_max_chars,
                )
            ),
            graph_extractor_mode=settings.knowledge_graph_extractor,
            graph_llm_fallback_to_rule=settings.knowledge_graph_llm_fallback_to_rule,
            summarizer=DocumentSummarizer(
                SummaryConfig(
                    enabled=settings.knowledge_summary_enabled,
                    llm_enabled=settings.knowledge_summary_llm_enabled,
                    model=settings.knowledge_summary_model,
                    api_key=settings.knowledge_summary_api_key,
                    base_url=settings.knowledge_summary_base_url,
                    max_chars=settings.knowledge_summary_max_chars,
                )
            ),
            summary_on_import=settings.knowledge_summary_on_import,
            summary_embedding_enabled=settings.knowledge_summary_embedding_enabled,
            upload_enabled=settings.knowledge_upload_enabled,
            upload_dir=settings.knowledge_upload_dir,
            converted_dir=settings.knowledge_converted_dir,
            upload_max_mb=settings.knowledge_upload_max_mb,
            upload_allowed_extensions=settings.knowledge_upload_allowed_extensions,
        )
    return _knowledge_service
