# Инструкция: как обновлять бота через GitHub и удалённый Mac

Эта инструкция для обычного рабочего сценария:

```text
меняем код локально
↓
отправляем изменения на GitHub
↓
обновляем удалённый Mac
↓
бот перезапускается и работает 24/7
```

## 0. Что уже настроено

Локальный проект:

```bash
/Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12
```

GitHub:

```text
https://github.com/Rask001/voice-to-text-telegram-bot
```

Удалённый Mac:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104
```

Проект на удалённом Mac:

```bash
/Users/niki4ka/Projects/voice-to-text-telegram-bot
```

Бот на удалённом Mac запускается через `launchd`:

```bash
~/Library/LaunchAgents/com.voitext.bot.plist
```

Важно:

- `.env` не хранится в GitHub;
- `data/bot.db` не хранится в GitHub;
- логи не хранятся в GitHub;
- основной рабочий бот сейчас запущен на удалённом Mac;
- локально не запускай бота с тем же Telegram token, иначе будет Telegram polling conflict.

## 1. Обычный сценарий после разработки

Когда мы добавили новую функцию или исправили баг, нужно сделать 3 шага.

### Самый простой способ

Если рабочий Mac и серверный Mac находятся в одной локальной сети:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12
./deploy_lan.sh
```

Если нужно обновить сервер через Tailscale:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12
./deploy_tailscale.sh
```

Оба скрипта:

```text
1. показывают локальный git status;
2. спрашивают название коммита;
3. запускают compileall и unittest;
4. делают git add, commit и push;
5. заходят на сервер по SSH;
6. запускают там ./deploy.sh;
7. показывают ./status.sh.
```

`deploy_tailscale.sh` дополнительно проверяет SSH через Tailscale. Если Hupp снова перехватил маршрут, скрипт запускает `fix_tailscale_route.sh`. Hupp при этом не отключается и не перезапускается.

### Шаг 1. Проверить проект локально

Открой Terminal на своём Mac и перейди в проект:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12
```

Проверь код:

```bash
.venv/bin/python -m compileall app tests
.venv/bin/python -m unittest discover -s tests
```

Если тесты прошли, можно отправлять код.

## 2. Как отправить изменения на GitHub

Посмотреть, что изменилось:

```bash
git status
```

Добавить изменения:

```bash
git add .
```

Создать коммит:

```bash
git commit -m "Коротко описать изменение"
```

Примеры сообщений:

```bash
git commit -m "Improve history buttons"
git commit -m "Add admin analytics"
git commit -m "Fix tariff limits"
```

Отправить на GitHub:

```bash
git push origin main
```

Проверить, что локальная ветка чистая:

```bash
git status
```

Нормальный результат:

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

## 3. Как обновить бота на удалённом Mac

После `git push` выполни одну команду:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./deploy.sh'
```

Что делает `deploy.sh`:

```text
1. заходит в проект на сервере;
2. делает git pull;
3. обновляет Python-зависимости;
4. безопасно перезапускает бота через launchd;
5. показывает статус.
```

Если всё хорошо, в конце увидишь примерно:

```text
Bot process found:
... Python ... -m app.main
```

## 4. Как проверить, что бот работает

Проверить статус:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./status.sh'
```

## Если Tailscale SSH снова не пускает

Hupp отключать нельзя. Если SSH по Tailscale IP `100.104.17.90` снова зависает, значит Hupp мог перехватить host-route до сервисного Mac.

На рабочем Mac запусти:

```bash
./fix_tailscale_route.sh
```

Скрипт:

```text
1. находит локальный Tailscale IP;
2. находит текущий Tailscale-интерфейс, например utun7;
3. удаляет только route до 100.104.17.90;
4. добавляет route до 100.104.17.90 через Tailscale;
5. не выключает и не перезапускает Hupp.
```

После этого проверь:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@100.104.17.90
```

Статус показывает:

- работает ли бот;
- PID процесса;
- CPU/RAM процесса;
- состояние `launchd`;
- последние строки логов.

## 5. Как перезапустить бота вручную

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./restart.sh'
```

