import os
import uuid
import requests
from dotenv import load_dotenv
from config import llm
from prompts import FINAL_REPORT_PROMPT

load_dotenv(override=True)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
AUDIO_DIR = "static/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

def transcribe_audio(audio_path: str) -> str:
    """STT: Converts Audio -> Text using Deepgram API (Raw HTTP)."""
    if not DEEPGRAM_API_KEY:
        print("Deepgram API Key missing.")
        return ""

    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=en"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav" # Assumes WAV from Streamlit
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

# --- ADD THIS TO THE END OF services.py ---

def generate_final_markdown_report(candidate_name, job_desc, evaluations, tone_summary):
    """
    Compiles data, calculates score in Python, and generates the report.
    """
    
    # 1. Format Transcript & Calculate Score (Python Math > LLM Math)
    interview_text = ""
    total_score = 0
    count = 0
    
    for i, turn in enumerate(evaluations, 1):
        score = turn.get('score', 0)
        total_score += score
        count += 1
        
        # Format for the prompt
        interview_text += f"\n**Question {i}:** {turn['question']}\n"
        interview_text += f"**Answer:** {turn['answer']}\n"
        interview_text += f"**Evaluation:**\n"
        interview_text += f"- Score: {score}/10\n"
        interview_text += f"- Feedback: {turn['feedback']}\n"
        interview_text += "---\n"

    # Calculate Average (Rounded to 1 decimal)
    avg_score = round(total_score / count, 1) if count > 0 else 0

    # 2. Prepare Tone Context
    tone_context = f"Primary Emotion: {tone_summary.get('primary_emotion', 'Neutral')}\n"
    tone_context += f"Detailed Analysis: {tone_summary.get('full_analysis', 'Audio analysis indicates stable speech patterns.')}"

    # 3. Invoke the LLM with the PRE-CALCULATED score
    chain = FINAL_REPORT_PROMPT | llm
    
    response = chain.invoke({
        "candidate_name": candidate_name,
        "job_description": job_desc[:800] + "...", # Truncate to save tokens
        "interview_data": interview_text,
        "tone_analysis": tone_context,
        "average_score": avg_score # <--- Passing the math result
    })
    
    return response.content