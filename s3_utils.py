import logging
import os
import shutil

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# When AWS_BUCKET_NAME is set, upload to real S3; otherwise fall back to local disk (dev mode).
AWS_BUCKET = os.getenv("AWS_BUCKET_NAME")

if AWS_BUCKET:
    s3_client = boto3.client("s3")
else:
    class _LocalS3:
        def head_bucket(self, **kwargs): pass
        def create_bucket(self, **kwargs): pass
    s3_client = _LocalS3()


def upload_file_to_s3(file_obj, bucket_name=None, prefix="uploads", **kwargs):
    """Upload a file to S3 (or local disk in dev mode).

    Accepts FastAPI UploadFile objects or local path strings.
    Returns the URL/path of the stored file, or None on failure.
    """
    if not file_obj:
        return None

    bucket = bucket_name or AWS_BUCKET
    filename = file_obj if isinstance(file_obj, str) else file_obj.filename

    if bucket and AWS_BUCKET:
        key = f"{prefix}/{filename}"
        try:
            if hasattr(file_obj, "file"):
                s3_client.upload_fileobj(file_obj.file, bucket, key)
            elif isinstance(file_obj, str) and os.path.exists(file_obj):
                s3_client.upload_file(file_obj, bucket, key)
            url = f"https://{bucket}.s3.amazonaws.com/{key}"
            logger.debug("Uploaded to S3: %s", url)
            return url
        except ClientError as e:
            logger.error("S3 upload failed: %s", e)
            return None
    else:
        # Dev mode: save locally
        destination = os.path.join(UPLOAD_DIR, filename)
        try:
            if hasattr(file_obj, "file"):
                with open(destination, "wb") as buf:
                    shutil.copyfileobj(file_obj.file, buf)
            elif isinstance(file_obj, str) and os.path.exists(file_obj):
                shutil.copy(file_obj, destination)
            logger.debug("File saved locally: %s", destination)
            return f"/{destination}"
        except Exception as e:
            logger.error("Local upload failed: %s", e)
            return None
