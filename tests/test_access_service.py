import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.access_service import check_user_access
from app.config import Settings
from app.db import create_session_factory
from app.preferences import get_or_create_user_settings
from app.tariffs import BROTHER


class AccessServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test.db"
        self.settings = Settings(
            telegram_bot_token="test-token",
            openai_api_key="test-key",
            database_url=f"sqlite:///{db_path}",
            owner_telegram_id=1,
            unlimited_user_ids=(2,),
        )
        self.session_factory = create_session_factory(self.settings)

    def tearDown(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()
        self.tmpdir.cleanup()

    def test_free_expired_by_days(self) -> None:
        with self.session_factory() as session:
            user_settings = get_or_create_user_settings(session, 100)
            user_settings.registration_date = datetime.now() - timedelta(days=4)
            user_settings.trial_expires_at = datetime.now() - timedelta(days=1)
            session.commit()

            status = check_user_access(session, 100, None, self.settings, 60)

        self.assertFalse(status.can_process)
        self.assertIn("Пробный период закончился", status.denial_reason or "")
        self.assertEqual(status.denial_code, "trial_expired")

    def test_free_expired_by_total_minutes(self) -> None:
        with self.session_factory() as session:
            user_settings = get_or_create_user_settings(session, 101)
            user_settings.minutes_used_total = 15
            session.commit()

            status = check_user_access(session, 101, None, self.settings, 60)

        self.assertFalse(status.can_process)
        self.assertIn("Пробный период закончился", status.denial_reason or "")
        self.assertEqual(status.denial_code, "trial_minutes_limit")

    def test_owner_always_passes(self) -> None:
        with self.session_factory() as session:
            status = check_user_access(session, 1, None, self.settings, 60 * 60)

        self.assertTrue(status.can_process)
        self.assertEqual(status.tariff_type, "owner")
        self.assertIsNone(status.daily_limit)

    def test_brother_tariff_limits(self) -> None:
        with self.session_factory() as session:
            ok_status = check_user_access(session, 2, None, self.settings, 10 * 60)
            denied_status = check_user_access(session, 2, None, self.settings, 10 * 60 + 1)

        self.assertTrue(ok_status.can_process)
        self.assertEqual(ok_status.tariff_type, BROTHER)
        self.assertFalse(denied_status.can_process)
        self.assertIn("Голосовое слишком длинное", denied_status.denial_reason or "")
        self.assertEqual(denied_status.denial_code, "voice_too_long")

    def test_daily_voice_limit_denies_free_user(self) -> None:
        with self.session_factory() as session:
            user_settings = get_or_create_user_settings(session, 102)
            user_settings.usage_date = datetime.now().date()
            user_settings.voices_used_today = 3
            session.commit()

            status = check_user_access(session, 102, None, self.settings, 60)

        self.assertFalse(status.can_process)
        self.assertEqual(status.remaining_today, 0)
        self.assertEqual(status.denial_code, "daily_voice_limit")


if __name__ == "__main__":
    unittest.main()
