import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)


def resume_adapter_enabled() -> bool:
    path = os.getenv("RESUME_ADAPTER_PATH", "")
    if not path or not Path(path).exists():
        return False
    if os.getenv("LLM_USE_RESUME_ADAPTER", "1").strip().lower() in (
        "0",
        "false",
        "no",
    ):
        return False
    return True


def _env(key, default=""):
    return os.getenv(key, default)


_PROVIDER = _env("LLM_PROVIDER", "local").lower()
_API_BASE = _env("LLM_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
_API_KEY = _env("LLM_API_KEY", "")
_API_MODEL = _env("LLM_API_MODEL", "google/gemma-2-9b-it")
_LOCAL_MODEL = _env(
    "LLM_LOCAL_MODEL", "mlx-community/Qwen2.5-3B-Instruct-4bit"
)
_RESUME_ADAPTER = _env("RESUME_ADAPTER_PATH", "")

_local_loaded = False
_adapter_loaded = False
_adapter_model = None
_adapter_tokenizer = None


def provider_label() -> str:
    if _RESUME_ADAPTER and Path(_RESUME_ADAPTER).exists():
        return f"local+adapter ({Path(_RESUME_ADAPTER).name})"
    if _PROVIDER == "api":
        return f"api ({_API_MODEL})"
    return f"local ({_LOCAL_MODEL})"


def init_models():
    global _local_loaded
    if _PROVIDER != "local":
        _local_loaded = True
        return
    from utils.llm_utils import init_model, model_loaded

    if not model_loaded:
        init_model(_LOCAL_MODEL)
    _local_loaded = True


def ensure_local_model_loaded():
    if _PROVIDER != "local":
        return
    from utils.llm_utils import model_loaded

    if model_loaded:
        return

    try:
        import streamlit as st

        if st.session_state.get("_mlx_loaded"):
            return
        if st.session_state.get("_mlx_loading"):
            st.stop()

        st.session_state._mlx_loading = True
        try:
            with st.spinner(f"Загружаю модель ({provider_label()})…"):
                init_models()
            st.session_state._mlx_loaded = True
        finally:
            st.session_state.pop("_mlx_loading", None)
        return
    except Exception:
        pass

    init_models()


def _load_resume_adapter():
    global _adapter_loaded, _adapter_model, _adapter_tokenizer
    if _adapter_loaded or not _RESUME_ADAPTER:
        return
    path = Path(_RESUME_ADAPTER)
    if not path.exists():
        return
    try:
        from utils.mlx_env import configure_mlx_env

        configure_mlx_env()
        from mlx_lm import load

        _adapter_model, _adapter_tokenizer = load(
            _LOCAL_MODEL,
            adapter_path=str(path),
        )
        _adapter_loaded = True
    except Exception as e:
        print(f"Не удалось загрузить адаптер резюме: {e}")


def _generate_api(prompt: str, max_tokens: int, temperature: float) -> str:
    import httpx

    if not _API_KEY:
        raise RuntimeError(
            "Задайте LLM_API_KEY в .env для режима LLM_PROVIDER=api"
        )
    resp = httpx.post(
        f"{_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": _API_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _generate_local(
    prompt: str, max_tokens: int, temperature: float, use_adapter: bool
) -> str:
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    from utils.llm_utils import model_loaded

    ensure_local_model_loaded()

    if use_adapter:
        _load_resume_adapter()
        if _adapter_loaded:
            model, tokenizer = _adapter_model, _adapter_tokenizer
        else:
            from utils import llm_utils

            model, tokenizer = llm_utils.model, llm_utils.tokenizer
    else:
        from utils import llm_utils

        model, tokenizer = llm_utils.model, llm_utils.tokenizer

    if hasattr(tokenizer, "apply_chat_template"):
        messages = [{"role": "user", "content": prompt}]
        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        input_text = prompt

    sampler = make_sampler(temp=temperature)
    return generate(
        model,
        tokenizer,
        prompt=input_text,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False,
    ).strip()


def generate_response(
    prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.5,
    task: str = "general",
    use_adapter: bool | None = None,
) -> str:
    if task != "adapt_resume":
        use_adapter = False
    elif use_adapter is None:
        use_adapter = (
            os.getenv("LLM_USE_RESUME_ADAPTER", "1").strip().lower()
            not in ("0", "false", "no")
            and bool(_RESUME_ADAPTER)
            and Path(_RESUME_ADAPTER).exists()
        )

    if task == "adapt_resume" and use_adapter:
        temperature = min(temperature, 0.28)

    if _PROVIDER == "api":
        return _generate_api(prompt, max_tokens, temperature)

    if _PROVIDER == "local" or use_adapter:
        return _generate_local(
            prompt, max_tokens, temperature, use_adapter=use_adapter
        )

    raise RuntimeError(f"Неизвестный LLM_PROVIDER: {_PROVIDER}")
