import os
import uuid
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
AUDIO_DIR = "static/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

def transcribe_audio(audio_path: str, content_type: str = None) -> str:
    """STT: Converts Audio -> Text using Deepgram API (Raw HTTP)."""
    if not DEEPGRAM_API_KEY:
        print("❌ Deepgram API Key missing.")
        return ""

    # Detect content type from file extension if not provided
    if not content_type:
        ext = os.path.splitext(audio_path)[1].lower()
        content_type = {
            ".webm": "audio/webm",
            ".mp4":  "audio/mp4",
            ".wav":  "audio/wav",
            ".mp3":  "audio/mp3",
            ".ogg":  "audio/ogg",
        }.get(ext, "audio/webm")  # default to webm (browser MediaRecorder output)

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=en"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type,
    }

    try:
        with open(audio_path, "rb") as audio_file:
            response = requests.post(url, headers=headers, data=audio_file)
        
        response.raise_for_status()
        data = response.json()
        
        # Extract transcript safely
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
            
    except Exception as e:
        print(f"STT Error: {e}")
        return ""

def generate_audio(text: str) -> str:
    """TTS: Converts Text -> Audio using Deepgram API (Raw HTTP)."""
    if not DEEPGRAM_API_KEY:
        return None

    # URL for Aura TTS
    url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"text": text}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Save audio file
        filename = f"q_{uuid.uuid4().hex[:8]}.mp3"
        file_path = os.path.join(AUDIO_DIR, filename)
        
        with open(file_path, "wb") as f:
            f.write(response.content)
            
        return file_path
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

def transcribe_audio_url(audio_url: str) -> str:
    """STT: Converts Audio -> Text using Deepgram API via a public URL."""
    if not DEEPGRAM_API_KEY:
        print("❌ Deepgram API Key missing.")
        return ""

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=en"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Deepgram accepts a JSON payload with the URL
    payload = {"url": audio_url}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract transcript safely
        return data["results"]["channels"][0]["alternatives"][0]["transcript"]
            
    except Exception as e:
        print(f"STT Error: {e}")
        return ""