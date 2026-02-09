import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq 

load_dotenv()

# --- Global Settings ---
STT_PROVIDER = "DEEPGRAM"
TTS_PROVIDER = "DEEPGRAM"
LLM_MODEL = "llama-3.3-70b-versatile" 

# Paths
UPLOAD_DIR = "./uploads"
STORAGE_DIR = "./storage"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

# --- SHARED LLM OBJECT ---
# This allows agent.py AND services.py to use the same connection
if os.getenv("GROQ_API_KEY"):
    llm = ChatGroq(
        model=LLM_MODEL,
        temperature=0.3,
        api_key=os.getenv("GROQ_API_KEY")
    )
else:
    print("⚠️ WARNING: GROQ_API_KEY not found in .env file!")
    llm = None