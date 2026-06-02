import json
import logging
from pathlib import Path
import re
import time
from typing import Callable, TypeVar

from openai import OpenAI, RateLimitError

from app.config import Settings
from app.tasks import normalize_tasks
from app.voice_analysis import normalize_voice_analysis


logger = logging.getLogger(__name__)
T = TypeVar("T")


class OpenAIInsufficientQuotaError(RuntimeError):
    """Raised when OpenAI reports that API quota or billing is exhausted."""


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._transcribe_model = settings.openai_transcribe_model
        self._text_model = settings.openai_text_model
        self._max_rate_limit_attempts = 3

    def transcribe(self, audio_path: Path) -> str:
        def request() -> object:
            with audio_path.open("rb") as audio_file:
                return self._client.audio.transcriptions.create(
                    model=self._transcribe_model,
                    file=audio_file,
                )

        transcript = self._with_rate_limit_retry(request, "audio transcription")
        text = getattr(transcript, "text", "")
        return text.strip()

    def analyze(self, transcript: str, duration_seconds: int = 0) -> dict[str, object]:
        prompt = (
            "Ты помощник для обработки длинных голосовых заметок. "
            "Верни только JSON с ключами title, summary, tasks, details, important_points, voice_analysis. "
            "title: короткий заголовок в 2-5 слов на языке пользователя, без кавычек и точки в конце. "
            "summary: очень короткое содержание на русском в 1-2 предложениях. "
            "details: 3-6 коротких предложений с полезными подробностями. "
            "important_points: массив строк. "
            "tasks: массив объектов вида {\"text\": \"Купить молоко\", \"priority\": false}. "
            "Выведи все задачи, которые явно или косвенно перечислены в сообщении. "
            "Не придумывай лишнее. "
            "Если задача выделена пользователем как важная, срочная или обязательная — "
            "пометь её как priority=true. Ориентируйся на слова и фразы: важно, "
            "очень важно, самое главное, главное не забыть, обязательно, срочно, "
            "не забудь, критично, в первую очередь, обязательно напомни и похожие. "
            "Не помечай задачу важной без явного акцента. "
            "Если задач нет, верни пустой массив tasks. "
            "voice_analysis: объект с ключами meaningful_duration_seconds, water_percent, "
            "wordiness_score, quality_score, voice_type_level, water_level, verdict_level, "
            "memorable_quote, verdict, meme, rare_title. "
            f"Полная длительность голосового: {duration_seconds} секунд. "
            "meaningful_duration_seconds — примерная длительность полезной содержательной части, "
            "не больше полной длительности. water_percent 0-100. wordiness_score и quality_score 0-10. "
            "voice_type_level, water_level, verdict_level — числа 1-10. "
            "rare_title возвращай только если wordiness_score >= 9.5 или water_percent >= 90, иначе пустую строку. "
            "Для voice_analysis сделай verdict и meme заметно жёстче, смешнее и вируснее. "
            "Тон: жёсткий сарказм, цинично, коротко, мемно, без канцелярита и без бережной душнины. "
            "Пиши так, чтобы результат хотелось переслать автору голосового. "
            "verdict: короткий едкий вывод о соотношении пользы, воды и драматургии голосового. "
            "meme: 1-2 коротких предложения, максимально пересылаемый мемный вывод, желательно с короткой цитатой из голосового. "
            "memorable_quote: самая смешная или характерная фраза из голосового, если она есть. "
            "Можно высмеивать длину голосового, воду, драматургию, формат аудиокниги, "
            "фразы вроде 'короче', 'ну в общем', 'я быстро', и то, что всё могло быть одним текстовым сообщением. "
            "Можно использовать едкие формулировки, но бей по формату сообщения, а не по человеку. "
            "Нельзя: оскорблять человека как личность, делать выводы о личности автора, устраивать травлю, "
            "угрожать, использовать мат, затрагивать внешность, национальность, пол, здоровье, религию или политику. "
            "Запрещено: унижения, личностные оскорбления, фразы вроде 'автор тупой', "
            "'человек не умеет говорить', 'что за бред'.\n\n"
            f"Текст расшифровки:\n{transcript}"
        )

        response = self._with_rate_limit_retry(
            lambda: self._client.responses.create(
                model=self._text_model,
                input=prompt,
            ),
            "text analysis",
        )

        raw_text = response.output_text.strip()
        try:
            data = json.loads(_extract_json(raw_text))
        except json.JSONDecodeError:
            logger.warning("OpenAI returned invalid JSON: %s", raw_text)
            return {
                "summary": raw_text,
                "title": "",
                "action_items": [],
                "details": "",
                "important_points": [],
                "voice_analysis": normalize_voice_analysis({}, duration_seconds),
            }

        tasks = data.get("tasks")
        if tasks is None:
            tasks = data.get("action_items")

        return {
            "title": str(data.get("title", "")).strip().strip("\"'“”«»."),
            "summary": str(data.get("summary", "")).strip(),
            "action_items": normalize_tasks(tasks),
            "details": str(data.get("details", "")).strip(),
            "important_points": _as_string_list(data.get("important_points")),
            "voice_analysis": normalize_voice_analysis(
                data.get("voice_analysis"),
                duration_seconds,
            ),
        }

    def _with_rate_limit_retry(self, request: Callable[[], T], label: str) -> T:
        for attempt in range(1, self._max_rate_limit_attempts + 1):
            try:
                return request()
            except RateLimitError as exc:
                if _is_insufficient_quota(exc):
                    raise OpenAIInsufficientQuotaError(
                        "OpenAI API quota is exhausted"
                    ) from exc

                if attempt >= self._max_rate_limit_attempts:
                    raise

                delay_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "OpenAI rate limit during %s, retrying in %s seconds "
                    "(attempt %s/%s)",
                    label,
                    delay_seconds,
                    attempt,
                    self._max_rate_limit_attempts,
                    exc_info=True,
                )
                time.sleep(delay_seconds)

        raise RuntimeError("OpenAI retry loop exited unexpectedly")


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return text[start : end + 1]

    return text


def _is_insufficient_quota(exc: RateLimitError) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        code = body.get("code")
        if code == "insufficient_quota":
            return True

        error = body.get("error")
        if isinstance(error, dict) and error.get("code") == "insufficient_quota":
            return True

    return "insufficient_quota" in str(exc)
