import re

from app.tasks import TaskItem, normalize_tasks
from app.voice_analysis import VoiceAnalysis, normalize_voice_analysis


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


def build_voice_analysis(
    *,
    transcript: str,
    duration_seconds: int,
    summary: str,
    tasks: list[TaskItem] | object,
    details: str,
    important_points: list[str] | object,
    voice_analysis_text: dict[str, object] | None = None,
) -> VoiceAnalysis:
    """Build numeric voice metrics locally and merge DeepSeek creative text."""

    normalized_tasks = normalize_tasks(tasks)
    normalized_points = _as_string_list(important_points)
    meaningful_duration = _estimate_meaningful_duration_seconds(
        summary=summary,
        tasks=normalized_tasks,
        details=details,
        important_points=normalized_points,
        duration_seconds=duration_seconds,
    )
    saved_seconds = max(0, int(duration_seconds) - meaningful_duration)
    water_percent = _calculate_water_percent(duration_seconds, meaningful_duration)
    wordiness_score = _calculate_wordiness_score(
        transcript=transcript,
        duration_seconds=duration_seconds,
        water_percent=water_percent,
    )
    quality_score = _calculate_quality_score(
        water_percent=water_percent,
        wordiness_score=wordiness_score,
        tasks_count=len(normalized_tasks),
        important_points_count=len(normalized_points),
    )
    text = voice_analysis_text or {}

    return normalize_voice_analysis(
        {
            "meaningful_duration_seconds": meaningful_duration,
            "water_percent": water_percent,
            "wordiness_score": wordiness_score,
            "quality_score": quality_score,
            "verdict": str(text.get("verdict", "")).strip(),
            "meme": str(text.get("meme", "")).strip(),
            "memorable_quote": str(text.get("memorable_quote", "")).strip(),
            "saved_seconds": saved_seconds,
        },
        int(duration_seconds),
    )


def _estimate_meaningful_duration_seconds(
    *,
    summary: str,
    tasks: list[TaskItem],
    details: str,
    important_points: list[str],
    duration_seconds: int,
) -> int:
    useful_text_parts = [summary, details, "\n".join(important_points)]
    useful_text_parts.extend(task["text"] for task in tasks)
    useful_words = _word_count("\n".join(useful_text_parts))
    if useful_words == 0 or duration_seconds <= 0:
        return 0

    # Average conversational Russian speech is roughly 2-3 words/sec.
    estimated = round(useful_words / 2.4)
    return max(1, min(int(duration_seconds), estimated))


def _calculate_water_percent(duration_seconds: int, meaningful_duration_seconds: int) -> int:
    if duration_seconds <= 0:
        return 0
    saved_seconds = max(0, duration_seconds - meaningful_duration_seconds)
    return max(0, min(100, round(saved_seconds / duration_seconds * 100)))


def _calculate_wordiness_score(
    *,
    transcript: str,
    duration_seconds: int,
    water_percent: int,
) -> float:
    duration_bonus = 0.0
    if duration_seconds >= 600:
        duration_bonus = 1.5
    elif duration_seconds >= 360:
        duration_bonus = 1.0
    elif duration_seconds >= 180:
        duration_bonus = 0.5

    words_per_minute = _words_per_minute(transcript, duration_seconds)
    density_bonus = 0.5 if words_per_minute >= 170 else 0.0
    score = 1.0 + (water_percent / 12.0) + duration_bonus + density_bonus
    return round(max(1.0, min(10.0, score)), 1)


def _calculate_quality_score(
    *,
    water_percent: int,
    wordiness_score: float,
    tasks_count: int,
    important_points_count: int,
) -> float:
    usefulness_bonus = min(2.0, tasks_count * 0.25 + important_points_count * 0.15)
    score = 10.0 - (water_percent / 13.0) - (wordiness_score / 3.0) + usefulness_bonus
    return round(max(0.0, min(10.0, score)), 1)


def _words_per_minute(text: str, duration_seconds: int) -> float:
    if duration_seconds <= 0:
        return 0.0
    return _word_count(text) / (duration_seconds / 60)


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()] if value else []
