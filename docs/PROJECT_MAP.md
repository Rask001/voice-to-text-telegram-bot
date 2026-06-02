# Project Map

Актуальная карта проекта Voice to Text Telegram Bot. Используйте этот файл как первую точку навигации перед чтением исходников.

## Корень проекта

### `README.md`

- Назначение: публичное описание проекта, установка, запуск, переменные окружения, тарифы, история, troubleshooting.
- Основные классы: нет.
- Основные функции: нет.
- Связи: ссылается на `app/`, `.env.example`, `Dockerfile`, `docker-compose.yml`, `docs/`.

### `.env.example`

- Назначение: безопасный шаблон переменных окружения без реальных секретов.
- Основные классы: нет.
- Основные функции: нет.
- Связи: читается через `app/config.py` после копирования в `.env`, `.env.local` или `.env.production`.

### `.env.local`

- Назначение: локальный тестовый env для отдельного Telegram test bot token и отдельной SQLite базы `bot_local_test.db`.
- Основные классы: нет.
- Основные функции: нет.
- Связи: загружается через `ENV_FILE=.env.local`; используется `start_local.sh`; не коммитится.

### `.env.production`

- Назначение: production env с боевым Telegram token, OpenAI key, DeepSeek key и production `DATABASE_URL`.
- Основные классы: нет.
- Основные функции: нет.
- Связи: загружается через `ENV_FILE=.env.production`; не коммитится.

### `.gitignore`

- Назначение: исключает секреты, виртуальное окружение, SQLite базу, логи, временные файлы и macOS metadata.
- Основные классы: нет.
- Основные функции: нет.
- Связи: защищает `.env`, `.env.local`, `.env.production`, `.venv/`, `data/*.db`, `*.db`, `logs/`, `.DS_Store`.

### `requirements.txt`

- Назначение: Python-зависимости проекта.
- Основные классы: нет.
- Основные функции: нет.
- Связи: используется локальной установкой и `Dockerfile`.
- Зависимости: `aiogram`, `openai`, `python-dotenv`, `SQLAlchemy`.

### `Dockerfile`

- Назначение: контейнер для запуска бота на Python 3.12 slim.
- Основные классы: нет.
- Основные функции: нет.
- Связи: устанавливает `ffmpeg`, зависимости из `requirements.txt`, копирует `app/`, запускает `python -m app.main`.

### `docker-compose.yml`

- Назначение: запуск Docker-сервиса `bot`.
- Основные классы: нет.
- Основные функции: нет.
- Связи: использует `.env`, монтирует `./data:/app/data`, собирает `Dockerfile`.

### `start.sh`

- Назначение: локальный запуск бота в foreground.
- Основные классы: нет.
- Основные функции: нет.
- Связи: подхватывает Homebrew PATH, проверяет существующий процесс `app.main`, запускает `.venv/bin/python -m app.main`.

### `start_local.sh`

- Назначение: безопасный запуск локального тестового бота в background.
- Основные классы: нет.
- Основные функции: нет.
- Связи: принудительно использует `.env.local`, проверяет отдельный test token и `bot_local_test.db`, пишет PID в `data/local_bot.pid`, логи в `logs/local.*.log`.

### `stop_local.sh`

- Назначение: остановка только локального тестового процесса.
- Основные классы: нет.
- Основные функции: нет.
- Связи: останавливает PID из `data/local_bot.pid` и не трогает другие Python-процессы.

### `status_local.sh`

- Назначение: статус локального тестового процесса.
- Основные классы: нет.
- Основные функции: нет.
- Связи: показывает `.env.local`, PID, resources и хвост логов `logs/local.*.log`.

### `stop.sh`

- Назначение: остановка локального процесса бота.
- Основные классы: нет.
- Основные функции: нет.
- Связи: останавливает процесс по паттерну `[a]pp.main`.

### `status.sh`

- Назначение: проверка локального процесса бота.
- Основные классы: нет.
- Основные функции: нет.
- Связи: ищет процесс по паттерну `[a]pp.main`.

### `deploy_common.sh`

- Назначение: общий локальный сценарий публикации изменений и обновления серверного Mac.
- Основные классы: нет.
- Основные функции: нет.
- Связи: используется `deploy_lan.sh` и `deploy_tailscale.sh`; запускает локальные проверки, `git add`, `git commit`, `git push`, затем по SSH вызывает серверный `./deploy.sh` и `./status.sh`.

### `deploy_lan.sh`

- Назначение: one-command deploy через локальный адрес серверного Mac `192.168.1.104`.
- Основные классы: нет.
- Основные функции: нет.
- Связи: задает `REMOTE_HOST` и вызывает `deploy_common.sh`.

### `deploy_tailscale.sh`

- Назначение: one-command deploy через Tailscale IP серверного Mac `100.104.17.90`.
- Основные классы: нет.
- Основные функции: нет.
- Связи: перед деплоем проверяет SSH через Tailscale; при необходимости вызывает `fix_tailscale_route.sh`, затем запускает `deploy_common.sh`.

### `fix_tailscale_route.sh`

- Назначение: чинит локальный route только до серверного Tailscale IP, если Hupp/VPN перехватил маршрут.
- Основные классы: нет.
- Основные функции: нет.
- Связи: используется вручную или из `deploy_tailscale.sh`; не отключает и не перезапускает Hupp.

