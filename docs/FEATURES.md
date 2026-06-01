# Features

Каталог реализованных функций проекта и файлов, которые за них отвечают.

## Telegram Polling Bot

Описание: бот запускается через aiogram polling и получает updates напрямую через Telegram Bot API.

Основные файлы:

- `app/main.py`
- `app/handlers/__init__.py`

## Локальная Тестовая Среда

Описание: отдельный локальный контур для разработки с тестовым Telegram bot token, тем же OpenAI API key и отдельной SQLite базой.

Основные файлы:

- `app/config.py`
- `app/db.py`
- `start_local.sh`
- `stop_local.sh`
- `status_local.sh`
- `.env.example`
- `.gitignore`

Ключевые элементы:

- `ENV_FILE=.env.local`;
- `APP_ENV=local`;
- `DATABASE_URL=sqlite+aiosqlite:///./bot_local_test.db`;
- PID-файл `data/local_bot.pid`;
- логи `logs/local.out.log` и `logs/local.err.log`;
- защита от запуска production token локально.

## Модульные Handlers

Описание: Telegram orchestration разделен по областям, вместо одного большого `handlers.py`.

Основные файлы:

- `app/handlers/__init__.py`
- `app/handlers/start.py`
- `app/handlers/help.py`
- `app/handlers/profile.py`
- `app/handlers/history.py`
- `app/handlers/voice.py`
- `app/handlers/callbacks.py`
- `app/handlers/menu.py`
- `app/handlers/settings.py`
- `app/handlers/admin.py`
- `app/handlers/system.py`
- `app/handlers/fallbacks.py`
- `app/handlers/keyboards.py`
- `app/handlers/utils.py`

Ключевые функции:

- aggregate `router`
- `handle_voice()`
- `fresh_note_callback()`
- `history_note_callback()`
- `reply_keyboard_handler()`

## Onboarding `/start`

Описание: приветственное сообщение, краткое объяснение возможностей и Reply Keyboard.

Основные файлы:

- `app/handlers/start.py`
- `app/handlers/keyboards.py`

Ключевые функции:

- `start()`
- `main_keyboard()`

## Reply Keyboard

Описание: постоянное нижнее меню Telegram.

Кнопки:

- `🎙 Новое голосовое`
- `👤 Профиль`
- `📚 История`
- `⚙️ Настройки`
- `❓ Помощь`

Основные файлы:

- `app/handlers/menu.py`
- `app/handlers/keyboards.py`
- `app/handlers/constants.py`

Ключевые функции:

- `main_keyboard()`
- `reply_keyboard_handler()`

## Прием Voice Messages

Описание: бот принимает только обычные Telegram voice messages.

Основные файлы:

- `app/handlers/voice.py`
- `app/handlers/utils.py`
- `app/access_service.py`
- `app/access.py`
- `app/openai_service.py`
- `app/models.py`

Ключевые функции:

- `handle_voice()`
- `download_voice()`
- `convert_to_mp3()`
- `check_user_access()`
- `OpenAIService.transcribe()`
- `OpenAIService.analyze()`

## Быстрый Статус Обработки

Описание: после получения voice бот сразу отправляет статус и редактирует одно сообщение по этапам.

Основные файлы:

- `app/handlers/voice.py`
- `app/handlers/utils.py`

Ключевые функции:

- `handle_voice()`
- `safe_edit()`

## OpenAI Transcription

Описание: MP3 после ffmpeg отправляется в OpenAI Audio Transcriptions.

Основные файлы:

- `app/openai_service.py`
- `app/tasks.py`
- `app/handlers/voice.py`

Ключевые функции:

- `OpenAIService.transcribe()`

## OpenAI Summary, Details, Tasks

Описание: transcript анализируется OpenAI Responses API, ожидается JSON.

Основные файлы:

- `app/openai_service.py`

Ключевые функции:

- `OpenAIService.analyze()`
- `_extract_json()`
- `_as_string_list()`
- `normalize_tasks()`

## Приоритетные Задачи

Описание: задачи с явным акцентом пользователя получают `priority=true`, выводятся первыми, жирным и с `❗`.

Основные файлы:

- `app/openai_service.py`
- `app/tasks.py`
- `app/formatters.py`
- `app/models.py`

Ключевые функции:

- `OpenAIService.analyze()`
- `normalize_tasks()`
- `serialize_tasks()`
- `parse_stored_tasks()`
- `sort_tasks_for_display()`
- `format_numbered_list()`

## Компактный Ответ

Описание: по умолчанию после voice отправляется краткое summary и задачи; полный текст доступен кнопкой.

Основные файлы:

- `app/handlers/voice.py`
- `app/formatters.py`
- `app/preferences.py`
- `.env.example`

