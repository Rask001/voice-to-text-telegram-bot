from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DailyUsage(Base):
    __tablename__ = "daily_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    usage_date: Mapped[date] = mapped_column(Date, index=True)
    voice_count: Mapped[int] = mapped_column(Integer, default=0)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tariff_type: Mapped[str] = mapped_column(String(30), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        server_default=func.now(),
        index=True,
    )


class VoiceNote(Base):
    __tablename__ = "voice_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_file_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(120), default="")
    duration_seconds: Mapped[int] = mapped_column(Integer)
    transcript: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    action_items: Mapped[str] = mapped_column(Text)
    important_points: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[str] = mapped_column(Text, default="")
    full_text_message_ids: Mapped[str] = mapped_column(Text, default="")
    details_message_ids: Mapped[str] = mapped_column(Text, default="")
    tasks_message_ids: Mapped[str] = mapped_column(Text, default="")
    share_message_ids: Mapped[str] = mapped_column(Text, default="")
    analysis_message_ids: Mapped[str] = mapped_column(Text, default="")
    voice_analysis_json: Mapped[str] = mapped_column(Text, default="")
    result_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    transcription_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    task_text: Mapped[str] = mapped_column(Text)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="telegram_stars", index=True)
    currency: Mapped[str] = mapped_column(String(10), default="XTR")
    amount: Mapped[int] = mapped_column(Integer)
    tariff: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[str] = mapped_column(String(255), index=True)
    telegram_payment_charge_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    provider_payment_charge_id: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        server_default=func.now(),
        index=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    response_mode: Mapped[str] = mapped_column(String(20), default="short")
    is_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    tariff_type: Mapped[str] = mapped_column(String(30), default="free")
    registration_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    trial_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    minutes_used_total: Mapped[int] = mapped_column(Integer, default=0)
    minutes_limit_total: Mapped[int] = mapped_column(Integer, default=15)
    minutes_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    minutes_limit_month: Mapped[int] = mapped_column(Integer, default=15)
    voices_used_today: Mapped[int] = mapped_column(Integer, default=0)
    daily_voice_limit: Mapped[int] = mapped_column(Integer, default=3)
    total_saved_seconds: Mapped[int] = mapped_column(Integer, default=0)
    tariff_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    usage_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    minutes_month_key: Mapped[str] = mapped_column(String(7), default="")
