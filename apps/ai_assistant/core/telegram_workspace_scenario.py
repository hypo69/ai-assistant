# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Telegram Workspace Scenario
# =============================================================================
# Description:
#   Сервис оркестрации специального сценария обработки рабочего пространства
#   «דוד משה» при получении файла «שיחה בין דוד משה לשמוליק» через Telegram-бота
#   или WebGUI: запускает 10-секундный индикатор обработки (спиннер) и по
#   завершении таймера добавляет целевой файл в рабочую область с фиксацией
#   в Git, SQLite (KnowledgeStore), векторном индексе FAISS и Obsidian Vault.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.telegram_workspace_scenario import TelegramWorkspaceScenarioService
#
#     service = TelegramWorkspaceScenarioService()
#     state = await service.trigger_scenario(wm, workspace_id="דוד_משה")
#
# File: telegram_workspace_scenario.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 23:16:00
# =============================================================================

from __future__ import annotations
"""Оркестратор специального сценария Telegram-бота для рабочего пространства דוד משה."""

import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import time
import unicodedata
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from header import __root__
from logger import logger
from apps.ai_assistant.core.demo_scenario_pack import DemoScenarioPack
from apps.ai_assistant.core.workspace_registry import (
    format_host_qualified_path,
    get_current_host_name,
)

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

DEMO_SCENARIOS_DIR = __root__ / "apps" / "ai_assistant" / "demo_scenarios"

DEFAULT_SCENARIO_TARGET_FILE = (
    Path.home() / "Desktop" / "דוד מושה — רשימת מסמכים" / "02_transcript_david_moshe_shmulik_v3.md"
)
DEFAULT_DEAL_PACKAGE_DIR = (
    Path.home() / "Desktop" / "דוד מושה — רשימת מסמכים" / "master_complete_cow_deal_package_zina-v5 (1)"
)


def _normalize_hebrew_token(value: Optional[str]) -> str:
    """Нормализует строку для сопоставления ивритских имен пространств и файлов без огласовок."""
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value)).strip()
    # Отбрасываем путь и расширение, если передано полное имя файла
    base = Path(text).name if ("\\" in text or "/" in text) else text
    stem = Path(base).stem if "." in base else base
    # Удаляем диакритические знаки (огласовки иврита niqqud: U+0591..U+05C7)
    no_niqqud = "".join(ch for ch in stem if not (0x0591 <= ord(ch) <= 0x05C7))
    # Приводим пробелы, дефисы и подчеркивания к единому пробелу
    collapsed = re.sub(r"[\s_\-—–]+", " ", no_niqqud).strip().lower()
    return collapsed