Ключевые функции:

- `format_response()`
- `format_short()`
- `get_response_mode()`

## Inline-Кнопки Свежего Результата

Описание: кнопки под только что обработанным voice читают кэш из SQLite и защищены от дублей.

Callback data:

- `fresh_full_text:<id>`
- `fresh_tasks:<id>`
- `fresh_details:<id>`
- `fresh_share:<id>`

Основные файлы:

- `app/handlers/callbacks.py`
- `app/handlers/keyboards.py`
- `app/formatters.py`
- `app/models.py`

Ключевые функции:

- `fresh_note_callback()`
- `note_keyboard(source="fresh")`

## История Обработок

Описание: `/history` показывает последние 5 обработанных voice и позволяет открыть запись.

Основные файлы:

- `app/handlers/history.py`
- `app/handlers/keyboards.py`
- `app/models.py`

Ключевые функции:

- `history_command()`
- `_send_history()`
- `format_history()`
- `history_keyboard()`
- `history_callback()`
- `format_history_item()`

## Inline-Кнопки Истории

Описание: кнопки внутри записи из истории заново отправляют блок из SQLite и не применяют fresh-защиту от дублей.

Callback data:

- `history_full_text:<id>`
- `history_tasks:<id>`
- `history_details:<id>`
- `history_share:<id>`

Основные файлы:

- `app/handlers/callbacks.py`
- `app/handlers/keyboards.py`
- `app/formatters.py`
- `app/models.py`

Ключевые функции:

- `history_note_callback()`
- `note_keyboard(source="history")`

## Поделиться

Описание: отправляет отдельный блок, удобный для ручной пересылки.

Основные файлы:

- `app/handlers/callbacks.py`
- `app/formatters.py`

Ключевые функции:

- `format_share()`
- `fresh_note_callback()`
- `history_note_callback()`

## Настройки Ответа `/settings`

Описание: пользователь выбирает `short`, `full`, `tasks`.

Основные файлы:

- `app/handlers/settings.py`
- `app/handlers/keyboards.py`
- `app/formatters.py`
- `app/preferences.py`
- `app/models.py`

Ключевые функции:

- `settings_command()`
- `settings_callback()`
- `settings_keyboard()`
- `format_settings()`
- `get_response_mode()`
- `set_response_mode()`

## Профиль `/profile` и Telegram ID `/my_id`

Описание: `/profile` показывает имя, username, тариф, дневные и минутные лимиты, trial days, reset date. `/my_id` показывает Telegram ID пользователя, чтобы он мог отправить его Тоше для ручного добавления в тариф.

Основные файлы:

- `app/handlers/profile.py`
- `app/formatters.py`
- `app/access_service.py`
- `app/access.py`
- `app/tariffs.py`
- `app/models.py`

Ключевые функции:

- `profile()`
- `my_id()`
- `build_profile_text()`
- `format_profile()`
- `format_my_id()`
- `check_user_access()`

## Тарифы

Описание: Owner, По-братски от Тоши, Free, Standard, Premium.

Основные файлы:

- `app/tariffs.py`
- `app/access_service.py`
- `app/access.py`
- `app/models.py`
- `app/config.py`

Ключевые функции:

- `get_tariff()`
- `check_user_access()`
- `is_owner()`
- `_resolve_tariff_type()`
- `_apply_plan_limits()`

## Проверка Лимитов

Описание: лимит проверяется перед скачиванием аудио и OpenAI.

Основные файлы:

- `app/access.py`
- `app/access_service.py`
- `app/handlers/voice.py`
- `app/handlers/menu.py`

Ключевые функции:

- `check_user_access()`
- `check_voice_access()`
- `get_access_status()`
- `_get_static_denial_reason()`
- `_billable_minutes()`

## Списание Использования

Описание: после успешной обработки записывает voice count и минуты.

Основные файлы:

- `app/access.py`
- `app/models.py`

Ключевые функции:

- `record_voice_usage()`

Примечание: старый `DailyUsage`/`app/limits.py` оставлен как legacy compatibility layer, но активное списание идет через `UserSettings`.

## Owner и Друзья

Описание: owner без ограничений, friends получают тариф `По-братски от Тоши`.

Основные файлы:

- `app/config.py`
- `app/access.py`
- `app/handlers/admin.py`

Ключевые функции:

- `is_owner()`
- `add_unlimited_user()`
- `admin_add_unlimited()`

## Локальная Аналитика

Описание: события использования пишутся в SQLite и доступны владельцу через admin stats.

События:

- `user_started`
- `voice_received`
- `voice_limit_blocked`
- `voice_processing_started`
- `voice_transcribed`
- `voice_processed_success`
- `voice_processing_failed`
- `history_opened`
- `history_item_opened`
- `profile_opened`
- `settings_opened`
- `share_clicked`
- `paywall_shown`