## `app/`

Основной Python-пакет бота.

### `app/__init__.py`

- Назначение: помечает `app` как Python-пакет.
- Основные классы: нет.
- Основные функции: нет.
- Связи: нужен для запуска `python -m app.main`.

### `app/main.py`

- Назначение: точка входа приложения.
- Основные классы: нет.
- Основные функции:
  - `main()` — настраивает логирование, читает настройки, создает `Bot`, `Dispatcher`, session factory, `TranscriptionService`, `TextAnalysisService`, запускает reminder scheduler, регистрирует router и запускает polling.
- Связи:
  - читает `get_settings()` из `app/config.py`;
  - создает SQLite session factory через `app/db.py`;
  - подключает aggregate router из `app/handlers/__init__.py`;
  - создает `TranscriptionService(OpenAITranscriptionClient)` и `TextAnalysisService(DeepSeekClient)`;
  - запускает `run_reminder_scheduler()` из `app/reminder_scheduler.py`;
  - использует aiogram polling, не webhook.

### `app/config.py`

- Назначение: загрузка env-файла через `ENV_FILE` и типизированные настройки.
- Основные классы:
  - `Settings` — dataclass с Telegram/OpenAI transcription/DeepSeek/SQLite/лимитами/owner настройками, `env_file`, `app_env`, `default_timezone`, `default_reminder_time`.
- Основные функции:
  - `get_settings()` — читает `ENV_FILE` или `.env`, валидирует обязательные `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`;
  - `openai_transcription_model` — compatibility property для нового имени `OPENAI_TRANSCRIPTION_MODEL`;
  - `_infer_app_env()` — определяет `local`/`production` по имени env-файла;
  - `_parse_optional_int()` — парсит `OWNER_TELEGRAM_ID`;
  - `_parse_int_list()` — парсит `UNLIMITED_USER_IDS`.
- Связи:
  - используется в `app/main.py`, `app/handlers/`, `app/access.py`, `app/ai_clients/`, `app/db.py`.

### `app/db.py`

- Назначение: SQLAlchemy Base, engine, session factory, простые SQLite schema updates.
- Основные классы:
  - `Base` — declarative base для моделей.
- Основные функции:
  - `create_session_factory()` — создает engine, таблицы и безопасно добавляет недостающие SQLite-колонки;
  - `_ensure_sqlite_parent()` — создает папку для SQLite файла;
  - `_sync_database_url()` — приводит `sqlite+aiosqlite:///...` к sync URL для текущего SQLAlchemy engine;
  - `_ensure_sqlite_schema_updates()` — добавляет новые колонки в `voice_notes` и `user_settings`;
  - `_add_text_column()`, `_add_integer_column()` — helpers для SQLite ALTER TABLE;
  - `session_scope()` — контекстный helper commit/rollback.
- Связи:
  - импортирует модели из `app/models.py`;
  - использует `Settings` из `app/config.py`;
  - создается в `app/main.py`;
  - session factory передается в handlers через aiogram dependency injection.

### `app/models.py`

- Назначение: SQLAlchemy-модели SQLite.
- Основные классы:
  - `DailyUsage` — legacy дневной счетчик обработок;
  - `AnalyticsEvent` — локальные события использования бота;
  - `VoiceNote` — сохраненная расшифровка, summary, tasks, details, message ids;
  - `Reminder` — ручные и будущие task/history/AI напоминания;
  - `AppConfig` — небольшие настройки бота, включая кастомный `/start`;
  - `UserSettings` — настройки пользователя, тариф, counters, trial/month limits.
- Основные функции: нет.
- Связи:
  - наследуется от `Base` из `app/db.py`;
  - используется в `app/handlers/`, `app/preferences.py`, `app/limits.py`, `app/access.py`, `app/reminder_service.py`;
  - `VoiceNote.action_items` хранит новые задачи JSON-массивом `{text, priority}`, старые записи могут быть newline-строками;
  - `VoiceNote.voice_analysis_json` хранит мемный анализ голосового и fallback поддерживает старые записи без анализа;
  - `AnalyticsEvent.payload_json` хранит только служебный JSON без расшифровок и секретов;
  - при полной очистке пользовательской истории удаляются строки из `voice_notes`, но структура таблицы сохраняется.

## `app/handlers/`

Пакет aiogram handlers. `app/handlers.py` удален; вместо него `app/handlers/__init__.py` собирает aggregate `router`, чтобы внешний импорт `from app.handlers import router` остался прежним.

### `app/handlers/__init__.py`

- Назначение: aggregate router и публичные exports для тестов.
- Основные классы: нет.
- Основные функции: нет.
- Связи: подключает роутеры `start`, `system`, `settings`, `profile`, `help`, `history`, `reminders`, `admin`, `voice`, `callbacks`, `menu`, `fallbacks`.

### `app/handlers/constants.py`

- Назначение: общие константы handlers.
- Основные классы: нет.
- Основные данные: `MODE_LABELS`, `BUTTON_LOCKS`, `MENU_*`, legacy-тексты старых Reply Keyboard кнопок.
- Связи: используется в keyboards, callbacks, menu.

### `app/handlers/keyboards.py`

