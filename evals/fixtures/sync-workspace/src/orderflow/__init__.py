"""orderflow: a small order-processing pipeline (internal service)."""

from .pipeline import Pipeline, Receipt

__all__ = ["Pipeline", "Receipt"]
