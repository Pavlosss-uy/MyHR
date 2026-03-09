import uvicorn
import shutil
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.graph import END 
from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db, SessionRecord
import json
from fastapi import BackgroundTasks # <-- Add this to your fastapi imports
from s3_utils import upload_file_to_s3 # <-- Assuming you created s3_utils.py from the previous step
from services import transcribe_audio_url, generate_audio
import io
import PyPDF2
from services import transcribe_audio, generate_audio
from celery_worker import process_audio_tone_task

# Import custom modules
from ingest import create_session_index
from agent import app_graph, rewrite_query_node, retrieve_node, generate_question_node, evaluate_answer_node, decide_next_step
from services import transcribe_audio, generate_audio
from tone import analyze_voice_tone

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

session_store = {}

@app.post("/start_interview")
async def start_interview(
    cv: UploadFile = File(...), 
    jd: str = Form(...),
    db: Session = Depends(get_db)  # <-- 1. Inject Database Session
):
    session_id = str(uuid.uuid4())
    
    # 2. Read PDF into Memory & Extract Text (NO DISK SAVING!)
    cv_bytes = await cv.read()
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(cv_bytes))
    cv_text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            cv_text += extracted + "\n"
            
    # 3. Upload original CV directly to S3 (Task 1.3 Achieved)
    await cv.seek(0) # Reset file pointer before upload
    s3_cv_url = upload_file_to_s3(cv, prefix=f"cvs/{session_id}")
        
    # 4. Send the extracted text straight to Pinecone
    try:
        create_session_index(session_id, cv_text, jd)
    except Exception as e:
        print(f"Ingestion Warning: {e}")
    
    # 5. Initialize State
    initial_state = {
        "session_id": session_id,
        "conversation_history": [],
        "current_topic": "Intro",
        "evaluations": [],
        "next_action": "continue",
        "loop_count": 0,         
        "current_search_query": "",
        "initial_job_context": {
            "jd_text": jd,
            "job_title": jd.split('\n')[0] if jd else "Position",
            "candidate_name": cv.filename.replace('.pdf', '').replace('_', ' ') if cv.filename else "Candidate",
            "cv_url": s3_cv_url  # Store S3 URL instead of local path
        },
        "multimodal_analysis": {}
    }
    
    # 6. Run LangGraph Agent
    result = app_graph.invoke(initial_state)
    
    # 7. SAVE TO POSTGRESQL DATABASE (Task 1.1 Achieved)
    # Replaces: session_store[session_id] = result
    db_record = SessionRecord(session_id=session_id, state_data=result)
    db.add(db_record)
    db.commit()
    
    # 8. TTS & Return
    question_text = result["last_question"]
    audio_path = generate_audio(question_text)
    audio_url = f"http://localhost:8000/static/audio/{os.path.basename(audio_path)}" if audio_path else None

    return {
        "session_id": session_id,
        "question": question_text,
        "audio_url": audio_url
    }

@app.post("/submit_answer")
async def submit_answer(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...), 
    audio: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Fetch State from Cloud Database
    record = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    current_state = record.state_data

    # 2. Read audio bytes into memory immediately (Fixes the "closed file" crash)
    audio_bytes = await audio.read()

    # 3. Save temporarily (Fixes Deepgram URL reachability and Librosa requirements)
    temp_audio_path = os.path.join(UPLOAD_DIR, f"temp_{session_id}.wav")
    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)

    # 4. Upload to MinIO/S3 in the background
    await audio.seek(0)
    s3_audio_url = upload_file_to_s3(audio, prefix=f"answers/{session_id}")
    
    # 5. Transcribe using the physical file, NOT the URL
    transcription = transcribe_audio(temp_audio_path)
    if not transcription: transcription = "(No speech detected)"
    
    # 6. Hand off Tone Analysis to Celery (Instantly returns!)
    process_audio_tone_task.delay(temp_audio_path, session_id)

    # Set a placeholder so the LangGraph agent doesn't crash right now
    current_state["last_answer"] = transcription
    current_state["multimodal_analysis"] = {"primary_emotion": "Processing...", "full_analysis": {}}
    
    # --- LOGIC FIX: Explicit Routing ---
    if "last_question" in current_state:
        current_state["conversation_history"].append(f"AI: {current_state['last_question']}")
    current_state["conversation_history"].append(f"Candidate: {transcription}")
    
    # A. Evaluate
    eval_out = evaluate_answer_node(current_state)
    current_state.update(eval_out)
    
    # B. Decide Next Step
    next_step = decide_next_step(current_state)
    
    if next_step == END:
        from ingest import save_interview_report
        candidate_name = current_state.get("initial_job_context", {}).get("candidate_name", "Unknown Candidate")
        save_interview_report(session_id, candidate_name, current_state["evaluations"])
        
        record.state_data = current_state
        db.commit()
        
        return {
            "status": "completed", 
            "report": current_state["evaluations"],
            "transcription": transcription
        }

    if current_state.get("next_action") == "drill_down":
        current_state["drill_down_count"] = current_state.get("drill_down_count", 0) + 1
        if current_state["drill_down_count"] >= 2:
            current_state["next_action"] = "switch"
            next_step = "rewrite"
            current_state["drill_down_count"] = 0
    else:
        current_state["drill_down_count"] = 0
        
    # C. Conditional Routing
    if next_step == "generate":
        pass 
    else:
        rewrite_out = rewrite_query_node(current_state)
        current_state.update(rewrite_out)
        
        retrieve_out = retrieve_node(current_state)
        current_state.update(retrieve_out)
    
    # D. Generate Question
    gen_out = generate_question_node(current_state)
    current_state.update(gen_out)
    
    record.state_data = current_state
    db.commit()
    
    # E. TTS & Return
    audio_path = generate_audio(gen_out["last_question"])
    audio_url = f"http://localhost:8000/static/audio/{os.path.basename(audio_path)}" if audio_path else None

    return {
        "status": "ongoing",
        "transcription": transcription,
        "next_question": gen_out["last_question"],
        "audio_url": audio_url,
        "feedback": eval_out["evaluations"][-1]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)