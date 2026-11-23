# Универсальный файловый редактор WYSIWYG (Rust + WebAssembly)

<!--
Updated: 2026-11-15 21:25:30
Author: hypo69
-->

## Описание
Универсальный переиспользуемый компонент файлового редактора с поддержкой визуального режима (WYSIWYG), разделенного просмотра (Split Preview) и режима исходного текста (Raw Code) для текстовых и Markdown файлов, работающий на базе высокоскоростного ядра Rust + WebAssembly.

## Возможности
- **Режимы отображения:**
  - `WYSIWYG`: Полноценное интерактивное визуальное редактирование контента.
  - `Split`: Синхронный разделенный экран (исходный текст слева, визуальный результат справа).
  - `Raw`: Режим редактирования чистого исходного текста/разметки.
- **Ядро Rust + WebAssembly:**
  - Мгновенный парсинг Markdown в HTML в линейной памяти.
  - Высокоскоростной подсчет статистики документа (строки, слова, символы, время чтения).
  - Извлечение структуры заголовков и оглавления (TOC).
  - Расчет FNV-1a хеша буфера для детекции изменений.
  - Прозрачный клиентский fallback при отсутствии предкомпилированного `.wasm`.
- **Интерфейс и локализация:**
  - Строгая поддержка i18n через SSR-токены `{{key}}` без жестко закодированных строк.
  - Оформление строго на системных CSS-переменных темы без хардкода цветов (HEX/RGB).

## Структура файлов
- [`editor_files.html`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/editor_files.html): Шаблон разметки со строгим соблюдением токенизации i18n (`{{key}}`).
- [`style.css`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/style.css): Стили компонента на базе CSS-переменных дизайн-системы (`var(--surface-*)`, `var(--accent-*)`).
- [`editor_files.js`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/editor_files.js): JavaScript-контроллер компонента, управление режимами и синхронизация буферов.
- [`wasm_bridge.js`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/wasm_bridge.js): Клиентский мост к WebAssembly с автоматическим fallback-движком.
- [`Cargo.toml`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/Cargo.toml): Манифест сборки Rust крейта в WebAssembly (`wasm32-unknown-unknown`).
- [`src/lib.rs`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/src/lib.rs): Точка входа ядра WebAssembly (экспорт FNV-1a, Markdown парсера, статистики, TOC).
- [`src/markdown_parser.rs`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/src/markdown_parser.rs): Высокоскоростной парсер Markdown и извлечение оглавления документов.
- [`src/stats.rs`](file:///c:/Users/onela/AppData/Local/AI-Assistant/apps/common/webgui/components/editor-files/src/stats.rs): Модуль анализа метрик документа.

## Сборка ядра Rust WebAssembly
Для сборки бинарного `.wasm` модуля (при установленном Rust и утилите `wasm-pack`):
```powershell
cd apps/common/webgui/components/editor-files
wasm-pack build --target web --release
```

## Использование компонента в WebGUI
```javascript
import { EditorFilesComponent } from '/static/common/components/editor-files/editor_files.js';

const container = document.getElementById('my-editor-container');
const editor = new EditorFilesComponent(container, {
  initialContent: '# Заголовок документа\n\nТекст...',
  mode: 'wysiwyg',
  onSave: (content) => {
    console.log('Сохранено:', content);
  }
});

await editor.init();
```
