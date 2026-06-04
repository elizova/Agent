import streamlit as st

from utils import api_client
from utils.auth_storage import (
    clear_persisted_auth,
    persist_auth_token,
    restore_auth_token,
)


def is_logged_in() -> bool:
    restore_auth_token()
    return bool(st.session_state.get("auth_token"))


def get_auth_token() -> str | None:
    return st.session_state.get("auth_token")


def logout():
    clear_persisted_auth()
    for key in (
        "access_token",
        "refresh_token",
        "expires_at",
        "app_access_token",
    ):
        st.session_state.pop(key, None)
    st.rerun()


def _load_user():
    token = st.session_state.get("auth_token")
    if token:
        try:
            st.session_state.auth_user = api_client.me(token)
        except api_client.ApiError:
            clear_persisted_auth()


def render_auth_page():
    st.subheader("Вход в аккаунт")
    st.caption(
        "Email и пароль — для ваших резюме и истории. "
        "HeadHunter подключается отдельно в боковой панели после входа."
    )

    tab_login, tab_reg = st.tabs(["Вход", "Регистрация"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Пароль", type="password")
            if st.form_submit_button(
                "Войти", type="primary", use_container_width=True
            ):
                try:
                    token = api_client.login(email, password)
                    persist_auth_token(token)
                    _load_user()
                    st.success("Вы вошли")
                    st.rerun()
                except api_client.ApiError as e:
                    st.error(str(e))

    with tab_reg:
        with st.form("reg_form"):
            email = st.text_input("Email", key="reg_email")
            name = st.text_input("Имя (необязательно)")
            password = st.text_input("Пароль", type="password", key="reg_pass")
            password2 = st.text_input("Повторите пароль", type="password")
            if st.form_submit_button(
                "Зарегистрироваться", type="primary", use_container_width=True
            ):
                if password != password2:
                    st.error("Пароли не совпадают")
                elif len(password) < 6:
                    st.error("Пароль не короче 6 символов")
                else:
                    try:
                        token = api_client.register(
                            email, password, name or None
                        )
                        persist_auth_token(token)
                        _load_user()
                        st.success("Аккаунт создан")
                        st.rerun()
                    except api_client.ApiError as e:
                        st.error(str(e))


def require_auth() -> bool:
    if is_logged_in():
        if "auth_user" not in st.session_state:
            _load_user()
        return True
    st.warning("Войдите в аккаунт: раздел **Вход** в меню слева.")
    st.page_link("pages/0_Вход.py", label="Перейти ко входу")
    st.stop()
    return False