- Назначение: Reply Keyboard и inline keyboards.
- Основные функции:
  - `main_keyboard()`;
  - `reminders_menu_keyboard()`;
  - `note_keyboard()`;
  - `settings_keyboard()`;
  - `history_keyboard()`;
  - `reminder_time_keyboard()`;
  - `reminder_fallback_time_keyboard()`;
  - `reminder_action_keyboard()`;
  - `reminders_keyboard()`.
- Связи: используется почти всеми handler-модулями.

### `app/handlers/utils.py`

- Назначение: общие технические helper-функции handlers.
- Основные функции:
  - `download_voice()`, `convert_to_mp3()`, `find_ffmpeg()`;
  - `safe_edit()`;
  - `clean_title()`;
  - `parse_note_action()`;
  - `send_html_chunks()`, `send_text_chunks()`;
  - `join_message_ids()`;
  - `split_html_for_telegram()`, `split_for_telegram()`.
- Связи: используется в voice, callbacks, history, system.

### `app/handlers/start.py`

- Назначение: `/start` и `start:*` callbacks.
- Основные функции:
  - `start()`;
  - `start_callback()`.
- Связи: использует `main_keyboard()`, `help_text()`, `build_profile_text()`, `get_start_text()` из `app/admin_service.py`.

### `app/handlers/system.py`

- Назначение: `/health`.
- Основные функции:
  - `health()`;
  - `_check_database()`;
  - `_check_ffmpeg()`.
- Связи: использует `find_ffmpeg()` из utils и SQLite session factory.

### `app/handlers/settings.py`

- Назначение: `/settings` и `settings:*` callbacks.
- Основные функции:
  - `settings_command()`;
  - `settings_callback()`.
- Связи: использует `app/preferences.py`, `format_settings()`, `settings_keyboard()`.

### `app/handlers/profile.py`

- Назначение: `/profile`, `/my_id` и сборка текста профиля.
- Основные функции:
  - `profile()`;
  - `my_id()`;
  - `build_profile_text()`.
- Связи: использует `check_user_access()`, `format_profile()`, `format_my_id()`.

### `app/handlers/help.py`

- Назначение: `/help`.
- Основные функции:
  - `help_command()`.
- Связи: использует `help_text()` и `main_keyboard()`.

### `app/handlers/history.py`

- Назначение: `/history`, список истории и открытие записи.
- Основные функции:
  - `history_command()`;
  - `history_callback()`;
  - `_send_history()`.
- Связи: использует `VoiceNote`, `format_history()`, `format_history_item()`, `history_keyboard()`, `note_keyboard(source="history")`.

### `app/handlers/reminders.py`

- Назначение: `/reminders`, `/remind`, ручной FSM создания и callback-кнопки напоминаний.
- Основные классы:
  - `ReminderCreation`.
- Основные функции:
  - `reminders_command()`;
  - `remind_command()`;
  - `reminder_text_received()`;
  - `reminder_time_selected()`;
  - `reminder_manual_time_received()`;
  - `reminder_action_callback()`;
  - `send_user_reminders()`.
- Связи: использует `app/reminder_service.py`, `app/reminder_parser.py`, `Reminder`, `format_reminders_list()`, `format_reminder_created()`, reminder keyboards и analytics events. Создание идет через `create_reminder()` как для FSM, так и для `/remind <время> <текст>`; если текст FSM уже содержит время, меню выбора времени не показывается.

### `app/handlers/admin.py`

- Назначение: owner-only админские команды и многошаговые FSM-сценарии.
- Основные классы:
  - `AdminStates` — ввод стартового текста, ввод/подтверждение broadcast.
- Основные функции:
  - `admin_help()`;
  - `start_text()`, `set_start_text_command()`, `start_text_received()`, `reset_start_text_command()`;
  - `admin_user_info()`, `set_tariff_command()`, `add_friend_command()`, `remove_friend_command()`;
  - `admin_users()`;
  - `admin_health()`;
  - `admin_backup()`;
  - `admin_broadcast()`, `admin_broadcast_text_received()`, `admin_broadcast_confirm()`;
  - `cancel_admin_mode()`;
  - `admin_add_unlimited()`;
  - `admin_stats()`, `admin_stats_today()`, `admin_stats_7d()`, `admin_stats_30d()`;
  - `admin_stats_callback()`;
  - `admin_cleanup_analytics()`, `admin_cleanup_analytics_callback()`;
  - `is_owner_command_user()`.
- Связи: использует `is_owner()` и `add_unlimited_user()` из `app/access.py`, бизнес-логику из `app/admin_service.py`, статистику из `app/analytics_service.py`.

### `app/handlers/voice.py`

- Назначение: основной pipeline voice message.
- Основные функции:
  - `handle_voice()`.
- Связи: использует `check_user_access()`, `record_voice_usage()`, `TranscriptionService`, `TextAnalysisService`, `build_voice_analysis()`, `VoiceNote`, `format_response()`, `note_keyboard(source="fresh")`, `get_random_progress_pack()` из `app/progress_messages.py`, utils для ffmpeg/download/chunking, `track_event()` для voice analytics. Если DeepSeek падает после успешной расшифровки, сохраняет transcript в `VoiceNote` и показывает понятную ошибку.

### `app/handlers/callbacks.py`

- Назначение: inline callbacks свежих результатов и истории.
- Основные функции:
  - `fresh_note_callback()`;
  - `history_note_callback()`.
