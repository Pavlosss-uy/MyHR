import uvicorn
import shutil
import os
import uuid
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from langgraph.graph import END 

# --- Custom Modules ---
from ingest import create_session_index, get_candidate_history, save_interview_report
from agent import app_graph, rewrite_query_node, retrieve_node, generate_question_node, evaluate_answer_node, decide_next_step
from services import transcribe_audio, generate_audio, generate_final_markdown_report
from tone import analyze_voice_tone
from vision import analyze_video_frame

# --- Configuration ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Simple in-memory session store
session_store = {}

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/start_interview")
async def start_interview(cv: UploadFile = File(...), jd: str = Form(...)):
    session_id = str(uuid.uuid4())
    logger.info(f"Starting session: {session_id}")
    
    cv_path = os.path.join(UPLOAD_DIR, f"{session_id}_{cv.filename}")
    with open(cv_path, "wb") as f:
        shutil.copyfileobj(cv.file, f)
        
    try:
        create_session_index(session_id, cv_path, jd)
    except Exception as e:
        logger.error(f"Ingestion Error: {e}")
    
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
            "cv_path": cv_path,
            "past_performance": "" 
        },
        "multimodal_analysis": {}
    }
    
    # Longitudinal Memory Check
    candidate_name = initial_state["initial_job_context"]["candidate_name"]
    try:
        candidate_history = get_candidate_history(candidate_name)
        if candidate_history:
            initial_state["initial_job_context"]["past_performance"] = candidate_history
            logger.info(f"Found history for {candidate_name}")
    except Exception as e:
        logger.warning(f"History fetch failed: {e}")
    
    # Start Agent
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
        
    # 1. Save Audio
    audio_path = os.path.join(UPLOAD_DIR, f"{session_id}_answer.wav")
    with open(audio_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)
        
    # 2. Transcribe (STT)
    transcription = transcribe_audio(audio_path)
    if not transcription: 
        transcription = "(No speech detected)"
    
    # 3. Analyze Tone
    try:
        dominant_tone, tone_report = analyze_voice_tone(audio_path)
    except Exception as e:
        logger.warning(f"Tone analysis failed: {e}")
        dominant_tone, tone_report = "Neutral", {}
        
    # 4. Vision Analysis (Safely Skipped for Audio)
    vision_result = {}
    if audio.filename.endswith(('.mp4', '.avi', '.mov')): # Only run if actual video
        try:
            vision_result = analyze_video_frame(audio_path) 
        except Exception as e:
            logger.warning(f"Vision analysis failed: {e}")

    # Update State
    current_state = session_store[session_id]
    
    if current_state.get("last_question"):
        current_state["conversation_history"].append(f"AI: {current_state['last_question']}")
    current_state["conversation_history"].append(f"Candidate: {transcription}")
    
    current_state["last_answer"] = transcription
    current_state["multimodal_analysis"] = {
        "primary_emotion": dominant_tone, 
        "full_analysis": tone_report,
        **vision_result
    }
    
    # 5. Agent Workflow
    eval_out = evaluate_answer_node(current_state)
    current_state.update(eval_out)
    
    next_step = decide_next_step(current_state)
    logger.info(f"Decision: {next_step} | Status: {current_state.get('next_action')}")
    
    # --- END OF INTERVIEW LOGIC ---
    if next_step == END:
        job_context = current_state.get("initial_job_context", {})
        
        # SAFE ACCESS to prevent KeyError
        c_name = job_context.get("candidate_name", "Candidate")
        j_desc = job_context.get("jd_text") or job_context.get("job_description") or "Job description not available."
        
        final_markdown = "Error generating report."
        try:
            logger.info("Generating Final Markdown Report...")
            final_markdown = generate_final_markdown_report(
                candidate_name=c_name,
                job_desc=j_desc,
                evaluations=current_state["evaluations"],
                tone_summary=current_state.get("multimodal_analysis", {})
            )
        except Exception as e:
            logger.error(f"Report Generation Failed: {e}")
            final_markdown = f"# Interview Complete\n\n**Note:** Automated report generation failed. \n\nError: {str(e)}"

        # Save to DB
        try:
            save_interview_report(session_id, c_name, current_state["evaluations"])
        except Exception as e:
            logger.error(f"Failed to save report to DB: {e}")
        
        return {
            "status": "completed", 
            "report": final_markdown,
            "transcription": transcription 
        }
        
    # C. Routing
    if next_step != "generate":
        # SWITCH Topic -> Rewrite & Retrieve
        rewrite_out = rewrite_query_node(current_state)
        current_state.update(rewrite_out)
        retrieve_out = retrieve_node(current_state)
        current_state.update(retrieve_out)
    
    # D. Generate Next Question
    gen_out = generate_question_node(current_state)
    current_state.update(gen_out)
    
    session_store[session_id] = current_state
    
    # E. TTS
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