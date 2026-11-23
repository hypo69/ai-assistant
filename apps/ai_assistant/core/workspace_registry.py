# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Workspace Registry
# =============================================================================
# Description:
#   Файловый реестр рабочих пространств без базы данных.
#   Рабочее пространство — подпапка каталога workspaces/, содержащая .git.
#   Настройки пространства (имя, описание, дата создания, привязанные источники)
#   хранятся в служебном файле <ws>/.workspace/config.json, который создаётся
#   автоматически при первом сканировании и исключается из Git через
#   .git/info/exclude.
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.workspace_registry import WorkspaceRegistry
#
#     registry = WorkspaceRegistry(Path("apps/ai_assistant/data/workspaces"))
#     for ws in registry.list_workspaces():
#         print(ws["workspace_id"], ws["name"])
#
# File: workspace_registry.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 17:25:00
# =============================================================================

from __future__ import annotations
"""Файловый реестр рабочих пространств на основе сканирования каталога workspaces/."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import stat
import threading
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple
import uuid

from logger import logger
from src.utils.jjson import j_loads, j_loads_ns
from apps.ai_assistant.core.nlp_analyzers import detect_language

WORKSPACE_META_DIR = ".workspace"
WORKSPACE_CONFIG_FILE = "config.json"

_APP_DIR = Path(__file__).resolve().parent.parent
_APP_CONFIG_PATH = _APP_DIR / "config.json"
_WS_CONFIG_DEFAULT_PATH = Path(__file__).resolve().with_name("workspace_config.json")

_HOST_PREFIX_RE = re.compile(r"^(?:\\\\|//)([^\\/]+)[\\/]([A-Za-z]:[\\/].*)$")
_HOST_COLON_RE = re.compile(r"^([A-Za-z0-9_.\-]+)::(.+)$")


def load_workspace_config() -> SimpleNamespace:
    """Загружает конфигурацию рабочих пространств через j_loads_ns без хардкода.

    Returns:
        SimpleNamespace: Объект конфигурации из workspace_config.json.
    """
    app_cfg = j_loads_ns(_APP_CONFIG_PATH)
    ws_section = getattr(app_cfg, "workspace", None)
    rel_path = getattr(ws_section, "config_file", None) if isinstance(ws_section, SimpleNamespace) else None
    cfg_path = (_APP_DIR / rel_path) if rel_path else _WS_CONFIG_DEFAULT_PATH
    cfg = j_loads_ns(cfg_path)
    if not vars(cfg):
        return SimpleNamespace()
    return cfg


def _ns_dict(ns: Any) -> Dict[str, Any]:
    """Преобразует SimpleNamespace в словарь."""
    if isinstance(ns, SimpleNamespace):
        return dict(vars(ns))
    if isinstance(ns, dict):
        return dict(ns)
    return {}


def get_system_data_dirs() -> set[str]:
    """Возвращает множество системных каталогов, исключаемых из списка пространств."""
    cfg = load_workspace_config()
    raw = getattr(cfg, "system_data_dirs", None)
    return {str(x).lower() for x in raw} if isinstance(raw, (list, tuple, set)) else set()


SYSTEM_DATA_DIRS = get_system_data_dirs()


def get_default_workspace_language() -> str:
    """Возвращает резервный язык рабочего пространства из конфигурации (config.json / workspace_config.json)."""
    app_cfg = j_loads_ns(_APP_CONFIG_PATH)
    ws_section = getattr(app_cfg, "workspace", None)
    app_default = getattr(ws_section, "default_language", None) if isinstance(ws_section, SimpleNamespace) else None
    if app_default:
        return str(app_default).strip().lower()
    cfg = load_workspace_config()
    return str(getattr(cfg, "default_language", "") or "").strip().lower()


def normalize_workspace_language(language: Optional[str] = None) -> str:
    """Нормализует код языка рабочего пространства по таблице алиасов из workspace_config.json."""
    cfg = load_workspace_config()
    aliases = {str(k).lower(): str(v).lower() for k, v in _ns_dict(getattr(cfg, "language_aliases", None)).items()}
    default_lang = get_default_workspace_language()

    raw = (language or "").strip().lower().replace("_", "-").split("-")[0]
    if not raw or raw == "unknown":
        return default_lang
    return aliases.get(raw, raw)


def resolve_workspace_language(
    language: Optional[str] = None,
    text_hints: Sequence[str] = (),
) -> str:
    """Определяет язык рабочего пространства: 1) явный параметр, 2) скрипт/текст подсказок, 3) конфиг.

    Args:
        language: Явно переданный код языка (если задан и валиден).
        text_hints: Текстовые подсказки (имя, workspace_id, описание, фрагменты файлов).

    Returns:
        str: Нормализованный код языка.
    """
    raw = (language or "").strip().lower()
    if raw and raw != "unknown":
        return normalize_workspace_language(raw)

    for hint in text_hints:
        text = str(hint or "").strip()
        if not text:
            continue
        detected = detect_language(text)
        if detected and detected != "unknown":
            return normalize_workspace_language(detected)

    return get_default_workspace_language()


def get_readme_locale(language: Optional[str] = None) -> Dict[str, str]:
    """Возвращает словарь локализации README.md для заданного языка из workspace_config.json."""
    cfg = load_workspace_config()
    locales_ns = getattr(cfg, "readme_locales", None)
    locales = _ns_dict(locales_ns)
    norm_lang = normalize_workspace_language(language)
    default_lang = get_default_workspace_language()
    chosen = locales.get(norm_lang) or locales.get(default_lang) or next(iter(locales.values()), SimpleNamespace())
    return {str(k): str(v) for k, v in _ns_dict(chosen).items()}


def get_default_descriptions() -> Dict[str, str]:
    """Возвращает карту стандартных описаний рабочих пространств по языкам из workspace_config.json."""
    cfg = load_workspace_config()
    locales = _ns_dict(getattr(cfg, "readme_locales", None))
    result: Dict[str, str] = {}
    for lang, loc_ns in locales.items():
        loc = _ns_dict(loc_ns)
        if loc.get("desc_default"):
            result[str(lang)] = str(loc["desc_default"])
    return result


def build_workspace_gitignore(language: Optional[str] = None) -> str:
    """Формирует содержимое .gitignore рабочего пространства с комментариями на языке пространства."""
    cfg = load_workspace_config()
    norm_lang = normalize_workspace_language(language)
    default_lang = get_default_workspace_language()
    rules = _ns_dict(getattr(cfg, "gitignore_rules", None))
    comments_map = _ns_dict(getattr(cfg, "gitignore_comments", None))
    comments = _ns_dict(comments_map.get(norm_lang) or comments_map.get(default_lang))

    lines: List[str] = []
    if comments.get("header"):
        lines.append(str(comments["header"]))

    for section in ("temp_and_cache", "infrastructure", "assets", "binary_media", "exceptions"):
        section_rules = rules.get(section)
        if not section_rules:
            continue
        if comments.get(section):
            lines.append(str(comments[section]))
        lines.extend(str(item) for item in section_rules)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_workspace_readme(
    name: str,
    description: str = "",
    language: Optional[str] = None,
) -> str:
    """Формирует содержимое файла README.md с языковой меткой lang=<lang> и главами Название и Описание.

    Args:
        name: Название рабочего пространства.
        description: Описание рабочего пространства.
        language: Язык рабочего пространства (en, ru, he, ua); при None определяется автоматически.

    Returns:
        str: Текст файла README.md в формате Markdown.
    """
    lang = resolve_workspace_language(language, text_hints=(name, description))
    loc = get_readme_locale(lang)
    ws_title = (name or "").strip() or loc.get("title_default", "")
    ws_desc = (description or "").strip() or loc.get("desc_default", "")

    return (
        f"lang={lang}\n\n"
        f"# {ws_title}\n\n"
        f"## {loc.get('desc_header', '')}\n"
        f"{ws_desc}\n"
    )


def parse_workspace_readme(readme_path: Path) -> Dict[str, str]:
    """Извлекает язык, название и описание из файла README.md рабочего пространства.

    Args:
        readme_path: Путь к файлу README.md.

    Returns:
        Dict[str, str]: Словарь с ключами 'language', 'name', 'description'.
    """
    result = {"language": "", "name": "", "description": ""}
    if not readme_path.is_file():
        return result
    try:
        content = readme_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines()]
        # Первая строка: lang=... или <!-- lang=... -->
        for line in lines:
            lang_match = re.match(r"^(?:<!--\s*)?lang\s*=\s*([A-Za-z\-_]+)(?:\s*-->)?$", line, re.IGNORECASE)
            if lang_match:
                result["language"] = normalize_workspace_language(lang_match.group(1).strip())
                break
        # Заголовок первого уровня '# ...'
        for line in lines:
            if line.startswith("# "):
                result["name"] = line[2:].strip()
                break
        # Секция '## ...'
        desc_lines: List[str] = []
        capturing = False
        for line in lines:
            if line.startswith("## "):
                capturing = True
                continue
            elif capturing and (line.startswith("#") or line.startswith("<!--") or line.startswith("---")):
                break
            elif capturing and line:
                desc_lines.append(line)
        if desc_lines:
            result["description"] = "\n".join(desc_lines).strip()
    except Exception as exc:
        logger.warning(f"[WorkspaceRegistry] Ошибка чтения {readme_path}: {exc}")
    return result


def get_current_host_name() -> str:
    """Возвращает нормализованное имя текущего компьютера для носимого (USB) режима."""
    raw = os.environ.get("COMPUTERNAME") or platform.node() or socket.gethostname() or "LOCALHOST"
    return raw.strip().upper()


def parse_host_qualified_path(raw_target: str, default_host: Optional[str] = None) -> Tuple[str, str, str]:
    """Разбирает путь и возвращает кортеж (host_name, local_path, qualified_path с именем ПК)."""
    s = str(raw_target or "").strip()
    host = (default_host or get_current_host_name()).strip().upper()
    if not s or s.lower().startswith(("http://", "https://")):
        return host, s, s

    m_unc = _HOST_PREFIX_RE.match(s)
    if m_unc:
        parsed_host = m_unc.group(1).strip().upper()
        local_p = m_unc.group(2).strip()
        return parsed_host, local_p, f"\\\\{parsed_host}\\{local_p}"

    m_col = _HOST_COLON_RE.match(s)
    if m_col:
        parsed_host = m_col.group(1).strip().upper()
        local_p = m_col.group(2).strip()
        return parsed_host, local_p, f"\\\\{parsed_host}\\{local_p}"

    return host, s, f"\\\\{host}\\{s}"


def format_host_qualified_path(local_path: str | Path, host_name: Optional[str] = None) -> str:
    """Формирует полный путь файла или папки, включая имя компьютера (\\\\<HOST>\\<PATH>)."""
    return parse_host_qualified_path(str(local_path), default_host=host_name)[2]



def _utc_now_iso() -> str:
    """Возвращает текущее время UTC в формате ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def resolve_workspaces_dir(custom_path: Optional[Path | str] = None) -> Path:
    """Определяет каталог рабочих пространств из config.json или явно переданного пути.

    Корректно обрабатывает относительные пути репозитория со слэшами вида '/data/workspaces'
    или '\\data\\workspaces', разрешая их строго относительно корня проекта (__root__),
    а не относительно корня системного диска (C:\\data\\workspaces).

    Args:
        custom_path: Явно переданный каталог рабочих пространств (опционально).

    Returns:
        Path: Абсолютный путь к каталогу workspaces.
    """
    from header import __root__

    raw_str = ""
    if custom_path is not None:
        raw_str = str(custom_path).strip()
    else:
        # 1. Проверяем переменные окружения
        env_ws = os.environ.get("AI_ASSISTANT_WORKSPACES_DIR") or os.environ.get("WORKSPACES_DIR")
        if env_ws:
            raw_str = env_ws.strip()

        # 2. Проверяем config.json приложения apps/ai_assistant/config.json
        app_cfg_file = _APP_CONFIG_PATH
        if not raw_str and app_cfg_file.exists():
            cfg = j_loads_ns(app_cfg_file)
            storage_cfg = getattr(cfg, "storage", None)
            if isinstance(storage_cfg, SimpleNamespace):
                raw_str = getattr(storage_cfg, "workspaces_dir", None) or getattr(storage_cfg, "workspaces", None) or ""
            elif isinstance(storage_cfg, str):
                raw_str = storage_cfg
            if not raw_str:
                git_cfg = getattr(cfg, "git", None)
                raw_str = getattr(cfg, "workspaces_dir", None) or (getattr(git_cfg, "workspaces_dir", None) if isinstance(git_cfg, SimpleNamespace) else None) or ""
            if not raw_str and isinstance(getattr(cfg, "workspaces", None), str):
                raw_str = cfg.workspaces

        # 3. Проверяем корневой config.json проекта
        root_cfg_file = __root__ / "config.json"
        if not raw_str and root_cfg_file.exists():
            root_cfg = j_loads_ns(root_cfg_file)
            storage_cfg = getattr(root_cfg, "storage", None)
            if isinstance(storage_cfg, SimpleNamespace):
                raw_str = getattr(storage_cfg, "workspaces_dir", None) or getattr(storage_cfg, "workspaces", None) or ""
            elif isinstance(storage_cfg, str):
                raw_str = storage_cfg
            if not raw_str:
                raw_str = getattr(root_cfg, "workspaces_dir", None) or ""
            if not raw_str and isinstance(getattr(root_cfg, "workspaces", None), str):
                raw_str = root_cfg.workspaces

    raw_str = (raw_str or "data/workspaces").strip()

    # Проверка на реальный абсолютный Windows диск (например, C:\ или C:/)
    is_windows_drive = bool(re.match(r"^[a-zA-Z]:[\\/]", raw_str))
    # UNC-путь: начинается с двух слэшей \\server\\share или //server/share
    is_unc = (raw_str.startswith(r"\\") or raw_str.startswith("//")) and not raw_str.startswith(r"\\?")

    if is_windows_drive or is_unc:
        ws_path = Path(raw_str).resolve()
        ws_path.mkdir(parents=True, exist_ok=True)
        return ws_path

    # Очищаем ведущие слэши для путей репозитория (/data/workspaces, \data\workspaces)
    clean = raw_str.replace("\\", "/").strip().lstrip("/")
    if clean.rstrip("/") in ("data", ""):
        clean = "data/workspaces"

    root_ws = (__root__ / clean).resolve()
    root_ws.mkdir(parents=True, exist_ok=True)
    return root_ws


