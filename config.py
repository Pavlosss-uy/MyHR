import os
from dotenv import load_dotenv

load_dotenv()

# --- Global Settings ---
# When the other team finishes models, we swap "MOCK" or "OPENAI" with "DEEPGRAM" here.
STT_PROVIDER = "WHISPER_LOCAL" # Options: "WHISPER_LOCAL", "DEEPGRAM"
TTS_PROVIDER = "MOCK"          # Options: "MOCK", "DEEPGRAM", "OPENAI"
LLM_MODEL = "gpt-3.5-turbo"    # Options: "gpt-4", "claude-3", etc.

# Paths
UPLOAD_DIR = "./uploads"
STORAGE_DIR = "./storage"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)