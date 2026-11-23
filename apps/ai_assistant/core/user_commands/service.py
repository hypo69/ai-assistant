# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant User Commands - Service
# =============================================================================
# Description:
#   Бизнес-логика управления базой знаний команд пользователя: фильтрация,
#   валидация, подстановка плейсхолдеров и безопасный запуск в подпроцессе хоста.
#
# File: service.py
# Package: apps.ai_assistant.core.user_commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:23:00
# =============================================================================

from __future__ import annotations

"""Сервисный слой управления базой знаний команд."""

import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger
from .models import (
    UserCommand,
    UserCommandCreate,
    UserCommandExecuteResult,
    get_current_iso_time,
)
from .storage import UserCommandsStorage


class UserCommandsService:
    """Сервис управления базой знаний команд."""

    def __init__(self, storage: Optional[UserCommandsStorage] = None) -> None:
        """Инициализация сервиса с инъекцией хранилища."""
        self.storage = storage or UserCommandsStorage()

    def list_commands(
        self,
        category: Optional[str] = None,
        shell: Optional[str] = None,
        favorite_only: bool = False,
        query: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[UserCommand]:
        """Возвращает список команд по поисковому запросу или фильтрам."""
        if query and query.strip():
            return self.storage.search_commands(query=query.strip(), limit=limit)
        return self.storage.list_commands(
            category=category,
            shell=shell,
            favorite_only=favorite_only,
            limit=limit,
            offset=offset,
        )

    def get_command(self, command_id: str) -> Optional[UserCommand]:
        """Получает команду по ID."""
        return self.storage.get_command(command_id)

    def save_command(self, payload: UserCommandCreate) -> UserCommand:
        """Создает или обновляет команду."""
        now = get_current_iso_time()
        cid = payload.command_id
        if not cid:
            short_id = uuid.uuid4().hex[:8]
            cid = f"cmd_user_{short_id}"

        existing = self.storage.get_command(cid)
        exec_count = existing.execution_count if existing else 0
        last_exec = existing.last_executed_at if existing else ""
        created_at = existing.created_at if existing else now

        cmd_obj = UserCommand(
            command_id=cid,
            title=payload.title.strip(),
            command=payload.command.strip(),
            shell=payload.shell.lower().strip() or "powershell",
            category=payload.category.strip() or "Общее",
            description=payload.description.strip(),
            tags=[t.strip() for t in payload.tags if t.strip()],
            placeholders=payload.placeholders,
            risk_level=payload.risk_level.lower().strip() or "safe",
            favorite=payload.favorite,
            execution_count=exec_count,
            last_executed_at=last_exec,
            created_at=created_at,
            updated_at=now,
        )
        return self.storage.save_command(cmd_obj)

    def delete_command(self, command_id: str) -> bool:
        """Удаляет команду."""
        return self.storage.delete_command(command_id)

    def toggle_favorite(self, command_id: str) -> bool:
        """Переключает статус 'избранное'."""
        return self.storage.toggle_favorite(command_id)

    def list_categories(self) -> List[str]:
        """Возвращает список доступных категорий."""
        return self.storage.list_categories()

    def execute_command(
        self,
        command_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout_sec: int = 30,
        as_admin: bool = False,
    ) -> UserCommandExecuteResult:
        """Выполняет команду на хосте с подстановкой параметров."""
        cmd_obj = self.storage.get_command(command_id)
        if not cmd_obj:
            return UserCommandExecuteResult(
                command_id=command_id,
                exit_code=-1,
                stdout="",
                stderr=f"Команда '{command_id}' не найдена в базе знаний.",
                duration_ms=0.0,
                executed_at=get_current_iso_time(),
                status="not_found",
            )

        cmd_text = cmd_obj.command
        params = parameters or {}
        for key, val in params.items():
            if str(key) in cmd_text:
                cmd_text = cmd_text.replace(str(key), str(val))

        shell_type = cmd_obj.shell.lower()
        t_start = time.perf_counter()

        if shell_type == "python":
            runner_cmd = [sys.executable, "-c", cmd_text]
        elif shell_type == "cmd":
            runner_cmd = ["cmd.exe", "/c", cmd_text]
        elif shell_type == "bash":
            runner_cmd = ["bash", "-c", cmd_text]
        else:
            # По умолчанию PowerShell с NoProfile
            if as_admin and os.name == "nt":
                ps_script = f"Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -Command \"{cmd_text}\"' -Wait"
                runner_cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
            else:
                runner_cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd_text]

        try:
            proc = subprocess.run(
                runner_cmd,
                capture_output=True,
                text=True,
                cwd=str(__root__),
                timeout=timeout_sec,
                encoding="utf-8",
                errors="replace",
            )
            dur_ms = round((time.perf_counter() - t_start) * 1000, 2)
            self.storage.record_execution(command_id)
            return UserCommandExecuteResult(
                command_id=command_id,
                exit_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration_ms=dur_ms,
                executed_at=get_current_iso_time(),
                status="success" if proc.returncode == 0 else "error",
            )
        except subprocess.TimeoutExpired:
            dur_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return UserCommandExecuteResult(
                command_id=command_id,
                exit_code=-2,
                stdout="",
                stderr=f"Превышен таймаут выполнения ({timeout_sec} сек).",
                duration_ms=dur_ms,
                executed_at=get_current_iso_time(),
                status="timeout",
            )
        except Exception as exc:
            dur_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error(f"[UserCommandsService] Ошибка выполнения {command_id}: {exc}")
            return UserCommandExecuteResult(
                command_id=command_id,
                exit_code=-3,
                stdout="",
                stderr=f"Ошибка процесса: {exc}",
                duration_ms=dur_ms,
                executed_at=get_current_iso_time(),
                status="failed",
            )
