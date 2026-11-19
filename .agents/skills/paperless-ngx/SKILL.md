---
name: paperless-ngx
description: Paperless-ngx DMS integration toolkit for converting diverse formats (PDF, DOCX, XLSX, PPTX, ODT, images, HTML, TXT) to Markdown via Paperless-ngx OCR/Tika, checking server status, listing documents, and syncing missing workspace files without duplicates.
description_i18n:
  en: Paperless-ngx DMS integration toolkit for converting diverse formats (PDF, DOCX, XLSX, PPTX, ODT, images, HTML, TXT) to Markdown via Paperless-ngx OCR/Tika, checking server status, listing documents, and syncing missing workspace files without duplicates.
  ru: Инструментарий интеграции с Paperless-ngx DMS: конвертация различных форматов (PDF, DOCX, XLSX, PPTX, ODT, изображения, HTML, TXT) в Markdown через встроенный OCR/Tika Paperless-ngx, проверка статуса сервера, просмотр документов и синхронизация рабочих областей без дубликатов.
---

# 📄 Paperless-ngx Integration Skill

Навык для диагностики, просмотра и синхронизации документов между рабочими областями `AI-Assistant` и локальным сервером **Paperless-ngx**.

---

## 🎯 Назначение и триггеры активации

Используйте этот навык, когда требуется:
- проверить доступность Paperless-ngx (`ping`), порт в `config.json` и валидность `PAPERLESS_API_TOKEN` в `.env`;
- получить список документов или тегов в Paperless-ngx;
- загрузить недостающие PDF/изображения/офисные файлы из рабочей области (`data/workspaces/<ws_id>`) в Paperless-ngx без создания дубликатов.

---

## ⚙️ Конфигурация

- **Адрес и таймауты:** секция `paperless` в корневом `config.json` (`base_url`, `api_version`, таймауты). Переменная `PAPERLESS_BASE_URL` в `.env` имеет приоритет.
- **Секреты (`.env`):**
  - `PAPERLESS_API_TOKEN` — API-токен для REST-запросов.
  - `PAPERLESS_ADMIN_USER` / `PAPERLESS_ADMIN_PASSWORD` — учётные данные веб-интерфейса (значения со спецсимволом `#` обязательно заключать в одинарные кавычки).

---

## 🛠️ CLI-утилита (`scripts/paperless_tool.py`)

Все команды используют штатный `PaperlessConnector.from_config()` и `WorkspaceManager` проекта.

### 1. Проверка статуса сервера
```powershell
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py status
```

### 2. Список документов в Paperless-ngx
```powershell
# Все документы
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py list

# Документы конкретной рабочей области (по тегу)
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py list --workspace דוד_משה
```

### 3. Загрузка недостающих файлов рабочей области
```powershell
# Предварительный просмотр (без загрузки)
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py sync-workspace דוד_משה --dry-run

# Загрузка всех недостающих PDF и поддерживаемых файлов
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py sync-workspace דוד_משה
```

### 4. Конвертация любого поддерживаемого формата в Markdown (`.md`)
Поддерживаются форматы Paperless-ngx: `.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, `.xls`, `.ods`, `.csv`, `.tsv`, `.pptx`, `.ppt`, `.txt`, `.html`, `.xhtml`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp`.

```powershell
# Конвертировать файл и вывести Markdown в консоль
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py convert C:\path\to\file.docx --workspace דוד_משה

# Конвертировать файл и сохранить рядом как <stem>.md
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py convert C:\path\to\scan.png --workspace דוד_משה --in-place

# Конвертировать и сохранить в указанный .md файл
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py convert C:\path\to\report.xlsx --output C:\path\to\report.md

# Экспортировать в Markdown уже загруженный документ по его Paperless ID
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py export-md 19 --output C:\path\to\doc_19.md
```

---

## 📋 Протокол работы

1. Перед загрузкой выполните `status` и убедитесь, что `ping: True`. Если `ping: False` — проверьте совпадение порта в `config.json` (`paperless.base_url`) и наличие `PAPERLESS_API_TOKEN` в `.env`.
2. Выполните `sync-workspace <ws_id> --dry-run` (при необходимости) или сразу `sync-workspace <ws_id>` — скрипт автоматически пропустит файлы, которые уже присутствуют в Paperless-ngx (сравнение по `title` / `original_file_name`).
3. После загрузки проверьте результат через `list --workspace <ws_id>` или в веб-интерфейсе `http://127.0.0.1:8000/documents`.
