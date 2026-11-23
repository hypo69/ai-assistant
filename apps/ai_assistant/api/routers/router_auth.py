# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant - Google OAuth & Account Management Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор аутентификации и авторизации Google OAuth 2.0,
#   проверки профиля (/api/v1/auth/check), запуска потока авторизации (/auth/google)
#   и управления пулом корпоративных учетных записей Google Workspace.
#
# File: router_auth.py
# Package: apps.ai_assistant.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 02:17:00
# =============================================================================

from __future__ import annotations

"""Маршрутизатор Google OAuth 2.0 авторизации и управления профилями."""

import asyncio
import html
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from src.ai.google_accounts_state import (
    DEFAULT_SCOPES,
    _OAUTH_FILES_DIR,
    _TOKENS_DIR,
    delete_google_account,
    get_account_info,
    list_google_accounts,
    load_account_credentials,
    reset_account_status,
    resolve_project_path,
    save_account_credentials,
    save_google_account,
    set_default_account,
)

router = APIRouter(tags=["Google OAuth & Accounts"])

_OAUTH_STATE_LOCK = threading.Lock()
_PENDING_OAUTH_FLOWS: Dict[str, Dict[str, Any]] = {}
_OAUTH_STATE_TTL_SEC: float = 600.0


def _purge_expired_oauth_states() -> None:
    """Удаляет просроченные OAuth state-записи из памяти."""
    now = time.time()
    expired = [k for k, v in _PENDING_OAUTH_FLOWS.items() if now - v.get("created_at", 0.0) > _OAUTH_STATE_TTL_SEC]
    for key in expired:
        _PENDING_OAUTH_FLOWS.pop(key, None)


def _build_callback_url(request: Request) -> str:
    """Формирует корректный redirect_uri для Google OAuth 2.0 callback на текущем хосте и порту."""
    raw_url = str(request.url_for("auth_google_callback"))
    parsed = urlparse(raw_url)
    host = parsed.hostname or "127.0.0.1"
    if host == "0.0.0.0":
        netloc = f"127.0.0.1:{parsed.port}" if parsed.port else "127.0.0.1"
        return urlunparse(parsed._replace(netloc=netloc))
    return raw_url


def _sanitize_next_url(raw_next: str) -> str:
    """Проверяет параметр перенаправления next против Open Redirect и управляющих символов."""
    cleaned = (raw_next or "/").strip()
    if not cleaned.startswith("/") or cleaned.startswith("//") or "\\" in cleaned:
        return "/"
    return cleaned


class GoogleAccountPayload(BaseModel):
    """Полезная нагрузка для создания/добавления Google аккаунта."""
    name: Optional[str] = Field(default=None, description="Имя аккаунта")
    account_name: Optional[str] = Field(default=None, description="Алиас имени аккаунта")
    type: Optional[str] = Field(default="oauth2", description="Тип: oauth2 или service_account")
    account_type: Optional[str] = Field(default=None, description="Алиас типа аккаунта")
    email: Optional[str] = Field(default=None, description="Email адрес")
    client_id: Optional[str] = Field(default=None, description="OAuth2 Client ID")
    client_secret: Optional[str] = Field(default=None, description="OAuth2 Client Secret")
    credentials_json: Optional[str] = Field(default=None, description="JSON учетных данных строкой")
    credentials_dict: Optional[Dict[str, Any]] = Field(default=None, description="JSON учетных данных словарем")
    set_as_default: Optional[bool] = Field(default=False, description="Установить по умолчанию")


class UserProfileUpdatePayload(BaseModel):
    """Полезная нагрузка обновления профиля пользователя."""
    full_name: Optional[str] = Field(default=None, description="Полное имя")
    email: Optional[str] = Field(default=None, description="Email адрес")
    picture: Optional[str] = Field(default=None, description="URL или путь к аватару")
    preferences: Optional[Dict[str, Any]] = Field(default=None, description="Пользовательские настройки")


