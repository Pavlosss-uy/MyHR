import asyncio
import io
import json
import logging
import os
import re
import time as _time
import uuid
import tempfile
from contextlib import asynccontextmanager
from typing import Tuple, Dict, Any

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_SERVER_START_TIME = _time.monotonic()

import PyPDF2
import uvicorn
from fastapi import (
    FastAPI,
    Request,
    UploadFile,
    File,
    Form,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Body,
    Depends,
    Header,
)
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.graph import END

from firestore_client import create_session, get_session, update_session_state
from ingest import create_session_index, save_interview_report, save_rich_report
from s3_utils import upload_file_to_s3
from models.registry import registry
from services import (
    transcribe_audio,
    transcribe_audio_bytes,
    generate_audio,
    generate_audio_stream,
)
from tone import analyze_voice_tone
from agent import (
    app_graph,
    rewrite_query_node,
    retrieve_node,
    generate_question_node,
    evaluate_answer_node,
    decide_next_step,
    synthesize_report,
    MAX_QUESTIONS,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize heavy models once so imports stay fast.
    try:
        from ingest import init_embedder
        await asyncio.to_thread(init_embedder)
        logger.info("LlamaIndex embedder (all-mpnet-base-v2) initialized.")
    except Exception as e:
        logger.warning("Embedder init skipped: %s", e)
    try:
        from models import proctor
        proctor.warmup()
    except Exception as e:
        logger.warning("Proctor warmup skipped: %s", e)
    try:
        from models.registry import registry as _reg
        _reg.load_emotion_model()
    except Exception as e:
        logger.warning("Emotion model pre-load skipped: %s", e)
    yield
    # Shutdown: nothing to clean up currently.


app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------------------------
# Task 3.2 — Rate limiting: prevent API abuse per IP address
# ---------------------------------------------------------------------------
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# Task 3.1 — CORS: allow only the configured frontend origin (not "*")
# Set FRONTEND_URL in .env for production, e.g. https://myhr.example.com
# ---------------------------------------------------------------------------
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# B2B / HR endpoints
try:
    from hr_routes import hr_router
    app.include_router(hr_router)
except ImportError as _hr_err:
    logger.warning("HR routes not loaded (missing dependencies): %s", _hr_err)

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Task 3.3 — environment-driven base URLs (replaces hardcoded localhost:8000)
BASE_URL    = os.environ.get("BASE_URL",    "http://localhost:8000")
BASE_WS_URL = os.environ.get("BASE_WS_URL", "ws://localhost:8000")

# Task 3.4 — upload size limits (413 on excess)
_CV_MAX_BYTES    = 10 * 1024 * 1024   # 10 MB
_AUDIO_MAX_BYTES = 50 * 1024 * 1024   # 50 MB


# Task 3.2 — Firebase token verification dependency
async def verify_firebase_token(authorization: str = Header(None)) -> str:
    """Verify a Firebase Bearer token; return the caller's UID on success.

    Task 6.3 — when TESTING=true, skip Firebase entirely and return a stub uid so
    the integration suite can exercise authed endpoints without real credentials.
    """
    if os.getenv("TESTING") == "true":
        return "test-uid"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(token, clock_skew_seconds=30)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired Firebase ID token.")


def _extract_jd_signals(jd_text: str) -> str:
    """
    Extract a concise, structured summary of key JD signals for use in interview prompts.
    Avoids injecting verbose JD paragraphs that cause long, unnatural questions.
    """
    if not jd_text or not jd_text.strip():
        return "No JD provided."

    lines = [l.strip() for l in jd_text.split("\n") if l.strip()]
    if not lines:
        return "No JD provided."

    role_line = lines[0]

    # Collect bullet-point lines as skill/requirement signals (max 10)
    skill_lines = []
    for line in lines[1:]:
        # Strip common bullet markers
        clean = re.sub(r"^[-•*·✓▪]\s*", "", line).strip()
        # Keep lines that look like a skill/requirement: short and meaningful
        if 8 < len(clean) < 120 and not clean.endswith(":"):
            skill_lines.append(clean)
        if len(skill_lines) >= 10:
            break

    if skill_lines:
        return (
            f"Role: {role_line}\n"
            "Key Requirements:\n"
            + "\n".join(f"- {s}" for s in skill_lines)
        )

    # Fallback: first 350 chars of the JD if no bullet points detected
    flat = " ".join(lines)
    return f"Role: {role_line}\nContext: {flat[:350]}"


def _is_valid_cv(text: str) -> bool:
    """Rule-based CV/resume content validation."""
    if not text or len(text.strip()) < 100:
        return False

    text_lower = text.lower()

    cv_sections = [
        "education", "experience", "work experience", "employment history",
        "professional experience", "skills", "objective", "summary", "profile",
        "contact", "references", "certifications", "achievements", "projects",
        "internship", "volunteer", "languages", "awards",
    ]
    section_hits = sum(1 for kw in cv_sections if kw in text_lower)

    # Documents that are clearly NOT a CV
    negative_keywords = [
        "invoice", "purchase order", "receipt", "payment due", "tax return",
        "table of contents", "bibliography", "dear sir", "dear madam",
        "sincerely yours", "to whom it may concern", "chapter ",
    ]
    negative_hits = sum(1 for kw in negative_keywords if kw in text_lower)
    if negative_hits >= 2:
        return False

    # Year-range patterns common in CVs (e.g. 2018–2022, 2020 - present)
    date_hits = len(re.findall(r'\b(19|20)\d{2}\b', text))

    # Pass if at least 2 recognisable CV sections OR high combined signal
    return section_hits >= 2 or (section_hits >= 1 and date_hits >= 2)


def _is_valid_jd(text: str) -> bool:
    """Rule-based Job Description content validation."""
    if not text or len(text.strip()) < 50:
        return False

    text_lower = text.lower()

    jd_keywords = [
        "responsibilities", "requirements", "qualifications", "skills",
        "experience", "role", "position", "candidate", "apply",
        "preferred", "must have", "required", "team", "company",
        "full-time", "part-time", "salary", "benefits",
        "we are looking", "we're looking", "join our", "opportunity",
        "degree", "bachelor", "master", "years of experience",
        "proficiency", "knowledge of", "ability to", "strong understanding",
    ]
    hits = sum(1 for kw in jd_keywords if kw in text_lower)

    negative_keywords = [
        "invoice", "receipt", "chapter ", "bibliography",
        "dear sir", "dear madam", "sincerely",
    ]
    negative_hits = sum(1 for kw in negative_keywords if kw in text_lower)
    if negative_hits >= 2:
        return False

    return hits >= 3


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


def _cleanup_session_vectors(session_id: str):
    """Delete this session's Pinecone namespace once the interview is over.

    Each interview indexes CV/JD vectors under namespace=session_id. Pinecone's
    free tier caps total namespaces (100) — without this the system fails after
    ~100 interviews and old candidates' vectors leak forever. Safe + idempotent:
    deleting a missing namespace is a no-op. The interview is finished, so the
    retriever is no longer needed.
    """
    try:
        from ingest import pinecone_index
        pinecone_index.delete(delete_all=True, namespace=session_id)
        logger.info("Cleaned Pinecone namespace for %s", session_id)
    except Exception as e:
        logger.warning("Pinecone namespace cleanup failed for %s: %s", session_id, e)


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
        "initial_job_context": {
            "jd_text": jd,
            "job_title": jd.split("\n")[0].strip() if jd else "Position",
            "jd_signals": _extract_jd_signals(jd),
            "candidate_name": candidate_name,
            "cv_url": s3_cv_url,
        },
        "multimodal_analysis": {},
        "facial_expression_data": {},
        "proctoring_data": {},
        "proctoring_history": [],
        "cv_chunk": "",
        "jd_chunk": "",
        "skill_match_score": skill_score,
        "question_number": 1,
        "asked_questions": [],
        "failed_topics": [],
        "consecutive_fails": 0,
        "current_difficulty": 3,
        "interview_mode": "first_question",
        "current_search_query": "candidate main technical skills and experience",
    }


