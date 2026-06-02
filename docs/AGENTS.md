# AGENTS

Практическая инструкция для AI-агентов, работающих с этим проектом.

## Обязательный порядок навигации

1. Сначала откройте `docs/PROJECT_MAP.md`.
2. Если нужна логика потоков, откройте `docs/ARCHITECTURE.md`.
3. Если задача про конкретную возможность, откройте `docs/FEATURES.md`.
4. Затем открывайте только нужные исходные файлы.
5. После изменения архитектуры, публичного поведения, callback data, БД или env обновите docs.

## Быстрые Маршруты

### Если нужно изменить запуск

Читать:

- `app/main.py`
- `app/config.py`
- `start.sh`
- `start_local.sh`
- `stop_local.sh`
- `status_local.sh`
- `Dockerfile`
- `docker-compose.yml`

Проверить:

- `python -m app.main`
- `./start_local.sh`
- `./status_local.sh`
- `./status.sh`

### Если нужно изменить `.env` или настройки

Читать:

- `app/config.py`
- `.env.example`
- `README.md`
- `start_local.sh`

Не делать:

- не выводить реальные значения `.env`;
- не коммитить `.env`, `.env.local`, `.env.production`;
- не использовать production Telegram token для локального polling.

Важно:

- локальная разработка использует `ENV_FILE=.env.local`;
- production/deploy flow по умолчанию продолжает читать `.env`;
- `bot_local_test.db` не должен смешиваться с `data/bot.db`.

### Если нужно изменить AI pipeline или prompt

Читать:

- `app/transcription_service.py`
- `app/text_analysis_service.py`
- `app/voice_metrics_service.py`
- `app/ai_clients/openai_client.py`
- `app/ai_clients/deepseek_client.py`
- `app/voice_analysis.py`, если меняется мемный анализ;
- `docs/ARCHITECTURE.md`, раздел AI Pipeline
- `docs/FEATURES.md`, разделы OpenAI и задач

Проверить:

- OpenAI используется только для audio transcription;
- DeepSeek используется для `summary`, `tasks`, `details`, `important_points`, `verdict`, `meme`, `memorable_quote`;
- локальные метрики считаются в `app/voice_metrics_service.py`;
- `calculate_pre_metrics()` передает DeepSeek `duration_seconds`, `word_count`, `words_per_minute`, `wordiness_score`;
- DeepSeek prompt должен содержать правило: локальные метрики — источник истины;
- JSON keys, которые ожидают `app/text_analysis_service.py`, `app/tasks.py`, `app/handlers/voice.py`;
- fallback на invalid JSON;
- обратную совместимость `action_items`/`tasks`.
- `voice_analysis` от DeepSeek содержит только текстовые творческие поля, без численных метрик;
- prompt для meme должен запрещать мат, унижения и оскорбления личности.

### Если нужно изменить обработку voice

Читать:

- `app/handlers/voice.py`: `handle_voice()`;
- `app/progress_messages.py`: локальные наборы progress messages;
- `app/handlers/utils.py`: `download_voice()`, `convert_to_mp3()`;
- `app/access_service.py`: `check_user_access()`;
- `app/access.py`: `record_voice_usage()`;
- `app/transcription_service.py`;
- `app/text_analysis_service.py`;
- `app/voice_metrics_service.py`.

Проверить:

- лимит до скачивания, ffmpeg, OpenAI и DeepSeek;
- status message;
- progress pack выбирается один раз на voice, каждый pack должен содержать ровно 8 сообщений;
- обычные progress packs живут в `ORDINARY_PROGRESS_PACKS`, редкие легендарные — в `LEGENDARY_PROGRESS_PACKS`;
- progress updater должен листать выбранный набор равномерно с `PROGRESS_UPDATE_INTERVAL_SECONDS` 1.5-2.0 секунды, а не привязывать статусы к реальным этапам OpenAI/SQLite;
- временные файлы удаляются;
- запись появляется в `VoiceNote`;
- inline-кнопки используют SQLite.

