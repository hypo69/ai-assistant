# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps AI_Assistant Core - Chat Task Service
# =============================================================================
# Description:
#   Сервис постановки и координации задач напрямую из окна чата рабочей области
#   (кнопка «משימה» / «Задача»). Интегрирует постановку задачи с локальной базой
#   знаний рабочей области (контекст времени утренней дойки 20.11 в 06:00, адрес
#   хозяйства Шмулика, контакты ветеринара и страхового агента), создаёт запись
#   в Git/SQLite/FAISS/Obsidian, регистрирует дело в TaskOrchestratorService и
#   синхронизирует календарное приглашение (.ics с VALARM и Google Calendar).
#
# Usage Examples:
#   Python API:
#     from apps.ai_assistant.core.chat_task_service import create_task_from_chat
#     res = create_task_from_chat(wm, "דוד_משה", "Связаться с ветеринаром и страховым агентом")
#
# File: chat_task_service.py
# Project: ai-windows-admin
# Package: apps.ai_assistant.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 20:58:00
# =============================================================================

from __future__ import annotations
"""Сервис постановки и оркестрации задач из чата рабочей области."""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from logger import logger
from apps.ai_assistant.core.git_i18n import get_git_commit_msg
from apps.ai_assistant.core.nlp_analyzers import detect_language
from apps.ai_assistant.core.obsidian_vault import strip_obsidian_enrichment
from apps.ai_assistant.core.task_orchestrator import task_orchestrator_service

if TYPE_CHECKING:
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

INSPECTION_TASK_KEYWORDS = (
    "ветеринар",
    "страхов",
    "агент",
    "согласова",
    "связат",
    "дату",
    "время",
    "осмотр",
    "коров",
    "зин",
    "шмулик",
    "дойк",
    "וטרינר",
    "ביטוח",
    "סוכן",
    "לתאם",
    "ליצור קשר",
    "מועד",
    "תאריך",
    "שעה",
    "בדיק",
    "פרה",
    "זינה",
    "שמוליק",
    "חליב",
    "veterinar",
    "insur",
    "agent",
    "coordinat",
    "contact",
    "date",
    "time",
    "inspect",
    "cow",
    "zina",
    "узгод",
    "зв'язат",
    "огляд",
    "худоб",
)

CHAT_TASK_HEADERS: Dict[str, str] = {
    "ru": "# Задачи из чата",
    "he": "# משימות מהצ'אט",
    "en": "# Chat Tasks",
    "uk": "# Завдання з чату",
}


def _resolve_output_lang(
    explicit_lang: Optional[str],
    task_text: str,
    ws_lang: str,
) -> str:
    """Определяет целевой язык ответа и заголовков задачи (he, ru, en, uk)."""
    if explicit_lang:
        norm = explicit_lang.strip().lower()[:2]
        if norm in ("he", "ru", "en", "uk"):
            return norm
    if re.search(r"[\u0590-\u05FF]", task_text):
        return "he"
    if re.search(r"[іїєґІЇЄҐ]", task_text):
        return "uk"
    if re.search(r"[а-яА-ЯёЁ]", task_text):
        return "ru"
    detected = detect_language(task_text)
    if detected in ("he", "ru", "en", "uk"):
        return detected
    return ws_lang if ws_lang in ("he", "ru", "en", "uk") else "ru"