def _read_git_head(ws_path: Path) -> str:
    """Читает хеш HEAD напрямую из каталога .git без вызова git.

    Returns:
        str: Полный хеш коммита или пустая строка, если коммитов ещё нет.
    """
    git_dir = ws_path / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head
        ref = head[4:].strip()
        ref_file = git_dir / ref
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8").strip()
        packed = git_dir / "packed-refs"
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(f" {ref}"):
                    return line.split(" ", 1)[0]
    except Exception:
        pass
    return ""


class WorkspaceRegistry:
    """Реестр рабочих пространств: сканирует каталог и управляет файлами .workspace/config.json."""

    def __init__(self, workspaces_dir: Path | str) -> None:
        """Инициализирует реестр с явно переданным каталогом рабочих пространств.

        Args:
            workspaces_dir: Каталог, подпапки которого являются рабочими пространствами.
        """
        self._lock = threading.RLock()
        self.workspaces_dir = resolve_workspaces_dir(workspaces_dir)
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_workspaces_from_legacy_data()

    def _migrate_workspaces_from_legacy_data(self) -> None:
        """Автоматически переносит рабочие пространства из корневого каталога data/ и app/data/ в data/workspaces/."""
        parent_dir = self.workspaces_dir.parent
        if parent_dir.exists() and parent_dir != self.workspaces_dir and parent_dir.name.lower() == "data":
            try:
                for item in list(parent_dir.iterdir()):
                    if not item.is_dir() or item.name.startswith((".", "~")):
                        continue
                    if item.name.lower() in SYSTEM_DATA_DIRS:
                        continue
                    if (item / ".git").exists() or (item / WORKSPACE_META_DIR).exists():
                        target_path = self.workspaces_dir / item.name
                        if not target_path.exists():
                            logger.info(f"[WorkspaceRegistry] Миграция рабочего пространства '{item.name}' из {item} в {target_path}")
                            shutil.move(str(item), str(target_path))
                        else:
                            logger.debug(f"[WorkspaceRegistry] Рабочее пространство '{item.name}' уже существует в {target_path}")
                        target_assets = (self.workspaces_dir / item.name) / "assets"
                        target_assets.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.warning(f"[WorkspaceRegistry] Ошибка автоматической миграции workspaces из data/: {exc}")

        # Миграция из каталога app/data/workspaces при его наличии
        try:
            from header import __root__
            legacy_app_dir = __root__ / "app" / "data" / "workspaces"
            if legacy_app_dir.exists() and legacy_app_dir.resolve() != self.workspaces_dir.resolve():
                for item in list(legacy_app_dir.iterdir()):
                    if not item.is_dir() or item.name.startswith((".", "~")):
                        continue
                    target_path = self.workspaces_dir / item.name
                    if not target_path.exists():
                        logger.info(f"[WorkspaceRegistry] Миграция рабочего пространства '{item.name}' из {item} в {target_path}")
                        shutil.move(str(item), str(target_path))
                    else:
                        logger.debug(f"[WorkspaceRegistry] Рабочее пространство '{item.name}' уже существует в {target_path}")
                    (self.workspaces_dir / item.name / "assets").mkdir(parents=True, exist_ok=True)
                shutil.rmtree(str(__root__ / "app"), ignore_errors=True)
        except Exception as exc:
            logger.warning(f"[WorkspaceRegistry] Ошибка автоматической миграции workspaces из app/data: {exc}")

    # ------------------------------------------------------------------
    # Служебные операции с config.json
    # ------------------------------------------------------------------

    def workspace_path(self, workspace_id: str) -> Path:
        """Возвращает путь к папке рабочего пространства (папка может не существовать)."""
        return self.workspaces_dir / workspace_id

    def _config_file(self, ws_path: Path) -> Path:
        """Возвращает путь к служебному файлу настроек пространства."""
        return ws_path / WORKSPACE_META_DIR / WORKSPACE_CONFIG_FILE

    def _exclude_meta_from_git(self, ws_path: Path) -> None:
        """Добавляет служебные каталоги (.workspace/, .obsidian/, faiss_indices/, *.faiss, *.db) в локальный .git/info/exclude."""
        exclude_file = ws_path / ".git" / "info" / "exclude"
        lines_to_exclude = [f"{WORKSPACE_META_DIR}/", "assets/", ".obsidian/", "faiss_indices/", "*.faiss", "*.db", "*.db-wal", "*.db-shm"]
        try:
            exclude_file.parent.mkdir(parents=True, exist_ok=True)
            current = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
            existing = set(current.splitlines())
            added = [ln for ln in lines_to_exclude if ln not in existing]
            if added:
                exclude_file.write_text(
                    current.rstrip("\n") + ("\n" if current else "") + "\n".join(added) + "\n",
                    encoding="utf-8",
                )
        except Exception as exc:
            logger.warning(f"[WorkspaceRegistry] Не удалось исключить служебные каталоги из Git в {ws_path}: {exc}")

    def _write_config(self, ws_path: Path, cfg: Dict[str, Any]) -> None:
        """Атомарно и потокобезопасно сохраняет настройки пространства в .workspace/config.json."""
        with self._lock:
            cfg_file = self._config_file(ws_path)
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = cfg_file.with_suffix(".json.tmp")
            content_str = json.dumps(cfg, indent=2, ensure_ascii=False)
            tmp_file.write_text(content_str, encoding="utf-8")
            try:
                os.replace(tmp_file, cfg_file)
            except OSError:
                import time
                time.sleep(0.05)
                try:
                    os.replace(tmp_file, cfg_file)
                except OSError:
                    cfg_file.write_text(content_str, encoding="utf-8")
                    tmp_file.unlink(missing_ok=True)
            self._exclude_meta_from_git(ws_path)

    def _load_config(self, ws_path: Path, default_language: Optional[str] = None) -> Dict[str, Any]:
        """Читает настройки пространства через j_loads; при отсутствии файла создаёт его с автоопределением языка."""
        cfg_file = self._config_file(ws_path)
        if cfg_file.exists():
            cfg = j_loads(cfg_file, ordered=False)
            if isinstance(cfg, dict) and cfg:
                cfg.setdefault("sources", [])
                if not cfg.get("language"):
                    cfg["language"] = resolve_workspace_language(
                        default_language,
                        text_hints=(cfg.get("name", ""), ws_path.name, cfg.get("description", "")),
                    )
                return cfg
        resolved_lang = resolve_workspace_language(default_language, text_hints=(ws_path.name,))
        cfg = {
            "name": ws_path.name,
            "description": "",
            "language": resolved_lang,
            "created_at": _utc_now_iso(),
            "sources": [],
        }
        self._write_config(ws_path, cfg)
        return cfg

    def _describe(self, ws_path: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Формирует публичное описание рабочего пространства."""
        ws_name = cfg.get("name") or ws_path.name
        ws_desc = cfg.get("description", "")
        ws_lang = resolve_workspace_language(cfg.get("language"), text_hints=(ws_name, ws_path.name, ws_desc))
        return {
            "workspace_id": ws_path.name,
            "name": ws_name,
            "description": ws_desc,
            "language": ws_lang,
            "created_at": cfg.get("created_at", ""),
            "path": str(ws_path),
            "git_head": _read_git_head(ws_path),
        }

    def _is_workspace_dir(self, p: Path) -> bool:
        """Признак рабочего пространства: подпапка с .git или .workspace, имя не начинается с '.' или '~' и не является системным каталогом."""
        return (
            p.is_dir()
            and not p.name.startswith((".", "~"))
            and p.name.lower() not in SYSTEM_DATA_DIRS
            and ((p / ".git").exists() or (p / WORKSPACE_META_DIR).exists())
        )

    # ------------------------------------------------------------------
    # Рабочие пространства
    # ------------------------------------------------------------------

    def ensure_workspace_readme(
        self,
        ws_path: Path,
        name: str = "",
        description: str = "",
        language: Optional[str] = None,
    ) -> Path:
        """Создаёт файл README.md в каталоге рабочего пространства, если он отсутствует.

        Args:
            ws_path: Путь к каталогу рабочего пространства.
            name: Название рабочего пространства.
            description: Описание рабочего пространства.
            language: Код языка рабочего пространства.

        Returns:
            Path: Путь к созданному файлу README.md.
        """
        readme_path = ws_path / "README.md"
        if not readme_path.exists():
            cfg = self._load_config(ws_path, default_language=language)
            eff_name = name or cfg.get("name") or ws_path.name
            eff_desc = description or cfg.get("description", "")
            eff_lang = resolve_workspace_language(
                language or cfg.get("language"),
                text_hints=(eff_name, ws_path.name, eff_desc),
            )
            content = generate_workspace_readme(eff_name, eff_desc, eff_lang)
            readme_path.write_text(content, encoding="utf-8")
            logger.info(f"[WorkspaceRegistry] Создан файл README.md для '{ws_path.name}' (lang={eff_lang})")
        return readme_path

    def list_workspaces(self) -> List[Dict[str, Any]]:
        """Возвращает список рабочих пространств быстрым чтением содержимого каталога data/workspaces.

        Returns:
            List[Dict[str, Any]]: Отсортированный по workspace_id список описаний.
        """
        workspaces = []
        if not self.workspaces_dir.exists():
            return []
        for p in sorted(self.workspaces_dir.iterdir(), key=lambda x: x.name.lower()):
            if not self._is_workspace_dir(p):
                continue
            readme_file = p / "README.md"
            meta = parse_workspace_readme(readme_file) if readme_file.exists() else {}
            cfg_data = self._load_config(p, default_language=meta.get("language"))

            ws_name = meta.get("name") or cfg_data.get("name") or p.name
            ws_desc = meta.get("description") or cfg_data.get("description") or ""
            ws_lang = resolve_workspace_language(
                meta.get("language") or cfg_data.get("language"),
                text_hints=(ws_name, p.name, ws_desc),
            )

            workspaces.append({
                "workspace_id": p.name,
                "name": ws_name,
                "description": ws_desc,
                "language": ws_lang,
                "created_at": cfg_data.get("created_at", ""),
                "path": str(p),
                "git_head": _read_git_head(p),
                "has_git": True,
            })
        return workspaces

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает описание рабочего пространства или None, если папки с .git нет."""
        if not workspace_id:
            return None
        ws_path = self.workspace_path(workspace_id)
        if not self._is_workspace_dir(ws_path):
            return None
        readme_file = ws_path / "README.md"
        meta = parse_workspace_readme(readme_file) if readme_file.exists() else {}
        cfg = self._load_config(ws_path, default_language=meta.get("language"))
        ws_name = meta.get("name") or cfg.get("name") or ws_path.name
        ws_desc = meta.get("description") or cfg.get("description", "")
        ws_lang = resolve_workspace_language(
            meta.get("language") or cfg.get("language"),
            text_hints=(ws_name, ws_path.name, ws_desc),
        )
        return {
            "workspace_id": ws_path.name,
            "name": ws_name,
            "description": ws_desc,
            "language": ws_lang,
            "created_at": cfg.get("created_at", ""),
            "path": str(ws_path),
            "git_head": _read_git_head(ws_path),
            "has_git": True,
        }

    def save_workspace(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Записывает имя, описание и язык в config.json и README.md существующей папки пространства.

        Args:
            workspace_id: Идентификатор (имя папки) рабочего пространства.
            name: Отображаемое имя.
            description: Описание (пустая строка сохраняет прежнее значение).
            language: Основной язык рабочего пространства ('he', 'ru', 'en', 'ua'); при None сохраняется текущий или автоопределяется.

        Returns:
            Dict[str, Any]: Обновлённое описание пространства.
        """
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            raise FileNotFoundError(f"Папка рабочего пространства не найдена: {ws_path}")
        (ws_path / "assets").mkdir(parents=True, exist_ok=True)
        norm_lang = normalize_workspace_language(language) if language else None
        cfg = self._load_config(ws_path, default_language=norm_lang)
        eff_name = name or cfg.get("name") or workspace_id
        cfg["name"] = eff_name
        if description:
            cfg["description"] = description

        readme_file = ws_path / "README.md"
        parsed = parse_workspace_readme(readme_file) if readme_file.exists() else {}
        eff_lang = resolve_workspace_language(
            norm_lang or parsed.get("language") or cfg.get("language"),
            text_hints=(eff_name, workspace_id, description or cfg.get("description", "")),
        )
        cfg["language"] = eff_lang
        self._write_config(ws_path, cfg)

        # Синхронизация README.md
        default_descs = get_default_descriptions()
        if readme_file.exists():
            eff_name = name or parsed.get("name") or cfg.get("name") or workspace_id
            raw_desc = (description or parsed.get("description") or cfg.get("description", "")).strip()
            # Если описание пустое или совпадает с дефолтным описанием на любом другом языке, переводим на новый язык
            if not raw_desc or raw_desc in default_descs.values():
                eff_desc = default_descs.get(eff_lang) or get_readme_locale(eff_lang).get("desc_default", "")
            else:
                eff_desc = raw_desc
            readme_file.write_text(generate_workspace_readme(eff_name, eff_desc, eff_lang), encoding="utf-8")
        else:
            self.ensure_workspace_readme(ws_path, name=eff_name, description=description, language=eff_lang)

        return self.get_workspace(workspace_id) or self._describe(ws_path, cfg)

    def delete_workspace(self, workspace_id: str) -> bool:
        """Удаляет рабочее пространство и его директорию с диска.

        Args:
            workspace_id: Идентификатор рабочего пространства.

        Returns:
            bool: True в случае успешного удаления.

        Raises:
            ValueError: При попытке path traversal или недопустимом имени.
            FileNotFoundError: Если директория пространства не найдена.
        """
        if not workspace_id or str(workspace_id).strip().startswith((".", "~")):
            raise ValueError(f"Недопустимый идентификатор рабочего пространства: {workspace_id}")

        clean_id = str(workspace_id).strip()
        if clean_id.lower() in SYSTEM_DATA_DIRS:
            raise ValueError(f"Запрещено удалять системный каталог: {clean_id}")
        ws_path = (self.workspaces_dir / clean_id).resolve()
        resolved_root = self.workspaces_dir.resolve()

        try:
            ws_path.relative_to(resolved_root)
        except ValueError:
            raise ValueError(f"Попытка выхода за пределы каталога рабочих пространств: {workspace_id}")
        if ws_path == resolved_root:
            raise ValueError(f"Попытка выхода за пределы каталога рабочих пространств: {workspace_id}")

        if not ws_path.exists() or not ws_path.is_dir():
            raise FileNotFoundError(f"Папка рабочего пространства не найдена: {ws_path}")

        def _handle_remove_readonly(func: Any, path: str, exc: Any) -> None:
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception as err:
                logger.warning(f"[WorkspaceRegistry] Не удалось удалить файл/папку {path}: {err}")

        shutil.rmtree(ws_path, onerror=_handle_remove_readonly)
        logger.info(f"[WorkspaceRegistry] Рабочее пространство '{clean_id}' успешно удалено с диска: {ws_path}")
        return True

    # ------------------------------------------------------------------
    # Привязанные источники
    # ------------------------------------------------------------------

    def list_sources(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Возвращает привязанные источники пространства с информацией об имени компьютера (новые первыми)."""
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            return []
        cur_host = get_current_host_name()
        sources = self._load_config(ws_path).get("sources", [])
        enriched: List[Dict[str, Any]] = []
        for s in sources:
            item = dict(s)
            raw_path = str(item.get("source_path", ""))
            s_host, local_p, qual_p = parse_host_qualified_path(raw_path, default_host=item.get("host_name"))
            item["host_name"] = s_host
            item["source_path"] = local_p
            item["qualified_path"] = item.get("qualified_path") or qual_p
            item["is_current_host"] = (s_host.upper() == cur_host.upper())
            enriched.append(item)
        return sorted(enriched, key=lambda s: s.get("created_at", ""), reverse=True)

    def add_source(
        self,
        workspace_id: str,
        source_type: str,
        source_path: str,
        name: str,
        auto_watch: bool = True,
        host_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Добавляет внешний источник (файл, папку или Google Таблицу) с привязкой к имени компьютера в config.json.

        Returns:
            Dict[str, Any]: Запись созданного источника с полями host_name и qualified_path.
        """
        ws_path = self.workspace_path(workspace_id)
        cfg = self._load_config(ws_path)
        now = _utc_now_iso()
        resolved_host, clean_local_path, qualified_path = parse_host_qualified_path(source_path, default_host=host_name)
        source = {
            "source_id": f"src_{uuid.uuid4().hex[:12]}",
            "workspace_id": workspace_id,
            "source_type": source_type,
            "host_name": resolved_host,
            "source_path": clean_local_path,
            "qualified_path": qualified_path,
            "is_current_host": (resolved_host.upper() == get_current_host_name().upper()),
            "name": name,
            "auto_watch": bool(auto_watch),
            "last_scanned_at": "",
            "item_count": 0,
            "status": "linked",
            "error_message": "",
            "created_at": now,
            "updated_at": now,
        }
        cfg["sources"].append(source)
        self._write_config(ws_path, cfg)
        return source

    def delete_source(self, workspace_id: str, source_id: str) -> bool:
        """Удаляет источник из config.json пространства.

        Returns:
            bool: True, если источник найден и удалён.
        """
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            return False
        cfg = self._load_config(ws_path)
        before = len(cfg["sources"])
        cfg["sources"] = [s for s in cfg["sources"] if s.get("source_id") != source_id]
        if len(cfg["sources"]) == before:
            return False
        self._write_config(ws_path, cfg)
        return True

    def update_source_status(
        self,
        workspace_id: str,
        source_id: str,
        status: str = "active",
        item_count: int = 0,
        error_message: str = "",
    ) -> bool:
        """Обновляет статус и результат последнего сканирования источника.

        Returns:
            bool: True, если источник найден и обновлён.
        """
        ws_path = self.workspace_path(workspace_id)
        if not ws_path.is_dir():
            return False
        cfg = self._load_config(ws_path)
        now = _utc_now_iso()
        for src in cfg["sources"]:
            if src.get("source_id") == source_id:
                src.update(
                    status=status,
                    item_count=item_count,
                    error_message=error_message,
                    last_scanned_at=now,
                    updated_at=now,
                )
                self._write_config(ws_path, cfg)
                return True
        return False