### Если нужно изменить историю

Читать:

- `app/handlers/history.py`: `history_command()`, `_send_history()`, `history_callback()`;
- `app/handlers/callbacks.py`: `history_note_callback()`;
- `app/formatters.py`: `format_history()`, `format_history_item()`;
- `app/models.py`: `VoiceNote`.

Важно:

- history callbacks не должны вызывать OpenAI;
- history callbacks должны проверять владельца записи;
- history callbacks могут отправлять блок повторно.

### Если нужно изменить свежие inline-кнопки

Читать:

- `app/handlers/callbacks.py`: `fresh_note_callback()`;
- `app/handlers/keyboards.py`: `note_keyboard()`;
- `app/handlers/utils.py`: `parse_note_action()`.

Важно:

- fresh callbacks используют `fresh_*`;
- старый `note:*` поддерживается для совместимости;
- защита от дублей хранится в полях `*_message_ids`;
- `fresh_analysis` использует `VoiceNote.voice_analysis_json` и `analysis_message_ids`;
- быстрые повторные клики идут через `BUTTON_LOCKS`.

### Если нужно изменить мемный анализ голосового

Читать:

- `app/voice_analysis.py`;
- `app/text_analysis_service.py`;
- `app/voice_metrics_service.py`;
- `app/formatters.py`: `format_voice_analysis()`, `format_share_voice_analysis()`;
- `app/handlers/voice.py`;
- `app/handlers/callbacks.py`;
- `app/handlers/keyboards.py`;
- `app/models.py`: `VoiceNote.voice_analysis_json`, `UserSettings.total_saved_seconds`.

Важно:

- не делать отдельный OpenAI-запрос;
- OpenAI не должен получать prompt для meme/verdict;
- DeepSeek генерирует только `verdict`, `meme`, `memorable_quote`;
- `duration`, `word_count`, `words_per_minute`, `useful_word_count`, `compression_ratio`, `water_percent`, `wordiness_score`, `quality_score`, `saved_seconds`, уровни и редкий титул считает локальный `voice_metrics_service`;
- вода и многословность считаются отдельно: вода через compression ratio, многословность через duration/word count/speech rate;
- `useful_word_count` не должен включать transcript/full_text; details учитывается максимум с весом `0.25`;
- `sanitize_ai_meme_by_metrics()` должен заменять DeepSeek verdict/meme, если они спорят с локальными метриками;
- старые записи без `voice_analysis_json` должны открываться через fallback;
- history callbacks не должны вызывать OpenAI;
- `saved_seconds` всегда `max(0, duration - meaningful_duration)`;
- `total_saved_seconds` увеличивается после успешной новой обработки;
- `voice_type_level` должен оставаться согласованным с `wordiness_score`, а `water_level` — с `water_percent`;
- короткое сообщение до 30 секунд не должно становиться `Подкастером`, `Аудиокнигой` или `Режиссёрской версией`;
- мем должен быть жёстким, цинично-саркастичным и пересылаемым, но без мата, унижений и оскорблений личности;
- шутка должна бить по формату голосового, а не по человеку;
- share-блок должен содержать короткую вирусную версию анализа.

### Если нужно изменить callback data

Читать:

- `app/handlers/keyboards.py`: `note_keyboard()`;
- `app/handlers/utils.py`: `parse_note_action()`;
- `app/handlers/callbacks.py`: fresh/history callback handlers;
- `app/handlers/history.py`: opening history records.
- `docs/FEATURES.md`: sections Inline-Кнопки.

После изменения:

- обновить `docs/ARCHITECTURE.md`;
- обновить `docs/FEATURES.md`;
- проверить старые callback formats, если нужна совместимость.

### Если нужно изменить Reply Keyboard

Читать:

- `app/handlers/constants.py`: constants `MENU_*`;
- `app/handlers/keyboards.py`: `main_keyboard()`;
- `app/handlers/keyboards.py`: `reminders_menu_keyboard()`;
- `app/handlers/menu.py`: `reply_keyboard_handler()`.

