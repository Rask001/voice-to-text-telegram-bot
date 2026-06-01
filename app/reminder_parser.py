import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_REMINDER_TIMEZONE = "Russia/Moscow"
DEFAULT_REMINDER_TIME = "10:00"
_ZONEINFO_FALLBACK_TIMEZONE = "Europe/Moscow"

REMINDER_TIME_CHOICES = {
    "in_1h": "Через 1 час",
    "tomorrow_09": "Завтра 09:00",
    "tomorrow_12": "Завтра 12:00",
    "tomorrow_18": "Завтра 18:00",
}

_TIME_RE = r"(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)"
_PART_TIMES = {
    "утром": time(hour=9),
    "днем": time(hour=12),
    "днём": time(hour=12),
    "вечером": time(hour=18),
    "ночью": time(hour=22),
}
_WEEKDAYS = {
    "понедельник": 0,
    "вторник": 1,
    "среда": 2,
    "среду": 2,
    "четверг": 3,
    "пятница": 4,
    "пятницу": 4,
    "суббота": 5,
    "субботу": 5,
    "воскресенье": 6,
}
_NUMBER_WORDS = {
    "один": 1,
    "одну": 1,
    "одна": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "десять": 10,
    "пятнадцать": 15,
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
}
_NUMBER_TOKEN_RE = (
    r"\d+(?:[\.,]\d+)?|"
    r"один|одну|одна|два|две|три|четыре|пять|десять|"
    r"пятнадцать|двадцать|тридцать|сорок|пятьдесят"
)
_RELATIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bчерез\s+пол[\s-]*час(?:а|ик|ика)?\b", "relative_half_hour"),
    (r"\bчерез\s+полтора\s+часа\b", "relative_one_and_half_hours"),
    (
        rf"\bчерез\s+(?P<hours>{_NUMBER_TOKEN_RE}|час|часик)\s*"
        rf"(?:час(?:а|ов)?|часик)?\s+"
        rf"(?P<minutes>{_NUMBER_TOKEN_RE})\s*мин(?:ут[ауы]?|ут)?\b",
        "relative_hours_minutes",
    ),
    (rf"\bчерез\s+(?P<hours>\d+[\.,]\d+)\s*час(?:а|ов)?\b", "relative_decimal_hours"),
    (r"\bчерез\s+(?P<amount>час|часик)\b", "relative_hours"),
    (
        rf"\bчерез\s+(?P<amount>{_NUMBER_TOKEN_RE}|пару|несколько|часик|час)\s*"
        rf"(?P<unit>час(?:а|ов)?|часик)\b",
        "relative_hours",
    ),
    (
        rf"\b(?:часа|часов|час)\s+через\s+"
        rf"(?P<amount>{_NUMBER_TOKEN_RE}|пару|несколько)\b",
        "relative_hours_reverse",
    ),
    (
        rf"\bчерез\s+минут\s+(?P<amount>{_NUMBER_TOKEN_RE}|пару|несколько)\b",
        "relative_minutes_reversed_after",
    ),
    (
        rf"\bминут\s+через\s+(?P<amount>{_NUMBER_TOKEN_RE}|пару|несколько)\b",
        "relative_minutes_reversed_before",
    ),
    (
        rf"\bчерез\s+(?P<amount>{_NUMBER_TOKEN_RE}|пару|несколько|минуту|минута|минуты|минут|мин)\s*"
        rf"(?P<unit>минут[ауы]?|минут|мин)?\b",
        "relative_minutes",
    ),
)
_WEEKDAY_RE = re.compile(
    r"\b(?:(?:в|во)\s+)?(?P<prefix>следующ(?:ий|ую)|эту|этот|ближайшую|ближайший)?\s*"
    r"(?P<weekday>понедельник|вторник|среду|среда|четверг|пятницу|пятница|"
    r"субботу|суббота|воскресенье)"
    rf"(?:\s+(?:в\s+)?{_TIME_RE}|\s+(?P<part>утром|днем|днём|вечером|ночью))?",
    re.IGNORECASE,
)
_DAY_RE = re.compile(
    rf"\b(?P<day>сегодня|завтра)(?:\s+(?:в\s+)?{_TIME_RE}|\s+(?P<part>утром|днем|днём|вечером|ночью))?\b",
    re.IGNORECASE,
)
_TIME_ONLY_PATTERNS = (
    re.compile(rf"\b(?:в|на)\s+{_TIME_RE}\b", re.IGNORECASE),
    re.compile(rf"^{_TIME_RE}\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ReminderParseResult:
    remind_at: datetime
    task_text: str
    time_text: str


@dataclass(frozen=True)
class ReminderTextParseResult:
    success: bool
    task_text: str
    remind_at: datetime | None
    timezone: str
    matched_pattern: str | None
    error: str | None
    needs_task: bool = False


@dataclass(frozen=True)
class _TimeCandidate:
    start: int
    end: int
    remind_at: datetime
    matched_pattern: str


def parse_reminder_text(
    text: str,
    timezone: str = DEFAULT_REMINDER_TIMEZONE,
    default_time: str = DEFAULT_REMINDER_TIME,
    now: datetime | None = None,
) -> ReminderTextParseResult:
    raw = text.strip()
    if not raw:
        return _result(False, "", None, timezone, None, "empty_text")

    current = now or now_in_timezone(timezone)
    candidate = _find_time_candidate(raw, current, default_time)
    if candidate is None:
        return _result(False, _clean_task_text(raw), None, timezone, None, "time_not_found")

    task_text = _clean_task_text(raw[: candidate.start] + " " + raw[candidate.end :])
    if not task_text:
        return _result(
            False,
            "",
            candidate.remind_at,
            timezone,
            candidate.matched_pattern,
            "missing_task",
            needs_task=True,
        )
    return _result(True, task_text, candidate.remind_at, timezone, candidate.matched_pattern, None)


def parse_reminder_time_choice(
    choice: str,
    timezone: str = DEFAULT_REMINDER_TIMEZONE,
    now: datetime | None = None,
    default_time: str = DEFAULT_REMINDER_TIME,
) -> datetime | None:
    current = now or now_in_timezone(timezone)
    if choice == "in_1h":
        return current + timedelta(hours=1)
    if choice.startswith("tomorrow_"):
        hour_text = choice.removeprefix("tomorrow_")
        if not hour_text.isdigit():
            return None
        return datetime.combine(
            current.date() + timedelta(days=1),
            time(hour=int(hour_text), minute=0),
        )
    if choice == "tomorrow_default":
        return datetime.combine(
            current.date() + timedelta(days=1),
            parse_default_time(default_time),
        )
    return None


def parse_simple_reminder_time(
    text: str,
    timezone: str = DEFAULT_REMINDER_TIMEZONE,
    now: datetime | None = None,
    default_time: str = DEFAULT_REMINDER_TIME,
) -> datetime | None:
    return parse_reminder_time_text(text, timezone, default_time, now)


def parse_reminder_time_text(
    text: str,
    timezone: str = DEFAULT_REMINDER_TIMEZONE,
    default_time: str = DEFAULT_REMINDER_TIME,
    now: datetime | None = None,
) -> datetime | None:
    normalized = _normalize(text)
    for choice, label in REMINDER_TIME_CHOICES.items():
        if normalized == _normalize(label):
            return parse_reminder_time_choice(choice, timezone, now, default_time)

    result = parse_reminder_text(text, timezone, default_time, now)
    return result.remind_at


def parse_reminder_request(
    text: str,
    timezone: str = DEFAULT_REMINDER_TIMEZONE,
    default_time: str = DEFAULT_REMINDER_TIME,
    now: datetime | None = None,
) -> ReminderParseResult | None:
    result = parse_reminder_text(text, timezone, default_time, now)
    if not result.success or result.remind_at is None:
        return None
    return ReminderParseResult(
        remind_at=result.remind_at,
        task_text=result.task_text,
        time_text=result.matched_pattern or "",
    )


def parse_default_time(value: str = DEFAULT_REMINDER_TIME) -> time:
    matched = re.fullmatch(_TIME_RE, value.strip())
    if matched is None:
        return time(hour=10, minute=0)
    return _time_from_match(matched)


def now_in_timezone(timezone: str = DEFAULT_REMINDER_TIMEZONE) -> datetime:
    try:
        zone = ZoneInfo(_normalize_timezone(timezone))
    except ZoneInfoNotFoundError:
        zone = ZoneInfo(_ZONEINFO_FALLBACK_TIMEZONE)
    return datetime.now(zone).replace(tzinfo=None)


def _find_time_candidate(
    raw: str,
    current: datetime,
    default_time: str,
) -> _TimeCandidate | None:
    candidates = []
    candidates.extend(_relative_candidates(raw, current))
    candidates.extend(_day_candidates(raw, current, default_time))
    candidates.extend(_weekday_candidates(raw, current, default_time))
    candidates.extend(_time_only_candidates(raw, current))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.start, -(item.end - item.start)))[0]


