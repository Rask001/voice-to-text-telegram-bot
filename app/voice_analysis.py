import json
from hashlib import sha1
from typing import Any, NotRequired, TypedDict


class VoiceAnalysis(TypedDict):
    duration_seconds: int
    word_count: NotRequired[int]
    words_per_minute: NotRequired[float]
    useful_word_count: NotRequired[float]
    compression_ratio: NotRequired[float]
    meaningful_duration_seconds: int
    water_percent: int
    water_class: NotRequired[str]
    wordiness_score: float
    quality_score: float
    voice_type_level: int
    voice_type: NotRequired[str]
    water_level: int
    verdict_level: int
    verdict: str
    memorable_quote: str
    meme: str
    rare_title: str
    saved_seconds: int


WATER_CLASSES = {
    1: ("🏜", "Пустыня — Сухо и эффективно."),
    2: ("🌵", "Засуха — Воды почти нет."),
    3: ("💧", "Роса — Небольшие следы воды."),
    4: ("🚿", "Душ — Иногда отвлекался от сути."),
    5: ("🌦", "Морось — Воды уже заметно."),
    6: ("🌧", "Дождь — Суть начинает намокать."),
    7: ("⛈", "Ливень — Нужен зонт."),
    8: ("🌊", "Наводнение — Смысл местами под водой."),
    9: ("🚢", "Атлантический океан — До сути пришлось плыть."),
    10: ("🌊", "Байкал — Самое глубокое голосовое."),
}

VOICE_TYPES = {
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

RARE_TITLES = [
    "👑 Народный артист голосовых сообщений",
    "🏆 Абсолютный чемпион по вступлениям",
    "🎙 Последний босс Telegram-аудио",
    "📼 Архивное издание на 12 кассетах",
    "🎬 Режиссёрская версия режиссёрской версии",
    "🛟 Спасательная операция по поиску смысла",
    "📡 Радиостанция “Короче смотри FM”",
    "🧘 Мастер долгого входа в тему",
    "🏛 Памятник устной речи",
    "🚢 Экспедиция к сути сообщения",
]


def normalize_voice_analysis(value: object, duration_seconds: int) -> VoiceAnalysis:
    data = value if isinstance(value, dict) else {}
    meaningful_duration = _as_int(data.get("meaningful_duration_seconds"), duration_seconds)
    meaningful_duration = max(0, min(meaningful_duration, duration_seconds))
    water_percent = _clamp(_as_int(data.get("water_percent"), 0), 0, 95)
    wordiness_score = _clamp_float(_as_float(data.get("wordiness_score"), 1.0), 1.0, 10.0)
    quality_score = _clamp_float(_as_float(data.get("quality_score"), 5.0), 1.0, 10.0)
    word_count = _as_int(data.get("word_count"), -1)
    voice_type_level = _voice_type_level_from_metrics(
        wordiness_score,
        duration_seconds,
        word_count if word_count >= 0 else None,
    )
    water_level = _level_from_percent(water_percent)
    verdict_level = _clamp(
        _as_int(data.get("verdict_level"), max(water_level, voice_type_level)),
        max(water_level, voice_type_level),
        10,
    )
    saved_seconds = max(0, duration_seconds - meaningful_duration)
    verdict = _clean_text(data.get("verdict")) or _fallback_verdict(saved_seconds)
    meme = _sanitize_meme(
        _clean_text(data.get("meme"))
        or "Голосовое обработано. Мемный разбор появится у новых записей."
    )
    quote = _clean_text(data.get("memorable_quote"))
    rare_title = _clean_text(data.get("rare_title"))
    if not _rare_title_allowed(water_percent, wordiness_score):
        rare_title = ""
    if not rare_title and _rare_title_allowed(water_percent, wordiness_score):
        rare_title = _pick_rare_title(meme + quote + str(duration_seconds))

    result: VoiceAnalysis = {
        "duration_seconds": duration_seconds,
        "meaningful_duration_seconds": meaningful_duration,
        "water_percent": water_percent,
        "wordiness_score": round(wordiness_score, 1),
        "quality_score": round(quality_score, 1),
        "voice_type_level": voice_type_level,
        "voice_type": voice_type(voice_type_level),
        "water_level": water_level,
        "water_class": water_class(water_level)[1],
        "verdict_level": verdict_level,
        "verdict": verdict,
        "memorable_quote": quote,
        "meme": meme,
        "rare_title": rare_title,
        "saved_seconds": saved_seconds,
    }
    if word_count >= 0:
        result["word_count"] = word_count
    if "words_per_minute" in data:
        result["words_per_minute"] = round(
            _clamp_float(_as_float(data.get("words_per_minute"), 0.0), 0.0, 1000.0),
            1,
        )
    if "useful_word_count" in data:
        result["useful_word_count"] = round(
            _clamp_float(_as_float(data.get("useful_word_count"), 0.0), 0.0, 100000.0),
            1,
        )
    if "compression_ratio" in data:
        result["compression_ratio"] = round(
            _clamp_float(_as_float(data.get("compression_ratio"), 0.0), 0.0, 1.0),
            3,
        )
    return result


def fallback_voice_analysis(duration_seconds: int) -> VoiceAnalysis:
    return normalize_voice_analysis(
        {
            "meaningful_duration_seconds": duration_seconds,
            "water_percent": 0,
            "wordiness_score": 1,
            "quality_score": 5,
            "voice_type_level": 3,
            "water_level": 1,
            "verdict": "Для этой старой записи мем-анализ ещё не сохранялся.",
            "meme": "Это голосовое появилось раньше, чем у бота появилось чувство юмора.",
        },
        duration_seconds,
    )


def serialize_voice_analysis(analysis: VoiceAnalysis) -> str:
    return json.dumps(analysis, ensure_ascii=False)


def parse_voice_analysis_json(value: str | None, duration_seconds: int) -> VoiceAnalysis:
    if not value:
        return fallback_voice_analysis(duration_seconds)
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return fallback_voice_analysis(duration_seconds)
    return normalize_voice_analysis(data, duration_seconds)


def water_class(level: int) -> tuple[str, str]:
    return WATER_CLASSES.get(_clamp(level, 1, 10), WATER_CLASSES[1])


def voice_type(level: int) -> str:
    return VOICE_TYPES.get(_clamp(level, 1, 10), VOICE_TYPES[3])


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours} ч {minutes:02d} мин"
    if minutes:
        return f"{minutes} мин {seconds:02d} сек"
    return f"{seconds} сек"


