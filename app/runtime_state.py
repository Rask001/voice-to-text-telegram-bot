from datetime import datetime


APP_STARTED_AT = datetime.now()
REMINDER_SCHEDULER_STARTED = False


def mark_reminder_scheduler_started() -> None:
    global REMINDER_SCHEDULER_STARTED
    REMINDER_SCHEDULER_STARTED = True


def uptime_seconds() -> int:
    return int((datetime.now() - APP_STARTED_AT).total_seconds())
