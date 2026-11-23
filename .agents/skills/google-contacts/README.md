# Навык: Google Contacts (People API)

Автономный навык для управления контактами и телефонной книгой Google через Google People API v1.

## Возможности
- Поиск и получение списка контактов по имени, email, номеру телефона и организации.
- Просмотр карточек контактов (телефоны, email, адреса, должности, заметки).
- Создание новых контактов в адресной книге Google.
- Редактирование и удаление контактов по идентификатору `resourceName`.
- **Экспорт контактов** в форматы CSV (UTF-8 BOM для Excel) и JSON.
- **Импорт контактов** из CSV и JSON файлов с поддержкой симуляции `--dry-run`.
- Форматированный JSON-вывод для агентных пайплайнов и вызова инструментов.

## Быстрый старт
```bash
# Список контактов
python scripts/list_contacts.py -n 20 --json

# Поиск контакта
python scripts/list_contacts.py -q "דוד" --json

# Создание контакта
python scripts/create_contact.py -n "Алексей" -p "+972501234567" -e "alex@example.com" --json

# Экспорт контактов в assets/contacts.csv
python scripts/export_contacts.py

# Импорт контактов из assets/contacts.csv с предварительной проверкой (dry-run)
python scripts/import_contacts.py -i "../../assets/contacts.csv" --dry-run --json
```
