import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from utils import fig_to_base64, generate_plot, generate_summary, init_model


@st.cache_resource
def load_cached_model():
    init_model()
    return True


if "model_initialized" not in st.session_state:
    with st.spinner("Загрузка модели (первый раз может занять до минуты)..."):
        load_cached_model()
    st.session_state.model_initialized = True

st.set_page_config(page_title="AI Аналитик", layout="wide")
st.title("AI-аналитик данных")
st.markdown(
    "Загрузите несколько файлов, переключайтесь между ними и анализируйте."
)

if "files_data" not in st.session_state:
    st.session_state.files_data = {}
if "current_file" not in st.session_state:
    st.session_state.current_file = None

uploaded_file = st.file_uploader(
    "Загрузите CSV или Excel", type=["csv", "xlsx"], key="file_uploader"
)

if uploaded_file is not None:
    file_name = uploaded_file.name
    if file_name not in st.session_state.files_data:
        if file_name.endswith(".csv"):
            encodings = [
                "utf-8",
                "cp1251",
                "windows-1251",
                "latin1",
                "iso-8859-1",
            ]
            df = None
            for enc in encodings:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                st.stop()
        else:
            df = pd.read_excel(uploaded_file)

        st.session_state.files_data[file_name] = {
            "df": df,
            "summary": None,
            "fig_base64": None,
            "chart_type": None,
            "col_x": None,
            "col_y": None,
            "plot_generated": False,
        }
        st.session_state.current_file = file_name
        st.rerun()

if st.session_state.files_data:
    file_names = list(st.session_state.files_data.keys())
    if st.session_state.current_file not in file_names:
        st.session_state.current_file = file_names[0]
    selected_file = st.selectbox(
        "Выберите файл для анализа",
        file_names,
        index=file_names.index(st.session_state.current_file),
    )
    if selected_file != st.session_state.current_file:
        st.session_state.current_file = selected_file
        st.rerun()
else:
    st.info("Загрузите файл, чтобы начать.")
    st.stop()

current = st.session_state.files_data[st.session_state.current_file]
df = current["df"]

st.subheader(f"Файл: {st.session_state.current_file}")
st.subheader("Предпросмотр данных")
st.dataframe(df.head())

numeric_cols = df.select_dtypes(include="number").columns.tolist()
if len(numeric_cols) == 0:
    st.warning("Нет числовых колонок для графика.")
    show_plot_controls = False
else:
    show_plot_controls = True

if show_plot_controls:
    with st.expander(
        "Настройки графика", expanded=not current["plot_generated"]
    ):
        chart_type = st.selectbox(
            "Тип графика",
            ["scatter plot", "line plot", "bar chart", "histogram"],
            key=f"chart_type_{st.session_state.current_file}",
        )
        if chart_type == "histogram":
            col_x = st.selectbox(
                "Колонка для гистограммы",
                numeric_cols,
                key=f"col_x_{st.session_state.current_file}",
            )
            col_y = None
        else:
            col_x = st.selectbox(
                "Ось X",
                numeric_cols,
                key=f"col_x_{st.session_state.current_file}",
            )
            col_y = st.selectbox(
                "Ось Y",
                numeric_cols,
                index=min(1, len(numeric_cols) - 1),
                key=f"col_y_{st.session_state.current_file}",
            )

        if st.button(
            "Сгенерировать аналитику и график",
            key=f"gen_{st.session_state.current_file}",
        ):
            with st.spinner("Генерация аналитики..."):
                summary = generate_summary(df)
                current["summary"] = summary
            with st.spinner("Генерация графика..."):
                fig, err = generate_plot(df, chart_type, col_x, col_y)
            if fig is not None:
                fig_base64 = fig_to_base64(fig)
                plt.close(fig)
                current["fig_base64"] = fig_base64
                current["chart_type"] = chart_type
                current["col_x"] = col_x
                current["col_y"] = col_y
                current["plot_generated"] = True
            else:
                current["plot_generated"] = False
                st.error(f"Не удалось сгенерировать график( {err}")

if current["summary"] is not None:
    st.subheader("AI-аналитика")
    st.write(current["summary"])

if current["plot_generated"] and current["fig_base64"] is not None:
    st.subheader(f"График: {current['chart_type']}")
    st.image(f"data:image/png;base64,{current['fig_base64']}")
