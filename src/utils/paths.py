# src/utils/paths.py
import os
from pathlib import Path

# Dynamically find the root directory of the project
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_path(raw: str | None, default: Path) -> Path:
    """Resolve an optional path override.

    Empty or missing values fall back to ``default``. Relative paths are
    resolved against the project root so runs are reproducible from any
    working directory; absolute paths are used as-is. ``~`` is expanded.
    """
    if not raw or not raw.strip():
        return default
    path = Path(raw.strip()).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


# Root for the medallion layers. Override with LUMINA_DATA_DIR to keep
# scratch runs away from the default demo data.
DATA_DIR = _resolve_path(os.getenv("LUMINA_DATA_DIR"), PROJECT_ROOT / "data")

# Define Medallion Layer paths
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
QUARANTINE_DIR = DATA_DIR / "quarantine"
STATE_FILE = _resolve_path(
    os.getenv("LUMINA_STATE_FILE"),
    PROJECT_ROOT / "configs" / "ingestion_state.json",
)

# Ensure directories exist
def ensure_directories():
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
