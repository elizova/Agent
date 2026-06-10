# AI-агент для поиска работы и адаптации резюме

Курсовой проект: **использование больших языковых моделей для создания ИИ-агентов** (+ дообучение LoRA для адаптации резюме).

## Архитектура

| Компонент | Назначение |
|-----------|------------|
| **Streamlit** (`app.py`, `pages/`) | Интерфейс |
| **FastAPI** (`api/`) | REST API, авторизация, данные в Postgres |
| **PostgreSQL** (Docker) | Резюме, история — **отдельно у каждого пользователя** |
| **MLX / API** | LLM: локально или OpenAI-совместимый endpoint |
| **LoRA** (`training/`) | Дообучение только на задачу адаптации резюме |

### Две авторизации

1. **Email + пароль** — вход в приложение, ваши резюме и история.
2. **HeadHunter OAuth** — опционально, для API hh.ru (кнопка «Подключить HH» в сайдбаре после входа по email).

## Быстрый старт

### 1. Docker: база и API

```bash
cp .env.example .env
# Заполните HH_CLIENT_ID, HH_CLIENT_SECRET, JWT_SECRET

docker compose up -d
```

API: http://localhost:8000/docs  
Postgres: `localhost:5432`, user/pass/db: `career` / `career` / `career_agent`

### 2. Streamlit (на хосте)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-api.txt   # если запускаете API локально без Docker

# Локальная модель (Mac Apple Silicon):
pip install -r requirements-ml.txt

streamlit run app.py
```

Откройте http://localhost:8501 → раздел **Вход** → регистрация → остальные страницы.

### 3. LLM: локально или облако

В `.env`:

```env
# Локально (Mac + MLX):
LLM_PROVIDER=local
LLM_LOCAL_MODEL=mlx-community/Qwen2.5-3B-Instruct-4bit

# Облако (без MLX):
LLM_PROVIDER=api
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_API_KEY=ваш_ключ
LLM_API_MODEL=google/Qwen2.5-3B-Instruct-4bit
```

### 4. Дообучение резюме

Подробно: **[training/README.md](training/README.md)**

Кратко:

1. Положите пары резюме в `training/data/resume_adaptation.jsonl`
2. `python training/build_mlx_dataset.py`
3. `python training/train_resume_lora.py`
4. В `.env`: `RESUME_ADAPTER_PATH=training/output/resume-lora`

