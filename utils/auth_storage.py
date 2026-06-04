from pathlib import Path

import streamlit as st

_AUTH_FILE = Path.home() / ".career_agent_auth"


def persist_auth_token(token: str):
    _AUTH_FILE.write_text(token, encoding="utf-8")
    st.session_state.auth_token = token


def clear_persisted_auth():
    if _AUTH_FILE.exists():
        _AUTH_FILE.unlink()
    for key in ("auth_token", "auth_user"):
        st.session_state.pop(key, None)


def restore_auth_token() -> bool:
    if st.session_state.get("auth_token"):
        return True
    if not _AUTH_FILE.exists():
        return False
    try:
        token = _AUTH_FILE.read_text(encoding="utf-8").strip()
        if token:
            st.session_state.auth_token = token
            return True
    except OSError:
        pass
    return False
