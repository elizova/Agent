import streamlit as st

from utils.hh_api import get_vacancy_details
from utils.streamlit_app import ensure_app_ready, page_header, render_sidebar
from utils.text_utils import strip_html
from utils.ui_components import render_vacancy_analysis

ensure_app_ready()
resume_text = render_sidebar()

vac_id = st.session_state.get("analyze_vacancy_id")
title = st.session_state.get("analyze_vacancy_title", "Вакансия")

if not vac_id:
    page_header("Анализ вакансии", "")
    st.info(
        "Сначала выберите вакансию на странице «Поиск HH» и нажмите «К анализу»."
    )
    if st.button("Перейти к поиску", type="primary"):
        st.switch_page("pages/1_Поиск_HH.py")
    st.stop()

page_header(title, f"Вакансия ID: {vac_id}")

if st.button("К списку вакансий"):
    for k in list(st.session_state.keys()):
        if k.startswith(
            ("reqs_hh_", "cmp_hh_", "gen_", "ats_after_hh_")
        ) or k.startswith("analyze_"):
            st.session_state.pop(k, None)
    st.switch_page("pages/1_Поиск_HH.py")

details = st.session_state.get("analyze_vacancy_details")
if not details:
    with st.spinner("Загружаю описание с hh.ru…"):
        details = get_vacancy_details(
            vac_id, access_token=st.session_state.app_access_token
        )
        st.session_state.analyze_vacancy_details = details

if not details:
    st.error("Не удалось загрузить вакансию. Повторите позже.")
    st.stop()

desc_html = details.get("description", "")
hh_skills = [s["name"] for s in details.get("key_skills", [])]
plain = strip_html(desc_html)

if plain:
    with st.expander("Текст вакансии", expanded=False):
        st.write(plain[:2000] + ("…" if len(plain) > 2000 else ""))

st.markdown("---")
vac_url = st.session_state.get("analyze_vacancy_url") or details.get(
    "alternate_url", ""
)

render_vacancy_analysis(
    vacancy_id=vac_id,
    vacancy_title=title,
    full_description=desc_html or " ".join(hh_skills),
    hh_skills=hh_skills,
    resume_text=resume_text,
    source="hh",
    cache_prefix="hh",
    vacancy_url=vac_url,
)
