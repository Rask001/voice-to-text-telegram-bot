# Database Migrations

Статус: подготовка к будущему Alembic без внедрения Alembic в текущем этапе.

Проект сейчас использует SQLite + SQLAlchemy. Таблицы создаются через `Base.metadata.create_all()`, а совместимость старых локальных баз поддерживается простыми `ALTER TABLE` в `app/db.py`.

## Текущие Таблицы

### `voice_notes`

Хранит историю обработанных голосовых и кэш результата для inline-кнопок.

Поля:

- `id INTEGER PRIMARY KEY`
- `telegram_user_id BIGINT`
- `telegram_file_id VARCHAR(255)`
- `duration_seconds INTEGER`
- `transcript TEXT`
- `summary TEXT`
- `action_items TEXT`
- `created_at DATETIME DEFAULT CURRENT_TIMESTAMP`
- `important_points TEXT DEFAULT ''`
- `details TEXT DEFAULT ''`
- `full_text_message_ids TEXT DEFAULT ''`
- `details_message_ids TEXT DEFAULT ''`
- `tasks_message_ids TEXT DEFAULT ''`
- `title VARCHAR(120) DEFAULT ''`
- `share_message_ids TEXT DEFAULT ''`
- `result_message_id INTEGER`

Примечание: `action_items` для новых записей хранит JSON-массив задач `{text, priority}`. Старые записи могут хранить строки через переносы.

### `user_settings`

Хранит пользовательские настройки, тарифы и актуальные лимитные счетчики.

Поля:

- `id INTEGER PRIMARY KEY`
- `telegram_user_id BIGINT UNIQUE`
- `response_mode VARCHAR(20)`
- `is_unlimited BOOLEAN DEFAULT 0`
- `is_premium BOOLEAN DEFAULT 0`
- `tariff_type VARCHAR(30) DEFAULT 'free'`
- `registration_date DATETIME`
- `trial_expires_at DATETIME`
- `minutes_used_total INTEGER DEFAULT 0`
- `minutes_limit_total INTEGER DEFAULT 15`
- `minutes_used_this_month INTEGER DEFAULT 0`
- `minutes_limit_month INTEGER DEFAULT 15`
- `voices_used_today INTEGER DEFAULT 0`
- `daily_voice_limit INTEGER DEFAULT 3`
- `usage_date DATE`
- `minutes_month_key VARCHAR(7) DEFAULT ''`

### `daily_usage`

Legacy таблица старого дневного счетчика.

Поля:

- `id INTEGER PRIMARY KEY`
- `telegram_user_id BIGINT`
- `usage_date DATE`
- `voice_count INTEGER`

Статус: не участвует в актуальной проверке лимитов. Актуальная система использует `user_settings.voices_used_today`, `usage_date`, `minutes_used_this_month`, `minutes_used_total`. Таблица оставлена для совместимости старых баз до отдельной миграции удаления.

### `analytics_events`

Хранит локальные события использования бота для owner-only статистики.

Поля:

- `id INTEGER PRIMARY KEY`
- `event_name VARCHAR(80)`
- `telegram_id BIGINT`
- `tariff_type VARCHAR(30) DEFAULT ''`
- `payload_json TEXT DEFAULT ''`
- `created_at DATETIME DEFAULT CURRENT_TIMESTAMP`

Примечание: `payload_json` хранит только служебные поля вроде `duration_seconds`, `error_type`, `transcription_id`, `remaining_minutes`, `remaining_daily_messages`, `reason`, `source`, `processing_time_seconds`. Полные расшифровки, summary, задачи и секреты не сохраняются.

### `reminders`

Хранит ручные и будущие task/history/AI напоминания.

Поля:

- `id INTEGER PRIMARY KEY`
- `telegram_id BIGINT`
- `transcription_id INTEGER NULL`
- `task_text TEXT`
- `source_text TEXT NULL`
- `remind_at DATETIME`
- `timezone VARCHAR(64) DEFAULT 'Europe/Moscow'`
- `status VARCHAR(20) DEFAULT 'pending'`
- `created_at DATETIME DEFAULT CURRENT_TIMESTAMP`
- `sent_at DATETIME NULL`
- `completed_at DATETIME NULL`
- `cancelled_at DATETIME NULL`
- `updated_at DATETIME NULL`

Статусы:

- `pending`
- `sending`
- `sent`
- `completed`
- `cancelled`
- `failed`

## Ручные ALTER TABLE, Которые Уже Поддерживаются

Файл: `app/db.py`, функция `_ensure_sqlite_schema_updates()`.