- Связи: использует `VoiceNote`, `parse_stored_tasks()`, `format_tasks()`, `format_details()`, `format_share()`, `send_html_chunks()`, `send_text_chunks()`, `track_event()` для `share_clicked`.

### `app/handlers/menu.py`

- Назначение: Reply Keyboard actions.
- Основные функции:
  - `reply_keyboard_handler()`.
- Связи: маршрутизирует главное меню в profile/history/settings/help/new voice и вложенное меню напоминаний в `/remind`/`/reminders`; пишет события `profile_opened`, `history_opened`, `reminders_opened`, `paywall_shown`.

### `app/handlers/fallbacks.py`

- Назначение: быстрые ответы на текст и неподдерживаемые media.
- Основные функции:
  - `text_fallback()`;
  - `unsupported_media()`;
  - `fallback()`.
- Связи: использует `main_keyboard()`.

### `app/formatters.py`

- Назначение: централизованное форматирование сообщений Telegram.
- Основные классы: нет.
- Основные функции:
  - `format_response()` — выбирает short/full/tasks режим;
  - `format_short()`, `format_details()`, `format_tasks()`, `format_share()`;
  - `format_voice_analysis()`, `format_share_voice_analysis()`;
  - `format_history()`, `format_history_item()`;
  - `format_profile()`, `format_my_id()`, `format_reminders_list()`, `format_reminder_created()`, `format_settings()`, `help_text()`;
  - `format_numbered_list()` — нумерованный список задач с priority-сортировкой;
  - `analysis_list()`, `fallback_title()`, `format_note_date()`, `trim()`, `trim_plain()`.
- Связи:
  - использует `AccessStatus` из `app/access.py`;
  - использует `normalize_tasks()`, `parse_stored_tasks()`, `sort_tasks_for_display()` из `app/tasks.py`;
  - использует `app/voice_analysis.py` для длительности, уровней воды и типа голосового;
  - вызывается из `app/handlers/`;
  - `TELEGRAM_TEXT_LIMIT` импортируется handlers для chunking.

### `app/voice_analysis.py`

- Назначение: нормализация, хранение и справочники мемного анализа голосовых.
- Основные классы:
  - `VoiceAnalysis` — TypedDict структуры анализа.
- Основные данные:
  - `WATER_CLASSES` — 10 уровней воды;
  - `VOICE_TYPES` — 10 типов голосового;
  - `RARE_TITLES` — редкие титулы для высокой воды/многословности.
- Основные функции:
  - `normalize_voice_analysis()` — приводит локально рассчитанные метрики и DeepSeek creative text к безопасной структуре;
  - `fallback_voice_analysis()` — fallback для старых записей без анализа;
  - `serialize_voice_analysis()`;
  - `parse_voice_analysis_json()`;
  - `water_class()`, `voice_type()`;
  - `format_duration()`, `format_compact_duration()`.
- Связи:
  - используется в `app/voice_metrics_service.py`, `app/formatters.py`, `app/handlers/voice.py`, `app/handlers/callbacks.py`;
  - не вызывает OpenAI и не знает о Telegram.

### `app/progress_messages.py`

- Назначение: локальные случайные наборы прогресс-сообщений для обработки voice.
- Основные данные:
  - `ORDINARY_PROGRESS_PACKS` — 24 обычных набора по 8 сообщений;
  - `LEGENDARY_PROGRESS_PACKS` — 5 редких легендарных наборов;
  - `LEGENDARY_PROGRESS_PROBABILITY` — вероятность легендарного набора 5%;
  - `PROGRESS_UPDATE_INTERVAL_SECONDS` — интервал между статусами 1.7 секунды.
- Основные функции:
  - `get_random_progress_pack()` — выбирает набор перед обработкой voice;
  - `validate_progress_packs()` — проверяет, что каждый набор содержит ровно 8 сообщений.
- Связи:
  - используется в `app/handlers/voice.py`;
  - не использует OpenAI, Telegram API или SQLite.

### `app/analytics_service.py`

- Назначение: локальная аналитика использования бота в SQLite.
- Основные классы:
  - `AdminStats` — агрегированный snapshot статистики за период: пользователи, voice, минуты, среднее время обработки, конверсии, причины ошибок и блокировок.
- Основные функции:
  - `track_event()` — безопасно пишет событие и не ломает пользовательский сценарий при ошибке аналитики;
  - `get_admin_stats()` — статистика за `today`, `7d`, `30d`;
  - `get_stats_for_period()` — статистика за произвольный период;
  - `cleanup_old_events()` — удаляет события старше заданного числа дней;
  - `format_admin_stats()` — форматирует owner-only отчет;
  - `_average_processing_time()` — считает среднее время обработки успешных voice;
  - `_payload_counts()` — считает причины ошибок и блокировок из payload;
  - `_active_users_by_latest_tariff()` — считает каждого активного пользователя в одном, последнем за период тарифе;
  - `_normalize_block_reason()` — нормализует legacy-тексты блокировок в стабильные reason codes;
  - `period_title()` — заголовок периода.
- Связи:
  - использует `AnalyticsEvent` из `app/models.py`;
  - использует `check_user_access()` для определения тарифа на момент события;
  - вызывается из `app/handlers/start.py`, `profile.py`, `settings.py`, `history.py`, `menu.py`, `voice.py`, `callbacks.py`, `admin.py`;
  - не сохраняет расшифровки, summary, задачи или секреты.

