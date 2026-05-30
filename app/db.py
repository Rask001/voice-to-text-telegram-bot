from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return

    db_path = Path(database_url.removeprefix("sqlite:///"))
    if db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    import app.models  # noqa: F401

    _ensure_sqlite_parent(settings.database_url)
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_engine(settings.database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    _ensure_sqlite_schema_updates(engine, settings.database_url)
    return sessionmaker(engine, expire_on_commit=False)


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


def _add_text_column(connection, columns: set[str], table_name: str, column_name: str) -> None:
    if column_name not in columns:
        connection.execute(
            text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT DEFAULT ''")
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
