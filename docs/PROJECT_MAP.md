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
- Связи: читается через `app/config.py` после копирования в `.env`.

### `.gitignore`

- Назначение: исключает секреты, виртуальное окружение, SQLite базу, логи, временные файлы и macOS metadata.
- Основные классы: нет.
- Основные функции: нет.
- Связи: защищает `.env`, `.venv/`, `data/*.db`, `logs/`, `.DS_Store`.

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
  - `main()` — настраивает логирование, читает настройки, создает `Bot`, `Dispatcher`, session factory, `OpenAIService`, регистрирует router и запускает polling.
- Связи:
  - читает `get_settings()` из `app/config.py`;
  - создает SQLite session factory через `app/db.py`;
  - подключает aggregate router из `app/handlers/__init__.py`;
  - создает `OpenAIService` из `app/openai_service.py`;
  - использует aiogram polling, не webhook.

### `app/config.py`

- Назначение: загрузка `.env` и типизированные настройки.
- Основные классы:
  - `Settings` — dataclass с Telegram/OpenAI/SQLite/лимитами/owner настройками.
- Основные функции:
  - `get_settings()` — читает env, валидирует обязательные `TELEGRAM_BOT_TOKEN` и `OPENAI_API_KEY`;
  - `_parse_optional_int()` — парсит `OWNER_TELEGRAM_ID`;
  - `_parse_int_list()` — парсит `UNLIMITED_USER_IDS`.
- Связи:
  - используется в `app/main.py`, `app/handlers/`, `app/access.py`, `app/openai_service.py`, `app/db.py`.

### `app/db.py`

- Назначение: SQLAlchemy Base, engine, session factory, простые SQLite schema updates.
- Основные классы:
  - `Base` — declarative base для моделей.
- Основные функции:
  - `create_session_factory()` — создает engine, таблицы и безопасно добавляет недостающие SQLite-колонки;
  - `_ensure_sqlite_parent()` — создает папку для SQLite файла;
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
  - `UserSettings` — настройки пользователя, тариф, counters, trial/month limits.
- Основные функции: нет.
- Связи:
  - наследуется от `Base` из `app/db.py`;
  - используется в `app/handlers/`, `app/preferences.py`, `app/limits.py`, `app/access.py`;
  - `VoiceNote.action_items` хранит новые задачи JSON-массивом `{text, priority}`, старые записи могут быть newline-строками;
  - `AnalyticsEvent.payload_json` хранит только служебный JSON без расшифровок и секретов;
  - при полной очистке пользовательской истории удаляются строки из `voice_notes`, но структура таблицы сохраняется.

## `app/handlers/`

Пакет aiogram handlers. `app/handlers.py` удален; вместо него `app/handlers/__init__.py` собирает aggregate `router`, чтобы внешний импорт `from app.handlers import router` остался прежним.

### `app/handlers/__init__.py`

- Назначение: aggregate router и публичные exports для тестов.
- Основные классы: нет.
- Основные функции: нет.
- Связи: подключает роутеры `start`, `system`, `settings`, `profile`, `help`, `history`, `admin`, `voice`, `callbacks`, `menu`, `fallbacks`.

### `app/handlers/constants.py`

- Назначение: общие константы handlers.
- Основные классы: нет.
- Основные данные: `MODE_LABELS`, `BUTTON_LOCKS`, `MENU_*`.
- Связи: используется в keyboards, callbacks, menu.

### `app/handlers/keyboards.py`

- Назначение: Reply Keyboard и inline keyboards.
- Основные функции:
  - `main_keyboard()`;
  - `note_keyboard()`;
  - `settings_keyboard()`;
  - `history_keyboard()`.
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
- Связи: использует `main_keyboard()`, `help_text()`, `build_profile_text()`.

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

- Назначение: `/profile` и сборка текста профиля.
- Основные функции:
  - `profile()`;
  - `build_profile_text()`.
- Связи: использует `check_user_access()` и `format_profile()`.

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

### `app/handlers/admin.py`

- Назначение: owner-only админские команды.
- Основные функции:
  - `admin_add_unlimited()`.
  - `admin_stats()`, `admin_stats_today()`, `admin_stats_7d()`, `admin_stats_30d()`;
  - `admin_stats_callback()`;
  - `admin_cleanup_analytics()`, `admin_cleanup_analytics_callback()`;
  - `is_owner_command_user()`.
- Связи: использует `is_owner()` и `add_unlimited_user()` из `app/access.py`, статистику из `app/analytics_service.py`.