### `app/admin_service.py`

- Назначение: бизнес-логика owner-only админки без Telegram orchestration.
- Основные классы:
  - `AdminUserInfo` — snapshot пользователя для `/user`.
- Основные функции:
  - `get_start_text()`, `set_start_text()`, `reset_start_text()`, `validate_start_text()`;
  - `set_user_tariff()`, `add_friend_tariff()`, `remove_friend_tariff()`;
  - `get_admin_user_info()`, `format_admin_user_info()`;
  - `list_admin_users()`, `format_admin_users()`;
  - `create_database_backup()`;
  - `get_broadcast_user_ids()`;
  - `format_admin_health()`.
- Связи:
  - работает с `AppConfig`, `UserSettings`, `VoiceNote`, `Reminder`, `AnalyticsEvent`;
  - вызывается из `app/handlers/admin.py`;
  - использует тарифы из `app/tariffs.py`;
  - backup SQLite создает файлы в `backups/`.

### `app/reminder_service.py`

- Назначение: единая бизнес-логика напоминаний.
- Основные функции:
  - `create_reminder()`;
  - `get_user_reminders()`;
  - `get_reminder_by_id()`;
  - `cancel_reminder()`;
  - `complete_reminder()`;
  - `snooze_reminder()`;
  - `get_due_reminders()`;
  - `mark_reminder_sending()`;
  - `mark_reminder_sent()`;
  - `mark_reminder_failed()`.
- Связи: работает с моделью `Reminder`; вызывается из `app/handlers/reminders.py` и `app/reminder_scheduler.py`.

### `app/reminder_scheduler.py`

- Назначение: фоновая отправка due reminders.
- Основные функции:
  - `run_reminder_scheduler()` — цикл каждые 30 секунд;
  - `process_due_reminders_once()` — один проход для scheduler и тестов.
- Связи: использует `reminder_service`, `now_in_timezone(settings.default_timezone)`, `reminder_action_keyboard()`, `Bot.send_message()`, пишет `reminder_sent`.

### `app/reminder_parser.py`

- Назначение: простой парсер времени напоминаний без OpenAI.
- Основные функции:
  - `parse_reminder_text()`;
  - `parse_reminder_time_choice()`;
  - `parse_simple_reminder_time()`;
  - `parse_reminder_time_text()`;
  - `parse_reminder_request()`;
  - `parse_default_time()`;
  - `now_in_timezone()`.
- Основные данные:
  - `AMBIGUOUS_TOMORROW_HOUR` — ночной порог для уточнения неоднозначного `завтра`.
- Связи: используется ручным `/remind`; поддерживает кнопки времени, ручной ввод, команды вида `/remind завтра 14:30 заехать в автосервис`, разговорные относительные фразы `через минуту`/`через 10`/`минут через 15`/`через пол часа`/`через пару часов`, смещения по дням `послезавтра`/`через день`/`через два дня`, дни недели и текст вида `позвонить Соне в 21:21`. С 00:00 до 05:59 возвращает `needs_tomorrow_clarification=True` для `завтра` без явной даты, чтобы `app/handlers/reminders.py` показал выбор `Сегодня`/`Через день`. Читает настройки через handler: `DEFAULT_TIMEZONE` и `DEFAULT_REMINDER_TIME`.

### `app/runtime_state.py`

- Назначение: легкое runtime-состояние процесса.
- Основные функции:
  - `mark_reminder_scheduler_started()`;
  - `uptime_seconds()`.
- Основные данные:
  - `APP_STARTED_AT`;
  - `REMINDER_SCHEDULER_STARTED`.
- Связи: вызывается из `app/main.py`, читается в `app/admin_service.py` для `/admin_health`.

### `app/tasks.py`

- Назначение: единый нормализатор задач и совместимость старого/нового формата.
- Основные классы:
  - `TaskItem` — TypedDict `{text: str, priority: bool}`.
- Основные функции:
  - `normalize_tasks()` — принимает строки, dict objects и списки;
  - `serialize_tasks()` — сохраняет задачи JSON-массивом;
  - `parse_stored_tasks()` — читает JSON или старый newline-format;
  - `sort_tasks_for_display()` — priority tasks first, порядок внутри групп сохраняется;
  - `split_stored_list()` — helper для старых строковых списков.
- Связи:
  - используется в `app/text_analysis_service.py`, `app/handlers/`, `app/formatters.py`;
  - обеспечивает обратную совместимость `VoiceNote.action_items`.

### `app/ai_clients/openai_client.py`

- Назначение: низкоуровневый OpenAI client только для speech-to-text.
- Основные классы:
  - `OpenAITranscriptionClient`;
  - `OpenAIInsufficientQuotaError`.
- Основные данные:
  - `TRANSCRIPTION_PROMPT` — просит дословную расшифровку без выводов, структурирования и интерпретации.
- Основные функции:
  - `OpenAITranscriptionClient.transcribe()` — отправляет MP3 в OpenAI Audio Transcriptions;
  - `_is_insufficient_quota()` — определяет quota exhaustion;
  - `_with_rate_limit_retry()` — ограниченный exponential backoff для обычного `RateLimitError`.
- Связи:
  - используется в `app/transcription_service.py` и `app/main.py`;
  - не анализирует текст и не строит JSON.

### `app/ai_clients/deepseek_client.py`

