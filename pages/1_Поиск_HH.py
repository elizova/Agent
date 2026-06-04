import streamlit as st

from utils.agent import parse_user_query_to_api_params
from utils.text_utils import strip_html
from utils.db import save_search
from utils.hh_api import format_salary, search_vacancies
from utils.search_rank import sort_vacancies
from utils.streamlit_app import (
    ensure_app_ready,
    is_hh_logged_in,
    page_header,
    render_sidebar,
)

PER_PAGE = 20

ensure_app_ready()
resume_text = render_sidebar()

page_header(
    "Поиск на HeadHunter",
    "Сначала подходящие (зарплата, совпадение с запросом) · ИИ-анализ на отдельной странице",
)

if not is_hh_logged_in():
    st.warning("Войдите через HeadHunter в боковой панели.")
    st.stop()


def _run_search(user_query: str, params: dict, page: int = 0):
    params = dict(params)
    results = search_vacancies(
        params,
        access_token=st.session_state.app_access_token,
        page=page,
        per_page=PER_PAGE,
    )
    if not results or not results.get("items"):
        results = search_vacancies(
            {"text": user_query},
            access_token=st.session_state.app_access_token,
            page=page,
            per_page=PER_PAGE,
        )
    return results


def _apply_results(results, user_query: str, params: dict):
    if results and results.get("items"):
        items = sort_vacancies(results["items"], user_query, params)
        st.session_state.search_items = items
        st.session_state.found_count = results.get("found", 0)
        st.session_state.search_pages = results.get("pages", 1)
        save_search(
            user_query,
            params,
            st.session_state.found_count,
            len(items),
            resume_text,
        )
    else:
        st.session_state.search_items = []
        st.warning("Ничего не найдено.")


if st.session_state.get("rerun_search"):
    rs = st.session_state.rerun_search
    q = rs["user_query"]
    st.session_state.last_query = q
    st.session_state.search_page = 0
    with st.spinner("Понимаю запрос…"):
        params = rs.get("params") or {}
        if not params or not params.get("text"):
            params = parse_user_query_to_api_params(q, resume_hint=resume_text)
        st.session_state.last_params = params
    with st.spinner("Повторяю поиск…"):
        _apply_results(
            _run_search(q, st.session_state.last_params, 0),
            q,
            st.session_state.last_params,
        )
    st.session_state.pop("rerun_search", None)
    st.info(f"Повторён поиск: «{q[:80]}»")

col_q, col_btn = st.columns([5, 1])
with col_q:
    user_query = st.text_area(
        "Что ищете?",
        value=st.session_state.get("last_query", ""),
        placeholder="Например: спокойная работа с хорошей зарплатой в Подмосковье",
        height=88,
        label_visibility="collapsed",
    )
with col_btn:
    st.write("")
    search_button = st.button(
        "Найти", type="primary", use_container_width=True
    )

if search_button and user_query:
    for key in list(st.session_state.keys()):
        if key.startswith(("reqs_", "cmp_", "gen_", "ats_after_", "analyze_")):
            st.session_state.pop(key, None)
    st.session_state.search_page = 0

    with st.spinner("Понимаю запрос…"):
        params = parse_user_query_to_api_params(
            user_query, resume_hint=resume_text
        )
    st.session_state.last_params = params
    st.session_state.last_query = user_query

    with st.spinner("Ищу на hh.ru…"):
        _apply_results(_run_search(user_query, params, 0), user_query, params)
    if st.session_state.get("search_items"):
        st.toast(
            f"На странице: {len(st.session_state.search_items)} (отсортировано)"
        )

if st.session_state.get("last_params") and st.session_state.get("last_query"):
    cur_page = st.session_state.get("search_page", 0)
    total_pages = st.session_state.get("search_pages", 1)
    found = st.session_state.get("found_count", 0)

    st.caption(
        f"Всего на HH: {found} · стр. {cur_page + 1}/{total_pages} · "
        f"сначала с зарплатой и лучшим совпадением"
    )

    pc1, _, pc3 = st.columns([1, 2, 1])
    with pc1:
        if cur_page > 0 and st.button("Назад", use_container_width=True):
            st.session_state.search_page = cur_page - 1
            with st.spinner("Загружаю…"):
                res = _run_search(
                    st.session_state.last_query,
                    st.session_state.last_params,
                    st.session_state.search_page,
                )
                if res and res.get("items"):
                    st.session_state.search_items = sort_vacancies(
                        res["items"],
                        st.session_state.last_query,
                        st.session_state.last_params,
                    )
            st.rerun()
    with pc3:
        if cur_page < total_pages - 1 and st.button(
            "Далее", use_container_width=True
        ):
            st.session_state.search_page = cur_page + 1
            with st.spinner("Загружаю…"):
                res = _run_search(
                    st.session_state.last_query,
                    st.session_state.last_params,
                    st.session_state.search_page,
                )
                if res and res.get("items"):
                    st.session_state.search_items = sort_vacancies(
                        res["items"],
                        st.session_state.last_query,
                        st.session_state.last_params,
                    )
            st.rerun()

    with st.expander("Параметры API"):
        st.json(st.session_state.last_params)

items = st.session_state.get("search_items", [])
for vac in items:
    salary = format_salary(vac)
    snippet = vac.get("snippet") or {}
    preview = ""
    if isinstance(snippet, dict):
        parts = [
            snippet.get("requirement", ""),
            snippet.get("responsibility", ""),
        ]
        preview = strip_html(" ".join(p for p in parts if p).strip())
    if preview:
        preview = preview[:280] + ("…" if len(preview) > 280 else "")

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"### {vac['name']}")
            st.caption(vac["employer"]["name"])
            if salary:
                st.markdown(
                    f'<span class="hh-salary">Зарплата: {salary}</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Зарплата не указана")
            if preview:
                st.write(preview)
        with c2:
            st.link_button(
                "Открыть на HH",
                vac["alternate_url"],
                use_container_width=True,
            )
            if st.button(
                "К анализу",
                key=f"go_{vac['id']}",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.analyze_vacancy_id = vac["id"]
                st.session_state.analyze_vacancy_details = None
                st.session_state.analyze_vacancy_title = vac["name"]
                st.session_state.analyze_vacancy_url = vac.get(
                    "alternate_url", ""
                )
                st.switch_page("pages/2_Анализ.py")
