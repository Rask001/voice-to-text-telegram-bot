import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.config import Settings
from app.db import create_session_factory
from app.reminder_scheduler import process_due_reminders_once
from app.reminder_service import (
    REMINDER_STATUS_CANCELLED,
    REMINDER_STATUS_COMPLETED,
    REMINDER_STATUS_PENDING,
    REMINDER_STATUS_SENT,
    cancel_reminder,
    complete_reminder,
    create_reminder,
    get_due_reminders,
    get_reminder_by_id,
    get_user_reminders,
    mark_reminder_sent,
)


class FakeBot:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )


class ReminderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "reminders.db"
        self.settings = Settings(
            telegram_bot_token="test-token",
            openai_api_key="test-key",
            database_url=f"sqlite:///{db_path}",
        )
        self.session_factory = create_session_factory(self.settings)

    def tearDown(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()
        self.tmpdir.cleanup()

    def test_create_reminder_creates_pending_reminder(self) -> None:
        remind_at = datetime.now() + timedelta(hours=1)
        with self.session_factory() as session:
            reminder = create_reminder(session, 1, "Позвонить", remind_at)
            session.commit()

        with self.session_factory() as session:
            reminders = get_user_reminders(session, 1)

        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].id, reminder.id)
        self.assertEqual(reminders[0].status, REMINDER_STATUS_PENDING)
        self.assertEqual(reminders[0].task_text, "Позвонить")

    def test_get_user_reminders_returns_only_user_reminders(self) -> None:
        now = datetime.now()
        with self.session_factory() as session:
            create_reminder(session, 1, "Моё", now + timedelta(hours=1))
            create_reminder(session, 2, "Чужое", now + timedelta(hours=1))
            session.commit()

        with self.session_factory() as session:
            reminders = get_user_reminders(session, 1)

        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0].task_text, "Моё")

    def test_get_reminder_by_id_checks_owner(self) -> None:
        with self.session_factory() as session:
            reminder = create_reminder(session, 1, "Секрет", datetime.now())
            reminder_id = reminder.id
            session.commit()

        with self.session_factory() as session:
            own = get_reminder_by_id(session, reminder_id, telegram_id=1)
            foreign = get_reminder_by_id(session, reminder_id, telegram_id=2)

        self.assertIsNotNone(own)
        self.assertIsNone(foreign)

    def test_cancel_reminder_sets_cancelled(self) -> None:
        with self.session_factory() as session:
            reminder = create_reminder(session, 1, "Отменить", datetime.now())
            cancel_reminder(session, reminder)
            session.commit()

        with self.session_factory() as session:
            reminders = get_user_reminders(session, 1, {REMINDER_STATUS_CANCELLED})

        self.assertEqual(reminders[0].status, REMINDER_STATUS_CANCELLED)
        self.assertIsNotNone(reminders[0].cancelled_at)

    def test_complete_reminder_sets_completed(self) -> None:
        with self.session_factory() as session:
            reminder = create_reminder(session, 1, "Сделать", datetime.now())
            complete_reminder(session, reminder)
            session.commit()

        with self.session_factory() as session:
            reminders = get_user_reminders(session, 1, {REMINDER_STATUS_COMPLETED})

        self.assertEqual(reminders[0].status, REMINDER_STATUS_COMPLETED)
        self.assertIsNotNone(reminders[0].completed_at)

    def test_get_due_reminders_returns_only_pending_due(self) -> None:
        now = datetime.now()
        with self.session_factory() as session:
            create_reminder(session, 1, "Пора", now - timedelta(minutes=1))
            create_reminder(session, 1, "Рано", now + timedelta(minutes=1))
            sent = create_reminder(session, 1, "Уже отправлено", now - timedelta(minutes=1))
            mark_reminder_sent(session, sent, now)
            session.commit()

        with self.session_factory() as session:
            due = get_due_reminders(session, now)

        self.assertEqual([reminder.task_text for reminder in due], ["Пора"])

    def test_inactive_reminders_are_not_due(self) -> None:
        now = datetime.now()
        with self.session_factory() as session:
            sent = create_reminder(session, 1, "Sent", now - timedelta(minutes=1))
            done = create_reminder(session, 1, "Done", now - timedelta(minutes=1))
            cancelled = create_reminder(session, 1, "Cancelled", now - timedelta(minutes=1))
            mark_reminder_sent(session, sent, now)
            complete_reminder(session, done, now)
            cancel_reminder(session, cancelled, now)
            session.commit()

        with self.session_factory() as session:
            due = get_due_reminders(session, now)

        self.assertEqual(due, [])

    def test_scheduler_does_not_send_reminder_twice(self) -> None:
        now = datetime.now()
        with self.session_factory() as session:
            create_reminder(session, 1, "Одно сообщение", now - timedelta(minutes=1))
            session.commit()

        bot = FakeBot()
        asyncio.run(process_due_reminders_once(bot, self.session_factory, now=now))
        asyncio.run(process_due_reminders_once(bot, self.session_factory, now=now))

        self.assertEqual(len(bot.messages), 1)
        self.assertIn("Одно сообщение", bot.messages[0]["text"])

    def test_scheduler_does_not_send_before_remind_at(self) -> None:
        now = datetime(2026, 6, 1, 23, 26)
        with self.session_factory() as session:
            create_reminder(session, 1, "Ровно в половину", now + timedelta(minutes=4))
            session.commit()

        bot = FakeBot()
        sent_count = asyncio.run(
            process_due_reminders_once(
                bot,
                self.session_factory,
                settings=self.settings,
                now=now,
            )
        )

        self.assertEqual(sent_count, 0)
        self.assertEqual(bot.messages, [])


if __name__ == "__main__":
    unittest.main()
