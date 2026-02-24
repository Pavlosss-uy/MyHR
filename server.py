import uvicorn
import shutil
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.graph import END 

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
async def start_interview(cv: UploadFile = File(...), jd: str = Form(...)):
    session_id = str(uuid.uuid4())
    
    cv_path = os.path.join(UPLOAD_DIR, f"{session_id}_{cv.filename}")
    with open(cv_path, "wb") as f:
        shutil.copyfileobj(cv.file, f)
        
    try:
        create_session_index(session_id, cv_path, jd)
    except Exception as e:
        print(f"Ingestion Warning: {e}")
    
    # Initialize State
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
            "cv_path": cv_path
        },
        "multimodal_analysis": {}
    }
    
    result = app_graph.invoke(initial_state)
    session_store[session_id] = result
    
    question_text = result["last_question"]
    audio_path = generate_audio(question_text)
    audio_url = f"http://localhost:8000/static/audio/{os.path.basename(audio_path)}" if audio_path else None

    return {
        "session_id": session_id,
        "question": question_text,
        "audio_url": audio_url
    }

@app.post("/submit_answer")
async def submit_answer(session_id: str = Form(...), audio: UploadFile = File(...)):
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 1. Save & Transcribe
    audio_path = os.path.join(UPLOAD_DIR, f"{session_id}_answer.wav")
    with open(audio_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)
        
    transcription = transcribe_audio(audio_path)
    if not transcription: transcription = "(No speech detected)"
    
    # 2. Tone Analysis
    try:
        dominant_tone, tone_report = analyze_voice_tone(audio_path)
    except Exception:
        dominant_tone, tone_report = "Neutral", {}
    
    current_state = session_store[session_id]
    current_state["last_answer"] = transcription
    current_state["multimodal_analysis"] = {"primary_emotion": dominant_tone, "full_analysis": tone_report}
    
    # --- LOGIC FIX: Explicit Routing ---
    
    # A. Evaluate
    eval_out = evaluate_answer_node(current_state)
    current_state.update(eval_out)
    
    # B. Decide Next Step
    next_step = decide_next_step(current_state)
    print(f"🧠 Decision: {next_step} (Status: {current_state.get('next_action')})")
    
    if next_step == END:
        from ingest import save_interview_report
        save_interview_report(session_id, current_state["initial_job_context"]["candidate_name"], current_state["evaluations"])
        return {"status": "completed", "report": current_state["evaluations"]}
        
    # C. Conditional Routing (The Missing Link)
    if next_step == "generate":
        # DRILL DOWN: Skip retrieval entirely. 
        # The agent will use conversation history to ask a follow-up.
        print("⚡ Action: Drill Down (Skipping Retrieval)")
        pass 
    else:
        # SWITCH / CONTINUE: Find new context.
        # 1. Rewrite Query (Missing in your previous code)
        print("🔄 Action: Switching Topic (Rewriting & Retrieving)")
        rewrite_out = rewrite_query_node(current_state)
        current_state.update(rewrite_out)
        
        # 2. Retrieve
        retrieve_out = retrieve_node(current_state)
        current_state.update(retrieve_out)
    
    # D. Generate Question
    gen_out = generate_question_node(current_state)
    current_state.update(gen_out)
    
    session_store[session_id] = current_state
    
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