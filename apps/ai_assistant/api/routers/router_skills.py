# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Skills Management Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор для управления автономными навыками (.agents/skills).
#   Обеспечивает получение метаданных навыков, чтение и сохранение конфигураций
#   секретов (secrets.json) и тестирование подключений (например, SMTP).
#
# Usage Examples:
#   GET  /api/v1/skills
#   GET  /api/v1/skills/{skill_name}/config
#   POST /api/v1/skills/{skill_name}/config
#   POST /api/v1/skills/{skill_name}/test-connection
#
# File: router_skills.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 20:30:00
# =============================================================================

from __future__ import annotations

"""REST API маршрутизатор управления навыками (.agents/skills) и их конфигурациями."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])

_SKILLS_DIR = (__root__ / ".agents" / "skills").resolve()


def _parse_frontmatter(content: str) -> Dict[str, Any]:
    """Парсит YAML-frontmatter из начала markdown файла."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter_raw = parts[1]
    res: Dict[str, Any] = {}
    current_key: Optional[str] = None
    for line in frontmatter_raw.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue
        if ":" in line_str and not line.startswith(" ") and not line.startswith("\t"):
            k, v = line_str.split(":", 1)
            current_key = k.strip()
            val = v.strip().strip('"').strip("'")
            res[current_key] = val
        elif current_key and (line.startswith("  ") or line.startswith("\t")):
            # Вложенные поля (например, description_i18n)
            if not isinstance(res.get(current_key), dict):
                res[current_key] = {}
            if ":" in line_str:
                sub_k, sub_v = line_str.split(":", 1)
                res[current_key][sub_k.strip()] = sub_v.strip().strip('"').strip("'")
    return res


def _get_skill_dir(skill_name: str) -> Path:
    """Безопасно разрешает путь к каталогу навыка, предотвращая Path Traversal."""
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "", skill_name)
    skill_path = (_SKILLS_DIR / clean_name).resolve()
    try:
        skill_path.relative_to(_SKILLS_DIR)
    except ValueError:
        raise HTTPException(status_code=400, detail="Недопустимое имя навыка")
    if not skill_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Навык '{clean_name}' не найден")
    return skill_path


class SkillConfigPayload(BaseModel):
    """Схема полезной нагрузки для обновления конфигурации навыка."""
    config: Dict[str, Any] = Field(..., description="Словарь параметров конфигурации")


@router.get("", summary="Получить список всех навыков")
async def list_skills() -> List[Dict[str, Any]]:
    """Возвращает метаданные всех обнаруженных навыков в каталоге .agents/skills."""
    skills: List[Dict[str, Any]] = []
    if not _SKILLS_DIR.is_dir():
        return skills

    for skill_path in sorted(_SKILLS_DIR.iterdir()):
        if not skill_path.is_dir() or skill_path.name.startswith((".", "~")):
            continue

        skill_md = skill_path / "SKILL.md"
        meta: Dict[str, Any] = {}
        if skill_md.is_file():
            try:
                content = skill_md.read_text(encoding="utf-8")
                meta = _parse_frontmatter(content)
            except Exception as exc:
                logger.warning(f"[router_skills] Ошибка парсинга {skill_md}: {exc}")

        has_secrets = (skill_path / "secrets.json").is_file()
        has_example = (skill_path / "secrets.json.example").is_file()
        has_scripts = (skill_path / "scripts").is_dir()

        desc = meta.get("description", "")
        if isinstance(meta.get("description_i18n"), dict):
            desc = meta["description_i18n"].get("ru") or meta.get("description", "")

        skills.append({
            "id": skill_path.name,
            "name": meta.get("name", skill_path.name),
            "description": desc,
            "has_config": has_secrets or has_example,
            "is_configured": has_secrets,
            "has_scripts": has_scripts,
            "path": str(skill_path.relative_to(__root__)).replace("\\", "/"),
        })

    return skills


@router.get("/{skill_name}/config", summary="Получить конфигурацию навыка")
async def get_skill_config(skill_name: str) -> Dict[str, Any]:
    """Возвращает текущую конфигурацию (или шаблон из secrets.json.example)."""
    skill_dir = _get_skill_dir(skill_name)
    secrets_file = skill_dir / "secrets.json"
    example_file = skill_dir / "secrets.json.example"

    config: Dict[str, Any] = {}
    is_template = False

    if secrets_file.is_file():
        try:
            config = json.loads(secrets_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(f"[router_skills] Ошибка чтения {secrets_file}: {exc}")
            raise HTTPException(status_code=500, detail=f"Ошибка чтения secrets.json: {exc}")
    elif example_file.is_file():
        try:
            config = json.loads(example_file.read_text(encoding="utf-8"))
            is_template = True
        except Exception as exc:
            logger.error(f"[router_skills] Ошибка чтения {example_file}: {exc}")
            raise HTTPException(status_code=500, detail=f"Ошибка чтения secrets.json.example: {exc}")
    else:
        raise HTTPException(status_code=404, detail="Файл конфигурации не найден для данного навыка")

    return {
        "skill": skill_name,
        "is_template": is_template,
        "config": config,
    }


@router.post("/{skill_name}/config", summary="Сохранить конфигурацию навыка")
async def save_skill_config(skill_name: str, payload: SkillConfigPayload) -> Dict[str, Any]:
    """Сохраняет параметры в secrets.json навыка."""
    skill_dir = _get_skill_dir(skill_name)
    secrets_file = skill_dir / "secrets.json"

    try:
        content = json.dumps(payload.config, ensure_ascii=False, indent=2)
        secrets_file.write_text(content, encoding="utf-8")
        logger.info(f"[router_skills] Конфигурация для навыка {skill_name} успешно сохранена")
        return {"status": "ok", "message": f"Конфигурация для {skill_name} сохранена", "skill": skill_name}
    except Exception as exc:
        logger.error(f"[router_skills] Ошибка записи secrets.json для {skill_name}: {exc}")
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить конфигурацию: {exc}")


@router.post("/{skill_name}/test-connection", summary="Проверить подключение навыка")
async def test_skill_connection(skill_name: str) -> Dict[str, Any]:
    """Выполняет проверку соединения, если у навыка есть соответствующий скрипт."""
    skill_dir = _get_skill_dir(skill_name)
    test_script = skill_dir / "scripts" / "test_connection.py"

    if not test_script.is_file():
        raise HTTPException(status_code=400, detail="Данный навык не поддерживает тестирование подключения")

    import subprocess
    import sys

    try:
        res = subprocess.run(
            [sys.executable, str(test_script), "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(skill_dir),
        )
        stdout = res.stdout.strip()
        try:
            parsed = json.loads(stdout)
            return {"status": "ok", "result": parsed}
        except Exception:
            return {
                "status": "ok" if res.returncode == 0 else "error",
                "output": stdout or res.stderr.strip(),
                "returncode": res.returncode,
            }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Таймаут проверки соединения (20 сек)")
    except Exception as exc:
        logger.error(f"[router_skills] Ошибка выполнения test_connection.py: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка выполнения диагностики: {exc}")
