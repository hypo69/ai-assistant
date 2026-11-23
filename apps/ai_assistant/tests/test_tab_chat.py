"""
=============================================================================
Process Name: Test AI Assistant Dedicated Chat Tab (tab-chat)
=============================================================================
Description:
    Модульные тесты для проверки выделенной вкладки диалога с ИИ (tab_chat, #tab-chat):
    структура файлов (index.html, main.js, README.md), регистрация в оркестраторе
    вкладок TABS, интеграция в Activity Bar и Drawer меню, клавиатурные сокращения
    (Alt+5), синхронизация рабочей области и многоязычная локализация i18n.

File: test_tab_chat.py
Package: apps/ai_assistant/tests
Author: hypo69
Copyright: © 2026 hypo69
# Updated: 2026-11-19 21:03:00
=============================================================================
"""

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from apps.ai_assistant.main import app

_WEBGUI_DIR = Path(__file__).resolve().parent.parent / "api" / "webgui"


def test_tab_chat_directory_and_files_exist() -> None:
    """Проверяет наличие каталога tab_chat и всех обязательных файлов."""
    tab_dir = _WEBGUI_DIR / "tab_chat"
    assert tab_dir.exists() and tab_dir.is_dir(), f"Каталог {tab_dir} не найден"

    index_html = tab_dir / "index.html"
    main_js = tab_dir / "main.js"
    readme_md = tab_dir / "README.md"

    assert index_html.exists(), "tab_chat/index.html не существует"
    assert main_js.exists(), "tab_chat/main.js не существует"
    assert readme_md.exists(), "tab_chat/README.md не существует"


def test_tab_chat_html_structure_and_i18n() -> None:
    """Проверяет разметку tab_chat/index.html на соответствие стандартам WebGUI и i18n."""
    html_content = (_WEBGUI_DIR / "tab_chat" / "index.html").read_text(encoding="utf-8")

    # 1. Проверяем шапку и дату обновления
    assert "Updated: 2026-" in html_content, "Отсутствует метка времени Updated в index.html"

    # 2. Проверяем ключевые идентификаторы элементов управления
    assert 'id="tab-chat-container"' in html_content, "Контейнер #tab-chat-container не найден"
    assert 'id="ws-chat-response-window"' in html_content, "Окно сообщений не найдено"
    assert 'id="ws-chat-messages"' in html_content, "Контейнер сообщений #ws-chat-messages не найден"
    assert 'id="ws-chat-input"' in html_content, "Поле ввода #ws-chat-input не найдено"
    assert 'id="ws-chat-send-btn"' in html_content, "Кнопка отправки #ws-chat-send-btn не найдена"
    assert 'id="ws-chat-clear-btn"' in html_content, "Кнопка очистки #ws-chat-clear-btn не найдена"
    assert 'id="chat-active-ws-name"' in html_content, "Бейдж рабочей области не найден"

    # 3. Проверяем i18n атрибуты
    assert 'data-i18n="tabs.chat"' in html_content, "Локализация tabs.chat не найдена"
    assert 'data-i18n-placeholder="workspace.chatInputPlaceholder"' in html_content, "i18n placeholder не найден"


def test_tab_chat_main_js_logic_and_exports() -> None:
    """Проверяет логику контроллера tab_chat/main.js."""
    js_content = (_WEBGUI_DIR / "tab_chat" / "main.js").read_text(encoding="utf-8")

    # 1. Проверяем шапку
    assert "Updated: 2026-" in js_content, "Отсутствует метка Updated в main.js"

    # 2. Проверяем экспорты функций жизненного цикла
    assert "export function initChatTab(" in js_content, "Экспорт initChatTab не найден"
    assert "export function deactivateChatTab(" in js_content, "Экспорт deactivateChatTab не найден"
    assert "export async function sendChatMessage(" in js_content, "Экспорт sendChatMessage не найден"
    assert "export function clearChatHistory(" in js_content, "Экспорт clearChatHistory не найден"
    assert "export function resolveCurrentWorkspaceId(" in js_content, "Экспорт resolveCurrentWorkspaceId не найден"

    # 3. Регистрация в глобальном объекте window
    assert "window.initChatTab = initChatTab;" in js_content, "Регистрация window.initChatTab не найдена"

    # 4. Проверка обращения к контуру /api/v1/ask
    assert "/api/v1/ask" in js_content, "Вызов /api/v1/ask не найден"

    # 5. Подписка на глобальные события рабочей области
    assert "document.addEventListener('context:changed'" in js_content
    assert "document.addEventListener('workspace:changed'" in js_content

    # 6. Поддержка динамических контекстных вопросов
    assert "export async function loadDynamicQuickPrompts(" in js_content
    assert "window.loadDynamicQuickPrompts = loadDynamicQuickPrompts;" in js_content
    assert "/suggested-questions" in js_content

    # 7. Использование унифицированных стилей пузырей чата без жесткого bg-primary
    assert "chat-msg-user" in js_content
    assert "chat-msg-bot" in js_content
    assert "bg-primary text-white" not in js_content