def _attach_tone_analysis(current_state: Dict[str, Any], audio_path: str, session_id: str):
    """
    Run emotion/tone analysis synchronously and store the result in current_state.
    Never skips — always produces a valid multimodal_analysis entry.
    Celery/Redis dependency removed: analysis runs in-process, no external services needed.
    """
    # analyze_voice_tone guarantees a return value — it never raises
    dominant_tone, tone_report = analyze_voice_tone(audio_path)

    # Derive confidence from the highest probability in the tone report
    try:
        confidence = max(
            (float(v.rstrip("%")) / 100 for v in tone_report.values()
             if isinstance(v, str) and v.endswith("%") and not v.startswith("_")),
            default=0.5,
        )
    except Exception:
        confidence = 0.5

    current_state["multimodal_analysis"] = {
        "primary_emotion": dominant_tone,
        "full_analysis": tone_report,
        "confidence": confidence,
    }
    logger.debug("[EMOTION OUTPUT] session=%s tone=%s confidence=%.2f", session_id, dominant_tone, confidence)


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

    # Determine answer classification for routing decisions
    last_evals = current_state.get("evaluations", [])
    last_classification = last_evals[-1].get("answer_classification", "WEAK") if last_evals else "WEAK"

    if current_state.get("next_action") == "drill_down":
        if last_classification == "OFF_TOPIC":
            # Off-topic is intentional, not a knowledge gap — do NOT enter fallback mode.
            # Redirect to a fresh topic instead of asking a simpler version of the same question.
            current_state["next_action"] = "switch"
            current_state["consecutive_fails"] = 0
            current_state["interview_mode"] = "normal"
        else:
            # I_DONT_KNOW or WEAK — trigger fallback (simpler question on same topic)
            current_state["consecutive_fails"] = current_state.get("consecutive_fails", 0) + 1
            current_state["interview_mode"] = "fallback"
            if current_state["consecutive_fails"] >= 2:
                failed_topic = current_state.get("current_topic", "unknown topic")
                current_state["failed_topics"] = current_state.get("failed_topics", []) + [failed_topic]
                current_state["next_action"] = "switch"
                current_state["consecutive_fails"] = 0
                current_state["interview_mode"] = "normal"
                next_step = "rewrite"
    else:
        current_state["consecutive_fails"] = 0
        current_state["interview_mode"] = "normal"

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
@limiter.limit("10/minute")
async def start_interview(
    request: Request,
    cv: UploadFile = File(...),
    jd: str = Form(...),
    uid: str = Depends(verify_firebase_token),
):
    session_id = str(uuid.uuid4())

    cv_bytes = await cv.read()
    if len(cv_bytes) > _CV_MAX_BYTES:
        raise HTTPException(status_code=413, detail="CV file too large. Maximum allowed size is 10 MB.")
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(cv_bytes))
    cv_text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            cv_text += extracted + "\n"

    if not _is_valid_cv(cv_text):
        raise HTTPException(
            status_code=422,
            detail="Invalid CV uploaded. Please upload a valid resume.",
        )

    if not _is_valid_jd(jd):
        raise HTTPException(
            status_code=422,
            detail="Invalid Job Description. Please provide a proper job description.",
        )

    await cv.seek(0)
    s3_cv_url = upload_file_to_s3(cv, prefix=f"cvs/{session_id}")

    candidate_name_early = extract_candidate_name(cv_text, cv.filename)
    job_title_early = jd.split("\n")[0].strip() if jd else "Position"
    try:
        create_session_index(session_id, cv_text, jd, candidate_name=candidate_name_early, role=job_title_early)
    except Exception as e:
        logger.warning("Ingestion warning: %s", e)

    try:
        skill_matcher = registry.load_skill_matcher()
        skill_score = skill_matcher.calculate_match_score(cv_text, jd)
        if isinstance(skill_score, (int, float)):
            skill_score = float(skill_score)
            skill_score = skill_score if skill_score <= 1.0 else skill_score / 100.0
        else:
            skill_score = 0.5
    except Exception as e:
        logger.warning("Skill match warning: %s", e)
        skill_score = 0.5

    candidate_name = extract_candidate_name(cv_text, cv.filename)
    initial_state = _build_initial_state(session_id, candidate_name, jd, s3_cv_url, skill_score)

    result = app_graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": session_id}},
    )

    # The graph increments question_number once during generation of Q1.
    # Reset it to 1 so the first submit correctly returns Q2, second Q3, etc.
    result["question_number"] = 1

    # Do NOT append the first AI question to history here — _run_interview_turn does it
    # on the first submit so we avoid duplicating it.
    create_session(session_id, result)

    job_title = initial_state["initial_job_context"]["job_title"]
    first_question = result["last_question"]
    greeting = (
        f"Hi {candidate_name}, welcome to your {job_title} interview — take your time and speak naturally.\n\n"
        f"{first_question}"
    )

    audio_path = generate_audio(greeting)
    audio_url = f"{BASE_URL}/static/audio/{os.path.basename(audio_path)}" if audio_path else None

    return {
        "session_id": session_id,
        "question": greeting,
        "audio_url": audio_url,
        "question_number": 1,
        "ws_url": f"{BASE_WS_URL}/ws/interview/{session_id}",
    }


