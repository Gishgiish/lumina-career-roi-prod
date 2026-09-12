# scripts/sync_to_r2.py
import os
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def upload_directory_to_r2(local_dir: Path, r2_prefix: str, client):
    if not local_dir.exists():
        print(f"   -> Local directory {local_dir} does not exist. Skipping.")
        return

    for file_path in local_dir.rglob("*"):
        if file_path.is_file():
            object_key = f"{r2_prefix}/{file_path.name}"
            print(f"   -> Uploading {file_path.name} to s3://{BUCKET_NAME}/{object_key}...")
            client.upload_file(str(file_path), BUCKET_NAME, object_key)

def run_cloud_sync():
    print("☁️ Starting Cloud Sync to Cloudflare R2...\n")
    
    if not all([BUCKET_NAME, ACCESS_KEY, SECRET_KEY, ENDPOINT_URL]):
        raise ValueError("Missing R2 credentials in .env file!")

    client = get_r2_client()
    client.head_bucket(Bucket=BUCKET_NAME) # Verify access
    print(f"✅ Successfully authenticated with bucket: {BUCKET_NAME}\n")

    from src.utils.paths import GOLD_DIR, SILVER_DIR

    print("🥈 Syncing Silver Layer...")
    upload_directory_to_r2(SILVER_DIR, "silver", client)
    
    print("\n🥇 Syncing Gold Layer...")
    upload_directory_to_r2(GOLD_DIR, "gold", client)
    
    print("\n✅ Cloud Sync Completed Successfully!")