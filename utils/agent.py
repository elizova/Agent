import re
import time

from .hh_api import get_vacancy_details
from .safe_llm import llm_json, llm_text
from .llm_provider import resume_adapter_enabled
from .text_utils import (
    chunk_text,
    dedupe_list,
    dedupe_resume_text,
    fix_contacts_section,
    is_resume_fluff_line,
    sanitize_adapted_resume,
    strip_html,
    strip_prompt_leakage,
)

EMPTY_REQUIREMENTS = {
    "skills": [],
    "experience": "",
    "duties": [],
    "soft_skills": [],
}

EMPTY_COMPARISON = {
    "missing_skills": [],
    "missing_experience": "",
    "missing_soft": [],
    "missing_duties": [],
    "recommendations": "",
}


def _merge_requirements(parts: list[dict]) -> dict:
    merged = {k: ([] if k != "experience" else "") for k in EMPTY_REQUIREMENTS}
    for part in parts:
        if not part:
            continue
        merged["skills"].extend(part.get("skills") or [])
        merged["duties"].extend(part.get("duties") or [])
        merged["soft_skills"].extend(part.get("soft_skills") or [])
        if part.get("experience") and not merged["experience"]:
            merged["experience"] = str(part["experience"])
    merged["skills"] = dedupe_list(merged["skills"])
    merged["duties"] = dedupe_list(merged["duties"])
    merged["soft_skills"] = dedupe_list(merged["soft_skills"])
    return merged


def _normalize_requirements(requirements: dict) -> dict:
    req = dict(EMPTY_REQUIREMENTS)
    if not requirements:
        return req
    req["skills"] = (
        list(requirements["skills"])
        if isinstance(requirements.get("skills"), list)
        else []
    )
    req["duties"] = (
        list(requirements["duties"])
        if isinstance(requirements.get("duties"), list)
        else []
    )
    req["soft_skills"] = (
        list(requirements["soft_skills"])
        if isinstance(requirements.get("soft_skills"), list)
        else []
    )
    exp = requirements.get("experience", "")
    req["experience"] = str(exp) if exp else ""
    return req


def _keyword_in_text(keyword: str, text: str) -> bool:
    kw_lower = keyword.lower().strip()
    text_lower = text.lower()
    # точное вхождение
    if kw_lower in text_lower:
        return True
    # совпадение по корню слова (первые 5 символов) для русской морфологии
    # "инвентаризация" найдёт "инвентаризаций", "инвентаризации" и т.д.
    words = [w for w in kw_lower.split() if len(w) > 4]
    if words and all(w[:5] in text_lower for w in words):
        return True
    # хотя бы одно значимое слово из многословного ключа
    long_words = [w for w in kw_lower.split() if len(w) > 5]
    if len(long_words) >= 2 and any(w[:5] in text_lower for w in long_words):
        return True
    return False


def calculate_ats_score(
    resume_text: str,
    requirements: dict,
    original_resume: str | None = None,
    penalize_invented: bool = False,
    ats_before: int | None = None,
) -> dict:
    if not resume_text:
        return {
            "score": 0,
            "matched": [],
            "missing": [],
            "invented": [],
            "total": 0,
            "message": "Резюме не указано — автофильтр, скорее всего, отклонит отклик.",
        }

    keywords = dedupe_list(
        (requirements.get("skills") or [])
        + (requirements.get("soft_skills") or [])
    )
    if not keywords:
        return {
            "score": 100,
            "matched": [],
            "missing": [],
            "invented": [],
            "total": 0,
            "message": "Ключевые слова не выделены — оценка по навыкам недоступна.",
        }

    resume_lower = resume_text.lower()
    orig_lower = (original_resume or "").lower()
    matched, missing, invented = [], [], []

    for kw in keywords:
        if _keyword_in_text(kw, resume_lower):
            if (
                penalize_invented
                and original_resume
                and not _keyword_in_text(kw, orig_lower)
            ):
                invented.append(kw)
            matched.append(kw)
        else:
            missing.append(kw)

    if penalize_invented and original_resume and invented:
        honest = [k for k in matched if k not in invented]
        weighted = len(honest) + 0.75 * len(invented)
        score = round(100 * weighted / len(keywords))
        if ats_before is not None and ats_before >= 99:
            score = round(100 * len(matched) / len(keywords))
        else:
            score = min(score, 96, max(score, (ats_before or 0) + 15))
    else:
        score = round(100 * len(matched) / len(keywords))

    if score >= 70:
        msg = "Хороший шанс пройти автоматический отбор по ключевым словам."
    elif score >= 40:
        msg = "Средний риск отсева: добавьте недостающие навыки в резюме."
    else:
        msg = "Высокий риск отсева без адаптации резюме под вакансию."

    if invented:
        msg += (
            f" Учтено {len(invented)} навыков, добавленных при адаптации "
            "(оценка без завышения до 100%)."
        )

    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "invented": invented,
        "total": len(keywords),
        "message": msg,
    }


def _clean_hh_params(params: dict) -> dict:
    bad_text = {
        "легкая работа",
        "спокойная работа",
        "не запарная работа",
        "хорошая работа",
        "работа",
        "легкая",
    }
    cleaned = {}
    for k, v in params.items():
        if v is None or v == "" or str(v).lower() in ("null", "none"):
            continue
        cleaned[k] = v
    text = str(cleaned.get("text", "")).strip().lower()
    if text in bad_text or len(text.split()) > 4:
        cleaned.pop("text", None)
    return cleaned


