import streamlit as st

from utils.auth_ui import is_logged_in, logout, render_auth_page
from utils.streamlit_app import configure_page, ensure_base_public, page_header

configure_page()
ensure_base_public()

page_header("Вход", "Регистрация и вход по email")

if is_logged_in():
    user = st.session_state.get("auth_user", {})
    st.success(f"Вы вошли как **{user.get('email', '')}**")
    st.caption(
        "Вход сохраняется на этом компьютере после перезапуска приложения. "
        "Чтобы выйти полностью — нажмите «Выйти»."
    )
    if st.button("Выйти"):
        logout()
else:
    render_auth_page()
