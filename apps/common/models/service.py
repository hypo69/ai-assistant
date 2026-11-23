# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Common Models - Service Layer
# =============================================================================
# Description:
#   Сервисный слой управления моделями ИИ, провайдерами, системными инструкциями,
#   избранным и тестированием генерации на уровне приложений.
#
# File: service.py
# Package: apps.common.models
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 01:15:00
# =============================================================================

from __future__ import annotations

"""Сервисный слой для управления моделями ИИ и провайдерами."""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger
from apps.common.models.models import SetModelRequest, TestModelPayload


def resolve_active_config_path() -> Path:
    """Возвращает путь к активному файлу конфигурации."""
    root_cfg = __root__ / "config.json"
    if root_cfg.exists():
        return root_cfg
    app_cfg = __root__ / "apps" / "ai_assistant" / "config.json"
    if app_cfg.exists():
        return app_cfg
    return root_cfg


def atomic_write_json_file(target_path: Path, data: Dict[str, Any], indent: int = 4) -> None:
    """Атомарно записывает JSON-файл через временный файл .tmp и os.replace()."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, target_path)


def load_root_config() -> Dict[str, Any]:
    """Загружает главный конфигурационный файл config.json."""
    cfg_path = resolve_active_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"[models.service] Ошибка чтения {cfg_path}: {exc}")
    return {}


def save_root_config(cfg: Dict[str, Any]) -> None:
    """Атомарно сохраняет главный конфигурационный файл config.json."""
    cfg_path = resolve_active_config_path()
    try:
        atomic_write_json_file(cfg_path, cfg, indent=4)
    except Exception as exc:
        logger.error(f"[models.service] Ошибка записи {cfg_path}: {exc}")


def save_ai_config(provider: Optional[str] = None, model_name: str = "") -> None:
    """Сохраняет выбранную модель и провайдера в конфигурационных файлах атомарно."""
    cfg = load_root_config()
    ai_sec = cfg.setdefault("ai_providers_and_models_configuration", {})
    if model_name:
        ai_sec["default_model"] = model_name
    if provider:
        ai_sec["default_provider"] = provider
        prov_key = provider.lower().strip()
        providers = ai_sec.setdefault("providers", {})
        prov_obj = providers.setdefault(prov_key, {})
        prov_obj["enabled"] = True
        if model_name:
            prov_obj["model"] = model_name
            prov_obj["default_model"] = model_name

    cfg.pop("ai", None)

    if "llm" in cfg:
        if model_name:
            cfg["llm"]["default_model"] = model_name
        if provider:
            cfg["llm"]["default_provider"] = provider
    save_root_config(cfg)

    # Синхронизация локальной конфигурации модуля ai_assistant при наличии
    app_cfg_path = __root__ / "apps" / "ai_assistant" / "config.json"
    if app_cfg_path.exists():
        try:
            with open(app_cfg_path, "r", encoding="utf-8") as f:
                app_cfg = json.load(f)
            if "llm" not in app_cfg:
                app_cfg["llm"] = {}
            if model_name:
                app_cfg["llm"]["default_model"] = model_name
            if provider:
                app_cfg["llm"]["default_provider"] = provider
            atomic_write_json_file(app_cfg_path, app_cfg, indent=2)
        except Exception as exc:
            logger.warning(f"[models.service] Ошибка синхронизации apps/ai_assistant/config.json: {exc}")


def get_provider_config(provider_key: str) -> Dict[str, Any]:
    """Возвращает секцию настроек указанного провайдера."""
    cfg = load_root_config()
    ai_sec = cfg.get("ai_providers_and_models_configuration", {})
    providers = ai_sec.get("providers", {})
    return providers.get(provider_key, {})


def update_provider_config(provider_key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Обновляет и сохраняет параметры конкретного провайдера."""
    cfg = load_root_config()
    if "ai_providers_and_models_configuration" not in cfg:
        cfg["ai_providers_and_models_configuration"] = {}
    if "providers" not in cfg["ai_providers_and_models_configuration"]:
        cfg["ai_providers_and_models_configuration"]["providers"] = {}

    cur = cfg["ai_providers_and_models_configuration"]["providers"].get(provider_key, {})
    cur.update(data)
    cfg["ai_providers_and_models_configuration"]["providers"][provider_key] = cur
    save_root_config(cfg)
    return cur