def parse_user_query_to_api_params(
    user_query: str, resume_hint: str = ""
) -> dict:
    resume_block = (
        f"\nРезюме (для выбора профессии в text): {resume_hint[:400]}"
        if resume_hint
        else ""
    )
    prompt = f"""
Ты формируешь параметры для API поиска вакансий HeadHunter (поле text ищет по НАЗВАНИЮ вакансии и навыкам в базе HH).

Поле text должно содержать 1-3 ключевых слова, описывающих реальную должность или профессию (например, «инженер», «бухгалтер», «водитель»). Избегай общих фраз вроде «лёгкая работа», «хорошая зарплата».

Если пользователь описывает желаемую работу нестандартно, выбери наиболее подходящую профессию на основе резюме и запроса.

Другие поля (только если уместны, иначе не включай):
- area: город/регион
- salary: число (100к = 100000)
- currency: RUR
- schedule: remote | fullDay | shift
- employment: full | part
- only_with_salary: true
- experience: noExperience | between1And3 | between3And6 | moreThan6

Верни только JSON.

Запрос пользователя:
{user_query}
{resume_block}
"""
    fallback = {"text": "специалист"}
    params, _ = llm_json(prompt, fallback, max_tokens=450, temperature=0.15)
    params = _clean_hh_params(params)

    if "text" not in params:
        params["text"] = "специалист"

    q_lower = user_query.lower()
    if any(
        w in q_lower
        for w in (
            "платят",
            "зарплат",
            "000",
            "руб",
            "доход",
            "100к",
            "нормально платят",
        )
    ):
        params["only_with_salary"] = True
    if "подмосков" in q_lower and "area" not in params:
        params["area"] = "Московская область"
    if any(
        w in q_lower
        for w in ("удален", "удалён", "дистанцион", "из дома", "удаленка")
    ):
        params["schedule"] = "remote"

    if "experience" in params and not any(
        x in q_lower for x in ("опыт", "лет", "стаж", "без опыта")
    ):
        del params["experience"]

    return params


def _pick_single_profession(text: str) -> str:
    if not text:
        return "специалист"
    t = str(text).strip()
    for sep in (" или ", " / ", ",", ";", "\n"):
        if sep in t:
            t = t.split(sep)[0].strip()
    words = t.split()
    if len(words) > 4:
        t = " ".join(words[:3])
    return t or "специалист"


def _format_search_display(params: dict) -> str:
    parts = [_pick_single_profession(params.get("text", "специалист"))]
    if params.get("area"):
        parts.append(str(params["area"]))
    if params.get("salary"):
        sal = params["salary"]
        cur = params.get("currency", "RUR")
        sym = "₽" if cur == "RUR" else str(cur)
        parts.append(f"от {sal:,} {sym}".replace(",", " "))
    if params.get("schedule") == "remote":
        parts.append("удалённо")
    if params.get("only_with_salary"):
        parts.append("с указанной зарплатой")
    return ", ".join(parts)


def build_hh_params_from_chat(
    messages: list[dict], resume_hint: str = ""
) -> tuple[dict, str]:
    last_assistant = ""
    for m in reversed(messages):
        if m["role"] == "assistant":
            last_assistant = m["content"]
            break

    dialogue = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Консультант'}: {m['content'][:350]}"
        for m in messages[-6:]
    )

    prompt = f"""
По диалогу сформируй ОДИН поисковый запрос для API HeadHunter.

Поле text — СТРОГО ОДНА должность (1-3 слова), самая подходящая из рекомендаций консультанта.
НЕ перечисляй несколько профессий в text. НЕ пиши «легкая работа», «IT или финансы».

Если консультант назвал несколько вариантов — выбери ОДИН лучший по резюме.

salary: число в рублях, если в диалоге важна зарплата (нормально платят → 70000-90000, 100к → 100000).
only_with_salary: true если зарплата важна.
area, schedule, employment — только если ясно из диалога.

Не включай search_summary. Только JSON: text, area, salary, currency, schedule, employment, only_with_salary, experience.

Диалог:
{dialogue}

Последний ответ консультанта:
{last_assistant[:800]}

Резюме:
{resume_hint[:400] if resume_hint else 'нет'}
"""
    data, _ = llm_json(
        prompt,
        {"text": "специалист"},
        max_tokens=350,
        temperature=0.1,
    )
    area_val = data.get("area")
    if isinstance(area_val, str) and not area_val.isdigit():
        dialogue_lower = dialogue.lower()
        if area_val.lower() not in dialogue_lower:
            data["area"] = ""
    data.pop("search_summary", None)
    params = _clean_hh_params(data)
    params["text"] = _pick_single_profession(params.get("text", "специалист"))

    full_dialog = (dialogue + last_assistant).lower()
    if "salary" not in params and any(
        w in full_dialog
        for w in (
            "зарплат",
            "платят",
            "000",
            "руб",
            "доход",
            "100к",
            "нормально плат",
        )
    ):
        params["only_with_salary"] = True
        if "salary" not in params:
            for num in ("100000", "90000", "80000", "70000", "60000", "50000"):
                if num[:2] in full_dialog or num in full_dialog:
                    params["salary"] = int(num)
                    params["currency"] = "RUR"
                    break
            if "salary" not in params:
                params["salary"] = 70000
                params["currency"] = "RUR"

    return params, _format_search_display(params)


