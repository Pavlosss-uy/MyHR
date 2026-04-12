import io
import json
import os
import re
import uuid
import tempfile
from typing import Tuple, Dict, Any

import PyPDF2
import uvicorn
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from langgraph.graph import END

from database import get_db, SessionRecord
from ingest import create_session_index, save_interview_report
from s3_utils import upload_file_to_s3
from models.registry import registry
from services import (
    transcribe_audio,
    transcribe_audio_bytes,
    generate_audio,
    generate_audio_stream,
)
from celery_worker import process_audio_tone_task
from tone import analyze_voice_tone
from agent import (
    app_graph,
    rewrite_query_node,
    retrieve_node,
    generate_question_node,
    evaluate_answer_node,
    decide_next_step,
    MAX_QUESTIONS,
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def extract_candidate_name(cv_text: str, filename: str) -> str:
    if cv_text:
        first_block = cv_text[:600].strip()

        label_match = re.search(
            r"(?i)(?:full\s+)?name\s*[:\-]\s*([A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+){1,2})",
            first_block,
        )
        if label_match:
            return label_match.group(1).strip()

        standalone = re.search(
            r"^([A-Z][a-zA-Z'\-]+(?:\s[A-Z][a-zA-Z'\-]+){1,2})\s*$",
            first_block,
            re.MULTILINE,
        )
        if standalone:
            candidate = standalone.group(1).strip()
            noise = {
                "curriculum", "vitae", "resume", "profile", "summary",
                "contact", "address", "objective", "education", "experience",
            }
            if candidate.split()[0].lower() not in noise:
                return candidate

    if filename:
        name = re.sub(r"\.[^.]+$", "", filename)
        name = re.sub(r"[_\-]+", " ", name)
        name = re.sub(
            r"\b(?:cv|resume|curriculum|vitae|application|candidate|profile)\b",
            "", name, flags=re.IGNORECASE,
        )
        name = " ".join(name.split()).strip()
        if len(name.split()) >= 2:
            return name.title()

    return "Candidate"


def _mime_to_ext(mime_type: str) -> str:
    base = (mime_type or "audio/webm").split(";")[0].strip().lower()
    return {
        "audio/webm": ".webm",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
    }.get(base, ".webm")


def _safe_remove(path: str | None):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _build_initial_state(
    session_id: str, candidate_name: str, jd: str, s3_cv_url: str, skill_score: float
) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "conversation_history": [],
        "current_topic": "Intro",
        "evaluations": [],
        "next_action": "continue",
        "loop_count": 0,
        "current_search_query": "",
        "initial_job_context": {
            "jd_text": jd,
            "job_title": jd.split("\n")[0] if jd else "Position",
            "candidate_name": candidate_name,
            "cv_url": s3_cv_url,
        },
        "multimodal_analysis": {},
        "facial_expression_data": {},
        "cv_chunk": "",
        "jd_chunk": "",
        "skill_match_score": skill_score,
        "question_number": 1,
        "asked_questions": [],
        "failed_topics": [],
        "consecutive_fails": 0,
        "current_difficulty": 3,
    }


def _attach_tone_analysis(current_state: Dict[str, Any], audio_path: str, session_id: str):
    try:
        dominant_tone, tone_report = analyze_voice_tone(audio_path)
        confidence = max(
            (
                float(v.rstrip("%")) / 100
                for v in tone_report.values()
                if isinstance(v, str) and v.endswith("%")
            ),
            default=0.5,
        )
        current_state["multimodal_analysis"] = {
            "primary_emotion": dominant_tone,
            "full_analysis": tone_report,
            "confidence": confidence,
        }
    except Exception as e:
        print(f"⚠️ Sync tone analysis failed: {e}")
        current_state["multimodal_analysis"] = {
            "primary_emotion": "neutral",
            "full_analysis": {},
            "confidence": 0.5,
        }

    try:
        process_audio_tone_task.delay(audio_path, session_id)
    except Exception as e:
        print(f"⚠️ Celery/Redis unavailable, skipping async tone persistence: {e}")


