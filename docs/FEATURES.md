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

Основная панель:

```text
🎙 Голосовое | 🔔 Напомни
👤 Профиль  | 📚 История
⚙️ Настройки | ❓ Помощь
```

Вложенное меню напоминаний:

```text
➕ Создать | 📋 Текущие
⬅️ Назад
```

Старые тексты `🎙 Новое голосовое`, `🔔` и `🔔 Напоминания` продолжают обрабатываться.

Основные файлы:

- `app/handlers/menu.py`
- `app/handlers/keyboards.py`
- `app/handlers/constants.py`

Ключевые функции:

- `main_keyboard()`
- `reminders_menu_keyboard()`
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

## Напоминания

Описание: отдельная подсистема ручных напоминаний поверх задач и истории. На этом этапе OpenAI не используется, напоминания не создаются автоматически и не добавляются в обычную расшифровку.

Команды:

- `/reminders`
- `/remind`

Основные файлы:

- `app/models.py`: `Reminder`
- `app/reminder_service.py`
- `app/reminder_scheduler.py`
- `app/reminder_parser.py`
- `app/handlers/reminders.py`
- `app/handlers/keyboards.py`
- `app/handlers/menu.py`
- `app/formatters.py`

Ключевые функции:

- `create_reminder()`
- `get_user_reminders()`
- `get_due_reminders()`
- `cancel_reminder()`
- `complete_reminder()`
- `snooze_reminder()`
- `parse_reminder_time_text()`
- `parse_reminder_request()`
- `run_reminder_scheduler()`
- `process_due_reminders_once()`

Создание:

- `/remind` — FSM: текст → сразу создать, если время есть в тексте; иначе выбор кнопки времени или ручной ввод времени;
- `/remind завтра 14:30 заехать в автосервис`;
- `/remind через 30 минут проверить бота`;
- `/remind через минуту проверить бота`;
- `/remind через 10 проверить бота`;
- `/remind 18:00 оплатить сервер`.
- `➕ Создать` → `позвонить Соне в 21:21` создает напоминание сразу без меню выбора времени.

Парсер времени работает без OpenAI и возвращает структурированный результат через `parse_reminder_text()`: `success`, `task_text`, `remind_at`, `timezone`, `matched_pattern`, `error`, `needs_task`, `needs_tomorrow_clarification`, `clarification_today_at`, `clarification_nextday_at`.

Поддерживаются:

- минуты: `через минуту`, `через одну минуту`, `через 10`, `через минут 10`, `минут через 15`, `через полчаса`, `через пол часа`, `через пару минут`, `через несколько минут`;
- часы: `через час`, `через часик`, `через два часа`, `часа через 2`, `через пару часов`, `через несколько часов`;
- смешанный формат: `через 1 час 30 минут`, `через час 30 минут`, `через полтора часа`, `через 1.5 часа`;
- `сегодня`, `завтра`, части дня (`утром`, `днём`, `вечером`, `ночью`);
- смещения по дням: `послезавтра`, `через день`, `через два дня`;
- дни недели: `в пятницу`, `в пятницу 14:30`, `позвонить Соне в пятницу вечером`;
- ввод только времени и формат `задача в HH:MM`.

Если время без даты уже прошло сегодня, используется завтра. Если написано `через 10` без единиц, это считается 10 минут. С 00:00 до 05:59 `завтра`/`завтрашний` без явной даты считается неоднозначным: handler показывает уточнение `📅 Сегодня` или `📅 Через день`. Явные даты, `послезавтра`, `через день`, дни недели и время после 06:00 уточнения не требуют. Служебные слова вроде `напомни`, `напомни мне`, `поставь напоминание`, `чтобы`, `пожалуйста` удаляются из `task_text`. Если время найдено, но задача пустая, handler спрашивает `Что напомнить?`. Часовой пояс берется из `DEFAULT_TIMEZONE`, дефолтное время — из `DEFAULT_REMINDER_TIME`. Scheduler также сравнивает due reminders со временем из `DEFAULT_TIMEZONE`, чтобы не зависеть от системной таймзоны сервера.

Статусы:

- `pending`
- `sending`
- `sent`
- `completed`
- `cancelled`
- `failed`

Callback data:

- `remind_time:<choice>`
- `remind_time:manual`
- `reminder_tomorrow_today:`
- `reminder_tomorrow_nextday:`
- `reminder_tomorrow_cancel:`
- `reminder_complete:<id>`
- `reminder_cancel:<id>`
- `reminder_snooze_hour:<id>`
- `reminder_snooze_tomorrow:<id>`

Будущие сценарии создания из задач, истории и AI `reminder_candidate` должны вызывать тот же `ReminderService.create_reminder()`.

## Быстрый Статус Обработки

Описание: после получения voice бот сразу отправляет статус и редактирует одно сообщение по этапам. Тексты прогресса выбираются случайно из локальных наборов VoiceToText.

Основные файлы:

- `app/handlers/voice.py`
- `app/handlers/utils.py`
- `app/progress_messages.py`

Ключевые функции:

- `handle_voice()`
- `safe_edit()`
- `get_random_progress_pack()`

Правила:

