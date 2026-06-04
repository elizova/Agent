import json

import streamlit as st

from utils.db import (
    get_analysis_detail,
    get_analysis_history,
    get_search_history,
)
from utils.history_local import get_cached_adapted_resume
from utils.streamlit_app import ensure_base, page_header, render_sidebar

ensure_base()
render_sidebar()

page_header("История", "Повтор поисков и сохранённые адаптации резюме")

tab_s, tab_a = st.tabs(["Поиски", "Анализы и резюме"])

with tab_s:
    searches = get_search_history(20)
    if not searches:
        st.info("История поисков пуста.")
    else:
        for row in searches:
            q = row["user_query"] or "—"
            label = q if len(q) <= 55 else q[:55] + "…"
            with st.expander(f"{row['created_at'][:16]} · {label}"):
                st.write(
                    f"Найдено на HH: **{row['found_count']}** · "
                    f"в подборке: **{row['results_count']}**"
                )
                if row.get("params_json"):
                    try:
                        params = json.loads(row["params_json"])
                        st.code(
                            json.dumps(params, ensure_ascii=False, indent=2),
                            language="json",
                        )
                    except Exception:
                        st.text(row["params_json"])
                if st.button(
                    "Повторить этот поиск",
                    key=f"repeat_{row['id']}",
                    type="primary",
                ):
                    st.session_state.rerun_search = {
                        "user_query": row["user_query"],
                        "params": json.loads(row["params_json"] or "{}"),
                    }
                    st.switch_page("pages/1_Поиск_HH.py")

with tab_a:
    analyses = get_analysis_history(20)
    if not analyses:
        st.info("Анализы появятся после генерации резюме.")
    else:
        for row in analyses:
            title = row["vacancy_title"] or row["vacancy_id"]
            after = row["ats_after"]
            before = row["ats_before"]
            delta = (
                f"{before}% -> {after}%" if after is not None else f"{before}%"
            )
            with st.expander(
                f"{row['created_at'][:16]} · {title} · ATS {delta}"
            ):
                st.caption(f"Источник: {row['source']}")
                url = row.get("vacancy_url") or ""
                if url:
                    st.link_button("Открыть вакансию", url)
                elif row["vacancy_id"] and row["vacancy_id"] != "manual":
                    hh_url = f"https://hh.ru/vacancy/{row['vacancy_id']}"
                    st.link_button("Открыть на hh.ru", hh_url)
                adapted = get_cached_adapted_resume(row["id"])
                if not adapted:
                    adapted = (row.get("resume_adapted") or "").strip()
                if not adapted:
                    detail = get_analysis_detail(row["id"])
                    if detail:
                        adapted = (detail.get("resume_adapted") or "").strip()
                if adapted:
                    st.text_area(
                        "Адаптированное резюме",
                        value=adapted,
                        height=220,
                        key=f"hist_{row['id']}",
                    )
                    st.download_button(
                        "Скачать .txt",
                        data=adapted,
                        file_name=f"resume_{row['id']}.txt",
                        mime="text/plain; charset=utf-8",
                        key=f"dl_hist_{row['id']}",
                    )
                else:
                    st.caption(
                        "Текст резюме в этой записи не сохранён. "
                        "Сгенерируйте резюме заново на странице анализа."
                    )
