# src/utils/paths.py
from pathlib import Path

# Dynamically find the root directory of the project
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Define Medallion Layer paths
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
GOLD_DIR = PROJECT_ROOT / "data" / "gold"
QUARANTINE_DIR = PROJECT_ROOT / "data" / "quarantine"
STATE_FILE = PROJECT_ROOT / "configs" / "ingestion_state.json"

# Ensure directories exist
def ensure_directories():
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)