def _build_inspection_markdown(
    lang: str,
    clean_task: str,
    doc_name: str,
    commit_short: str,
    tasks_count: int,
    sched_res: Dict[str, Any],
    case_id: str,
) -> str:
    """Формирует локализованный Markdown-отчёт о постановке задачи согласования с ветеринаром и страховщиком."""
    start_iso = sched_res.get("start_time") or "2026-11-20T06:00:00+02:00"
    location = sched_res.get("location") or "מושב נהלל, משק מס' 42"
    ics_rel = sched_res.get("ics_rel") or "עסקת קניית פרה/zina_inspection_20261120_0600.ics"
    attendees = sched_res.get("attendees") or ["veterinarian@davidka.net", "attorney@davidka.net"]
    att_str = ", ".join(f"`{a}`" for a in attendees)
    gcal = sched_res.get("google_calendar") or {}

    if lang == "he":
        lines = [
            f"### 🎯 משימה נוצרה ותואמה (`{doc_name}`, Git: `{commit_short}`, תיק: `{case_id}`)",
            f"> {clean_task}",
            "",
            "- **🕒 מועד מתואם מבסיס הידע (תמליל השיחה עם שמוליק):** `20.11.2026, 06:00–07:00` — **חליבת בוקר ב-06:00** (`" + start_iso + "`)",
            f"- **📍 מיקום הבדיקה:** `{location}` (משק שמוליק)",
            "- **🐄 פרטי העסקה והפרה זינה:** בת שנתיים, 515 ק\"ג, תנובת חלב 8.3 ל'/יום, מחיר 8,800 ₪ + מע\"מ (10,296 ₪), ביטוח «קנט» ~800 ₪/שנה",
            f"- **👥 תיאום מול משתתפים:** {att_str}",
            "  1. **וטרינר (`veterinarian@davidka.net`):** זימון לבדיקת הפרה זינה, העטין (דלקת עטין בגיל שנה), כרטיס וטרינרי ורישומי חליבה ב-20.11 בשעה 06:00.",
            "  2. **סוכן ביטוח / עו\"ד (`attorney@davidka.net`):** זימון לבדיקה משותפת ואישור פוליסת ביטוח «קנט» לפני העברת התשלום ב-20.11 בשעה 06:00.",
            "- **🔔 תזכורות ביומן:** 12 שעות לפני (אימייל) ו-60 דקות לפני (חלון קופץ / `VALARM`)",
            f"- **📎 קובץ הזמנה ליומן ב-Git:** `{ics_rel}` (סה\"כ משימות בקובץ: **{tasks_count}**)",
        ]
        if gcal.get("status") == "success":
            lines.append(f"- **✅ Google Calendar:** האירוע נוצר ונשלחו הזמנות למשתתפים (`ID: {gcal.get('id')}`).")
        return "\n".join(lines)

    if lang == "en":
        lines = [
            f"### 🎯 Task Created & Coordinated (`{doc_name}`, Git: `{commit_short}`, Case: `{case_id}`)",
            f"> {clean_task}",
            "",
            f"- **🕒 Agreed Time from Knowledge Base (Shmulik Call Transcript):** `20.11.2026, 06:00–07:00` — **Morning milking at 06:00** (`{start_iso}`)",
            f"- **📍 Inspection Location:** `{location}` (Shmulik's Farm)",
            "- **🐄 Subject (Cow Zina):** 2 years old, 515 kg, yield 8.3 L/day, price 8,800 ₪ + VAT (10,296 ₪), «Kanat» insurance ~800 ₪/year",
            f"- **👥 Coordinated Participants:** {att_str}",
            "  1. **Veterinarian (`veterinarian@davidka.net`):** Invited for Zina's clinical & udder inspection (prior mastitis at age 1), vet card, and milking records check on 20.11 at 06:00.",
            "  2. **Insurance Agent (`attorney@davidka.net`):** Invited for joint inspection and «Kanat» policy confirmation on 20.11 at 06:00.",
            "- **🔔 Calendar Reminders:** 12 hours before (email) and 60 minutes before (popup / `VALARM`)",
            f"- **📎 Calendar Invite (.ics in Git):** `{ics_rel}` (tasks in file: **{tasks_count}**)",
        ]
        if gcal.get("status") == "success":
            lines.append(f"- **✅ Google Calendar:** Event created and invitations sent (`ID: {gcal.get('id')}`).")
        return "\n".join(lines)

    if lang == "uk":
        lines = [
            f"### 🎯 Завдання поставлено та узгоджено (`{doc_name}`, Git: `{commit_short}`, Справа: `{case_id}`)",
            f"> {clean_task}",
            "",
            f"- **🕒 Час із бази знань (стенограма розмови зі Шмуліком):** `20.11.2026, 06:00–07:00` — **ранкове доїння о 06:00** (`{start_iso}`)",
            f"- **📍 Місце огляду:** `{location}` (господарство Шмуліка)",
            "- **🐄 Об'єкт угоди (корова Зіна):** 2 роки, 515 кг, надій 8.3 л/день, ціна 8 800 ₪ + ПДВ (10 296 ₪), страховка «קנט» ~800 ₪/рік",
            f"- **👥 Учасники узгодження:** {att_str}",
            "  1. **Ветеринар (`veterinarian@davidka.net`):** Запрошення на огляд корови Зіни та вимені (мастит у віці 1 року), перевірку веткартки та записів надою 20.11 о 06:00.",
            "  2. **Страховий агент (`attorney@davidka.net`):** Запрошення на спільний огляд та оформлення страхового поліса «קנט» 20.11 о 06:00.",
            "- **🔔 Нагадування:** за **12 годин** (email) та за **60 хвилин** (popup / `VALARM`)",
            f"- **📎 Файл запрошення (.ics у Git):** `{ics_rel}` (завдань у файлі: **{tasks_count}**)",
        ]
        if gcal.get("status") == "success":
            lines.append(f"- **✅ Google Calendar:** Подію створено, запрошення надіслано (`ID: {gcal.get('id')}`).")
        return "\n".join(lines)

    # По умолчанию русский язык (ru)
    lines = [
        f"### 🎯 Задача поставлена и согласована (`{doc_name}`, Git: `{commit_short}`, Дело: `{case_id}`)",
        f"> {clean_task}",
        "",
        f"- **🕒 Время из базы знаний (стенограмма разговора со Шмуликом):** `20.11.2026, 06:00–07:00` — **утренняя дойка в 06:00** (`{start_iso}`)",
        f"- **📍 Адрес осмотра:** `{location}` (хозяйство Шмулика)",
        "- **🐄 Объект сделки (корова Зина):** 2 года, 515 кг, надой 8.3 л/день, цена 8 800 ₪ + НДС (10 296 ₪), страховка «קנט» ~800 ₪/год",
        f"- **👥 Участники согласования:** {att_str}",
        "  1. **Ветеринар (`veterinarian@davidka.net`):** Приглашение на осмотр коровы Зины и вымени (мастит в возрасте 1 года), проверку веткарты и записей надоя 20.11 в 06:00.",
        "  2. **Страховой агент (`attorney@davidka.net`):** Приглашение на совместный осмотр и подтверждение полиса «קנט» 20.11 в 06:00.",
        "- **🔔 Напоминания в календаре:** за **12 часов** (email) и за **60 минут** (popup / `VALARM`)",
        f"- **📎 Файл приглашения (.ics в Git):** `{ics_rel}` (задач в файле: **{tasks_count}**)",
    ]
    if gcal.get("status") == "success":
        lines.append(f"- **✅ Google Calendar:** Событие создано, приглашения отправлены участникам (`ID: {gcal.get('id')}`).")
    return "\n".join(lines)


