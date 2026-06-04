import streamlit as st

from utils.streamlit_app import ensure_app_ready, page_header, render_sidebar
from utils.ui_components import render_vacancy_analysis

ensure_app_ready()
resume_text = render_sidebar()

page_header(
    "Вакансия из текста",
    "Вставьте описание с любого сайта — без поиска на hh.ru",
)

manual_title = st.text_input(
    "Название позиции",
    placeholder="Например, Менеджер по продажам",
)

manual_text = st.text_area(
    "Текст вакансии",
    height=240,
    placeholder="Обязанности, требования, условия работы…",
)

analyze_btn = st.button("Анализировать", type="primary")

if analyze_btn:
    if not manual_text or len(manual_text.strip()) < 80:
        st.warning("Нужно не менее 80 символов описания.")
    else:
        st.session_state.manual_active = True
        st.session_state.manual_title = manual_title or "Вакансия (вручную)"
        st.session_state.manual_text = manual_text
        for k in list(st.session_state.keys()):
            if k.startswith(
                (
                    "reqs_manual_",
                    "cmp_manual_",
                    "gen_manual_",
                    "ats_after_manual_",
                )
            ):
                st.session_state.pop(k, None)

if st.session_state.get("manual_active"):
    st.markdown("---")
    render_vacancy_analysis(
        vacancy_id="manual",
        vacancy_title=st.session_state.get("manual_title", "Вакансия"),
        full_description=st.session_state.manual_text,
        hh_skills=None,
        resume_text=resume_text,
        source="manual",
        cache_prefix="manual",
        vacancy_url="",
    )
