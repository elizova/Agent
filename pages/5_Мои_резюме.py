import streamlit as st

from utils.db import (
    delete_resume_record,
    get_saved_resume,
    list_saved_resumes,
    save_resume_record,
)
from utils.streamlit_app import (
    ensure_base,
    page_header,
    render_sidebar_compact,
)

ensure_base()
render_sidebar_compact()

page_header(
    "Мои резюме",
    "Редактирование и создание профилей. Какое резюме использовать — выберите в панели слева.",
)

saved = list_saved_resumes()
is_new = st.session_state.get("editing_resume_id") is None

if "editing_resume_id" not in st.session_state and saved:
    st.session_state.editing_resume_id = st.session_state.get(
        "active_resume_id"
    )

col_list, col_edit = st.columns([1, 2])

with col_list:
    st.subheader("Список")
    if not saved:
        st.caption("Пока нет сохранённых резюме.")
    else:
        for r in saved:
            is_active = r["id"] == st.session_state.get("active_resume_id")
            label = r["name"] + (" · активное" if is_active else "")
            if st.button(
                label,
                key=f"open_{r['id']}",
                use_container_width=True,
            ):
                st.session_state.editing_resume_id = r["id"]
                rec = get_saved_resume(r["id"])
                if rec:
                    st.session_state.resume_draft_name = rec["name"]
                    st.session_state.resume_draft_body = rec["body"]
                st.rerun()

    if st.button(
        "+ Создать новое резюме", use_container_width=True, type="primary"
    ):
        st.session_state.editing_resume_id = None
        st.session_state.resume_draft_name = f"Резюме {len(saved) + 1}"
        st.session_state.resume_draft_body = ""
        st.rerun()

with col_edit:
    st.subheader("Новое резюме" if is_new else "Редактор")

    if is_new:
        default_name = st.session_state.get(
            "resume_draft_name", "Новое резюме"
        )
        default_body = st.session_state.get("resume_draft_body", "")
    else:
        rec = get_saved_resume(st.session_state.editing_resume_id)
        default_name = rec["name"] if rec else "Резюме"
        default_body = rec["body"] if rec else ""

    name = st.text_input("Название", value=default_name)
    body = st.text_area(
        "Текст резюме",
        value=default_body or st.session_state.get("resume_text", ""),
        height=360,
    )

    if is_new:
        if st.button(
            "Создать резюме", type="primary", use_container_width=True
        ):
            rid = save_resume_record(name, body, resume_id=None)
            st.session_state.active_resume_id = rid
            st.session_state.editing_resume_id = rid
            st.session_state.resume_text = body
            st.session_state._resume_sync_id = rid
            st.rerun()
    else:
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(
                "Сохранить изменения", type="primary", use_container_width=True
            ):
                rid = save_resume_record(
                    name, body, resume_id=st.session_state.editing_resume_id
                )
                st.session_state.active_resume_id = rid
                st.session_state.resume_text = body
                st.session_state._resume_sync_id = rid
                st.rerun()
        with b2:
            if st.button("Сохранить как новое", use_container_width=True):
                rid = save_resume_record(name, body, resume_id=None)
                st.session_state.active_resume_id = rid
                st.session_state.editing_resume_id = rid
                st.session_state.resume_text = body
                st.session_state._resume_sync_id = rid
                st.rerun()
        with b3:
            if st.button("Удалить", use_container_width=True):
                delete_resume_record(st.session_state.editing_resume_id)
                rest = [
                    x
                    for x in saved
                    if x["id"] != st.session_state.editing_resume_id
                ]
                if rest:
                    st.session_state.active_resume_id = rest[0]["id"]
                    st.session_state.editing_resume_id = rest[0]["id"]
                    st.session_state.resume_text = get_saved_resume(
                        rest[0]["id"]
                    )["body"]
                    st.session_state._resume_sync_id = rest[0]["id"]
                else:
                    st.session_state.pop("active_resume_id", None)
                    st.session_state.editing_resume_id = None
                    st.session_state.resume_text = ""
                st.rerun()