def _extract_requirements_chunk(chunk: str) -> dict:
    prompt = f"""
Ты — ассистент по анализу вакансий. Извлеки из текста вакансии ключевые требования строго в JSON.

Формат ответа:
{{
  "skills": ["навык1", "навык2", ...],
  "experience": "опыт работы (если указан, например '1-3 года', или '')",
  "duties": ["обязанность1", "обязанность2", ...],
  "soft_skills": ["качество1", ...]
}}

Правила:
- skills – только профессиональные инструменты, технологии, методики, языки, конкретные умения. Не включай общие фразы.
- soft_skills – личностные качества, если они прямо указаны в тексте (например, "коммуникабельность", "стрессоустойчивость"). Не додумывай.
- duties – короткие глагольные фразы.
- experience – только если явно указано, иначе пустая строка.

Пример:
Текст вакансии: "Требуется инженер со знанием AutoCAD, опыт от 1 года. Обязанности: проектирование, работа с чертежами. Приветствуется внимательность к деталям."
Ответ:
{{"skills": ["AutoCAD", "проектирование"], "experience": "от 1 года", "duties": ["проектирование", "работа с чертежами"], "soft_skills": ["внимательность к деталям"]}}

Текст для анализа:
{chunk}

JSON:
"""
    data, _ = llm_json(
        prompt, dict(EMPTY_REQUIREMENTS), max_tokens=400, temperature=0.1
    )
    return _normalize_requirements(data)


def extract_requirements(
    vacancy_text: str, hh_skills: list | None = None
) -> dict:
    plain = strip_html(vacancy_text)
    if not plain or len(plain) < 50:
        reqs = dict(EMPTY_REQUIREMENTS)
    else:
        chunks = chunk_text(plain, chunk_size=1800)
        parts = [_extract_requirements_chunk(c) for c in chunks]
        reqs = _merge_requirements(parts)

    if hh_skills:
        reqs["skills"] = dedupe_list(reqs["skills"] + list(hh_skills))

    if not reqs["skills"] and not reqs["duties"]:
        reqs["_note"] = (
            "Требования извлечены частично. Используйте также навыки с карточки HH."
        )
    return reqs


def compare_resume_to_vacancy(resume_text: str, requirements: dict) -> dict:
    if not resume_text:
        c = dict(EMPTY_COMPARISON)
        c["recommendations"] = (
            "Добавьте резюме в боковой панели для сравнения."
        )
        return c

    skills = requirements.get("skills", [])
    soft = requirements.get("soft_skills", [])
    exp = requirements.get("experience", "")
    duties = requirements.get("duties", [])

    if not skills and not soft and not exp and not duties:
        c = dict(EMPTY_COMPARISON)
        c["recommendations"] = (
            "Конкретные требования не найдены — сравнение выполнено в упрощённом режиме."
        )
        return c

    req_parts = []
    if skills:
        req_parts.append(f"Навыки: {', '.join(skills)}")
    if soft:
        req_parts.append(f"Soft skills: {', '.join(soft)}")
    if exp:
        req_parts.append(f"Опыт: {exp}")
    if duties:
        req_parts.append(f"Обязанности: {', '.join(duties)}")

    prompt = f"""
Сравни резюме с требованиями. Только JSON на русском:
- missing_skills, missing_experience, missing_soft, missing_duties (списки/строка)
- recommendations: 1-2 предложения

Резюме:
{resume_text[:1500]}

Требования:
{chr(10).join(req_parts)}

JSON:
"""
    comparison, ok = llm_json(
        prompt, dict(EMPTY_COMPARISON), max_tokens=600, temperature=0.2
    )
    if not ok:
        comparison["recommendations"] = (
            "Автоматическое сравнение выполнено в упрощённом режиме. "
            "Смотрите оценку ATS и список ключевых слов ниже."
        )
        ats = calculate_ats_score(resume_text, requirements)
        comparison["missing_skills"] = ats["missing"]
        return _finalize_comparison(
            comparison, resume_text, skills, soft, duties, exp
        )

    return _finalize_comparison(
        comparison, resume_text, skills, soft, duties, exp
    )


def _finalize_comparison(comparison, resume_text, skills, soft, duties, exp):
    def filter_missing(missing_list, original_list):
        if not original_list or not isinstance(missing_list, list):
            return []
        original_lower = [item.lower().strip() for item in original_list]
        filtered = []
        for m in missing_list:
            m_lower = str(m).lower().strip()
            if any(
                m_lower == orig or orig in m_lower or m_lower in orig
                for orig in original_lower
            ):
                filtered.append(m)
        return filtered

    comparison["missing_skills"] = filter_missing(
        comparison.get("missing_skills", []), skills
    )
    comparison["missing_soft"] = filter_missing(
        comparison.get("missing_soft", []), soft
    )
    comparison["missing_duties"] = filter_missing(
        comparison.get("missing_duties", []), duties
    )

    if comparison.get("missing_experience") and exp:
        if any(
            word in resume_text.lower()
            for word in exp.lower().split()
            if len(word) > 2
        ):
            comparison["missing_experience"] = ""

    for key in EMPTY_COMPARISON:
        if key not in comparison:
            comparison[key] = (
                []
                if key not in ("missing_experience", "recommendations")
                else ""
            )
    return comparison


