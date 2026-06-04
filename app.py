import streamlit as st

from utils.auth_ui import is_logged_in
from utils.db import get_analysis_history_optional, get_search_history_optional
from utils.streamlit_app import (
    configure_page,
    ensure_base_public,
    feature_card,
    hero_block,
    is_hh_logged_in,
    render_sidebar_compact,
    step_card,
)

st.set_page_config(
    page_title="Главная", layout="wide", initial_sidebar_state="expanded"
)

configure_page("Главная")
ensure_base_public()
render_sidebar_compact()

hero_block(
    "AI-агент для поиска работы",
    "Анализируем требования, оцениваем совместимость и улучшаем ваше резюме автоматически",
)

st.info(
    "Разделы в **меню слева**: поиск, анализ, вакансия из текста, "
    "мои резюме, карьерный чат, история. Для работы с данными войдите в аккаунт."
)

c1, c2, c3 = st.columns(3)
feature_card(
    c1,
    "Поиск на HH",
    "Запрос на естественном языке, ранжирование вакансий и переход к анализу.",
)
feature_card(
    c2,
    "Вакансия из текста",
    "Вставьте описание без API: те же ключевые слова и адаптация резюме.",
)
feature_card(
    c3,
    "История",
    "Сохранённые поиски и версии адаптированных резюме (после входа).",
)

st.markdown("---")
st.subheader("Как работает агент")

steps = st.columns(4)
step_card(steps[0], "1", "Парсинг запроса", "Интеллектуальный поиск вакансий")
step_card(steps[1], "2", "Ключевые слова", "Анализируем описание вакансии")
step_card(steps[2], "3", "Оценка ATS", "Процент совпадения с резюме")
step_card(steps[3], "4", "Резюме", "Адаптация под вакансию")

st.markdown("---")
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Последние поиски**")
    if not is_logged_in():
        st.caption("Войдите в аккаунт, чтобы видеть историю поисков.")
    else:
        searches = get_search_history_optional(5)
        if searches:
            for row in searches:
                q = (row["user_query"] or "")[:50]
                st.caption(f"{row['created_at'][:16]} · {q}")
        else:
            st.caption("Пока нет — начните с раздела «Поиск HH»")

with col_b:
    st.markdown("**Последние анализы**")
    if not is_logged_in():
        st.caption(
            "Войдите в аккаунт, чтобы видеть сохранённые адаптации резюме."
        )
    else:
        analyses = get_analysis_history_optional(5)
        if analyses:
            for row in analyses:
                ats = row["ats_after"] or row["ats_before"]
                st.caption(
                    f"{row['created_at'][:16]} · {row['vacancy_title']} · ATS {ats}%"
                )
        else:
            st.caption("Появятся после генерации резюме")

if not is_logged_in():
    st.page_link("pages/0_Вход.py", label="Войти или зарегистрироваться")
elif not is_hh_logged_in():
    st.warning(
        "Для поиска на hh.ru: подключите **HeadHunter** в боковой панели."
    )
