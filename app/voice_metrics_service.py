import math
import re
from typing import Any

from app.tasks import TaskItem, normalize_tasks
from app.voice_analysis import VoiceAnalysis, normalize_voice_analysis


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
_DETAILS_WEIGHT = 0.25

_LOW_WATER_CONFLICTS = [
    "много воды",
    "воды",
    "водянист",
    "аудиокнига",
    "подкаст",
    "сериал",
    "долго",
    "многословно",
    "байкал",
    "океан",
    "ливень",
]
_SHORT_DURATION_CONFLICTS = [
    "длинное голосовое",
    "подкаст",
    "аудиокнига",
    "сериал",
    "второй сезон",
    "режиссёрская версия",
    "режиссерская версия",
    "долго",
    "полнометражный",
]
_LOW_WORDINESS_CONFLICTS = [
    "многословно",
    "много слов",
    "поток слов",
    "болтовня",
    "лекция",
]
_HIGH_QUALITY_VERDICT_CONFLICTS = [
    "плох",
    "бессмыслен",
    "водянист",
    "много воды",
    "бред",
]


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
    metrics = calculate_final_metrics(
        transcription=transcript,
        summary=summary,
        tasks=normalized_tasks,
        details=details,
        important_points=normalized_points,
        duration_seconds=duration_seconds,
    )
    creative_text = voice_analysis_text or {}
    verdict, meme = sanitize_ai_meme_by_metrics(
        verdict=str(creative_text.get("verdict", "")).strip(),
        meme=str(creative_text.get("meme", "")).strip(),
        metrics=metrics,
    )

    return normalize_voice_analysis(
        {
            **metrics,
            "verdict": verdict,
            "meme": meme,
            "memorable_quote": str(creative_text.get("memorable_quote", "")).strip(),
        },
        int(duration_seconds),
    )


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def calculate_pre_metrics(transcription: str, duration_seconds: int) -> dict[str, object]:
    duration = max(0, int(duration_seconds))
    word_count = count_words(transcription)
    words_per_minute = _words_per_minute(word_count, duration)
    return {
        "duration_seconds": duration,
        "word_count": word_count,
        "words_per_minute": round(words_per_minute, 1),
        "wordiness_score": calculate_wordiness_score(
            duration_seconds=duration,
            word_count=word_count,
            words_per_minute=words_per_minute,
        ),
    }


def calculate_final_metrics(
    *,
    transcription: str,
    summary: str,
    tasks: list[TaskItem] | object,
    details: str,
    important_points: list[str] | object,
    duration_seconds: int,
) -> dict[str, object]:
    duration = max(0, int(duration_seconds))
    normalized_tasks = normalize_tasks(tasks)
    normalized_points = _as_string_list(important_points)
    word_count = count_words(transcription)
    words_per_minute = _words_per_minute(word_count, duration)
    wordiness_score = calculate_wordiness_score(
        duration_seconds=duration,
        word_count=word_count,
        words_per_minute=words_per_minute,
    )
    useful_word_count = calculate_useful_word_count(
        summary=summary,
        tasks=normalized_tasks,
        details=details,
        important_points=normalized_points,
    )
    compression_ratio = calculate_compression_ratio(
        useful_word_count=useful_word_count,
        word_count=word_count,
    )
    water_percent = calculate_water_percent(
        duration_seconds=duration,
        word_count=word_count,
        useful_word_count=useful_word_count,
        compression_ratio=compression_ratio,
        wordiness_score=wordiness_score,
    )
    meaningful_duration = calculate_meaningful_duration_seconds(
        duration_seconds=duration,
        word_count=word_count,
        compression_ratio=compression_ratio,
    )
    saved_seconds = max(duration - meaningful_duration, 0)
    quality_score = calculate_quality_score(
        duration_seconds=duration,
        water_percent=water_percent,
        wordiness_score=wordiness_score,
        tasks_count=len(normalized_tasks),
    )
    water_level, water_class_text = get_water_class(water_percent)
    voice_type_level, voice_type_text = get_voice_type(
        wordiness_score=wordiness_score,
        duration_seconds=duration,
        word_count=word_count,
    )
    return {
        "duration_seconds": duration,
        "word_count": word_count,
        "words_per_minute": round(words_per_minute, 1),
        "useful_word_count": round(useful_word_count, 1),
        "compression_ratio": round(compression_ratio, 3),
        "meaningful_duration_seconds": meaningful_duration,
        "saved_seconds": saved_seconds,
        "water_percent": water_percent,
        "water_level": water_level,
        "water_class": water_class_text,
        "wordiness_score": wordiness_score,
        "voice_type_level": voice_type_level,
        "voice_type": voice_type_text,
        "quality_score": quality_score,
    }


