# Навык `paperless-ngx`

Навык для управления интеграцией **AI-Assistant** с локальной системой электронного документооборота **Paperless-ngx**.

## Возможности

- Проверка соединения (`ping`) и текущей конфигурации (`config.json` + `.env`).
- Просмотр списка документов в Paperless-ngx (общий и по тегу рабочей области).
- Инкрементальная загрузка недостающих поддерживаемых файлов (PDF, изображения, офисные документы) из любой рабочей области `data/workspaces/<ws_id>` в Paperless-ngx без дублирования.
- Конвертация файлов любых поддерживаемых форматов (`.pdf`, `.docx`, `.doc`, `.odt`, `.rtf`, `.xlsx`, `.xls`, `.ods`, `.csv`, `.tsv`, `.pptx`, `.ppt`, `.txt`, `.html`, `.png`, `.jpg`, `.tiff`, `.bmp`, `.webp`) в Markdown (`.md`) через встроенный OCR/Tika Paperless-ngx (`convert` и `export-md`).

## Структура

```text
.agents/skills/paperless-ngx/
├── SKILL.md                  # Манифест и инструкции для агента
├── README.md                 # Документация навыка
└── scripts/
    └── paperless_tool.py     # CLI-инструмент (использует PaperlessConnector и WorkspaceManager)
```

## Примеры запуска

```powershell
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py status
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py list --workspace דוד_משה
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py sync-workspace דוד_משה
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py convert C:\path\to\file.docx --in-place
.\venv\Scripts\python.exe .agents/skills/paperless-ngx/scripts/paperless_tool.py export-md 19
```