class TelegramWorkspaceScenarioService:
    """Управляет специальным сценарием добавления файла через Telegram-бота в рабочую область דוד משה."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        state_file: Optional[Path] = None,
    ) -> None:
        """Инициализирует сервис сценария с загрузкой параметров из config.json."""
        self.config_path = config_path or (__root__ / "apps" / "ai_assistant" / "config.json")
        self.state_file = state_file or (__root__ / "data" / "ai_assistant" / "telegram_scenario_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._active_tasks: Dict[str, asyncio.Task[Any]] = {}

    def load_scenario_config(self) -> Dict[str, Any]:
        """Считывает секцию scenarios.david_moshe_telegram из конфигурационного файла."""
        cfg_data: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                cfg_data = (raw.get("scenarios") or {}).get("david_moshe_telegram") or {}
            except Exception as exc:
                logger.warning(f"[TelegramWorkspaceScenario] Ошибка чтения {self.config_path}: {exc}")

        return {
            "enabled": bool(cfg_data.get("enabled", False)),
            "workspace_id": str(cfg_data.get("workspace_id") or ""),
            "workspace_name": str(cfg_data.get("workspace_name") or "דוד משה"),
            "workspace_aliases": list(
                cfg_data.get("workspace_aliases")
                or ["דוד משה", "דוד_משה", "דוד מושה", "דוד_מושה"]
            ),
            "trigger_file_names": list(
                cfg_data.get("trigger_file_names")
                or [
                    "דוד משה - שמוליק שיחת טלפון.mp3",
                    "דוד משה - שמוליק שיחת טלפון",
                    "דוד משה שמוליק שיחת טלפון",
                    "דוד_משה_-_שמוליק_שיחת_טלפון.mp3",
                    "02_transcript_david_moshe_shmulik_v3.md",
                    "שיחה בין דוד משה לשמוליק",
                    "שיחה_בין_דוד_משה_לשמוליק",
                    "שיחה בין דוד מושה לשמוליק",
                    "שיחה_בין_דוד_מושה_לשמוליק",
                ]
            ),
            "target_file_path": str(
                cfg_data.get("target_file_path")
                or os.environ.get("AI_ASSISTANT_DAVID_MOSHE_TARGET_FILE")
                or DEFAULT_SCENARIO_TARGET_FILE
            ),
            "pack_dir": str(cfg_data.get("pack_dir") or "david_moshe"),
            "deal_dir": str(cfg_data.get("deal_dir") or "עסקת קניית פרה"),
            "deal_package_dir": str(cfg_data.get("deal_package_dir") or DEFAULT_DEAL_PACKAGE_DIR),
            "open_chat_on_complete": bool(cfg_data.get("open_chat_on_complete", True)),
            "delay_seconds": float(cfg_data.get("delay_seconds", 10)),
        }

    def import_deal_package(
        self,
        wm: WorkspaceManager,
        workspace_id: str,
        ws_path: Path,
        deal_dir: str,
        package_dir: Path,
    ) -> Dict[str, Any]:
        """Импортирует пакет сделки: Paperless-first (OCR + paperless_id) с резервным локальным извлечением PDF -> MD."""
        from apps.ai_assistant.core.content_extractor import extract_pdf_text
        from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError

        if not package_dir.exists() or not package_dir.is_dir():
            logger.warning(f"[DavidMosheScenario] Директория пакета сделки не найдена: {package_dir}")
            return {"copied_pdfs": [], "generated_mds": [], "originals": [], "paperless_ids": []}

        deal_root = Path(ws_path) / deal_dir
        assets_root = deal_root / "assets"
        assets_root.mkdir(parents=True, exist_ok=True)

        ws_info = wm.get_workspace(workspace_id) if hasattr(wm, "get_workspace") else None
        ws_name = str((ws_info.get("name") if ws_info else None) or workspace_id)

        connector: Optional[PaperlessConnector] = None
        try:
            cand = PaperlessConnector.from_config()
            if cand.ping():
                connector = cand
            else:
                cand.close()
        except Exception as exc:
            logger.info(f"[DavidMosheScenario] Paperless-ngx недоступен, используется локальный PDF-экстрактор: {exc}")

        copied_pdfs: List[str] = []
        generated_mds: List[str] = []
        originals: List[Tuple[str, Path]] = []
        paperless_ids: List[int] = []

        try:
            for src_file in sorted(package_dir.rglob("*")):
                if not src_file.is_file():
                    continue
                rel_inside_pkg = src_file.relative_to(package_dir)
                dest_asset = assets_root / rel_inside_pkg
                dest_asset.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_asset)
                rel_asset_str = str(dest_asset.relative_to(ws_path)).replace("\\", "/")
                copied_pdfs.append(rel_asset_str)
                originals.append((rel_asset_str, src_file))

                if src_file.suffix.lower() == ".pdf" or (
                    connector is not None and PaperlessConnector.is_supported_file(src_file)
                ):
                    rel_md_inside_deal = rel_inside_pkg.with_suffix(".md")
                    rel_md_str = f"{deal_dir}/{str(rel_md_inside_deal).replace(chr(92), '/')}"
                    asset_link = str(Path("assets") / rel_inside_pkg).replace("\\", "/")
                    extracted = ""
                    paperless_id: Optional[int] = None

                    if connector is not None and PaperlessConnector.is_supported_file(src_file):
                        try:
                            ingest_res = connector.ingest_file(
                                file_path=src_file,
                                workspace_id=workspace_id,
                                workspace_name=ws_name,
                                title=src_file.stem,
                            )
                            if ingest_res and ingest_res.get("paperless_id"):
                                paperless_id = int(ingest_res["paperless_id"])
                                extracted = str(ingest_res.get("content") or "").strip()
                                paperless_ids.append(paperless_id)
                        except (PaperlessError, OSError, ValueError) as exc:
                            logger.warning(f"[DavidMosheScenario] Сбой Paperless для {src_file.name}, fallback: {exc}")

                    if not extracted and src_file.suffix.lower() == ".pdf":
                        extracted = (extract_pdf_text(src_file) or "").strip()

                    front_lines = [
                        "---",
                        f'title: "{src_file.stem}"',
                        f'source_pdf: "[[{asset_link}]]"',
                    ]
                    if paperless_id is not None:
                        front_lines.append(f"paperless_id: {paperless_id}")
                    front_lines.append("---")

                    meta_line = f"**מקור PDF:** `[[{asset_link}]]`"
                    if paperless_id is not None:
                        meta_line += f" • Paperless ID: `#{paperless_id}`"

                    md_content = (
                        "\n".join(front_lines)
                        + f"\n\n# {src_file.stem}\n\n{meta_line}\n\n"
                        + f"{extracted or f'*(Пустой или нераспознанный документ: {src_file.name})*'}\n"
                    )
                    wm.import_document(
                        workspace_id=workspace_id,
                        document_id=rel_md_str,
                        content=md_content,
                        commit_message=f"Пакет сделки ({deal_dir}): {rel_md_inside_deal.as_posix()}",
                        language="he",
                        paperless_id=paperless_id,
                    )
                    generated_mds.append(rel_md_str)
        finally:
            if connector is not None:
                connector.close()

        logger.console(
            f"[DavidMosheScenario] Пакет сделки импортирован: PDF в '{deal_dir}/assets/' ({len(copied_pdfs)}), "
            f"MD в '{deal_dir}/' ({len(generated_mds)}), Paperless ({len(paperless_ids)})."
        )
        return {
            "copied_pdfs": copied_pdfs,
            "generated_mds": generated_mds,
            "originals": originals,
            "paperless_ids": paperless_ids,
        }

    def _build_chat_scenario(
        self,
        cfg: Dict[str, Any],
        deal_dir: str,
        transcript_rel: str,
    ) -> Dict[str, Any]:
        """Формирует структуру сценария покупки для отображения в окне чата с поддержкой мультиязычности (i18n)."""
        pack_dir = DEMO_SCENARIOS_DIR / cfg["pack_dir"]
        scenario_data: Dict[str, Any] = {}
        try:
            pack = DemoScenarioPack.load(pack_dir)
            scenario_data = pack.purchase_scenario
        except Exception as exc:
            logger.warning(f"[DavidMosheScenario] Не удалось загрузить purchase_scenario из pack.json: {exc}")

        return {
            "scenario_id": "david_moshe_cow_deal",
            "open_chat": bool(cfg.get("open_chat_on_complete", True)),
            "deal_dir": deal_dir,
            "transcript_rel": transcript_rel,
            "title": str(scenario_data.get("title") or f"{deal_dir} — זינה"),
            "title_i18n": dict(scenario_data.get("title_i18n") or {}),
            "summary": str(scenario_data.get("summary") or ""),
            "summary_i18n": dict(scenario_data.get("summary_i18n") or {}),
            "conditions": list(scenario_data.get("conditions") or []),
            "calendar_event": dict(scenario_data.get("calendar_event") or {}),
        }

    def _track_original_sources(
        self,
        wm: WorkspaceManager,
        workspace_id: str,
        ws_path: Path,
        originals: List[Tuple[str, Path]],
    ) -> List[str]:
        """Подключает оригинальные файлы на диске для слежения Git (link_source + .tracked_sources.json)."""
        cur_host = get_current_host_name()
        manifest_file = Path(ws_path) / ".tracked_sources.json"
        manifest_data: Dict[str, Any] = {}
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                manifest_data = {}

        linked: List[str] = []
        for rel_key, orig_path in originals:
            if not orig_path or not orig_path.exists() or not orig_path.is_file():
                continue
            try:
                wm.link_source(
                    workspace_id=workspace_id,
                    target=str(orig_path),
                    name=orig_path.stem,
                    auto_watch=True,
                    host_name=cur_host,
                )
            except Exception as link_exc:
                logger.debug(f"[DavidMosheScenario] Привязка внешнего источника '{orig_path}': {link_exc}")

            try:
                st = orig_path.stat()
                qual_path = format_host_qualified_path(orig_path, cur_host)
                manifest_data[rel_key] = {
                    "host_name": cur_host,
                    "file_path": str(orig_path),
                    "qualified_path": qual_path,
                    "updated_at": time.time(),
                    "source_mtime": st.st_mtime,
                    "source_size": st.st_size,
                }
                linked.append(str(orig_path))
            except OSError as st_exc:
                logger.debug(f"[DavidMosheScenario] Ошибка stat для '{orig_path}': {st_exc}")

        if linked:
            try:
                tmp_manifest = manifest_file.with_suffix(".json.tmp")
                tmp_manifest.write_text(
                    json.dumps(manifest_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                os.replace(tmp_manifest, manifest_file)
                commit_msg = f"Сценарий דוד משה: подключены оригиналы для слежения Git ({len(linked)})"
                if hasattr(wm, "_run_git"):
                    wm._run_git(ws_path, ["add", ".tracked_sources.json"])
                    if wm._run_git(ws_path, ["status", "--porcelain", ".tracked_sources.json"]):
                        wm._run_git(ws_path, ["commit", "-m", commit_msg])
                elif hasattr(wm, "git_sync"):
                    wm.git_sync.commit_all(ws_path, commit_msg)
            except Exception as man_exc:
                logger.debug(f"[DavidMosheScenario] Сохранение/коммит .tracked_sources.json: {man_exc}")
        return linked

    def update_condition_status(self, condition_id: str, new_status: str) -> Dict[str, Any]:
        """Обновляет статус отдельного условия сценария покупки и сохраняет состояние."""
        allowed = {"completed", "planned", "in_progress"}
        clean_status = new_status if new_status in allowed else "completed"
        state = self._read_state()
        chat_scen = state.get("chat_scenario")
        if not isinstance(chat_scen, dict):
            cfg = self.load_scenario_config()
            chat_scen = self._build_chat_scenario(
                cfg=cfg,
                deal_dir=cfg["deal_dir"],
                transcript_rel=f"{cfg['deal_dir']}/02_transcript_david_moshe_shmulik_v3.md",
            )
            state["chat_scenario"] = chat_scen

        updated = False
        for cond in chat_scen.get("conditions", []):
            if str(cond.get("id")) == condition_id:
                cond["status"] = clean_status
                cond["updated_at"] = time.time()
                updated = True
                break

        if updated:
            self._write_state(state)
        return state

    @staticmethod
    def _build_ics_invite(
        uid: str,
        summary: str,
        description: str,
        location: str,
        dtstart_utc: str,
        dtend_utc: str,
        attendees: List[str],
        language: str = "he",
    ) -> str:
        """Генерирует iCalendar (.ics) приглашение с METHOD:REQUEST и двумя будильниками VALARM (12ч и 1ч)."""
        clean_lang = str(language or "he").lower()[:2]
        alarm_12h_labels = {
            "he": "תזכורת (12 שעות)",
            "ru": "Напоминание (12ч)",
            "en": "Reminder (12h)",
            "uk": "Нагадування (12 год)",
        }
        alarm_1h_labels = {
            "he": "תזכורת (שעה)",
            "ru": "Напоминание (1ч)",
            "en": "Reminder (1h)",
            "uk": "Нагадування (1 год)",
        }
        lbl_12h = alarm_12h_labels.get(clean_lang, alarm_12h_labels["he"])
        lbl_1h = alarm_1h_labels.get(clean_lang, alarm_1h_labels["he"])

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AI-Assistant//David Moshe Cow Deal//HE",
            "CALSCALE:GREGORIAN",
            "METHOD:REQUEST",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"SUMMARY:{summary}",
            f"DTSTART:{dtstart_utc}",
            f"DTEND:{dtend_utc}",
            f"LOCATION:{location}",
            f"DESCRIPTION:{description.replace(chr(10), ' ')}",
            "STATUS:CONFIRMED",
        ]
        for email in attendees:
            clean_email = email.strip()
            if clean_email:
                lines.append(
                    f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{clean_email}"
                )
        # Напоминание за 12 часов (720 минут)
        lines.extend([
            "BEGIN:VALARM",
            "TRIGGER:-PT12H",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{lbl_12h}: {summary}",
            "END:VALARM",
            # Напоминание за 1 час (60 минут)
            "BEGIN:VALARM",
            "TRIGGER:-PT1H",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{lbl_1h}: {summary}",
            "END:VALARM",
            "END:VEVENT",
            "END:VCALENDAR",
        ])
        return "\r\n".join(lines) + "\r\n"

    def schedule_cow_inspection(
        self,
        wm: WorkspaceManager,
        workspace_id: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Заносит осмотр коровы 20.11 в 06:00 в Google Calendar с напоминаниями и сохраняет .ics в рабочую область."""
        cfg = self.load_scenario_config()
        ws_id = self.resolve_david_moshe_workspace_id(wm, preferred_id=workspace_id)
        deal_dir = cfg.get("deal_dir") or "עסקת קניית פרה"
        clean_lang = str(language or "he").lower()[:2]

        pack = DemoScenarioPack.load(DEMO_SCENARIOS_DIR / cfg["pack_dir"])
        cal_cfg = pack.purchase_scenario.get("calendar_event") or {}
        summary_i18n = cal_cfg.get("summary_i18n") if isinstance(cal_cfg.get("summary_i18n"), dict) else {}
        desc_i18n = cal_cfg.get("description_i18n") if isinstance(cal_cfg.get("description_i18n"), dict) else {}

        summary = str(
            summary_i18n.get(clean_lang)
            or cal_cfg.get("summary")
            or "בדיקת הפרה זינה במשק שמוליק — דוד משה"
        )
        start_iso = str(start_time or cal_cfg.get("start_time") or "2026-11-20T06:00:00+02:00")
        end_iso = str(end_time or cal_cfg.get("end_time") or "2026-11-20T07:00:00+02:00")
        location = str(cal_cfg.get("location") or "מושב נהלל, משק מס' 42")
        description = str(
            desc_i18n.get(clean_lang)
            or cal_cfg.get("description")
            or ""
        )
        target_attendees = list(
            attendees
            or cal_cfg.get("attendees")
            or ["veterinarian@davidka.net", "attorney@davidka.net"]
        )
        reminders = list(
            cal_cfg.get("reminders")
            or [{"method": "email", "minutes": 720}, {"method": "popup", "minutes": 60}]
        )

        # 1. Генерируем и сохраняем .ics файл с VALARM в папку сделки (и фиксируем в Git)
        ics_rel = f"{deal_dir}/zina_inspection_20261120_0600.ics"
        ics_content = self._build_ics_invite(
            uid="zina-inspection-20261120-0600@davidka.net",
            summary=summary,
            description=description,
            location=location,
            dtstart_utc="20261120T040000Z",
            dtend_utc="20261120T050000Z",
            attendees=target_attendees,
            language=clean_lang,
        )
        wm.import_document(
            workspace_id=ws_id,
            document_id=ics_rel,
            content=ics_content,
            commit_message=f"Календарное приглашение (.ics): осмотр коровы Зины 20.11 06:00 ({', '.join(target_attendees)})",
            language="he",
        )

        # 2. Создаем событие в Google Calendar с отправкой приглашений (sendUpdates='all') и напоминаниями
        gcal_res: Dict[str, Any] = {"status": "skipped"}
        try:
            import importlib.util

            client_path = __root__ / ".agents" / "skills" / "google-calendar" / "scripts" / "calendar_client.py"
            spec = importlib.util.spec_from_file_location("google_calendar_client_mod", client_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                client = mod.GoogleCalendarClient()
                gcal_res = client.create_event(
                    summary=summary,
                    start_time=start_iso,
                    end_time=end_iso,
                    description=description,
                    location=location,
                    attendees=target_attendees,
                    send_updates="all",
                    reminders=reminders,
                )
        except Exception as cal_exc:
            logger.warning(f"[DavidMosheScenario] Google Calendar API вернул ошибку: {cal_exc}")
            gcal_res = {"status": "error", "error": str(cal_exc)}

        # 3. Отмечаем условие schedule_inspection выполненным
        state = self.update_condition_status("schedule_inspection", "completed")
        logger.console(
            f"[DavidMosheScenario] Осмотр коровы 20.11 06:00 запланирован для {target_attendees} "
            f"(ICS: {ics_rel}, GCal: {gcal_res.get('status')})."
        )
        return {
            "status": "ok",
            "workspace_id": ws_id,
            "summary": summary,
            "start_time": start_iso,
            "end_time": end_iso,
            "location": location,
            "attendees": target_attendees,
            "reminders": reminders,
            "ics_rel": ics_rel,
            "google_calendar": gcal_res,
            "scenario": state,
        }

    def is_david_moshe_workspace(self, workspace_id_or_name: Optional[str]) -> bool:
        """Проверяет, соответствует ли переданный идентификатор или название рабочему пространству דוד משה."""
        if not workspace_id_or_name:
            return False
        cfg = self.load_scenario_config()
        if not cfg.get("enabled", True):
            return False
        norm_candidate = _normalize_hebrew_token(workspace_id_or_name)
        if not norm_candidate:
            return False
        aliases: List[str] = [
            cfg["workspace_id"],
            cfg["workspace_name"],
            *cfg.get("workspace_aliases", []),
        ]
        for alias in aliases:
            if _normalize_hebrew_token(alias) == norm_candidate:
                return True
        return False

    def is_trigger_file(self, filename_or_text: Optional[str]) -> bool:
        """Проверяет, соответствует ли имя файла, подпись или текст триггеру «שיחה בין דוד משה לשמוליק»."""
        if not filename_or_text:
            return False
        cfg = self.load_scenario_config()
        if not cfg.get("enabled", True):
            return False
        norm_input = _normalize_hebrew_token(filename_or_text)
        raw_clean = re.sub(r"[\s_\-—–]+", " ", str(filename_or_text)).strip().lower()
        for trigger in cfg.get("trigger_file_names", []):
            norm_trig = _normalize_hebrew_token(trigger)
            if not norm_trig:
                continue
            if norm_input == norm_trig or norm_trig in norm_input or norm_trig in raw_clean:
                return True
        return False

    async def handle_audio_upload_scenario(
        self,
        wm: WorkspaceManager,
        workspace_id: str,
        audio_path: Path,
    ) -> Optional[Dict[str, Any]]:
        """Копирует целевой транскрипт туда же, куда сохранен аудиофайл דוד משה, с фиксацией в Git и базе знаний.

        Args:
            wm: Экземпляр WorkspaceManager.
            workspace_id: Идентификатор рабочей области.
            audio_path: Абсолютный путь к сохраненному аудиофайлу на диске.

        Returns:
            Словарь с данными о скопированном транскрипте или None, если сценарий не сработал.
        """
        if not self.is_david_moshe_workspace(workspace_id):
            return None

        clean_name = audio_path.name
        is_trigger = self.is_trigger_file(clean_name)
        if not is_trigger:
            norm_name = _normalize_hebrew_token(clean_name)
            if "דוד משה" in norm_name and "שמוליק" in norm_name:
                is_trigger = True

        if not is_trigger:
            return None

        cfg = self.load_scenario_config()
        if not cfg.get("enabled", True):
            return None

        target_path_str = cfg.get("target_file_path") or str(DEFAULT_SCENARIO_TARGET_FILE)
        candidate_paths = [
            Path(target_path_str),
            Path.home() / "Desktop" / "דוד מושה — רשימת מסמכים" / "02_transcript_david_moshe_shmulik_v3.md",
            Path.home() / "Desktop" / "דוד מושה — רשימת מסמכים" / "שיחה בין דוד משה לשמוליק.md",
            audio_path.parent / "02_transcript_david_moshe_shmulik_v3.md",
            audio_path.parent.parent / "02_transcript_david_moshe_shmulik_v3.md",
        ]
        src_transcript: Optional[Path] = None
        for cand in candidate_paths:
            if cand.exists() and cand.is_file():
                src_transcript = cand
                break

        dest_filename = src_transcript.name if src_transcript else Path(target_path_str).name
        transcript_text = ""
        if src_transcript:
            try:
                transcript_text = src_transcript.read_text(encoding="utf-8")
            except OSError as read_exc:
                logger.error(f"[DavidMosheScenario] Ошибка чтения транскрипта: {read_exc}")

        _, ws_path = wm._get_or_create_workspace(workspace_id)
        deal_dir = cfg.get("deal_dir") or "עסקת קניית פרה"
        deal_dir_path = ws_path / deal_dir
        deal_dir_path.mkdir(parents=True, exist_ok=True)

        rel_doc_id = f"{deal_dir}/{dest_filename}"
        dest_transcript_path = deal_dir_path / dest_filename
        if transcript_text:
            audio_path.with_name(f"{audio_path.name}.md").write_text(transcript_text, encoding="utf-8")
            pack = DemoScenarioPack.load(DEMO_SCENARIOS_DIR / cfg["pack_dir"])
            audio_rel = str(audio_path.relative_to(ws_path)).replace("\\", "/")
            pack_res = await pack.apply(
                wm=wm,
                workspace_id=workspace_id,
                transcript_text=transcript_text,
                audio_rel=audio_rel,
                workspace_name=cfg["workspace_name"],
                transcript_name=dest_filename,
            )
            rel_doc_id = pack_res["transcript_rel"]
            dest_transcript_path = ws_path / rel_doc_id
            logger.console(
                f"[DavidMosheScenario] Директория '{deal_dir}' создана, транскрипт '{dest_filename}' "
                f"скопирован в '{rel_doc_id}' и зафиксирован в Git."
            )

        originals_to_track: List[Tuple[str, Path]] = []
        if src_transcript:
            originals_to_track.append((rel_doc_id, src_transcript))
            desktop_audio = src_transcript.parent / clean_name
            if desktop_audio.exists() and desktop_audio.is_file():
                originals_to_track.append((f"assets/{clean_name}", desktop_audio))

        pkg_dir = Path(cfg.get("deal_package_dir") or DEFAULT_DEAL_PACKAGE_DIR)
        pkg_res = await asyncio.to_thread(
            self.import_deal_package, wm, workspace_id, ws_path, deal_dir, pkg_dir
        )
        originals_to_track.extend(pkg_res.get("originals", []))
        linked_originals = self._track_original_sources(wm, workspace_id, ws_path, originals_to_track)

        now_ts = time.time()
        run_id = uuid.uuid4().hex[:12]
        chat_scenario = self._build_chat_scenario(cfg, deal_dir=deal_dir, transcript_rel=rel_doc_id)
        state: Dict[str, Any] = {
            "run_id": run_id,
            "status": "completed",
            "workspace_id": workspace_id,
            "deal_dir": deal_dir,
            "open_chat": bool(chat_scenario.get("open_chat", True)),
            "trigger_file": clean_name,
            "target_file_path": str(src_transcript or dest_transcript_path),
            "target_file_name": dest_filename,
            "destination_file": str(dest_transcript_path),
            "linked_originals": linked_originals,
            "completed_at": now_ts,
            "chat_scenario": chat_scenario,
            "result": {
                "deal_dir": deal_dir,
                "transcript_file": dest_filename,
                "transcript_path": str(dest_transcript_path),
                "transcript_rel": rel_doc_id,
                "audio_file": clean_name,
                "linked_originals": linked_originals,
                "copied": bool(src_transcript and dest_transcript_path.exists()),
            },
        }
        self._write_state(state)

        return {
            "status": "ok",
            "scenario": "david_moshe_audio_transcript",
            "run_id": run_id,
            "deal_dir": deal_dir,
            "audio_path": str(audio_path),
            "transcript_path": str(dest_transcript_path),
            "transcript_name": dest_filename,
            "transcript_rel": rel_doc_id,
            "transcript_text": transcript_text,
            "chat_scenario": chat_scenario,
            "file_info": {
                "name": rel_doc_id or dest_filename,
                "path": str(dest_transcript_path),
                "size": dest_transcript_path.stat().st_size if dest_transcript_path.exists() else 0,
                "type": "uploaded_file",
                "source": "david_moshe_scenario_transcript",
                "rel_path": rel_doc_id or dest_filename,
                "converted": False,
                "is_raw": False,
                "in_assets": False,
                "tracked_by_git": True,
            },
        }

    def resolve_david_moshe_workspace_id(self, wm: WorkspaceManager, preferred_id: Optional[str] = None) -> str:
        """Находит существующий идентификатор рабочей области דוד משה в реестре или возвращает канонический."""
        if preferred_id and self.is_david_moshe_workspace(preferred_id):
            ws = wm.get_workspace(preferred_id)
            if ws and ws.get("workspace_id"):
                return str(ws["workspace_id"])
        for ws in wm.registry.list_workspaces():
            ws_id = str(ws.get("workspace_id") or "")
            ws_name = str(ws.get("name") or "")
            if self.is_david_moshe_workspace(ws_id) or self.is_david_moshe_workspace(ws_name):
                return ws_id
        cfg = self.load_scenario_config()
        return str(cfg["workspace_id"])

    def _read_state(self) -> Dict[str, Any]:
        """Считывает текущее состояние сценария из JSON-файла синхронизации."""
        if not self.state_file.exists():
            return {"status": "idle"}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"status": "idle"}
        except Exception as exc:
            logger.debug(f"[TelegramWorkspaceScenario] Ошибка чтения файла состояния: {exc}")
            return {"status": "idle"}

    def _write_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Атомарно записывает состояние сценария в JSON-файл для межпроцессной синхронизации (бот <-> WebGUI)."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.state_file.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_path, self.state_file)
        except Exception as exc:
            logger.warning(f"[TelegramWorkspaceScenario] Не удалось сохранить состояние: {exc}")
        return state

    async def trigger_scenario(
        self,
        wm: WorkspaceManager,
        workspace_id: Optional[str] = None,
        trigger_source: str = "telegram_bot",
        trigger_file_name: Optional[str] = None,
        delay_seconds: Optional[float] = None,
        wait_for_completion: bool = False,
    ) -> Dict[str, Any]:
        """Запускает сценарий: выставляет статус processing (для спиннера) и планирует добавление файла через 10 секунд."""
        cfg = self.load_scenario_config()
        if not cfg.get("enabled", False):
            return {"status": "disabled", "message": "Сценарий отключен"}
        resolved_ws_id = self.resolve_david_moshe_workspace_id(wm, preferred_id=workspace_id)

        ws = wm.get_workspace(resolved_ws_id)
        if not ws:
            raise ValueError(f"Рабочая область '{resolved_ws_id}' не найдена. Создайте её вручную.")
        try:
            wm.store.set_active_workspace(resolved_ws_id)
        except Exception as exc:
            logger.debug(f"[TelegramWorkspaceScenario] Не удалось переключить активную область: {exc}")

        effective_delay = float(delay_seconds if delay_seconds is not None else cfg["delay_seconds"])
        run_id = uuid.uuid4().hex[:12]
        now_ts = time.time()
        target_path = cfg["target_file_path"]
        trigger_label = trigger_file_name or cfg["trigger_file_names"][0]

        state: Dict[str, Any] = {
            "run_id": run_id,
            "status": "processing",
            "workspace_id": resolved_ws_id,
            "workspace_name": ws.get("name") or cfg["workspace_name"],
            "trigger_source": trigger_source,
            "trigger_file": trigger_label,
            "target_file_path": target_path,
            "target_file_name": Path(target_path).name,
            "delay_seconds": effective_delay,
            "started_at": now_ts,
            "completed_at": None,
            "elapsed_seconds": 0.0,
            "remaining_seconds": effective_delay,
        }
        self._write_state(state)
        logger.console(
            f"[TelegramScenario] Запущен сценарий для '{resolved_ws_id}' (источник: {trigger_source}, "
            f"файл: '{trigger_label}', ожидание: {effective_delay} сек) -> {target_path}"
        )

        if wait_for_completion:
            if effective_delay > 0:
                await asyncio.sleep(effective_delay)
            return await self.complete_scenario(wm, run_id=run_id)

        task = asyncio.create_task(self._delayed_complete_worker(wm, run_id, effective_delay))
        self._active_tasks[run_id] = task
        return state

    async def _delayed_complete_worker(
        self,
        wm: WorkspaceManager,
        run_id: str,
        delay_seconds: float,
    ) -> None:
        """Фоновая корутина ожидания таймера спиннера и последующего добавления файла."""
        try:
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            await self.complete_scenario(wm, run_id=run_id)
        except Exception as exc:
            logger.error(f"[TelegramWorkspaceScenario] Ошибка фонового завершения сценария {run_id}: {exc}")
        finally:
            self._active_tasks.pop(run_id, None)

    async def complete_scenario(
        self,
        wm: WorkspaceManager,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Завершает сценарий: добавляет целевой файл с рабочего стола в рабочую область דוד משה."""
        state = self._read_state()
        if run_id and state.get("run_id") and state.get("run_id") != run_id:
            return state
        if state.get("status") == "completed" and state.get("result"):
            return state

        cfg = self.load_scenario_config()
        ws_id = str(state.get("workspace_id") or self.resolve_david_moshe_workspace_id(wm))
        target_path_str = str(state.get("target_file_path") or cfg["target_file_path"])
        target_path = Path(target_path_str)

        try:
            if not target_path.exists():
                for alt_cand in [
                    DEFAULT_SCENARIO_TARGET_FILE,
                    Path.home() / "Desktop" / "דוד מושה — רשימת מסמכים" / "02_transcript_david_moshe_shmulik_v3.md",
                    Path.home() / "Desktop" / "דוד מושה — רשימת מסמכים" / "שיחה בין דוד משה לשמוליק.md",
                ]:
                    if alt_cand.exists() and alt_cand.is_file():
                        target_path = alt_cand
                        break
            if not target_path.exists():
                raise FileNotFoundError(f"Целевой файл сценария не найден: {target_path_str}")

            _, ws_path = wm._get_or_create_workspace(ws_id)
            deal_dir = cfg.get("deal_dir") or "עסקת קניית פרה"
            deal_dir_path = Path(ws_path) / deal_dir
            deal_dir_path.mkdir(parents=True, exist_ok=True)

            # 1. Копируем транскрипт в директорию עסקת קניית פרה и фиксируем в Git + SQLite + FAISS + Obsidian
            rel_doc_id = f"{deal_dir}/{target_path.name}"
            transcript_text = target_path.read_text(encoding="utf-8")
            commit_msg = f"Telegram сценарий (דוד משה): добавлен {rel_doc_id}"
            import_res = wm.import_document(
                workspace_id=ws_id,
                document_id=rel_doc_id,
                content=transcript_text,
                commit_message=commit_msg,
                language="he",
            )

            # 2. Если оригинал аудиофайла есть рядом на рабочем столе и отсутствует в assets/, копируем и его
            desktop_audio = target_path.parent / "דוד משה - שמוליק שיחת טלפון.mp3"
            originals_to_track: List[Tuple[str, Path]] = [(rel_doc_id, target_path)]
            if desktop_audio.exists() and desktop_audio.is_file():
                assets_dir = Path(ws_path) / "assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                dest_audio = assets_dir / desktop_audio.name
                if not dest_audio.exists():
                    shutil.copy2(desktop_audio, dest_audio)
                originals_to_track.append((f"assets/{desktop_audio.name}", desktop_audio))

            # 3. Копируем пакет сделки (PDF -> עסקת קניית פרה/assets/, MD -> עסקת קניית פרה/)
            pkg_dir = Path(cfg.get("deal_package_dir") or DEFAULT_DEAL_PACKAGE_DIR)
            pkg_res = await asyncio.to_thread(
                self.import_deal_package, wm, ws_id, Path(ws_path), deal_dir, pkg_dir
            )
            originals_to_track.extend(pkg_res.get("originals", []))

            # 4. Подключаем оригиналы на диске для слежения Git
            linked_originals = self._track_original_sources(wm, ws_id, Path(ws_path), originals_to_track)

            now_ts = time.time()
            started_at = float(state.get("started_at") or now_ts)
            chat_scenario = self._build_chat_scenario(cfg, deal_dir=deal_dir, transcript_rel=rel_doc_id)
            state.update({
                "status": "completed",
                "workspace_id": ws_id,
                "deal_dir": deal_dir,
                "open_chat": bool(chat_scenario.get("open_chat", True)),
                "target_file_path": str(target_path),
                "target_file_name": target_path.name,
                "destination_file": str(deal_dir_path / target_path.name),
                "linked_originals": linked_originals,
                "completed_at": now_ts,
                "elapsed_seconds": round(max(0.0, now_ts - started_at), 2),
                "remaining_seconds": 0.0,
                "chat_scenario": chat_scenario,
                "result": {
                    "deal_dir": deal_dir,
                    "transcript_rel": rel_doc_id,
                    "files_added": 1,
                    "git_head": str(import_res.get("commit_hash") or ""),
                    "linked_originals": linked_originals,
                },
            })
            self._write_state(state)
            logger.console(
                f"[TelegramScenario] Сценарий завершён: '{rel_doc_id}' добавлен в '{ws_id}', оригиналы на Git-слежении."
            )
            return state
        except Exception as exc:
            logger.error(f"[TelegramWorkspaceScenario] Ошибка добавления целевого файла: {exc}")
            state.update({
                "status": "error",
                "error": str(exc),
                "completed_at": time.time(),
                "remaining_seconds": 0.0,
            })
            self._write_state(state)
            return state

    async def get_status(self, wm: WorkspaceManager) -> Dict[str, Any]:
        """Возвращает актуальный статус сценария и автоматически завершает его по истечении 10 секунд."""
        state = self._read_state()
        status = state.get("status", "idle")
        if status == "processing":
            now_ts = time.time()
            started_at = float(state.get("started_at") or now_ts)
            delay = float(state.get("delay_seconds") or 10.0)
            elapsed = max(0.0, now_ts - started_at)
            remaining = max(0.0, delay - elapsed)
            state["elapsed_seconds"] = round(elapsed, 2)
            state["remaining_seconds"] = round(remaining, 2)
            if elapsed >= delay:
                state = await self.complete_scenario(wm, run_id=state.get("run_id"))
        return state