def calculate_useful_word_count(
    *,
    summary: str,
    tasks: list[TaskItem],
    details: str,
    important_points: list[str],
) -> float:
    tasks_text = "\n".join(task["text"] for task in tasks)
    important_text = "\n".join(important_points)
    return (
        count_words(summary)
        + count_words(tasks_text)
        + count_words(important_text)
        + count_words(details) * _DETAILS_WEIGHT
    )


def calculate_wordiness_score(
    *,
    duration_seconds: int,
    word_count: int,
    words_per_minute: float,
) -> float:
    speech_rate_score = _clamp_float((words_per_minute - 80) / 140, 0.0, 1.0)
    duration_score = _clamp_float(
        math.log1p(duration_seconds / 30) / math.log1p(600 / 30),
        0.0,
        1.0,
    )
    word_count_score = _clamp_float(
        math.log1p(word_count / 50) / math.log1p(1000 / 50),
        0.0,
        1.0,
    )
    wordiness_raw = (
        0.45 * word_count_score
        + 0.35 * duration_score
        + 0.20 * speech_rate_score
    )
    score = round(1 + wordiness_raw * 9, 1)

    if duration_seconds < 30 and word_count < 80:
        score = min(score, 2.0)
    if duration_seconds < 60 and word_count < 120:
        score = min(score, 3.0)
    if duration_seconds > 180 and word_count < 100:
        score = min(score, 2.5)
    if words_per_minute < 70:
        score = min(score, 3.0)
    return round(_clamp_float(score, 1.0, 10.0), 1)


def calculate_compression_ratio(*, useful_word_count: float, word_count: int) -> float:
    if word_count <= 0:
        return 0.0
    return _clamp_float(useful_word_count / max(word_count, 1), 0.05, 1.0)


def calculate_water_percent(
    *,
    duration_seconds: int,
    word_count: int,
    useful_word_count: float,
    compression_ratio: float,
    wordiness_score: float,
) -> int:
    if word_count <= 0 or duration_seconds <= 0:
        return 0

    water_percent = round((1 - compression_ratio) * 100)
    water_percent = _clamp(water_percent, 0, 95)

    if word_count < 20:
        water_percent = min(water_percent, 20)
    if duration_seconds < 30:
        water_percent = min(water_percent, 25)
    if duration_seconds < 60 and word_count < 100:
        water_percent = min(water_percent, 35)
    if useful_word_count >= word_count * 0.75:
        water_percent = min(water_percent, 25)
    if wordiness_score <= 2:
        water_percent = min(water_percent, 25)
    if wordiness_score >= 8 and compression_ratio < 0.35:
        water_percent = max(water_percent, 70)
    return _clamp(water_percent, 0, 95)


def calculate_meaningful_duration_seconds(
    *,
    duration_seconds: int,
    word_count: int,
    compression_ratio: float,
) -> int:
    if word_count == 0 or duration_seconds <= 0:
        return 0
    meaningful = round(duration_seconds * compression_ratio)
    meaningful = _clamp(meaningful, 1, duration_seconds)
    if duration_seconds < 30 and word_count < 80:
        meaningful = duration_seconds
    return meaningful


def calculate_quality_score(
    *,
    duration_seconds: int,
    water_percent: int,
    wordiness_score: float,
    tasks_count: int,
) -> float:
    score = 10.0
    score -= water_percent * 0.05
    score -= max(wordiness_score - 4, 0) * 0.45
    if duration_seconds < 30 and water_percent <= 25:
        score += 0.5
    if tasks_count > 0:
        score += 0.3
    return round(_clamp_float(score, 1.0, 10.0), 1)


def get_water_class(water_percent: int) -> tuple[int, str]:
    if water_percent <= 10:
        return 1, "Пустыня — Сухо и эффективно."
    if water_percent <= 20:
        return 2, "Засуха — Воды почти нет."
    if water_percent <= 30:
        return 3, "Роса — Небольшие следы воды."
    if water_percent <= 45:
        return 4, "Душ — Иногда отвлекался от сути."
    if water_percent <= 60:
        return 5, "Морось — Воды уже заметно."
    if water_percent <= 70:
        return 6, "Дождь — Суть начинает намокать."
    if water_percent <= 80:
        return 7, "Ливень — Нужен зонт."
    if water_percent <= 88:
        return 8, "Наводнение — Смысл местами под водой."
    if water_percent <= 94:
        return 9, "Атлантический океан — До сути пришлось плыть."
    return 10, "Байкал — Самое глубокое голосовое."


