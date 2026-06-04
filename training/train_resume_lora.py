import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "mlx"
OUTPUT = ROOT / "output" / "resume-lora"

PROFILE = os.getenv("TRAIN_PROFILE", "").strip().lower()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


_PROFILE_DEFAULTS = {
    "default": {
        "batch_size": 2,
        "lora_layers": 16,
        "iters": 600,
        "max_seq_length": 2048,
        "grad_checkpoint": False,
        "val_batches": 5,
        "grad_accumulation_steps": 1,
        "clear_cache_threshold": 0,
    },
    "light": {
        "batch_size": 1,
        "lora_layers": 8,
        "iters": 400,
        "max_seq_length": 1024,
        "grad_checkpoint": True,
        "val_batches": 2,
        "grad_accumulation_steps": 2,
        "clear_cache_threshold": "512MB",
    },
    "m3-16g": {
        "batch_size": 1,
        "lora_layers": 8,
        "iters": 400,
        "max_seq_length": 768,
        "grad_checkpoint": True,
        "val_batches": 2,
        "grad_accumulation_steps": 2,
        "clear_cache_threshold": "512MB",
    },
}

_defaults = _PROFILE_DEFAULTS.get(PROFILE, _PROFILE_DEFAULTS["default"])
if PROFILE and PROFILE not in _PROFILE_DEFAULTS:
    print(
        f"Неизвестный TRAIN_PROFILE={PROFILE!r}, используются обычные настройки."
    )
    _defaults = _PROFILE_DEFAULTS["default"]
elif PROFILE in ("light", "m3-16g"):
    print(
        f"Профиль TRAIN_PROFILE={PROFILE} — пониженная нагрузка на память.\n"
    )

BASE_MODEL = os.getenv(
    "TRAIN_BASE_MODEL", "mlx-community/Qwen2.5-3B-Instruct-4bit"
)
ITERS = str(_env_int("TRAIN_ITERS", _defaults["iters"]))
BATCH_SIZE = str(_env_int("TRAIN_BATCH_SIZE", _defaults["batch_size"]))
LORA_LAYERS = str(_env_int("TRAIN_LORA_LAYERS", _defaults["lora_layers"]))
MAX_SEQ_LENGTH = str(
    _env_int("TRAIN_MAX_SEQ_LENGTH", _defaults["max_seq_length"])
)
VAL_BATCHES = str(_env_int("TRAIN_VAL_BATCHES", _defaults["val_batches"]))
GRAD_ACCUM = str(
    _env_int(
        "TRAIN_GRAD_ACCUMULATION_STEPS", _defaults["grad_accumulation_steps"]
    )
)
CLEAR_CACHE = os.getenv(
    "TRAIN_CLEAR_CACHE_THRESHOLD", str(_defaults["clear_cache_threshold"])
)
GRAD_CHECKPOINT = _env_bool(
    "TRAIN_GRAD_CHECKPOINT", _defaults["grad_checkpoint"]
)


def main():
    train_file = DATA / "train.jsonl"
    if not train_file.exists():
        print("Сначала: python training/build_mlx_dataset.py")
        sys.exit(1)

    OUTPUT.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "mlx_lm.lora",
        "--model",
        BASE_MODEL,
        "--train",
        "--data",
        str(DATA),
        "--adapter-path",
        str(OUTPUT),
        "--batch-size",
        BATCH_SIZE,
        "--iters",
        ITERS,
        "--num-layers",
        LORA_LAYERS,
        "--max-seq-length",
        MAX_SEQ_LENGTH,
        "--val-batches",
        VAL_BATCHES,
        "--grad-accumulation-steps",
        GRAD_ACCUM,
        "--clear-cache-threshold",
        CLEAR_CACHE,
    ]
    if GRAD_CHECKPOINT:
        cmd.append("--grad-checkpoint")

    print("Параметры:")
    print(f"  модель: {BASE_MODEL}")
    print(f"  batch={BATCH_SIZE}, слоёв LoRA={LORA_LAYERS}, iters={ITERS}")
    print(
        f"  max_seq_length={MAX_SEQ_LENGTH}, grad_checkpoint={GRAD_CHECKPOINT}"
    )
    print(f"  grad_accum={GRAD_ACCUM}, clear_cache={CLEAR_CACHE}")
    print()
    print("Запуск:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"\nАдаптер сохранён: {OUTPUT}")
    print("В .env добавьте:")
    print(f"RESUME_ADAPTER_PATH={OUTPUT.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
