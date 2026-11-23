# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Assistant Tests - User Commands Suite
# =============================================================================
# Description:
#   Модульные тесты для сервиса и API пользовательской базы знаний команд.
#
# File: test_user_commands.py
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:42:00
# =============================================================================

import os
from pathlib import Path
import tempfile
import pytest

from apps.ai_assistant.core.user_commands.models import UserCommandCreate
from apps.ai_assistant.core.user_commands.service import UserCommandsService
from apps.ai_assistant.core.user_commands.storage import UserCommandsStorage


@pytest.fixture
def temp_commands_service():
    """Создает изолированный сервис с временной SQLite базой и временным Markdown."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_user_commands.db"
        md_path = Path(tmp_dir) / "test_commands.md"
        storage = UserCommandsStorage(db_path=db_path, md_path=md_path)
        service = UserCommandsService(storage=storage)
        yield service


def test_user_commands_crud(temp_commands_service):
    """Тест создания, получения, обновления и удаления команды."""
    srv = temp_commands_service

    # Создание команды
    new_cmd = UserCommandCreate(
        title="Тестовая команда echo",
        command="Write-Output 'Hello Unit Test'",
        shell="powershell",
        category="Тесты",
        description="Проверка создания команды",
        tags=["#test", "#echo"],
        placeholders={},
        risk_level="safe",
        favorite=True,
    )
    saved = srv.save_command(new_cmd)
    assert saved.command_id is not None
    assert saved.title == "Тестовая команда echo"
    assert saved.favorite is True

    # Получение по ID
    fetched = srv.get_command(saved.command_id)
    assert fetched is not None
    assert fetched.command == "Write-Output 'Hello Unit Test'"

    # Поиск по запросу
    found = srv.list_commands(query="Hello Unit Test")
    assert len(found) >= 1
    assert found[0].command_id == saved.command_id

    # Переключение избранного
    is_fav = srv.toggle_favorite(saved.command_id)
    assert is_fav is False
    assert srv.get_command(saved.command_id).favorite is False

    # Удаление
    deleted = srv.delete_command(saved.command_id)
    assert deleted is True
    assert srv.get_command(saved.command_id) is None


def test_user_commands_execution(temp_commands_service):
    """Тест выполнения команды с параметрами."""
    srv = temp_commands_service

    cmd = UserCommandCreate(
        title="Вычисление через Python",
        command="import sys; print(f'RESULT={10 + 20}')",
        shell="python",
        category="Тесты",
    )
    saved = srv.save_command(cmd)

    res = srv.execute_command(saved.command_id, timeout_sec=10)
    assert res.exit_code == 0
    assert "RESULT=30" in res.stdout
    assert res.duration_ms > 0

    # Проверка счетчика запусков
    updated_cmd = srv.get_command(saved.command_id)
    assert updated_cmd.execution_count == 1
    assert updated_cmd.last_executed_at != ""


def test_user_commands_markdown_export(temp_commands_service):
    """Тест автогенерации и синхронизации с Markdown файлом."""
    srv = temp_commands_service
    srv.storage.sync_to_markdown()

    md_file = srv.storage.md_path
    assert md_file.is_file()
    content = md_file.read_text(encoding="utf-8")
    assert "# 📖 База знаний команд и шпаргалка (CheatSheet)" in content
