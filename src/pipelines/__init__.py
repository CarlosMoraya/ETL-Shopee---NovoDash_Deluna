"""
Pipelines ETL Shopee
"""

__all__ = [
    "run_monitoramento_pipeline",
    "run_driver_profile_pipeline",
    "run_pnr_pipeline",
]


def __getattr__(name):
    """Lazy imports para evitar warnings de import circular"""
    if name == "run_monitoramento_pipeline":
        from .shopee_monitoramento_pipeline import run_pipeline
        return run_pipeline
    elif name == "run_driver_profile_pipeline":
        from .shopee_driver_profile_pipeline import run_pipeline
        return run_pipeline
    elif name == "run_pnr_pipeline":
        from .shopee_pnr_pipeline import run_pipeline
        return run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