Основные файлы:

- `app/analytics_service.py`
- `app/models.py`
- `app/handlers/admin.py`
- `app/handlers/voice.py`
- `app/handlers/callbacks.py`
- `app/handlers/history.py`
- `app/handlers/profile.py`
- `app/handlers/settings.py`
- `app/handlers/menu.py`
- `app/handlers/start.py`

Ключевые функции:

- `track_event()`
- `get_admin_stats()`
- `get_stats_for_period()`
- `format_admin_stats()`

## Admin Stats

Описание: owner-only статистика за сегодня, 7 дней или 30 дней.

Команды:

- `/admin_stats`
- `/admin_stats_today`
- `/admin_stats_7d`
- `/admin_stats_30d`
- `/admin_cleanup_analytics`

Основные файлы:

- `app/handlers/admin.py`
- `app/analytics_service.py`

Метрики:

- новые и активные пользователи;
- пользователи с голосовыми;
- полученные и успешно обработанные voice;
- ошибки и блокировки лимитом;
- минуты аудио с одной цифрой после запятой;
- среднее время обработки;
- открытия истории/профиля;
- share clicks и paywall views;
- конверсии на русском: активация новых, голосовые от активных, успешная обработка, блокировки лимитом, доля “Поделиться”;
- причины ошибок по `error_type`;
- причины блокировок по `reason`.

## Health Check

Описание: `/health` проверяет bot, SQLite, ffmpeg, OPENAI_API_KEY без дорогого OpenAI-запроса.

Основные файлы:

- `app/handlers/system.py`
- `app/handlers/utils.py`

Ключевые функции:

- `health()`
- `_check_database()`
- `_check_ffmpeg()`

## Unsupported Messages

Описание: текст, фото, документы, видео, кружки и audio files не отправляются в OpenAI.

Основные файлы:

- `app/handlers/fallbacks.py`

Ключевые функции:

- `text_fallback()`
- `unsupported_media()`
- `fallback()`

## SQLite Schema Compatibility

Описание: простые ALTER TABLE обновления для локальной SQLite базы.

Основные файлы:

- `app/db.py`
- `app/models.py`
- `docs/DATABASE_MIGRATIONS.md`

Ключевые функции:

- `_ensure_sqlite_schema_updates()`
- `_add_text_column()`
- `_add_integer_column()`

## Подготовка К Alembic

Описание: полноценный Alembic пока не внедрен, но текущая схема и ручные миграции зафиксированы для будущего перехода.

Основные файлы:

- `docs/DATABASE_MIGRATIONS.md`
- `app/db.py`
- `app/models.py`

Ключевые решения:

- `Base.metadata.create_all()` остается текущим механизмом;
- ручные `ALTER TABLE` остаются в `_ensure_sqlite_schema_updates()`;
- `daily_usage` помечен как legacy и может быть удален только отдельной миграцией.

## Очистка Истории

Описание: прошлые обработки очищаются удалением строк из `voice_notes`; пользователи, тарифы, лимиты и настройки сохраняются.

Основные файлы:

- `app/models.py`
- `app/db.py`

Runtime:

- `data/bot.db`

Проверка:

- `/history` должен показывать `История пока пуста. Отправьте первое голосовое сообщение.`

## Централизованное Форматирование

Описание: summary, tasks, profile, history, share, settings и help форматируются в одном модуле.

Основные файлы:

- `app/formatters.py`
- `app/handlers/`

Ключевые функции:

- `format_response()`
- `format_tasks()`
- `format_history()`
- `format_history_item()`
- `format_profile()`
- `format_share()`

## Нормализация Задач

Описание: единое внутреннее представление задач `{text, priority}` для новых и старых записей.

Основные файлы:

- `app/tasks.py`
- `app/openai_service.py`
- `app/formatters.py`
- `app/handlers/voice.py`
- `app/handlers/callbacks.py`

Ключевые функции:

- `normalize_tasks()`
- `serialize_tasks()`
- `parse_stored_tasks()`
- `sort_tasks_for_display()`

## Минимальные Тесты

Описание: unit-тесты без OpenAI-запросов.

Основные файлы:

- `tests/test_access_service.py`
- `tests/test_tasks.py`
- `tests/test_history.py`

Команда:

```bash
.venv/bin/python -m unittest discover -s tests
```

## Local Run Scripts

Описание: shell-скрипты для запуска, остановки и статуса.

Основные файлы:

- `start.sh`
- `stop.sh`
- `status.sh`
- `scripts/run_bot.command`

## Docker Run

Описание: контейнерный запуск с ffmpeg и volume для SQLite.

Основные файлы:

- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
