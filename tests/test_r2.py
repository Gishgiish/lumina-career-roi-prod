# test_r2.py
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

client = boto3.client(
    's3',
    endpoint_url=os.getenv("R2_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

bucket = os.getenv("R2_BUCKET_NAME")
print(f"Attempting to connect to bucket: {bucket}")
print(f"Using endpoint: {os.getenv('R2_ENDPOINT_URL')}")

try:
    client.head_bucket(Bucket=bucket)
    print("✅ SUCCESS! Bucket exists and credentials are valid.")
    
    # List objects to prove it works
    response = client.list_objects_v2(Bucket=bucket)
    print(f"Objects in bucket: {[obj['Key'] for obj in response.get('Contents', [])]}")
except (ClientError, BotoCoreError, ConnectionError) as e:
    print(f"❌ FAILED: {e}")
