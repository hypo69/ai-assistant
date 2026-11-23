# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant Core - Workspace Creator Engine
# =============================================================================
# Description:
#   Движок интеллектуального создания рабочего пространства на основе
#   локальной директории на диске (In-Place Grounding).
#   Выполняет полный инженерный протокол:
#   1. Аудит и профилирование локальной папки (файлы, типы, доминирующий язык, домен).
#   2. Генерация адаптивного имени, идентификатора и семантического описания.
#   3. Инициализация рабочей области через WorkspaceManager и WorkspaceRegistry.
#   4. Привязка локальной папки без перемещения файлов (Git-версионирование на месте).
#   5. Настройка Obsidian Vault, адаптивного .gitignore и единого манифеста.
#   6. Создание контекстно-обогащенного README.md на языке документов.
#   7. Индексация контента, извлечение фактов, построение FAISS и стартовых prompt chips.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_creator_engine import WorkspaceCreatorEngine
#     from apps.ai_assistant.core.workspace_manager import WorkspaceManager
#
#     wm = WorkspaceManager()
#     engine = WorkspaceCreatorEngine(wm)
#     audit = engine.audit_directory("C:/Users/.../Desktop/דוד מושה")
#     res = await engine.create_workspace_from_directory("C:/Users/.../Desktop/דוד מושה")
#
# File: workspace_creator_engine.py
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 16:59:00
# =============================================================================

from __future__ import annotations
"""Движок создания рабочих пространств на базе анализа локальных директорий."""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from logger import logger
from apps.ai_assistant.core.git_i18n import get_git_commit_msg
from apps.ai_assistant.core.nlp_analyzers import detect_language
from apps.ai_assistant.core.service_file_authenticator import ServiceFileAuthenticator
from apps.ai_assistant.core.workspace_prompt_generator import WorkspacePromptGenerator
from apps.ai_assistant.core.workspace_registry import (
    build_workspace_gitignore,
    get_current_host_name,
    get_readme_locale,
    load_workspace_config,
    parse_host_qualified_path,
    resolve_workspace_language,
)

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

_RE_HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")


