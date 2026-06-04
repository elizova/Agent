import json
import re

from .llm_provider import generate_response


def extract_json_from_text(text: str):
    if not text:
        return None
    text = text.strip()
    for pattern in (
        r"```json\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```",
    ):
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            text = m.group(1).strip()
            break
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def llm_json(
    prompt: str,
    fallback: dict,
    max_tokens: int = 500,
    temperature: float = 0.1,
    retries: int = 2,
    task: str = "general",
) -> tuple[dict, bool]:
    current_prompt = prompt
    for attempt in range(retries):
        try:
            response = generate_response(
                current_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                task=task,
            )
        except Exception:
            return dict(fallback), False

        parsed = extract_json_from_text(response)
        if parsed is not None and isinstance(parsed, dict):
            return parsed, True

        if attempt < retries - 1:
            current_prompt = (
                prompt
                + "\n\nВажно: ответь ТОЛЬКО одним валидным JSON-объектом, без пояснений."
            )

    return dict(fallback), False


def llm_text(
    prompt: str,
    fallback: str,
    max_tokens: int = 800,
    temperature: float = 0.4,
    retries: int = 2,
    min_length: int = 40,
    task: str = "general",
    use_adapter: bool | None = None,
) -> str:
    for attempt in range(retries):
        try:
            response = generate_response(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                task=task,
                use_adapter=use_adapter,
            )
        except Exception:
            return fallback

        cleaned = response.strip()
        if task == "adapt_resume":
            from utils.text_utils import strip_prompt_leakage

            cleaned = strip_prompt_leakage(cleaned)
        elif task == "sanitize_resume":
            from utils.text_utils import strip_prompt_leakage

            cleaned = strip_prompt_leakage(cleaned)
        if task == "adapt_resume" and _looks_like_resume_fluff(cleaned):
            cleaned = ""
        if len(cleaned) >= min_length and not _looks_like_error(cleaned):
            return cleaned

        if attempt < retries - 1:
            extra = "\n\nОтветь только готовым текстом на русском, без извинений и без описания ошибок."
            if task == "adapt_resume":
                extra += (
                    " Без советов HR. Только блоки с заголовками. "
                    "Не выдумывай технологии и версии (Метрика 1.0). Только русский язык."
                )
            elif task == "sanitize_resume":
                extra += (
                    " Верни только чистый текст резюме с заголовками блоков. "
                    "Без пояснений и комментариев."
                )
            prompt = prompt + extra

    return fallback


def _looks_like_resume_fluff(text: str) -> bool:
    from utils.text_utils import is_resume_fluff_line

    for line in text.split("\n"):
        if is_resume_fluff_line(line.strip()):
            return True
    return False


def _looks_like_error(text: str) -> bool:
    lower = text.lower()[:200]
    markers = (
        "error",
        "exception",
        "traceback",
        "не могу",
        "cannot",
        "sorry",
        "извините",
        "ошибка",
    )
    return any(m in lower for m in markers)
