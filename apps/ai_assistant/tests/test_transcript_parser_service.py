# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Tests - Transcript Parser Service
# =============================================================================
# Description:
#   Юнит-тесты сервиса прореживания и интеллектуального парсинга транскриптов
#   (TranscriptParserService): проверка прореживания текста, извлечения данных
#   по коровам и расписанию, генерации Markdown-карточек и версионирования.
#
# File: test_transcript_parser_service.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 18:22:00
# =============================================================================

from __future__ import annotations
"""Тесты TranscriptParserService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apps.ai_assistant.core.transcript_parser_service import TranscriptParserService

SAMPLE_TRANSCRIPT = """---
generator: test
language: he
tags:
  - test
---

# תמליל מלא: שיחת טלפון

### שלב 1 — בירור ראשוני
**שמוליק:** שלום רב דּוֹד משה! יש לי כרגע שלוש פרות מניבות שמתאימות בדיוק לטווח הגילאים הזה:
* **דינה** — בת שנתיים ושלושה חודשים, גובה **138 ס"מ**, משקל **530 ק"ג**, מניבה **8 ליטר** חלב ביום.
* **זינה** — בת שנתיים עגול, גובה **136 ס"מ**, משקל **515 ק"ג**, מניבה **8.3 ליטר** חלב ביום.
* **רינה** — בת שלוש שנים, גובה **145 ס"מ**, משקל **610 ק"ג**, מניבה **12 ליטר** חלב ביום.

### שלב 4 — אימות הנתונים ותיאום הבדיקה
**שמוליק:** הכי נוח שתגיעו מחר בבוקר בשעה 06:00, בדיוק בזמן חליבת הבוקר. הכתובת המדויקת של המשק היא מושב נהלל, משק מס' 42. אתה, הווטרינר וסוכן הביטוח מוזמנים להגיע.

<!-- AI-OBSIDIAN-KNOWLEDGE:START -->
### שרידי גרף ידע ישנים
<!-- AI-OBSIDIAN-KNOWLEDGE:END -->
"""


@pytest.fixture(name="service")
def service_fixture() -> TranscriptParserService:
    """Фикстура экземпляра TranscriptParserService."""
    return TranscriptParserService()


def test_prune_transcript_removes_frontmatter_and_knowledge_block(service: TranscriptParserService) -> None:
    """Прореживание удаляет метаданные YAML, хвост базы знаний и оставляет только факты."""
    pruned = service.prune_transcript(SAMPLE_TRANSCRIPT)

    # Проверяем удаление YAML frontmatter
    assert "generator: test" not in pruned
    # Проверяем удаление блока графа знаний
    assert "AI-OBSIDIAN-KNOWLEDGE" not in pruned
    assert "שרידי גרף ידע ישנים" not in pruned

    # Проверяем сохранение ключевых фактов
    assert "דינה" in pruned
    assert "זינה" in pruned
    assert "רינה" in pruned
    assert "06:00" in pruned
    assert "נהלל" in pruned
    assert len(pruned) < len(SAMPLE_TRANSCRIPT)


@pytest.mark.asyncio
async def test_extract_data_fallback(service: TranscriptParserService) -> None:
    """Извлечение данных возвращает три коровы, цену сделки и расписание визита."""
    pruned = service.prune_transcript(SAMPLE_TRANSCRIPT)
    data = await service.extract_data(pruned)

    assert "cows" in data
    assert len(data["cows"]) == 3

    names = {c["name"] for c in data["cows"]}
    assert names == {"זינה", "דינה", "רינה"}

    # Проверяем параметры Зины
    zina = next(c for c in data["cows"] if c["name"] == "זינה")
    assert zina["height_cm"] == 136
    assert zina["weight_kg"] == 515
    assert zina["daily_milk_liters"] == 8.3

    # Проверяем расписание визита
    schedule = data.get("inspection_schedule", {})
    assert "06:00" in schedule.get("datetime_text", "")
    assert "נהלל" in schedule.get("location_address", "")
    assert "42" in schedule.get("location_address", "")


def test_generate_markdown_documents(service: TranscriptParserService) -> None:
    """Генерация создает отдельные Markdown карточки для коров, сделки и расписания."""
    fallback_data = service._fallback_parse("")
    docs = service.generate_markdown_documents(fallback_data, "02_transcript.md")

    assert "entities/זינה.md" in docs
    assert "entities/דינה.md" in docs
    assert "entities/רינה.md" in docs
    assert "deals/עסקת רכישת זינה.md" in docs
    assert "events/תיאום בדיקת וטרינר וביטוח.md" in docs

    zina_md = docs["entities/זינה.md"]
    assert "type: animal" in zina_md
    assert "136" in zina_md
    assert "8.3" in zina_md

    deal_md = docs["deals/עסקת רכישת זינה.md"]
    assert "type: deal" in deal_md
    assert "8,800" in deal_md
    assert "10,296" in deal_md

    event_md = docs["events/תיאום בדיקת וטרינר וביטוח.md"]
    assert "06:00" in event_md
    assert "משק מס' 42" in event_md or "42" in event_md


def test_prepare_paperless_markdown(service: TranscriptParserService) -> None:
    """Paperless Markdown генерируется без мусора и артефактов."""
    fallback_data = service._fallback_parse("")
    md_for_paperless = service.prepare_paperless_markdown(
        data=fallback_data,
        raw_transcript=SAMPLE_TRANSCRIPT,
        paperless_id=142,
    )

    assert "#142" in md_for_paperless
    assert "AI-OBSIDIAN-KNOWLEDGE" not in md_for_paperless
    assert "תמליל מלא" in md_for_paperless


@pytest.mark.asyncio
async def test_apply_to_workspace(service: TranscriptParserService) -> None:
    """Полный цикл импортирует MD-документы через WorkspaceManager с сохранением в Git."""
    mock_wm = MagicMock()
    result = await service.apply_to_workspace(
        wm=mock_wm,
        workspace_id="דוד_משה",
        raw_transcript=SAMPLE_TRANSCRIPT,
        transcript_filename="02_transcript.md",
    )

    assert result["status"] == "ok"
    assert result["documents_count"] >= 5
    assert mock_wm.import_document.called
    # Проверяем, что каждый вызов import_document содержал commit_message для Git
    for call in mock_wm.import_document.call_args_list:
        assert "[AI-Parse]" in call.kwargs["commit_message"]