@app.post("/candidate-interview/{token}/start")
async def start_interview_from_token(
    token: str,
):
    """
    Start an AI interview session for a candidate using their invitation token.
    Fetches the candidate's stored CV text and job description from Firestore —
    no file upload required.  Uses the same session infrastructure as /start_interview.
    """
    from hr_routes import get_interview_context_for_token

    ctx = get_interview_context_for_token(token)  # raises HTTPException on bad token

    cv_text = ctx["cv_text"]
    jd = ctx["jd"]
    candidate_name = ctx["candidate_name"]

    if not cv_text or len(cv_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Candidate CV not found or too short to conduct interview.")
    if not jd or len(jd.strip()) < 50:
        raise HTTPException(status_code=422, detail="Job description not found.")

    session_id = str(uuid.uuid4())

    try:
        create_session_index(session_id, cv_text, jd, candidate_name=candidate_name, role=ctx["job_title"])
    except Exception as e:
        logger.warning("Ingestion warning: %s", e)

    try:
        skill_matcher = registry.load_skill_matcher()
        skill_score = skill_matcher.calculate_match_score(cv_text, jd)
        if isinstance(skill_score, (int, float)):
            skill_score = float(skill_score)
            skill_score = skill_score if skill_score <= 1.0 else skill_score / 100.0
        else:
            skill_score = 0.5
    except Exception as e:
        logger.warning("Skill match warning: %s", e)
        skill_score = 0.5

    initial_state = _build_initial_state(session_id, candidate_name, jd, "", skill_score)
    result = app_graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": session_id}},
    )
    result["question_number"] = 1

    create_session(session_id, result)

    job_title = ctx["job_title"]
    first_question = result["last_question"]
    greeting = (
        f"Hi {candidate_name}, welcome to your {job_title} interview — take your time and speak naturally.\n\n"
        f"{first_question}"
    )

    audio_path = generate_audio(greeting)
    audio_url = f"{BASE_URL}/static/audio/{os.path.basename(audio_path)}" if audio_path else None

    return {
        "session_id": session_id,
        "question": greeting,
        "audio_url": audio_url,
        "max_questions": MAX_QUESTIONS,
    }