def test_chat_user_bubble_color_hsl_216_100_91() -> None:
    """Проверяет, что фон пузыря сообщения в чате задан в формате hsl(216, 100%, 91%) и оба блока выравниваются по правому краю в RTL."""
    common_WEBGUI = Path(__file__).resolve().parent.parent.parent / "common" / "webgui"

    for css_dir in [_WEBGUI_DIR / "css", common_WEBGUI / "css"]:
        vars_css = (css_dir / "variables.css").read_text(encoding="utf-8")
        chat_css = (css_dir / "chat.css").read_text(encoding="utf-8")
        assert "hsl(216, 100%, 91%)" in vars_css, f"hsl(216, 100%, 91%) не найден в {css_dir / 'variables.css'}"
        assert "hsl(216, 100%, 91%)" in chat_css, f"hsl(216, 100%, 91%) не найден в {css_dir / 'chat.css'}"
        assert ".chat-msg-user" in chat_css
        assert ".chat-msg-bot" in chat_css
        assert "margin-left: auto !important" in chat_css
        assert "text-align: right !important" in chat_css


def test_index_html_registers_tab_chat() -> None:
    """Проверяет регистрацию вкладки tab-chat в главном index.html."""
    main_html = (_WEBGUI_DIR / "index.html").read_text(encoding="utf-8")

    # Activity Bar кнопка
    assert 'data-tab="tab-chat"' in main_html, "Кнопка с data-tab='tab-chat' не найдена в Activity Bar"
    assert 'id="ide-nav-chat"' in main_html, "Элемент #ide-nav-chat не найден в index.html"

    # Боковое меню Offcanvas
    assert 'id="drawer-nav-tab-chat"' in main_html, "Элемент #drawer-nav-tab-chat не найден в Drawer"

    # Контейнер содержимого вкладки в #mainTabContent
    assert 'id="tab-chat"' in main_html, "Контейнер #tab-chat не найден в #mainTabContent"


def test_js_main_registers_tab_chat() -> None:
    """Проверяет карту вкладок TABS в apps/ai_assistant/api/webgui/js/main.js."""
    js_main = (_WEBGUI_DIR / "js" / "main.js").read_text(encoding="utf-8")

    assert "'chat':" in js_main, "Запись 'chat' отсутствует в словаре TABS"
    assert "/html/tab_chat/index.html" in js_main, "Путь к tab_chat/index.html отсутствует в TABS"
    assert "/html/tab_chat/main.js" in js_main, "Путь к tab_chat/main.js отсутствует в TABS"


def test_ide_navigation_shortcut_for_chat() -> None:
    """Проверяет привязку горячей клавиши Alt+5 к tab-chat в ide_navigation.js."""
    nav_js = (_WEBGUI_DIR / "js" / "ide_navigation.js").read_text(encoding="utf-8")

    assert "'5': 'tab-chat'" in nav_js, "Сочетание Alt+5 не привязано к tab-chat в shortcutMap"


def test_tab_chat_i18n_keys_in_all_locales() -> None:
    """Проверяет наличие локализаций для вкладки chat во всех поддерживаемых языках."""
    for lang in ["ru", "en", "he", "uk"]:
        locale_path = _WEBGUI_DIR / "locales" / f"{lang}.json"
        assert locale_path.exists(), f"Файл локали {locale_path} не найден"

        data = json.loads(locale_path.read_text(encoding="utf-8"))

        assert "tabs" in data, f"Секция 'tabs' отсутствует в {lang}.json"
        assert "chat" in data["tabs"], f"Ключ 'chat' отсутствует в tabs в {lang}.json"
        assert len(data["tabs"]["chat"].strip()) > 0, f"Название вкладки chat пусто в {lang}.json"

        assert "titles" in data and "ide" in data["titles"], f"Секция titles.ide отсутствует в {lang}.json"
        assert "chat" in data["titles"]["ide"], f"Ключ 'chat' отсутствует в titles.ide в {lang}.json"


def test_tab_chat_send_event_bindings_and_isolation() -> None:
    """Проверяет привязку событий Enter и Click, а также изоляцию контейнеров."""
    html_content = (_WEBGUI_DIR / "tab_chat" / "index.html").read_text(encoding="utf-8")
    js_content = (_WEBGUI_DIR / "tab_chat" / "main.js").read_text(encoding="utf-8")

    # Проверяем обработчик Enter на textarea и клика на кнопке отправки
    assert 'sendChatMessage' in html_content, "Прямой вызов sendChatMessage отсутствует в HTML разметке tab_chat"
    assert 'export function getChatContainer(' in js_content, "Функция изоляции getChatContainer не найдена"
    assert 'container.querySelector(' in js_content, "Контекстный поиск внутри контейнера не используется"
    assert "e.key === 'Enter'" in js_content, "Обработка клавиши Enter отсутствует в main.js"