def _build_closing_message(current_state: Dict[str, Any]) -> str:
    """Generate a warm, contextual closing sentence spoken aloud at interview end."""
    evaluations = current_state.get("evaluations", [])
    name = current_state.get("initial_job_context", {}).get("candidate_name", "")
    first_name = name.split()[0] if name else "there"

    avg = (
        sum(e["score"] for e in evaluations) / len(evaluations)
        if evaluations else 0
    )

    if avg >= 75:
        return (
            f"That was a great session, {first_name}. "
            "You demonstrated strong technical knowledge across the topics we covered. "
            "We will review your responses and be in touch very soon. "
            "Thank you so much for your time today — best of luck!"
        )
    elif avg >= 50:
        return (
            f"Thanks for your time today, {first_name}. "
            "You showed solid understanding in several areas, and we have a good picture of your background now. "
            "We will be reviewing everything carefully and will reach out with next steps. "
            "Take care!"
        )
    else:
        return (
            f"Thank you for coming in today, {first_name}. "
            "We appreciate your honesty and effort throughout the session. "
            "We will be in touch after reviewing all candidates. "
            "All the best!"
        )


def _run_interview_turn(
    current_state: Dict[str, Any], transcription: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    current_state["last_answer"] = transcription

    # Append history — AI question first, then candidate answer
    if current_state.get("last_question"):
        current_state["conversation_history"].append(f"AI: {current_state['last_question']}")
    current_state["conversation_history"].append(f"Candidate: {transcription}")

    eval_out = evaluate_answer_node(current_state)
    current_state.update(eval_out)

    next_step = decide_next_step(current_state)
    if next_step == END:
        closing = _build_closing_message(current_state)
        return current_state, {"status": "completed", "closing_message": closing}

    if current_state.get("next_action") == "drill_down":
        current_state["consecutive_fails"] = current_state.get("consecutive_fails", 0) + 1
        if current_state["consecutive_fails"] >= 2:
            failed_topic = current_state.get("current_topic", "unknown topic")
            current_state["failed_topics"] = current_state.get("failed_topics", []) + [failed_topic]
            current_state["next_action"] = "switch"
            current_state["consecutive_fails"] = 0
            next_step = "rewrite"
    else:
        current_state["consecutive_fails"] = 0

    if next_step != "generate":
        current_state.update(rewrite_query_node(current_state))
        current_state.update(retrieve_node(current_state))

    gen_out = generate_question_node(current_state)
    current_state.update(gen_out)

    return current_state, {
        "status": "ongoing",
        "next_question": gen_out["last_question"],
        "feedback": eval_out["evaluations"][-1],
        "question_number": current_state.get("question_number", 2),
        "max_questions": MAX_QUESTIONS,
    }


@app.post("/start_interview")
async def start_interview(
    cv: UploadFile = File(...),
    jd: str = Form(...),
    db: Session = Depends(get_db),
):
    session_id = str(uuid.uuid4())

    cv_bytes = await cv.read()
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(cv_bytes))
    cv_text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            cv_text += extracted + "\n"

    await cv.seek(0)
    s3_cv_url = upload_file_to_s3(cv, prefix=f"cvs/{session_id}")

    candidate_name_early = extract_candidate_name(cv_text, cv.filename)
    job_title_early = jd.split("\n")[0].strip() if jd else "Position"
    try:
        create_session_index(session_id, cv_text, jd, candidate_name=candidate_name_early, role=job_title_early)
    except Exception as e:
        print(f"Ingestion Warning: {e}")

    try:
        skill_matcher = registry.load_skill_matcher()
        skill_score = skill_matcher.calculate_match_score(cv_text, jd)
        if isinstance(skill_score, (int, float)):
            skill_score = float(skill_score)
            skill_score = skill_score if skill_score <= 1.0 else skill_score / 100.0
        else:
            skill_score = 0.5
    except Exception as e:
        print(f"Skill Match Warning: {e}")
        skill_score = 0.5

    candidate_name = extract_candidate_name(cv_text, cv.filename)
    initial_state = _build_initial_state(session_id, candidate_name, jd, s3_cv_url, skill_score)

    result = app_graph.invoke(initial_state)

    # The graph increments question_number once during generation of Q1.
    # Reset it to 1 so the first submit correctly returns Q2, second Q3, etc.
    result["question_number"] = 1

    # Do NOT append the first AI question to history here — _run_interview_turn does it
    # on the first submit so we avoid duplicating it.
    db_record = SessionRecord(session_id=session_id, state_data=result)
    db.add(db_record)
    db.commit()

    job_title = initial_state["initial_job_context"]["job_title"]
    first_question = result["last_question"]
    greeting = (
        f"Hello {candidate_name}! Welcome to your AI interview for the {job_title} position. "
        f"I'm your interviewer today. We'll go through a series of questions — just speak naturally and take your time. "
        f"Let's get started!\n\n{first_question}"
    )

    audio_path = generate_audio(greeting)
    audio_url = f"http://localhost:8000/static/audio/{os.path.basename(audio_path)}" if audio_path else None

    return {
        "session_id": session_id,
        "question": greeting,
        "audio_url": audio_url,
        "question_number": 1,
        "ws_url": f"ws://localhost:8000/ws/interview/{session_id}",
    }