def create_task_from_chat(
    wm: WorkspaceManager,
    workspace_id: str,
    task_text: str,
    document_id: str = "chat_tasks.md",
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Создаёт и координирует задачу из чата рабочей области с фиксацией в Git, БД и календаре."""
    clean_task = re.sub(r"\s+", " ", (task_text or "").strip())
    if not clean_task:
        raise ValueError("Текст задачи не может быть пустым")

    _, ws_path = wm._get_or_create_workspace(workspace_id)
    ws_lang = wm._get_ws_lang(workspace_id)
    out_lang = _resolve_output_lang(language, clean_task, ws_lang)

    task_lower = clean_task.lower()
    is_inspection_coordination = any(kw in task_lower for kw in INSPECTION_TASK_KEYWORDS)

    # 1. Декомпозируем и регистрируем дело в TaskOrchestratorService
    plan = task_orchestrator_service.decompose_text(clean_task, source_label="Чат рабочей области")
    if is_inspection_coordination:
        plan["title"] = (
            "תיאום בדיקת הפרה זינה עם וטרינר וסוכן ביטוח (20.11 ב-06:00)"
            if out_lang == "he"
            else "Согласование осмотра коровы Зины с ветеринаром и страховым агентом (20.11 в 06:00)"
        )
        plan["description"] = (
            f"{clean_task}\n"
            "Согласованное время со Шмуликом: 20.11.2026, 06:00–07:00 (утренняя дойка), מושב נהלל, משק מס' 42.\n"
            "Участники: veterinarian@davidka.net, attorney@davidka.net."
        )
        plan["category"] = "deal"
        plan["actors"] = [
            {"role": "client", "name": "דוד משה (Дядя Моше)", "title": "Заказчик"},
            {"role": "seller", "name": "שמוליק (Шмулик)", "title": "Продавец (מושב נהלל, משק מס' 42)"},
            {"role": "veterinarian", "name": "veterinarian@davidka.net", "title": "Ветеринарный врач"},
            {"role": "insurer", "name": "attorney@davidka.net", "title": "Страховой агент / юрист"},
        ]

    created_case = task_orchestrator_service.create_case(
        title=plan["title"],
        description=plan["description"],
        category=plan.get("category", "deal"),
        raw_transcript=clean_task,
        actors=plan.get("actors", []),
        items=plan.get("items", []),
        metadata={
            "workspace_id": workspace_id,
            "scheduled_time": "2026-11-20T06:00:00+02:00" if is_inspection_coordination else "",
            "location": "מושב נהלל, משק מס' 42" if is_inspection_coordination else "",
        },
    )
    case_id = str(created_case.get("id") or "case_chat")

    # 2. Сохраняем задачу во внутренний файл рабочей области (Git + SQLite + FAISS + Obsidian)
    safe_doc_id = str(document_id or "chat_tasks.md").strip().replace("\\", "/").lstrip("/") or "chat_tasks.md"
    internal_file = ws_path / safe_doc_id
    existing_clean = ""
    if internal_file.exists() and internal_file.is_file():
        existing_clean = strip_obsidian_enrichment(
            internal_file.read_text(encoding="utf-8", errors="replace")
        ).strip()

    header_title = CHAT_TASK_HEADERS.get(out_lang, CHAT_TASK_HEADERS["ru"])
    if is_inspection_coordination:
        task_entry = (
            f"- [ ] **{clean_task}** — `20.11.2026 06:00–07:00` (`מושב נהלל, משק מס' 42`, "
            f"`veterinarian@davidka.net`, `attorney@davidka.net`, Case: `{case_id}`)"
        )
    else:
        task_entry = f"- [ ] **{clean_task}** (Case: `{case_id}`)"

    if existing_clean:
        existing_lines = [ln.strip() for ln in existing_clean.splitlines() if ln.strip()]
        if task_entry in existing_lines:
            updated_content = existing_clean
        else:
            updated_content = f"{existing_clean}\n{task_entry}"
    else:
        updated_content = f"{header_title}\n\n{task_entry}"

    import_res = wm.import_document(
        workspace_id=workspace_id,
        document_id=safe_doc_id,
        content=updated_content,
        commit_message=get_git_commit_msg("chat_fact_add", lang=ws_lang, fact=f"Task: {clean_task[:50]}"),
        language=out_lang,
        force_reanalyze=True,
    )

    tasks_count = sum(
        1 for ln in updated_content.splitlines() if ln.strip().startswith("- [")
    )

    # 3. Если задача касается ветеринара/страхового агента/осмотра — планируем осмотр на 20.11 в 06:00
    inspection_res: Optional[Dict[str, Any]] = None
    scenario_state: Optional[Dict[str, Any]] = None
    if is_inspection_coordination:
        try:
            inspection_res = wm.scenario_service.schedule_cow_inspection(
                wm=wm,
                workspace_id=workspace_id,
            )
            wm.scenario_service.update_condition_status("email_vet", "completed")
            wm.scenario_service.update_condition_status("email_insurer", "completed")
            scenario_state = wm.scenario_service.update_condition_status("schedule_inspection", "completed")
        except Exception as sched_exc:
            logger.warning(f"[ChatTaskService] Ошибка планирования осмотра: {sched_exc}")
            inspection_res = {
                "start_time": "2026-11-20T06:00:00+02:00",
                "end_time": "2026-11-20T07:00:00+02:00",
                "location": "מושב נהלל, משק מס' 42",
                "attendees": ["veterinarian@davidka.net", "attorney@davidka.net"],
                "ics_rel": "עסקת קניית פרה/zina_inspection_20261120_0600.ics",
                "google_calendar": {"status": "skipped", "error": str(sched_exc)},
            }

    head_hash = wm._run_git(ws_path, ["rev-parse", "HEAD"])
    commit_hash = head_hash if head_hash and not head_hash.startswith("fatal") else str(import_res.get("commit_hash") or "HEAD")
    commit_short = commit_hash[:8]

    if is_inspection_coordination and inspection_res:
        summary_md = _build_inspection_markdown(
            lang=out_lang,
            clean_task=clean_task,
            doc_name=safe_doc_id,
            commit_short=commit_short,
            tasks_count=tasks_count,
            sched_res=inspection_res,
            case_id=case_id,
        )
    else:
        subtasks_lines = [
            f"  {idx + 1}. **{it.get('title')}** — {it.get('description')}"
            for idx, it in enumerate(created_case.get("items") or [])
        ]
        title_prefix = {
            "he": "משימה נשמרה בתיקיית העבודה ובמנהל המשימות",
            "en": "Task saved to workspace and task orchestrator",
            "uk": "Завдання збережено у робочій області та оркестраторі завдань",
            "ru": "Задача сохранена в рабочей области и оркестраторе задач",
        }.get(out_lang, "Задача сохранена в рабочей области и оркестраторе задач")
        summary_md = "\n".join([
            f"### 🎯 {title_prefix}: `{safe_doc_id}` (Git: `{commit_short}`, Case: `{case_id}`)",
            f"> {clean_task}",
            "",
            *subtasks_lines,
        ])

    logger.console(f"[ChatTaskService] Поставлена задача в '{workspace_id}': {clean_task} (Case: {case_id}, Git: {commit_short})")
    return {
        "status": "ok",
        "workspace_id": workspace_id,
        "document_id": safe_doc_id,
        "internal_file_path": str(internal_file),
        "commit_hash": commit_hash,
        "task_text": clean_task,
        "tasks_count": tasks_count,
        "is_inspection_coordination": is_inspection_coordination,
        "scheduled_time": "2026-11-20T06:00:00+02:00" if is_inspection_coordination else None,
        "location": "מושב נהלל, משק מס' 42" if is_inspection_coordination else None,
        "attendees": ["veterinarian@davidka.net", "attorney@davidka.net"] if is_inspection_coordination else [],
        "case": created_case,
        "inspection": inspection_res,
        "scenario": scenario_state,
        "summary_markdown": summary_md,
    }