def test_tab_main_js_relative_imports_valid() -> None:
    """Проверяет отсутствие ошибочных относительных путей ../../js/ в корневых main.js вкладок."""
    for tab_main in _WEBGUI_DIR.glob("tab_*/main.js"):
        content = tab_main.read_text(encoding="utf-8")
        assert "../../js/" not in content, (
            f"Обнаружен некорректный относительный импорт '../../js/' в {tab_main.name} "
            "(должен быть '../js/', так как webgui монтируется в /html)"
        )


@pytest.mark.asyncio
async def test_workspace_suggested_questions_endpoint() -> None:
    """Проверяет эндпоинт /api/v1/workspaces/{workspace_id}/suggested-questions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/workspaces/default/suggested-questions?language=he")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["language"] == "he"
        assert "prompts" in data
        assert isinstance(data["prompts"], list)
        assert len(data["prompts"]) > 0


def test_chat_task_button_layout_below_larger_input_and_rtl_i18n() -> None:
    """Проверяет наличие кнопки משימה (Задача), увеличенное поле ввода, расположение кнопок СНИЗУ поля ввода и выравнивание вправо в RTL."""
    common_webgui = Path(__file__).resolve().parent.parent.parent / "common" / "webgui"

    for rel_html, task_btn_id in [("tab_chat/index.html", "chat-add-task-btn"), ("tab_workspace/index.html", "ws-chat-add-task-btn")]:
        html = (_WEBGUI_DIR / rel_html).read_text(encoding="utf-8")
        assert f'id="{task_btn_id}"' in html, f"Кнопка задачи #{task_btn_id} не найдена в {rel_html}"
        assert 'data-i18n="workspace.chatAddTaskBtn"' in html
        assert 'data-i18n-title="workspace.chatAddTaskTitle"' in html
        assert 'rows="4"' in html, f"Поле ввода чата в {rel_html} должно иметь rows='4'"

        # Кнопки должны располагаться строго ПОСЛЕ (снизу) поля ввода #ws-chat-input
        idx_input = html.index('id="ws-chat-input"')
        idx_actions = html.index('id="ws-chat-actions-row"')
        idx_task_btn = html.index(f'id="{task_btn_id}"')
        assert idx_input < idx_actions < idx_task_btn, f"Кнопки в {rel_html} должны находиться снизу (после) поля ввода"

    # Проверяем локализацию бейджей и кнопки משימה во всех 4 языках обоих слоёв WebGUI
    for locales_dir in [_WEBGUI_DIR / "locales", common_webgui / "locales"]:
        he_data = json.loads((locales_dir / "he.json").read_text(encoding="utf-8"))
        assert he_data["workspace"]["chatAddTaskBtn"] == "משימה"
        for lang in ("ru", "en", "he", "uk"):
            loc = json.loads((locales_dir / f"{lang}.json").read_text(encoding="utf-8"))
            ws = loc["workspace"]
            for key in ("chatAddTaskBtn", "chatAddTaskTitle", "chatSendTitle", "chatRagBadge", "chatSourcesBadge"):
                assert key in ws and ws[key].strip(), f"Ключ workspace.{key} отсутствует или пуст в {locales_dir / f'{lang}.json'}"

    # Проверяем CSS для увеличенного поля ввода и выравнивания кнопок вправо в RTL
    for css_dir in [_WEBGUI_DIR / "css", common_webgui / "css"]:
        chat_css = (css_dir / "chat.css").read_text(encoding="utf-8")
        assert "flex-direction: column" in chat_css
        assert "min-height: 104px" in chat_css
        assert '[dir="rtl"] .chat-input-actions' in chat_css


@pytest.mark.asyncio
async def test_add_task_from_chat_veterinarian_and_insurer_remembers_time(tmp_path: Path) -> None:
    """Проверяет постановку задачи из чата: связь с ветеринаром и страховщиком с учётом времени осмотра 20.11 в 06:00."""
    from unittest.mock import patch
    from apps.ai_assistant.core.workspace_manager import WorkspaceManager

    wm = WorkspaceManager(
        base_dir=tmp_path / "base_data",
        workspaces_dir=tmp_path / "workspaces",
    )
    wm.create_or_select_workspace("דוד_משה", name="דוד משה", language="he")

    with patch("apps.ai_assistant.api.routers.router_knowledge._workspace_manager", wm):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/workspaces/דוד_משה/tasks",
                json={
                    "task_text": "Связаться с ветеринаром и страховым агентом, согласовать с ними дату",
                    "language": "ru",
                },
            )
            assert res.status_code == 200
            body = res.json()
            assert body["status"] == "ok"
            assert body["is_inspection_coordination"] is True
            assert body["scheduled_time"] == "2026-11-20T06:00:00+02:00"
            assert "06:00" in body["summary_markdown"]
            assert "20.11.2026" in body["summary_markdown"]
            assert "veterinarian@davidka.net" in body["summary_markdown"]
            assert "attorney@davidka.net" in body["summary_markdown"]