- Назначение: низкоуровневый DeepSeek client для structured text analysis через OpenAI-compatible Chat Completions.
- Основные классы:
  - `DeepSeekClient`;
  - `DeepSeekClientError`.
- Основные функции:
  - `DeepSeekClient.analyze_text()` — отправляет system/user prompt и возвращает raw JSON text.
- Связи:
  - используется в `app/text_analysis_service.py` и `app/main.py`;
  - читает `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` из `Settings`;
  - не получает аудиофайлы.

### `app/transcription_service.py`

- Назначение: доменный сервис audio-to-text.
- Основные классы:
  - `TranscriptionService`;
  - `TranscriptionClient` protocol.
- Основные функции:
  - `TranscriptionService.transcribe()`.
- Связи:
  - оборачивает `OpenAITranscriptionClient`;
  - вызывается из `app/handlers/voice.py`;
  - возвращает только plain text transcript.

### `app/text_analysis_service.py`

- Назначение: DeepSeek structured analysis для transcript и локального metrics context.
- Основные классы:
  - `TextAnalysisService`;
  - `TextAnalysisError`;
  - `TextAnalysisResult`;
  - `VoiceAnalysisText`.
- Основные функции:
  - `TextAnalysisService.analyze()` — принимает transcript + optional `pre_metrics`, возвращает `title`, `summary`, `action_items`, `details`, `important_points`, `voice_analysis_text`;
  - `_analysis_system_prompt()` — prompt для summary/tasks/details/meme и правило “локальные метрики — источник истины”;
  - `_analysis_user_prompt()` — передает transcript и `voice_metrics`;
  - `_extract_json()`;
  - `_as_string_list()`.
- Связи:
  - использует `normalize_tasks()` из `app/tasks.py`;
  - вызывается из `app/handlers/voice.py`;
  - не считает численные voice metrics.

### `app/voice_metrics_service.py`

- Назначение: локальный расчет метрик голосового без AI.
- Основные функции:
  - `count_words()`;
  - `calculate_pre_metrics()` — считает `duration_seconds`, `word_count`, `words_per_minute`, rough `wordiness_score` перед DeepSeek;
  - `calculate_final_metrics()` — считает `useful_word_count`, `compression_ratio`, `meaningful_duration_seconds`, `water_percent`, `wordiness_score`, `quality_score`, тип и класс воды после DeepSeek;
  - `calculate_useful_word_count()` — использует `summary + tasks + important_points + details * 0.25`, без transcript;
  - `get_water_class()`;
  - `get_voice_type()`;
  - `validate_voice_analysis_consistency()`;
  - `sanitize_ai_meme_by_metrics()` — заменяет DeepSeek verdict/meme локальным fallback при конфликте с метриками;
  - `build_voice_analysis()` — объединяет финальные локальные метрики с DeepSeek `verdict/meme/quote`.
- Связи:
  - использует `normalize_voice_analysis()` из `app/voice_analysis.py`;
  - вызывается из `app/handlers/voice.py`;
  - не вызывает OpenAI или DeepSeek.

### `app/openai_service.py`

- Назначение: совместимый alias для старых импортов, теперь только OpenAI transcription.
- Основные классы:
  - `OpenAIService` — subclass `TranscriptionService`, оборачивает `OpenAITranscriptionClient`.
- Основные функции и методы:
  - `OpenAIService.transcribe()` — унаследованная audio transcription.
- Связи:
  - не вызывается из `app/main.py` в новой архитектуре;
  - не имеет `analyze()` и не содержит text-analysis prompt.

### `app/access.py`

- Назначение: низкоуровневые правила тарифного доступа, лимиты, owner/brother/free/standard/premium.
- Основные классы:
  - `AccessStatus` — snapshot доступа пользователя для `/profile` и проверок, включая пользовательский `denial_reason` и машинный `denial_code` для аналитики.
- Основные функции:
  - `is_owner()` — owner по `OWNER_TELEGRAM_ID` или username `aaios`;
  - `get_access_status()` — статус без учета конкретного voice duration;
  - `check_voice_access()` — проверка перед OpenAI: дневной лимит, длительность, месячные/total минуты, trial;
  - `record_voice_usage()` — списывает voice и минуты после успешной обработки;
  - `add_unlimited_user()` — добавляет пользователя в тариф `По-братски от Тоши`;
  - internal helpers `_prepare_user_settings()`, `_resolve_tariff_type()`, `_reset_period_counters()`, `_apply_plan_limits()`, `_get_static_denial()`, `_build_access_status()`, `_trial_days_left()`, `_billable_minutes()`.
- Связи:
  - использует `UserSettings` через `app/preferences.py`;
  - не использует `DailyUsage` в актуальной логике лимитов;
  - использует тарифы из `app/tariffs.py`;
  - вызывается через `app/access_service.py`;
  - `record_voice_usage()` и `add_unlimited_user()` вызываются из `app/handlers/`.

### `app/access_service.py`

- Назначение: единая публичная точка проверки доступа.
- Основные классы: нет.
- Основные функции:
  - `check_user_access()` — возвращает `AccessStatus`; без `duration_seconds` дает общий статус, с duration проверяет конкретное voice до скачивания файла.
- Связи:
  - использует `check_voice_access()` и `get_access_status()` из `app/access.py`;
  - вызывается из `app/handlers/`;
  - тестируется в `tests/test_access_service.py`.

