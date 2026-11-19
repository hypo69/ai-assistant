# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Skill - Paperless-ngx CLI Tool
# =============================================================================
# Description:
#   CLI-утилита навыка paperless-ngx для проверки доступности Paperless-ngx,
#   просмотра загруженных документов и инкрементальной синхронизации
#   недостающих файлов из рабочих областей AI-Assistant без дубликатов.
#
# Usage Examples:
#   python .agents/skills/paperless-ngx/scripts/paperless_tool.py status
#   python .agents/skills/paperless-ngx/scripts/paperless_tool.py list --workspace דוד_משה
#   python .agents/skills/paperless-ngx/scripts/paperless_tool.py sync-workspace דוד_משה
#
# File: paperless_tool.py
# Project: ai-windows-admin
# Package: skills.paperless_ngx
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 23:07:00
# =============================================================================

from __future__ import annotations
"""CLI-утилита навыка paperless-ngx для диагностики и синхронизации рабочих областей."""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set

# Обеспечиваем импорт модулей проекта при запуске из любой директории
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(_PROJECT_ROOT / ".env")

from logger import logger
from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError
from apps.ai_assistant.core.watchdog_pdf_pipeline import format_paperless_markdown
from apps.ai_assistant.core.workspace_manager import WorkspaceManager

_IGNORED_DIRS: Set[str] = {
    ".git",
    ".workspace",
    ".obsidian",
    ".extracted_snapshots",
    "faiss_indices",
    "__pycache__",
}


def _collect_existing_names(connector: PaperlessConnector, tag_name: str | None = None) -> Set[str]:
    """Собирает множество нормализованных имён и заголовков уже загруженных в Paperless документов."""
    existing: Set[str] = set()
    for doc in connector.iter_documents(tag_name=tag_name):
        for field in ("title", "original_file_name"):
            val = str(doc.get(field) or "").strip().lower()
            if val:
                existing.add(val)
                existing.add(Path(val).stem.lower())
    return existing


def _collect_workspace_files(ws_path: Path, pdf_only: bool = False) -> List[Path]:
    """Рекурсивно собирает поддерживаемые Paperless файлы рабочей области (исключая служебные папки)."""
    files: List[Path] = []
    ws_resolved = ws_path.resolve()
    for item in sorted(ws_resolved.rglob("*")):
        if not item.is_file():
            continue
        try:
            rel_parts = item.relative_to(ws_resolved).parts
        except ValueError:
            continue
        if any(p.startswith(".") or p.lower() in _IGNORED_DIRS for p in rel_parts[:-1]):
            continue
        if item.name.startswith(".") or item.name.startswith("~"):
            continue
        if pdf_only:
            if item.suffix.lower() != ".pdf":
                continue
        else:
            if not PaperlessConnector.is_supported_file(item):
                continue
            # Исключаем системные сгенерированные .md и служебные файлы
            if item.suffix.lower() in {".md", ".txt"}:
                continue
        files.append(item)
    return files


def cmd_status() -> int:
    """Проверяет соединение с Paperless-ngx и выводит базовую статистику."""
    try:
        connector = PaperlessConnector.from_config()
    except PaperlessError as exc:
        logger.console(f"[paperless-ngx] Ошибка конфигурации: {exc}")
        return 1

    try:
        ok = connector.ping()
        logger.console(f"[paperless-ngx] URL: {connector.base_url} | ping: {ok}")
        if not ok:
            return 1
        docs = list(connector.iter_documents())
        logger.console(f"[paperless-ngx] Документов в системе: {len(docs)}")
        return 0
    finally:
        connector.close()


def cmd_list(workspace_id: str | None) -> int:
    """Выводит список документов в Paperless-ngx (всех или по тегу рабочей области)."""
    connector = PaperlessConnector.from_config()
    try:
        if not connector.ping():
            logger.console(f"[paperless-ngx] Сервер недоступен: {connector.base_url}")
            return 1
        tag_name = None
        if workspace_id:
            wm = WorkspaceManager()
            ws = wm.get_workspace(workspace_id)
            ws_name = (ws.get("name") if ws else None) or workspace_id
            tag_name = connector.workspace_tag_name(workspace_id, workspace_name=ws_name)
        docs = list(connector.iter_documents(tag_name=tag_name))
        logger.console(f"[paperless-ngx] Найдено документов: {len(docs)}" + (f" (тег: {tag_name})" if tag_name else ""))
        for doc in docs:
            logger.console(f"  #{doc.get('id')}: {doc.get('title')} ({doc.get('original_file_name')})")
        return 0
    finally:
        connector.close()