- 24 обычных набора по 8 сообщений хранятся в `ORDINARY_PROGRESS_PACKS`;
- легендарные наборы можно добавить в `LEGENDARY_PROGRESS_PACKS`;
- обычные наборы используются в 95% случаев, легендарные — в 5%, если они есть;
- набор выбирается один раз перед обработкой voice и дальше используется последовательно;
- progress updater редактирует одно статусное сообщение каждые 1.7 секунды;
- при успешной обработке бот дожидается завершения набора, чтобы последние сообщения не пролетали мгновенно;
- при ошибке updater останавливается и статус заменяется понятной ошибкой;
- OpenAI не используется для progress messages.

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

## Мемный Анализ Голосового

Описание: после каждой новой расшифровки бот показывает вирусный блок `📊 Анализ голосового`: длительность, содержательная часть, индекс воды, класс воды, многословность, тип голосового, оценка, редкий титул, цитата, вердикт, мем и сэкономленное время.

Основные файлы:

- `app/openai_service.py`
- `app/voice_analysis.py`
- `app/formatters.py`
- `app/handlers/voice.py`
- `app/handlers/callbacks.py`
- `app/handlers/keyboards.py`
- `app/models.py`

Ключевые функции:

- `normalize_voice_analysis()`
- `serialize_voice_analysis()`
- `parse_voice_analysis_json()`
- `format_voice_analysis()`
- `format_share_voice_analysis()`

Хранение:

- `VoiceNote.voice_analysis_json`
- `VoiceNote.analysis_message_ids`
- `UserSettings.total_saved_seconds`

Callback data:

- `fresh_analysis:<id>`
- `history_analysis:<id>`

Правила:

- отдельный OpenAI-запрос не делается;
- meme генерируется внутри текущего JSON анализа;
- мем должен быть коротким, жёстко саркастичным, циничным и пересылаемым;
- можно высмеивать длину, воду, драматургию, формат и фразы вроде `короче`, но нельзя переходить на личность автора;
- запрещены мат, угрозы, травля, унижения, оскорбления личности и чувствительные признаки;
- нормализатор заменяет очевидно токсичный meme на безопасный fallback;
- `voice_type_level` нормализуется из `wordiness_score`, `water_percent` и длительности, чтобы низкая многословность не показывала тип `Подкастер`;
- `water_level` нормализуется из `water_percent`, чтобы класс воды не конфликтовал с индексом воды;
- редкие титулы появляются только при `wordiness_score >= 9.5` или `water_percent >= 90`;
- старые записи без `voice_analysis_json` открываются через fallback без ошибки;
- history callbacks берут анализ только из SQLite и не вызывают OpenAI.

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
- `app/admin_service.py`

Ключевые функции:

- `is_owner()`
- `add_unlimited_user()`
- `admin_add_unlimited()`
- `set_user_tariff()`
- `add_friend_tariff()`
- `remove_friend_tariff()`

## Расширенная Админка

Описание: owner управляет ботом из Telegram без ручной правки `.env` и SQLite.

Команды:

- `/admin_help` или `/ah`
- `/start_text`
- `/set_start_text`
- `/reset_start_text`
- `/user <telegram_id>`
- `/set_tariff <telegram_id> <free|standard|premium|friend|owner>`
- `/tf <telegram_id> <free|standard|premium|friend|owner>`
- `/add_friend <telegram_id>`
- `/bro <telegram_id>`
- `/remove_friend <telegram_id>`
- `/unbro <telegram_id>`
- `/admin_users`
- `/admin_users 20`
- `/admin_users tariff=free`
- `/admin_stats`
- `/stats`
- `/admin_health`
- `/admin_backup`
- `/admin_broadcast`
- `/cancel`

Основные файлы:

- `app/handlers/admin.py`
- `app/admin_service.py`
- `app/models.py`: `AppConfig`, `UserSettings`
- `app/runtime_state.py`

Ключевые функции:

- `get_start_text()`, `set_start_text()`, `reset_start_text()`
- `set_user_tariff()`, `add_friend_tariff()`, `remove_friend_tariff()`
- `get_admin_user_info()`, `list_admin_users()`
- `format_admin_health()`
- `create_database_backup()`
- `get_broadcast_user_ids()`

Поведение:

- все команды проверяют owner через существующий `is_owner()`;
- non-owner получает `Команда доступна только владельцу бота.`;
- стартовый текст хранится в SQLite `app_config` под ключом `start_text`;
- если кастомный стартовый текст удален, `/start` использует дефолт из кода;
- `friend` в командах соответствует внутреннему тарифу `brother`;
- backup SQLite создается в `backups/`;
- broadcast идет через FSM с подтверждением inline-кнопкой.

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
- `reminders_opened`
- `reminder_created`
- `reminder_sent`
- `reminder_completed`
- `reminder_cancelled`
- `reminder_snoozed`

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
- `app/handlers/reminders.py`
- `app/reminder_scheduler.py`

Ключевые функции:

- `track_event()`
- `get_admin_stats()`
- `get_stats_for_period()`
- `format_admin_stats()`

## Admin Stats

Описание: owner-only статистика за сегодня, 7 дней или 30 дней.

Команды:

- `/admin_stats`
- `/stats`
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
- активные пользователи по тарифам, где каждый пользователь считается один раз по последнему тарифу за период;
- открытия истории/профиля;
- share clicks и paywall views;
- конверсии на русском: активация новых, голосовые от активных, успешная обработка, блокировки лимитом, доля “Поделиться”;
- причины ошибок по `error_type`;
- причины блокировок по стабильному `reason` code: `daily_voice_limit`, `monthly_minutes_limit`, `trial_expired`, `trial_minutes_limit`, `voice_too_long`.

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