Важно:

- основная панель компактная: `🎙 Голосовое | 🔔 Напомни`, `👤 Профиль | 📚 История`, `⚙️ Настройки | ❓ Помощь`;
- `🔔 Напомни` открывает вложенное меню напоминаний: `➕ Создать`, `📋 Текущие`, `⬅️ Назад`;
- старые тексты `🎙 Новое голосовое`, `🔔` и `🔔 Напоминания` должны оставаться совместимыми.

Проверить:

- `/start`;
- `/help`;
- кнопки нижнего меню;
- обычный текст не должен уходить в OpenAI.

### Если нужно изменить профиль

Читать:

- `app/handlers/profile.py`: `profile()`, `my_id()`, `build_profile_text()`;
- `app/formatters.py`: `format_profile()`, `format_my_id()`;
- `app/access_service.py`: `check_user_access()`;
- `app/access.py`: `AccessStatus`;
- `app/tariffs.py`.

Важно:

- Telegram ID не показывается в `/profile`, но доступен отдельной командой `/my_id`;
- owner/friends логика остается внутренней.

### Если нужно изменить тарифы

Читать:

- `app/tariffs.py`;
- `app/access_service.py`;
- `app/access.py`;
- `app/models.py`: `UserSettings`;
- `.env.example`;
- `README.md`.

Проверить:

- Owner;
- По-братски от Тоши;
- Free trial days и total minutes;
- Standard/Premium monthly limits;
- `/profile`;
- кнопка `🎙 Голосовое` и legacy-текст `🎙 Новое голосовое`;
- voice access до OpenAI.

### Если нужно добавить оплату Telegram Stars

Читать:

- `app/access.py`;
- `app/tariffs.py`;
- `app/models.py`;
- `app/handlers/admin.py`;
- future payment handlers inside `app/handlers/`;
- Telegram payment docs отдельно.

Ожидаемая точка расширения:

- после успешной оплаты менять `UserSettings.tariff_type` на `standard` или `premium`;
- не ломать `check_user_access()`.

### Если нужно изменить админские команды

Читать:

- `app/handlers/admin.py`;
- `app/admin_service.py`;
- `app/models.py`: `AppConfig`, `UserSettings`;
- `app/tariffs.py`;
- `app/runtime_state.py`;
- `docs/FEATURES.md`, раздел "Расширенная Админка".

Важно:

- все админские команды должны проверять owner через существующий `is_owner()`;
- обычный пользователь получает `Команда доступна только владельцу бота.`;
- handler должен оставаться тонким, бизнес-логику держать в `app/admin_service.py`;
- стартовый текст хранится в `app_config` под ключом `start_text`;
- `/set_tariff` принимает внешний alias `friend`, но в базе это внутренний тариф `brother`;
- `/admin_backup` пишет копии SQLite в `backups/` и не должен логировать секреты;
- `/admin_broadcast` обязан иметь подтверждение перед отправкой.

### Если нужно изменить аналитику

Читать:

- `app/analytics_service.py`;
- `app/models.py`: `AnalyticsEvent`;
- `app/handlers/admin.py`: `/admin_stats`, `/admin_cleanup_analytics`;
- конкретный handler, где нужно добавить событие.

Важно:

- аналитика пишется только в SQLite;
- не добавлять внешние сервисы без отдельного решения;
- не писать transcript, summary, tasks, OpenAI key, DeepSeek key, Telegram token или другие секреты в `payload_json`;
- `track_event()` должен оставаться best-effort: ошибка аналитики логируется, но не ломает пользовательский сценарий;
- новые события документировать в `docs/FEATURES.md` и `docs/ARCHITECTURE.md`.
- admin stats форматируются в `app/analytics_service.py:format_admin_stats()`;
- минуты в admin stats должны оставаться дробными, чтобы короткие voice не округлялись в 0;
- блокировки в аналитике должны писать стабильный `denial_code`, а не длинный пользовательский текст;
- активные пользователи по тарифам считаются по последнему `tariff_type` пользователя за период;
- блок конверсий в UI должен быть на русском.