Для `voice_notes`:

- `ADD COLUMN title VARCHAR(120) DEFAULT ''`
- `ADD COLUMN important_points TEXT DEFAULT ''`
- `ADD COLUMN details TEXT DEFAULT ''`
- `ADD COLUMN full_text_message_ids TEXT DEFAULT ''`
- `ADD COLUMN details_message_ids TEXT DEFAULT ''`
- `ADD COLUMN tasks_message_ids TEXT DEFAULT ''`
- `ADD COLUMN share_message_ids TEXT DEFAULT ''`
- `ADD COLUMN result_message_id INTEGER`

Для `user_settings`:

- `ADD COLUMN is_unlimited BOOLEAN DEFAULT 0`
- `ADD COLUMN is_premium BOOLEAN DEFAULT 0`
- `ADD COLUMN tariff_type VARCHAR(30) DEFAULT 'free'`
- `ADD COLUMN registration_date DATETIME`
- `ADD COLUMN trial_expires_at DATETIME`
- `ADD COLUMN minutes_used_total INTEGER DEFAULT 0`
- `ADD COLUMN minutes_limit_total INTEGER DEFAULT 15`
- `ADD COLUMN minutes_used_this_month INTEGER DEFAULT 0`
- `ADD COLUMN minutes_limit_month INTEGER DEFAULT 15`
- `ADD COLUMN voices_used_today INTEGER DEFAULT 0`
- `ADD COLUMN daily_voice_limit INTEGER DEFAULT 3`
- `ADD COLUMN usage_date DATE`
- `ADD COLUMN minutes_month_key VARCHAR(7) DEFAULT ''`

Для `analytics_events`:

- `ADD COLUMN payload_json TEXT DEFAULT ''`
- `ADD COLUMN tariff_type VARCHAR(30) DEFAULT ''`

Для `reminders` ручных `ALTER TABLE` пока нет: таблица создается через `Base.metadata.create_all()` как новая таблица.

## Очистка Пользовательской Истории

Для полной очистки прошлых обработок удаляются только строки из:

- `voice_notes`

Не удаляются:

- `user_settings`
- `daily_usage`
- `analytics_events`
- `reminders`
- структура таблиц
- `.env`
- тарифы
- настройки пользователей

После очистки `/history` должен показывать:

```text
История пока пуста. Отправьте первое голосовое сообщение.
```

## Очистка Аналитики

Аналитика не очищается автоматически. Owner может удалить события старше 90 дней командой:

```text
/admin_cleanup_analytics
```

Команда требует подтверждения. Для серверного деплоя можно добавить cron/job, который периодически удаляет старые строки из `analytics_events`.

## Что Потребует Alembic Позже

Alembic стоит подключать, когда появится хотя бы один из сценариев:

- продакшен-деплой с несколькими окружениями;
- PostgreSQL или другая серверная БД;
- платежи Telegram Stars и таблицы транзакций/подписок;
- необходимость удалить legacy `daily_usage`;
- переименование колонок;
- изменение типов колонок;
- добавление индексов/unique constraints задним числом;
- backfill данных между версиями схемы.

## Потенциальные Будущие Миграции

1. Создать таблицы платежей:
   - `payments`
   - `subscriptions`
   - `telegram_star_transactions`

2. Удалить legacy `daily_usage` после проверки, что больше нет старого кода и отчетов, которые его читают.

3. Разнести `VoiceNote.action_items` в отдельную таблицу `voice_note_tasks`, если понадобятся поиск, фильтры, статусы выполнения задач.

4. Добавить отдельную таблицу связей задач и напоминаний, если понадобится несколько напоминаний на одну задачу.

5. Добавить индексы:
   - `voice_notes(telegram_user_id, created_at)`
   - `user_settings(tariff_type)`
   - `reminders(telegram_id, status, remind_at)`

6. Перейти с SQLite на PostgreSQL для серверного деплоя с большим числом пользователей.

## Рекомендованный Путь Внедрения Alembic

1. Добавить `alembic` в `requirements.txt`.
2. Выполнить `alembic init migrations`.
3. Настроить `env.py`, чтобы он импортировал `Base.metadata` из `app/db.py` и модели из `app/models.py`.
4. Создать baseline migration текущей схемы.
5. Отдельной миграцией описать удаление `daily_usage`, если будет принято решение удалить таблицу.
6. После Alembic убрать или ограничить `_ensure_sqlite_schema_updates()`.

Пока этот проект остается MVP на SQLite, текущий ручной механизм достаточно прост и прозрачен.