_MODE_INSTRUCTION_STRICT = """
СТРОГИЕ ОГРАНИЧЕНИЯ:
- Используй ТОЛЬКО информацию из исходного резюме.
- Запрещено добавлять новые профессиональные навыки (hard skills), инструменты, технологии, языки программирования, если их не было в исходном резюме.
- Добавь в раздел КЛЮЧЕВЫЕ НАВЫКИ личные качества (soft skills) из требований вакансии — ответственность, пунктуальность, коммуникабельность и т.п. Soft skills можно добавлять всегда, они не являются выдуманными профессиональными навыками.
- Опыт работы должен оставаться фактически тем же: не меняй названия компаний, должностей и даты. Разрешено менять формулировки обязанностей, чтобы они звучали более профессионально и релевантно вакансии, но без добавления новых обязанностей или проектов.
- Контакты и имя оставь точно как в исходном резюме.
"""

_MODE_INSTRUCTION_BOOST = """
РЕЖИМ РАСШИРЕННОЙ АДАПТАЦИИ:
- Создай раздел КЛЮЧЕВЫЕ НАВЫКИ и добавь в него навыки из вакансии, которые подходят кандидату по опыту.
- Обязательно добавь личные качества (soft skills) из требований вакансии — ответственность, пунктуальность, коммуникабельность и т.п.
- СТРОГО ЗАПРЕЩЕНО: не выдумывай новые места работы, не меняй названия компаний и должностей.
- СТРОГО ЗАПРЕЩЕНО: не сокращай и не удаляй строки из раздела ОПЫТ РАБОТЫ — сохраняй дословно все обязанности из исходника.
- Контакты и имя копируй точно из исходного резюме без изменений.
"""

_SANITIZER_SKILLS_STRICT = (
    "Если навык явно относится к профессиональным инструментам/технологиям "
    "и отсутствует в исходном резюме — удали его. "
    "Общие личные качества (soft skills) можно оставить."
)

_SANITIZER_SKILLS_BOOST = (
    "Удали только явно бессмысленные или мусорные фразы "
    "(например, 'moloko', 'geschenk', версии типа 'Яндекс Метрика 5.3'). "
    "Остальные навыки сохраняй."
)


def _format_requirements_for_prompt(requirements: dict) -> str:
    parts = []
    skills = requirements.get("skills") or []
    if skills:
        parts.append(f"Навыки: {', '.join(skills)}")
    exp = requirements.get("experience") or ""
    if exp:
        parts.append(f"Опыт: {exp}")
    duties = requirements.get("duties") or []
    if duties:
        parts.append(f"Обязанности: {', '.join(duties)}")
    soft = requirements.get("soft_skills") or []
    if soft:
        parts.append(f"Личные качества: {', '.join(soft)}")
    return "\n".join(parts) if parts else "Конкретные требования не выделены."


def _get_mode_instruction(allow_invented_skills: bool) -> str:
    return (
        _MODE_INSTRUCTION_BOOST
        if allow_invented_skills
        else _MODE_INSTRUCTION_STRICT
    )


def _build_skills_prompt(
    resume_text: str, requirements_text: str, allow_invented: bool
) -> str:
    if allow_invented:
        rule = (
            "Можно включать навыки из вакансии, если они правдоподобны для опыта кандидата. "
            "Обязательно добавь soft skills из требований вакансии."
        )
    else:
        rule = (
            "Включай только навыки и качества, которые прямо или косвенно упоминаются в резюме. "
            "Soft skills (ответственность, коммуникабельность и т.п.) из требований вакансии добавляй всегда."
        )
    return f"""Составь список ключевых навыков для раздела КЛЮЧЕВЫЕ НАВЫКИ резюме.

РЕЗЮМЕ КАНДИДАТА:
{resume_text[:2500]}

ТРЕБОВАНИЯ ВАКАНСИИ:
{requirements_text}

ПРАВИЛО: {rule}

Выведи только список навыков — каждый с новой строки, без нумерации и пояснений. Не более 12 навыков.
"""


def _build_draft_prompt(
    resume_text: str, requirements_text: str, mode_instruction: str
) -> str:
    return f"""
Ты — профессиональный карьерный консультант. Составь адаптированное резюме кандидата на основе его ИСХОДНОГО РЕЗЮМЕ и требований ВАКАНСИИ.

ИСХОДНОЕ РЕЗЮМЕ:
{resume_text[:3500]}

ТРЕБОВАНИЯ ВАКАНСИИ:
{requirements_text}

{mode_instruction}

ОБЯЗАТЕЛЬНО:
- Сохраняй ВСЕ детали опыта работы из исходного резюме — обязанности, даты, названия компаний, должности. Не сокращай и не выбрасывай ни одну строку из раздела ОПЫТ РАБОТЫ.
- Контакты (телефон, email) копируй точно из исходного резюме.
- Если в исходном резюме нет раздела КЛЮЧЕВЫЕ НАВЫКИ — создай его и заполни навыками из вакансии.

ФОРМАТ ОТВЕТА:
Только готовое резюме на русском языке. Используй ЗАГЛАВНЫЕ заголовки:
ИМЯ И КОНТАКТЫ
КЛЮЧЕВЫЕ НАВЫКИ
ОПЫТ РАБОТЫ
ОБРАЗОВАНИЕ
ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ

Раздел «Цель» не добавляй. Никаких пояснений, комментариев, вводных фраз. Начинай сразу с ИМЯ И КОНТАКТЫ.
"""


