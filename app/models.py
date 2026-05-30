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
    result_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    response_mode: Mapped[str] = mapped_column(String(20), default="short")
    is_unlimited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
