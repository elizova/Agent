# Дообучение модели для адаптации резюме

Здесь — **настоящее fine-tuning (LoRA)** под задачу «переписать резюме под вакансию».  
Остальные шаги агента (парсинг запроса, ключевые слова) по-прежнему используют базовую модель или API.

## 1. Куда класть данные

Положите файл с примерами сюда:

```
training/data/resume_adaptation.jsonl
```

Можно скопировать шаблон:

```bash
cp training/data/resume_adaptation.example.jsonl training/data/resume_adaptation.jsonl
```

### Формат одной строки (JSONL)

Каждая строка — один JSON-объект:

| Поле | Обязательно | Описание |
|------|-------------|----------|
| `resume_original` | да | Исходное резюме кандидата |
| `resume_adapted` | да | Эталон: как резюме должно выглядеть после адаптации |
| `vacancy_title` | нет | Название вакансии |
| `vacancy_requirements` | нет | Текст требований / описание вакансии |
| `allow_invented_skills` | нет | `true` / `false` — можно ли добавлять навыки |

Пример:

```json
{
  "resume_original": "Иванов Иван\nОпыт: Python 2 года...",
  "resume_adapted": "КЛЮЧЕВЫЕ НАВЫКИ\nPython, FastAPI...\n\nОПЫТ РАБОТЫ\n...",
  "vacancy_title": "Python-разработчик",
  "vacancy_requirements": "Требуется FastAPI, PostgreSQL, Docker",
  "allow_invented_skills": false
}
```

**Сколько данных:** для курсовой обычно достаточно **50–200** качественных пар; для заметного эффекта — **500+**.

Рекомендации по сбору:

- Пары «исходное резюме → адаптированное под конкретную вакансию» (ручная правка или проверенная генерация).
- Разные профессии и уровни.
- `resume_adapted` в том же формате, что ожидает приложение (блоки КЛЮЧЕВЫЕ НАВЫКИ, ЦЕЛЬ, ОПЫТ РАБОТЫ…).

## 2. Подготовка датасета для MLX

На Mac с Apple Silicon:

```bash
pip install mlx-lm
python training/build_mlx_dataset.py
```

Скрипт создаст:

```
training/data/mlx/
  train.jsonl
  valid.jsonl
```

(90% train / 10% valid из `resume_adaptation.jsonl`).

## 3. Запуск обучения LoRA

```bash
python training/train_resume_lora.py
```

По умолчанию:

- базовая модель: `mlx-community/Qwen2.5-3B-Instruct-4bit` (как в приложении);
- адаптер сохраняется в `training/output/resume-lora/`.

Параметры через переменные окружения:

```bash
export TRAIN_BASE_MODEL=mlx-community/Qwen2.5-3B-Instruct-4bit
export TRAIN_ITERS=600
export TRAIN_BATCH_SIZE=2
python training/train_resume_lora.py
```

### Mac M3 (или M1/M2/M4) с 16 GB RAM

Обычный профиль (`batch_size=2`, `max_seq_length=2048`) часто упирается в память и swap.
Для 16 GB используйте:

```bash
TRAIN_MAX_FIELD_CHARS=2500 python training/build_mlx_dataset.py
TRAIN_PROFILE=m3-16g python training/train_resume_lora.py
```

Ожидайте **~30–90 минут** обучения (зависит от размера датасета). В Activity Monitor память должна держаться примерно в **12–14 GB**; если swap > 5 GB — остановите и уменьшите `TRAIN_MAX_SEQ_LENGTH=512`.

### Если Mac перегружается или перезагружается

Используйте **лёгкий профиль** (меньше RAM, дольше по времени):

```bash
TRAIN_PROFILE=light python training/train_resume_lora.py
```

(для 16 GB `m3-16g` обычно надёжнее: короче последовательности в батче)

Что делает `light`: `batch_size=1`, 8 слоёв LoRA, `max_seq_length=1024`, gradient checkpointing, реже валидация, периодическая очистка кэша MLX.

Дополнительно перед обучением можно **укоротить примеры** в датасете:

```bash
TRAIN_MAX_FIELD_CHARS=2500 python training/build_mlx_dataset.py
TRAIN_PROFILE=light python training/train_resume_lora.py
```

| Переменная | По умолчанию | Зачем |
|------------|--------------|--------|
| `TRAIN_PROFILE` | — | `m3-16g` (16 GB Mac), `light` — общий лёгкий режим |
| `TRAIN_BATCH_SIZE` | 2 (1 в light) | Главный рычаг памяти |
| `TRAIN_MAX_SEQ_LENGTH` | 2048 (1024 в light) | Длинные резюме = много RAM |
| `TRAIN_GRAD_CHECKPOINT` | 0 (1 в light) | Меньше памяти, чуть медленнее |
| `TRAIN_LORA_LAYERS` | 16 (8 в light) | Меньше обучаемых параметров |
| `TRAIN_ITERS` | 600 (400 в light) | Меньше итераций — быстрее закончить |
| `TRAIN_MAX_FIELD_CHARS` | 0 | Обрезка текстов при `build_mlx_dataset.py` |

Перед запуском закройте браузер, Streamlit и Docker. В **Мониторинг системы** смотрите «Память» — если swap растёт до десятков ГБ, остановите (`Ctrl+C`) и уменьшите `TRAIN_MAX_SEQ_LENGTH` или `TRAIN_BATCH_SIZE`.

Обучение идёт **на вашем Mac**, не в Docker (нужен GPU Apple).

## 4. Подключить адаптер в приложении

В `.env`:

```env
LLM_PROVIDER=local
RESUME_ADAPTER_PATH=training/output/resume-lora
```

Перезапустите Streamlit. При **адаптации резюме** (шаги `adapt_resume` в агенте) будет использоваться дообученный адаптер; остальные вызовы LLM — базовая модель.

Проверка в логах/интерфейсе: в сайдбаре можно вывести `provider_label()` — будет `local+adapter (resume-lora)`.

## 5. Облачная модель без MLX

Если локально не обучаете, но хотите API для всего агента:

```env
LLM_PROVIDER=api
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_API_KEY=sk-...
LLM_API_MODEL=google/gemma-2-9b-it
```

Дообученный адаптер в режиме `api` **не подключается** — его нужно либо мержить в модель отдельно, либо использовать `LLM_PROVIDER=local` с адаптером.

## 6. Структура папки

```
training/
  README.md                 ← вы здесь
  data/
    resume_adaptation.jsonl ← ВАШИ данные (в git не коммитить большие файлы)
    resume_adaptation.example.jsonl
    mlx/                    ← генерируется build_mlx_dataset.py
      train.jsonl
      valid.jsonl
  output/
    resume-lora/            ← веса после train_resume_lora.py
  build_mlx_dataset.py
  train_resume_lora.py
```
