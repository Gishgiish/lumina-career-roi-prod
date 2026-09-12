# src/ingestion/sources/registry.py 
"""
Central registry for all source adapters.

The registry is responsible for instantiation and lookup of the available
job board sources. It also handles graceful degradation — if a source's
credentials are missing, that source is just skipped during ingestion.
"""
import logging
from typing import TYPE_CHECKING

from src.schemas import JobSource

if TYPE_CHECKING:
    from src.ingestion.sources.base import BaseSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Registry that maps JobSource -> adapter class and manages instances."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._adapters: dict[JobSource, BaseSource] = {}

    def register(self, source: JobSource, adapter: "BaseSource"):
        """Register a source adapter instance."""
        self._adapters[source] = adapter

    def get(self, source: JobSource) -> "BaseSource":
        """Get the adapter for a source."""
        adapter = self._adapters.get(source)
        if adapter is None:
            raise KeyError(f"No adapter registered for source: {source}")
        return adapter

    @property
    def available_sources(self) -> list[JobSource]:
        """Sources that have been successfully registered."""
        return list(self._adapters.keys())

    def fetch_all(self, watermarks: dict[str, str | None]) -> dict[JobSource, object]:
        """
        Fetch from all registered sources, skipping any that fail.

        :param watermarks: Mapping of JobSource -> last watermark (ISO str)
        :returns: Mapping of JobSource -> RawJobBatch (or error info for failures)
        """
        results: dict[JobSource, object] = {}
        for source, adapter in self._adapters.items():
            try:
                watermark = watermarks.get(source.value)
                batch = adapter.fetch(last_watermark=watermark)
                results[source] = batch
                logger.info(
                    "Fetched %d jobs from %s (watermark: %s)",
                    len(batch.jobs),
                    source.value,
                    batch.new_watermark,
                )
            except Exception as exc:  # noqa: BLE001 - we want to trap all source errors
                logger.error("Failed to fetch from %s: %s", source.value, exc)
                results[source] = {"error": str(exc)}
        return results


def build_default_registry(env_config: dict | None = None) -> SourceRegistry:
    """
    Build the registry with all adapters that can be configured from the
    current environment.

    :param env_config: Optional dict for overriding env vars (mainly for tests)
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()

    registry = SourceRegistry(env_config or {})

    # Keyless sources — always available
    from src.ingestion.sources.arbeitnow import ArbeitnowSource
    from src.ingestion.sources.greenhouse import GreenhouseSource
    from src.ingestion.sources.hackernews import HackerNewsSource
    from src.ingestion.sources.lever import LeverSource
    from src.ingestion.sources.remoteok import RemoteOKSource
    from src.ingestion.sources.remotive import RemotiveSource

    registry.register(JobSource.REMOTEOK, RemoteOKSource())
    registry.register(JobSource.REMOTIVE, RemotiveSource())
    registry.register(JobSource.ARBEITNOW, ArbeitnowSource())
    registry.register(JobSource.HACKERNEWS, HackerNewsSource())
    registry.register(JobSource.GREENHOUSE, GreenhouseSource())
    registry.register(JobSource.LEVER, LeverSource())

    # Adzuna — requires API key
    adzuna_app_id = os.getenv("ADZUNA_APP_ID")
    adzuna_app_key = os.getenv("ADZUNA_APP_KEY")
    if adzuna_app_id and adzuna_app_key:
        from src.ingestion.sources.adzuna import AdzunaSource

        registry.register(
            JobSource.ADZUNA,
            AdzunaSource(
                {
                    "app_id": adzuna_app_id,
                    "app_key": adzuna_app_key,
                }
            ),
        )
        logger.info("Adzuna source registered (credentials present)")
    else:
        logger.warning("Adzuna credentials not found — source disabled")

    # USAJobs — requires API key
    usajobs_key = os.getenv("USAJOBS_API_KEY")
    if usajobs_key:
        from src.ingestion.sources.usajobs import USAJobsSource

        registry.register(
            JobSource.USAJOBS,
            USAJobsSource({"api_key": usajobs_key}),
        )
        logger.info("USAJobs source registered (credentials present)")
    else:
        logger.warning("USAJobs API key not found — source disabled")

    return registry