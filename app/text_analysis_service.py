import json
import logging
import re
from typing import Protocol, TypedDict

from app.tasks import TaskItem, normalize_tasks


logger = logging.getLogger(__name__)


class TextAnalysisError(RuntimeError):
    """Raised when structured text analysis cannot be produced."""


class TextAnalysisClient(Protocol):
    def analyze_text(self, system_prompt: str, user_prompt: str) -> str:
        ...


class VoiceAnalysisText(TypedDict):
    memorable_quote: str
    verdict: str
    meme: str


class TextAnalysisResult(TypedDict):
    title: str
    summary: str
    action_items: list[TaskItem]
    details: str
    important_points: list[str]
    voice_analysis_text: VoiceAnalysisText


class TextAnalysisService:
    """Structured text analysis through DeepSeek."""

    def __init__(self, client: TextAnalysisClient) -> None:
        self._client = client

    def analyze(
        self,
        transcript: str,
        pre_metrics: dict[str, object] | None = None,
    ) -> TextAnalysisResult:
        try:
            raw_text = self._client.analyze_text(
                _analysis_system_prompt(),
                _analysis_user_prompt(transcript, pre_metrics),
            )
        except Exception as exc:
            raise TextAnalysisError("DeepSeek text analysis failed") from exc

        try:
            data = json.loads(_extract_json(raw_text))
        except json.JSONDecodeError as exc:
            logger.warning("DeepSeek returned invalid JSON: %s", raw_text)
            raise TextAnalysisError("DeepSeek returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise TextAnalysisError("DeepSeek returned JSON with an unexpected shape")

        tasks = data.get("tasks")
        if tasks is None:
            tasks = data.get("action_items")
        voice_analysis = data.get("voice_analysis")
        if not isinstance(voice_analysis, dict):
            voice_analysis = {}

        return {
            "title": str(data.get("title", "")).strip().strip("\"'“”«»."),
            "summary": str(data.get("summary", "")).strip(),
            "action_items": normalize_tasks(tasks),
            "details": str(data.get("details", "")).strip(),
            "important_points": _as_string_list(data.get("important_points")),
            "voice_analysis_text": {
                "memorable_quote": str(voice_analysis.get("memorable_quote", "")).strip(),
                "verdict": str(voice_analysis.get("verdict", "")).strip(),
                "meme": str(voice_analysis.get("meme", "")).strip(),
            },
        }


def _analysis_system_prompt() -> str:
    return (
        "Ты анализируешь уже готовую дословную расшифровку голосового сообщения. "
        "Верни только JSON без Markdown. "
        "JSON keys: title, summary, tasks, details, important_points, voice_analysis. "
        "title: короткий заголовок 2-5 слов на языке пользователя, без кавычек и точки. "
        "summary: краткое содержание в 1-2 предложениях. "
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
        "voice_analysis содержит только текстовые творческие поля: "
        "memorable_quote, verdict, meme. "
        "Не возвращай технические числа, уровни, длительности, оценки или проценты: "
        "их считает локальный сервер. "
        "Метрики голосового сообщения рассчитаны локально и являются источником истины. "
        "Не рассчитывай их самостоятельно и не противоречь им. "
        "Если duration_seconds маленький — не шути про длинное голосовое, подкаст, аудиокнигу или сериал. "
        "Если wordiness_score низкий — не шути про многословность. "
        "Если water_percent низкий или неизвестен — не утверждай, что в сообщении много воды. "
        "Если quality_score высокий — не делай вид, что сообщение плохое. "
        "Шутка должна соответствовать переданным метрикам. "
        "Для verdict и meme сделай тон заметно жёстче, смешнее и вируснее. "
        "Тон: жёсткий сарказм, цинично, коротко, мемно, без канцелярита и без бережной душнины. "
        "Пиши так, чтобы результат хотелось переслать автору голосового. "
        "verdict: короткий едкий вывод о соотношении пользы, воды и драматургии голосового. "
        "meme: 1-2 коротких предложения, максимально пересылаемый мемный вывод, "
        "желательно с короткой цитатой из голосового. "
        "memorable_quote: самая смешная или характерная фраза из голосового, если она есть. "
        "Можно высмеивать длину голосового, воду, драматургию, формат аудиокниги, "
        "фразы вроде 'короче', 'ну в общем', 'я быстро', и то, что всё могло быть одним сообщением. "
        "Можно использовать едкие формулировки, но бей по формату сообщения, а не по человеку. "
        "Нельзя: оскорблять человека как личность, делать выводы о личности автора, устраивать травлю, "
        "угрожать, использовать мат, затрагивать внешность, национальность, пол, здоровье, религию или политику. "
        "Запрещено: унижения, личностные оскорбления, фразы вроде 'автор тупой', "
        "'человек не умеет говорить', 'что за бред'."
    )


def _analysis_user_prompt(
    transcript: str,
    pre_metrics: dict[str, object] | None = None,
) -> str:
    payload: dict[str, object] = {"transcription": transcript}
    if pre_metrics:
        payload["voice_metrics"] = pre_metrics
    return (
        "Данные для анализа. Метрики voice_metrics уже посчитаны локально, "
        "не меняй и не пересчитывай их:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


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