def get_voice_type(
    *,
    wordiness_score: float,
    duration_seconds: int,
    word_count: int,
) -> tuple[int, str]:
    if wordiness_score < 2.0:
        level = 1
    elif wordiness_score < 3.0:
        level = 2
    elif wordiness_score < 4.0:
        level = 3
    elif wordiness_score < 5.0:
        level = 4
    elif wordiness_score < 6.0:
        level = 5
    elif wordiness_score < 7.0:
        level = 6
    elif wordiness_score < 8.0:
        level = 7
    elif wordiness_score < 8.8:
        level = 8
    elif wordiness_score < 9.5:
        level = 9
    else:
        level = 10

    if duration_seconds < 60:
        level = min(level, 3)
    if duration_seconds < 30:
        level = min(level, 2)
    if word_count < 50:
        level = min(level, 2)

    voice_types = {
        1: "Снайпер",
        2: "Деловой человек",
        3: "По существу",
        4: "Любитель предисловий",
        5: "Рассказчик",
        6: "Подкастер",
        7: "Лектор",
        8: "Аудиокнига",
        9: "Режиссёрская версия",
        10: "Человек, которому нельзя давать микрофон",
    }
    return level, voice_types[level]


def validate_voice_analysis_consistency(
    *,
    verdict: str,
    meme: str,
    metrics: dict[str, Any],
) -> bool:
    return not _has_metric_conflict(verdict=verdict, meme=meme, metrics=metrics)


def sanitize_ai_meme_by_metrics(
    *,
    verdict: str,
    meme: str,
    metrics: dict[str, Any],
) -> tuple[str, str]:
    if not verdict:
        verdict = _fallback_verdict(metrics)
    if not meme:
        meme = _fallback_meme(metrics)
    if _has_metric_conflict(verdict=verdict, meme=meme, metrics=metrics):
        return _fallback_verdict(metrics), _fallback_meme(metrics)
    return verdict, meme


def _has_metric_conflict(*, verdict: str, meme: str, metrics: dict[str, Any]) -> bool:
    combined = f"{verdict}\n{meme}".lower()
    verdict_lower = verdict.lower()
    water_percent = int(metrics.get("water_percent", 0) or 0)
    duration_seconds = int(metrics.get("duration_seconds", 0) or 0)
    wordiness_score = float(metrics.get("wordiness_score", 1.0) or 1.0)
    quality_score = float(metrics.get("quality_score", 5.0) or 5.0)

    if water_percent <= 20 and _contains_any(combined, _LOW_WATER_CONFLICTS):
        return True
    if duration_seconds < 30 and _contains_any(combined, _SHORT_DURATION_CONFLICTS):
        return True
    if wordiness_score < 3 and _contains_any(combined, _LOW_WORDINESS_CONFLICTS):
        return True
    if quality_score >= 8 and _contains_any(verdict_lower, _HIGH_QUALITY_VERDICT_CONFLICTS):
        return True
    return False


def _fallback_verdict(metrics: dict[str, Any]) -> str:
    water_percent = int(metrics.get("water_percent", 0) or 0)
    duration_seconds = int(metrics.get("duration_seconds", 0) or 0)
    quality_score = float(metrics.get("quality_score", 5.0) or 5.0)
    if water_percent <= 25 or duration_seconds < 30 or quality_score >= 8:
        return "Редкий случай: коротко, по делу и без экспедиции к смыслу."
    return "Смысл найден. Он прятался между ‘короче’ и ‘ну в общем’."


def _fallback_meme(metrics: dict[str, Any]) -> str:
    water_percent = int(metrics.get("water_percent", 0) or 0)
    duration_seconds = int(metrics.get("duration_seconds", 0) or 0)
    quality_score = float(metrics.get("quality_score", 5.0) or 5.0)
    if water_percent <= 25 or duration_seconds < 30 or quality_score >= 8:
        return "Голосовое прошло проверку: клавиатура не подала в суд за неуважение."
    return "Можно было написать одну строку, но автор выбрал формат аудиокниги."


def _words_per_minute(word_count: int, duration_seconds: int) -> float:
    return word_count / max(duration_seconds, 1) * 60


def _contains_any(text: str, fragments: list[str]) -> bool:
    return any(fragment in text for fragment in fragments)


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()] if value else []


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