@app.websocket("/ws/interview/{session_id}")
async def live_interview_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db),
):
    """
    Utterance-based WebSocket protocol.

    Frontend flow:
      1) Send {"type": "start_utterance", "mime_type": "audio/webm"}
      2) Send binary audio chunks while the user speaks
      3) Send {"type": "end_utterance"} when the user stops

    Server responses:
      {"type": "ready"}                          — session confirmed, ready for first utterance
      {"type": "status", "message": "listening"} — utterance window opened
      {"type": "transcript", "text": "..."}      — what the candidate said
      {"type": "ai_response_text", "text": "..."}— next interviewer question
      {"type": "audio_stream_start", ...}        — raw PCM stream starting
      (binary frames)                            — PCM audio chunks
      {"type": "audio_stream_complete"}          — PCM stream done
      {"type": "retry", "message": "..."}        — no audio or no speech, try again
      {"type": "end_interview", "report": [...]} — interview finished
      {"type": "error", "message": "..."}        — something went wrong
    """
    await websocket.accept()

    record = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if not record:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close(code=1008)
        return

    audio_buffer = bytearray()
    mime_type = "audio/webm"

    await websocket.send_json({"type": "ready", "session_id": session_id})

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect()

            if message.get("bytes") is not None:
                audio_buffer.extend(message["bytes"])
                continue

            if message.get("text") is None:
                continue

            try:
                payload = json.loads(message["text"])
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON message"})
                continue

            event_type = payload.get("type")

            if event_type == "start_utterance":
                audio_buffer.clear()
                mime_type = payload.get("mime_type", "audio/webm")
                await websocket.send_json({"type": "status", "message": "listening"})
                continue

            if event_type != "end_utterance":
                await websocket.send_json({"type": "error", "message": f"Unknown event type: {event_type}"})
                continue

            # --- Process the completed utterance ---
            if not audio_buffer:
                await websocket.send_json({"type": "retry", "message": "No audio received. Please answer again."})
                continue

            current_state = record.state_data
            temp_path = None

            try:
                transcription = transcribe_audio_bytes(bytes(audio_buffer), content_type=mime_type)

                # Write a temp file only for tone analysis compatibility
                suffix = _mime_to_ext(mime_type)
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_DIR) as tmp:
                    tmp.write(audio_buffer)
                    temp_path = tmp.name

                if not transcription or not transcription.strip():
                    _safe_remove(temp_path)
                    await websocket.send_json({"type": "retry", "message": "I didn't catch that. Please answer again."})
                    audio_buffer.clear()
                    continue

                _attach_tone_analysis(current_state, temp_path, session_id)

                await websocket.send_json({"type": "transcript", "text": transcription})

                current_state, outcome = _run_interview_turn(current_state, transcription)

                record.state_data = current_state
                flag_modified(record, "state_data")
                db.commit()

                if outcome["status"] == "completed":
                    closing = outcome.get("closing_message", "Thank you for your time today. Goodbye!")
                    candidate_name = current_state.get("initial_job_context", {}).get("candidate_name", "Unknown Candidate")
                    save_interview_report(session_id, candidate_name, current_state["evaluations"])

                    await websocket.send_json({"type": "ai_response_text", "text": closing})
                    await websocket.send_json(
                        {"type": "audio_stream_start", "format": "linear16", "sample_rate": 16000, "channels": 1}
                    )
                    async for audio_chunk in generate_audio_stream(closing):
                        await websocket.send_bytes(audio_chunk)
                    await websocket.send_json({"type": "audio_stream_complete"})

                    await websocket.send_json(
                        {
                            "type": "end_interview",
                            "message": closing,
                            "report": current_state["evaluations"],
                            "transcription": transcription,
                        }
                    )
                    break

                next_question = outcome["next_question"]
                await websocket.send_json({"type": "ai_response_text", "text": next_question})
                await websocket.send_json(
                    {
                        "type": "audio_stream_start",
                        "format": "linear16",
                        "sample_rate": 16000,
                        "channels": 1,
                    }
                )

                async for audio_chunk in generate_audio_stream(next_question):
                    await websocket.send_bytes(audio_chunk)

                await websocket.send_json({"type": "audio_stream_complete"})
                audio_buffer.clear()

            except Exception as e:
                print(f"⚠️ WebSocket interview turn failed: {e}")
                await websocket.send_json({"type": "error", "message": "Failed to process utterance"})
            finally:
                _safe_remove(temp_path)

    except WebSocketDisconnect:
        print(f"Client {session_id} disconnected.")


