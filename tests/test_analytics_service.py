import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.analytics_service import get_stats_for_period, track_event
from app.config import Settings
from app.db import create_session_factory
from app.handlers.admin import is_owner_command_user
from app.models import AnalyticsEvent


class AnalyticsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "analytics.db"
        self.settings = Settings(
            telegram_bot_token="test-token",
            openai_api_key="test-key",
            database_url=f"sqlite:///{db_path}",
            owner_telegram_id=1,
        )
        self.session_factory = create_session_factory(self.settings)

    def tearDown(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()
        self.tmpdir.cleanup()

    def test_track_event_creates_event(self) -> None:
        user = SimpleNamespace(id=42, username="tester")

        track_event(
            self.session_factory,
            "voice_received",
            user,
            {"duration_seconds": 125, "unknown": "ignored"},
            settings=self.settings,
        )

        with self.session_factory() as session:
            event = session.query(AnalyticsEvent).one()

        payload = json.loads(event.payload_json)
        self.assertEqual(event.event_name, "voice_received")
        self.assertEqual(event.telegram_id, 42)
        self.assertEqual(event.tariff_type, "free")
        self.assertEqual(payload["duration_seconds"], 125)
        self.assertNotIn("unknown", payload)

    def test_track_event_error_does_not_raise(self) -> None:
        def broken_session_factory():
            raise RuntimeError("db is unavailable")

        with self.assertLogs("app.analytics_service", level="ERROR"):
            track_event(broken_session_factory, "user_started", SimpleNamespace(id=42))

    def test_get_stats_for_period_counts_events(self) -> None:
        now = datetime.now()
        with self.session_factory() as session:
            session.add_all(
                [
                    AnalyticsEvent(
                        event_name="user_started",
                        telegram_id=1,
                        tariff_type="free",
                        payload_json="{}",
                        created_at=now,
                    ),
                    AnalyticsEvent(
                        event_name="voice_received",
                        telegram_id=1,
                        tariff_type="free",
                        payload_json='{"duration_seconds": 120}',
                        created_at=now,
                    ),
                    AnalyticsEvent(
                        event_name="voice_processed_success",
                        telegram_id=1,
                        tariff_type="free",
                        payload_json='{"duration_seconds": 60}',
                        created_at=now,
                    ),
                    AnalyticsEvent(
                        event_name="share_clicked",
                        telegram_id=1,
                        tariff_type="free",
                        payload_json="{}",
                        created_at=now,
                    ),
                ]
            )
            session.commit()

        stats = get_stats_for_period(
            self.session_factory,
            now - timedelta(minutes=1),
            now + timedelta(minutes=1),
        )

        self.assertEqual(stats.new_users, 1)
        self.assertEqual(stats.active_users, 1)
        self.assertEqual(stats.voice_received, 1)
        self.assertEqual(stats.voice_processed_success, 1)
        self.assertEqual(stats.share_clicked, 1)
        self.assertEqual(stats.audio_minutes_received, 2)
        self.assertEqual(stats.audio_minutes_processed, 1)
        self.assertEqual(stats.activation_rate, 1)
        self.assertEqual(stats.success_rate, 1)
        self.assertEqual(stats.share_rate, 1)

    def test_metrics_do_not_fail_with_zero_values(self) -> None:
        now = datetime.now()
        stats = get_stats_for_period(
            self.session_factory,
            now - timedelta(minutes=1),
            now + timedelta(minutes=1),
        )

        self.assertEqual(stats.activation_rate, 0)
        self.assertEqual(stats.success_rate, 0)
        self.assertEqual(stats.limit_block_rate, 0)
        self.assertEqual(stats.share_rate, 0)

    def test_admin_stats_available_for_owner(self) -> None:
        user = SimpleNamespace(id=1, username=None)

        self.assertTrue(is_owner_command_user(user, self.settings))

    def test_admin_stats_denied_for_regular_user(self) -> None:
        user = SimpleNamespace(id=2, username=None)

        self.assertFalse(is_owner_command_user(user, self.settings))


if __name__ == "__main__":
    unittest.main()
