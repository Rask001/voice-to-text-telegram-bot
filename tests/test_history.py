import inspect
import unittest
from datetime import datetime

from app.formatters import format_history_item
from app.handlers import history_callback, history_note_callback
from app.models import VoiceNote


class HistoryTests(unittest.TestCase):
    def test_history_item_uses_saved_data(self) -> None:
        note = VoiceNote(
            telegram_user_id=1,
            telegram_file_id="file",
            title="Тестовая запись",
            duration_seconds=10,
            transcript="Полный текст",
            summary="Кратко",
            action_items='[{"text":"Оплатить сервер","priority":true}]',
            details="Детали",
            important_points="",
        )
        note.created_at = datetime.now()

        rendered = format_history_item(note)

        self.assertIn("Тестовая запись", rendered)
        self.assertIn("<b>Оплатить сервер</b> ❗", rendered)

    def test_history_callbacks_do_not_require_openai_service(self) -> None:
        history_params = inspect.signature(history_callback).parameters
        history_note_params = inspect.signature(history_note_callback).parameters

        self.assertNotIn("openai_service", history_params)
        self.assertNotIn("openai_service", history_note_params)


if __name__ == "__main__":
    unittest.main()
