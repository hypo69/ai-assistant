# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-assistant Apps AI_Assistant Tests - Telegram AI Chat
# =============================================================================
# Description:
#   Юнит-тесты гибридного чата с моделью ИИ в Telegram-боте:
#   разрешение активной модели из конфигурации, режимы auto/chat/rag,
#   история диалога и очистка (/clear), разбивка длинных сообщений,
#   а также интеграция с TelegramBotEngine.
#
# File: test_telegram_chat.py
# Project: ai-assistant
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 22:17:00
# =============================================================================

from __future__ import annotations

"""Тестирование чата с моделью ИИ в плагине Telegram-бота."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from apps.ai_assistant.core.workspace_manager import WorkspaceManager
from plugins.telegram_bot.bot import TelegramBotEngine
from plugins.telegram_bot.chat_handler import (
    TelegramChatService,
    handle_clear_command,
    handle_mode_command,
    resolve_active_model_config,
    split_telegram_message,
)


def test_split_telegram_message_respects_limit() -> None:
    """Проверяет разбиение длинного текста на чанки не длиннее max_len."""
    short = "Короткий ответ"
    assert split_telegram_message(short, max_len=100) == [short]
    assert split_telegram_message("   ", max_len=100) == []

    long_text = "\n\n".join([f"Абзац {i}: " + ("текст " * 30) for i in range(10)])
    chunks = split_telegram_message(long_text, max_len=400)
    assert len(chunks) > 1
    assert all(len(c) <= 400 for c in chunks)
    assert "Абзац 0:" in chunks[0]
    assert "Абзац 9:" in chunks[-1]


def test_resolve_active_model_config_reads_root_config() -> None:
    """Проверяет чтение актуального провайдера и модели из корневого config.json."""
    fake_cfg = {
        "ai_providers_and_models_configuration": {
            "default_provider": "ollama",
            "default_model": "llama3.2:latest",
        }
    }
    with patch("apps.common.models.load_root_config", return_value=fake_cfg):
        provider, model = resolve_active_model_config()
    assert provider == "ollama"
    assert model == "llama3.2:latest"


@pytest.mark.asyncio
async def test_chat_service_auto_uses_rag_when_found(tmp_path: Path) -> None:
    """В режиме auto при найденном факте в базе знаний возвращается ответ с цитатой источника."""
    wm = WorkspaceManager(base_dir=tmp_path / "data_ai", workspaces_dir=tmp_path / "ws")
    wm.create_or_select_workspace("demo_ws", name="Демо область")

    fake_qa = MagicMock()
    fake_qa.ask = AsyncMock(
        return_value={
            "status": "success",
            "answer": "Мама мыла раму.",
            "sources": [{"document_id": "mama.txt", "quote": "Мама мыла раму утром."}],
            "processing": {"provider": "gemini", "model": "gemini-3.5-flash-lite"},
        }
    )

    chat_factory = MagicMock()
    svc = TelegramChatService(workspace_manager=wm, qa_engine=fake_qa, chat_model_factory=chat_factory)

    res = await svc.generate_reply(tg_id=101, user_text="Кто мыл раму?")
    assert res["source"] == "rag"
    assert "Мама мыла раму." in res["text"]
    assert "mama.txt" in res["text"]
    chat_factory.assert_not_called()
    assert len(svc.get_history(101)) == 2


@pytest.mark.asyncio
async def test_chat_service_auto_falls_back_to_llm_with_history(tmp_path: Path) -> None:
    """В режиме auto при недостатке данных в БЗ запрос идёт в UnifiedChatModel с историей."""
    wm = WorkspaceManager(base_dir=tmp_path / "data_ai", workspaces_dir=tmp_path / "ws")
    wm.create_or_select_workspace("demo_ws", name="Демо область")

    fake_qa = MagicMock()
    fake_qa.ask = AsyncMock(
        return_value={
            "status": "insufficient_data",
            "answer": "Недостаточно данных в документах.",
            "sources": [],
        }
    )

    fake_llm = MagicMock()
    fake_llm.chat = AsyncMock(side_effect=["Привет! Чем помочь?", "Конечно, вот пример кода."])
    chat_factory = MagicMock(return_value=fake_llm)

    svc = TelegramChatService(workspace_manager=wm, qa_engine=fake_qa, chat_model_factory=chat_factory)
    with patch(
        "plugins.telegram_bot.chat_handler.resolve_active_model_config",
        return_value=("gemini", "gemini-3.5-flash-lite"),
    ):
        res1 = await svc.generate_reply(tg_id=202, user_text="Привет!")
        res2 = await svc.generate_reply(tg_id=202, user_text="Напиши пример на Python")

    assert res1["source"] == "llm"
    assert res1["text"] == "Привет! Чем помочь?"
    assert res2["text"] == "Конечно, вот пример кода."
    # На втором вызове в модель передалась история из первого обмена
    second_call_kwargs = fake_llm.chat.call_args_list[1].kwargs
    assert second_call_kwargs["history"] == [
        {"role": "user", "content": "Привет!"},
        {"role": "assistant", "content": "Привет! Чем помочь?"},
    ]


@pytest.mark.asyncio
async def test_chat_service_modes_and_clear(tmp_path: Path) -> None:
    """Проверяет режимы chat и rag, а также очистку истории."""
    wm = WorkspaceManager(base_dir=tmp_path / "data_ai", workspaces_dir=tmp_path / "ws")
    wm.create_or_select_workspace("demo_ws", name="Демо область")

    fake_qa = MagicMock()
    fake_qa.ask = AsyncMock(
        return_value={"status": "insufficient_data", "answer": "Нет данных в БЗ.", "sources": []}
    )
    fake_llm = MagicMock()
    fake_llm.chat = AsyncMock(return_value="Ответ напрямую от модели")

    svc = TelegramChatService(
        workspace_manager=wm,
        qa_engine=fake_qa,
        chat_model_factory=MagicMock(return_value=fake_llm),
    )

    # Режим rag: строго по базе знаний без обращения к LLM
    svc.set_mode(303, "rag")
    with patch(
        "plugins.telegram_bot.chat_handler.resolve_active_model_config",
        return_value=("gemini", "gemini-3.5-flash-lite"),
    ):
        res_rag = await svc.generate_reply(303, "Расскажи анекдот")
    assert res_rag["source"] == "rag"
    assert res_rag["text"] == "Нет данных в БЗ."
    fake_llm.chat.assert_not_called()

    # Режим chat: прямой диалог с моделью без вызова QA
    fake_qa.ask.reset_mock()
    svc.set_mode(303, "chat")
    with patch(
        "plugins.telegram_bot.chat_handler.resolve_active_model_config",
        return_value=("gemini", "gemini-3.5-flash-lite"),
    ):
        res_chat = await svc.generate_reply(303, "Расскажи анекдот")
    assert res_chat["source"] == "llm"
    assert res_chat["text"] == "Ответ напрямую от модели"
    fake_qa.ask.assert_not_called()

    assert svc.clear_history(303) == 2
    assert svc.get_history(303) == []


@pytest.mark.asyncio
async def test_bot_engine_text_message_uses_chat_service_without_explicit_ai_model(tmp_path: Path) -> None:
    """Проверяет, что TelegramBotEngine отвечает через модель даже когда ai_model=None."""
    wm = WorkspaceManager(base_dir=tmp_path / "data_ai", workspaces_dir=tmp_path / "ws")
    wm.create_or_select_workspace("demo_ws", name="Демо область")

    engine = TelegramBotEngine(
        token="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_1234567",
        admin_ids=[777],
        ai_model=None,
    )
    fake_qa = MagicMock()
    fake_qa.ask = AsyncMock(return_value={"status": "insufficient_data", "answer": "", "sources": []})
    engine.attach_services(workspace_manager=wm, qa_engine=fake_qa)

    fake_llm = MagicMock()
    fake_llm.chat = AsyncMock(return_value="Готов к работе в Telegram!")
    engine._get_chat_service().chat_model_factory = MagicMock(return_value=fake_llm)

    update = MagicMock()
    update.effective_user.id = 777
    update.effective_user.username = "admin"
    update.effective_user.first_name = "Admin"
    update.message.text = "Привет, бот!"
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    context = MagicMock()

    with (
        patch("plugins.telegram_bot.user_auth._AUTH_FILE", tmp_path / "tg_auth.json"),
        patch(
            "plugins.telegram_bot.chat_handler.resolve_active_model_config",
            return_value=("gemini", "gemini-3.5-flash-lite"),
        ),
    ):
        await engine._handle_text_message(update, context)
        status_text = engine._build_status_message()

    update.message.chat.send_action.assert_awaited_once_with("typing")
    update.message.reply_text.assert_awaited_once_with("Готов к работе в Telegram!")
    assert "gemini:gemini-3.5-flash-lite" in status_text
    assert "Не подключена" not in status_text


@pytest.mark.asyncio
async def test_mode_and_clear_commands(tmp_path: Path) -> None:
    """Проверяет команды /mode и /clear в обработчике чата."""
    svc = TelegramChatService()
    svc._append_history(555, "q", "a")

    update = MagicMock()
    update.effective_user.id = 555
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["chat"]

    await handle_mode_command(update, context, svc)
    assert svc.get_mode(555) == "chat"

    await handle_clear_command(update, context, svc)
    assert svc.get_history(555) == []
