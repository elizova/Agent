import os

_CONFIGURED = False


def configure_mlx_env() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    os.environ.setdefault("MLX_METAL_PREALLOCATE", "0")
    os.environ.setdefault("AGX_RELAX_CDM_CTXSTORE_TIMEOUT", "1")
    _CONFIGURED = True