### Если нужно изменить напоминания

Читать:

- `app/reminder_service.py`;
- `app/reminder_scheduler.py`;
- `app/reminder_parser.py`;
- `app/handlers/reminders.py`;
- `app/models.py`: `Reminder`;
- `app/handlers/keyboards.py`: reminder keyboards.

Важно:

- handlers не должны напрямую писать в таблицу `reminders`;
- простой текстовый парсер времени живет только в `app/reminder_parser.py` и не использует OpenAI;
- основная точка входа parser — `parse_reminder_text()`, старые функции остаются совместимыми обертками;
- разговорные относительные фразы вроде `через минуту`, `через 10`, `минут через 15`, `через пол часа`, `через пару часов` должны парситься там же;
- `послезавтра`, `через день`, `через два дня` должны парситься как смещения по дням и не попадать в ночное уточнение `завтра`;
- с 00:00 до 05:59 `завтра` без явной даты должно возвращать `needs_tomorrow_clarification=True`; порог хранится в `AMBIGUOUS_TOMORROW_HOUR`;
- уточнение даты использует callback data `reminder_tomorrow_today:`, `reminder_tomorrow_nextday:`, `reminder_tomorrow_cancel:`;
- ручной ввод времени после уже сохраненной задачи тоже должен проходить через `parse_reminder_text()` вместе с `task_text`, чтобы ночное `завтра 11:00` не обходило уточнение;
- service words cleanup (`напомни`, `напомни мне`, `поставь напоминание`, `чтобы`, `пожалуйста`) тоже живет в parser;
- если пользователь в FSM `/remind` прислал текст уже со временем, handler должен сразу создать reminder без меню выбора времени;
- если parser нашел время, но задача пустая, handler должен спросить `Что напомнить?`, а не создавать пустой reminder;
- `/remind <время> <текст>` и FSM `/remind` оба должны создавать записи через `create_reminder()`;
- настройки времени берутся из `DEFAULT_TIMEZONE` и `DEFAULT_REMINDER_TIME`;
- scheduler должен сравнивать due reminders со временем из `DEFAULT_TIMEZONE`, а не с системным `datetime.now()`;
- создание из задач, истории и будущий AI `reminder_candidate` должны идти через `create_reminder()`;
- не менять OpenAI prompt для напоминаний без отдельной задачи;
- не добавлять автоматическое создание напоминаний после каждой расшифровки;
- scheduler защищается от дублей статусами `pending`, `sending`, `sent`.

### Если нужно изменить задачи

Читать:

- `app/text_analysis_service.py`: DeepSeek prompt и JSON mapping;
- `app/tasks.py`: `normalize_tasks()`, `serialize_tasks()`, `parse_stored_tasks()`, `sort_tasks_for_display()`;
- `app/formatters.py`: `format_tasks()`, `format_numbered_list()`;
- `app/handlers/voice.py`: сохранение `VoiceNote.action_items`;
- `app/handlers/callbacks.py`: чтение `VoiceNote.action_items`.

Важно:

- новые задачи хранятся JSON-массивом `{text, priority}`;
- старые newline-задачи должны открываться как `priority=false`;
- все задачи выводятся, не обрезать до 5;
- длинные списки должны идти через `send_html_chunks()`.

### Если нужно изменить кнопку `📤 Поделиться`

Читать:

- `app/handlers/callbacks.py`: `fresh_note_callback()`, `history_note_callback()`.
- `app/formatters.py`: `format_share()`.

Важно:

- fresh share не дублируется;
- history share может отправляться повторно;
- footer: `🎙Создано через: @voitext_bot`.

### Если нужно изменить SQLite

Читать:

- `app/models.py`;
- `app/db.py`;
- `docs/DATABASE_MIGRATIONS.md`;
- места использования модели через `rg "ModelName|column_name" app`.

Важно:

- для SQLite добавлять безопасный `ALTER TABLE` в `_ensure_sqlite_schema_updates()`;
- фиксировать новые поля и ручные миграции в `docs/DATABASE_MIGRATIONS.md`;
- не удалять/переименовывать поля без миграционного плана;
- проверить существующую `data/bot.db`.

### Если нужно очистить историю обработок

Читать:

- `app/models.py`: `VoiceNote`;
- `docs/ARCHITECTURE.md`, раздел SQLite.

Делать:

- удалять строки только из `voice_notes`;
- сохранять `user_settings`, `daily_usage`, schema, `.env`, docs.

Проверить:

- `SELECT COUNT(*) FROM voice_notes` равен 0;
- `/history` показывает пустое состояние.

### Если нужно изменить лимит Telegram message length

Читать:

- `app/handlers/utils.py`: `send_text_chunks()`, `split_for_telegram()`, `send_html_chunks()`, `split_html_for_telegram()`.
- `app/formatters.py`: `TELEGRAM_TEXT_LIMIT`.

Важно:

- plain text transcript экранируется;
- HTML blocks уже содержат теги и режутся как HTML text.

### Если нужно изменить ошибки OpenAI

Читать:

- `app/ai_clients/openai_client.py`;
- `app/transcription_service.py`;
- `app/handlers/voice.py`: `except OpenAIInsufficientQuotaError`, `except RateLimitError`, `except OpenAIError`.

Проверить:

- insufficient_quota не ретраится бесконечно;
- обычный RateLimitError ретраится ограниченно;
- техническая ошибка логируется.

### Если нужно изменить ошибки DeepSeek

Читать:

- `app/ai_clients/deepseek_client.py`;
- `app/text_analysis_service.py`;
- `app/handlers/voice.py`: fallback после успешной transcription.

Важно:

- если DeepSeek недоступен, полный текст должен сохраняться в `VoiceNote.transcript`;
- пользователь получает `Текст расшифрован, но анализ временно недоступен. Попробуйте позже.`;
- OpenAI transcription не повторяется при нажатии inline-кнопок или открытии истории.

### Если нужно изменить `/health`

Читать:

- `app/handlers/system.py`: `health()`, `_check_database()`, `_check_ffmpeg()`;
- `app/handlers/utils.py`: `find_ffmpeg()`.

Важно:

- не делать дорогой OpenAI-запрос;
- проверять только наличие ключа.

### Если нужно изменить unsupported media

Читать:

- `app/handlers/fallbacks.py`: `text_fallback()`, `unsupported_media()`, `fallback()`.

Важно:

- unsupported messages не должны уходить в OpenAI;
- пока поддерживается только `F.voice`.

## Проверки Перед Финалом

Минимум:

```bash
.venv/bin/python -m compileall app
```

Тесты:

```bash
.venv/bin/python -m unittest discover -s tests
```

Для локального бота:

```bash
./status.sh
./stop.sh
./start.sh
```

Для форматтеров можно использовать маленькие `python -c` проверки, но не читать/печатать `.env`.

## Когда Обновлять Документацию

Обновляйте docs, если меняются:

- файлы или структура проекта;
- callback data;
- SQLite schema;
- тарифы и лимиты;
- AI JSON format;
- task normalization format;
- formatter ownership;
- user-facing команды;
- Reply Keyboard или inline buttons;
- Docker/local run flow;
- публичные env variables.

## Не Делать

- Не читать и не печатать реальные секреты из `.env`.
- Не коммитить `data/bot.db`, `.venv/`, логи и временные файлы.
- Не вызывать OpenAI в тестах без явной необходимости.
- Не переписывать архитектуру ради маленькой UX-правки.
- Не убирать compatibility для старых `note:*` callbacks и старых строковых задач без отдельного задания.