def _build_sanitizer_prompt(
    draft_resume: str,
    resume_text: str,
    allow_invented_skills: bool,
) -> str:
    skills_rule = (
        _SANITIZER_SKILLS_BOOST
        if allow_invented_skills
        else _SANITIZER_SKILLS_STRICT
    )
    strict_mode_extra = ""
    if not allow_invented_skills:
        strict_mode_extra = """
ДОПОЛНИТЕЛЬНО: В этом режиме запрещено добавлять в резюме новые профессиональные навыки, которых не было в исходном. Если санитайзер обнаружит такие навыки, он должен их удалить.
"""
    return f"""
Ты — ассистент, который проверяет и исправляет готовое резюме. Твоя задача: сделать текст чистым, структурированным и соответствующим правилам.

На вход подан ЧЕРНОВИК резюме и ИСХОДНОЕ РЕЗЮМЕ кандидата.

ЧЕРНОВИК:
{draft_resume[:4000]}

ИСХОДНОЕ РЕЗЮМЕ:
{resume_text[:3500]}

ПРАВИЛА ОБРАБОТКИ:
1. Убери из черновика все строки, которые являются инструкциями, советами, комментариями (например, "Вы можете добавить...", "Вот готовое резюме...", "—" без текста).
2. Убедись, что контакты (телефон, email, мессенджеры) совпадают с исходным резюме. Если в черновике контакты отсутствуют или заменены на плейсхолдеры, вставь реальные контакты из исходного резюме.
3. Приведи заголовки к стандартному виду ЗАГЛАВНЫМИ: ИМЯ И КОНТАКТЫ, КЛЮЧЕВЫЕ НАВЫКИ, ОПЫТ РАБОТЫ, ОБРАЗОВАНИЕ, ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ. Убедись, что нет раздела «Цель».
4. Проверь блок «КЛЮЧЕВЫЕ НАВЫКИ»:
   - {skills_rule}
5. Убедись, что опыт работы не содержит явно вымышленных компаний или полной замены фактов (проверь по исходному резюме). Если заметил грубые расхождения — исправь, используя исходный текст.
6. Убери дублирующиеся строки и абзацы.
7. Если какой-то обязательный блок (кроме контактов) пуст, но есть данные в исходном резюме, добавь их из исходника.
8. Верни ТОЛЬКО текст резюме — без правил, без комментариев, без нумерованных списков, без пояснений.

{strict_mode_extra}
Выведи исправленное резюме начиная прямо сейчас, без вступления:
"""


def _minimal_postprocess(text: str, original: str) -> str:
    text = strip_prompt_leakage(text or "")
    _leak_markers = [
        "ПРАВИЛА ОБРАБОТКИ",
        "Убедись, что контакты",
        "Приведи заголовки",
        "Верни только готовый",
        "Выведи исправленное резюме",
        "ДОПОЛНИТЕЛЬНО: В этом режиме",
    ]
    for marker in _leak_markers:
        idx = text.find(marker)
        if idx > 100:  # обрезаем только если перед маркером есть контент
            text = text[:idx].strip()
    lines = []
    for line in text.split("\n"):
        line = line.replace("**", "").replace("##", "").strip()
        if "[Указать" in line or "[указать" in line:
            continue
        if line.lower().startswith("блок резюме"):
            continue
        if is_resume_fluff_line(line):
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    text = fix_contacts_section(text, original)
    text = dedupe_resume_text(text)
    if len(text) < 80:
        return (
            "Адаптированное резюме сформировано частично. "
            "Скопируйте блоки выше или повторите генерацию."
        )
    return text


def _sanitize_with_llm(
    draft: str,
    resume_text: str,
    allow_invented_skills: bool,
) -> str:
    if not draft or len(draft.strip()) < 40:
        return sanitize_adapted_resume(draft, original=resume_text)

    prompt = _build_sanitizer_prompt(draft, resume_text, allow_invented_skills)
    sanitized = llm_text(
        prompt,
        fallback=draft,
        max_tokens=2000,
        temperature=0.0,
        min_length=60,
        task="sanitize_resume",
        use_adapter=False,
    )
    if sanitized == draft or len(sanitized.strip()) < 60:
        return sanitize_adapted_resume(draft, original=resume_text)
    return sanitized


