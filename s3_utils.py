import boto3
import os
from fastapi import UploadFile
import uuid

# Check if we are using MinIO locally
ENDPOINT_URL = os.getenv("MINIO_ENDPOINT")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "myhr-media")

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    endpoint_url=ENDPOINT_URL
)

# Auto-create the bucket if it doesn't exist
try:
    s3_client.head_bucket(Bucket=BUCKET_NAME)
except Exception:
    print(f"🪣 Creating local MinIO bucket: {BUCKET_NAME}")
    s3_client.create_bucket(Bucket=BUCKET_NAME)

def upload_file_to_s3(file: UploadFile, prefix: str = "audio") -> str:
    """Uploads a FastAPI UploadFile to S3 (or MinIO) and returns the URL."""
    file_extension = file.filename.split(".")[-1]
    s3_key = f"{prefix}/{uuid.uuid4().hex}.{file_extension}"
    
    # FIX: Add a fallback content type if it comes through as None
    content_type = file.content_type or "application/octet-stream"
    if not file.content_type:
        if file.filename.endswith('.pdf'):
            content_type = "application/pdf"
        elif file.filename.endswith('.wav'):
            content_type = "audio/wav"
    
    s3_client.upload_fileobj(
        file.file, 
        BUCKET_NAME, 
        s3_key,
        ExtraArgs={"ContentType": content_type} # <--- Uses the safe fallback here
    )
    
    # Generate the correct URL depending on if we use MinIO or AWS
    if ENDPOINT_URL:
        s3_url = f"{ENDPOINT_URL}/{BUCKET_NAME}/{s3_key}"
    else:
        s3_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
        
    return s3_url

def download_file_from_s3(s3_url: str, local_path: str):
    """Helper to download if a local tool strictly needs a local file."""
    s3_key = s3_url.split(f"{BUCKET_NAME}/")[-1]
    s3_client.download_file(BUCKET_NAME, s3_key, local_path)