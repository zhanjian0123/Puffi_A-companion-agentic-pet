from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import json
import math
import re
import sqlite3
from pathlib import Path

from knowledge.graph import ExtractedEntity, ExtractedRelation
from knowledge.models import (
    KnowledgeDeleteResult,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeRelation,
    KnowledgeSearchResult,
    KnowledgeStatus,
)


class KnowledgeStore:
    def __init__(self, *, db_path: str, document_dir: str, enabled: bool) -> None:
        self._db_path = Path(db_path).expanduser().resolve()
        self._document_dir = Path(document_dir).expanduser().resolve()
        self._enabled = enabled
        self._ensure_schema()

    @property
    def document_dir(self) -> Path:
        return self._document_dir

    @property
    def db_path(self) -> Path:
        return self._db_path

    def upsert_document(
        self,
        *,
        path: str,
        title: str,
        file_hash: str,
        size: int,
        chunks: list[str],
        keywords: list[str],
        entities: list[str],
        graph_chunks: list[tuple[list[ExtractedEntity], list[ExtractedRelation]]] | None = None,
        graph_extractor: str | None = None,
        graph_model: str | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents(
                    path, title, hash, size, status, indexed_at,
                    graph_indexed_at, graph_extractor, graph_model
                )
                VALUES (?, ?, ?, ?, 'indexed', ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title = excluded.title,
                    hash = excluded.hash,
                    size = excluded.size,
                    status = excluded.status,
                    indexed_at = excluded.indexed_at,
                    graph_indexed_at = excluded.graph_indexed_at,
                    graph_extractor = excluded.graph_extractor,
                    graph_model = excluded.graph_model
                """,
                (
                    path,
                    title,
                    file_hash,
                    size,
                    now,
                    now if graph_chunks is not None else None,
                    graph_extractor if graph_chunks is not None else None,
                    graph_model if graph_chunks is not None else None,
                ),
            )
            document_id = self._document_id(connection, path)
            if document_id is None:
                document_id = int(cursor.lastrowid)

            self._delete_chunks(connection, document_id)

            for chunk_index, content in enumerate(chunks):
                chunk_keywords = self._keywords_for_chunk(content, keywords)
                chunk_entities = self._keywords_for_chunk(content, entities)
                chunk_cursor = connection.execute(
                    """
                    INSERT INTO chunks(document_id, chunk_index, content, keywords, entities)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        chunk_index,
                        content,
                        json.dumps(chunk_keywords, ensure_ascii=False),
                        json.dumps(chunk_entities, ensure_ascii=False),
                    ),
                )
                chunk_id = int(chunk_cursor.lastrowid)
                connection.execute(
                    "INSERT INTO chunks_fts(rowid, title, path, content) VALUES (?, ?, ?, ?)",
                    (chunk_id, title, path, content),
                )
                if graph_chunks and chunk_index < len(graph_chunks):
                    extracted_entities, extracted_relations = graph_chunks[chunk_index]
                    self._save_graph_chunk(
                        connection,
                        document_id=document_id,
                        chunk_id=chunk_id,
                        entities=extracted_entities,
                        relations=extracted_relations,
                    )

    def chunks_missing_embeddings(self, *, model: str) -> list[tuple[int, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.content
                FROM chunks c
                LEFT JOIN chunk_embeddings e ON e.chunk_id = c.id AND e.model = ?
                WHERE e.chunk_id IS NULL
                ORDER BY c.id
                """,
                (model,),
            ).fetchall()

        return [(int(row["id"]), str(row["content"])) for row in rows]

    def graph_items_missing_embeddings(self, *, model: str) -> list[tuple[str, int, str]]:
        with self._connect() as connection:
            entity_rows = connection.execute(
                """
                SELECT e.id, e.name, e.type, e.description
                FROM entities e
                LEFT JOIN entity_embeddings emb ON emb.entity_id = e.id AND emb.model = ?
                WHERE emb.entity_id IS NULL
                ORDER BY e.id
                """,
                (model,),
            ).fetchall()
            relation_rows = connection.execute(
                """
                SELECT r.id, r.source_entity, r.relation, r.target_entity, r.description, r.evidence
                FROM relations r
                LEFT JOIN relation_embeddings emb ON emb.relation_id = r.id AND emb.model = ?
                WHERE emb.relation_id IS NULL
                ORDER BY r.id
                """,
                (model,),
            ).fetchall()

        items: list[tuple[str, int, str]] = []
        for row in entity_rows:
            text = self._entity_embedding_text(row)
            if text:
                items.append(("entity", int(row["id"]), text))
        for row in relation_rows:
            text = self._relation_embedding_text(row)
            if text:
                items.append(("relation", int(row["id"]), text))
        return items

    def save_embeddings(self, *, model: str, embeddings: list[tuple[int, list[float]]]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            for chunk_id, embedding in embeddings:
                connection.execute(
                    """
                    INSERT INTO chunk_embeddings(chunk_id, model, dimensions, embedding_json, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id, model) DO UPDATE SET
                        dimensions = excluded.dimensions,
                        embedding_json = excluded.embedding_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        chunk_id,
                        model,
                        len(embedding),
                        json.dumps(embedding),
                        now,
                    ),
                )

    def save_graph_embeddings(self, *, model: str, embeddings: list[tuple[str, int, list[float]]]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            for kind, item_id, embedding in embeddings:
                if kind == "entity":
                    connection.execute(
                        """
                        INSERT INTO entity_embeddings(entity_id, model, dimensions, embedding_json, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(entity_id, model) DO UPDATE SET
                            dimensions = excluded.dimensions,
                            embedding_json = excluded.embedding_json,
                            updated_at = excluded.updated_at
                        """,
                        (item_id, model, len(embedding), json.dumps(embedding), now),
                    )
                elif kind == "relation":
                    connection.execute(
                        """
                        INSERT INTO relation_embeddings(relation_id, model, dimensions, embedding_json, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(relation_id, model) DO UPDATE SET
                            dimensions = excluded.dimensions,
                            embedding_json = excluded.embedding_json,
                            updated_at = excluded.updated_at
                        """,
                        (item_id, model, len(embedding), json.dumps(embedding), now),
                    )

    def upsert_document_summary(
        self,
        *,
        path: str,
        summary: str,
        keywords: list[str],
        topics: list[str],
        extractor: str,
        model: str | None,
    ) -> None:
        if not summary.strip():
            return

        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            document_id = self._document_id(connection, path)
            if document_id is None:
                return
            connection.execute(
                """
                INSERT INTO document_summaries(
                    document_id, summary, keywords, topics, extractor, model, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    summary = excluded.summary,
                    keywords = excluded.keywords,
                    topics = excluded.topics,
                    extractor = excluded.extractor,
                    model = excluded.model,
                    updated_at = excluded.updated_at
                """,
                (
                    document_id,
                    summary,
                    json.dumps(keywords, ensure_ascii=False),
                    json.dumps(topics, ensure_ascii=False),
                    extractor,
                    model,
                    now,
                ),
            )
            connection.execute("DELETE FROM document_summary_embeddings WHERE document_id = ?", (document_id,))

    def document_summaries_missing_embeddings(self, *, model: str) -> list[tuple[int, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT s.document_id, d.title, d.path, s.summary, s.keywords, s.topics
                FROM document_summaries s
                JOIN documents d ON d.id = s.document_id
                LEFT JOIN document_summary_embeddings emb
                    ON emb.document_id = s.document_id AND emb.model = ?
                WHERE emb.document_id IS NULL
                ORDER BY s.document_id
                """,
                (model,),
            ).fetchall()

        items: list[tuple[int, str]] = []
        for row in rows:
            text = self._summary_embedding_text(row)
            if text:
                items.append((int(row["document_id"]), text))
        return items

    def save_document_summary_embeddings(self, *, model: str, embeddings: list[tuple[int, list[float]]]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as connection:
            for document_id, embedding in embeddings:
                connection.execute(
                    """
                    INSERT INTO document_summary_embeddings(
                        document_id, model, dimensions, embedding_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(document_id, model) DO UPDATE SET
                        dimensions = excluded.dimensions,
                        embedding_json = excluded.embedding_json,
                        updated_at = excluded.updated_at
                    """,
                    (document_id, model, len(embedding), json.dumps(embedding), now),
                )
    def document_hash(self, path: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT hash FROM documents WHERE path = ?", (path,)).fetchone()
            return str(row["hash"]) if row else None

    def document_is_current(
        self,
        *,
        path: str,
        file_hash: str,
        require_graph: bool,
        graph_extractor: str | None = None,
        graph_model: str | None = None,
        require_summary: bool = False,
        summary_extractor: str | None = None,
        summary_model: str | None = None,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    d.hash,
                    d.graph_indexed_at,
                    d.graph_extractor,
                    d.graph_model,
                    s.extractor AS summary_extractor,
                    s.model AS summary_model
                FROM documents d
                LEFT JOIN document_summaries s ON s.document_id = d.id
                WHERE d.path = ?
                """,
                (path,),
            ).fetchone()
            if not row or str(row["hash"]) != file_hash:
                return False
            if require_graph and not row["graph_indexed_at"]:
                return False
            if require_graph and graph_extractor and row["graph_extractor"] != graph_extractor:
                return False
            if require_graph and graph_model and row["graph_model"] != graph_model:
                return False
            if require_summary and not row["summary_extractor"]:
                return False
            if require_summary and summary_extractor and row["summary_extractor"] != summary_extractor:
                return False
            if require_summary and summary_model and row["summary_model"] != summary_model:
                return False
            return True

    def delete_document(self, path: str) -> KnowledgeDeleteResult:
        with self._connect() as connection:
            row = connection.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
            if row is None:
                return KnowledgeDeleteResult(
                    deleted=False,
                    path=path,
                    chunks_deleted=0,
                    relations_deleted=0,
                    summaries_deleted=0,
                    orphan_entities_deleted=0,
                    message="知识库索引中没有找到该文档。",
                )

            document_id = int(row["id"])
            chunk_rows = connection.execute(
                "SELECT id FROM chunks WHERE document_id = ?",
                (document_id,),
            ).fetchall()
            chunk_ids = [int(chunk_row["id"]) for chunk_row in chunk_rows]
            chunks_deleted = len(chunk_ids)
            relations_deleted = int(
                connection.execute(
                    "SELECT COUNT(*) FROM relations WHERE document_id = ?",
                    (document_id,),
                ).fetchone()[0]
            )
            summaries_deleted = int(
                connection.execute(
                    "SELECT COUNT(*) FROM document_summaries WHERE document_id = ?",
                    (document_id,),
                ).fetchone()[0]
            )

            for chunk_id in chunk_ids:
                relation_rows = connection.execute(
                    "SELECT id FROM relations WHERE chunk_id = ?",
                    (chunk_id,),
                ).fetchall()
                for relation_row in relation_rows:
                    connection.execute(
                        "DELETE FROM relation_embeddings WHERE relation_id = ?",
                        (int(relation_row["id"]),),
                    )
                connection.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,))
                connection.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,))
                connection.execute("DELETE FROM chunk_entities WHERE chunk_id = ?", (chunk_id,))

            connection.execute(
                """
                DELETE FROM relation_embeddings
                WHERE relation_id IN (
                    SELECT id FROM relations WHERE document_id = ?
                )
                """,
                (document_id,),
            )
            connection.execute("DELETE FROM relations WHERE document_id = ?", (document_id,))
            connection.execute(
                "DELETE FROM document_summary_embeddings WHERE document_id = ?",
                (document_id,),
            )
            connection.execute("DELETE FROM document_summaries WHERE document_id = ?", (document_id,))
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            self._refresh_entity_counts(connection)
            orphan_entities_deleted = self._delete_orphan_entities(connection)

        return KnowledgeDeleteResult(
            deleted=True,
            path=path,
            chunks_deleted=chunks_deleted,
            relations_deleted=relations_deleted,
            summaries_deleted=summaries_deleted,
            orphan_entities_deleted=orphan_entities_deleted,
            message="已删除知识库资料并清理索引。",
        )

    def search(
        self,
        query: str,
        *,
        top_k: int,
        max_context_chars: int,
        query_embedding: list[float] | None = None,
        embedding_model: str | None = None,
        keyword_weight: float = 1.0,
        vector_weight: float = 0.0,
        graph_enabled: bool = False,
        graph_entities: list[str] | None = None,
        graph_weight: float = 0.0,
        graph_context_limit: int = 0,
        include_debug_context: bool = False,
        global_query: bool = False,
    ) -> list[KnowledgeSearchResult]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []

        scored: dict[int, KnowledgeSearchResult] = {}
        keyword_scores: dict[int, float] = {}
        vector_scores: dict[int, float] = {}
        graph_scores: dict[int, float] = {}

        with self._connect() as connection:
            for row in self._fts_search(connection, normalized_query, top_k * 4):
                self._merge_score(keyword_scores, row, score=float(row["score"]))
                self._ensure_result(scored, row)

            for row in self._like_search(connection, normalized_query, top_k * 4):
                self._merge_score(keyword_scores, row, score=float(row["score"]))
                self._ensure_result(scored, row)

            if query_embedding and embedding_model:
                for row, score in self._vector_search(connection, query_embedding, embedding_model, top_k * 8):
                    self._merge_score(vector_scores, row, score=score)
                    self._ensure_result(scored, row)
                for row, score in self._summary_vector_search(
                    connection,
                    query_embedding,
                    embedding_model,
                    top_k * 4,
                ):
                    self._merge_score(vector_scores, row, score=score if global_query else score * 0.7)
                    self._ensure_summary_result(scored, row)

            if global_query:
                for row, score in self._summary_like_search(connection, normalized_query, top_k * 4):
                    self._merge_score(keyword_scores, row, score=score)
                    self._ensure_summary_result(scored, row)

            graph_relations: dict[int, list[str]] = {}
            graph_entity_context: dict[int, list[str]] = {}
            if graph_enabled and graph_entities:
                for row, score, relations in self._graph_search(connection, graph_entities, top_k * 8):
                    self._merge_score(graph_scores, row, score=score)
                    self._ensure_result(scored, row)
                    chunk_id = int(row["id"])
                    graph_relations.setdefault(chunk_id, []).extend(relations)

            if graph_enabled and query_embedding and embedding_model:
                for row, score, entity_context in self._entity_vector_search(
                    connection,
                    query_embedding,
                    embedding_model,
                    top_k * 8,
                ):
                    self._merge_score(graph_scores, row, score=score)
                    self._ensure_result(scored, row)
                    chunk_id = int(row["id"])
                    graph_entity_context.setdefault(chunk_id, []).extend(entity_context)

                for row, score, relations in self._relation_vector_search(
                    connection,
                    query_embedding,
                    embedding_model,
                    top_k * 8,
                ):
                    self._merge_score(graph_scores, row, score=score)
                    self._ensure_result(scored, row)
                    chunk_id = int(row["id"])
                    graph_relations.setdefault(chunk_id, []).extend(relations)

            for chunk_id, relations in graph_relations.items():
                if chunk_id in scored:
                    scored[chunk_id].relations = relations
            for chunk_id, entities in graph_entity_context.items():
                if chunk_id in scored:
                    scored[chunk_id].entities = entities

        self._apply_hybrid_scores(
            scored=scored,
            keyword_scores=keyword_scores,
            vector_scores=vector_scores,
            graph_scores=graph_scores,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
        )

        results = sorted(scored.values(), key=lambda item: item.score, reverse=True)
        trimmed: list[KnowledgeSearchResult] = []
        used_chars = 0
        for result in results:
            if len(trimmed) >= top_k:
                break
            remaining = max_context_chars - used_chars
            if remaining <= 0:
                break
            content = result.content[:remaining]
            used_chars += len(content)
            relation_context = result.relations or []
            relations: list[str] | None = None
            if relation_context and graph_context_limit > 0:
                relations = self._trim_relations(relation_context, graph_context_limit)
            entities = None
            if result.entities and (include_debug_context or graph_context_limit > 0):
                entities = self._trim_relations(result.entities, graph_context_limit or 1200)

            trimmed.append(
                KnowledgeSearchResult(
                    document=result.document,
                    chunk_index=result.chunk_index,
                    score=round(result.score, 4),
                    content=content,
                    relations=relations,
                    entities=entities,
                    summaries=result.summaries,
                )
            )

        return trimmed

    def list_documents(self) -> list[KnowledgeDocument]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.path,
                    d.title,
                    d.hash,
                    d.size,
                    d.status,
                    d.indexed_at,
                    COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.path
                """
            ).fetchall()

        return [
            KnowledgeDocument(
                path=str(row["path"]),
                title=str(row["title"]),
                hash=str(row["hash"]),
                size=int(row["size"]),
                status=str(row["status"]),
                indexed_at=row["indexed_at"],
                chunk_count=int(row["chunk_count"]),
            )
            for row in rows
        ]

    def list_entities(self, *, limit: int = 100) -> list[KnowledgeEntity]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, normalized_name, type, document_count, chunk_count, updated_at
                FROM entities
                ORDER BY chunk_count DESC, name
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            KnowledgeEntity(
                name=str(row["name"]),
                normalized_name=str(row["normalized_name"]),
                type=str(row["type"]),
                document_count=int(row["document_count"]),
                chunk_count=int(row["chunk_count"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def list_relations(self, *, query: str | None = None, limit: int = 100) -> list[KnowledgeRelation]:
        with self._connect() as connection:
            params: tuple[object, ...]
            where = ""
            if query:
                like_query = f"%{query}%"
                where = "WHERE r.source_entity LIKE ? OR r.relation LIKE ? OR r.target_entity LIKE ?"
                params = (like_query, like_query, like_query, limit)
            else:
                params = (limit,)

            rows = connection.execute(
                f"""
                SELECT
                    r.source_entity,
                    r.relation,
                    r.target_entity,
                    d.path AS document,
                    c.chunk_index,
                    r.confidence,
                    r.description,
                    r.evidence,
                    r.extractor,
                    r.model
                FROM relations r
                LEFT JOIN documents d ON d.id = r.document_id
                LEFT JOIN chunks c ON c.id = r.chunk_id
                {where}
                ORDER BY r.confidence DESC, r.id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [
            KnowledgeRelation(
                source_entity=str(row["source_entity"]),
                relation=str(row["relation"]),
                target_entity=str(row["target_entity"]),
                document=row["document"],
                chunk_index=row["chunk_index"],
                confidence=float(row["confidence"]),
                description=row["description"],
                evidence=row["evidence"],
                extractor=row["extractor"],
                model=row["model"],
            )
            for row in rows
        ]

    def status(self) -> KnowledgeStatus:
        with self._connect() as connection:
            document_count = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            chunk_count = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
            entity_count = int(connection.execute("SELECT COUNT(*) FROM entities").fetchone()[0])
            relation_count = int(connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0])

        return KnowledgeStatus(
            enabled=self._enabled,
            document_dir=str(self._document_dir),
            index_db_path=str(self._db_path),
            document_count=document_count,
            chunk_count=chunk_count,
            entity_count=entity_count,
            relation_count=relation_count,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        self._document_dir.mkdir(parents=True, exist_ok=True)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    indexed_at TEXT,
                    graph_indexed_at TEXT,
                    graph_extractor TEXT,
                    graph_model TEXT
                )
                """
            )
            self._ensure_column(connection, "documents", "graph_indexed_at", "TEXT")
            self._ensure_column(connection, "documents", "graph_extractor", "TEXT")
            self._ensure_column(connection, "documents", "graph_model", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT '[]',
                    entities TEXT NOT NULL DEFAULT '[]',
                    embedding_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(chunk_id, model),
                    FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entity_embeddings (
                    entity_id INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(entity_id, model),
                    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relation_embeddings (
                    relation_id INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(relation_id, model),
                    FOREIGN KEY(relation_id) REFERENCES relations(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_summaries (
                    document_id INTEGER PRIMARY KEY,
                    summary TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT '[]',
                    topics TEXT NOT NULL DEFAULT '[]',
                    extractor TEXT,
                    model TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS document_summary_embeddings (
                    document_id INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(document_id, model),
                    FOREIGN KEY(document_id) REFERENCES document_summaries(document_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(title, path, content)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    description TEXT,
                    extractor TEXT,
                    model TEXT,
                    document_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                )
                """
            )
            self._ensure_column(connection, "entities", "description", "TEXT")
            self._ensure_column(connection, "entities", "extractor", "TEXT")
            self._ensure_column(connection, "entities", "model", "TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_entities (
                    chunk_id INTEGER NOT NULL,
                    entity_id INTEGER NOT NULL,
                    relevance REAL NOT NULL DEFAULT 1.0,
                    PRIMARY KEY(chunk_id, entity_id),
                    FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
                    FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_entity TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    document_id INTEGER,
                    chunk_id INTEGER,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    description TEXT,
                    evidence TEXT,
                    extractor TEXT,
                    model TEXT,
                    created_at TEXT
                )
                """
            )
            self._ensure_column(connection, "relations", "description", "TEXT")
            self._ensure_column(connection, "relations", "evidence", "TEXT")
            self._ensure_column(connection, "relations", "extractor", "TEXT")
            self._ensure_column(connection, "relations", "model", "TEXT")
            self._ensure_column(connection, "relations", "created_at", "TEXT")

    def _document_id(self, connection: sqlite3.Connection, path: str) -> int | None:
        row = connection.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
        return int(row["id"]) if row else None

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if any(str(row["name"]) == column for row in rows):
            return
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _delete_chunks(self, connection: sqlite3.Connection, document_id: int) -> None:
        rows = connection.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,)).fetchall()
        for row in rows:
            chunk_id = int(row["id"])
            connection.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_id,))
            connection.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,))
            connection.execute("DELETE FROM chunk_entities WHERE chunk_id = ?", (chunk_id,))
            relation_rows = connection.execute("SELECT id FROM relations WHERE chunk_id = ?", (chunk_id,)).fetchall()
            for relation_row in relation_rows:
                connection.execute("DELETE FROM relation_embeddings WHERE relation_id = ?", (int(relation_row["id"]),))
            connection.execute("DELETE FROM relations WHERE chunk_id = ?", (chunk_id,))
        connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        self._refresh_entity_counts(connection)

    def _fts_search(self, connection: sqlite3.Connection, query: str, limit: int) -> Iterable[sqlite3.Row]:
        match_query = self._build_fts_query(query)
        if not match_query:
            return []

        try:
            return connection.execute(
                """
                SELECT
                    c.id,
                    d.path AS document,
                    c.chunk_index,
                    c.content,
                    10.0 / (1.0 + bm25(chunks_fts)) AS score
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.rowid
                JOIN documents d ON d.id = c.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (match_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    def _like_search(self, connection: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
        terms = self._query_terms(query)
        if not terms:
            return []

        clauses = ["c.content LIKE ?"] * len(terms)
        params = [f"%{term}%" for term in terms]
        rows = connection.execute(
            f"""
            SELECT
                c.id,
                d.path AS document,
                c.chunk_index,
                c.content,
                1.0 AS score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE {" OR ".join(clauses)}
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()

        return rows

    def _build_fts_query(self, query: str) -> str:
        terms = self._query_terms(query)
        return " OR ".join(f'"{term}"' for term in terms)

    def _query_terms(self, query: str) -> list[str]:
        terms: list[str] = []
        normalized = re.sub(r"[，。？?！!、,.;；:：()（）\[\]【】\"“”]", " ", query)
        for term in normalized.split():
            cleaned = term.strip().strip('"')
            if cleaned:
                terms.append(cleaned)

        chinese_parts = re.findall(r"[\u4e00-\u9fff]+", query)
        for part in chinese_parts:
            if len(part) >= 2:
                terms.extend(part[index : index + 2] for index in range(len(part) - 1))
            if len(part) >= 3:
                terms.extend(part[index : index + 3] for index in range(len(part) - 2))

        terms.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", query))

        if not terms and query.strip():
            terms.append(query.strip())

        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if not term or term in seen:
                continue
            seen.add(term)
            deduped.append(term)
            if len(deduped) >= 20:
                break

        return deduped

    def _vector_search(
        self,
        connection: sqlite3.Connection,
        query_embedding: list[float],
        model: str,
        limit: int,
    ) -> list[tuple[sqlite3.Row, float]]:
        rows = connection.execute(
            """
            SELECT
                c.id,
                d.path AS document,
                c.chunk_index,
                c.content,
                e.embedding_json
            FROM chunk_embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE e.model = ?
            """,
            (model,),
        ).fetchall()

        scored_rows: list[tuple[sqlite3.Row, float]] = []
        for row in rows:
            try:
                embedding = json.loads(str(row["embedding_json"]))
            except json.JSONDecodeError:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            if score > 0:
                scored_rows.append((row, score))

        scored_rows.sort(key=lambda item: item[1], reverse=True)
        return scored_rows[:limit]

    def _summary_vector_search(
        self,
        connection: sqlite3.Connection,
        query_embedding: list[float],
        model: str,
        limit: int,
    ) -> list[tuple[sqlite3.Row, float]]:
        rows = connection.execute(
            """
            SELECT
                -d.id AS id,
                d.path AS document,
                -1 AS chunk_index,
                s.summary AS content,
                s.keywords,
                s.topics,
                e.embedding_json
            FROM document_summary_embeddings e
            JOIN document_summaries s ON s.document_id = e.document_id
            JOIN documents d ON d.id = s.document_id
            WHERE e.model = ?
            """,
            (model,),
        ).fetchall()

        scored_rows: list[tuple[sqlite3.Row, float]] = []
        for row in rows:
            try:
                embedding = json.loads(str(row["embedding_json"]))
            except json.JSONDecodeError:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            if score > 0:
                scored_rows.append((row, score))

        scored_rows.sort(key=lambda item: item[1], reverse=True)
        return scored_rows[:limit]

    def _summary_like_search(self, connection: sqlite3.Connection, query: str, limit: int) -> list[tuple[sqlite3.Row, float]]:
        terms = self._query_terms(query)
        if not terms:
            return []

        clauses = ["s.summary LIKE ? OR s.keywords LIKE ? OR s.topics LIKE ?"] * len(terms)
        params: list[str] = []
        for term in terms:
            params.extend([f"%{term}%", f"%{term}%", f"%{term}%"])
        rows = connection.execute(
            f"""
            SELECT
                -d.id AS id,
                d.path AS document,
                -1 AS chunk_index,
                s.summary AS content,
                s.keywords,
                s.topics
            FROM document_summaries s
            JOIN documents d ON d.id = s.document_id
            WHERE {" OR ".join(clauses)}
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [(row, 1.0) for row in rows]

    def _entity_vector_search(
        self,
        connection: sqlite3.Connection,
        query_embedding: list[float],
        model: str,
        limit: int,
    ) -> list[tuple[sqlite3.Row, float, list[str]]]:
        rows = connection.execute(
            """
            SELECT
                e.id AS entity_id,
                e.name,
                e.type,
                e.description,
                emb.embedding_json,
                c.id,
                d.path AS document,
                c.chunk_index,
                c.content
            FROM entity_embeddings emb
            JOIN entities e ON e.id = emb.entity_id
            JOIN chunk_entities ce ON ce.entity_id = e.id
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE emb.model = ?
            """,
            (model,),
        ).fetchall()

        scored_rows: list[tuple[sqlite3.Row, float, list[str]]] = []
        for row in rows:
            try:
                embedding = json.loads(str(row["embedding_json"]))
            except json.JSONDecodeError:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            if score <= 0:
                continue
            context = f"{row['name']}（{row['type']}）"
            if row["description"]:
                context = f"{context}: {row['description']}"
            scored_rows.append((row, score, [context]))

        scored_rows.sort(key=lambda item: item[1], reverse=True)
        return scored_rows[:limit]

    def _relation_vector_search(
        self,
        connection: sqlite3.Connection,
        query_embedding: list[float],
        model: str,
        limit: int,
    ) -> list[tuple[sqlite3.Row, float, list[str]]]:
        rows = connection.execute(
            """
            SELECT
                r.id AS relation_id,
                r.source_entity,
                r.relation,
                r.target_entity,
                r.description,
                r.evidence,
                emb.embedding_json,
                c.id,
                d.path AS document,
                c.chunk_index,
                c.content
            FROM relation_embeddings emb
            JOIN relations r ON r.id = emb.relation_id
            JOIN chunks c ON c.id = r.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE emb.model = ?
            """,
            (model,),
        ).fetchall()

        scored_rows: list[tuple[sqlite3.Row, float, list[str]]] = []
        for row in rows:
            try:
                embedding = json.loads(str(row["embedding_json"]))
            except json.JSONDecodeError:
                continue
            score = self._cosine_similarity(query_embedding, embedding)
            if score <= 0:
                continue
            relation_text = self._format_relation_context(row)
            scored_rows.append((row, score, [relation_text]))

        scored_rows.sort(key=lambda item: item[1], reverse=True)
        return scored_rows[:limit]

    def _graph_search(
        self,
        connection: sqlite3.Connection,
        entity_names: list[str],
        limit: int,
    ) -> list[tuple[sqlite3.Row, float, list[str]]]:
        normalized_entities = [self._normalize_entity(name) for name in entity_names if name.strip()]
        if not normalized_entities:
            return []

        chunk_scores: dict[int, float] = {}
        chunk_relations: dict[int, list[str]] = {}

        for entity in normalized_entities[:20]:
            like_query = f"%{entity}%"
            rows = connection.execute(
                """
                SELECT
                    c.id,
                    d.path AS document,
                    c.chunk_index,
                    c.content,
                    r.source_entity,
                    r.relation,
                    r.target_entity,
                    r.confidence,
                    r.description,
                    r.evidence
                FROM relations r
                JOIN chunks c ON c.id = r.chunk_id
                JOIN documents d ON d.id = c.document_id
                WHERE
                    lower(r.source_entity) LIKE ?
                    OR lower(r.target_entity) LIKE ?
                    OR lower(r.relation) LIKE ?
                """,
                (like_query, like_query, like_query),
            ).fetchall()

            for row in rows:
                chunk_id = int(row["id"])
                confidence = float(row["confidence"])
                chunk_scores[chunk_id] = max(chunk_scores.get(chunk_id, 0.0), confidence)
                relation_text = self._format_relation_context(row)
                chunk_relations.setdefault(chunk_id, [])
                if relation_text not in chunk_relations[chunk_id]:
                    chunk_relations[chunk_id].append(relation_text)

        if not chunk_scores:
            return []

        placeholders = ", ".join("?" for _ in chunk_scores)
        rows = connection.execute(
            f"""
            SELECT
                c.id,
                d.path AS document,
                c.chunk_index,
                c.content
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.id IN ({placeholders})
            """,
            tuple(chunk_scores.keys()),
        ).fetchall()

        row_by_id = {int(row["id"]): row for row in rows}
        results = [
            (row_by_id[chunk_id], score, chunk_relations.get(chunk_id, []))
            for chunk_id, score in chunk_scores.items()
            if chunk_id in row_by_id
        ]
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:limit]

    def _merge_score(self, scores: dict[int, float], row: sqlite3.Row, *, score: float) -> None:
        chunk_id = int(row["id"])
        scores[chunk_id] = scores.get(chunk_id, 0.0) + score

    def _ensure_result(self, scored: dict[int, KnowledgeSearchResult], row: sqlite3.Row) -> None:
        chunk_id = int(row["id"])
        if chunk_id in scored:
            return

        scored[chunk_id] = KnowledgeSearchResult(
            document=str(row["document"]),
            chunk_index=int(row["chunk_index"]),
            score=0.0,
            content=str(row["content"]),
        )

    def _ensure_summary_result(self, scored: dict[int, KnowledgeSearchResult], row: sqlite3.Row) -> None:
        summary_id = int(row["id"])
        if summary_id in scored:
            return

        summary = str(row["content"])
        topics = self._json_list(row["topics"]) if "topics" in row.keys() else []
        keywords = self._json_list(row["keywords"]) if "keywords" in row.keys() else []
        summary_context = summary
        tags = topics or keywords
        if tags:
            summary_context = f"{summary_context}（主题：{'、'.join(tags[:6])}）"

        scored[summary_id] = KnowledgeSearchResult(
            document=str(row["document"]),
            chunk_index=-1,
            score=0.0,
            content=summary,
            summaries=[summary_context],
        )

    def _apply_hybrid_scores(
        self,
        *,
        scored: dict[int, KnowledgeSearchResult],
        keyword_scores: dict[int, float],
        vector_scores: dict[int, float],
        graph_scores: dict[int, float],
        keyword_weight: float,
        vector_weight: float,
        graph_weight: float,
    ) -> None:
        max_keyword = max(keyword_scores.values(), default=0.0)

        for chunk_id, result in scored.items():
            keyword_score = keyword_scores.get(chunk_id, 0.0)
            keyword_norm = keyword_score / max_keyword if max_keyword > 0 else 0.0
            vector_norm = vector_scores.get(chunk_id, 0.0)
            graph_norm = graph_scores.get(chunk_id, 0.0)

            if vector_scores or graph_scores:
                result.score = (
                    keyword_weight * keyword_norm
                    + vector_weight * vector_norm
                    + graph_weight * graph_norm
                )
            else:
                result.score = keyword_score

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0

        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0

        return (dot / (left_norm * right_norm) + 1.0) / 2.0

    def _save_graph_chunk(
        self,
        connection: sqlite3.Connection,
        *,
        document_id: int,
        chunk_id: int,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
    ) -> None:
        for entity in entities:
            entity_id = self._upsert_entity(connection, entity)
            connection.execute(
                """
                INSERT OR IGNORE INTO chunk_entities(chunk_id, entity_id, relevance)
                VALUES (?, ?, 1.0)
                """,
                (chunk_id, entity_id),
            )

        for relation in relations:
            connection.execute(
                """
                INSERT INTO relations(
                    source_entity, relation, target_entity, document_id, chunk_id,
                    confidence, description, evidence, extractor, model, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation.source,
                    relation.relation,
                    relation.target,
                    document_id,
                    chunk_id,
                    relation.confidence,
                    relation.description,
                    relation.evidence,
                    relation.extractor,
                    relation.model,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

        self._refresh_entity_counts(connection)

    def _upsert_entity(self, connection: sqlite3.Connection, entity: ExtractedEntity) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        normalized_name = self._normalize_entity(entity.name)
        connection.execute(
            """
            INSERT INTO entities(name, normalized_name, type, description, extractor, model, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_name) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                description = COALESCE(excluded.description, entities.description),
                extractor = COALESCE(excluded.extractor, entities.extractor),
                model = COALESCE(excluded.model, entities.model),
                updated_at = excluded.updated_at
            """,
            (entity.name, normalized_name, entity.type, entity.description, entity.extractor, entity.model, now),
        )
        row = connection.execute(
            "SELECT id FROM entities WHERE normalized_name = ?",
            (normalized_name,),
        ).fetchone()
        return int(row["id"])

    def _format_relation_context(self, row: sqlite3.Row) -> str:
        relation_text = f"{row['source_entity']} {row['relation']} {row['target_entity']}"
        if "description" in row.keys() and row["description"]:
            relation_text = f"{relation_text}（说明：{row['description']}）"
        if "evidence" in row.keys() and row["evidence"]:
            relation_text = f"{relation_text}（证据：{row['evidence']}）"
        return relation_text

    def _entity_embedding_text(self, row: sqlite3.Row) -> str:
        parts = [str(row["name"]), str(row["type"])]
        if row["description"]:
            parts.append(str(row["description"]))
        return " ".join(part for part in parts if part).strip()

    def _relation_embedding_text(self, row: sqlite3.Row) -> str:
        parts = [str(row["source_entity"]), str(row["relation"]), str(row["target_entity"])]
        if row["description"]:
            parts.append(str(row["description"]))
        if row["evidence"]:
            parts.append(f"证据：{row['evidence']}")
        return " ".join(part for part in parts if part).strip()

    def _summary_embedding_text(self, row: sqlite3.Row) -> str:
        parts = [str(row["title"]), str(row["path"]), str(row["summary"])]
        parts.extend(self._json_list(row["keywords"]))
        parts.extend(self._json_list(row["topics"]))
        return " ".join(part for part in parts if part).strip()

    def _json_list(self, value: object) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed if str(item).strip()]

    def _refresh_entity_counts(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            UPDATE entities
            SET
                chunk_count = (
                    SELECT COUNT(*)
                    FROM chunk_entities ce
                    WHERE ce.entity_id = entities.id
                ),
                document_count = (
                    SELECT COUNT(DISTINCT c.document_id)
                    FROM chunk_entities ce
                    JOIN chunks c ON c.id = ce.chunk_id
                    WHERE ce.entity_id = entities.id
                )
            """
        )

    def _delete_orphan_entities(self, connection: sqlite3.Connection) -> int:
        rows = connection.execute(
            """
            SELECT id
            FROM entities
            WHERE chunk_count = 0 AND document_count = 0
            """
        ).fetchall()
        entity_ids = [int(row["id"]) for row in rows]
        if not entity_ids:
            return 0

        for entity_id in entity_ids:
            connection.execute("DELETE FROM entity_embeddings WHERE entity_id = ?", (entity_id,))
            connection.execute("DELETE FROM entities WHERE id = ?", (entity_id,))

        return len(entity_ids)

    def _normalize_entity(self, name: str) -> str:
        return re.sub(r"\s+", "", name.strip().lower())

    def _trim_relations(self, relations: list[str], limit: int) -> list[str]:
        trimmed: list[str] = []
        used = 0
        for relation in relations:
            if relation in trimmed:
                continue
            if used + len(relation) > limit:
                break
            trimmed.append(relation)
            used += len(relation)
        return trimmed

    def _keywords_for_chunk(self, content: str, keywords: list[str]) -> list[str]:
        return [keyword for keyword in keywords if keyword and keyword in content][:20]