def _extract_section(text: str, header: str) -> str:
    """Извлекает содержимое раздела между заголовком и следующим заголовком."""
    pattern = re.compile(
        rf"(?:^|\n){re.escape(header)}\s*\n(.*?)(?=\n[А-ЯЁ][А-ЯЁ\s]{{2,}}\n|\Z)",
        re.S | re.I,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _merge_skills_from_original(result: str, original: str) -> str:
    """Добавляет в результат навыки из оригинала, если LLM их потерял."""
    from .text_utils import filter_skill_list, _split_skill_phrases

    orig_skills_text = _extract_section(original, "КЛЮЧЕВЫЕ НАВЫКИ")
    if not orig_skills_text:
        return result

    orig_skills: list[str] = []
    for line in orig_skills_text.split("\n"):
        orig_skills.extend(_split_skill_phrases(line))
    orig_skills = filter_skill_list(orig_skills)
    if not orig_skills:
        return result

    result_lower = result.lower()
    missing_from_orig = [
        s for s in orig_skills if not _keyword_in_text(s, result_lower)
    ]
    if not missing_from_orig:
        return result

    return _inject_missing_skills(result, missing_from_orig)


def _merge_skills_with_original(result: str, original: str) -> str:
    """Добавляет в КЛЮЧЕВЫЕ НАВЫКИ навыки из оригинала которые потерялись."""
    from .text_utils import _split_skill_phrases, filter_skill_list

    orig_skills_raw = _extract_section(original, "КЛЮЧЕВЫЕ НАВЫКИ")
    if not orig_skills_raw:
        return result

    orig_skills = filter_skill_list(_split_skill_phrases(orig_skills_raw), original)
    if not orig_skills:
        return result

    result_lower = result.lower()
    missing_from_orig = [
        s for s in orig_skills
        if not _keyword_in_text(s, result_lower)
    ]
    if not missing_from_orig:
        return result

    return _inject_missing_skills(result, missing_from_orig)


def _extract_skills_from_draft(draft: str) -> list[str]:
    """Извлекает список навыков из LLM-вывода (ищет раздел КЛЮЧЕВЫЕ НАВЫКИ)."""
    from .text_utils import _normalize_section_header, _split_skill_phrases, filter_skill_list

    lines = draft.split("\n")
    in_skills = False
    skill_lines = []
    for line in lines:
        header = _normalize_section_header(line)
        if header == "КЛЮЧЕВЫЕ НАВЫКИ":
            in_skills = True
            continue
        if in_skills:
            if header and header != "КЛЮЧЕВЫЕ НАВЫКИ":
                break
            skill_lines.append(line)

    if not skill_lines:
        return []
    return filter_skill_list(_split_skill_phrases("\n".join(skill_lines)))


def _build_skills_block(skills: list[str]) -> str:
    return "КЛЮЧЕВЫЕ НАВЫКИ\n" + "\n".join(f"— {s}" for s in skills)


def _splice_skills_into_original(original: str, skills: list[str]) -> str:
    """
    Берёт оригинальное резюме и заменяет/вставляет раздел КЛЮЧЕВЫЕ НАВЫКИ.
    Всё остальное (опыт, образование, контакты) остаётся из оригинала.
    """
    from .text_utils import _normalize_section_header

    if not skills:
        return original

    lines = original.split("\n")
    skills_block = _build_skills_block(skills).split("\n")

    # ищем существующий раздел навыков и заменяем
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        header = _normalize_section_header(line)
        if header == "КЛЮЧЕВЫЕ НАВЫКИ":
            start_idx = i
            continue
        if start_idx is not None and end_idx is None:
            if _normalize_section_header(line) and _normalize_section_header(line) != "КЛЮЧЕВЫЕ НАВЫКИ":
                end_idx = i
                break

    if start_idx is not None:
        end = end_idx if end_idx is not None else len(lines)
        return "\n".join(lines[:start_idx] + skills_block + [""] + lines[end:])

    # раздела нет — вставляем перед первым разделом опыта работы
    for i, line in enumerate(lines):
        h = _normalize_section_header(line)
        if h in ("ОПЫТ РАБОТЫ",):
            return "\n".join(lines[:i] + skills_block + [""] + lines[i:])

    # нет ни навыков ни опыта — вставляем после первого пустого блока
    for i, line in enumerate(lines):
        if line.strip() == "" and i > 2:
            return "\n".join(lines[:i+1] + skills_block + [""] + lines[i+1:])

    return "\n".join(skills_block) + "\n\n" + original


def _replace_skills_section(resume: str, new_skills: list[str]) -> str:
    """Заменяет или создаёт раздел КЛЮЧЕВЫЕ НАВЫКИ, не трогая остальной текст."""
    skills_block = "КЛЮЧЕВЫЕ НАВЫКИ\n" + "\n".join(f"— {s}" for s in new_skills)

    # заменяем существующий раздел
    pattern = re.compile(
        r"КЛЮЧЕВЫЕ НАВЫКИ\s*\n.*?(?=\n[А-ЯЁ]{3}|\Z)",
        re.S,
    )
    m = pattern.search(resume)
    if m:
        return resume[: m.start()] + skills_block + "\n\n" + resume[m.end():].lstrip()

    # раздела нет — вставляем перед ОПЫТ РАБОТЫ
    m2 = re.search(r"\nОПЫТ РАБОТЫ", resume)
    if m2:
        return resume[: m2.start()] + "\n\n" + skills_block + resume[m2.start():]

    # нет ни того ни другого — добавляем после первого блока (контакты)
    lines = resume.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "" and i > 2:
            return "\n".join(lines[:i]) + "\n\n" + skills_block + "\n" + "\n".join(lines[i:])

    return skills_block + "\n\n" + resume


def _adapt_skills_only(
    resume_text: str,
    requirements_text: str,
    requirements: dict,
    allow_invented_skills: bool,
    ats_missing: list,
) -> str:
    """
    Безопасная адаптация: LLM генерирует только список навыков,
    оригинальный текст резюме остаётся нетронутым.
    Гарантирует что ATS не упадёт ниже исходного значения.
    """
    from .text_utils import filter_skill_list, _split_skill_phrases

    prompt = _build_skills_prompt(resume_text, requirements_text, allow_invented_skills)
    raw = llm_text(
        prompt,
        fallback="",
        max_tokens=400,
        temperature=0.2,
        task="sanitize_resume",
        use_adapter=False,
    )

    # парсим список навыков из ответа LLM
    lines = [
        l.strip().lstrip("—•-*0123456789. ").strip()
        for l in raw.split("\n")
        if l.strip() and len(l.strip()) > 2
    ]
    skills = filter_skill_list(lines, resume_text)

    # в строгом режиме оставляем только те навыки, что есть в резюме
    # + всегда разрешаем soft skills
    if not allow_invented_skills:
        resume_lower = resume_text.lower()
        soft = {s.lower() for s in (requirements.get("soft_skills") or [])}
        skills = [
            s for s in skills
            if _keyword_in_text(s, resume_lower) or s.lower() in soft
        ]

    # всегда добавляем soft skills из ats_missing
    if ats_missing:
        soft_set = {s.lower() for s in (requirements.get("soft_skills") or [])}
        for s in ats_missing:
            if s.lower() in soft_set and s not in skills:
                skills.append(s)

    # boost: добавляем все пропущенные
    if allow_invented_skills and ats_missing:
        from .text_utils import is_plausible_skill
        resume_lower = resume_text.lower()
        for s in ats_missing:
            if (
                s not in skills
                and not _keyword_in_text(s, resume_lower)
                and is_plausible_skill(s)
            ):
                skills.append(s)

    if not skills:
        return resume_text

    return _replace_skills_section(resume_text, skills)


def _restore_experience_if_truncated(result: str, original: str) -> str:
    """Если LLM обрезал ОПЫТ РАБОТЫ, восстанавливаем из оригинала."""
    orig_exp = _extract_section(original, "ОПЫТ РАБОТЫ")
    if not orig_exp:
        return result

    res_exp = _extract_section(result, "ОПЫТ РАБОТЫ")
    # если результат потерял > 40% символов опыта — восстанавливаем
    if res_exp and len(res_exp) >= len(orig_exp) * 0.6:
        return result

    # заменяем раздел ОПЫТ РАБОТЫ в result на оригинальный
    pattern = re.compile(
        r"(ОПЫТ РАБОТЫ\s*\n)(.*?)(\n[А-ЯЁ][А-ЯЁ\s]{2,}\n|\Z)",
        re.S,
    )
    m = pattern.search(result)
    if m:
        return result[: m.start(1)] + "ОПЫТ РАБОТЫ\n" + orig_exp + "\n\n" + result[m.start(3):]

    # раздел не найден в result — вставляем после КЛЮЧЕВЫЕ НАВЫКИ
    skills_end = re.search(r"\n(ОБРАЗОВАНИЕ|ДОПОЛНИТЕЛЬНАЯ)", result)
    if skills_end:
        insert_pos = skills_end.start()
        return result[:insert_pos] + "\n\nОПЫТ РАБОТЫ\n" + orig_exp + result[insert_pos:]

    return result


def _inject_missing_skills(resume: str, missing: list[str]) -> str:
    """Программно добавляет пропущенные скиллы в раздел КЛЮЧЕВЫЕ НАВЫКИ."""
    if not missing:
        return resume

    # фильтруем скиллы которых реально нет в резюме
    resume_lower = resume.lower()
    from .text_utils import is_plausible_skill
    to_add = [
        s for s in missing
        if not _keyword_in_text(s, resume_lower) and is_plausible_skill(s)
    ]
    if not to_add:
        return resume

    # ищем раздел КЛЮЧЕВЫЕ НАВЫКИ
    pattern = re.compile(
        r"(КЛЮЧЕВЫЕ НАВЫКИ\s*\n)(.*?)(\n\s*\n|\n[А-ЯЁ]{3,})",
        re.S,
    )
    m = pattern.search(resume)
    if m:
        header = m.group(1)
        body = m.group(2).rstrip()
        tail = m.group(3)
        extra = "\n".join(f"— {s}" for s in to_add)
        new_body = body + "\n" + extra
        return resume[: m.start()] + header + new_body + tail + resume[m.end() :]

    # раздел не найден — ищем любой заголовок навыков
    lines = resume.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^\s*(КЛЮЧЕВЫЕ\s+НАВЫКИ|НАВЫКИ)\s*$", line.strip(), re.I):
            insert_at = i + 1
            extra_lines = [f"— {s}" for s in to_add]
            lines = lines[:insert_at] + extra_lines + lines[insert_at:]
            return "\n".join(lines)

    # раздел вообще отсутствует — вставляем перед ОПЫТ РАБОТЫ или в начало
    skills_block = "КЛЮЧЕВЫЕ НАВЫКИ\n" + "\n".join(f"— {s}" for s in to_add) + "\n"
    insert_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s*ОПЫТ\s+РАБОТЫ\s*$", line.strip(), re.I):
            insert_idx = i
            break
    if insert_idx is not None:
        lines = lines[:insert_idx] + [skills_block] + lines[insert_idx:]
    else:
        lines = [skills_block] + lines
    return "\n".join(lines)


def tailor_resume(
    resume_text: str,
    vacancy_text: str,
    requirements: dict,
    missing_info: dict,
    allow_invented_skills: bool = False,
    ats_missing: list | None = None,
) -> str:
    del vacancy_text, missing_info

    if not resume_text:
        return (
            "Укажите исходное резюме в боковой панели — "
            "без него адаптация невозможна."
        )

    requirements_text = _format_requirements_for_prompt(requirements)
    mode_instruction = _get_mode_instruction(allow_invented_skills)
    draft_prompt = _build_draft_prompt(
        resume_text, requirements_text, mode_instruction
    )

    use_lora = resume_adapter_enabled() and allow_invented_skills
    draft = llm_text(
        draft_prompt,
        fallback=resume_text,
        max_tokens=2000,
        temperature=0.4 if allow_invented_skills else 0.2,
        task="adapt_resume",
        use_adapter=use_lora,
    )

    if allow_invented_skills:
        # boost: LLM переписывает → санитайзер → постобработка
        sanitized = _sanitize_with_llm(draft, resume_text, allow_invented_skills)
        result = _minimal_postprocess(sanitized, resume_text)
        result = _restore_experience_if_truncated(result, resume_text)
        result = _merge_skills_with_original(result, resume_text)
        if ats_missing:
            result = _inject_missing_skills(result, ats_missing)
    else:
        # strict: берём навыки из LLM, всё остальное — из оригинала
        skills = _extract_skills_from_draft(draft)

        # добавляем soft skills из ats_missing которых нет
        if ats_missing:
            soft_set = {s.lower() for s in (requirements.get("soft_skills") or [])}
            existing = {s.lower() for s in skills}
            for s in ats_missing:
                if s.lower() in soft_set and s.lower() not in existing:
                    skills.append(s)
                    existing.add(s.lower())

        result = _splice_skills_into_original(resume_text, skills)

    return result


def _heuristic_score(
    vac: dict, details: dict, resume_text: str | None
) -> tuple[int, str]:
    if not resume_text:
        return 5, "Резюме не указано — нейтральная оценка"

    resume_lower = resume_text.lower()
    skills = [s["name"] for s in details.get("key_skills", [])]
    score = 2.0
    skill_hits = 0
    for sk in skills[:12]:
        if _keyword_in_text(sk, resume_lower):
            skill_hits += 1
            score += 0.9

    desc = strip_html(details.get("description", ""))[:600].lower()
    name = (vac.get("name") or "").lower()
    if any(w in name for w in resume_lower.split() if len(w) > 4):
        score += 1.5

    resume_words = [w for w in resume_lower.split() if len(w) > 4][:25]
    text_hits = sum(1 for w in resume_words if w in desc)
    score += min(2.5, text_hits * 0.35)

    final = int(round(min(10, max(1, score))))
    reason = f"Совпадение навыков: {skill_hits}/{max(len(skills), 1)}"
    if text_hits:
        reason += f", общих слов в описании: {text_hits}"
    return final, reason


def _parse_llm_rankings(data: dict, expected_ids: list[str]) -> dict:
    result = {}
    if not data:
        return result

    for key, val in data.items():
        if not isinstance(val, dict):
            continue
        kid = str(key).strip().replace("ID", "").replace("id", "").strip()
        if kid in expected_ids:
            result[kid] = val

    if len(result) >= len(expected_ids) // 2:
        return result

    for key, val in data.items():
        if isinstance(val, dict) and "score" in val:
            for eid in expected_ids:
                if eid in str(key) or eid in str(val.get("reason", "")):
                    result[eid] = val
    return result


def filter_and_rank_vacancies(
    vacancies, user_resume_text=None, top_n=None, access_token=None
):
    if not vacancies:
        return []

    summaries = []
    details_cache = {}
    heuristics = {}

    for vac in vacancies:
        details = get_vacancy_details(vac["id"], access_token=access_token)
        time.sleep(0.2)
        if not details:
            continue
        vac_id_str = str(vac["id"])
        details_cache[vac_id_str] = details
        h_score, h_reason = _heuristic_score(vac, details, user_resume_text)
        heuristics[vac_id_str] = (h_score, h_reason)

        desc = strip_html(details.get("description", ""))[:500]
        skills = [s["name"] for s in details.get("key_skills", [])]
        summaries.append(
            {
                "id": vac_id_str,
                "name": vac["name"],
                "employer": vac["employer"]["name"],
                "description": desc,
                "skills": skills,
            }
        )

    if not summaries:
        return []

    expected_ids = [s["id"] for s in summaries]
    all_scores = {}
    batch_size = 4

    for i in range(0, len(summaries), batch_size):
        batch = summaries[i : i + batch_size]
        ids_list = ", ".join(s["id"] for s in batch)
        prompt = f"""Оцени релевантность каждой вакансии для кандидата по шкале 1-10 (разные оценки!).
Резюме кандидата:
{user_resume_text or "не указано"}

Верни JSON. Ключи — ТОЛЬКО эти ID: {ids_list}
Формат: {{"ID": {{"score": число от 1 до 10, "reason": "одно предложение"}}}}

Вакансии:
"""
        for s in batch:
            prompt += (
                f"\nID {s['id']}: {s['name']} | {s['employer']}\n"
                f"Навыки: {', '.join(s['skills'][:8]) or 'нет'}\n"
                f"Описание: {s['description'][:300]}\n"
            )

        data, ok = llm_json(prompt, {}, max_tokens=600, temperature=0.35)
        if ok:
            parsed = _parse_llm_rankings(data, [s["id"] for s in batch])
            all_scores.update(parsed)

    ranked = []
    for vac in vacancies:
        vac_id_str = str(vac["id"])
        if vac_id_str not in details_cache:
            continue

        h_score, h_reason = heuristics.get(vac_id_str, (5, ""))
        entry = all_scores.get(vac_id_str, {})
        llm_score = entry.get("score")
        try:
            llm_score = (
                int(float(llm_score)) if llm_score is not None else None
            )
            llm_score = max(1, min(10, llm_score))
        except (TypeError, ValueError):
            llm_score = None

        if llm_score is not None:
            final_score = round(0.5 * h_score + 0.5 * llm_score)
            reason = entry.get("reason") or h_reason
        else:
            final_score = h_score
            reason = h_reason + " (оценка по совпадению с резюме)"

        ranked.append(
            {
                "vac": vac,
                "score": final_score,
                "reason": reason,
                "details": details_cache[vac_id_str],
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    if top_n:
        return ranked[:top_n]
    return ranked
