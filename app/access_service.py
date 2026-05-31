from sqlalchemy.orm import Session

from app.access import AccessStatus, check_voice_access, get_access_status
from app.config import Settings


def check_user_access(
    session: Session,
    user_id: int,
    username: str | None,
    settings: Settings,
    duration_seconds: int | None = None,
) -> AccessStatus:
    if duration_seconds is None:
        return get_access_status(session, user_id, username, settings)
    return check_voice_access(session, user_id, username, settings, duration_seconds)
