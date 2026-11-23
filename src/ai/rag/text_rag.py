# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Text RAG Engine (SQLite WAL + FTS5 + RRF)
# =============================================================================
# Description:
#   Локальный гибридный RAG-движок на SQLite (WAL): бинарное хранение векторов
#   float32 BLOB (0 МБ RAM в простое), лексический поиск FTS5 Okapi BM25,
#   склейка через Reciprocal Rank Fusion (RRF), SQL-фильтрация (INSTR вместо LIKE
#   для Windows-путей) и адаптер размерностей векторов на лету.
#
# Usage Examples:
#   Python API:
#     from src.ai.rag.text_rag import TextRAG
#
#     rag = TextRAG(provider="agy")
#     rag.add_documents([{"id": "doc1", "text": "Текст документа"}])
#     results = rag.search("запрос", top_k=3)
#
# File: text_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-23 17:50:00
# =============================================================================

from __future__ import annotations
"""Локальный гибридный RAG-движок на SQLite WAL (float32 BLOB + FTS5 BM25 + RRF)."""

import json
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

from logger import logger
from src.ai.orchestration.embeddings import embed_texts, hash_embed

_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_RRF_K = 60


class TextRAG:
    """Гибридный векторно-лексический RAG-движок на SQLite WAL (0 МБ RAM в простое).

    Attributes:
        db_path: Базовый путь к базе данных индекса.
        db_file: Файл SQLite (.sqlite).
        dimension: Размерность векторов по умолчанию.
        provider: Имя активного провайдера ИИ.
    """

    def __init__(
        self,
        api_key: str = "",
        db_path: Optional[Path] = None,
        dimension: int = 3072,
        provider: Optional[str] = None,
    ) -> None:
        """Инициализирует SQLite-хранилище TextRAG.

        Args:
            api_key: Прямой ключ API для генерации эмбеддингов (опционально).
            db_path: Путь к файлу индекса (по умолчанию data/rag/text_index).
            dimension: Размерность векторов (по умолчанию 3072 для Gemini, 256 для рабочих пространств).
            provider: Имя провайдера ИИ ('agy', 'gemini', 'ollama', 'openai' и др.).
        """
        self.db_path = Path(db_path) if db_path else Path("data/rag/text_index")
        self.db_file = self.db_path.with_suffix(".sqlite")
        self.index_file = self.db_file
        self.meta_file = self.db_file
        self.dimension = int(dimension)
        self.api_key = api_key
        self._lock = threading.RLock()
        self.provider = str(provider).lower().strip() if provider else self._resolve_default_provider()

        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @staticmethod
    def _resolve_default_provider() -> str:
        """Определяет провайдера по умолчанию из глобальной конфигурации."""
        try:
            from src.config import ai_cfg
            prov = getattr(ai_cfg, "default_provider", None)
            if prov:
                return str(prov).lower().strip()
        except Exception:
            pass
        return "gemini"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Открывает потокобезопасное соединение SQLite с режимом WAL и busy_timeout."""
        conn = sqlite3.connect(str(self.db_file), timeout=15.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=15000;")
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Создаёт таблицы rag_chunks и полнотекстовый индекс FTS5 (BM25)."""
        with self._lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    workspace_id TEXT NOT NULL DEFAULT '',
                    document_id TEXT NOT NULL DEFAULT '',
                    file_path TEXT NOT NULL DEFAULT '',
                    vector BLOB NOT NULL,
                    dim INTEGER NOT NULL,
                    is_sparse INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_chunks_ws_doc ON rag_chunks(workspace_id, document_id)"
            )
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
                    id UNINDEXED,
                    text,
                    tokenize='unicode61'
                )
            """)
            conn.commit()

    @staticmethod
    def _is_sparse_hash_vector(vec: Any) -> bool:
        """Проверяет, является ли вектор разреженным детерминированным хэш-эмбеддингом (>50% нулей)."""
        arr = np.asarray(vec, dtype=np.float32)
        if arr.size == 0:
            return False
        return bool(np.count_nonzero(arr == 0.0) > (arr.size * 0.5))

    @staticmethod
    def _normalize_vector(vec: Any) -> np.ndarray:
        """Приводит вектор к float32 и выполняет L2-нормализацию."""
        arr = np.asarray(vec, dtype=np.float32).ravel()
        norm = float(np.linalg.norm(arr))
        if norm > 1e-12:
            arr = arr / norm
        return arr.astype(np.float32, copy=False)

    @staticmethod
    def _adapt_query_vector(query_vec: np.ndarray, stored_dim: int) -> np.ndarray:
        """Адаптирует размерность вектора запроса под размерность сохранённого индекса на лету."""
        dim = int(query_vec.shape[0])
        if dim == stored_dim:
            return TextRAG._normalize_vector(query_vec)
        if dim > stored_dim:
            adapted = query_vec[:stored_dim]
        else:
            adapted = np.zeros(stored_dim, dtype=np.float32)
            adapted[:dim] = query_vec
        return TextRAG._normalize_vector(adapted)

    def _hash_embed(self, texts: List[str]) -> List[List[float]]:
        """Генерирует детерминированные локальные хэш-векторы заданной размерности."""
        return hash_embed(texts, dimension=self.dimension)

    def _embed(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Генерация эмбеддингов через единый маршрутизатор src.ai.orchestration.embeddings."""
        if not texts:
            return []
        return embed_texts(
            texts=texts,
            provider=self.provider,
            dimension=self.dimension,
            task_type=task_type,
            api_key=self.api_key or None,
        )

    def add_documents(self, docs: List[Dict[str, Any]], batch_size: int = 100) -> int:
        """Инкрементально векторизует и сохраняет документы в SQLite (BLOB + FTS5) одной транзакцией.

        Args:
            docs: Список словарей формата {'id': str, 'text': str, 'meta': dict}.
            batch_size: Размер пачки для вызовов эмбеддера (до 100).

        Returns:
            Количество добавленных/обновлённых документов.
        """
        if not docs:
            return 0

        rows: List[Tuple[str, str, str, str, str, str, bytes, int, int, float]] = []
        now = time.time()

        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            texts = [str(d["text"]) for d in batch]
            vectors = self._embed(texts, task_type="RETRIEVAL_DOCUMENT")
            for doc, vec in zip(batch, vectors):
                arr = self._normalize_vector(vec)
                meta = doc.get("meta") or {}
                f_path = str(meta.get("original_path") or meta.get("file_path") or meta.get("document_id") or "")
                rows.append((
                    str(doc["id"]),
                    str(doc["text"]),
                    json.dumps(meta, ensure_ascii=False, separators=(",", ":")),
                    str(meta.get("workspace_id", "")),
                    str(meta.get("document_id", "")),
                    f_path,
                    arr.tobytes(),
                    int(arr.shape[0]),
                    1 if self._is_sparse_hash_vector(arr) else 0,
                    now,
                ))

        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            ids = [(r[0],) for r in rows]
            cur.executemany("DELETE FROM rag_chunks_fts WHERE id = ?", ids)
            cur.executemany(
                """
                INSERT OR REPLACE INTO rag_chunks
                    (id, text, meta_json, workspace_id, document_id, file_path, vector, dim, is_sparse, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            cur.executemany(
                "INSERT INTO rag_chunks_fts (id, text) VALUES (?, ?)",
                [(r[0], r[1]) for r in rows],
            )
            conn.commit()
        return len(rows)

    def delete_document(self, doc_id: str) -> None:
        """Удаляет один чанк/документ по точному идентификатору."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM rag_chunks WHERE id = ?", (doc_id,))
            conn.execute("DELETE FROM rag_chunks_fts WHERE id = ?", (doc_id,))
            conn.commit()

    def delete_by_prefix(self, prefix: str) -> int:
        """Удаляет все чанки, чей идентификатор начинается с указанного префикса (без LIKE)."""
        if not prefix:
            return 0
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM rag_chunks_fts WHERE INSTR(id, ?) = 1", (prefix,))
            cur.execute("DELETE FROM rag_chunks WHERE INSTR(id, ?) = 1", (prefix,))
            deleted = cur.rowcount
            conn.commit()
            return max(0, int(deleted))

    def rename_prefix(
        self,
        old_prefix: str,
        new_prefix: str,
        meta_updates: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Переименовывает префикс идентификаторов и обновляет метаданные без пересчёта векторов."""
        if not old_prefix or old_prefix == new_prefix:
            return 0
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, text, meta_json, workspace_id, document_id, file_path, vector, dim, is_sparse, updated_at "
                "FROM rag_chunks WHERE INSTR(id, ?) = 1",
                (old_prefix,),
            )
            matched = cur.fetchall()
            if not matched:
                return 0

            updated_rows = []
            for row in matched:
                old_id, text, meta_json, ws_id, doc_id, f_path, vec_blob, dim, is_sparse, upd = row
                new_id = f"{new_prefix}{old_id[len(old_prefix):]}"
                meta = json.loads(meta_json) if meta_json else {}
                if meta_updates:
                    meta.update({k: v for k, v in meta_updates.items() if v is not None})
                    if "document_id" in meta_updates and meta_updates["document_id"] is not None:
                        doc_id = str(meta_updates["document_id"])
                    if "workspace_id" in meta_updates and meta_updates["workspace_id"] is not None:
                        ws_id = str(meta_updates["workspace_id"])
                    if "original_path" in meta_updates and meta_updates["original_path"] is not None:
                        f_path = str(meta_updates["original_path"])
                updated_rows.append((
                    new_id,
                    text,
                    json.dumps(meta, ensure_ascii=False, separators=(",", ":")),
                    ws_id,
                    doc_id,
                    f_path,
                    vec_blob,
                    dim,
                    is_sparse,
                    upd,
                ))

            cur.execute("DELETE FROM rag_chunks WHERE INSTR(id, ?) = 1", (old_prefix,))
            cur.execute("DELETE FROM rag_chunks_fts WHERE INSTR(id, ?) = 1", (old_prefix,))
            cur.executemany(
                "DELETE FROM rag_chunks_fts WHERE id = ?",
                [(r[0],) for r in updated_rows],
            )
            cur.executemany(
                """
                INSERT OR REPLACE INTO rag_chunks
                    (id, text, meta_json, workspace_id, document_id, file_path, vector, dim, is_sparse, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                updated_rows,
            )
            cur.executemany(
                "INSERT INTO rag_chunks_fts (id, text) VALUES (?, ?)",
                [(r[0], r[1]) for r in updated_rows],
            )
            conn.commit()
            return len(updated_rows)

    def list_by_prefix(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Возвращает список чанков (id, text, meta) по префиксу без загрузки бинарных векторов."""
        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            if prefix:
                cur.execute(
                    "SELECT id, text, meta_json FROM rag_chunks WHERE INSTR(id, ?) = 1 ORDER BY id",
                    (prefix,),
                )
            else:
                cur.execute("SELECT id, text, meta_json FROM rag_chunks ORDER BY id")
            return [
                {
                    "id": row[0],
                    "text": row[1],
                    "meta": json.loads(row[2]) if row[2] else {},
                }
                for row in cur.fetchall()
            ]

    def clear(self) -> None:
        """Полная очистка индекса и FTS5-таблицы."""
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM rag_chunks")
            conn.execute("DELETE FROM rag_chunks_fts")
            conn.commit()

    def _build_where(
        self,
        workspace_id: Optional[str] = None,
        document_id: Optional[str] = None,
        path_contains: Optional[str] = None,
        alias: str = "",
    ) -> Tuple[str, List[Any]]:
        """Формирует SQL-условие фильтрации (с INSTR вместо LIKE для Windows-путей)."""
        p = f"{alias}." if alias else ""
        clauses: List[str] = []
        params: List[Any] = []
        if workspace_id:
            clauses.append(f"{p}workspace_id = ?")
            params.append(workspace_id)
        if document_id:
            clauses.append(f"{p}document_id = ?")
            params.append(document_id)
        if path_contains:
            clauses.append(f"INSTR(LOWER({p}file_path), LOWER(?)) > 0")
            params.append(path_contains)
        return (" AND ".join(clauses) if clauses else "1=1"), params

    def search(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
        workspace_id: Optional[str] = None,
        document_id: Optional[str] = None,
        path_contains: Optional[str] = None,
        hybrid: bool = True,
    ) -> List[Dict[str, Any]]:
        """Гибридный семантический (float32 BLOB) + лексический (FTS5 BM25) поиск с RRF.

        Args:
            query: Поисковый запрос.
            top_k: Максимальное количество результатов.
            threshold: Минимальный порог релевантности (от 0.0 до 1.0).
            workspace_id: Опциональный SQL-фильтр по рабочей области.
            document_id: Опциональный SQL-фильтр по идентификатору документа.
            path_contains: Опциональный SQL-фильтр подстроки в метаданных (через INSTR).
            hybrid: Включить склейку Dense + FTS5 BM25 через RRF (по умолчанию True).

        Returns:
            Список найденных документов с оценками релевантности.
        """
        if not query or not query.strip():
            return []

        where_sql, params = self._build_where(workspace_id, document_id, path_contains)

        with self._lock, self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, text, meta_json, vector, dim, is_sparse FROM rag_chunks WHERE {where_sql}",
                params,
            )
            rows = cur.fetchall()
            if not rows:
                return []

            # 1. Плотный векторный поиск (с адаптацией размерности на лету)
            stored_dim = int(rows[0][4])
            is_sparse_index = bool(rows[0][5])
            query_vecs = self._hash_embed([query]) if is_sparse_index else self._embed([query], task_type="RETRIEVAL_QUERY")
            if not query_vecs:
                return []

            query_norm = self._adapt_query_vector(np.asarray(query_vecs[0], dtype=np.float32), stored_dim)

            valid_rows: List[Tuple[str, str, str, np.ndarray]] = []
            for r_id, r_text, r_meta, r_blob, r_dim, _ in rows:
                if not r_blob:
                    continue
                vec = np.frombuffer(r_blob, dtype=np.float32)
                if vec.shape[0] != stored_dim:
                    vec = self._adapt_query_vector(vec, stored_dim)
                valid_rows.append((r_id, r_text, r_meta, vec))

            if not valid_rows:
                return []

            matrix = np.vstack([r[3] for r in valid_rows])
            similarities = np.dot(matrix, query_norm)
            cand_k = min(max(top_k * 4, 20), len(valid_rows))
            dense_order = np.argsort(similarities)[::-1][:cand_k]

            row_map: Dict[str, Tuple[str, str, float]] = {}
            dense_ranks: Dict[str, int] = {}
            for rank_idx, idx in enumerate(dense_order, start=1):
                r_id, r_text, r_meta, _ = valid_rows[int(idx)]
                sim = max(0.0, float(similarities[int(idx)]))
                row_map[r_id] = (r_text, r_meta, sim)
                dense_ranks[r_id] = rank_idx

            # 2. Лексический поиск FTS5 Okapi BM25
            bm25_ranks: Dict[str, int] = {}
            if hybrid:
                tokens = [t for t in _FTS_TOKEN_RE.findall(query) if len(t) >= 2][:16]
                if tokens:
                    fts_expr = " OR ".join(f'"{t}"' for t in tokens)
                    where_join, join_params = self._build_where(workspace_id, document_id, path_contains, alias="c")
                    try:
                        cur.execute(
                            f"""
                            SELECT c.id, c.text, c.meta_json
                            FROM rag_chunks_fts f
                            JOIN rag_chunks c ON c.id = f.id
                            WHERE rag_chunks_fts MATCH ? AND {where_join}
                            ORDER BY bm25(rag_chunks_fts)
                            LIMIT ?
                            """,
                            [fts_expr, *join_params, cand_k],
                        )
                        for rank_idx, (r_id, r_text, r_meta) in enumerate(cur.fetchall(), start=1):
                            bm25_ranks[r_id] = rank_idx
                            if r_id not in row_map:
                                row_map[r_id] = (r_text, r_meta, 0.0)
                    except sqlite3.OperationalError as fts_err:
                        logger.debug(f"[TextRAG] Пропуск FTS5 BM25 для запроса '{query[:40]}': {fts_err}")

        # 3. Reciprocal Rank Fusion (RRF)
        max_rrf = (1.0 / (_RRF_K + 1)) * (2.0 if bm25_ranks else 1.0)
        fused: List[Tuple[float, float, str]] = []
        for r_id, (_, _, vec_sim) in row_map.items():
            rrf = 0.0
            if r_id in dense_ranks:
                rrf += 1.0 / (_RRF_K + dense_ranks[r_id])
            if r_id in bm25_ranks:
                rrf += 1.0 / (_RRF_K + bm25_ranks[r_id])
            # Комбинированная оценка в [0.0, 1.0]: сохраняет косинусный масштаб и усиливает BM25-совпадения
            if r_id in bm25_ranks:
                rrf_norm = min(1.0, rrf / max_rrf) if max_rrf > 0 else 0.0
                final_score = (0.65 * vec_sim + 0.35 * rrf_norm) if vec_sim > 0 else (0.5 * rrf_norm)
            else:
                final_score = vec_sim
            if final_score >= threshold:
                fused.append((rrf, final_score, r_id))

        fused.sort(key=lambda item: (item[0], item[1]), reverse=True)

        results: List[Dict[str, Any]] = []
        for rrf, final_score, r_id in fused[:top_k]:
            r_text, r_meta, vec_sim = row_map[r_id]
            results.append({
                "id": r_id,
                "text": r_text,
                "meta": json.loads(r_meta) if r_meta else {},
                "score": round(final_score, 4),
                "vector_score": round(vec_sim, 4),
                "bm25_rank": bm25_ranks.get(r_id),
                "rrf_score": round(rrf, 6),
            })
        return results

    def count(self) -> int:
        """Возвращает общее количество чанков в SQLite-индексе."""
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()
            return int(row[0]) if row else 0
