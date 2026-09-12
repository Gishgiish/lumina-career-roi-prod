# src/ingestion/sources/base.py
"""
Base class for all job board source adapters.

Each source adapter must:
  1. Know how to authenticate with its API
  2. Know how to paginate through results
  3. Know how to map the API's response to the canonical `RawJob` schema
  4. Track its own watermark for incremental ingestion
"""
import abc
import hashlib
import logging
from datetime import UTC, datetime

from tenacity import retry, stop_after_attempt, wait_exponential

from src.schemas import RawJobBatch

logger = logging.getLogger(__name__)


class SourceError(Exception):
    """Raised when a source adapter fails to fetch or parse data."""


class BaseSource(abc.ABC):
    """Abstract base class for job board source adapters."""

    #: A human-readable name for the source
    name: str = "base"

    #: Order of preference when deduplicating across sources (higher = more trusted)
    trust_rank: int = 0

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._validate_config()

    def _validate_config(self):
        """Hook for subclasses to validate required config/credentials."""
        return

    @abc.abstractmethod
    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        """
        Fetch a batch of jobs from the source and return them as a canonical
        RawJobBatch.

        :param last_watermark: Timestamp of the last successful fetch. Sources
            should only fetch jobs posted AFTER this timestamp when supported.
        :returns: A RawJobBatch containing mapped jobs + new watermark.
        """
        raise NotImplementedError

    @staticmethod
    def make_job_id(source: str, external_id: str) -> str:
        """
        Deterministic globally-unique job ID across all sources.
        Uses a SHA-256 hash of (source, external_id).
        """
        raw = f"{source}|{external_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _safe_datetime(dt_str: str | float | None, default: str | None = None) -> str:
        """
        Parse a datetime string or unix timestamp and return ISO 8601 format
        or the default (now) if unparseable.

        Supports:
          - ISO 8601 strings: "2025-06-01T10:00:00Z"
          - Unix timestamps (sec or ms): "1717238400" or 1717238400
        """
        if dt_str is None or dt_str == "":
            return default or datetime.now(UTC).isoformat()

        # Handle unix timestamps (float/int or numeric string)
        if isinstance(dt_str, (int, float)) or str(dt_str).replace(".", "").isdigit():
            try:
                numer = float(dt_str)
                # Detect ms vs sec: ms timestamps are > 1e12 (e.g., 1.7e12)
                if numer > 10_000_000_000:
                    numer = numer / 1000.0
                parsed = datetime.fromtimestamp(numer, tz=UTC)
                return parsed.isoformat()
            except (ValueError, OSError, OverflowError):
                pass

        try:
            parsed = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.isoformat()
        except (ValueError, TypeError):
            return default or datetime.now(UTC).isoformat()

    @staticmethod
    def _clean_text(value: str | None) -> str:
        """Strip HTML tags and clean whitespace from text fields."""
        import re

        if not value:
            return ""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", value)
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _retry_fetch(self, func):
        """Wrap HTTP fetch calls with retry/backoff logic."""
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            reraise=True,
        )
        def _wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return _wrapped()