def cmd_sync_workspace(workspace_id: str, dry_run: bool = False, pdf_only: bool = False) -> int:
    """Загружает в Paperless-ngx все недостающие поддерживаемые файлы из рабочей области."""
    wm = WorkspaceManager()
    ws = wm.get_workspace(workspace_id)
    if not ws:
        logger.console(f"[paperless-ngx] Рабочая область '{workspace_id}' не найдена.")
        return 1

    ws_path = Path(ws["path"])
    ws_name = str(ws.get("name") or workspace_id)

    connector = PaperlessConnector.from_config()
    try:
        if not connector.ping():
            logger.console(f"[paperless-ngx] Сервер недоступен: {connector.base_url}")
            return 1

        existing_all = _collect_existing_names(connector)
        candidates = _collect_workspace_files(ws_path, pdf_only=pdf_only)
        missing: List[Path] = []
        skipped: List[Path] = []
        for fpath in candidates:
            if fpath.name.lower() in existing_all or fpath.stem.lower() in existing_all:
                skipped.append(fpath)
            else:
                missing.append(fpath)

        logger.console(
            f"[paperless-ngx] Рабочая область '{ws_name}' ({workspace_id}): "
            f"найдено файлов={len(candidates)}, уже в Paperless={len(skipped)}, к загрузке={len(missing)}"
        )
        if dry_run:
            for fpath in missing:
                logger.console(f"  [dry-run] -> {fpath.relative_to(ws_path)}")
            return 0

        uploaded = 0
        failed = 0
        for fpath in missing:
            try:
                res = connector.ingest_file(
                    file_path=fpath,
                    workspace_id=workspace_id,
                    workspace_name=ws_name,
                    title=fpath.stem,
                    timeout=90.0,
                )
                if res and res.get("paperless_id"):
                    uploaded += 1
                    logger.console(f"  [OK] #{res['paperless_id']} <- {fpath.name}")
                else:
                    failed += 1
                    logger.console(f"  [WARN] Таймаут/пустой ответ для {fpath.name}")
            except PaperlessError as exc:
                failed += 1
                logger.console(f"  [ERR] {fpath.name}: {exc}")

        logger.console(
            f"[paperless-ngx] Синхронизация завершена: загружено={uploaded}, пропущено={len(skipped)}, ошибок={failed}"
        )
        return 0 if failed == 0 else 1
    finally:
        connector.close()


def cmd_convert(
    file_path_str: str,
    workspace_id: str = "default",
    output_path_str: str | None = None,
    in_place: bool = False,
) -> int:
    """Конвертирует файл любого поддерживаемого формата в Markdown через Paperless-ngx (OCR/Tika)."""
    file_path = Path(file_path_str).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        logger.console(f"[paperless-ngx] Файл не найден: {file_path}")
        return 1
    if not PaperlessConnector.is_supported_file(file_path):
        supported = ", ".join(sorted(PaperlessConnector.PAPERLESS_SUPPORTED_EXTENSIONS))
        logger.console(f"[paperless-ngx] Неподдерживаемый формат '{file_path.suffix}'. Поддерживаются: {supported}")
        return 1

    wm = WorkspaceManager()
    ws = wm.get_workspace(workspace_id)
    ws_name = str((ws.get("name") if ws else None) or workspace_id)

    connector = PaperlessConnector.from_config()
    try:
        if not connector.ping():
            logger.console(f"[paperless-ngx] Сервер недоступен: {connector.base_url}")
            return 1

        res = connector.ingest_file(
            file_path=file_path,
            workspace_id=workspace_id,
            workspace_name=ws_name,
            title=file_path.stem,
            timeout=90.0,
        )
        if not res or not res.get("paperless_id"):
            logger.console(f"[paperless-ngx] Не удалось обработать файл в Paperless-ngx: {file_path.name}")
            return 1

        pid = int(res["paperless_id"])
        md_text = format_paperless_markdown(
            file_name=file_path.name,
            content=str(res.get("content") or ""),
            paperless_id=pid,
            metadata=dict(res.get("metadata") or {}),
        )
        out_path: Path | None = None
        if output_path_str:
            out_path = Path(output_path_str).expanduser().resolve()
        elif in_place:
            out_path = file_path.with_suffix(".md")

        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_text, encoding="utf-8")
            logger.console(f"[paperless-ngx] Конвертация завершена (#{pid}): {out_path}")
        else:
            logger.console(md_text)
        return 0
    except PaperlessError as exc:
        logger.console(f"[paperless-ngx] Ошибка конвертации: {exc}")
        return 1
    finally:
        connector.close()


