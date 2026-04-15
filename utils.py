import base64
import io

import matplotlib.pyplot as plt
import pandas as pd
from mlx_lm import generate, load

model = None
tokenizer = None
model_loaded = False


def init_model(model_path="mlx-community/gemma-2-2b-it-4bit"):
    global model, tokenizer, model_loaded
    model, tokenizer = load(model_path)
    model_loaded = True
    print(f"Модель {model_path} загружена через MLX")


def generate_local_response(prompt, max_tokens=1024, temp=0.5):
    global model, tokenizer
    if not model_loaded:
        raise RuntimeError("Модель не загружена. Вызовите init_model().")

    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template"):
        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        input_text = f"<|user|>\n{prompt}\n<|assistant|>\n"

    response = generate(
        model,
        tokenizer,
        prompt=input_text,
        max_tokens=max_tokens,
        temp=temp,
    )
    return response.strip()


def generate_summary(df):
    desc = df.describe(include="all").to_string()
    missing = df.isnull().sum().to_string()
    dtypes = df.dtypes.to_string()
    nunique = df.nunique().to_string()
    sample_rows = df.head(3).to_string()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    categorical_cols = df.select_dtypes(
        include=["object", "category"]
    ).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    prompt = f"""
    Проведи глубокий анализ датасета по следующим данным.

    Основная информация:
    Количество строк: {df.shape[0]};
    Количество столбцов: {df.shape[1]};
    Числовые колонки: {numeric_cols if numeric_cols else 'нет'};
    Категориальные колонки: {categorical_cols if categorical_cols else 'нет'};
    Дата/время колонки: {datetime_cols if datetime_cols else 'нет'};

    Детали по колонкам:
    Типы данных: {dtypes}
    Уникальные значения (первые 5 для каждой колонки): {nunique}

    Качество данных:
    Пропуски (колонка: количество): {missing}

    Основные статистики (для числовых и категориальных): {desc}

    Пример данных (первые 3 строки): {sample_rows}

    Твой ответ должен содержать следующие разделы:

    1. Общая характеристика (1-2 предложения: что это за данные, какую предметную область описывают)

    2. Качество данных и предобработка:
    Есть ли пропуски? Если да, в каких колонках, насколько критично, как их можно заполнить.
    Корректны ли типы данных? Если нет, что нужно изменить (например, дату из object в datetime).
    Есть ли дубликаты? (предположи, если нет точной информации)
    Есть ли выбросы в числовых колонках? (на основе статистик, например, min/max, стандартное отклонение)

    3. Ключевые метрики и распределения:
    Для числовых колонок: назови среднее, медиану, разброс, асимметрию (если видно из статистик).
    Для категориальных: топ 3 самых частых значений, редкие категории.
    Если есть временные колонки укажи диапазон дат, возможную сезонность.

    4. Взаимосвязи и потенциальные инсайты:
    Какие числовые пары могут быть коррелированы? (на основе предметной области)
    Какие категориальные группы могут влиять на числовые метрики?
    Один неочевидный вывод, который можно сделать из метаданных (например, «большое количество пропусков в колонке X может говорить о том, что её заполняли только в определённых условиях»).

    5. Рекомендации по дальнейшему анализу:
    Какие визуализации стоит построить в первую очередь (укажи конкретные типы графиков и колонки).
    Какие метрики или группировки помогут ответить на типовые бизнес вопросы.
    Если данные временные, предложи анализ тренда или скользящего среднего.

    Требования к ответу:
    Пиши на русском языке.
    Используй маркированные списки и жирный шрифт для ключевых выводов.
    Не пиши общих фраз вроде «данные могут быть полезны», давай конкретику.
    Если каких то данных не хватает (например нет информации о дубликатах) скажи «требуется дополнительная проверка».
    """
    try:
        return generate_local_response(prompt, max_tokens=1500, temp=0.5)
    except Exception as e:
        return f"Ошибка при генерации аналитики: {e}"


def generate_plot(df, chart_type, col_x, col_y):
    if chart_type == "histogram":
        sample_data = df[col_x].head(10).to_string()
        prompt = f"""
        Напиши только Python код для построения гистограммы matplotlib.
        НЕ используй plt.savefig(). НЕ сохраняй график в файл.
        Создай фигуру и сохрани её в переменную 'fig' (например, fig, ax = plt.subplots()).
        Данные (первые 10 строк):\n{sample_data}
        Построй гистограмму для колонки '{col_x}'.
        Используй весь DataFrame 'df'.
        Добавь заголовок, подпись оси X ('{col_x}'), подпись оси Y ('Частота').
        В конце не вызывай plt.show().
        """
    elif chart_type == "bar chart":
        sample_data = df[[col_x, col_y]].head(10).to_string()
        prompt = f"""
        Напиши только Python код для столбчатой диаграммы matplotlib.
        НЕ используй plt.savefig(). НЕ сохраняй график в файл.
        Создай фигуру и сохрани её в переменную 'fig' (например, fig, ax = plt.subplots()).
        Данные (первые 10 строк):\n{sample_data}
        Построй bar chart: X='{col_x}', Y='{col_y}'.
        Используй весь 'df'.
        Добавь заголовок, подписи осей.
        В конце не вызывай plt.show().
        """
    elif chart_type == "line plot":
        sample_data = df[[col_x, col_y]].head(10).to_string()
        prompt = f"""
        Напиши только Python код для линейного графика matplotlib.
        НЕ используй plt.savefig(). НЕ сохраняй график в файл.
        Создай фигуру и сохрани её в переменную 'fig' (например, fig, ax = plt.subplots()).
        Данные (первые 10 строк):\n{sample_data}
        Построй line plot: X='{col_x}', Y='{col_y}'.
        Используй весь 'df'.
        Добавь заголовок, подписи осей.
        В конце не вызывай plt.show().
        """
    else:  # scatter plot
        sample_data = df[[col_x, col_y]].head(10).to_string()
        prompt = f"""
        Напиши только Python код для scatter plot matplotlib.
        НЕ используй plt.savefig(). НЕ сохраняй график в файл.
        Создай фигуру и сохрани её в переменную 'fig' (например, fig, ax = plt.subplots()).
        Данные (первые 10 строк):\n{sample_data}
        Построй scatter plot: X='{col_x}', Y='{col_y}'.
        Используй весь 'df'.
        Добавь заголовок, подписи осей.
        В конце не вызывай plt.show().
        """
    try:
        code_response = generate_local_response(
            prompt, max_tokens=800, temp=0.2
        )
        code = code_response
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        exec_globals = {"plt": plt, "pd": pd, "df": df}
        exec(code, exec_globals)
        fig = exec_globals.get("fig", plt.gcf())
        return fig, code
    except Exception as e:
        return None, str(e)


def fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