### `app/tariffs.py`

- Назначение: декларативные правила тарифов.
- Основные классы:
  - `TariffPlan` — code, label, daily limit, max voice duration, monthly/total minutes, trial days.
- Основные функции:
  - `get_tariff()` — возвращает тариф или Free fallback.
- Основные константы:
  - `OWNER`, `BROTHER`, `FREE`, `STANDARD`, `PREMIUM`, `TARIFFS`.
- Связи:
  - используется в `app/access.py`;
  - indirectly отображается в `/profile` через `AccessStatus`.

### `app/preferences.py`

- Назначение: настройки формата ответа пользователя.
- Основные классы: нет.
- Основные функции:
  - `normalize_response_mode()` — validates `short`, `full`, `tasks`;
  - `get_response_mode()` — читает режим пользователя или default;
  - `set_response_mode()` — сохраняет режим;
  - `get_or_create_user_settings()` — создает/читает `UserSettings`.
- Связи:
  - использует `UserSettings` из `app/models.py`;
  - вызывается из `app/handlers/` и `app/access.py`.

### `app/limits.py`

- Назначение: legacy дневной счетчик `DailyUsage`.
- Основные классы: нет.
- Основные функции:
  - `get_or_create_daily_usage()`;
  - `can_process_voice()` — legacy проверка дневного лимита;
  - `increment_voice_usage()` — legacy increment.
- Связи:
  - использует `DailyUsage` из `app/models.py`;
  - сейчас основной контроль лимитов находится в `app/access.py`;
  - активный runtime больше не вызывает `increment_voice_usage()`, модуль оставлен как compatibility layer для старой таблицы.

## `scripts/`

### `scripts/run_bot.command`

- Назначение: macOS double-click запуск бота из Finder/Terminal.
- Основные классы: нет.
- Основные функции: нет.
- Связи: подхватывает Homebrew shellenv, запускает `.venv/bin/python -m app.main`.

## `data/`

### `data/.gitkeep`

- Назначение: сохраняет пустую папку `data/` в репозитории.
- Основные классы: нет.
- Основные функции: нет.
- Связи: рядом создается runtime SQLite база `data/bot.db`, которая игнорируется git.

## `tests/`

### `tests/__init__.py`

- Назначение: помечает `tests` как Python-пакет.
- Основные классы: нет.
- Основные функции: нет.

### `tests/test_access_service.py`

- Назначение: unit-тесты доступа и тарифов.
- Основные классы:
  - `AccessServiceTests`.
- Основные проверки:
  - Free закончился по дням;
  - Free закончился по минутам;
  - Owner всегда проходит;
  - тариф `По-братски от Тоши`;
  - дневной лимит Free.
- Связи: использует временную SQLite базу, `app/access_service.py`, `app/db.py`, `app/preferences.py`.

### `tests/test_tasks.py`

- Назначение: unit-тесты нормализации и отображения задач.
- Основные классы:
  - `TaskNormalizationTests`.
- Основные проверки:
  - priority tasks выводятся первыми;
  - старый newline-format поддерживается;
  - JSON roundtrip сохраняет priority;
  - пустой список показывает `Задачи не найдены.`
- Связи: использует `app/tasks.py` и `app/formatters.py`.

### `tests/test_history.py`

- Назначение: unit-тесты истории без OpenAI.
- Основные классы:
  - `HistoryTests`.
- Основные проверки:
  - history item форматируется из сохраненного `VoiceNote`;
  - history callback signatures не требуют `openai_service`.
- Связи: использует `app/formatters.py`, `app/handlers/history.py`, `app/handlers/callbacks.py`, `app/models.py`.

### `tests/test_analytics_service.py`

- Назначение: unit-тесты локальной аналитики и owner-only доступа к stats.
- Основные классы:
  - `AnalyticsServiceTests`.
- Основные проверки:
  - `track_event()` создает событие;
  - ошибка записи аналитики не пробрасывается в пользовательский сценарий;
  - `get_stats_for_period()` считает события и conversion rates;
  - метрики не падают при нулевых значениях;
  - owner имеет доступ к admin stats;
  - обычный пользователь не имеет доступ к admin stats.
- Связи: использует `app/analytics_service.py`, `app/handlers/admin.py`, `app/models.py`.

### `tests/test_voice_analysis.py`

- Назначение: unit-тесты мемного анализа голосовых.
- Основные классы:
  - `VoiceAnalysisTests`.
- Основные проверки:
  - `voice_analysis` нормализует сохраненный JSON;
  - meme сохраняется в SQLite;
  - старые записи без анализа не ломаются;
  - `saved_seconds` не бывает меньше 0;
  - `total_saved_seconds` увеличивается;
  - `build_voice_analysis()` считает метрики локально;
  - `calculate_pre_metrics()` ограничивает короткие сообщения;
  - `calculate_final_metrics()` считает воду через compression ratio;
  - `sanitize_ai_meme_by_metrics()` заменяет противоречивые verdict/meme;
  - formatter выводит анализ;
  - share-блок содержит meme;
  - rare title появляется только при высокой воде/многословности;
  - токсичный meme заменяется безопасным fallback.
- Связи: использует `app/voice_analysis.py`, `app/voice_metrics_service.py`, `app/formatters.py`, `app/models.py`.

