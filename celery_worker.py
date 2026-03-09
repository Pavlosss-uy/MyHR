import os
from celery import Celery
from dotenv import load_dotenv
from tone import analyze_voice_tone
from database import SessionLocal, SessionRecord

load_dotenv(override=True)

# Initialize Celery connected to your Upstash Redis
celery_app = Celery(
    "myhr_worker",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

@celery_app.task(name="process_audio_tone")
def process_audio_tone_task(audio_path: str, session_id: str):
    """Runs the heavy ML tone analysis in the background and updates the DB."""
    try:
        print(f"🛠️ Background Worker: Analyzing tone for session {session_id}...")
        
        # 1. Run the heavy Wav2Vec2 model
        dominant_tone, tone_report = analyze_voice_tone(audio_path)
        
        # 2. Save the results directly to PostgreSQL
        db = SessionLocal()
        record = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if record:
            state = record.state_data
            state["multimodal_analysis"] = {
                "primary_emotion": dominant_tone, 
                "full_analysis": tone_report
            }
            record.state_data = state
            db.commit()
            print(f"✅ Background Worker: Tone ({dominant_tone}) saved to DB!")
        db.close()

    except Exception as e:
        print(f"❌ Background Worker Error: {e}")
    finally:
        # 3. Clean up the audio file NOW that the worker is done with it
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print("🧹 Background Worker: Cleaned up temporary audio file.")