## 6. Как смотреть логи

Логи на удалённом Mac:

```bash
/Users/niki4ka/Projects/voice-to-text-telegram-bot/logs/launchd.out.log
/Users/niki4ka/Projects/voice-to-text-telegram-bot/logs/launchd.err.log
```

Смотреть последние строки:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'tail -80 ~/Projects/voice-to-text-telegram-bot/logs/launchd.err.log'
```

Смотреть лог в реальном времени:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'tail -f ~/Projects/voice-to-text-telegram-bot/logs/launchd.err.log'
```

Остановить просмотр `tail -f`:

```text
Ctrl + C
```

## 7. Если изменились зависимости

Если мы поменяли `requirements.txt`, ничего особенного делать не нужно.

Обычная команда деплоя сама выполнит:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

То есть снова достаточно:

```bash
git push origin main
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./deploy.sh'
```

## 8. Если нужно изменить .env на сервере

`.env` не обновляется через GitHub.

Чтобы открыть `.env` на сервере:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104
cd ~/Projects/voice-to-text-telegram-bot
nano .env
```

После изменения `.env` перезапусти бота:

```bash
./restart.sh
```

Выйти из SSH:

```bash
exit
```

Важно:

- не добавляй `.env` в git;
- не отправляй `.env` в GitHub;
- не вставляй токены в код.

## 9. Если GitHub не принимает push

Если видишь ошибку вроде:

```text
Updates were rejected because the remote contains work that you do not have locally
```

Сделай:

```bash
git pull origin main
```

Если конфликтов нет:

```bash
git push origin main
```

Если появились конфликты, лучше остановиться и попросить Codex помочь.

## 10. Если бот не запускается после деплоя

Проверить статус:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./status.sh'
```

Посмотреть ошибки:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'tail -120 ~/Projects/voice-to-text-telegram-bot/logs/launchd.err.log'
```

Частые причины:

- ошибка в коде;
- не прошли тесты;
- неправильный `.env`;
- закончилась OpenAI quota;
- нет интернета/VPN;
- локально запущен второй экземпляр этого же Telegram-бота.

## 11. Если Telegram пишет Conflict

Ошибка:

```text
Conflict: terminated by other getUpdates request
```

Значит один и тот же Telegram bot token запущен в двух местах.

Что делать:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12
./stop.sh
```

И проверить сервер:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./status.sh'
```

## 12. Как скачать свежую версию с GitHub локально

Если на GitHub появились изменения, а локально их ещё нет:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12
git pull origin main
```

## 13. Мини-шпаргалка

Полный стандартный цикл:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12

./deploy_lan.sh
```

Через Tailscale:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12

./deploy_tailscale.sh
```

Ручной вариант, если хочется пройти все шаги самому:

```bash
cd /Users/tosha/Documents/Codex/2026-05-29/telegram-python-mvp-python-3-12

.venv/bin/python -m compileall app tests
.venv/bin/python -m unittest discover -s tests

git status
git add .
git commit -m "Describe change"
git push origin main

ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./deploy.sh'
```

Проверка сервера:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./status.sh'
```

Перезапуск сервера:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'cd ~/Projects/voice-to-text-telegram-bot && ./restart.sh'
```

Логи:

```bash
ssh -i ~/.ssh/codex_remote_mac niki4ka@192.168.1.104 'tail -f ~/Projects/voice-to-text-telegram-bot/logs/launchd.err.log'
```

## 14. Что нужно помнить

- GitHub хранит код.
- Сервер хранит рабочую копию, `.env`, SQLite базу и логи.
- `.env` и `bot.db` не коммитим.
- После `git push` сервер сам не обновится, пока не выполнить `./deploy.sh`.
- Локального и серверного бота нельзя держать одновременно с одним Telegram token.
- Перед деплоем желательно всегда запускать тесты.

## 15. Как сделать PDF

Открой этот файл на Mac и выбери:

```text
File → Print → Save as PDF
```

Или можно открыть его в редакторе Markdown и экспортировать в PDF.
