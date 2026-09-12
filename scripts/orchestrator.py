# scripts/orchestrator.py
""" 
Prefect orchestration for the Lumina Medallion pipeline.

Flow: Multi-Source Ingest -> Bronze -> Silver (dedup + skills) -> Gold -> Cloud Sync
"""
import json
import logging
from datetime import UTC, datetime

import polars as pl
from prefect import flow, get_run_logger, task

from scripts.sync_to_r2 import run_cloud_sync
from src.ingestion.sources.registry import build_default_registry
from src.ingestion.validator import enforce_constraints
from src.transformation.gold import transform_silver_to_gold
from src.transformation.silver import transform_bronze_to_silver
from src.utils.paths import (
    BRONZE_DIR,
    QUARANTINE_DIR,
    STATE_FILE,
    ensure_directories,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_state() -> dict:
    """Load the ingestion state (per-source watermarks)."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"watermarks": {}}


def _save_state(state: dict):
    """Persist the ingestion state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# --- TASKS ---

@task(retries=2, retry_delay_seconds=5)
def task_ingest_bronze():
    """
    Fetch from all registered sources, validate, and write to Bronze.
    Tracks per-source watermarks.
    """
    log = get_run_logger()
    ensure_directories()

    state = _load_state()
    watermarks = state.get("watermarks", {})

    registry = build_default_registry()
    log.info(
        "Fetching from %d sources...",
        len(registry.available_sources),
    )

    # Fetch from all sources
    results = registry.fetch_all(watermarks)

    total_valid = 0
    total_invalid = 0
    total_new = 0
    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    for source, batch in results.items():
        if isinstance(batch, dict) and "error" in batch:
            log.warning("Source %s failed: %s", source.value, batch["error"])
            continue

        jobs = batch.jobs
        if not jobs:
            log.info("Source %s: no new jobs", source.value)
            continue

        total_new += len(jobs)

        # Convert RawJob models to a Polars DataFrame
        records = [job.model_dump() for job in jobs]
        df = pl.DataFrame(records)

        # Validate (currency-aware salary parsing)
        valid_df, invalid_df = enforce_constraints(
            df,
            source=source.value,
            default_currency="USD",
        )
        total_valid += len(valid_df)
        total_invalid += len(invalid_df)

        # Write valid rows to Bronze
        if not valid_df.is_empty():
            bronze_path = BRONZE_DIR / f"jobs_raw_{source.value}_{run_id}.json"
            valid_df.write_ndjson(bronze_path)
            log.info("Source %s: %d valid -> %s", source.value, len(valid_df), bronze_path.name)

        # Write invalid rows to Quarantine
        if not invalid_df.is_empty():
            quarantine_path = QUARANTINE_DIR / f"jobs_rejected_{source.value}_{run_id}.json"
            invalid_df.write_ndjson(quarantine_path)
            log.info("Source %s: %d rejected -> %s", source.value, len(invalid_df), quarantine_path.name)

        # Update watermark
        if batch.new_watermark:
            watermarks[source.value] = batch.new_watermark

    # Persist state
    state["watermarks"] = watermarks
    state["last_run"] = datetime.now(UTC).isoformat()
    _save_state(state)

    log.info(
        "Ingestion summary: %d fetched, %d valid, %d rejected",
        total_new,
        total_valid,
        total_invalid,
    )

    if total_new == 0:
        return "skipped"
    return "success"


@task
def task_transform_silver():
    log = get_run_logger()
    log.info("Starting Silver transformation...")
    return transform_bronze_to_silver()


@task
def task_transform_gold():
    log = get_run_logger()
    log.info("Starting Gold transformation...")
    return transform_silver_to_gold()


@task(retries=2, retry_delay_seconds=5)
def task_sync_to_cloud():
    log = get_run_logger()
    log.info("Starting Cloud Sync...")
    run_cloud_sync()
    return "success"


# --- FLOW ---

@flow(name="Lumina-Medallion-Pipeline", log_prints=True)
def run_full_pipeline():
    logger.info("🚀 Starting Lumina Career ROI Medallion Pipeline")

    # 1. Ingest from all sources
    ingest_status = task_ingest_bronze()

    if ingest_status == "skipped":
        logger.info("Pipeline skipped: No new data.")
        return

    # 2. Transform to Silver (depends on Ingest)
    silver_ok = task_transform_silver()
    if not silver_ok:
        logger.warning("Silver transformation produced no output.")
        return

    # 3. Transform to Gold (depends on Silver)
    task_transform_gold()

    # 4. Sync to Cloud (depends on Gold)
    task_sync_to_cloud()

    logger.info("✅ Pipeline Completed Successfully!")


if __name__ == "__main__":
    run_full_pipeline()