class ModelsService:
    """Сервис управления моделями ИИ на общесистемном уровне."""

    @staticmethod
    def get_available_chat_models(refresh: bool = False, include_unsupported: bool = False) -> Dict[str, Any]:
        """Возвращает сгруппированный список моделей для всех поддерживаемых провайдеров."""
        try:
            from src.ai.model_manager import get_available_models, load_unsupported_models

            gemini_models = get_available_models("gemini", force_refresh=refresh, include_unsupported=include_unsupported)
            foundry_raw = get_available_models("foundry", force_refresh=refresh, include_unsupported=include_unsupported)
            foundry_models = [f"foundry:{m}" if not m.startswith("foundry:") else m for m in foundry_raw]

            ollama_raw = get_available_models("ollama", force_refresh=refresh, include_unsupported=include_unsupported)
            ollama_models = [f"ollama:{m}" if not m.startswith("ollama:") else m for m in ollama_raw]

            agy_models = get_available_models("agy", force_refresh=refresh, include_unsupported=include_unsupported)

            gemini_cli_raw = get_available_models("gemini_cli", force_refresh=refresh, include_unsupported=include_unsupported)
            gemini_cli_models = [f"gemini_cli:{m}" if not m.startswith("gemini_cli:") else m for m in gemini_cli_raw]

            openai_raw = get_available_models("openai", force_refresh=refresh, include_unsupported=include_unsupported)
            openai_models = [
                f"openai:{m}" if not any(m.startswith(f"{p}:") for p in ("openai", "deepseek", "groq", "openrouter", "lmstudio")) else m
                for m in openai_raw
            ]

            return {
                "models": {
                    "gemini": gemini_models or [],
                    "foundry": foundry_models or [],
                    "ollama": ollama_models or [],
                    "agy": agy_models or [],
                    "gemini_cli": gemini_cli_models or [],
                    "openai": openai_models or [],
                    "onnx": ["onnx:directml-default"],
                },
                "unsupported_models": {
                    "gemini": list(load_unsupported_models("gemini")),
                    "foundry": list(load_unsupported_models("foundry")),
                    "ollama": list(load_unsupported_models("ollama")),
                    "agy": list(load_unsupported_models("agy")),
                }
            }
        except Exception as exc:
            logger.warning(f"[models.service] Ошибка загрузки списка моделей: {exc}")
            return {
                "models": {
                    "gemini": [],
                    "agy": [],
                    "ollama": [],
                    "foundry": [],
                }
            }

    @staticmethod
    def get_active_model() -> Dict[str, Any]:
        """Возвращает текущую выбранную модель и провайдер."""
        try:
            from src.user_settings import get_user_settings
            settings = get_user_settings()
            if settings.get("model"):
                user_model = settings.get("model")
                prov = "gemini"
                mod = user_model
                if ":" in user_model:
                    prov, mod = user_model.split(":", 1)
                elif user_model.startswith("agy-"):
                    prov, mod = "agy", user_model
                return {"status": "ok", "provider": prov, "model": mod, "config_file": "user_settings"}
        except Exception:
            pass

        cfg = load_root_config()
        ai_sec = cfg.get("ai_providers_and_models_configuration", {})
        prov = ai_sec.get("default_provider", "gemini")
        model = ai_sec.get("default_model", "gemini-3.1-flash-lite")
        return {"status": "ok", "provider": prov, "model": model, "config_file": "config.json"}

    @staticmethod
    def set_active_model(req: SetModelRequest) -> Dict[str, Any]:
        """Сохраняет выбранную модель и провайдер в конфигурации и настройках пользователя."""
        target_model = req.model.strip()
        provider = (req.provider or "").strip().lower()
        if not provider:
            if ":" in target_model:
                provider, target_model = target_model.split(":", 1)
            elif target_model.startswith("agy-"):
                provider = "agy"
            else:
                provider = "gemini"

        try:
            from src.user_settings import update_user_settings
            update_user_settings(model=target_model)
        except Exception as exc:
            logger.debug(f"[models.service] Ошибка обновления user_settings: {exc}")

        if req.save_to_config:
            save_ai_config(provider=provider, model_name=target_model)

        return {
            "status": "success",
            "message": f"Модель {target_model} успешно сохранена",
            "model": target_model,
            "provider": provider
        }

    @staticmethod
    def get_user_auth_settings() -> Dict[str, Any]:
        """Возвращает сохраненные настройки пользователя, включая избранные модели."""
        try:
            from src.user_settings import get_user_settings
            settings = get_user_settings()
        except Exception:
            settings = {}

        if not settings.get("model"):
            cfg = load_root_config()
            ai_sec = cfg.get("ai_providers_and_models_configuration", {})
            prov = ai_sec.get("default_provider", "gemini")
            model = ai_sec.get("default_model", "gemini-3.1-flash-lite")
            settings["model"] = model
            settings["provider"] = prov

        settings.setdefault("status", "ok")
        settings.setdefault("favorite_models", {})
        return settings

    @staticmethod
    def update_user_auth_settings(model_name: Optional[str] = None, provider: str = "") -> None:
        """Обновляет пользовательские настройки и активную модель."""
        if model_name:
            try:
                from src.user_settings import update_user_settings
                update_user_settings(model=model_name)
            except Exception:
                pass
            save_ai_config(provider=provider, model_name=model_name)

    @staticmethod
    def get_favorite_models() -> Dict[str, Any]:
        """Возвращает словарь избранных моделей и заметок к ним."""
        try:
            from src.user_settings import get_user_settings
            settings = get_user_settings()
            favs = settings.get("favorite_models", {})
            return {"status": "ok", "favorites": favs}
        except Exception:
            return {"status": "ok", "favorites": {}}

    @staticmethod
    def add_favorite_model(model_name: str, note: str = "") -> Dict[str, Any]:
        """Добавляет модель в избранное с опциональной заметкой и меткой UTC ISO 8601."""
        from src.user_settings import get_user_settings, update_user_settings
        settings = get_user_settings()
        favs = dict(settings.get("favorite_models", {}))
        favs[model_name] = {
            "note": note,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        update_user_settings(favorite_models=favs)
        return {"status": "ok", "model": model_name, "favorites": favs}

    @staticmethod
    def delete_favorite_model(model_name: str) -> Dict[str, Any]:
        """Удаляет модель из списка избранного."""
        from src.user_settings import get_user_settings, update_user_settings
        settings = get_user_settings()
        favs = dict(settings.get("favorite_models", {}))
        favs.pop(model_name, None)
        update_user_settings(favorite_models=favs)
        return {"status": "ok", "model": model_name, "favorites": favs}

    @staticmethod
    async def test_model(req: TestModelPayload) -> Dict[str, Any]:
        """Отправляет тестовый запрос к указанной модели и замеряет время отклика."""
        start_time = time.perf_counter()
        target_model = req.model.strip()
        provider = req.provider.strip().lower()

        if not target_model or not provider:
            cfg = load_root_config()
            ai_sec = cfg.get("ai_providers_and_models_configuration", {})
            def_prov = str(ai_sec.get("default_provider", "gemini")).strip().lower() or "gemini"
            def_model = str(ai_sec.get("default_model", "")).strip()
            if not target_model:
                target_model = def_model
            if not provider:
                provider = def_prov

        test_msg = req.message.strip() or "Привет! Назови свою модель и провайдера, и подтверди готовность к работе."

        try:
            from src.ai.orchestration.unified_chat import UnifiedChatModel
            model_instance = UnifiedChatModel(
                provider=provider,
                model=target_model,
                system_instruction=req.system_instruction or "",
            )
            response_text = ""

            if hasattr(model_instance, "ask"):
                response_text = await model_instance.ask(test_msg, attempts=1)
            elif hasattr(model_instance, "chat"):
                response_text = await model_instance.chat(test_msg)
            elif hasattr(model_instance, "chat_stream"):
                chunks = []
                async for chunk in model_instance.chat_stream(test_msg):
                    if chunk:
                        clean_chunk = chunk.replace("[CHAT]", "").replace("[VOICE]", "")
                        if clean_chunk:
                            chunks.append(clean_chunk)
                response_text = "".join(chunks)
            else:
                response_text = f"Модель {target_model} готова к генерации (режим ответа подтвержден)."

            actual_model = target_model
            gemini_inner = getattr(model_instance, "gemini_model", False)
            if gemini_inner:
                actual_model = str(getattr(gemini_inner, "model_name", target_model) or target_model)
            if actual_model != target_model:
                logger.warning(f"[models.service] Запрошена модель {target_model}, фактически ответила {actual_model}")

            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                "status": "success",
                "response": response_text,
                "model": actual_model,
                "requested_model": target_model,
                "provider": provider,
                "duration_ms": duration_ms
            }
        except Exception as exc:
            logger.error(f"[models.service] Ошибка проверочного запроса к {target_model}: {exc}", exc_info=True)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                "status": "error",
                "message": str(exc),
                "model": target_model,
                "provider": provider,
                "duration_ms": duration_ms
            }

    @staticmethod
    def get_system_instruction() -> str:
        """Возвращает текущую системную инструкцию ИИ."""
        try:
            from src.user_settings import get_user_settings
            settings = get_user_settings()
            if settings.get("system_instruction"):
                return settings["system_instruction"]
        except Exception:
            pass

        prompt_file = __root__ / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
        if not prompt_file.exists():
            prompt_file = __root__ / "apps" / "windows" / "prompts" / "chat" / "system_instruction.md"

        if prompt_file.exists():
            try:
                return prompt_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        return "Вы — интеллектуальный ассистент платформы AI-Assistant."

    @staticmethod
    def save_system_instruction(content: str) -> None:
        """Сохраняет системную инструкцию ИИ на диск и в профиль пользователя."""
        if not content:
            return
        try:
            from src.user_settings import update_user_settings
            update_user_settings(system_instruction=content)
        except Exception:
            pass

        prompt_file = __root__ / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_prompt = prompt_file.with_suffix(".md.tmp")
        tmp_prompt.write_text(content, encoding="utf-8")
        os.replace(tmp_prompt, prompt_file)

    @staticmethod
    def get_models_summary() -> Dict[str, Any]:
        """Возвращает общую сводку доступности провайдеров и моделей."""
        cfg = load_root_config()
        ai_sec = cfg.get("ai_providers_and_models_configuration", {})
        return {
            "status": "active",
            "default_provider": ai_sec.get("default_provider", "gemini"),
            "default_model": str(ai_sec.get("default_model", "")).strip(),
            "providers": list(ai_sec.get("providers", {}).keys()),
        }