MIN_REPORT_QUESTIONS = 2  # need at least this many answered questions for a valid report


@app.get("/end_interview/{session_id}")
def end_interview(session_id: str, db: Session = Depends(get_db)):
    """
    Called when the user clicks 'End Interview' early OR when the frontend needs
    the report for an already-completed session.
    Returns status='incomplete' when fewer than MIN_REPORT_QUESTIONS were answered.
    """
    record = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    current_state = record.state_data
    evaluations = current_state.get("evaluations", [])
    job_ctx = current_state.get("initial_job_context", {})
    candidate_name = job_ctx.get("candidate_name", "Candidate")
    job_title = job_ctx.get("job_title", "Interview")

    # Guard: refuse to generate a report for an effectively empty session
    if len(evaluations) < MIN_REPORT_QUESTIONS:
        return {
            "session_id": session_id,
            "status": "incomplete",
            "message": (
                f"The interview ended too early. "
                f"Answer at least {MIN_REPORT_QUESTIONS} questions to generate a full report."
            ),
            "evaluations": [],
            "average_score": 0,
            "total_questions": len(evaluations),
            "job_title": job_title,
            "candidate_name": candidate_name,
        }

    # Persist report to storage (idempotent — safe to call multiple times)
    try:
        save_interview_report(session_id, candidate_name, evaluations)
    except Exception as e:
        print(f"⚠️ Report save warning: {e}")

    avg_score = round(sum(e["score"] for e in evaluations) / len(evaluations), 1)

    return {
        "session_id": session_id,
        "status": "complete",
        "evaluations": evaluations,
        "average_score": avg_score,
        "total_questions": len(evaluations),
        "job_title": job_title,
        "candidate_name": candidate_name,
    }


@app.post("/submit_answer")
async def submit_answer(
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    record = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    current_state = record.state_data

    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    ext = _mime_to_ext(content_type)
    temp_audio_path = os.path.join(UPLOAD_DIR, f"temp_{session_id}{ext}")

    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)

    await audio.seek(0)
    try:
        upload_file_to_s3(audio, prefix=f"answers/{session_id}")
    except Exception as e:
        print(f"S3 upload warning: {e}")

    transcription = transcribe_audio(temp_audio_path, content_type=content_type)

    if not transcription or not transcription.strip():
        _safe_remove(temp_audio_path)
        return {
            "status": "retry",
            "transcription": "",
            "message": "I didn't catch that. Please answer again.",
            "question_number": current_state.get("question_number", 1),
            "max_questions": MAX_QUESTIONS,
        }

    _attach_tone_analysis(current_state, temp_audio_path, session_id)

    try:
        current_state, outcome = _run_interview_turn(current_state, transcription)

        record.state_data = current_state
        flag_modified(record, "state_data")   # force SQLAlchemy to detect JSON changes
        db.commit()

        if outcome["status"] == "completed":
            closing = outcome.get("closing_message", "Thank you for your time today. Goodbye!")
            candidate_name = current_state.get("initial_job_context", {}).get("candidate_name", "Unknown Candidate")
            save_interview_report(session_id, candidate_name, current_state["evaluations"])

            closing_audio_path = generate_audio(closing)
            closing_audio_url = (
                f"http://localhost:8000/static/audio/{os.path.basename(closing_audio_path)}"
                if closing_audio_path else None
            )
            return {
                "status": "completed",
                "closing_message": closing,
                "closing_audio_url": closing_audio_url,
                "report": current_state["evaluations"],
                "transcription": transcription,
            }

        audio_path = generate_audio(outcome["next_question"])
        audio_url = f"http://localhost:8000/static/audio/{os.path.basename(audio_path)}" if audio_path else None

        return {
            "status": "ongoing",
            "transcription": transcription,
            "next_question": outcome["next_question"],
            "audio_url": audio_url,
            "feedback": outcome["feedback"],
            "question_number": outcome["question_number"],
            "max_questions": outcome["max_questions"],
        }
    finally:
        _safe_remove(temp_audio_path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