def format_compact_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _fallback_verdict(saved_seconds: int) -> str:
    if saved_seconds <= 0:
        return "Суть и длительность почти совпали. Редкий дисциплинированный случай."
    return f"{format_duration(saved_seconds)} экономии. Бот аккуратно отделил смысл от маршрута к нему."


def _rare_title_allowed(water_percent: int, wordiness_score: float) -> bool:
    return wordiness_score >= 9.5 or water_percent >= 90


def _pick_rare_title(seed: str) -> str:
    digest = sha1(seed.encode("utf-8")).hexdigest()
    return RARE_TITLES[int(digest[:8], 16) % len(RARE_TITLES)]


def _level_from_percent(value: int) -> int:
    if value <= 10:
        return 1
    if value <= 20:
        return 2
    if value <= 30:
        return 3
    if value <= 45:
        return 4
    if value <= 60:
        return 5
    if value <= 70:
        return 6
    if value <= 80:
        return 7
    if value <= 88:
        return 8
    if value <= 94:
        return 9
    return 10


def _level_from_score(value: float) -> int:
    return _clamp(round(value) or 1, 1, 10)


def _voice_type_level_from_metrics(
    wordiness_score: float,
    duration_seconds: int,
    word_count: int | None,
) -> int:
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
    if word_count is not None and word_count < 50:
        level = min(level, 2)
    return _clamp(level, 1, 10)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _clean_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _sanitize_meme(value: str) -> str:
    lowered = value.lower()
    banned_fragments = [
        "автор туп",
        "человек туп",
        "не умеет говорить",
        "что за бред",
        "идиот",
        "дебил",
        "дурак",
        "хер",
        "хуй",
        "пизд",
        "бля",
        "еба",
        "ёба",
    ]
    if any(fragment in lowered for fragment in banned_fragments):
        return "Голосовое начиналось как сообщение, но где-то по пути стало маленьким подкастом."
    return value
