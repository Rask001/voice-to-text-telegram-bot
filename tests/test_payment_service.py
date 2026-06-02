import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.config import Settings
from app.db import create_session_factory
from app.models import Payment
from app.payment_service import (
    STARS_CURRENCY,
    activate_paid_tariff,
    can_buy_tariff,
    create_payment_payload,
    expected_amount,
    parse_payment_payload,
    process_successful_payment,
    validate_payment_payload,
)
from app.preferences import get_or_create_user_settings
from app.tariffs import BROTHER, FREE, OWNER, PREMIUM, STANDARD


class PaymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "payments.db"
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

    def test_payload_is_created_and_parsed(self) -> None:
        payload = create_payment_payload(PREMIUM, 123)
        parsed = parse_payment_payload(payload)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tariff, PREMIUM)
        self.assertEqual(parsed.telegram_id, 123)

    def test_unknown_tariff_payload_rejects(self) -> None:
        ok, reason, parsed = validate_payment_payload(
            "stars:banana:123:1:nonce",
            123,
            STARS_CURRENCY,
            499,
        )

        self.assertFalse(ok)
        self.assertIsNone(parsed)
        self.assertIn("payload", reason or "")

    def test_successful_payment_activates_tariff(self) -> None:
        payload = create_payment_payload(STANDARD, 123)

        with self.session_factory() as session:
            result = process_successful_payment(
                session,
                telegram_id=123,
                payload=payload,
                currency=STARS_CURRENCY,
                amount=expected_amount(STANDARD),
                telegram_payment_charge_id="charge-1",
            )
            session.commit()

        self.assertTrue(result.activated)
        self.assertEqual(result.tariff, STANDARD)
        self.assertIsNotNone(result.expires_at)

        with self.session_factory() as session:
            user = get_or_create_user_settings(session, 123)
            self.assertEqual(user.tariff_type, STANDARD)
            self.assertFalse(user.is_premium)

    def test_duplicate_successful_payment_does_not_extend_twice(self) -> None:
        payload = create_payment_payload(PREMIUM, 123)

        with self.session_factory() as session:
            first = process_successful_payment(
                session,
                telegram_id=123,
                payload=payload,
                currency=STARS_CURRENCY,
                amount=expected_amount(PREMIUM),
                telegram_payment_charge_id="charge-dup",
            )
            session.commit()
            first_expires_at = first.expires_at

        with self.session_factory() as session:
            second = process_successful_payment(
                session,
                telegram_id=123,
                payload=payload,
                currency=STARS_CURRENCY,
                amount=expected_amount(PREMIUM),
                telegram_payment_charge_id="charge-dup",
            )
            session.commit()
            user = get_or_create_user_settings(session, 123)
            paid_count = session.scalar(
                select(func.count()).select_from(Payment).where(Payment.status == "paid")
            )
            duplicate_count = session.scalar(
                select(func.count()).select_from(Payment).where(Payment.status == "duplicate")
            )

        self.assertTrue(second.duplicate)
        self.assertEqual(user.tariff_expires_at, first_expires_at)
        self.assertEqual(paid_count, 1)
        self.assertEqual(duplicate_count, 1)

    def test_owner_and_friend_are_not_overwritten(self) -> None:
        with self.session_factory() as session:
            owner = get_or_create_user_settings(session, 1)
            owner.tariff_type = OWNER
            friend = get_or_create_user_settings(session, 2)
            friend.tariff_type = BROTHER
            friend.is_unlimited = True
            session.commit()

        with self.session_factory() as session:
            owner = get_or_create_user_settings(session, 1)
            friend = get_or_create_user_settings(session, 2)
            self.assertFalse(can_buy_tariff(owner, PREMIUM)[0])
            self.assertFalse(can_buy_tariff(friend, PREMIUM)[0])

    def test_active_premium_extends_from_current_expiration(self) -> None:
        now = datetime.now()
        current_expiration = now + timedelta(days=10)

        with self.session_factory() as session:
            user = get_or_create_user_settings(session, 123)
            user.tariff_type = PREMIUM
            user.is_premium = True
            user.tariff_expires_at = current_expiration
            new_expiration = activate_paid_tariff(user, PREMIUM, now)
            session.commit()

        self.assertEqual(new_expiration, current_expiration + timedelta(days=30))

    def test_wrong_amount_does_not_activate_tariff(self) -> None:
        payload = create_payment_payload(PREMIUM, 123)

        with self.session_factory() as session:
            with self.assertRaises(ValueError):
                process_successful_payment(
                    session,
                    telegram_id=123,
                    payload=payload,
                    currency=STARS_CURRENCY,
                    amount=1,
                    telegram_payment_charge_id="charge-wrong",
                )
            session.commit()

        with self.session_factory() as session:
            user = get_or_create_user_settings(session, 123)
            self.assertEqual(user.tariff_type, FREE)


if __name__ == "__main__":
    unittest.main()