@app.websocket("/ws/interview/{session_id}")
async def live_interview_websocket(
    websocket: WebSocket,
    session_id: str,
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

    record = get_session(session_id)
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

            current_state = record["state_data"]
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

                current_state, outcome = await asyncio.to_thread(_run_interview_turn, current_state, transcription)

                update_session_state(session_id, current_state)
                record["state_data"] = current_state

                if outcome["status"] == "completed":
                    closing = outcome.get("closing_message", "Thank you for your time today. Goodbye!")
                    candidate_name = current_state.get("initial_job_context", {}).get("candidate_name", "Unknown Candidate")
                    job_title_ws = current_state.get("initial_job_context", {}).get("job_title", "Interview")
                    save_interview_report(session_id, candidate_name, current_state["evaluations"])

                    # Single-report guarantee: generate once, save once, never regenerate
                    import json as _json_ws
                    _ws_report_path = os.path.join("storage", "reports", f"{session_id}_rich_report.json")
                    rich_report_ws = {}
                    if os.path.exists(_ws_report_path):
                        try:
                            with open(_ws_report_path, "r", encoding="utf-8") as _f:
                                rich_report_ws = _json_ws.load(_f)
                        except Exception:
                            pass
                    if not rich_report_ws:
                        try:
                            rich_report_ws = synthesize_report(current_state, candidate_name, job_title_ws)
                            if rich_report_ws:
                                save_rich_report(session_id, rich_report_ws)
                        except Exception as _e:
                            logger.warning("WS report synthesis warning: %s", _e)

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
                            "rich_report": rich_report_ws,
                            "transcription": transcription,
                        }
                    )
                    _cleanup_session_vectors(session_id)  # interview done — free the Pinecone namespace
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
                logger.error("WebSocket interview turn failed: %s", e)
                await websocket.send_json({"type": "error", "message": "Failed to process utterance"})
            finally:
                _safe_remove(temp_path)

    except WebSocketDisconnect:
        logger.info("Client %s disconnected.", session_id)


