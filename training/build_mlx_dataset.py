import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SRC_CANDIDATES = (
    DATA_DIR / "resume_adaptation.jsonl",
    DATA_DIR / "resume_adaptation.example.jsonl",
)
OUT_DIR = DATA_DIR / "mlx"
TRAIN_RATIO = 0.9
MAX_FIELD_CHARS = int(os.getenv("TRAIN_MAX_FIELD_CHARS", "0") or "0")


def resolve_source() -> Path:
    for path in SRC_CANDIDATES:
        if path.exists() and path.stat().st_size > 10:
            return path
    raise SystemExit(
        "Не найден файл с данными.\n"
        "Положите пары резюме в:\n"
        "  training/data/resume_adaptation.jsonl\n"
        "или переименуйте ваш файл в это имя."
    )


def load_samples(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    rows: list[dict] = []
    line_objects = 0
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                rows.append(json.loads(line))
                line_objects += 1
            except json.JSONDecodeError:
                pass
    if line_objects >= 3:
        return rows

    rows = []
    dec = json.JSONDecoder()
    pos = 0
    while pos < len(content):
        while pos < len(content) and content[pos] in " \n\r\t,":
            pos += 1
        if pos >= len(content):
            break
        obj, end = dec.raw_decode(content, pos)
        rows.append(obj)
        pos = end

    return rows


def validate_rows(rows: list[dict]) -> list[dict]:
    ok = []
    for i, row in enumerate(rows, 1):
        if not row.get("resume_original") or not row.get("resume_adapted"):
            print(f"  пропуск #{i}: нет resume_original или resume_adapted")
            continue
        ok.append(row)
    return ok


def _clip(text: str, label: str) -> str:
    if not text or MAX_FIELD_CHARS <= 0 or len(text) <= MAX_FIELD_CHARS:
        return text
    clipped = text[:MAX_FIELD_CHARS].rstrip() + "\n… [обрезано]"
    print(f"  обрезка {label}: {len(text)} → {MAX_FIELD_CHARS} символов")
    return clipped


def build_prompt(sample: dict) -> str:
    title = sample.get("vacancy_title") or "Вакансия"
    reqs = _clip(
        sample.get("vacancy_requirements") or "", "vacancy_requirements"
    )
    resume_orig = _clip(sample["resume_original"], "resume_original")
    allow = sample.get("allow_invented_skills", False)
    inv = (
        "Можно добавить навыки из вакансии, если их не было в исходном."
        if allow
        else "Не добавляй навыки, которых не было в исходном резюме."
    )
    return f"""Адаптируй резюме под вакансию на русском. Формат: ИМЯ И КОНТАКТЫ, КЛЮЧЕВЫЕ НАВЫКИ, ОПЫТ РАБОТЫ, ОБРАЗОВАНИЕ, ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (без блока «Цель»).
Только текст резюме, без советов читателю.
{inv}

Вакансия: {title}
Требования:
{reqs}

ИСХОДНОЕ РЕЗЮМЕ:
{resume_orig}

АДАПТИРОВАННОЕ РЕЗЮМЕ:
"""


def main():
    src = resolve_source()
    print(f"Источник: {src}")

    rows = validate_rows(load_samples(src))
    if len(rows) < 3:
        raise SystemExit(
            f"Нужно минимум 3 валидных примера, сейчас: {len(rows)}"
        )

    random.seed(42)
    random.shuffle(rows)
    split = max(1, int(len(rows) * TRAIN_RATIO))
    train_rows, valid_rows = rows[:split], rows[split:]
    if not valid_rows:
        valid_rows = rows[-1:]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def write_split(name: str, data: list):
        path = OUT_DIR / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as out:
            for s in data:
                completion = _clip(
                    s["resume_adapted"].strip(), "resume_adapted"
                )
                record = {
                    "prompt": build_prompt(s),
                    "completion": completion,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"  {path}: {len(data)} примеров")

    print(f"Всего примеров: {len(rows)}")
    write_split("train", train_rows)
    write_split("valid", valid_rows)
    print("\nГотово. Дальше:")
    print("  python training/train_resume_lora.py")


if __name__ == "__main__":
    main()