def _relative_candidates(raw: str, current: datetime) -> list[_TimeCandidate]:
    candidates = []
    for pattern, name in _RELATIVE_PATTERNS:
        for matched in re.finditer(pattern, raw, re.IGNORECASE):
            delta = _relative_delta(matched, name)
            if delta is not None:
                candidates.append(
                    _TimeCandidate(
                        start=matched.start(),
                        end=matched.end(),
                        remind_at=current + delta,
                        matched_pattern=name,
                    )
                )
    return candidates


def _day_candidates(raw: str, current: datetime, default_time: str) -> list[_TimeCandidate]:
    candidates = []
    for matched in _DAY_RE.finditer(raw):
        day = matched.group("day").lower()
        target_date = current.date() + (timedelta(days=1) if day == "завтра" else timedelta())
        target_time = _extract_time_or_part(matched, parse_default_time(default_time))
        remind_at = datetime.combine(target_date, target_time)
        candidates.append(
            _TimeCandidate(matched.start(), matched.end(), remind_at, f"{day}_time")
        )
    return candidates


def _weekday_candidates(raw: str, current: datetime, default_time: str) -> list[_TimeCandidate]:
    candidates = []
    for matched in _WEEKDAY_RE.finditer(raw):
        weekday = _WEEKDAYS[matched.group("weekday").lower()]
        target_time = _extract_time_or_part(matched, parse_default_time(default_time))
        days_ahead = (weekday - current.weekday()) % 7
        prefix = (matched.group("prefix") or "").lower()
        if prefix.startswith("следующ") and days_ahead == 0:
            days_ahead = 7
        remind_at = datetime.combine(current.date() + timedelta(days=days_ahead), target_time)
        if remind_at <= current:
            remind_at += timedelta(days=7)
        candidates.append(
            _TimeCandidate(matched.start(), matched.end(), remind_at, "weekday_time")
        )
    return candidates


