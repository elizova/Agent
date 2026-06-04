import streamlit as st

from .agent import (
    calculate_ats_score,
    compare_resume_to_vacancy,
    extract_requirements,
    tailor_resume,
)
from .db import save_analysis
from .streamlit_app import render_ats_score_html


def render_keyword_tags(
    skills: list, soft: list, hh_skills: list | None = None
):
    all_skills = list(skills or [])
    if hh_skills:
        for s in hh_skills:
            if s not in all_skills:
                all_skills.append(s)
    if all_skills:
        st.markdown("##### Ключевые слова для ATS")
        cols = st.columns(min(3, max(1, len(all_skills[:9]) // 3 + 1)))
        for i, skill in enumerate(all_skills[:24]):
            cols[i % len(cols)].markdown(f"`{skill}`")
    if soft:
        st.markdown("##### Soft skills")
        st.markdown(" ".join(f"`{s}`" for s in soft[:12]))


def render_ats_block(ats: dict, label: str = "Оценка ATS"):
    score = ats["score"]
    render_ats_score_html(score, label, ats.get("message", ""))
    if ats.get("missing"):
        with st.expander("Не хватает в резюме", expanded=score < 50):
            for m in ats["missing"][:20]:
                st.write(f"• {m}")
    if ats.get("matched"):
        with st.expander("Уже есть в резюме"):
            for m in ats["matched"][:20]:
                st.write(f"• {m}")


def render_vacancy_analysis(
    vacancy_id: str,
    vacancy_title: str,
    full_description: str,
    hh_skills: list | None,
    resume_text: str,
    source: str = "hh",
    cache_prefix: str = "",
    vacancy_url: str = "",
):
    key_base = f"{cache_prefix}_{vacancy_id}"

    reqs_key = f"reqs_{key_base}"
    if reqs_key not in st.session_state:
        with st.spinner("Извлекаю ключевые требования..."):
            st.session_state[reqs_key] = extract_requirements(
                full_description, hh_skills=hh_skills
            )
    reqs = st.session_state[reqs_key]

    if reqs.get("_note"):
        st.info(reqs["_note"])

    st.write(f"**Требуемый опыт:** {reqs.get('experience') or 'не указан'}")
    render_keyword_tags(
        reqs.get("skills", []),
        reqs.get("soft_skills", []),
        hh_skills=None,
    )

    if reqs.get("duties"):
        st.write("**Обязанности:**")
        for d in reqs["duties"]:
            st.write(f"- {d}")

    if not resume_text:
        st.info("Введите резюме в боковой панели для сравнения и адаптации.")
        return

    st.markdown("---")
    st.subheader("Автофильтр работодателя (ATS)")
    ats_before = calculate_ats_score(resume_text, reqs)
    render_ats_block(ats_before, "До адаптации")

    cmp_key = f"cmp_{key_base}"
    if cmp_key not in st.session_state:
        with st.spinner("Сравниваю резюме с требованиями..."):
            st.session_state[cmp_key] = compare_resume_to_vacancy(
                resume_text, reqs
            )
    comparison = st.session_state[cmp_key]

    st.subheader("Пробелы в резюме")
    for label, key, ok_msg in (
        ("Навыки", "missing_skills", "Все навыки отражены"),
        ("Soft skills", "missing_soft", "Soft skills отражены"),
        ("Обязанности", "missing_duties", "Обязанности отражены"),
    ):
        missing = comparison.get(key, [])
        if missing:
            st.write(f"**{label}:**")
            for item in missing:
                st.write(f"- {item}")
        else:
            st.write(ok_msg)

    if comparison.get("missing_experience"):
        st.write(f"**Опыт:** не отражён — {comparison['missing_experience']}")
    else:
        st.write("Требования к опыту выполнены")

    if comparison.get("recommendations"):
        st.write(f"**Рекомендации:** {comparison['recommendations']}")

    st.markdown("---")
    st.subheader("Адаптация резюме")
    allow_extra = st.session_state.get("allow_invented_skills", False)
    if allow_extra:
        st.caption(
            "Адаптация с добавлением навыков из вакансии для улучшения отклика."
        )
    else:
        st.caption(
            "Адаптация только на основе вашего текущего опыта, без добавления новых навыков."
        )

    gen_key = f"gen_btn_{key_base}"
    if st.button(
        "Сгенерировать адаптированное резюме", key=gen_key, type="primary"
    ):
        with st.spinner("Адаптирую резюме..."):
            ats_missing = ats_before.get("missing") or []
            new_resume = tailor_resume(
                resume_text,
                full_description,
                reqs,
                comparison,
                allow_invented_skills=allow_extra,
                ats_missing=ats_missing,
            )
            st.session_state[f"gen_resume_{key_base}"] = new_resume
            ats_after = calculate_ats_score(
                new_resume,
                reqs,
                original_resume=resume_text,
                penalize_invented=not allow_extra,
                ats_before=ats_before["score"],
            )
            if not allow_extra:
                cap = min(
                    88, max(ats_before["score"] + 12, ats_before["score"])
                )
                ats_after["score"] = min(ats_after["score"], cap)
                if ats_after.get("invented"):
                    ats_after["message"]
            if ats_after["score"] < ats_before["score"] - 8:
                st.warning(
                    "Оценка ATS снизилась после адаптации. Убедитесь, что в разделе «Ключевые навыки» указаны навыки, а не фразы из опыта. Попробуйте перегенерировать."
                )
            st.session_state[f"ats_after_{key_base}"] = ats_after
            adapted_to_save = (new_resume or "").strip()
            if len(adapted_to_save) < 80:
                st.warning(
                    "Текст резюме слишком короткий — в историю не сохранён."
                )
            else:
                try:
                    from utils.auth_storage import restore_auth_token
                    from utils.history_local import cache_adapted_resume

                    restore_auth_token()
                    meta = save_analysis(
                        vacancy_id=str(vacancy_id),
                        vacancy_title=vacancy_title,
                        source=source,
                        requirements=reqs,
                        comparison=comparison,
                        ats_before=ats_before["score"],
                        ats_after=ats_after["score"],
                        resume_original=resume_text,
                        resume_adapted=adapted_to_save,
                        vacancy_url=vacancy_url,
                    )
                    if meta.get("id"):
                        cache_adapted_resume(meta["id"], adapted_to_save)
                    if meta.get("saved"):
                        st.toast(f"Сохранено в истории (#{meta.get('id')})")
                    elif meta.get("id"):
                        st.toast(
                            f"Резюме сохранено локально (#{meta.get('id')}). "
                            "Для полной синхронизации обновите API-сервер."
                        )
                    else:
                        st.warning("Не удалось сохранить в историю.")
                except Exception as e:
                    st.warning(
                        f"Резюме готово, но не удалось сохранить в историю: {e}"
                    )

    if f"gen_resume_{key_base}" in st.session_state:
        adapted = st.session_state[f"gen_resume_{key_base}"]
        st.text_area("Адаптированное резюме", value=adapted, height=320)
        st.download_button(
            "Скачать .txt",
            data=adapted,
            file_name=f"resume_{vacancy_id}.txt",
            mime="text/plain",
            key=f"dl_{key_base}",
        )
        if f"ats_after_{key_base}" in st.session_state:
            st.markdown("---")
            render_ats_block(
                st.session_state[f"ats_after_{key_base}"],
                "После адаптации",
            )
