import streamlit as st

_CACHE_KEY = "resume_history_cache"


def cache_adapted_resume(analysis_id: int | str, text: str) -> None:
    if not text or not str(text).strip():
        return
    cache = st.session_state.setdefault(_CACHE_KEY, {})
    cache[str(analysis_id)] = text.strip()


def get_cached_adapted_resume(analysis_id: int | str) -> str:
    cache = st.session_state.get(_CACHE_KEY, {})
    return (cache.get(str(analysis_id)) or "").strip()
