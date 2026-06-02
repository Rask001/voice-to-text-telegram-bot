from openai import OpenAI

from app.config import Settings


class DeepSeekClientError(RuntimeError):
    """Raised when DeepSeek text analysis cannot be completed."""


class DeepSeekClient:
    """OpenAI-compatible DeepSeek client used only for text analysis."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.deepseek_api_key
        self._model = settings.deepseek_model
        kwargs: dict[str, str] = {"api_key": settings.deepseek_api_key or "missing"}
        if settings.deepseek_base_url:
            kwargs["base_url"] = settings.deepseek_base_url
        self._client = OpenAI(**kwargs)

    def analyze_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise DeepSeekClientError("DEEPSEEK_API_KEY is not configured")

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
            )
        except Exception as exc:
            raise DeepSeekClientError("DeepSeek text analysis failed") from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise DeepSeekClientError("DeepSeek returned an unexpected response") from exc

        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        text = str(content or "").strip()
        if not text:
            raise DeepSeekClientError("DeepSeek returned an empty response")
        return text
