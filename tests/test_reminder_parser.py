import unittest
from datetime import datetime, timedelta

from app.reminder_parser import (
    parse_reminder_text,
    parse_reminder_request,
    parse_reminder_time_text,
)


class ReminderParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 1, 12, 0)

    def test_relative_10_minutes(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через 10 минут", now=self.now),
            self.now + timedelta(minutes=10),
        )

    def test_relative_1_minute(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через 1 минуту", now=self.now),
            self.now + timedelta(minutes=1),
        )

    def test_relative_30_minutes(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через 30 минут", now=self.now),
            self.now + timedelta(minutes=30),
        )

    def test_relative_1_hour(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через 1 час", now=self.now),
            self.now + timedelta(hours=1),
        )

    def test_relative_one_minute_without_number(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через минуту", now=self.now),
            self.now + timedelta(minutes=1),
        )

    def test_relative_number_without_unit_defaults_to_minutes(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через 10", now=self.now),
            self.now + timedelta(minutes=10),
        )

    def test_relative_half_hour_with_space(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через пол часа", now=self.now),
            self.now + timedelta(minutes=30),
        )

    def test_relative_half_hour_one_word(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("через полчаса", now=self.now),
            self.now + timedelta(minutes=30),
        )

    def test_tomorrow_time(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("завтра 14:30", now=self.now),
            datetime(2026, 6, 2, 14, 30),
        )

    def test_ambiguous_tomorrow_at_5_requires_clarification(self) -> None:
        parsed = parse_reminder_text(
            "разбуди меня завтра в 11:00",
            now=datetime(2026, 6, 2, 5, 0),
        )

        self.assertFalse(parsed.success)
        self.assertTrue(parsed.needs_tomorrow_clarification)
        self.assertEqual(parsed.clarification_today_at, datetime(2026, 6, 2, 11, 0))
        self.assertEqual(parsed.clarification_nextday_at, datetime(2026, 6, 3, 11, 0))
        self.assertEqual(parsed.task_text, "разбуди меня")

    def test_ambiguous_tomorrow_morning_at_2_requires_clarification(self) -> None:
        parsed = parse_reminder_text(
            "разбуди меня завтра утром",
            now=datetime(2026, 6, 2, 2, 0),
        )

        self.assertTrue(parsed.needs_tomorrow_clarification)
        self.assertEqual(parsed.clarification_today_at, datetime(2026, 6, 2, 9, 0))
        self.assertEqual(parsed.clarification_nextday_at, datetime(2026, 6, 3, 9, 0))

    def test_tomorrow_after_6_does_not_require_clarification(self) -> None:
        parsed = parse_reminder_text(
            "разбуди меня завтра в 11:00",
            now=datetime(2026, 6, 2, 7, 0),
        )

        self.assertTrue(parsed.success)
        self.assertFalse(parsed.needs_tomorrow_clarification)
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 3, 11, 0))

    def test_day_after_tomorrow_does_not_require_clarification(self) -> None:
        parsed = parse_reminder_text(
            "разбуди меня послезавтра в 11:00",
            now=datetime(2026, 6, 2, 2, 0),
        )

        self.assertFalse(parsed.needs_tomorrow_clarification)
        self.assertTrue(parsed.success)
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 4, 11, 0))

    def test_relative_days_do_not_require_tomorrow_clarification(self) -> None:
        parsed = parse_reminder_text(
            "разбуди меня через два дня в 11:00",
            now=datetime(2026, 6, 2, 2, 0),
        )

        self.assertFalse(parsed.needs_tomorrow_clarification)
        self.assertTrue(parsed.success)
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 4, 11, 0))

        parsed_next_day = parse_reminder_text(
            "разбуди меня через день в 11:00",
            now=datetime(2026, 6, 2, 2, 0),
        )

        self.assertFalse(parsed_next_day.needs_tomorrow_clarification)
        self.assertTrue(parsed_next_day.success)
        self.assertEqual(parsed_next_day.remind_at, datetime(2026, 6, 3, 11, 0))

    def test_explicit_date_does_not_require_clarification(self) -> None:
        parsed = parse_reminder_text(
            "разбуди меня 03.06 в 11:00",
            now=datetime(2026, 6, 2, 2, 0),
        )

        self.assertTrue(parsed.success)
        self.assertFalse(parsed.needs_tomorrow_clarification)
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 3, 11, 0))

    def test_tomorrow_morning(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("завтра утром", now=self.now),
            datetime(2026, 6, 2, 9, 0),
        )

    def test_tomorrow_day(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("завтра днём", now=self.now),
            datetime(2026, 6, 2, 12, 0),
        )

    def test_tomorrow_evening(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("завтра вечером", now=self.now),
            datetime(2026, 6, 2, 18, 0),
        )

    def test_time_only_today_if_still_ahead(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("18:00", now=self.now),
            datetime(2026, 6, 1, 18, 0),
        )

    def test_time_only_tomorrow_if_already_passed(self) -> None:
        self.assertEqual(
            parse_reminder_time_text("18:00", now=datetime(2026, 6, 1, 19, 0)),
            datetime(2026, 6, 2, 18, 0),
        )

    def test_invalid_format(self) -> None:
        self.assertIsNone(parse_reminder_time_text("когда-нибудь потом", now=self.now))

    def test_parse_reminder_command_request(self) -> None:
        parsed = parse_reminder_request(
            "через 30 минут проверить бота",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=30))
        self.assertEqual(parsed.task_text, "проверить бота")

    def test_parse_relative_without_number_request(self) -> None:
        parsed = parse_reminder_request(
            "через минуту проверить бота",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=1))
        self.assertEqual(parsed.task_text, "проверить бота")

    def test_parse_relative_without_unit_request(self) -> None:
        parsed = parse_reminder_request(
            "через 10 проверить бота",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=10))
        self.assertEqual(parsed.task_text, "проверить бота")

    def test_parse_relative_half_hour_request(self) -> None:
        parsed = parse_reminder_request(
            "через пол часа проверить бота",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=30))
        self.assertEqual(parsed.task_text, "проверить бота")

    def test_parse_embedded_relative_request(self) -> None:
        parsed = parse_reminder_request(
            "проверить бота через 10 минут",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=10))
        self.assertEqual(parsed.task_text, "проверить бота")

    def test_parse_task_with_embedded_time_today(self) -> None:
        parsed = parse_reminder_request(
            "позвонить Соне в 21:21",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 1, 21, 21))
        self.assertEqual(parsed.task_text, "позвонить Соне")

    def test_parse_task_with_embedded_time_tomorrow_if_passed(self) -> None:
        parsed = parse_reminder_request(
            "позвонить Соне в 21:21",
            now=datetime(2026, 6, 1, 22, 0),
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 2, 21, 21))
        self.assertEqual(parsed.task_text, "позвонить Соне")

    def test_parse_task_with_embedded_today_time(self) -> None:
        parsed = parse_reminder_request(
            "позвонить Соне сегодня в 21:21",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 1, 21, 21))
        self.assertEqual(parsed.task_text, "позвонить Соне")

    def test_parse_task_with_embedded_tomorrow_time(self) -> None:
        parsed = parse_reminder_request(
            "позвонить Соне завтра в 09:00",
            now=self.now,
        )

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.remind_at, datetime(2026, 6, 2, 9, 0))
        self.assertEqual(parsed.task_text, "позвонить Соне")

    def test_natural_minute_phrases(self) -> None:
        cases = [
            ("через минуту поставить угли", 1, "поставить угли"),
            ("поставить угли через минуту", 1, "поставить угли"),
            ("через 10 минут проверить бота", 10, "проверить бота"),
            ("минут через 15 проверить бота", 15, "проверить бота"),
            ("через полчаса проверить бота", 30, "проверить бота"),
            ("через пол часа проверить бота", 30, "проверить бота"),
            ("через пол-часа проверить бота", 30, "проверить бота"),
            ("через полчасика проверить бота", 30, "проверить бота"),
            ("через пару минут проверить бота", 2, "проверить бота"),
            ("через несколько минут проверить бота", 5, "проверить бота"),
            ("через сорок минут проверить бота", 40, "проверить бота"),
        ]
        for text, minutes, task_text in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=minutes))
                self.assertEqual(parsed.task_text, task_text)

    def test_natural_hour_phrases(self) -> None:
        cases = [
            ("через час позвонить Соне", 1, "позвонить Соне"),
            ("позвонить Соне через час", 1, "позвонить Соне"),
            ("через часик позвонить Соне", 1, "позвонить Соне"),
            ("через 2 часа проверить бота", 2, "проверить бота"),
            ("через два часа проверить бота", 2, "проверить бота"),
            ("через три часа проверить бота", 3, "проверить бота"),
            ("часа через 2 проверить бота", 2, "проверить бота"),
            ("часов через 5 проверить бота", 5, "проверить бота"),
            ("через пару часов проверить бота", 2, "проверить бота"),
            ("через несколько часов проверить бота", 3, "проверить бота"),
        ]
        for text, hours, task_text in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.remind_at, self.now + timedelta(hours=hours))
                self.assertEqual(parsed.task_text, task_text)

    def test_mixed_relative_time_phrases(self) -> None:
        cases = [
            ("через 1 час 30 минут проверить бота", 90),
            ("через час 30 минут проверить бота", 90),
            ("через полтора часа проверить бота", 90),
            ("через 1.5 часа проверить бота", 90),
            ("через 2 часа 15 минут проверить бота", 135),
        ]
        for text, minutes in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=minutes))
                self.assertEqual(parsed.task_text, "проверить бота")

    def test_service_words_are_removed(self) -> None:
        cases = [
            (
                "Напомни через минуту мне поставить угли от кальяна",
                "поставить угли от кальяна",
            ),
            (
                "Поставь напоминание через 10 минут чтобы проверить бота",
                "проверить бота",
            ),
            (
                "Минут через 10 напомни поставить угли",
                "поставить угли",
            ),
        ]
        for text, task_text in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.task_text, task_text)

    def test_time_at_start_and_with_preposition(self) -> None:
        cases = [
            ("позвонить Соне в 21:21", datetime(2026, 6, 1, 21, 21), "позвонить Соне"),
            ("в 21:21 позвонить Соне", datetime(2026, 6, 1, 21, 21), "позвонить Соне"),
            ("на 21:21 поставить угли", datetime(2026, 6, 1, 21, 21), "поставить угли"),
            ("поставить угли на 21:21", datetime(2026, 6, 1, 21, 21), "поставить угли"),
            ("завтра 14:30 заехать в сервис", datetime(2026, 6, 2, 14, 30), "заехать в сервис"),
            ("завтра в 09:00 проверить бота", datetime(2026, 6, 2, 9, 0), "проверить бота"),
            ("сегодня в 18:00 оплатить сервер", datetime(2026, 6, 1, 18, 0), "оплатить сервер"),
        ]
        for text, remind_at, task_text in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.remind_at, remind_at)
                self.assertEqual(parsed.task_text, task_text)

    def test_day_parts(self) -> None:
        cases = [
            ("завтра утром позвонить Соне", datetime(2026, 6, 2, 9, 0), "позвонить Соне"),
            ("позвонить Соне завтра вечером", datetime(2026, 6, 2, 18, 0), "позвонить Соне"),
            ("сегодня вечером проверить бота", datetime(2026, 6, 1, 18, 0), "проверить бота"),
            ("сегодня ночью проверить бота", datetime(2026, 6, 1, 22, 0), "проверить бота"),
        ]
        for text, remind_at, task_text in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.remind_at, remind_at)
                self.assertEqual(parsed.task_text, task_text)

    def test_weekdays(self) -> None:
        cases = [
            ("в пятницу позвонить Соне", datetime(2026, 6, 5, 10, 0), "позвонить Соне"),
            ("в пятницу в 14:30 позвонить Соне", datetime(2026, 6, 5, 14, 30), "позвонить Соне"),
            ("позвонить Соне в пятницу вечером", datetime(2026, 6, 5, 18, 0), "позвонить Соне"),
            ("следующий понедельник проверить бота", datetime(2026, 6, 8, 10, 0), "проверить бота"),
            ("в ближайшую пятницу проверить бота", datetime(2026, 6, 5, 10, 0), "проверить бота"),
        ]
        for text, remind_at, task_text in cases:
            with self.subTest(text=text):
                parsed = parse_reminder_text(text, now=self.now)
                self.assertTrue(parsed.success)
                self.assertEqual(parsed.remind_at, remind_at)
                self.assertEqual(parsed.task_text, task_text)

    def test_no_time_does_not_create_reminder(self) -> None:
        parsed = parse_reminder_text("поставить угли от кальяна", now=self.now)

        self.assertFalse(parsed.success)
        self.assertIsNone(parsed.remind_at)
        self.assertEqual(parsed.error, "time_not_found")

    def test_time_without_task_needs_task(self) -> None:
        parsed = parse_reminder_text("через 10 минут", now=self.now)

        self.assertFalse(parsed.success)
        self.assertEqual(parsed.remind_at, self.now + timedelta(minutes=10))
        self.assertTrue(parsed.needs_task)
        self.assertEqual(parsed.error, "missing_task")


if __name__ == "__main__":
    unittest.main()