### `app/handlers/voice.py`

- Назначение: основной pipeline voice message.
- Основные функции:
  - `handle_voice()`.
- Связи: использует `check_user_access()`, `record_voice_usage()`, `OpenAIService`, `VoiceNote`, `format_response()`, `note_keyboard(source="fresh")`, utils для ffmpeg/download/chunking, `track_event()` для voice analytics.

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
- Связи: маршрутизирует нижнее меню в profile/history/settings/help/new voice, пишет события `profile_opened`, `history_opened`, `paywall_shown`.

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
  - `format_history()`, `format_history_item()`;
  - `format_profile()`, `format_settings()`, `help_text()`;
  - `format_numbered_list()` — нумерованный список задач с priority-сортировкой;
  - `analysis_list()`, `fallback_title()`, `format_note_date()`, `trim()`, `trim_plain()`.
- Связи:
  - использует `AccessStatus` из `app/access.py`;
  - использует `normalize_tasks()`, `parse_stored_tasks()`, `sort_tasks_for_display()` из `app/tasks.py`;
  - вызывается из `app/handlers/`;
  - `TELEGRAM_TEXT_LIMIT` импортируется handlers для chunking.

### `app/analytics_service.py`

- Назначение: локальная аналитика использования бота в SQLite.
- Основные классы:
  - `AdminStats` — агрегированный snapshot статистики за период.
- Основные функции:
  - `track_event()` — безопасно пишет событие и не ломает пользовательский сценарий при ошибке аналитики;
  - `get_admin_stats()` — статистика за `today`, `7d`, `30d`;
  - `get_stats_for_period()` — статистика за произвольный период;
  - `cleanup_old_events()` — удаляет события старше заданного числа дней;
  - `format_admin_stats()` — форматирует owner-only отчет;
  - `period_title()` — заголовок периода.
- Связи:
  - использует `AnalyticsEvent` из `app/models.py`;
  - использует `check_user_access()` для определения тарифа на момент события;
  - вызывается из `app/handlers/start.py`, `profile.py`, `settings.py`, `history.py`, `menu.py`, `voice.py`, `callbacks.py`, `admin.py`;
  - не сохраняет расшифровки, summary, задачи или секреты.

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
  - используется в `app/openai_service.py`, `app/handlers/`, `app/formatters.py`;
  - обеспечивает обратную совместимость `VoiceNote.action_items`.

### `app/openai_service.py`

- Назначение: изоляция вызовов OpenAI API.
- Основные классы:
  - `OpenAIInsufficientQuotaError` — специальная ошибка для `insufficient_quota`;
  - `OpenAIService` — клиент OpenAI.
- Основные функции и методы:
  - `OpenAIService.transcribe()` — отправляет MP3 в Audio Transcriptions;
  - `OpenAIService.analyze()` — просит JSON с `title`, `summary`, `tasks`, `details`, `important_points`;
  - `OpenAIService._with_rate_limit_retry()` — ограниченный exponential backoff для обычных `RateLimitError`;
  - `_as_string_list()` — normalizer массивов строк;
  - `_extract_json()` — вытаскивает JSON из текста/markdown fence;
  - `_is_insufficient_quota()` — определяет quota exhaustion.
- Связи:
  - получает `Settings` из `app/config.py`;
  - использует `normalize_tasks()` из `app/tasks.py`;
  - вызывается из `app/handlers/voice.py`;
  - не знает о SQLite и Telegram.

### `app/access.py`

- Назначение: низкоуровневые правила тарифного доступа, лимиты, owner/brother/free/standard/premium.
- Основные классы:
  - `AccessStatus` — snapshot доступа пользователя для `/profile` и проверок.
- Основные функции:
  - `is_owner()` — owner по `OWNER_TELEGRAM_ID` или username `aaios`;
  - `get_access_status()` — статус без учета конкретного voice duration;
  - `check_voice_access()` — проверка перед OpenAI: дневной лимит, длительность, месячные/total минуты, trial;
  - `record_voice_usage()` — списывает voice и минуты после успешной обработки;
  - `add_unlimited_user()` — добавляет пользователя в тариф `По-братски от Тоши`;
  - internal helpers `_prepare_user_settings()`, `_resolve_tariff_type()`, `_reset_period_counters()`, `_apply_plan_limits()`, `_get_static_denial_reason()`, `_build_access_status()`, `_trial_days_left()`, `_billable_minutes()`.
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