class WorkspaceCreatorEngine:
    """Сервис аудита и интеллектуального создания рабочих пространств из локальной папки."""

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        """Инициализирует движок с внедрением экземпляра WorkspaceManager.

        Args:
            workspace_manager: Менеджер рабочих пространств приложения.
        """
        self.wm = workspace_manager

    def audit_directory(self, directory_path: str | Path) -> Dict[str, Any]:
        """Выполняет глубокий аудит локальной директории перед созданием пространства.

        Args:
            directory_path: Локальный путь к целевой директории на диске.

        Returns:
            Словарь с профилем директории (статистика файлов, языки, рекомендуемые метаданные).

        Raises:
            FileNotFoundError: Если директория не существует на диске.
            NotADirectoryError: Если переданный путь является файлом.
        """
        raw_p = str(directory_path).strip()
        _, clean_str, qual_p = parse_host_qualified_path(raw_p)
        target_dir = Path(clean_str).resolve()

        if not target_dir.exists():
            raise FileNotFoundError(f"Локальная директория не найдена: {clean_str}")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"Указанный путь не является директорией: {clean_str}")

        ws_cfg = load_workspace_config()
        text_exts = {str(e).lower() for e in getattr(ws_cfg, "supported_text_extensions", [])}

        files_found: List[Path] = []
        ext_counts: Dict[str, int] = {}
        total_size = 0
        sample_texts: List[str] = []

        try:
            for item in target_dir.rglob("*"):
                if item.is_file():
                    if any(part.startswith((".", "~")) for part in item.parts):
                        continue
                    if ServiceFileAuthenticator.is_service_name(item):
                        continue
                    if item.name.lower() in ("config.json", "knowledge_store.db"):
                        continue
                    files_found.append(item)
                    ext = item.suffix.lower() or "no_ext"
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1
                    try:
                        total_size += item.stat().st_size
                        if len(sample_texts) < 10 and item.suffix.lower() in text_exts and item.suffix.lower() in (".txt", ".md", ".csv", ".json"):
                            with item.open("r", encoding="utf-8", errors="ignore") as f:
                                sample_texts.append(f.read(1024))
                    except Exception:
                        pass
        except Exception as scan_err:
            logger.warning(f"[WorkspaceCreatorEngine] Ошибка сканирования директории {target_dir}: {scan_err}")

        # Приоритет определения языка:
        # 1) имя папки на иврите -> he,
        # 2) содержимое текстовых файлов (detect_language),
        # 3) имя папки / резервный язык из workspace_config.json
        combined_samples = "\n".join(sample_texts)
        if _RE_HEBREW_CHARS.search(target_dir.name):
            detected_lang = resolve_workspace_language("he")
        elif combined_samples.strip():
            raw_lang = detect_language(combined_samples)
            detected_lang = resolve_workspace_language(
                raw_lang if raw_lang != "unknown" else None,
                text_hints=(target_dir.name,),
            )
        else:
            detected_lang = resolve_workspace_language(None, text_hints=(target_dir.name,))

        folder_name = target_dir.name or "workspace"
        clean_id = re.sub(r"[^\w\-]+", "_", folder_name).strip("_") or "workspace"

        readme_loc = get_readme_locale(detected_lang)
        desc_tpl = readme_loc.get("desc_template", "")
        suggested_desc = (
            desc_tpl.format(folder_name=folder_name, total_files=len(files_found))
            if desc_tpl
            else readme_loc.get("desc_default", "")
        )

        return {
            "path": str(target_dir),
            "host_name": get_current_host_name(),
            "qualified_path": qual_p,
            "folder_name": folder_name,
            "total_files": len(files_found),
            "total_size_bytes": total_size,
            "extensions": ext_counts,
            "detected_language": detected_lang,
            "suggested_id": clean_id,
            "suggested_name": folder_name,
            "suggested_description": suggested_desc,
            "has_git": (target_dir / ".git").exists(),
            "sample_files": [f.name for f in files_found[:15]],
        }

    async def create_workspace_from_directory(
        self,
        directory_path: str | Path,
        workspace_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        language: Optional[str] = None,
        in_place: bool = True,
    ) -> Dict[str, Any]:
        """Создает полноценное рабочее пространство на основе указанной локальной директории.

        Args:
            directory_path: Путь к исходной локальной директории на диске.
            workspace_id: Идентификатор рабочего пространства (опционально, авто-генерация при None).
            name: Человекочитаемое имя (опционально, по имени папки при None).
            description: Описание рабочего пространства (опционально, авто-генерация при None).
            language: Основной язык рабочего пространства ('ru', 'he', 'en', 'ua').
            in_place: Если True — привязывает файлы на месте без копирования (copy_to_workspace=False).

        Returns:
            Словарь с метаданными созданного пространства, статистикой файлов и Git HEAD.
        """
        audit = self.audit_directory(directory_path)
        target_dir = Path(audit["path"])

        ws_id = (workspace_id or audit["suggested_id"]).strip()
        ws_name = (name or audit["suggested_name"]).strip()
        ws_lang = resolve_workspace_language(
            language or audit["detected_language"],
            text_hints=(ws_name, ws_id, target_dir.name),
        )

        readme_loc = get_readme_locale(ws_lang)
        if description and description.strip():
            ws_desc = description.strip()
        else:
            desc_tpl = readme_loc.get("desc_template", "")
            ws_desc = (
                desc_tpl.format(folder_name=audit["folder_name"], total_files=audit["total_files"])
                if desc_tpl
                else audit["suggested_description"]
            )

        # 1. Создание рабочей области через WorkspaceManager
        self.wm.create_or_select_workspace(
            workspace_id=ws_id,
            name=ws_name,
            description=ws_desc,
            language=ws_lang,
        )
        ws_path = self.wm.registry.workspace_path(ws_id)

        # 2. Адаптивный .gitignore на языке рабочего пространства
        gitignore_file = ws_path / ".gitignore"
        if not gitignore_file.exists():
            gitignore_file.write_text(build_workspace_gitignore(ws_lang), encoding="utf-8")

        # 3. Подключение файлов локальной директории
        files_linked = 0
        if target_dir.resolve() != ws_path.resolve():
            tracker = self.wm.items_tracker
            link_res = await tracker.add_disk_items(
                workspace_id=ws_id,
                paths=[str(target_dir)],
                copy_to_workspace=not in_place,
                commit_message=get_git_commit_msg("link_directory", lang=ws_lang, name=target_dir.name),
            )
            files_linked = link_res.get("files_added", 0)
        else:
            scan_res = self.wm.scan_and_index_workspace(ws_id)
            files_linked = scan_res.get("indexed_files", 0)

        # 4. Инициализация Obsidian Vault и базы знаний
        self.wm.obsidian.ensure_vault_config(ws_path)
        self.wm.obsidian.rebuild_knowledge_base_index(ws_id)

        # 5. Генерация обогащенного README.md с описанием подключенной папки
        readme_file = ws_path / "README.md"
        files_sample_str = ", ".join(audit["sample_files"][:8]) if audit["sample_files"] else "—"
        tracking_mode = readme_loc.get("mode_in_place", "") if in_place else readme_loc.get("mode_copy", "")
        readme_body = (
            f"lang={ws_lang}\n\n"
            f"# {ws_name}\n\n"
            f"## {readme_loc.get('desc_header', '')}\n"
            f"{ws_desc}\n\n"
            f"## {readme_loc.get('source_header', '')}\n"
            f"- **{readme_loc.get('path_label', '')}:** `{audit['qualified_path']}`\n"
            f"- **{readme_loc.get('host_label', '')}:** `{audit['host_name']}`\n"
            f"- **{readme_loc.get('files_count_label', '')}:** {audit['total_files']}\n"
            f"- **{readme_loc.get('sample_files_label', '')}:** {files_sample_str}\n"
            f"- **{readme_loc.get('tracking_mode_label', '')}:** {tracking_mode}\n"
        )
        readme_file.write_text(readme_body, encoding="utf-8")

        # 6. Построение векторного индекса FAISS и генерация стартовых подсказок (chips)
        try:
            self.wm.rebuild_faiss_index(ws_id)
        except Exception as faiss_err:
            logger.debug(f"[WorkspaceCreatorEngine] FAISS ребилд: {faiss_err}")

        prompt_gen = WorkspacePromptGenerator(self.wm)
        starter_prompts = await prompt_gen.generate_prompts(workspace_id=ws_id, language=ws_lang, limit=4)

        logger.info(f"[WorkspaceCreatorEngine] Успешно создано рабочее пространство '{ws_id}' (lang={ws_lang}) на основе '{target_dir}'")

        return {
            "status": "ok",
            "workspace_id": ws_id,
            "name": ws_name,
            "description": ws_desc,
            "language": ws_lang,
            "path": str(ws_path),
            "source_directory": str(target_dir),
            "source_qualified_path": audit["qualified_path"],
            "files_linked": files_linked,
            "audit": audit,
            "starter_prompts": starter_prompts,
        }