def _time_only_candidates(raw: str, current: datetime) -> list[_TimeCandidate]:
    candidates = []
    for pattern in _TIME_ONLY_PATTERNS:
        for matched in pattern.finditer(raw):
            candidate = datetime.combine(current.date(), _time_from_match(matched))
            if candidate <= current:
                candidate += timedelta(days=1)
            candidates.append(
                _TimeCandidate(matched.start(), matched.end(), candidate, "time_only")
            )
    return candidates


def _relative_delta(matched: re.Match[str], pattern_name: str) -> timedelta | None:
    if pattern_name == "relative_half_hour":
        return timedelta(minutes=30)
    if pattern_name == "relative_one_and_half_hours":
        return timedelta(minutes=90)
    if pattern_name == "relative_decimal_hours":
        return timedelta(minutes=round(_number_value(matched.group("hours")) * 60))
    if pattern_name == "relative_hours_minutes":
        hours_text = matched.group("hours")
        hours = 1 if hours_text in {"час", "часик"} else int(_number_value(hours_text))
        minutes = int(_number_value(matched.group("minutes")))
        return timedelta(hours=hours, minutes=minutes)
    if pattern_name in {"relative_hours", "relative_hours_reverse"}:
        return timedelta(hours=_relative_amount(matched.group("amount"), several=3))
    if pattern_name in {
        "relative_minutes",
        "relative_minutes_reversed_after",
        "relative_minutes_reversed_before",
    }:
        return timedelta(minutes=_relative_amount(matched.group("amount"), several=5))
    return None


def _relative_amount(value: str, several: int) -> int:
    normalized = _normalize(value)
    if normalized in {"минуту", "минута", "минуты", "минут", "мин", "час", "часик"}:
        return 1
    if normalized == "пару":
        return 2
    if normalized == "несколько":
        return several
    return int(_number_value(normalized))


def _number_value(value: str) -> float:
    normalized = _normalize(value).replace(",", ".")
    if normalized in _NUMBER_WORDS:
        return float(_NUMBER_WORDS[normalized])
    return float(normalized)


def _extract_time_or_part(matched: re.Match[str], fallback: time) -> time:
    if matched.groupdict().get("hour") is not None:
        return _time_from_match(matched)
    part = matched.groupdict().get("part")
    if part:
        return _PART_TIMES[part.lower()]
    return fallback


def _time_from_match(matched: re.Match[str]) -> time:
    return time(hour=int(matched.group("hour")), minute=int(matched.group("minute")))


def _clean_task_text(value: str) -> str:
    text = f" {_normalize_spaces(value)} "
    service_phrases = [
        "поставь напоминание",
        "создай напоминание",
        "напомни мне",
        "о том что",
        "напомни",
        "напомнить",
        "напоминание",
        "пожалуйста",
        "плиз",
        "можешь",
        "сделай",
        "надо",
        "нужно",
        "чтобы",
        "мне",
    ]
    for phrase in service_phrases:
        text = re.sub(rf"(?i)(?<!\w){re.escape(phrase)}(?!\w)", " ", text)
    return _normalize_spaces(text).strip(" \t\n\r,.-—")


def _result(
    success: bool,
    task_text: str,
    remind_at: datetime | None,
    timezone: str,
    matched_pattern: str | None,
    error: str | None,
    needs_task: bool = False,
) -> ReminderTextParseResult:
    return ReminderTextParseResult(
        success=success,
        task_text=task_text,
        remind_at=remind_at,
        timezone=timezone,
        matched_pattern=matched_pattern,
        error=error,
        needs_task=needs_task,
    )


def _normalize(value: str) -> str:
    return _normalize_spaces(value).lower()


def _normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def _normalize_timezone(timezone: str) -> str:
    value = timezone.strip() or DEFAULT_REMINDER_TIMEZONE
    aliases = {
        "Russia/Moscow": _ZONEINFO_FALLBACK_TIMEZONE,
        "russia/moscow": _ZONEINFO_FALLBACK_TIMEZONE,
    }
    return aliases.get(value, value)
