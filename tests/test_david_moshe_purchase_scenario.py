# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - David Moshe Cow Purchase Scenario
# =============================================================================
# Description:
#   Модульные тесты презентационного сценария «דוד משה» (עסקת קניית פרה):
#   проверка загрузки pack.json, создания директории сделки, копирования
#   транскрипта, подключения оригиналов к Git-слежению и переключения статусов
#   выполненных/намеченных условий сценария покупки для окна чата.
#
# File: test_david_moshe_purchase_scenario.py
# Project: ai-windows-admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 20:02:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from apps.ai_assistant.core.demo_scenario_pack import DemoScenarioPack
from apps.ai_assistant.core.telegram_workspace_scenario import (
    DEMO_SCENARIOS_DIR,
    TelegramWorkspaceScenarioService,
)


class _DummyGitSync:
    """Заглушка GitSync для проверки коммитов."""

    def __init__(self) -> None:
        self.commits: List[str] = []

    def commit_all(self, ws_path: Path, message: str) -> str:
        self.commits.append(message)
        return "abc12345"


class _DummyWorkspaceManager:
    """Минимальная заглушка WorkspaceManager для изолированного теста сценария."""

    def __init__(self, ws_path: Path) -> None:
        self.ws_path = ws_path
        self.git_sync = _DummyGitSync()
        self.imported_docs: Dict[str, str] = {}
        self.linked_sources: List[str] = []

    def _get_or_create_workspace(self, workspace_id: str) -> tuple[Dict[str, Any], Path]:
        self.ws_path.mkdir(parents=True, exist_ok=True)
        return {"workspace_id": workspace_id, "name": "דוד משה"}, self.ws_path

    def get_workspace(self, workspace_id: str) -> Dict[str, Any]:
        return {"workspace_id": workspace_id, "name": "דוד משה"}

    def import_document(
        self,
        workspace_id: str,
        document_id: str,
        content: str,
        commit_message: str = "",
        language: str = "he",
        paperless_id: Any = None,
    ) -> Dict[str, Any]:
        dest = self.ws_path / document_id
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        self.imported_docs[document_id] = content
        self.git_sync.commit_all(self.ws_path, commit_message)
        return {"commit_hash": "deadbeef", "document_id": document_id}

    def link_source(
        self,
        workspace_id: str,
        target: str,
        name: str = "",
        auto_watch: bool = True,
        host_name: str = "",
    ) -> None:
        self.linked_sources.append(target)


def test_david_moshe_pack_structure() -> None:
    """Проверяет конфигурацию пакета сценария david_moshe (папка עסקת קניית פרה и условия)."""
    pack = DemoScenarioPack.load(DEMO_SCENARIOS_DIR / "david_moshe")
    assert pack.transcript_dest_dir == "עסקת קניית פרה"
    assert pack.data.get("create_extra_notes") is False
    assert pack.data.get("open_chat_on_complete") is True

    purchase = pack.purchase_scenario
    cond_ids = {c["id"]: c["status"] for c in purchase.get("conditions", [])}
    assert cond_ids["audio_saved"] == "completed"
    assert cond_ids["deal_dir_created"] == "completed"
    assert cond_ids["transcript_copied_git"] == "completed"
    assert cond_ids["deal_package_imported"] == "completed"
    assert cond_ids["email_vet"] == "planned"
    assert cond_ids["email_insurer"] == "planned"
    assert cond_ids["schedule_inspection"] == "planned"
    cal_ev = purchase.get("calendar_event", {})
    assert "veterinarian@davidka.net" in cal_ev.get("attendees", [])
    assert "attorney@davidka.net" in cal_ev.get("attendees", [])


