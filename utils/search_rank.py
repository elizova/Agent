import re


def _salary_sort_key(vac: dict) -> int:
    sal = vac.get("salary") or {}
    return sal.get("to") or sal.get("from") or 0


def _query_words(user_query: str, params: dict) -> list[str]:
    text = (user_query or "") + " " + str(params.get("text", ""))
    words = re.findall(r"[а-яёa-z]{4,}", text.lower())
    stop = {
        "хочу",
        "работу",
        "работа",
        "где",
        "нибудь",
        "нужна",
        "нужен",
        "очень",
        "чтобы",
        "который",
        "которая",
    }
    return [w for w in words if w not in stop][:15]


def sort_vacancies(items: list, user_query: str, params: dict) -> list:
    if not items:
        return []

    words = _query_words(user_query, params)
    want_salary = bool(
        params.get("salary")
        or params.get("only_with_salary")
        or any(
            w in (user_query or "").lower()
            for w in ("зарплат", "оплат", "доход", "руб", "000", "тыс")
        )
    )

    def rank(vac: dict) -> tuple:
        score = 0
        name = (vac.get("name") or "").lower()
        snippet = str(vac.get("snippet") or "").lower()
        area = str(params.get("area", "")).lower()

        if vac.get("salary"):
            score += 40
            if want_salary:
                score += 25
        elif want_salary:
            score -= 15

        for w in words:
            if w in name:
                score += 8
            if w in snippet:
                score += 3

        if area and area in snippet:
            score += 10

        if (
            params.get("schedule") == "remote"
            or "удален" in (user_query or "").lower()
        ):
            if "удал" in snippet or "remote" in snippet:
                score += 12

        sal_key = _salary_sort_key(vac)
        return (score, sal_key)

    return sorted(items, key=rank, reverse=True)
