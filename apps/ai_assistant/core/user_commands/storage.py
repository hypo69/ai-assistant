# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant User Commands - SQLite & Markdown Storage
# =============================================================================
# Description:
#   Хранилище пользовательской базы знаний команд с поддержкой SQLite (WAL-режим)
#   и автоматической синхронизацией в Markdown-файл (commands_cheatsheet.md).
#
# File: storage.py
# Package: apps.ai_assistant.core.user_commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:22:00
# =============================================================================

from __future__ import annotations

"""Модуль хранения пользовательских команд в SQLite и Markdown."""

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, Generator, List, Optional
from contextlib import contextmanager

from header import __root__
from logger import logger
from .default_commands import DEFAULT_USER_COMMANDS
from .models import UserCommand, get_current_iso_time


class UserCommandsStorage:
    """Управление хранением и синхронизацией пользовательских команд."""

    def __init__(
        self,
        db_path: str | Path = "data/user_commands/user_commands.db",
        md_path: str | Path = "data/user_commands/commands_cheatsheet.md",
    ) -> None:
        """Инициализирует менеджер хранилища команд."""
        self._lock = threading.RLock()
        self.db_path = (__root__ / Path(db_path)).resolve() if not Path(db_path).is_absolute() else Path(db_path)
        self.md_path = (__root__ / Path(md_path)).resolve() if not Path(md_path).is_absolute() else Path(md_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.md_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite_db()
        self._seed_if_empty()

    @contextmanager
    def _connect_sqlite(self) -> Generator[sqlite3.Connection, None, None]:
        """Потокобезопасный контекстный менеджер SQLite соединения в режиме WAL."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=15000;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_sqlite_db(self) -> None:
        """Создает таблицы и индексы базы команд."""
        with self._connect_sqlite() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_commands (
                    command_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    command TEXT NOT NULL,
                    shell TEXT NOT NULL DEFAULT 'powershell',
                    category TEXT NOT NULL DEFAULT 'Общее',
                    description TEXT DEFAULT '',
                    tags_json TEXT DEFAULT '[]',
                    placeholders_json TEXT DEFAULT '{}',
                    risk_level TEXT DEFAULT 'safe',
                    favorite INTEGER DEFAULT 0,
                    execution_count INTEGER DEFAULT 0,
                    last_executed_at TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cmd_category ON user_commands(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cmd_shell ON user_commands(shell)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cmd_favorite ON user_commands(favorite)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cmd_title ON user_commands(title)")

    def _seed_if_empty(self) -> None:
        """Наполняет базу дефолтными командами при первом запуске."""
        with self._connect_sqlite() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM user_commands")
            count = cur.fetchone()[0]
            if count == 0:
                now = get_current_iso_time()
                for item in DEFAULT_USER_COMMANDS:
                    conn.execute(
                        """
                        INSERT INTO user_commands (
                            command_id, title, command, shell, category, description,
                            tags_json, placeholders_json, risk_level, favorite,
                            execution_count, last_executed_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?)
                        """,
                        (
                            item["command_id"],
                            item["title"],
                            item["command"],
                            item.get("shell", "powershell"),
                            item.get("category", "Общее"),
                            item.get("description", ""),
                            json.dumps(item.get("tags", []), ensure_ascii=False),
                            json.dumps(item.get("placeholders", {}), ensure_ascii=False),
                            item.get("risk_level", "safe"),
                            1 if item.get("favorite") else 0,
                            now,
                            now,
                        ),
                    )
        self.sync_to_markdown()

    def _map_row(self, row: sqlite3.Row | Dict[str, Any]) -> UserCommand:
        """Преобразует строку базы в объект модели UserCommand."""
        d = dict(row)
        tags_raw = d.get("tags_json") or "[]"
        ph_raw = d.get("placeholders_json") or "{}"
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else list(tags_raw)
        except Exception:
            tags = []
        try:
            placeholders = json.loads(ph_raw) if isinstance(ph_raw, str) else dict(ph_raw)
        except Exception:
            placeholders = {}

        return UserCommand(
            command_id=str(d["command_id"]),
            title=str(d["title"]),
            command=str(d["command"]),
            shell=str(d.get("shell", "powershell")),
            category=str(d.get("category", "Общее")),
            description=str(d.get("description", "")),
            tags=tags,
            placeholders=placeholders,
            risk_level=str(d.get("risk_level", "safe")),
            favorite=bool(d.get("favorite", 0)),
            execution_count=int(d.get("execution_count", 0)),
            last_executed_at=str(d.get("last_executed_at") or ""),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )

    def list_commands(
        self,
        category: Optional[str] = None,
        shell: Optional[str] = None,
        favorite_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> List[UserCommand]:
        """Возвращает список команд с фильтрацией."""
        clauses: List[str] = []
        params: List[Any] = []

        if category and category != "all":
            clauses.append("category = ?")
            params.append(category)
        if shell and shell != "all":
            clauses.append("shell = ?")
            params.append(shell)
        if favorite_only:
            clauses.append("favorite = 1")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM user_commands {where_sql} ORDER BY favorite DESC, execution_count DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect_sqlite() as conn:
            cur = conn.execute(sql, tuple(params))
            return [self._map_row(r) for r in cur.fetchall()]

    def search_commands(self, query: str, limit: int = 100) -> List[UserCommand]:
        """Поиск по названию, команде, описанию или тегам."""
        q = f"%{query.strip().lower()}%"
        sql = """
        SELECT * FROM user_commands
        WHERE LOWER(title) LIKE ? OR LOWER(command) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags_json) LIKE ?
        ORDER BY favorite DESC, execution_count DESC LIMIT ?
        """
        with self._connect_sqlite() as conn:
            cur = conn.execute(sql, (q, q, q, q, limit))
            return [self._map_row(r) for r in cur.fetchall()]

    def get_command(self, command_id: str) -> Optional[UserCommand]:
        """Возвращает команду по идентификатору."""
        with self._connect_sqlite() as conn:
            cur = conn.execute("SELECT * FROM user_commands WHERE command_id = ? LIMIT 1", (command_id,))
            row = cur.fetchone()
            return self._map_row(row) if row else None

    def save_command(self, cmd: UserCommand) -> UserCommand:
        """Сохраняет новую команду или обновляет существующую."""
        with self._connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO user_commands (
                    command_id, title, command, shell, category, description,
                    tags_json, placeholders_json, risk_level, favorite,
                    execution_count, last_executed_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(command_id) DO UPDATE SET
                    title = excluded.title,
                    command = excluded.command,
                    shell = excluded.shell,
                    category = excluded.category,
                    description = excluded.description,
                    tags_json = excluded.tags_json,
                    placeholders_json = excluded.placeholders_json,
                    risk_level = excluded.risk_level,
                    favorite = excluded.favorite,
                    updated_at = excluded.updated_at
                """,
                (
                    cmd.command_id,
                    cmd.title,
                    cmd.command,
                    cmd.shell,
                    cmd.category,
                    cmd.description,
                    json.dumps(cmd.tags, ensure_ascii=False),
                    json.dumps(cmd.placeholders, ensure_ascii=False),
                    cmd.risk_level,
                    1 if cmd.favorite else 0,
                    cmd.execution_count,
                    cmd.last_executed_at or "",
                    cmd.created_at,
                    cmd.updated_at,
                ),
            )
        self.sync_to_markdown()
        return cmd

    def delete_command(self, command_id: str) -> bool:
        """Удаляет команду по ID."""
        with self._connect_sqlite() as conn:
            cur = conn.execute("DELETE FROM user_commands WHERE command_id = ?", (command_id,))
            deleted = cur.rowcount > 0
        if deleted:
            self.sync_to_markdown()
        return deleted

    def toggle_favorite(self, command_id: str) -> bool:
        """Переключает статус 'избранное' для команды."""
        with self._connect_sqlite() as conn:
            cur = conn.execute(
                "UPDATE user_commands SET favorite = 1 - favorite, updated_at = ? WHERE command_id = ?",
                (get_current_iso_time(), command_id),
            )
            if cur.rowcount == 0:
                return False
            cur2 = conn.execute("SELECT favorite FROM user_commands WHERE command_id = ?", (command_id,))
            row = cur2.fetchone()
            fav = bool(row[0]) if row else False
        return fav

    def record_execution(self, command_id: str) -> None:
        """Увеличивает счетчик запусков команды и обновляет время последнего запуска."""
        now = get_current_iso_time()
        with self._connect_sqlite() as conn:
            conn.execute(
                "UPDATE user_commands SET execution_count = execution_count + 1, last_executed_at = ? WHERE command_id = ?",
                (now, command_id),
            )

    def list_categories(self) -> List[str]:
        """Возвращает список уникальных категорий команд."""
        with self._connect_sqlite() as conn:
            cur = conn.execute("SELECT DISTINCT category FROM user_commands ORDER BY category ASC")
            return [r[0] for r in cur.fetchall() if r[0]]

    def sync_to_markdown(self) -> None:
        """Формирует красивый Markdown Cheatsheet из всех команд."""
        try:
            items = self.list_commands(limit=1000)
            lines = [
                "# 📖 База знаний команд и шпаргалка (CheatSheet)",
                "",
                f"> Сгенерировано автоматически: {get_current_iso_time()} | Всего команд: {len(items)}",
                "",
            ]

            by_cat: Dict[str, List[UserCommand]] = {}
            for it in items:
                by_cat.setdefault(it.category, []).append(it)

            for cat, cmd_list in sorted(by_cat.items()):
                lines.append(f"## 📁 {cat}")
                lines.append("")
                for it in cmd_list:
                    fav_icon = "⭐ " if it.favorite else ""
                    lines.append(f"### {fav_icon}{it.title} (`{it.shell}`)")
                    if it.description:
                        lines.append(f"{it.description}")
                        lines.append("")
                    lines.append(f"```{it.shell}")
                    lines.append(it.command)
                    lines.append("```")
                    if it.tags:
                        lines.append(f"*Теги:* `{'`, `'.join(it.tags)}`")
                    lines.append("")

            self.md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"[UserCommandsStorage] Ошибка экспорта в Markdown: {exc}")
