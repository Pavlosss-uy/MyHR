import os
import shutil

# Configuration
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def upload_file_to_s3(file_obj, bucket_name=None, **kwargs):
    """
    Handles FastAPI UploadFile objects by saving them locally.
    """
    if not file_obj:
        return None
        
    try:
        # 1. Get the original filename from the FastAPI object
        # If it's already a string (path), use it; otherwise get the .filename attribute
        filename = file_obj if isinstance(file_obj, str) else file_obj.filename
        destination = os.path.join(UPLOAD_DIR, filename)
        
        # 2. Save the file content
        if hasattr(file_obj, "file"): # It's a FastAPI UploadFile
            with open(destination, "wb") as buffer:
                shutil.copyfileobj(file_obj.file, buffer)
        elif isinstance(file_obj, str) and os.path.exists(file_obj): # It's a local path string
            shutil.copy(file_obj, destination)
            
        print(f"✅ File saved locally to: {destination}")
        return f"/{destination}"
        
    except Exception as e:
        print(f"❌ Local upload failed: {e}")
        return None

class MockS3:
    def head_bucket(self, **kwargs): pass
    def create_bucket(self, **kwargs): pass

s3_client = MockS3()