def cmd_export_md(document_id: int, output_path_str: str | None = None) -> int:
    """Экспортирует уже загруженный документ Paperless-ngx по его ID в формат Markdown."""
    connector = PaperlessConnector.from_config()
    try:
        if not connector.ping():
            logger.console(f"[paperless-ngx] Сервер недоступен: {connector.base_url}")
            return 1

        meta = connector._request("GET", f"/api/documents/{int(document_id)}/").json()
        content = str(meta.get("content") or "")
        orig_name = str(meta.get("original_file_name") or f"document_{document_id}.pdf")
        md_text = format_paperless_markdown(
            file_name=orig_name,
            content=content,
            paperless_id=int(document_id),
            metadata=meta,
        )
        if output_path_str:
            out_path = Path(output_path_str).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md_text, encoding="utf-8")
            logger.console(f"[paperless-ngx] Экспортировано #{document_id} -> {out_path}")
        else:
            logger.console(md_text)
        return 0
    except PaperlessError as exc:
        logger.console(f"[paperless-ngx] Ошибка экспорта #{document_id}: {exc}")
        return 1
    finally:
        connector.close()


def main() -> int:
    """Точка входа CLI-утилиты paperless-ngx."""
    parser = argparse.ArgumentParser(description="Утилита интеграции AI-Assistant с Paperless-ngx")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Проверить доступность Paperless-ngx и число документов")

    p_list = sub.add_parser("list", help="Показать список документов в Paperless-ngx")
    p_list.add_argument("--workspace", default=None, help="Идентификатор рабочей области (фильтр по тегу)")

    p_sync = sub.add_parser("sync-workspace", help="Загрузить недостающие файлы рабочей области в Paperless-ngx")
    p_sync.add_argument("workspace_id", help="Идентификатор рабочей области (например, דוד_משה)")
    p_sync.add_argument("--dry-run", action="store_true", help="Только показать список файлов без загрузки")
    p_sync.add_argument("--pdf-only", action="store_true", help="Синхронизировать только PDF-файлы")

    p_conv = sub.add_parser("convert", help="Конвертировать файл (PDF/DOCX/XLSX/PPTX/IMG/HTML/TXT) в Markdown через Paperless-ngx")
    p_conv.add_argument("file_path", help="Путь к исходному файлу")
    p_conv.add_argument("--workspace", default="default", help="Тег рабочей области (по умолчанию default)")
    p_conv.add_argument("--output", default=None, help="Путь для сохранения итогового .md файла")
    p_conv.add_argument("--in-place", action="store_true", help="Сохранить <stem>.md рядом с исходным файлом")

    p_exp = sub.add_parser("export-md", help="Получить Markdown для уже загруженного документа по его Paperless ID")
    p_exp.add_argument("document_id", type=int, help="ID документа в Paperless-ngx")
    p_exp.add_argument("--output", default=None, help="Путь для сохранения итогового .md файла")

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status()
    if args.command == "list":
        return cmd_list(args.workspace)
    if args.command == "sync-workspace":
        return cmd_sync_workspace(args.workspace_id, dry_run=args.dry_run, pdf_only=args.pdf_only)
    if args.command == "convert":
        return cmd_convert(args.file_path, workspace_id=args.workspace, output_path_str=args.output, in_place=args.in_place)
    if args.command == "export-md":
        return cmd_export_md(args.document_id, output_path_str=args.output)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
