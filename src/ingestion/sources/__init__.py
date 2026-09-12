# src/ingestion/sources/__init__.py
"""
Source adapter layer for multi-source job data ingestion.

Each adapter wraps a job board API and produces the canonical `RawJobBatch`
schema defined in `src/schemas.py`.
"""

from src.ingestion.sources.base import BaseSource
from src.ingestion.sources.registry import SourceRegistry

__all__ = ["BaseSource", "SourceRegistry"]