MIN_REPORT_QUESTIONS = 2  # need at least this many answered questions for a valid report


@app.get("/end_interview/{session_id}")
async def end_interview(session_id: str):
    """
    Called when the user clicks 'End Interview' early OR when the frontend needs
    the report for an already-completed session.
    Returns status='incomplete' when fewer than MIN_REPORT_QUESTIONS were answered.
    """
    record = get_session(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    current_state = record["state_data"]
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
        logger.warning("Report save warning: %s", e)

    avg_score = round(sum(e["score"] for e in evaluations) / len(evaluations), 1)

    # --- Single-report guarantee ---
    # Load from disk if already generated (idempotent: same object every time).
    # Only call synthesize_report once — on first completion. Never regenerate.
    import json as _json
    _rich_report_path = os.path.join("storage", "reports", f"{session_id}_rich_report.json")
    rich_report = {}
    if os.path.exists(_rich_report_path):
        try:
            with open(_rich_report_path, "r", encoding="utf-8") as _f:
                rich_report = _json.load(_f)
            logger.debug("Loaded existing rich report for %s", session_id)
        except Exception as _e:
            logger.warning("Rich report load warning: %s", _e)

    if not rich_report:
        try:
            rich_report = synthesize_report(current_state, candidate_name, job_title)
            if rich_report:
                save_rich_report(session_id, rich_report)
        except Exception as e:
            logger.warning("Report synthesis warning: %s", e)

    # Interview is over (incl. early end) — free the Pinecone namespace. Idempotent.
    _cleanup_session_vectors(session_id)

    return {
        "session_id": session_id,
        "status": "complete",
        "evaluations": evaluations,
        "average_score": avg_score,
        "total_questions": len(evaluations),
        "job_title": job_title,
        "candidate_name": candidate_name,
        "rich_report": rich_report,
    }


@app.post("/analyze_frame")
@limiter.limit("60/minute")
async def analyze_frame(
    request: Request,
    frame: str = Form(...),
    uid: str = Depends(verify_firebase_token),
):
    """Proctoring — integrity signals for one video frame (OpenCV, no TensorFlow).

    Returns face_count, face_present, multiple_faces, looking_away. Detection runs
    in a worker thread so the FastAPI event loop is never stalled.
    """
    import base64
    import numpy as np
    import cv2
    from models import proctor

    try:
        img_bytes = base64.b64decode(frame)
        nparr     = np.frombuffer(img_bytes, np.uint8)
        img       = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return proctor._empty_result(0.0)

    # Offload the CPU-bound detection — do NOT block the event loop.
    result = await asyncio.to_thread(proctor.analyze, img)

    # Log significant proctoring signals
    if result.get("multiple_faces"):
        logger.warning("[PROCTOR] multiple faces detected: %s", result.get("face_count"))
    elif not result.get("face_present"):
        logger.warning("[PROCTOR] no face in frame")
    elif result.get("looking_away"):
        gaze_info = f"gaze={result.get('gaze_score', 0):.2f}"
        if result.get("iris_offset") is not None:
            gaze_info += f" iris={result.get('iris_offset'):.2f}"
        logger.warning("[PROCTOR] looking away (%s)", gaze_info)

    return result


@app.post("/submit_answer")
@limiter.limit("30/minute")
async def submit_answer(
    request: Request,
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    face_emotion: str = Form(None),
    integrity: str = Form(None),
):
    record = get_session(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    current_state = record["state_data"]

    audio_bytes = await audio.read()
    if len(audio_bytes) > _AUDIO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large. Maximum allowed size is 50 MB.")
    content_type = audio.content_type or "audio/webm"
    ext = _mime_to_ext(content_type)
    temp_audio_path = os.path.join(UPLOAD_DIR, f"temp_{session_id}{ext}")

    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)

    await audio.seek(0)
    try:
        upload_file_to_s3(audio, prefix=f"answers/{session_id}")
    except Exception as e:
        logger.warning("S3 upload warning: %s", e)

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

    # Task 5.3 — store facial emotion from the client frame snapshot
    if face_emotion:
        try:
            import json as _json
            current_state["facial_expression_data"] = _json.loads(face_emotion)
        except Exception:
            pass  # malformed JSON — leave existing state as-is

    # Proctoring — store per-answer integrity aggregate (out-of-frame / multi-face / looking-away)
    if integrity:
        try:
            import json as _json
            parsed_integrity = _json.loads(integrity)
            current_state["proctoring_data"] = parsed_integrity
            
            # Cumulative session log
            if "proctoring_history" not in current_state:
                current_state["proctoring_history"] = []
            
            # Add metadata to track which question this belongs to
            q_num = current_state.get("question_number", 1)
            parsed_integrity["question_number"] = q_num
            current_state["proctoring_history"].append(parsed_integrity)
        except Exception:
            pass  # malformed JSON — leave existing state as-is

    try:
        current_state, outcome = await asyncio.to_thread(_run_interview_turn, current_state, transcription)

        update_session_state(session_id, current_state)

        if outcome["status"] == "completed":
            closing = outcome.get("closing_message", "Thank you for your time today. Goodbye!")
            candidate_name = current_state.get("initial_job_context", {}).get("candidate_name", "Unknown Candidate")
            job_title_sa = current_state.get("initial_job_context", {}).get("job_title", "Interview")
            save_interview_report(session_id, candidate_name, current_state["evaluations"])

            # Single-report guarantee: generate once, save once, never regenerate
            import json as _json_sa
            _sa_report_path = os.path.join("storage", "reports", f"{session_id}_rich_report.json")
            rich_report_sa = {}
            if os.path.exists(_sa_report_path):
                try:
                    with open(_sa_report_path, "r", encoding="utf-8") as _f:
                        rich_report_sa = _json_sa.load(_f)
                except Exception:
                    pass
            if not rich_report_sa:
                try:
                    rich_report_sa = synthesize_report(current_state, candidate_name, job_title_sa)
                    if rich_report_sa:
                        save_rich_report(session_id, rich_report_sa)
                except Exception as _e:
                    logger.warning("submit_answer report synthesis warning: %s", _e)

            closing_audio_path = generate_audio(closing)
            closing_audio_url = (
                f"{BASE_URL}/static/audio/{os.path.basename(closing_audio_path)}"
                if closing_audio_path else None
            )
            _cleanup_session_vectors(session_id)  # interview done — free the Pinecone namespace
            return {
                "status": "completed",
                "closing_message": closing,
                "closing_audio_url": closing_audio_url,
                "report": current_state["evaluations"],
                "rich_report": rich_report_sa,
                "transcription": transcription,
            }

        audio_path = generate_audio(outcome["next_question"])
        audio_url = f"{BASE_URL}/static/audio/{os.path.basename(audio_path)}" if audio_path else None

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



# ---------------------------------------------------------------------------
# Task 2.3 — Candidate Ranking Endpoint (MOD-5)
# ---------------------------------------------------------------------------
# NOTE: This endpoint is intentionally unauthenticated until Phase 3 (Task 3.2)
# adds Firebase token verification.  Add auth before exposing to production.
# Known limitation: ranker has perfect NDCG due to data leakage in training
# triplets — see Task 4.3 for the fix.  Rankings are directionally useful but
# scores should not be treated as absolute ground truth until retrained.

class RankCandidatesRequest(BaseModel):
    session_ids: list[str]


@app.post("/candidates/rank")
@limiter.limit("20/minute")
async def rank_candidates(request: Request, body: RankCandidatesRequest = Body(...), uid: str = Depends(verify_firebase_token)):
    """
    Rank a list of completed interview sessions by candidate quality.

    Body: {"session_ids": ["abc123", "def456", ...]}

    Returns candidates sorted best-to-worst by cosine similarity of their
    aggregate 8-D feature vector to the ideal-candidate anchor.
    """
    from recommender.feature_store import extract_candidate_features, build_ideal_profile
    import torch
    import torch.nn.functional as F

    if not body.session_ids:
        raise HTTPException(status_code=422, detail="session_ids must not be empty")

    ranker = registry.load_candidate_ranker()
    device = next(ranker.parameters()).device
    ideal  = build_ideal_profile().to(device)

    with torch.no_grad():
        ideal_emb = ranker(ideal)          # (1, 32) L2-normalised embedding

    ranked = []
    skipped = []

    for sid in body.session_ids:
        features = extract_candidate_features(sid)
        if features is None:
            skipped.append({"session_id": sid, "reason": "session not found or no evaluations"})
            continue
        try:
            with torch.no_grad():
                cand_emb  = ranker(features.to(device))           # (1, 32)
                similarity = F.cosine_similarity(cand_emb, ideal_emb).item()
            ranked.append({"session_id": sid, "score": round(similarity, 4)})
        except Exception as e:
            skipped.append({"session_id": sid, "reason": str(e)})

    ranked.sort(key=lambda x: x["score"], reverse=True)

    return {
        "ranked": ranked,
        "skipped": skipped,
        "note": (
            "Ranking uses cosine similarity to an ideal-candidate anchor. "
            "Known data-leakage issue in training data (Task 4.3) — treat as "
            "directional signal, not absolute ground truth."
        ),
    }


@app.get("/health")
async def health():
    """Liveness/readiness probe (H2). Reports per-model checkpoint status without
    loading anything heavy. Returns 200 always so the process counts as alive; the
    `models` map shows whether each checkpoint is present/loaded/missing."""
    models_status = {}
    try:
        for name, filename in registry.versions.items():
            path = os.path.join(registry.base_path, filename)
            if name in registry.loaded_models:
                models_status[name] = "loaded" if registry.loaded_models[name] is not None else "unavailable"
            else:
                models_status[name] = "present" if os.path.exists(path) else "missing"
    except Exception as e:
        models_status = {"error": str(e)}
    return {"status": "ok", "models": models_status}


@app.get("/metrics")
async def metrics():
    """Operational metrics for monitoring — no auth required."""
    uptime = round(_time.monotonic() - _SERVER_START_TIME, 1)
    models_status = {}
    try:
        for name, filename in registry.versions.items():
            path = os.path.join(registry.base_path, filename)
            if name in registry.loaded_models:
                models_status[name] = "loaded" if registry.loaded_models[name] is not None else "unavailable"
            else:
                models_status[name] = "present" if os.path.exists(path) else "missing"
    except Exception as e:
        models_status = {"error": str(e)}
    return {"uptime_seconds": uptime, "models": models_status}


@app.get("/api/proctoring/{session_id}")
async def get_proctoring_timeline(session_id: str, uid: str = Depends(verify_firebase_token)):
    """Retrieve the full proctoring timeline for a session.
    
    Used by the HR dashboard and FeedbackReport to show integrity alerts.
    """
    record = get_session(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
        
    state = record.get("state_data", {})
    history = state.get("proctoring_history", [])
    
    # Simple aggregate if _aggregate_session_integrity hasn't run yet
    total_violations = sum(h.get("violation_count", 0) for h in history)
    max_suspicion = max([h.get("suspicion_score", 0) for h in history] + [0])
    
    return {
        "session_id": session_id,
        "total_violations": total_violations,
        "max_suspicion_score": max_suspicion,
        "per_answer_integrity": history
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
