import streamlit as st

from utils.agent import build_hh_params_from_chat
from utils.streamlit_app import ensure_app_ready, page_header, render_sidebar

ensure_app_ready()
resume_text = render_sidebar()

page_header(
    "Карьерный чат",
    "Опишите ситуацию — поиск на HH по рекомендации агента (одна должность + фильтры)",
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if st.session_state.get("chat_pending_user"):
    st.session_state.chat_pending_user = None

    resume_ctx = resume_text[:600] if resume_text else "не указано"
    prior = st.session_state.chat_messages[:-1]
    history = "\n".join(
        f"{'Пользователь' if m['role'] == 'user' else 'Консультант'}: {m['content'][:350]}"
        for m in prior[-6:]
    )
    is_first_reply = len([m for m in prior if m["role"] == "assistant"]) == 0

    style = (
        "Это первый ответ: кратко (4-6 предложений), без приветствия и без «Привет»."
        if is_first_reply
        else "Продолжай диалог: без приветствий, сразу по сути, 3-5 предложений."
    )

    system_prompt = f"""Ты карьерный консультант. Отвечай коротко, по-русски, 2-3 предложения без списков и звёздочек.

Правила:
- Внимательно читай резюме кандидата и предлагай профессии на основе его реального опыта и навыков.
- Если просят творческую работу — думай какие творческие профессии подходят именно этому человеку по его опыту. Например: повар → фуд-стилист, кулинарный блогер, разработчик меню, преподаватель кулинарии, фуд-фотограф. Менеджер → контент-менеджер, event-менеджер, арт-директор проекта.
- Если просят спокойную или несложную работу — предлагай: кладовщик, приёмщик заказов, архивариус, библиотекарь, оператор на входящих звонках.
- Если человек отказался от варианта — предложи ДРУГУЮ профессию из той же категории что он просил, не возвращайся к предыдущим вариантам и не меняй категорию без причины.
- Зарплату НЕ придумывай и не называй цифры.
- Не упоминай IT и программирование если не просят.
- В конце каждого ответа одна строка: «Для поиска на HH: [конкретная должность], [город если назвал]»

Резюме кандидата: {resume_ctx}"""

    last_user = st.session_state.chat_messages[-1]["content"]
    user_msg = (history + "\n" + last_user).strip() if history else last_user

    from utils.llm_provider import ensure_local_model_loaded
    ensure_local_model_loaded()
    from utils import llm_utils
    llm_model, llm_tokenizer = llm_utils.model, llm_utils.tokenizer

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_msg},
    ]
    input_text = llm_tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler
    with st.spinner("Думаю…"):
        reply = generate(
            llm_model, llm_tokenizer,
            prompt=input_text,
            max_tokens=200,
            sampler=make_sampler(temp=0.5),
            verbose=False,
        ).strip()

    st.session_state.chat_messages.append(
        {"role": "assistant", "content": reply}
    )
    st.rerun()

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

last_msg = (
    st.session_state.chat_messages[-1]
    if st.session_state.chat_messages
    else None
)
if last_msg and last_msg["role"] == "assistant":
    user_msgs = [
        m for m in st.session_state.chat_messages if m["role"] == "user"
    ]
    if user_msgs and st.button(
        "Искать на HH по рекомендации агента", type="primary"
    ):
        with st.spinner("Формирую запрос для HH…"):
            params, display_q = build_hh_params_from_chat(
                st.session_state.chat_messages,
                resume_hint=resume_text,
            )
        st.session_state.rerun_search = {
            "user_query": display_q,
            "params": params,
        }
        st.switch_page("pages/1_Поиск_HH.py")

prompt = st.chat_input("Ваше сообщение…")
if prompt:
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    st.session_state.chat_pending_user = prompt
    st.rerun()
