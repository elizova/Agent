import re
from html import unescape


def strip_html(html_text: str) -> str:
    if not html_text:
        return ""
    text = unescape(html_text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(
    text: str, chunk_size: int = 1800, overlap: int = 200
) -> list[str]:
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


RESUME_SECTION_ORDER = [
    "ИМЯ И КОНТАКТЫ",
    "КЛЮЧЕВЫЕ НАВЫКИ",
    "ОПЫТ РАБОТЫ",
    "ОБРАЗОВАНИЕ",
    "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ",
]

_HEADER_ALIASES = {
    "имя и контакты": "ИМЯ И КОНТАКТЫ",
    "контакты": "ИМЯ И КОНТАКТЫ",
    "цель": None,
    "цели": None,
    "ожидания": None,
    "ключевые навыки": "КЛЮЧЕВЫЕ НАВЫКИ",
    "навыки": "КЛЮЧЕВЫЕ НАВЫКИ",
    "опыт работы": "ОПЫТ РАБОТЫ",
    "опыт": "ОПЫТ РАБОТЫ",
    "образование": "ОБРАЗОВАНИЕ",
    "дополнительная информация": "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ",
    "дополнительно": "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ",
}

_JUNK_CONTACT_RE = re.compile(
    r"обязанност|достижен|опыт\s*работ|навык|образован|личн(ые|ые)\s+качеств|"
    r"ключевые\s+навыки|дополнительн",
    re.I,
)

_GARBAGE_SKILL_RE = re.compile(
    r"(moloko|geschenk|vouch|made in ukraine|púš|p[uú]š|–moloko|more_email|"
    r"имя:\s*имя|обязанности и достижения)",
    re.I,
)
_VERSION_SPAM_RE = re.compile(
    r"(яндекс\s*метрик|инкотермс|метрик[аи])\s*[\d.]+",
    re.I,
)
_CONTACT_IN_SKILL_RE = re.compile(
    r"(@\w|email\s*:|phone\s*:|telegram\s*:|тел\.|\+7\s*\(|xxx\.ru)",
    re.I,
)
_EXPERIENCE_FRAGMENT_RE = re.compile(
    r"(«|»|более\s+\d|в\s+неделю|в\s+день|в\s+месяц|в\s+том\s+числе|особо\s+крупн|"
    r"^\s*как\s+|сервисного\s+обслуживания|переговор|млн\s|миллион|рубл|\d\s*%|"
    r"компани[йяе]|заключил|провел|провёл|ежедневно|холодн|выезд|прибыл)",
    re.I,
)
_PLACEHOLDER_RE = re.compile(
    r"\[[^\]]+\]|номер\s+(телефона|email|whatsapp|telegram)|не\s+указано",
    re.I,
)
_SKILL_SECTION_RE = re.compile(
    r"(?:ключевые\s+)?навыки\s*:?\s*\n(.+?)(?=\n\s*(?:опыт|образование|дополнительн|$))",
    re.I | re.S,
)
_INLINE_HEADER = re.compile(
    r"^("
    r"имя и контакты|контакты|цель|цели|ключевые навыки|навыки|"
    r"опыт работы|опыт|образование|дополнительная информация|дополнительно|"
    r"ожидания"
    r")\s*:\s*(.*)$",
    re.I,
)

_ALLOWED_LATIN_SKILLS = frozenset(
    {
        "sql",
        "git",
        "crm",
        "api",
        "rest",
        "excel",
        "word",
        "powerpoint",
        "jira",
        "confluence",
        "python",
        "java",
        "php",
        "html",
        "css",
        "javascript",
        "docker",
        "linux",
        "windows",
        "macos",
        "figma",
        "photoshop",
        "1с",
        "ibso",
    }
)


def _normalize_section_header(line: str) -> str | None:
    raw = line.strip().strip("*#").strip()
    if not raw:
        return None
    name = raw.rstrip(":").strip().lower()
    if name in _HEADER_ALIASES:
        return _HEADER_ALIASES[name]
    upper = raw.rstrip(":").strip().upper()
    for canonical in RESUME_SECTION_ORDER:
        if upper == canonical or upper.startswith(canonical):
            return canonical
    return None


def _split_skill_phrases(text: str) -> list[str]:
    parts = re.split(r"[,;•\n]|(?:\s*[-*]\s+)", text)
    out = []
    for p in parts:
        p = p.strip().strip(".")
        if p and len(p) > 2:
            out.append(p)
    return out


def _dedupe_paragraph_lines(lines: list[str]) -> list[str]:
    seen = set()
    out = []
    for line in lines:
        line = line.strip().lstrip("*-• ").strip()
        if not line or line.lower().startswith("блок резюме"):
            continue
        key = re.sub(r"\s+", " ", line.lower())
        if key in seen:
            continue
        if any(
            key in s or s in key for s in seen if len(s) > 20 and len(key) > 20
        ):
            continue
        seen.add(key)
        out.append(line)
    return out


def _cyrillic_letter_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 1.0
    cyr = sum(1 for c in letters if "\u0400" <= c <= "\u04ff" or c in "ёЁ")
    return cyr / len(letters)


def dedupe_list(items: list, max_items: int = 50) -> list:
    seen = set()
    result = []
    for item in items:
        if not item or not str(item).strip():
            continue
        key = str(item).strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(str(item).strip())
        if len(result) >= max_items:
            break
    return result


def is_experience_fragment(text: str) -> bool:
    s = text.strip()
    if len(s) < 3:
        return True
    if _EXPERIENCE_FRAGMENT_RE.search(s):
        return True
    if s.count("(") >= 1 and len(s) > 35:
        return True
    if re.search(r"\d{4}", s) and len(s) > 25:
        return True
    if len(s.split()) > 8:
        return True
    return False


def is_plausible_skill(skill: str, original_lower: str = "") -> bool:
    s = skill.strip()
    if len(s) < 2 or len(s) > 55:
        return False
    if is_experience_fragment(s):
        return False
    if _GARBAGE_SKILL_RE.search(s) or _CONTACT_IN_SKILL_RE.search(s):
        return False
    if _VERSION_SPAM_RE.search(s):
        return False
    low = s.lower()
    if "метрика" in low and re.search(r"\d", s):
        return False
    if re.search(r"\b\d+\.\d+\s*$", s) and re.search(
        r"(метрик|инкотермс)", low
    ):
        return False

    latin_words = re.findall(r"[a-z]{3,}", s, re.I)
    if latin_words and re.search(r"[а-яё]", s, re.I):
        known = all(w.lower() in _ALLOWED_LATIN_SKILLS for w in latin_words)
        in_orig = original_lower and any(
            w.lower() in original_lower for w in latin_words
        )
        if not known and not in_orig and _cyrillic_letter_ratio(s) < 0.55:
            return False

    if _cyrillic_letter_ratio(s) < 0.3 and len(s) > 12:
        if not original_lower or low not in original_lower:
            return False
    return True


def dedupe_versioned_skills(skills: list[str]) -> list[str]:
    seen_roots: set[str] = set()
    out: list[str] = []
    for skill in skills:
        root = re.sub(r"\s*[\d.]+\s*$", "", skill.lower()).strip()
        root = re.sub(r"\s+", " ", root)
        if root in seen_roots:
            continue
        if re.search(r"\d", skill):
            for prev in list(seen_roots):
                if root.startswith(prev) or prev.startswith(root):
                    skill = re.sub(r"\s*[\d.]+\s*$", "", skill).strip()
                    root = prev
                    break
        seen_roots.add(root)
        out.append(skill)
    return out


def filter_skill_list(skills: list[str], original: str = "") -> list[str]:
    orig_lower = (original or "").lower()
    cleaned = [
        s.strip()
        for s in skills
        if s.strip() and is_plausible_skill(s.strip(), orig_lower)
    ]
    return dedupe_list(dedupe_versioned_skills(cleaned), max_items=18)


def is_resume_fluff_line(line: str) -> bool:
    if not line or len(line) < 8:
        return False
    low = line.lower()
    fluff = (
        "желаю успех",
        "перед отправкой",
        "убедитесь",
        "используйте конкрет",
        "используйте пример",
        "вашей карьер",
        "ваше резюме",
        "ваш отклик",
        "рекомендую вам",
        "советую вам",
        "обратите внимание",
        "не забудьте",
        "удачи в поиск",
        "надеюсь, этот",
        "данный текст",
        "ниже привед",
        "как ии",
        "как ассистент",
        "я подготовил",
        "вот адаптирован",
        "вы можете добавить",
        "вот готовое резюме",
    )
    if any(f in low for f in fluff):
        return True
    if low.startswith(("вы ", "вам ", "тебе ", "твой ", "твоя ")):
        if any(
            w in low
            for w in ("убедит", "используй", "добавь", "провер", "отправ")
        ):
            return True
    return False


def is_junk_contact_line(line: str) -> bool:
    s = line.strip()
    if not s or len(s) < 2:
        return True
    if _JUNK_CONTACT_RE.search(s):
        return True
    low = s.lower().rstrip(":")
    if low in (
        "обязанности и достижения",
        "обязанности",
        "достижения",
        "обязанности и достижения:",
    ):
        return True
    if s.startswith("—") or s.startswith("- "):
        return True
    if "«" in s and "»" in s and len(s) > 25:
        return True
    return False


def is_garbage_experience_line(line: str) -> bool:
    low = line.lower()
    if _GARBAGE_SKILL_RE.search(line):
        return True
    if "made in ukraine" in low or "geschenk" in low or "moloko" in low:
        return True
    if re.search(r"^(among\s+clients|вакансия\s*:)", low):
        return True
    if re.search(r"умею (оцени|работать с большими объём)", low):
        return True
    if (
        re.search(r"[a-z]{4,}", line)
        and re.search(r"[а-яё]", line)
        and _cyrillic_letter_ratio(line) < 0.45
    ):
        if not any(t in low for t in ("git", "crm", "sql", "api", "rest")):
            return True
    return False


def strip_prompt_leakage(text: str) -> str:
    if not text:
        return text
    cut_markers = (
        r"\n\s*РЕЗЮМЕ\s*:",
        r"\n\s*ИСХОДНОЕ\s+РЕЗЮМЕ",
        r"\n\s*ИТОГОВОЕ\s+РЕЗЮМЕ",
        r"\n\s*АДАПТИРОВАННОЕ\s+РЕЗЮМЕ",
        r"\n\s*Требования\s*:",
        r"\n\s*ТРЕБОВАНИЯ\s+ВАКАНСИИ",
    )
    for pat in cut_markers:
        m = re.search(pat, text, re.I)
        if m:
            text = text[: m.start()].strip()

    lines: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        low = s.lower().rstrip(":")
        if not s or s == "—":
            continue
        if low in (
            "вакансия",
            "резюме",
            "требования",
            "исходное резюме",
            "контактная информация",
        ):
            continue
        if low.startswith(("вакансия:", "резюме:", "контактная информация:")):
            continue
        if re.match(r"^\[ука", s, re.I):
            continue
        if re.match(r"^soft\s+skills\s*:?\s*$", low):
            continue
        # is_junk_contact_line убирает строки с "—" — применяем только для
        # явного мусора (плейсхолдеры, пустые строки), но НЕ для тире-пунктов
        if (
            is_junk_contact_line(s)
            and not _normalize_section_header(line)
            and not s.startswith("—")
            and not s.startswith("- ")
            and not s.startswith("• ")
        ):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def dedupe_resume_text(text: str) -> str:
    if not text:
        return text

    text = re.sub(r"Блок резюме\s*#\d+\s*", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)

    sections: dict[str, list[str]] = {}
    current: str | None = None
    preamble: list[str] = []

    for line in text.split("\n"):
        inline = _INLINE_HEADER.match(line.strip())
        if inline:
            header = _normalize_section_header(inline.group(1))
            body = inline.group(2).strip()
            if header:
                current = header
                sections.setdefault(current, [])
                if body:
                    sections[current].append(body)
                continue
            current = None
            continue

        header = _normalize_section_header(line)
        if header is not None:
            if header:
                current = header
                sections.setdefault(current, [])
            else:
                current = None
            continue
        if current:
            sections[current].append(line)
        elif line.strip():
            preamble.append(line)

    merged: dict[str, list[str]] = {}
    for name, lines in sections.items():
        if name not in merged:
            merged[name] = []
        merged[name].extend(lines)

    if "КЛЮЧЕВЫЕ НАВЫКИ" in merged:
        all_phrases = []
        for line in merged["КЛЮЧЕВЫЕ НАВЫКИ"]:
            line = re.sub(r"^ключевые навыки\s*:\s*", "", line, flags=re.I)
            all_phrases.extend(_split_skill_phrases(line))
        skills = filter_skill_list(dedupe_list(all_phrases))
        merged["КЛЮЧЕВЫЕ НАВЫКИ"] = (
            [", ".join(skills)] if skills else merged["КЛЮЧЕВЫЕ НАВЫКИ"][:1]
        )

    merged.pop("ЦЕЛЬ", None)

    for name in (
        "ОПЫТ РАБОТЫ",
        "ОБРАЗОВАНИЕ",
        "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ",
        "ИМЯ И КОНТАКТЫ",
    ):
        if name in merged:
            cleaned = _dedupe_paragraph_lines(merged[name])
            if name == "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ":
                filtered = []
                for ln in cleaned:
                    low = ln.lower()
                    if low.startswith("навыки:") or low.startswith("цел"):
                        continue
                    if "ключевые навыки" in low and ":" in ln:
                        continue
                    filtered.append(ln)
                cleaned = filtered
            merged[name] = cleaned

    parts = []
    if preamble:
        parts.append("\n".join(_dedupe_paragraph_lines(preamble)))

    for section in RESUME_SECTION_ORDER:
        if section not in merged or not any(
            l.strip() for l in merged[section]
        ):
            continue
        body = "\n".join(merged[section]).strip()
        if section == "КЛЮЧЕВЫЕ НАВЫКИ":
            parts.append(f"{section}\n{body}")
        else:
            lines = _dedupe_paragraph_lines(merged[section].copy())
            parts.append(section + "\n" + "\n".join(lines))

    return "\n\n".join(parts).strip()


def extract_contacts_lines(resume_text: str) -> list[str]:
    if not resume_text:
        return []
    lines: list[str] = []
    seen: set[str] = set()

    def add(item: str):
        item = item.strip()
        key = item.lower()
        if (
            item
            and key not in seen
            and not _PLACEHOLDER_RE.search(item)
            and not is_junk_contact_line(item)
        ):
            seen.add(key)
            lines.append(item)

    for m in re.finditer(
        r"(?:\+7|8)[\s\-()]*(?:\d[\s\-()]*){9,10}", resume_text
    ):
        add(m.group(0))
    for m in re.finditer(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", resume_text, re.I):
        add(m.group(0))
    for m in re.finditer(
        r"(?:telegram|tg|whatsapp|ватсап)\s*[:@]?\s*[@\w]+", resume_text, re.I
    ):
        add(m.group(0).strip())

    for line in resume_text.split("\n")[:8]:
        line = line.strip()
        if not line or _PLACEHOLDER_RE.search(line):
            continue
        if re.match(r"^(обязанност|достижен|—\s|-\s)", line, re.I):
            break
        if "@" in line or re.search(r"\+?\d[\d\s\-()]{8,}", line):
            add(line)
            continue
        if (
            2 < len(line) < 60
            and not is_experience_fragment(line)
            and not re.search(r"навык|опыт|образован", line, re.I)
            and sum(1 for c in line if c.isupper()) <= 4
        ):
            if not any(ch.isdigit() for ch in line) or len(line) < 25:
                add(line)

    return lines[:6]


def fix_contacts_section(adapted: str, original: str) -> str:
    if not adapted:
        return adapted

    orig_lines = extract_contacts_lines(original)
    lines = adapted.split("\n")
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if line.strip().upper().startswith("ИМЯ И КОНТАКТЫ") and not replaced:
            out.append("ИМЯ И КОНТАКТЫ")
            i += 1
            while i < len(lines) and not _normalize_section_header(lines[i]):
                i += 1
            if orig_lines:
                out.extend(orig_lines)
            replaced = True
            continue
        if (
            _PLACEHOLDER_RE.search(line) or is_junk_contact_line(line)
        ) and not _normalize_section_header(line):
            i += 1
            continue
        out.append(line)
        i += 1

    if not replaced and orig_lines:
        return "ИМЯ И КОНТАКТЫ\n" + "\n".join(orig_lines) + "\n\n" + adapted
    return "\n".join(out)


def sanitize_adapted_resume(text: str, original: str = "") -> str:
    if not text:
        return text

    text = dedupe_resume_text(strip_prompt_leakage(text))
    lines = text.split("\n")
    out: list[str] = []
    section: str | None = None

    for line in lines:
        header = _normalize_section_header(line)
        if header:
            section = header
            out.append(header)
            continue
        if section == "ОПЫТ РАБОТЫ" and is_garbage_experience_line(line):
            continue
        if is_resume_fluff_line(line):
            continue
        out.append(line)

    result_lines: list[str] = []
    i = 0
    while i < len(out):
        line = out[i]
        if line.strip().upper().startswith("КЛЮЧЕВЫЕ НАВЫКИ"):
            result_lines.append("КЛЮЧЕВЫЕ НАВЫКИ")
            skill_lines = []
            i += 1
            while i < len(out) and not _normalize_section_header(out[i]):
                skill_lines.append(out[i])
                i += 1
            phrases: list[str] = []
            for sl in skill_lines:
                phrases.extend(_split_skill_phrases(sl))
            filtered = filter_skill_list(phrases, original)
            if filtered:
                result_lines.append(", ".join(filtered))
            continue
        result_lines.append(line)
        i += 1

    return dedupe_resume_text("\n".join(result_lines).strip())
