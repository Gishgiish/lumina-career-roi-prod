# scripts/run_bronze_ingestion.py
import json
from datetime import UTC, datetime

from src.ingestion.source import fetch_realistic_job_data
from src.ingestion.validator import enforce_constraints
from src.utils.paths import BRONZE_DIR, QUARANTINE_DIR, STATE_FILE, ensure_directories


def load_state() -> str | None:
    """Loads the last processed watermark from the state file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f).get("last_watermark")
    return None

def save_state(watermark: str):
    """Saves the new watermark to the state file."""
    with open(STATE_FILE, "w") as f:
        json.dump({"last_watermark": watermark}, f)

def run_ingestion():
    print("🔄 Starting Bronze Layer Ingestion...\n")
    
    # Ensure directories exist
    ensure_directories()
    
    # 1. Load state (Watermark)
    last_watermark = load_state()
    print(f"📍 Current Watermark: {last_watermark}")
    
    # 2. Fetch data from source
    raw_df, new_watermark = fetch_realistic_job_data(last_watermark)
    print(f"📥 Fetched {len(raw_df)} raw records from source.\n")
    
    if raw_df.is_empty():
        print("✅ No new data to process. Exiting gracefully.")
        return

    # 3. Enforce constraints (The Bouncer)
    valid_df, invalid_df = enforce_constraints(raw_df)
    print("🛡️ Constraints Enforced:")
    print(f"   -> Valid records: {len(valid_df)}")
    print(f"   -> Rejected records: {len(invalid_df)}\n")
    
    # Generate a unique run ID based on UTC time
    run_id = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    
    # 4. Save Valid Data to Bronze Layer
    if not valid_df.is_empty():
        bronze_path = BRONZE_DIR / f"jobs_raw_{run_id}.json"
        valid_df.write_ndjson(bronze_path)
        print(f"🥉 Saved valid data to Bronze: {bronze_path}")
        
    # 5. Save Invalid Data to Quarantine
    if not invalid_df.is_empty():
        quarantine_path = QUARANTINE_DIR / f"jobs_rejected_{run_id}.json"
        invalid_df.write_ndjson(quarantine_path)
        print(f"🗑️ Saved rejected data to Quarantine: {quarantine_path}")
        
    # 6. Update State (Watermark)
    save_state(new_watermark)
    print(f"\n📍 Updated Watermark to: {new_watermark}")
    print("✅ Bronze Ingestion Completed Successfully!\n")

if __name__ == "__main__":
    run_ingestion()