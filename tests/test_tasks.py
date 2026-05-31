import unittest

from app.formatters import format_tasks
from app.tasks import normalize_tasks, parse_stored_tasks, serialize_tasks


class TaskNormalizationTests(unittest.TestCase):
    def test_priority_tasks_are_first(self) -> None:
        tasks = normalize_tasks(
            [
                {"text": "Купить молоко", "priority": False},
                {"text": "Купить лекарства", "priority": True},
                {"text": "Купить хлеб", "priority": False},
            ]
        )

        rendered = format_tasks(tasks)

        self.assertIn("1. <b>Купить лекарства</b> ❗", rendered)
        self.assertIn("2. Купить молоко", rendered)
        self.assertIn("3. Купить хлеб", rendered)

    def test_old_string_tasks_are_supported(self) -> None:
        tasks = parse_stored_tasks("Купить молоко\nКупить хлеб")

        self.assertEqual(
            tasks,
            [
                {"text": "Купить молоко", "priority": False},
                {"text": "Купить хлеб", "priority": False},
            ],
        )

    def test_json_roundtrip_preserves_priority(self) -> None:
        tasks = normalize_tasks([{"text": "Оплатить сервер", "priority": True}])

        stored = serialize_tasks(tasks)
        restored = parse_stored_tasks(stored)

        self.assertEqual(restored, [{"text": "Оплатить сервер", "priority": True}])

    def test_empty_tasks_message(self) -> None:
        self.assertIn("Задачи не найдены.", format_tasks([]))


if __name__ == "__main__":
    unittest.main()