### `tests/test_ai_pipeline.py`

- Назначение: unit-тесты разделения AI pipeline.
- Основные классы:
  - `AIPipelineTests`.
- Основные проверки:
  - `TranscriptionService` возвращает только text;
  - `TextAnalysisService` отправляет transcript + pre_metrics в DeepSeek-compatible client и парсит JSON;
  - DeepSeek prompt содержит правило “локальные метрики — источник истины”;
  - `OpenAIService` больше не имеет `analyze()`;
  - DeepSeek invalid JSON превращается в `TextAnalysisError`;
  - `voice_metrics_service` локально считает water и saved seconds;
  - при падении анализа full text сохраняется в `VoiceNote`.
- Связи: использует `app/transcription_service.py`, `app/text_analysis_service.py`, `app/voice_metrics_service.py`, `app/handlers/voice.py`.

### `tests/test_admin_service.py`

- Назначение: unit-тесты сервисной части админки.
- Основные классы:
  - `AdminServiceTests`.
- Основные проверки:
  - `set_start_text()` и `reset_start_text()`;
  - `set_user_tariff()`;
  - `add_friend_tariff()`;
  - `remove_friend_tariff()`;
  - `create_database_backup()`.
- Связи: использует `app/admin_service.py`, временную SQLite базу и `app/models.py`.

### `tests/test_admin_handlers.py`

- Назначение: unit-тесты owner-only поведения админских handlers.
- Основные классы:
  - `AdminHandlerTests`.
- Основные проверки:
  - non-owner не видит `/admin_help`;
  - owner видит `/admin_help`;
  - `/cancel` сбрасывает активный FSM state.
- Связи: использует `app/handlers/admin.py` и aiogram `MemoryStorage`.

### `tests/test_reminder_service.py`

- Назначение: unit-тесты напоминаний и scheduler без Telegram API.
- Основные классы:
  - `ReminderServiceTests`.
- Основные проверки:
  - `create_reminder()` создает `pending`;
  - `get_user_reminders()` и `get_reminder_by_id()` не показывают чужие напоминания;
  - cancel/complete меняют статусы;
  - `get_due_reminders()` возвращает только due `pending`;
  - sent/completed/cancelled не попадают в due;
  - scheduler не отправляет одно напоминание дважды.
- Связи: использует `app/reminder_service.py`, `app/reminder_scheduler.py`, `app/db.py`, `app/models.py`.

### `tests/test_reminder_parser.py`

- Назначение: unit-тесты простого парсера времени напоминаний без OpenAI.
- Основные классы:
  - `ReminderParserTests`.
- Основные проверки:
  - относительное время: `через минуту`, `через 10`, `через пол часа`, `через 10 минут`, `через 30 минут`, `через 1 час`;
  - `завтра 14:30`, `завтра утром`, `завтра днём`, `завтра вечером`;
  - ночное неоднозначное `завтра` требует уточнения до 06:00 и не требует после;
  - явная дата, `послезавтра`, `через день`, `через два дня` не требуют уточнения;
  - ввод только времени на сегодня или завтра;
  - неправильный формат возвращает `None`;
  - команда `/remind <время> <текст>` разделяет время и текст задачи.
- Связи: использует `app/reminder_parser.py`.

### `tests/test_reminder_handlers.py`

- Назначение: unit-тесты UX создания напоминания в FSM без Telegram API.
- Основные классы:
  - `ReminderHandlerTests`.
- Основные проверки:
  - текст со временем создает напоминание сразу и не показывает меню выбора времени;
  - выбор `Сегодня`/`Через день` после ночного уточнения создает правильную дату;
  - текст без времени показывает меню выбора времени и не создает запись.
- Связи: использует `app/handlers/reminders.py`, `app/db.py`, `app/models.py`.

## `docs/`

### `docs/PROJECT_MAP.md`

- Назначение: карта файлов, классов, функций и связей.
- Основные классы: нет.
- Основные функции: нет.
- Связи: основной навигационный файл для AI и разработчиков.

### `docs/ARCHITECTURE.md`

- Назначение: архитектурные потоки Telegram, OpenAI, SQLite, тарифов и кнопок.
- Основные классы: нет.
- Основные функции: нет.
- Связи: дополняет `PROJECT_MAP.md`.

### `docs/FEATURES.md`

- Назначение: каталог реализованных продуктовых и технических функций.
- Основные классы: нет.
- Основные функции: нет.
- Связи: помогает быстро понять, где менять конкретную возможность.

### `docs/AGENTS.md`

- Назначение: практическая инструкция для AI-агентов.
- Основные классы: нет.
- Основные функции: нет.
- Связи: задает порядок навигации: сначала docs, затем конкретные файлы.

### `docs/DATABASE_MIGRATIONS.md`

- Назначение: текущая SQLite-схема, список ручных `ALTER TABLE` и план будущего перехода на Alembic.
- Основные классы: нет.
- Основные функции: нет.
- Связи: дополняет `app/db.py`, `app/models.py` и архитектурный раздел про SQLite.

## Runtime и игнорируемые пути

- `.env` — реальные секреты, не читать и не коммитить без необходимости.
- `.venv/` — локальное виртуальное окружение.
- `data/bot.db` — SQLite база.
- `logs/`, `downloads/`, `*.pyc`, `__pycache__/`, `.DS_Store` — runtime/temporary.