def _get_active_auth_state() -> Dict[str, Any]:
    """Определяет текущий статус аутентификации пользователя через Google и базу data/users.db."""
    from apps.ai_assistant.core.users import user_service

    accounts = list_google_accounts()
    default_acc = next((a for a in accounts if a.get("is_default")), accounts[0] if accounts else None)

    has_google = False
    user_email = ""
    user_name = "davidka"
    role = "Admin"
    picture = ""

    if default_acc:
        acc_name = default_acc.get("name", "")
        token_rel = default_acc.get("token_file", "")
        token_path = resolve_project_path(token_rel) if token_rel else (_TOKENS_DIR / f"{acc_name}_token.json")

        if token_path.exists():
            has_google = True
            user_name = acc_name
            user_email = default_acc.get("email") or ""

            # Попытка извлечь email из сохраненного токена, если он не указан
            if not user_email:
                try:
                    with open(token_path, "r", encoding="utf-8") as f:
                        tdata = json.load(f)
                        user_email = tdata.get("account", "")
                except Exception:
                    pass

            if not user_email:
                user_email = f"{acc_name}@gmail.com"

    # Синхронизация с профилем в локальной БД data/users.db
    user = user_service.get_or_sync_active_user(
        username=user_name,
        email=user_email,
        has_google=has_google,
    )
    if user:
        picture = user.picture or ""
        user_email = user.email or user_email
        role = user.role.capitalize() if user.role else "Admin"

    display_name = user.full_name if (user and user.full_name) else (user_name if has_google else "Локальный пользователь")

    return {
        "authenticated": has_google,
        "email": user_email,
        "name": display_name,
        "picture": picture or None,
        "role": role,
        "is_admin": True,
        "has_google": has_google,
        "oauth_enabled": True,
        "accounts": accounts,
        "user_profile": user.to_dict() if user else {},
    }


# =============================================================================
#  Маршруты статуса и сессии пользователя
# =============================================================================

@router.get("/api/v1/auth/check", summary="Проверка текущего статуса авторизации")
async def auth_check() -> Dict[str, Any]:
    """Возвращает информацию о текущем пользователе и состоянии Google OAuth."""
    return await asyncio.to_thread(_get_active_auth_state)


@router.get("/api/v1/auth/profile", summary="Получение профиля пользователя")
async def get_user_profile(username: Optional[str] = None) -> Dict[str, Any]:
    """Возвращает профиль пользователя из базы data/users.db."""
    from apps.ai_assistant.core.users import user_service
    u = await asyncio.to_thread(user_service.get_user, username or "davidka")
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"status": "success", "user": u.to_dict()}


@router.post("/api/v1/auth/profile", summary="Обновление профиля пользователя")
async def update_user_profile(payload: UserProfileUpdatePayload, username: Optional[str] = None) -> Dict[str, Any]:
    """Обновляет профиль пользователя в базе data/users.db."""
    from apps.ai_assistant.core.users import user_service
    uname = username or "davidka"
    u = await asyncio.to_thread(
        user_service.update_profile,
        username=uname,
        full_name=payload.full_name,
        email=payload.email,
        picture=payload.picture,
        preferences=payload.preferences,
    )
    if not u:
        raise HTTPException(status_code=404, detail="Не удалось обновить профиль пользователя")
    return {"status": "success", "user": u.to_dict()}


@router.post("/api/v1/auth/logout", summary="Выход из сессии Google OAuth")
async def auth_logout() -> Dict[str, Any]:
    """Сбрасывает токен текущей авторизации."""
    def _do_logout() -> Dict[str, Any]:
        accounts = list_google_accounts()
        for acc in accounts:
            token_rel = acc.get("token_file", "")
            if token_rel:
                tp = resolve_project_path(token_rel)
                if tp.exists():
                    tp.unlink(missing_ok=True)
        return {"status": "success", "message": "Сессия успешно завершена"}

    try:
        return await asyncio.to_thread(_do_logout)
    except Exception as exc:
        logger.warning(f"[Auth] Ошибка выхода: {exc}")
        return {"status": "error", "message": str(exc)}


# =============================================================================
#  Маршруты потока авторизации Google OAuth 2.0
# =============================================================================

