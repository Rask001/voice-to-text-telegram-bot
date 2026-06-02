from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent(database_url: str) -> None:
    database_url = _sync_database_url(database_url)
    if not database_url.startswith("sqlite:///"):
        return

    db_path = Path(database_url.removeprefix("sqlite:///"))
    if db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    import app.models  # noqa: F401

    database_url = _sync_database_url(settings.database_url)
    _ensure_sqlite_parent(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    _ensure_sqlite_schema_updates(engine, database_url)
    return sessionmaker(engine, expire_on_commit=False)


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite:///"):
        return database_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    return database_url


def _ensure_sqlite_schema_updates(engine, database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "voice_notes" in table_names:
            columns = {column["name"] for column in inspector.get_columns("voice_notes")}
            if "title" not in columns:
                connection.execute(
                    text("ALTER TABLE voice_notes ADD COLUMN title VARCHAR(120) DEFAULT ''")
                )
            _add_text_column(connection, columns, "voice_notes", "important_points")
            _add_text_column(connection, columns, "voice_notes", "details")
            _add_text_column(connection, columns, "voice_notes", "full_text_message_ids")
            _add_text_column(connection, columns, "voice_notes", "details_message_ids")
            _add_text_column(connection, columns, "voice_notes", "tasks_message_ids")
            _add_text_column(connection, columns, "voice_notes", "share_message_ids")
            _add_text_column(connection, columns, "voice_notes", "analysis_message_ids")
            _add_text_column(connection, columns, "voice_notes", "voice_analysis_json")
            if "result_message_id" not in columns:
                connection.execute(
                    text("ALTER TABLE voice_notes ADD COLUMN result_message_id INTEGER")
                )

        if "user_settings" in table_names:
            columns = {column["name"] for column in inspector.get_columns("user_settings")}
            if "is_unlimited" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN is_unlimited BOOLEAN DEFAULT 0")
                )
            if "is_premium" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN is_premium BOOLEAN DEFAULT 0")
                )
            if "tariff_type" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN tariff_type VARCHAR(30) DEFAULT 'free'")
                )
            if "registration_date" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN registration_date DATETIME")
                )
            if "trial_expires_at" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN trial_expires_at DATETIME")
                )
            _add_integer_column(connection, columns, "user_settings", "minutes_used_total", 0)
            _add_integer_column(connection, columns, "user_settings", "minutes_limit_total", 15)
            _add_integer_column(connection, columns, "user_settings", "minutes_used_this_month", 0)
            _add_integer_column(connection, columns, "user_settings", "minutes_limit_month", 15)
            _add_integer_column(connection, columns, "user_settings", "voices_used_today", 0)
            _add_integer_column(connection, columns, "user_settings", "daily_voice_limit", 3)
            _add_integer_column(connection, columns, "user_settings", "total_saved_seconds", 0)
            if "tariff_expires_at" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN tariff_expires_at DATETIME")
                )
            if "usage_date" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN usage_date DATE")
                )
            if "minutes_month_key" not in columns:
                connection.execute(
                    text("ALTER TABLE user_settings ADD COLUMN minutes_month_key VARCHAR(7) DEFAULT ''")
                )

        if "analytics_events" in table_names:
            columns = {column["name"] for column in inspector.get_columns("analytics_events")}
            _add_text_column(connection, columns, "analytics_events", "payload_json")
            if "tariff_type" not in columns:
                connection.execute(
                    text("ALTER TABLE analytics_events ADD COLUMN tariff_type VARCHAR(30) DEFAULT ''")
                )


def _add_text_column(connection, columns: set[str], table_name: str, column_name: str) -> None:
    if column_name not in columns:
        connection.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT DEFAULT ''")
        )


def _add_integer_column(
    connection,
    columns: set[str],
    table_name: str,
    column_name: str,
    default: int,
) -> None:
    if column_name not in columns:
        connection.execute(
            text(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} "
                f"INTEGER DEFAULT {default}"
            )
        )


def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
