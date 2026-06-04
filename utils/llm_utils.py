model = None
tokenizer = None
model_loaded = False


def init_model(model_path="mlx-community/Qwen2.5-3B-Instruct-4bit"):
    global model, tokenizer, model_loaded
    from utils.mlx_env import configure_mlx_env

    configure_mlx_env()
    from mlx_lm import load

    model, tokenizer = load(model_path)
    model_loaded = True
    print(f"Модель {model_path} загружена через MLX")


def generate_local_response(prompt, max_tokens=1024, temperature=0.5):
    global model, tokenizer
    if not model_loaded:
        from utils.llm_provider import ensure_local_model_loaded

        ensure_local_model_loaded()
    if not model_loaded:
        raise RuntimeError("Модель не загружена.")
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    if hasattr(tokenizer, "apply_chat_template"):
        messages = [{"role": "user", "content": prompt}]
        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        input_text = prompt
    sampler = make_sampler(temp=temperature)
    response = generate(
        model,
        tokenizer,
        prompt=input_text,
        max_tokens=max_tokens,
        sampler=sampler,
        verbose=False,
    )
    return response.strip()
