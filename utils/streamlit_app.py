import os
import time

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from utils.mlx_env import configure_mlx_env

configure_mlx_env()

from utils import api_client
from utils.auth_ui import get_auth_token, is_logged_in, require_auth
from utils.db import get_saved_resume, init_db
from utils.llm_provider import ensure_local_model_loaded, provider_label
from utils.auth_storage import persist_auth_token, restore_auth_token
from utils.oauth import (
    exchange_code_for_token,
    get_auth_url,
    peek_app_jwt_from_state,
    refresh_access_token,
)

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Manrope', 'Segoe UI', sans-serif;
}

.hero {
    background: linear-gradient(120deg, #1a1a2e 0%, #16213e 45%, #0f3460 100%);
    padding: 2rem 2.2rem;
    border-radius: 18px;
    color: #f0f4ff;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(15, 52, 96, 0.25);
}
.hero h1 { color: #fff !important; font-size: 1.85rem !important; margin: 0 0 0.5rem 0 !important; }
.hero p { color: #c5d4f0; margin: 0; font-size: 1.05rem; }

.feature-card {
    background: linear-gradient(180deg, #ffffff 0%, #f6f8fc 100%);
    border: 1px solid #e4e8f0;
    border-radius: 14px;
    padding: 1.25rem 1.35rem;
    min-height: 155px;
    box-sizing: border-box;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
    overflow: hidden;
    word-wrap: break-word;
    overflow-wrap: anywhere;
}
.feature-card h3 {
    margin: 0 0 0.55rem 0;
    font-size: 1.05rem;
    color: #1a1a2e;
    font-weight: 700;
    word-wrap: break-word;
}
.feature-card p {
    margin: 0;
    color: #5a6478;
    font-size: 0.9rem;
    line-height: 1.45;
    word-wrap: break-word;
    overflow-wrap: anywhere;
}

.step-card {
    background: #f8f9fc;
    border: 1px solid #e4e8f0;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    min-height: 100px;
    height: 100%;
}
.step-card .step-num {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0f3460;
    margin-bottom: 0.35rem;
}
.step-card .step-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1a1a2e;
    margin-bottom: 0.25rem;
}
.step-card .step-desc {
    font-size: 0.85rem;
    color: #5a6478;
    margin: 0;
}

.ats-score-box {
    background: #f0f4fa;
    border: 1px solid #d8dee9;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin: 0.5rem 0 1rem 0;
}
.ats-score-box .ats-label {
    font-size: 0.9rem;
    color: #4b5563;
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.ats-score-box .ats-value {
    font-size: 2rem;
    font-weight: 700;
    color: #1a1a2e;
    line-height: 1.2;
}
.ats-score-box .ats-hint {
    font-size: 0.82rem;
    color: #6b7280;
    margin-top: 0.35rem;
}
.ats-score-box.ats-low .ats-value { color: #1d4ed8; }
.ats-score-box.ats-mid .ats-value { color: #b45309; }
.ats-score-box.ats-high .ats-value { color: #047857; }

.hh-salary { color: #d6001c; font-weight: 600; }
.feature-card { border-left: 4px solid #2563eb; }
.step-card { border-left: 3px solid #2563eb; }

div[data-testid="stMetric"],
div[data-testid="stMetric"] * {
    color: #1a1a2e !important;
}
div[data-testid="stMetric"] {
    background: #f8f9fc !important;
    border: 1px solid #e8ecf4;
    border-radius: 12px;
    padding: 0.75rem 1rem;
}

.page-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 0.25rem;
}
.page-sub {
    color: #6b7280;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

.vac-card-hh {
    border-left: 4px solid #d6001c;
}

div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #fafbfe 0%, #f0f3f9 100%);
}

div[data-testid="stMetric"] {
    background: #f8f9fc;
    border: 1px solid #e8ecf4;
    border-radius: 12px;
    padding: 0.75rem 1rem;
}

.tag-pill {
    display: inline-block;
    background: #eef2ff;
    color: #3730a3;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-size: 0.82rem;
    margin: 0.15rem 0.2rem 0.15rem 0;
}
</style>
"""


def configure_page(title: str = "AI Карьерный советник"):
    st.set_page_config(
        page_title=title,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


@st.cache_resource(ttl=300)
def _get_app_token():
    cid = os.getenv("HH_CLIENT_ID", "").strip()
    secret = os.getenv("HH_CLIENT_SECRET", "").strip()
    if cid and secret:
        from utils.oauth import get_app_access_token

        return get_app_access_token()
    return api_client.get_app_hh_token()


def ensure_base_public():
    inject_css()


def ensure_base():
    inject_css()
    require_auth()
    init_db()


def ensure_app_ready():
    ensure_base()
    provider = os.getenv("LLM_PROVIDER", "local").lower()

    eager = os.getenv("LLM_EAGER_LOAD", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if provider == "local" and eager:
        ensure_local_model_loaded()
    elif provider == "api":
        st.session_state.model_loaded = True

    if "app_access_token" not in st.session_state:
        try:
            st.session_state.app_access_token = _get_app_token()
        except Exception as e:
            st.error(f"Не удалось получить токен HH приложения: {e}")
            st.stop()


def process_oauth_callback():
    qp = st.query_params
    if "code" not in qp or "state" not in qp:
        return

    restore_auth_token()
    state = qp.get("state", "")
    if isinstance(state, list):
        state = state[0] if state else ""
    saved_jwt = peek_app_jwt_from_state(state)
    if saved_jwt and not get_auth_token():
        persist_auth_token(saved_jwt)

    if not get_auth_token():
        st.error(
            "Сначала войдите по email, затем снова нажмите «Подключить HH»."
        )
        return
    try:
        code = qp["code"]
        if isinstance(code, list):
            code = code[0]
        token_data = exchange_code_for_token(code, state)
        expires = time.time() + token_data["expires_in"]
        api_client.save_hh_token(
            get_auth_token(),
            token_data["access_token"],
            token_data["refresh_token"],
            expires,
        )
        st.session_state.access_token = token_data["access_token"]
        st.session_state.refresh_token = token_data["refresh_token"]
        st.session_state.expires_at = expires
        if "auth_user" not in st.session_state:
            from utils.auth_ui import _load_user

            _load_user()
        st.query_params.clear()
        st.success("HeadHunter подключён")
        st.rerun()
    except Exception as e:
        st.error(f"Ошибка авторизации HH: {e}")


def _sync_hh_tokens_from_api():
    token = get_auth_token()
    if not token:
        return
    try:
        data = api_client.get_hh_tokens(token)
        st.session_state.access_token = data["access_token"]
        st.session_state.refresh_token = data["refresh_token"]
        st.session_state.expires_at = data["expires_at"]
    except api_client.ApiError:
        for key in ("access_token", "refresh_token", "expires_at"):
            st.session_state.pop(key, None)


def is_hh_logged_in() -> bool:
    process_oauth_callback()
    if not is_logged_in():
        return False
    if "access_token" not in st.session_state:
        _sync_hh_tokens_from_api()
    logged = "access_token" in st.session_state
    if logged and time.time() > st.session_state.get("expires_at", 0):
        try:
            new_tokens = refresh_access_token(st.session_state.refresh_token)
            expires = time.time() + new_tokens["expires_in"]
            st.session_state.access_token = new_tokens["access_token"]
            st.session_state.refresh_token = new_tokens["refresh_token"]
            st.session_state.expires_at = expires
            if get_auth_token():
                api_client.save_hh_token(
                    get_auth_token(),
                    new_tokens["access_token"],
                    new_tokens["refresh_token"],
                    expires,
                )
        except Exception:
            for key in ("access_token", "refresh_token", "expires_at"):
                st.session_state.pop(key, None)
            logged = False
    return logged


def _sync_active_resume_text():
    from utils.db import get_saved_resume, list_saved_resumes_optional

    saved = list_saved_resumes_optional()
    if not saved:
        return st.session_state.get("resume_text", "")

    if st.session_state.get("active_resume_id") not in {
        r["id"] for r in saved
    }:
        st.session_state.active_resume_id = saved[0]["id"]

    if st.session_state.get("active_resume_id"):
        rec = get_saved_resume(st.session_state.active_resume_id)
        if rec:
            st.session_state.resume_text = rec["body"]
            return rec["body"]
    return st.session_state.get("resume_text", "")


def render_sidebar_compact():
    st.sidebar.markdown("### Карьерный агент")
    user = st.session_state.get("auth_user", {})
    if user:
        st.sidebar.caption(f"Аккаунт: {user.get('email', '')}")
    st.sidebar.page_link("pages/0_Вход.py", label="Вход / выход")

    logged = is_hh_logged_in()
    st.sidebar.markdown("**HeadHunter (API)**")
    if logged:
        st.sidebar.success("HH подключён")
    elif is_logged_in():
        url, _, _ = get_auth_url(app_jwt=get_auth_token())
        st.sidebar.link_button("Подключить HH", url, use_container_width=True)
    else:
        st.sidebar.caption("Сначала войдите по email")

    st.sidebar.markdown("---")
    _render_active_resume_block()
    _render_adaptation_checkbox()


def render_sidebar() -> str:
    render_sidebar_compact()
    return _sync_active_resume_text()


def _render_active_resume_block():
    st.sidebar.markdown("**Активное резюме**")
    if not is_logged_in():
        st.sidebar.caption("Войдите, чтобы выбрать и сохранять резюме.")
        st.sidebar.page_link(
            "pages/0_Вход.py",
            label="Войти",
            icon=None,
        )
        return
    from utils.db import list_saved_resumes_optional

    saved = list_saved_resumes_optional()
    id_to_name = {r["id"]: r["name"] for r in saved}

    if saved:
        keys = list(id_to_name.keys())
        idx = (
            keys.index(st.session_state.active_resume_id)
            if st.session_state.get("active_resume_id") in id_to_name
            else 0
        )
        picked = st.sidebar.selectbox(
            "Профиль",
            options=keys,
            index=idx,
            format_func=lambda i: id_to_name[i],
            label_visibility="collapsed",
            key="resume_select",
        )
        st.session_state.active_resume_id = picked
        if picked != st.session_state.get("_resume_sync_id"):
            st.session_state._resume_sync_id = picked
            rec = get_saved_resume(picked)
            if rec:
                st.session_state.resume_text = rec["body"]

        rec = get_saved_resume(st.session_state.active_resume_id)
        if rec:
            preview = rec["body"][:150].replace("\n", " ")
            if len(rec["body"]) > 150:
                preview += "…"
            st.sidebar.caption(preview or "(пусто)")
    else:
        st.sidebar.caption("Нет сохранённых резюме")

    st.sidebar.page_link(
        "pages/5_Мои_резюме.py",
        label="Мои резюме — редактировать",
        icon=None,
    )


def _render_adaptation_checkbox():
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Адаптация**")
    st.session_state.allow_invented_skills = st.sidebar.checkbox(
        "Добавлять правдоподобные навыки из вакансии",
        value=st.session_state.get("allow_invented_skills", False),
    )
    st.sidebar.caption(
        "При включении в резюме могут добавляться навыки из вакансии, чтобы улучшить соответствие."
    )
    st.sidebar.caption(f"Модель: {provider_label()}")


def page_header(title: str, subtitle: str = ""):
    st.markdown(f'<p class="page-title">{title}</p>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(
            f'<p class="page-sub">{subtitle}</p>', unsafe_allow_html=True
        )


def hero_block(title: str, subtitle: str):
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def feature_card(col, title: str, text: str):
    with col:
        st.markdown(
            f'<div class="feature-card"><h3>{title}</h3><p>{text}</p></div>',
            unsafe_allow_html=True,
        )


def step_card(col, num: str, title: str, desc: str):
    with col:
        st.markdown(
            f'<div class="step-card">'
            f'<div class="step-num">{num}</div>'
            f'<div class="step-title">{title}</div>'
            f'<p class="step-desc">{desc}</p></div>',
            unsafe_allow_html=True,
        )


def render_ats_score_html(score: int, label: str, hint: str = ""):
    level = (
        "ats-high"
        if score >= 70
        else ("ats-mid" if score >= 40 else "ats-low")
    )
    hint_html = f'<p class="ats-hint">{hint}</p>' if hint else ""
    st.markdown(
        f'<div class="ats-score-box {level}">'
        f'<div class="ats-label">{label}</div>'
        f'<div class="ats-value">{score}%</div>'
        f"{hint_html}</div>",
        unsafe_allow_html=True,
    )
