import tempfile
import unittest
from pathlib import Path

from app.admin_service import (
    DEFAULT_START_TEXT,
    add_friend_tariff,
    create_database_backup,
    get_start_text,
    normalize_admin_tariff,
    remove_friend_tariff,
    reset_start_text,
    set_start_text,
    set_user_tariff,
)
from app.config import Settings
from app.db import create_session_factory
from app.models import UserSettings
from app.tariffs import BROTHER, FREE, PREMIUM


class AdminServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "admin.db"
        self.settings = Settings(
            telegram_bot_token="test-token",
            openai_api_key="test-key",
            database_url=f"sqlite:///{self.db_path}",
            owner_telegram_id=1,
        )
        self.session_factory = create_session_factory(self.settings)

    def tearDown(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()
        self.tmpdir.cleanup()

    def test_set_and_reset_start_text(self) -> None:
        with self.session_factory() as session:
            set_start_text(session, "Новый старт")
            session.commit()

        with self.session_factory() as session:
            self.assertEqual(get_start_text(session), "Новый старт")
            reset_start_text(session)
            session.commit()

        with self.session_factory() as session:
            self.assertEqual(get_start_text(session), DEFAULT_START_TEXT)

    def test_set_tariff_changes_user_tariff(self) -> None:
        with self.session_factory() as session:
            set_user_tariff(session, 123, "premium")
            session.commit()

        with self.session_factory() as session:
            user = session.query(UserSettings).filter_by(telegram_user_id=123).one()
            self.assertEqual(user.tariff_type, PREMIUM)
            self.assertTrue(user.is_premium)

    def test_unknown_admin_tariff_is_rejected(self) -> None:
        self.assertIsNone(normalize_admin_tariff("banana"))

    def test_add_friend_sets_brother_tariff(self) -> None:
        with self.session_factory() as session:
            add_friend_tariff(session, 123)
            session.commit()

        with self.session_factory() as session:
            user = session.query(UserSettings).filter_by(telegram_user_id=123).one()
            self.assertEqual(user.tariff_type, BROTHER)
            self.assertTrue(user.is_unlimited)

    def test_remove_friend_returns_free(self) -> None:
        with self.session_factory() as session:
            add_friend_tariff(session, 123)
            remove_friend_tariff(session, 123)
            session.commit()

        with self.session_factory() as session:
            user = session.query(UserSettings).filter_by(telegram_user_id=123).one()
            self.assertEqual(user.tariff_type, FREE)
            self.assertFalse(user.is_unlimited)

    def test_backup_creates_file(self) -> None:
        backup_path = create_database_backup(self.settings)

        self.assertTrue(backup_path.exists())
        self.assertIn("bot_backup_", backup_path.name)


if __name__ == "__main__":
    unittest.main()