def test_audio_upload_creates_deal_dir_tracks_originals_and_opens_chat(tmp_path: Path) -> None:
    """Проверяет полный конвейер: аудио -> עסקת קניית פרה -> транскрипт -> Git -> трекер чата."""
    ws_path = tmp_path / "ws_david_moshe"
    assets_dir = ws_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    audio_file = assets_dir / "דוד משה - שמוליק שיחת טלפון.mp3"
    audio_file.write_bytes(b"fake-mp3-data")

    desktop_dir = tmp_path / "desktop_docs"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    src_transcript = desktop_dir / "02_transcript_david_moshe_shmulik_v3.md"
    src_transcript.write_text("# תמליל שיחה\nדוד משה ושמוליק מדברים על זינה.", encoding="utf-8")
    src_audio = desktop_dir / "דוד משה - שמוליק שיחת טלפון.mp3"
    src_audio.write_bytes(b"orig-mp3-data")

    pkg_dir = tmp_path / "deal_pkg"
    sub_legal = pkg_dir / "01_Legal_and_Purchase"
    sub_legal.mkdir(parents=True, exist_ok=True)
    sample_pdf = sub_legal / "02_handover_protocol_zina_v3.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4\n%fake\n")

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "scenarios": {
                    "david_moshe_telegram": {
                        "enabled": True,
                        "workspace_id": "דוד_משה",
                        "workspace_name": "דוד משה",
                        "deal_dir": "עסקת קניית פרה",
                        "deal_package_dir": str(pkg_dir),
                        "open_chat_on_complete": True,
                        "target_file_path": str(src_transcript),
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    state_file = tmp_path / "scenario_state.json"

    service = TelegramWorkspaceScenarioService(config_path=cfg_path, state_file=state_file)
    wm = _DummyWorkspaceManager(ws_path)

    res = asyncio.run(service.handle_audio_upload_scenario(wm, "דוד_משה", audio_file))
    assert res is not None
    assert res["status"] == "ok"
    assert res["deal_dir"] == "עסקת קניית פרה"
    assert res["transcript_rel"] == "עסקת קניית פרה/02_transcript_david_moshe_shmulik_v3.md"

    copied_file = ws_path / "עסקת קניית פרה" / "02_transcript_david_moshe_shmulik_v3.md"
    assert copied_file.is_file()
    assert "זינה" in copied_file.read_text(encoding="utf-8")

    # Проверяем, что PDF скопирован в עסקת קניית פרה/assets/, а MD — в корне עסקת קניית פרה/ в той же иерархии
    copied_pdf = ws_path / "עסקת קניית פרה" / "assets" / "01_Legal_and_Purchase" / "02_handover_protocol_zina_v3.pdf"
    generated_md = ws_path / "עסקת קניית פרה" / "01_Legal_and_Purchase" / "02_handover_protocol_zina_v3.md"
    assert copied_pdf.is_file()
    assert generated_md.is_file()

    tracked_manifest = ws_path / ".tracked_sources.json"
    assert tracked_manifest.is_file()
    manifest_data = json.loads(tracked_manifest.read_text(encoding="utf-8"))
    assert "עסקת קניית פרה/02_transcript_david_moshe_shmulik_v3.md" in manifest_data
    assert "assets/דוד משה - שמוליק שיחת טלפון.mp3" in manifest_data
    assert str(src_transcript) in wm.linked_sources
    assert str(src_audio) in wm.linked_sources
    assert len(wm.git_sync.commits) >= 2

    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved_state["status"] == "completed"
    assert saved_state["open_chat"] is True
    assert saved_state["run_id"]
    assert saved_state["chat_scenario"]["deal_dir"] == "עסקת קניית פרה"

    # Проверяем обновление статуса намеченного условия на выполненное
    updated_state = service.update_condition_status("email_vet", "completed")
    vet_cond = next(c for c in updated_state["chat_scenario"]["conditions"] if c["id"] == "email_vet")
    assert vet_cond["status"] == "completed"

    # Проверяем занесение осмотра 20.11 в 06:00 в календарь и генерацию .ics с VALARM
    sched_res = service.schedule_cow_inspection(wm, workspace_id="דוד_משה")
    assert sched_res["status"] == "ok"
    assert "veterinarian@davidka.net" in sched_res["attendees"]
    assert "attorney@davidka.net" in sched_res["attendees"]
    ics_file = ws_path / "עסקת קניית פרה" / "zina_inspection_20261120_0600.ics"
    assert ics_file.is_file()
    ics_text = ics_file.read_text(encoding="utf-8")
    assert "mailto:veterinarian@davidka.net" in ics_text
    assert "mailto:attorney@davidka.net" in ics_text
    assert "BEGIN:VALARM" in ics_text
    sched_cond = next(c for c in sched_res["scenario"]["chat_scenario"]["conditions"] if c["id"] == "schedule_inspection")
    assert sched_cond["status"] == "completed"