@router.get("/auth/google", response_class=HTMLResponse, summary="Точка входа авторизации Google OAuth")
@router.get("/api/v1/auth/google", response_class=HTMLResponse, summary="Точка входа авторизации Google OAuth (v1)", include_in_schema=False)
async def auth_google_page(next: str = "/") -> HTMLResponse:
    """Отображает интерактивную страницу запуска OAuth потока в браузере с защитой от XSS и Open Redirect."""
    safe_next = _sanitize_next_url(next)
    escaped_next_attr = html.escape(safe_next, quote=True)
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Google OAuth Авторизация — AI Assistant</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
  <style>
    body {{
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background: #111827;
      color: #f3f4f6;
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 1rem;
    }}
    .auth-box {{
      width: 100%;
      max-width: 440px;
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 14px;
      padding: 2rem;
      text-align: center;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }}
    .google-badge {{
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: #ffffff;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      margin-bottom: 1.25rem;
    }}
  </style>
</head>
<body>
  <div class="auth-box">
    <div class="google-badge">
      <svg width="32" height="32" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
      </svg>
    </div>
    <h4 class="fw-bold mb-2">Google OAuth Авторизация</h4>
    <p class="text-secondary small mb-4" id="auth-status-desc">
      Запуск локального сервера авторизации... В вашем браузере откроется окно выбора аккаунта Google.
    </p>

    <div class="d-flex justify-content-center mb-4">
      <div class="spinner-border text-primary" role="status" id="auth-spinner">
        <span class="visually-hidden">Загрузка...</span>
      </div>
    </div>

    <div class="alert alert-danger d-none py-2 small mb-3" id="auth-error-box"></div>

    <div class="d-flex gap-2 justify-content-center">
      <button class="btn btn-primary btn-sm px-3 fw-semibold" id="btn-trigger-oauth" type="button">
        <i class="bi bi-box-arrow-up-right me-1"></i> Запустить авторизацию
      </button>
      <a href="{escaped_next_attr}" class="btn btn-outline-secondary btn-sm px-3">
        Назад к приложению
      </a>
    </div>
  </div>

  <script>
    const nextUrl = {json.dumps(safe_next)};
    const desc = document.getElementById('auth-status-desc');
    const spinner = document.getElementById('auth-spinner');
    const errBox = document.getElementById('auth-error-box');
    const btn = document.getElementById('btn-trigger-oauth');

    async function runOAuth() {{
      btn.disabled = true;
      spinner.classList.remove('d-none');
      errBox.classList.add('d-none');
      desc.textContent = 'Ожидание подтверждения в окне Google... Пожалуйста, выберите ваш аккаунт Google и разрешите доступ.';

      try {{
        const loginUrl = `/api/v1/auth/google/login?next=${{encodeURIComponent(nextUrl)}}`;
        const resp = await fetch(loginUrl, {{ method: 'POST' }});
        const data = await resp.json();

        if (data.status === 'redirect' && data.auth_url) {{
          desc.textContent = 'Перенаправление на страницу авторизации Google...';
          window.location.href = data.auth_url;
          return;
        }}
        if (data.status === 'success') {{
          desc.innerHTML = '<span class="text-success fw-bold">✓ Авторизация успешно выполнена!</span> Перенаправление...';
          spinner.classList.add('d-none');
          setTimeout(() => {{ window.location.href = nextUrl; }}, 800);
        }} else {{
          throw new Error(data.message || 'Ошибка авторизации');
        }}
      }} catch (err) {{
        spinner.classList.add('d-none');
        btn.disabled = false;
        errBox.textContent = err.message;
        errBox.classList.remove('d-none');
        desc.textContent = 'Не удалось завершить авторизацию. Попробуйте еще раз или проверьте настройки Google Cloud Console.';
      }}
    }}

    btn.addEventListener('click', runOAuth);
    // Автоматический запуск при первой загрузке страницы
    window.addEventListener('load', () => {{
      setTimeout(runOAuth, 400);
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


def _prepare_web_oauth_flow(callback_url: str, account_name: Optional[str], safe_next: str) -> Dict[str, Any]:
    """Создает Google OAuth 2.0 authorization URL и сохраняет PKCE-состояние для серверного callback."""
    from google_auth_oauthlib.flow import Flow

    acc_info = get_account_info(account_name)
    if not acc_info:
        return {
            "status": "error",
            "message": "Не найден настроенный Google аккаунт. Загрузите credentials.json в настройках.",
        }

    name = acc_info.get("name") or account_name or "default"
    creds_rel = acc_info.get("credentials_file", "")
    creds_path = resolve_project_path(creds_rel) if creds_rel else None
    if not creds_path or not creds_path.exists():
        return {
            "status": "error",
            "message": f"Файл учетных данных для '{name}' не найден ({creds_path}). Проверьте src/secrets/google_ouath_files.",
        }

    flow = Flow.from_client_secrets_file(
        str(creds_path),
        scopes=DEFAULT_SCOPES,
        redirect_uri=callback_url,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    with _OAUTH_STATE_LOCK:
        _purge_expired_oauth_states()
        _PENDING_OAUTH_FLOWS[state] = {
            "account_name": name,
            "next_url": safe_next,
            "redirect_uri": callback_url,
            "creds_path": str(creds_path),
            "code_verifier": getattr(flow, "code_verifier", None),
            "created_at": time.time(),
        }

    return {
        "status": "redirect",
        "account": name,
        "auth_url": auth_url,
    }


def _exchange_oauth_code(pending: Dict[str, Any], code: str) -> Dict[str, Any]:
    """Обменивает OAuth authorization code на токены и сохраняет учетные данные аккаунта."""
    from google_auth_oauthlib.flow import Flow

    redirect_uri = pending["redirect_uri"]
    parsed = urlparse(redirect_uri)
    if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    flow = Flow.from_client_secrets_file(
        pending["creds_path"],
        scopes=DEFAULT_SCOPES,
        redirect_uri=redirect_uri,
    )
    if pending.get("code_verifier"):
        flow.code_verifier = pending["code_verifier"]

    flow.fetch_token(code=code)
    prof = save_account_credentials(pending["account_name"], flow.credentials)
    return {"account": pending["account_name"], "profile": prof}


@router.post("/api/v1/auth/google/login", summary="Запуск OAuth consent flow")
async def api_auth_google_login(
    request: Request,
    account_name: Optional[str] = None,
    next: str = "/",
) -> Dict[str, Any]:
    """Формирует URL перенаправления Google OAuth 2.0 (работает локально и в Docker)."""
    try:
        callback_url = _build_callback_url(request)
        safe_next = _sanitize_next_url(next)
        return await asyncio.to_thread(_prepare_web_oauth_flow, callback_url, account_name, safe_next)
    except Exception as exc:
        logger.error(f"[Auth] Ошибка подготовки OAuth авторизации: {exc}")
        return {"status": "error", "message": str(exc)}


@router.get("/auth/google/callback", name="auth_google_callback", summary="Обработчик возврата Google OAuth 2.0")
async def auth_google_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
) -> Response:
    """Принимает код авторизации от Google, обменивает его на токен и возвращает пользователя в приложение."""
    if error:
        safe_err = html.escape(error)
        return HTMLResponse(
            content=f"<html><body style='font-family:sans-serif;padding:2rem;background:#111827;color:#f3f4f6'>"
            f"<h3>Авторизация Google отменена</h3><p>Ошибка: {safe_err}</p>"
            f"<a href='/' style='color:#60a5fa'>Вернуться в приложение</a></body></html>",
            status_code=400,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Отсутствуют обязательные параметры code или state")

    with _OAUTH_STATE_LOCK:
        _purge_expired_oauth_states()
        pending = _PENDING_OAUTH_FLOWS.pop(state, None)

    if not pending:
        return HTMLResponse(
            content="<html><body style='font-family:sans-serif;padding:2rem;background:#111827;color:#f3f4f6'>"
            "<h3>Сессия авторизации истекла</h3><p>Пожалуйста, запустите вход через Google заново.</p>"
            "<a href='/auth/google' style='color:#60a5fa'>Повторить вход</a></body></html>",
            status_code=400,
        )

    try:
        await asyncio.to_thread(_exchange_oauth_code, pending, code)
        return RedirectResponse(url=_sanitize_next_url(pending.get("next_url", "/")), status_code=302)
    except Exception as exc:
        logger.error(f"[Auth] Ошибка обмена OAuth кода на токен: {exc}")
        safe_msg = html.escape(str(exc))
        return HTMLResponse(
            content=f"<html><body style='font-family:sans-serif;padding:2rem;background:#111827;color:#f3f4f6'>"
            f"<h3>Не удалось завершить авторизацию Google</h3><p>{safe_msg}</p>"
            f"<a href='/auth/google' style='color:#60a5fa'>Повторить вход</a></body></html>",
            status_code=500,
        )


# =============================================================================
#  Маршруты управления пулом учетных записей Google Workspace
# =============================================================================

@router.get("/api/v1/auth/google-accounts", summary="Список аккаунтов Google")
async def list_accounts_endpoint() -> Dict[str, Any]:
    """Возвращает список всех зарегистрированных Google аккаунтов в пуле."""
    def _do_list():
        raw_accounts = list_google_accounts()
        accounts = []
        for acc in raw_accounts:
            item = dict(acc)
            token_str = item.get("token_file", "")
            if token_str:
                token_path = resolve_project_path(token_str)
                item["has_token"] = token_path.exists()
            else:
                item["has_token"] = False
            accounts.append(item)
        return {"status": "success", "accounts": accounts}

    try:
        return await asyncio.to_thread(_do_list)
    except Exception as exc:
        logger.error(f"[Auth] Ошибка получения списка аккаунтов: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/v1/auth/google-accounts", summary="Создать Google аккаунт")
async def create_account_endpoint(payload: GoogleAccountPayload) -> Dict[str, Any]:
    """Создает или обновляет аккаунт Google в пуле."""
    acc_name = (payload.account_name or payload.name or "").strip()
    if not acc_name:
        raise HTTPException(status_code=400, detail="Имя аккаунта обязательно для заполнения")

    acc_type = (payload.account_type or payload.type or "oauth2").strip().lower()
    creds_data: Any = None

    if payload.credentials_dict:
        creds_data = payload.credentials_dict
    elif payload.credentials_json:
        try:
            creds_data = json.loads(payload.credentials_json)
        except Exception:
            creds_data = payload.credentials_json
    elif payload.client_id and payload.client_secret:
        creds_data = {
            "installed": {
                "client_id": payload.client_id.strip(),
                "client_secret": payload.client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
    else:
        raise HTTPException(status_code=400, detail="Предоставьте файл JSON ключа или Client ID/Secret")

    res = await asyncio.to_thread(
        save_google_account,
        account_name=acc_name,
        credentials_path_or_dict=creds_data,
        account_type=acc_type,
        email=payload.email or "",
        set_as_default=bool(payload.set_as_default),
    )
    if not res:
        raise HTTPException(status_code=500, detail="Не удалось сохранить аккаунт в пуле")

    info = await asyncio.to_thread(get_account_info, acc_name)
    return {"status": "success", "account": info}


@router.post("/api/v1/auth/google-accounts/upload", summary="Загрузить credentials.json")
async def upload_credentials_endpoint(
    account_name: Optional[str] = Form(None),
    account_type: Optional[str] = Form("oauth2"),
    email: Optional[str] = Form(""),
    set_as_default: Optional[str] = Form("false"),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Загрузка файла client_secrets или service_account JSON."""
    try:
        content = await file.read()
        try:
            creds_dict = json.loads(content.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Файл не содержит валидный JSON: {exc}")

        detected_type = "service_account" if creds_dict.get("type") == "service_account" else (account_type or "oauth2")
        acc_name = (account_name or "").strip()
        if not acc_name:
            filename = file.filename or "credentials.json"
            acc_name = Path(filename).stem.removesuffix("_secret").removesuffix("_credentials")
            if not acc_name:
                acc_name = "default"

        is_default = str(set_as_default).lower() in ("true", "1", "yes")

        res = await asyncio.to_thread(
            save_google_account,
            account_name=acc_name,
            credentials_path_or_dict=creds_dict,
            account_type=detected_type,
            email=email or "",
            set_as_default=is_default,
        )
        if not res:
            raise HTTPException(status_code=500, detail="Не удалось сохранить аккаунт из файла")

        info = await asyncio.to_thread(get_account_info, acc_name)
        return {"status": "success", "account_name": acc_name, "account": info}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[Auth] Ошибка загрузки файла: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/v1/auth/google-accounts/{name}/set-default", summary="Назначить аккаунт по умолчанию")
@router.post("/api/v1/auth/google-accounts/{name}/default", summary="Назначить аккаунт по умолчанию (алиас)")
async def set_default_endpoint(name: str) -> Dict[str, Any]:
    """Назначает выбранный аккаунт по умолчанию."""
    res = await asyncio.to_thread(set_default_account, name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
    return {"status": "success", "default_account": name}


@router.post("/api/v1/auth/google-accounts/{name}/reset-status", summary="Сбросить статус исчерпания")
async def reset_status_endpoint(name: str) -> Dict[str, Any]:
    """Сбрасывает статус исчерпания квоты в активный."""
    res = await asyncio.to_thread(reset_account_status, name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
    return {"status": "success", "name": name}


def _sync_test_google_account(name: str) -> Dict[str, Any]:
    """Синхронно проверяет и при необходимости обновляет OAuth 2.0 токен."""
    info = get_account_info(name)
    if not info:
        return {"status": "error", "name": name, "message": f"Аккаунт '{name}' не найден"}

    token_rel = info.get("token_file", "")
    token_path = resolve_project_path(token_rel) if token_rel else (_TOKENS_DIR / f"{name}_token.json")

    if not token_path.exists():
        return {
            "status": "warning",
            "name": name,
            "message": "Учетные данные загружены, но токен OAuth 2.0 еще не создан. Нажмите 'Войти через Google'.",
        }

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(token_path), DEFAULT_SCOPES)
        if creds.valid:
            return {"status": "success", "name": name, "message": "OAuth 2.0 токен валиден и активен", "scopes": list(creds.scopes or DEFAULT_SCOPES)}

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as tf:
                    tf.write(creds.to_json())
                return {"status": "success", "name": name, "message": "Токен успешно обновлен через Refresh Token", "scopes": list(creds.scopes or DEFAULT_SCOPES)}
            except Exception as ref_err:
                return {"status": "warning", "name": name, "message": f"Срок токена истек, требуется повторная авторизация: {ref_err}"}

        return {"status": "warning", "name": name, "message": "Токен недействителен, требуется авторизация"}
    except Exception as exc:
        return {"status": "error", "name": name, "message": f"Ошибка верификации токена: {exc}"}


@router.post("/api/v1/auth/google-accounts/{name}/test", summary="Тест валидности токена")
async def test_account_endpoint(name: str) -> Dict[str, Any]:
    """Проверяет аутентификацию и валидность токена Google аккаунта в пуле потоков."""
    return await asyncio.to_thread(_sync_test_google_account, name)


@router.delete("/api/v1/auth/google-accounts/{name}", summary="Удалить аккаунт из пула")
async def delete_account_endpoint(name: str) -> Dict[str, Any]:
    """Удаляет учетную запись Google из пула."""
    res = await asyncio.to_thread(delete_google_account, name)
    if not res:
        raise HTTPException(status_code=404, detail=f"Аккаунт '{name}' не найден")
    return {"status": "success", "message": f"Аккаунт '{name}' удален"}


@router.post("/api/v1/auth/telegram/token", summary="Генерация кода для привязки Telegram к аккаунту")
async def generate_telegram_link_code() -> Dict[str, Any]:
    """Генерирует одноразовый 8-значный код привязки к Telegram-боту."""
    try:
        from plugins.telegram_bot import user_auth
        token = await asyncio.to_thread(user_auth.generate_telegram_link_token)
    except Exception:
        import secrets
        token = f"{secrets.randbelow(90000000) + 10000000}"
    return {
        "status": "success",
        "token": token,
        "expires_in_seconds": 900,
        "instructions": f"Отправьте боту команду: /link {token}",
    }


@router.get("/api/v1/auth/telegram/status", summary="Статус привязки Telegram-аккаунта")
async def get_telegram_link_status() -> Dict[str, Any]:
    """Возвращает информацию о текущей привязке Telegram."""
    try:
        from plugins.telegram_bot import user_auth
        return await asyncio.to_thread(user_auth.get_telegram_link_status)
    except Exception:
        return {"status": "error", "linked": False}


@router.post("/api/v1/auth/telegram/unlink", summary="Отвязка Telegram-аккаунта")
async def unlink_telegram_code() -> Dict[str, Any]:
    """Отвязывает Telegram-аккаунт от текущего профиля."""
    try:
        from plugins.telegram_bot import user_auth
        await asyncio.to_thread(user_auth.unlink_telegram_account)
    except Exception:
        pass
    return {"status": "success", "message": "Telegram-аккаунт успешно отвязан"}
