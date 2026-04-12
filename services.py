import os
import re
import uuid
import asyncio
from typing import AsyncIterator, Optional

import httpx
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
AUDIO_DIR = "static/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=en"
DEEPGRAM_SPEAK_MP3_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
DEEPGRAM_SPEAK_STREAM_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&sample_rate=16000"


def _clean_for_tts(text: str) -> str:
    """
    Prepare text for Deepgram TTS so punctuation creates natural pauses
    and markdown characters are not read aloud literally.
    """
    if not text:
        return ""

    # Remove any lingering <thinking> blocks the LLM might have leaked
    text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)

    # Strip markdown: bold, italic, code spans
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
    text = re.sub(r"`{1,3}([^`\n]+)`{1,3}", r"\1", text)

    # Strip markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Convert em-dashes and en-dashes to a comma + space (natural pause in TTS)
    text = re.sub(r"\s*[—–]\s*", ", ", text)

    # Remove bullet / numbered list markers
    text = re.sub(r"^\s*[-•*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines → single space between sentences
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\n", " ", text)

    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def _detect_content_type(audio_path: str) -> str:
    ext = os.path.splitext(audio_path)[1].lower()
    return {
        ".webm": "audio/webm",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
        ".mp3": "audio/mp3",
        ".ogg": "audio/ogg",
    }.get(ext, "audio/webm")


def transcribe_audio(audio_path: str, content_type: Optional[str] = None) -> str:
    """Prerecorded STT from a file path."""
    if not DEEPGRAM_API_KEY:
        print("❌ Deepgram API Key missing.")
        return ""

    if not content_type:
        content_type = _detect_content_type(audio_path)

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type,
    }

    try:
        with open(audio_path, "rb") as audio_file:
            response = requests.post(DEEPGRAM_LISTEN_URL, headers=headers, data=audio_file, timeout=120)

        response.raise_for_status()
        data = response.json()
        return data["results"]["channels"][0]["alternatives"][0].get("transcript", "").strip()
    except Exception as e:
        print(f"STT Error: {e}")
        return ""


def transcribe_audio_bytes(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """Prerecorded STT from raw bytes. Used for utterance-finalized WebSocket audio."""
    if not DEEPGRAM_API_KEY:
        print("❌ Deepgram API Key missing.")
        return ""

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type,
    }

    try:
        response = requests.post(DEEPGRAM_LISTEN_URL, headers=headers, data=audio_bytes, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["results"]["channels"][0]["alternatives"][0].get("transcript", "").strip()
    except Exception as e:
        print(f"STT Bytes Error: {e}")
        return ""


def generate_audio(text: str) -> Optional[str]:
    """TTS to an MP3 file for the REST fallback."""
    if not DEEPGRAM_API_KEY:
        return None

    text = _clean_for_tts(text)
    if not text:
        return None

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(DEEPGRAM_SPEAK_MP3_URL, headers=headers, json={"text": text}, timeout=120)
        response.raise_for_status()

        filename = f"q_{uuid.uuid4().hex[:8]}.mp3"
        file_path = os.path.join(AUDIO_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path
    except Exception as e:
        print(f"TTS Error: {e}")
        return None


async def generate_audio_stream(text: str) -> AsyncIterator[bytes]:
    """
    Stream raw PCM audio bytes from Deepgram without blocking the event loop.
    Frontend should treat this as linear16 PCM, 16kHz, mono.
    """
    if not DEEPGRAM_API_KEY:
        return

    text = _clean_for_tts(text)
    if not text:
        return

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", DEEPGRAM_SPEAK_STREAM_URL, headers=headers, json={"text": text}) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
    except Exception as e:
        print(f"Live TTS Error: {e}")
        return


def transcribe_audio_url(audio_url: str) -> str:
    """STT from a public URL."""
    if not DEEPGRAM_API_KEY:
        print("❌ Deepgram API Key missing.")
        return ""

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {"url": audio_url}

    try:
        response = requests.post(DEEPGRAM_LISTEN_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["results"]["channels"][0]["alternatives"][0].get("transcript", "").strip()
    except Exception as e:
        print(f"STT URL Error: {e}")
        return ""
